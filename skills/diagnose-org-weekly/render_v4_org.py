"""V4 超表适配器（org-weekly 版）。

从 SectionContext + drill_long_df 构造行数据，调用壳库 supertable.* 组件渲染。
org 特征适配：
  - 5 YTD 窗口（上季度/上月/上上周/上周/当周），ytd_idx=4、对比基准=上周(idx=3)
  - 指标列复用壳库 JS 硬编码的 vcr/lr/freq/avg（无 coef：org 标准指标不含自主系数，
    coef 列以 null 占位并默认隐藏，避免 SUPERTABLE_JS 的 expand-row 遍历 5 指标时崩溃）
  - 对比口径：vs 上周 / vs 警戒线（壳库默认的 yoy/m12/warn 中 yoy 复用为"上周"）
  - 交叉下钻暂关闭（group_to_sec_id / drill_dims_v4 传空 → buildCrossDimSection 返回空）
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Optional

# 复用 render_v1_org 的段定义与工具
from render_v1_org import (
    _safe,
    PERIOD_ORDER_ORG, YTD_IDX, PREV_IDX,
    SECTION_DEFS_ORG, build_section_defs,
)

# 行 metrics 键(与壳库 SUPERTABLE_JS METRIC_DEFS 的 id 严格对齐)→ standard/drill 列名 + 打灯 key。
# coef 槽位复用为 expense_ratio_pct(org 无自主系数,JS 显示标签"费用率")。
# plan/grow/rnw/hh 4 个新槽位的列名对齐 standard_query / drill_long_df 输出(由
# ctx.standard_rows / drill_long_df 提供;无对应列时 series 自动为 None)。
V4_METRIC_MAP = [
    ("vcr",  "variable_cost_ratio_pct", "variable_cost_ratio_pct"),
    ("lr",   "earned_loss_ratio_pct",   "earned_loss_ratio_pct"),
    ("freq", "earned_loss_freq_pct",    "earned_loss_freq_pct"),
    ("avg",  "avg_claim",               None),
    ("coef", "expense_ratio_pct",       "expense_ratio_pct"),
    ("plan", "plan_completion_pct",     "plan_completion_pct"),
    ("grow", "premium_growth_pct",      "premium_growth_pct"),
    ("rnw",  "renewal_rate_pct",        "renewal_rate_pct"),
    ("hh",   "household_share_pct",     "household_share_pct"),
]

# 控制条指标 pill(9 个;coef 槽位展示为"费用率")
ORG_V4_METRIC_DEFS = [
    ("vcr",  "变率"),
    ("lr",   "赔付率"),
    ("freq", "出险率"),
    ("avg",  "案均"),
    ("coef", "费用率"),
    ("plan", "达成率"),
    ("grow", "增长率"),
    ("rnw",  "续保率"),
    ("hh",   "家车占比"),
]

# 组名 → 段 ID（供 V4 交叉下钻 buildCrossDimSection）
ORG_V4_GROUP_TO_SEC_ID = {
    "客户类别": "customer",
    "销售团队": "team",
    "险类":     "insurance",
    "险别组合": "combo",
    "能源类型": "energy",
    "新旧车":   "newused",
    "是否过户": "transfer",
    "是否续保": "renewal",
}

# 段 ID → 可下钻次级维度 [(sec2_id, label), ...]（salesman 不作主维入口）
_ORG_V4_ALL_SECS = [
    ("customer", "客户类别"), ("insurance", "险类"), ("combo", "险别组合"),
    ("energy", "能源类型"), ("newused", "新旧车"), ("transfer", "是否过户"), ("renewal", "是否续保"),
]
ORG_V4_DRILL_DIMS = {
    sec_id: [(s2, lbl) for s2, lbl in _ORG_V4_ALL_SECS if s2 != sec_id]
    for sec_id, _ in _ORG_V4_ALL_SECS
}
ORG_V4_DRILL_DIMS["team"] = _ORG_V4_ALL_SECS  # team 可下钻所有 7 维（不含 team 自身）


def build_v4_drill(level: str = "org"):
    """按层级返回 (group_to_sec_id, drill_dims)。

    branch 层把 org3（三级机构）加进交叉维：org3 可下钻全部业务维，
    各业务维亦可下钻 org3；team 段重命名为「Top20 团队」。
    """
    if level != "branch":
        return ORG_V4_GROUP_TO_SEC_ID, ORG_V4_DRILL_DIMS
    all_secs = _ORG_V4_ALL_SECS + [("org3", "三级机构")]
    drill = {
        sec_id: [(s2, lbl) for s2, lbl in all_secs if s2 != sec_id]
        for sec_id, _ in all_secs
    }
    drill["team"] = all_secs  # Top20 团队 可下钻全部业务维 + 三级机构
    group_to_sec = {
        "客户类别": "customer", "Top20 团队": "team", "三级机构": "org3",
        "险类": "insurance", "险别组合": "combo", "能源类型": "energy",
        "新旧车": "newused", "是否过户": "transfer", "是否续保": "renewal",
    }
    return group_to_sec, drill

ORG_V4_COMPARE_OPTS = [("yoy", "vs 上周"), ("warn", "vs 警戒线")]
ORG_V4_SORT_OPTS = [
    ("default", "默认"), ("ytd-desc", "本年值↓"), ("delta-desc", "周Δ↓"),
    ("prem-desc", "保费↓"), ("name", "名称"),
]
# 期标签简称（与 PERIOD_ORDER_ORG 一一对应）
ORG_V4_PERIOD_LABELS = ["上季", "上月", "上上周", "上周", "当周"]


def _series_from_standard(standard_rows, col) -> list:
    """整体行：按窗口顺序取 standard_rows 的某列。"""
    out = []
    for r in standard_rows:
        v = _safe(r.get(col)) if (r is not None and col) else None
        out.append(round(v, 3) if v is not None else None)
    return out


def _series_from_cohort(cohort, period_labels, col) -> list:
    """维度行：按窗口顺序从 cohort（同一 dim_value 的多期行）取某列。"""
    out = []
    for plabel in period_labels:
        if not col:
            out.append(None)
            continue
        sub = cohort[cohort["period"] == plabel]
        v = _safe(sub.iloc[0].get(col)) if not sub.empty else None
        out.append(round(v, 3) if v is not None else None)
    return out


def _build_metrics_and_deltas(series_by_col, warn_vals):
    """由 {col: series} 构造 metrics(按 metric id) + deltas(yoy=当周−上周 / warn=当周−警戒线)。"""
    metrics: dict[str, list] = {}
    for m_id, col, _wk in V4_METRIC_MAP:
        metrics[m_id] = series_by_col.get(col, [None] * len(PERIOD_ORDER_ORG)) if col else [None] * len(PERIOD_ORDER_ORG)

    deltas: dict[str, dict] = {}
    for m_id, _col, _wk in V4_METRIC_MAP:
        ser = metrics[m_id]
        ytd_v = ser[YTD_IDX] if YTD_IDX < len(ser) else None
        prev_v = ser[PREV_IDX] if PREV_IDX < len(ser) else None
        warn_v = warn_vals.get(m_id)
        deltas[m_id] = {
            "yoy": round(ytd_v - prev_v, 2) if (ytd_v is not None and prev_v is not None) else None,
            "m12": None,
            "warn": round(ytd_v - warn_v, 2) if (ytd_v is not None and warn_v is not None) else None,
        }
    return metrics, deltas


def _build_rows(ctx, drill_long_df, section_defs=None) -> tuple[list[dict], dict]:
    """构造 V4 行数据 + topbar meta。"""
    from lib import light, TH  # noqa: PLC0415

    period_labels = [w[0] for w in ctx.windows]

    # 警戒线（健康线 = TH[key][1]）；无阈值的 avg/coef → None
    warn_vals = {
        m_id: (TH.get(wk, (0, 0, 0))[1] if wk else None)
        for m_id, _col, wk in V4_METRIC_MAP
    }

    n_overall = ctx.sample_n[YTD_IDX] if YTD_IDX < len(ctx.sample_n) else 0
    overall_prem = _safe(ctx.total_premiums[YTD_IDX]) if YTD_IDX < len(ctx.total_premiums) else None
    overall_prem = overall_prem or 0.0
    meta = {
        "policies": f"{n_overall / 10000:.2f}" if n_overall else "—",
        "premium": f"{overall_prem / 10000:,.0f}" if overall_prem else "—",
    }

    rows: list[dict] = []

    _sec_defs = section_defs if section_defs is not None else SECTION_DEFS_ORG
    for sec_def in _sec_defs:
        sec_id = sec_def["id"]
        glabel = sec_def["label"]
        field = sec_def.get("field")

        if sec_id == "overall":
            series_by_col = {
                col: _series_from_standard(ctx.standard_rows, col)
                for _m, col, _wk in V4_METRIC_MAP if col
            }
            metrics, deltas = _build_metrics_and_deltas(series_by_col, warn_vals)
            vcr_ytd = metrics["vcr"][YTD_IDX]
            sev_cls, _ = light("variable_cost_ratio_pct", vcr_ytd, n_overall) if vcr_ytd is not None else ("alert-gray", "")
            rows.append({
                "group": "整体", "name": "整体", "key": "overall_0", "raw_val": "整体",
                "sev": sev_cls.replace("alert-", ""), "prem": 100.0,
                "metrics": metrics, "deltas": deltas, "n_pol": n_overall,
            })
            continue

        if drill_long_df is None or drill_long_df.empty or not field:
            continue
        dim_df = drill_long_df[drill_long_df["dim_key"] == field]
        if dim_df.empty:
            continue

        for i, dim_value in enumerate(dim_df["dim_value"].unique()):
            cohort = dim_df[dim_df["dim_value"] == dim_value]
            ytd_sub = cohort[cohort["period"] == period_labels[YTD_IDX]]
            n_pol = int(_safe(ytd_sub.iloc[0].get("policy_count")) or 0) if not ytd_sub.empty else 0
            prem_ytd = _safe(ytd_sub.iloc[0].get("premium")) if not ytd_sub.empty else None
            prem_share = round(prem_ytd / overall_prem * 100, 1) if (prem_ytd and overall_prem > 0) else None

            series_by_col = {
                col: _series_from_cohort(cohort, period_labels, col)
                for _m, col, _wk in V4_METRIC_MAP if col
            }
            metrics, deltas = _build_metrics_and_deltas(series_by_col, warn_vals)
            vcr_ytd = metrics["vcr"][YTD_IDX]
            sev_cls, _ = light("variable_cost_ratio_pct", vcr_ytd, n_pol) if vcr_ytd is not None else ("alert-gray", "")

            rows.append({
                "group": glabel, "name": str(dim_value),
                "key": f"{sec_id}_{i}", "raw_val": str(dim_value),
                "sev": sev_cls.replace("alert-", ""), "prem": prem_share,
                "metrics": metrics, "deltas": deltas, "n_pol": n_pol,
            })

    return rows, meta


def render_v4(ctx, drill_long_df, args):
    """生成 V4 超表 HTML。"""
    from lib.render.supertable import (
        SUPERTABLE_CSS,
        render_topbar, render_controls, render_footer, render_table_shell,
    )  # noqa: PLC0415

    org = ctx.org
    cutoff = ctx.cutoff
    cs = cutoff.isoformat()
    out_dir = Path(args.output)

    # 主题资源
    try:
        from themes_v2 import (FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
                               THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn)
    except ImportError:
        import importlib, sys
        sys.path.insert(0, str(Path.home() / ".claude/skills/diagnose-period-trend/lib"))
        _tv2 = importlib.import_module("themes_v2")
        FONT_LINKS, BASE_CSS = _tv2.FONT_LINKS, _tv2.BASE_CSS
        DARK_CSS, THEME_TOGGLE_CSS = _tv2.DARK_CSS, _tv2.THEME_TOGGLE_CSS
        THEME_INIT_SCRIPT, THEME_TOGGLE_JS = _tv2.THEME_INIT_SCRIPT, _tv2.THEME_TOGGLE_JS
        theme_toggle_btn = _tv2.theme_toggle_btn

    level = getattr(args, "level", "org")
    section_defs = build_section_defs(level)
    group_to_sec_id, drill_dims_v4 = build_v4_drill(level)
    rows, meta = _build_rows(ctx, drill_long_df, section_defs=section_defs)
    rows_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    dd_json = json.dumps(ctx.org_dd or {}, ensure_ascii=False, separators=(",", ":"))

    dash_href = f"{org}_{ctx.year}_cockpit.html"
    week_href = f"{org}_{ctx.year}_narrative.html"

    topbar = render_topbar(
        cutoff=cutoff, meta=meta,
        view_links=[(dash_href, "驾驶舱"), (week_href, "叙事")],
        title=f"{org} · 全字段超表",
        brand_mark=org[0], brand_text=f"{org} · 经营诊断周报",
        theme_toggle_btn=theme_toggle_btn(),
    )
    # sort_opts 不传:超表统一按"主指标(activeMetrics 第一个)组内从差到好"
    controls = render_controls(
        compare_opts=ORG_V4_COMPARE_OPTS,
        metric_defs=ORG_V4_METRIC_DEFS,
        default_metrics=["vcr", "lr"],
    )
    table_shell = render_table_shell(
        rows_json=rows_json,
        warn_json="{}",
        dd_json=dd_json,
        period_labels=ORG_V4_PERIOD_LABELS,
        group_to_sec_id=group_to_sec_id,
        drill_dims_v4=drill_dims_v4,
        ytd_idx=YTD_IDX,   # 当周 = idx 4
        yoy_idx=PREV_IDX,  # 对比基准 = 上周 idx 3
        m12_idx=PREV_IDX,  # org 无滚动12月，占位为有效索引
        compare_labels={"yoy": "上周", "warn": "警戒线"},
    )
    footer = render_footer(dash_href=dash_href, week_href=week_href)

    page = f"""<!doctype html>
<html lang="zh-CN" data-theme="ink">
<head>
<meta charset="utf-8"/>
<title>{org} {ctx.year} 超表 · {cs}</title>
<meta name="viewport" content="width=1600, initial-scale=1"/>
{FONT_LINKS}
<style>
{BASE_CSS}
{DARK_CSS}
{THEME_TOGGLE_CSS}
{SUPERTABLE_CSS}
</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{topbar}
{controls}
<div class="table-wrap">
  {table_shell}
</div>
{footer}
<script>{THEME_TOGGLE_JS}</script>
</body>
</html>"""

    out_path = out_dir / f"{org}_{ctx.year}_table.html"
    out_path.write_text(page, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"      [v4] 已写入：{out_path}（{size_kb:.1f} KB · {len(rows)} 行）")
