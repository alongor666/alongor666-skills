"""V1 驾驶舱适配器（org-weekly 版）。

从 SectionContext + drill_long_df 提取数据，调用壳库 dashboard.py 组件渲染。
保留 org-weekly 的 5 YTD 窗口、7 维度、9 指标数据，渲染为 DPT 驾驶舱风格。
"""
from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path
from typing import Optional

# ── 共享常量 ──────────────────────────────────────────────────────

PERIOD_ORDER_ORG = ["上季度", "上月", "上上周", "上周", "当周"]
YTD_IDX = 4  # "当周" 在 5 期中的索引
PREV_IDX = 3  # "上周"

# 10 段定义，顺序对齐 legacy SECTIONS：整体 → 客户 → 团队 → 业务员 → 险类 …
# field 即 drill_long_df 中的 dim_key；customer/team/salesman 的 dim_key 分别为
# customer_category / team / salesman（后两者来自 fetch_team_salesman_periods）。
SECTION_DEFS_ORG = [
    {"id": "overall",    "label": "整体指标",   "kind": "overall"},
    {"id": "customer",   "label": "客户类别",   "kind": "cat", "field": "customer_category"},
    {"id": "team",       "label": "销售团队",   "kind": "org", "field": "team"},
    {"id": "salesman",   "label": "Top 业务员", "kind": "org", "field": "salesman"},
    {"id": "insurance",  "label": "险类",       "kind": "aux", "field": "insurance_type"},
    {"id": "combo",      "label": "险别组合",   "kind": "aux", "field": "coverage_combination"},
    {"id": "energy",     "label": "能源类型",   "kind": "aux", "field": "is_nev"},
    {"id": "newused",    "label": "新旧车",     "kind": "aux", "field": "is_new_car"},
    {"id": "transfer",   "label": "是否过户",   "kind": "aux", "field": "is_transfer"},
    {"id": "renewal",    "label": "是否续保",   "kind": "aux", "field": "is_renewal"},
]

# salesman 基数大：明细段只展示按 YTD 保费排序的前 N 名
SALESMAN_TOP_N = 15

# V1 首屏 8 KPI(指标列名, 中文标签, 亮灯 key)
# 顺序:综合(VCR) → 运营管理(达成/增长/续保) → 结构(家车) → 拆分指标(费用/赔付/出险)
ORG_KPI_DEFS = [
    ("variable_cost_ratio_pct",  "变动成本率", "variable_cost_ratio_pct"),
    ("plan_completion_pct",      "计划达成率", "plan_completion_pct"),
    ("premium_growth_pct",       "增长率",     "premium_growth_pct"),
    ("renewal_rate_pct",         "续保率",     "renewal_rate_pct"),
    ("household_share_pct",      "家车占比",   "household_share_pct"),
    ("expense_ratio_pct",        "费用率",     "expense_ratio_pct"),
    ("earned_loss_ratio_pct",    "满期赔付率", "earned_loss_ratio_pct"),
    ("earned_loss_freq_pct",     "满期出险率", "earned_loss_freq_pct"),
]

# 折叠明细中可切换的 9 个指标 tab
# 格式：(col_id, label, kind)  col_id 对应 drill_long_df 的列名
ORG_METRIC_TABS = [
    ("premium",              "保费",   "wan"),
    ("premium_share_pct",    "占比",   "pct"),
    ("plan_completion_pct",  "达成率", "pct"),
    ("premium_growth_pct",   "增长率", "pct"),
    ("variable_cost_ratio_pct", "变率", "pct"),
    ("expense_ratio_pct",    "费用率", "pct"),
    ("earned_loss_ratio_pct","赔付率", "pct"),
    ("avg_claim",            "案均",   "money"),
    ("renewal_rate_pct",     "续保率", "pct"),
]

# data-kinds 字符串（对齐 ORG_METRIC_TABS 顺序，供 switchMetric JS）
_ORG_METRIC_KINDS = "/".join(kind for _, _, kind in ORG_METRIC_TABS)

# 下钻面板专属指标（对齐 build_org_drilldown_data DD 输出 series 顺序）
# DD row: [disp, sev_int, vcr_series, lr_series, freq_series, avg_series]
# seriesOffset = 2 + metricIdx → 0→r[2]=vcr, 1→r[3]=lr, 2→r[4]=freq, 3→r[5]=avg
ORG_DRILL_PANEL_METRICS = [
    ("variable_cost_ratio_pct", "变率",   "pct"),
    ("earned_loss_ratio_pct",   "赔付率", "pct"),
    ("earned_loss_freq_pct",    "出险率", "pct"),
    ("avg_claim",               "案均",   "money"),
]

# dim_key → section_id 映射
DIM_KEY_TO_SEC = {
    "customer_category": "customer",
    "team": "team",
    "salesman": "salesman",
    "insurance_type": "insurance",
    "coverage_combination": "combo",
    "is_nev": "energy",
    "is_new_car": "newused",
    "is_transfer": "transfer",
    "is_renewal": "renewal",
}


# ── 层级感知段定义（org=三级机构 / branch=分公司）──────────────────
# 分公司层：salesman 段 → org_level_3（三级机构，sec_id="org3" 对齐交叉数据 prim_sec_id）；
#           team 段重命名为「Top20 团队」（数据侧已按签单保费 YTD 截取前 20）。

def build_section_defs(level: str = "org", skip: set[str] | None = None) -> list[dict]:
    """按层级返回段定义列表。

    skip 为要剔除的 section id 集合（如 {"team","org3"}）。branch 层业务员段
    实际是 org3（三级机构），故 skip 判 org3；team 段判 team。
    """
    skip = skip or set()
    if level != "branch":
        return [dict(s) for s in SECTION_DEFS_ORG if s["id"] not in skip]
    out = []
    for s in SECTION_DEFS_ORG:
        if s["id"] == "salesman":
            if "org3" not in skip:
                out.append({"id": "org3", "label": "三级机构", "kind": "org", "field": "org_level_3"})
        elif s["id"] == "team":
            if "team" not in skip:
                out.append({**s, "label": "Top20 团队"})
        else:
            if s["id"] not in skip:
                out.append(dict(s))
    return out


def build_dim_key_to_sec(level: str = "org") -> dict:
    """dim_key → section_id 映射（分公司层用 org_level_3→org3 替代 salesman）。"""
    m = dict(DIM_KEY_TO_SEC)
    if level == "branch":
        m.pop("salesman", None)
        m["org_level_3"] = "org3"
    return m


# ── 驾驶舱布局 CSS（从 DPT render_v1.py V1_PAGE_CSS 提取）──────

V1_PAGE_CSS = """
/* topbar */
.topbar{
  position: sticky; top: 0; z-index: 50;
  background: var(--paper); border-bottom: 1px solid var(--line);
  padding: 14px 32px; display: flex; align-items: center; gap: 18px;
}
.topbar .brand{ display: flex; align-items: center; gap: 8px; color: var(--ink); font-weight: 600; }
.topbar .brand-mark{
  width: 24px; height: 24px; border-radius: 5px; background: var(--navy);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 13px; font-weight: 700; letter-spacing: -.5px;
}
.topbar h1{ font-family:'Noto Serif SC',serif; font-size: 18px; font-weight: 500; margin: 0; letter-spacing: .02em; }
.topbar .date-pill{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border: 1px solid var(--line); background: var(--surface);
  border-radius: var(--radius); font-size: 13px; color: var(--ink-soft);
}
.topbar .meta{ color: var(--ink-mute); font-size: 13px; }
.topbar .meta b{ color: var(--ink-soft); font-weight: 500; }

/* shell */
.shell{ display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }
.rail{
  position: sticky; top: 53px; align-self: start;
  height: calc(100vh - 53px); padding: 20px 0;
  border-right: 1px solid var(--line); overflow-y: auto; background: var(--paper);
}
.rail h6{ font-size: 11px; color: var(--ink-mute); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 500; margin: 0 0 8px 26px; }
.rail ul{ list-style: none; padding: 0; margin: 0; }
.rail li{
  padding: 7px 26px; font-size: 13.5px; color: var(--ink-soft); cursor: pointer;
  border-left: 2px solid transparent; display: flex; align-items: center; justify-content: space-between;
}
.rail li:hover{ color: var(--ink); background: var(--paper-soft); }
.rail li .alert{ font-size: 11px; padding: 1px 6px; border-radius: 8px; background: var(--red-soft); color: var(--red); font-weight: 500; }
.rail li .alert.org{ background: var(--orange-soft); color: var(--orange); }

.main{ padding: 24px 32px 60px; max-width: 1240px; }
.section-tag{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--ink-mute);
  text-transform: uppercase; letter-spacing: 1.5px; font-weight: 500; margin-bottom: 8px;
}
.section-tag .bar{ width: 18px; height: 1.5px; background: var(--ink-mute); }
.h-section{ font-family:'Noto Serif SC',serif; font-size: 22px; font-weight: 500; margin: 0 0 16px; }

/* KPI */
.kpi-grid{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
.kpi{
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px; position: relative; overflow: hidden;
}
.kpi .label{ font-size: 12px; color: var(--ink-mute); margin-bottom: 6px; display:flex; align-items:center; gap:6px; }
.kpi .value-row{ display: flex; align-items: baseline; gap: 8px; }
.kpi .value{ font-family:'Noto Serif SC',serif; font-size: 30px; font-weight: 500; line-height: 1; color: var(--ink); font-variant-numeric: tabular-nums; }
.kpi .delta{ font-size: 12px; padding: 2px 7px; border-radius: 3px; font-weight: 500; background: var(--paper-soft); color: var(--ink-soft); }
.kpi .delta.red{ background: var(--red-soft); color: var(--red); }
.kpi .delta.org{ background: var(--orange-soft); color: var(--orange); }
.kpi .delta.gn{ background: var(--green-soft); color: var(--green); }
.kpi .sub{ font-size: 11.5px; color: var(--ink-mute); margin-top: 6px; }
.kpi .spark{ margin-top: 10px; }
.kpi.alert::before{ content:''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--orange); }
.kpi.alert.red::before{ background: var(--red); }

/* anomaly card */
.anom-grid{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px; }
.anom-card{
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px; cursor: pointer; position: relative;
  transition: all .14s ease;
}
.anom-card:hover{ box-shadow: var(--shadow-md); transform: translateY(-1px); border-color: var(--line-strong); }
.anom-card .rank{ position: absolute; top: 12px; right: 14px; font-family:'Noto Serif SC',serif; font-size: 14px; color: var(--ink-light); font-weight: 500; }
.anom-card .head{ display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.anom-card .dim{ font-size: 11px; color: var(--ink-mute); }
.anom-card .tag{ font-size: 14.5px; font-weight: 600; color: var(--ink); margin-bottom: 2px; }
.anom-card .value-row{ display: flex; align-items: baseline; gap: 10px; margin: 10px 0 6px; }
.anom-card .value{ font-family:'Noto Serif SC',serif; font-size: 28px; font-weight: 500; line-height: 1; font-variant-numeric: tabular-nums; }
.anom-card .delta{ font-size: 13px; font-weight: 500; }
.anom-card .delta.red{ color: var(--red); }
.anom-card .delta.org{ color: var(--orange); }
.anom-card .spark{ margin: 6px 0 8px; }
.anom-card .foot{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 8px; gap: 8px; }
.anom-card .reason{ font-size: 11.5px; color: var(--ink-soft); line-height: 1.4; flex: 1; }
.anom-card .prem{ font-size: 10.5px; color: var(--ink-mute); text-align: right; white-space: nowrap; }
.anom-card .drill-hint{ opacity: 0; transition: opacity .14s; position: absolute; bottom: 8px; right: 12px; font-size: 11px; color: var(--navy); }
.anom-card:hover .drill-hint{ opacity: 1; }

/* section detail (折叠卡) */
.det-card{ background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); margin-bottom: 12px; overflow: hidden; }
.det-head{ padding: 14px 18px; display: flex; align-items: center; gap: 14px; cursor: pointer; border-bottom: 1px solid transparent; transition: background .12s; }
.det-head:hover{ background: var(--surface-soft); }
.det-card.open .det-head{ border-bottom-color: var(--line); }
.det-head .idx{ font-family:'Noto Serif SC',serif; font-size: 13px; color: var(--ink-light); font-weight: 500; width: 28px; }
.det-head .name{ font-size: 15px; font-weight: 600; color: var(--ink); }
.det-head .status{ display: flex; gap: 6px; margin-left: 12px; }
.det-head .chip{ font-size: 11px; padding: 2px 7px; border-radius: 9px; background: var(--paper-soft); color: var(--ink-soft); }
.det-head .chip.warn{ background: var(--red-soft); color: var(--red); }
.det-head .chip.mid{ background: var(--orange-soft); color: var(--orange); }
.det-head .chip.ok{ background: var(--green-soft); color: var(--green); }
.det-head .findings{ flex: 1; margin: 0 16px; color: var(--ink-mute); font-size: 12.5px; }
.det-head .findings b{ color: var(--ink); font-weight: 500; }
.det-head .caret{ color: var(--ink-mute); font-size: 12px; }
.det-body{ padding: 6px 18px 18px; display: none; }
.det-card.open .det-body{ display: block; }

.dtab{ width: 100%; border-collapse: collapse; font-size: 13px; }
.dtab th, .dtab td{ padding: 8px 10px; text-align: right; }
.dtab th{ font-weight: 500; font-size: 11.5px; color: var(--ink-mute); border-bottom: 1px solid var(--line); }
.dtab th.thlt, .dtab td.tdlt{ text-align: left; }
.dtab th.thcur{ background: var(--navy); color: var(--paper); font-weight: 600; }
.dtab td.tdcur{ background: var(--navy-soft); color: var(--ink); font-weight: 600; }
.dtab tbody tr{ border-bottom: 1px solid var(--line-soft); }
.dtab tbody tr:hover{ background: var(--surface-soft); }
.dtab .obj-name{ color: var(--navy); font-weight: 500; }
"""


# ── 工具函数 ──────────────────────────────────────────────────────

def _safe(v) -> Optional[float]:
    if v is None: return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _e(s: str) -> str:
    return html.escape(str(s))


def _fmt(v: Optional[float], kind: str = "pct") -> str:
    f = _safe(v)
    if f is None: return "—"
    if kind == "pct":   return f"{f:.1f}%"
    if kind == "coef":  return f"{f:.3f}"
    if kind == "money": return f"¥{f:,.0f}"
    if kind == "wan":   return f"{round(f / 10000):,}"
    return f"{f:.2f}"


def _fmt_delta(d: Optional[float]) -> str:
    f = _safe(d)
    if f is None: return "—"
    return f"{f:+.1f} PP"


# ── 数据提取 ──────────────────────────────────────────────────────

def _extract_kpi_cards(ctx) -> list[dict]:
    """从 ctx.standard_rows 构造 5 KPI 卡片数据。"""
    from lib import light, sparkline  # noqa: PLC0415

    cards = []
    n_ytd = ctx.sample_n[YTD_IDX] if ctx.sample_n else 0
    for col, label, alert_key in ORG_KPI_DEFS:
        # 5 期值
        series = [_safe(r.get(col)) if r is not None else None for r in ctx.standard_rows]
        val_ytd = series[YTD_IDX]
        val_prev = series[PREV_IDX] if PREV_IDX is not None else None

        # delta = 当周 − 上周
        delta = None
        if val_ytd is not None and val_prev is not None:
            delta = val_ytd - val_prev

        # 亮灯
        sev = ""
        if val_ytd is not None and alert_key:
            sev, _ = light(alert_key, val_ytd, n_ytd)

        cards.append({
            "label": label,
            "value": _fmt(val_ytd),
            "delta": _fmt_delta(delta),
            "sub": "vs 上周",
            "sev": sev,
            "spark6": series,
        })
    return cards


def _extract_anomalies(
    ctx, drill_long_df,
    section_defs=None, dim_key_to_sec=None,
) -> tuple[list, list[str]]:
    """从 drill_long_df 提取各维度 Top 异常。

    Returns:
        (anomalies, sec_ids) — 等长列表，sec_ids[i] 是 anomalies[i] 所属段 ID，
        供 render_anomaly_grid 注入 data-secid，openDrawer JS 定位并展开对应段。
    """
    from lib import light  # noqa: PLC0415
    from lib.render.dashboard import AnomalyCard  # noqa: PLC0415

    if drill_long_df is None or drill_long_df.empty:
        return [], []

    ytd_period = ctx.windows[YTD_IDX][0]
    ytd_df = drill_long_df[drill_long_df["period"] == ytd_period]
    if ytd_df.empty:
        return [], []

    overall_prem = _safe(ctx.total_premiums[YTD_IDX]) or 1.0

    pairs: list[tuple] = []  # (AnomalyCard, sec_id)
    for _, row in ytd_df.iterrows():
        vcr = _safe(row.get("variable_cost_ratio_pct"))
        if vcr is None: continue
        n_pol = int(_safe(row.get("policy_count")) or 0)

        sev, _ = light("variable_cost_ratio_pct", vcr, n_pol)
        if sev not in ("alert-red", "alert-yellow"): continue

        dim_key = row["dim_key"]
        dim_value = row["dim_value"]
        cohort = drill_long_df[
            (drill_long_df["dim_key"] == dim_key) &
            (drill_long_df["dim_value"] == dim_value)
        ]
        series = [_safe(w_row.get("variable_cost_ratio_pct")) for _, w_row in cohort.iterrows()]
        while len(series) < 5: series.append(None)

        prem = _safe(row.get("premium")) or 0
        prem_share = round(prem / overall_prem * 100, 1) if overall_prem > 0 else 0

        prev_period = ctx.windows[PREV_IDX][0]
        prev_cohort = cohort[cohort["period"] == prev_period]
        prev_vcr = _safe(prev_cohort.iloc[0].get("variable_cost_ratio_pct")) if not prev_cohort.empty else None
        delta = vcr - prev_vcr if prev_vcr is not None else None

        _sec_defs = section_defs if section_defs is not None else SECTION_DEFS_ORG
        _dk2s = dim_key_to_sec if dim_key_to_sec is not None else DIM_KEY_TO_SEC
        sec_id = _dk2s.get(dim_key, dim_key)
        sec_def = next((s for s in _sec_defs if s["id"] == sec_id), None)

        note = f"{'🔴' if sev == 'alert-red' else '🟡'} {_e(dim_value)} 变率 {_fmt(vcr)}"
        if delta is not None:
            direction = "上升" if delta > 0 else "下降"
            note += f"，周{direction} {abs(delta):.1f} pp"

        pairs.append((AnomalyCard(
            rank=0, metric_label="变动成本率", dim_display=dim_value,
            value=vcr, delta_vs_yoy=delta or 0, spark6=series,
            note=note, premium_share=prem_share, sev=sev,
        ), sec_id))

    sev_order = {"alert-red": 0, "alert-yellow": 1}
    pairs.sort(key=lambda p: (sev_order.get(p[0].sev, 9), -p[0].value))

    anomalies, sec_ids = [], []
    for i, (a, sid) in enumerate(pairs[:8], 1):
        anomalies.append(AnomalyCard(
            rank=i, metric_label=a.metric_label, dim_display=a.dim_display,
            value=a.value, delta_vs_yoy=a.delta_vs_yoy, spark6=a.spark6,
            note=a.note, premium_share=a.premium_share, sev=a.sev,
        ))
        sec_ids.append(sid)
    return anomalies, sec_ids


# 明细段指标 → (col_id 与 ORG_METRIC_TABS 对齐, drill_long_df 列名, 是否打灯)
# col_id 用于 data-vals-{col_id} / data-sev-{col_id} 属性注入，供 switchMetric JS 读取
SECTION_METRIC_MAP = [
    ("premium",              "premium",              False),
    ("premium_share_pct",    "premium_share_pct",    False),
    ("plan_completion_pct",  "plan_completion_pct",  True),
    ("premium_growth_pct",   "premium_growth_pct",   False),
    ("variable_cost_ratio_pct", "variable_cost_ratio_pct", True),
    ("expense_ratio_pct",    "expense_ratio_pct",    True),
    ("earned_loss_ratio_pct","earned_loss_ratio_pct",True),
    ("avg_claim",            "avg_claim",            False),
    ("renewal_rate_pct",     "renewal_rate_pct",     True),
]


def _extract_section_details(ctx, drill_long_df, section_defs=None) -> list[dict]:
    """构造 N 段折叠明细数据（整体 + 各下钻维度）。"""
    from lib import light  # noqa: PLC0415
    from lib.render.dashboard import SectionDetail  # noqa: PLC0415

    details = []
    period_labels = [w[0] for w in ctx.windows]

    # 1. 整体段
    overall_rows = []
    for col, label, _kind in ORG_METRIC_TABS:
        series = [_safe(r.get(col)) if r is not None else None for r in ctx.standard_rows]
        sev = ""
        val_ytd = series[YTD_IDX] if YTD_IDX < len(series) else None
        if val_ytd is not None:
            n_ytd = ctx.sample_n[YTD_IDX] if YTD_IDX < len(ctx.sample_n) else 0
            sev, _ = light(col, val_ytd, n_ytd)
        # kind 传给 overall 段表体，保费用 wan（万元绝对值）、率值用 pct
        # wan 类指标在名称后标注「(万)」单位（单元格只显示数字，不带万后缀）
        row_name = f"{label}(万)" if _kind == "wan" else label
        overall_rows.append({"name": row_name, "spark6": series, "sev": sev, "kind": _kind})
    details.append(SectionDetail(
        id="overall", label="整体指标", kind="overall",
        rows=overall_rows, section_index=1, default_open=True,
    ))

    # 2-N. 维度段
    if drill_long_df is None or drill_long_df.empty:
        return details

    _sec_defs = section_defs if section_defs is not None else SECTION_DEFS_ORG
    for sec_def in _sec_defs[1:]:  # 跳过 overall
        sec_id = sec_def["id"]
        field = sec_def.get("field")
        if not field: continue
        dim_key = field  # drill_long_df 中 dim_key 即字段名 / team / salesman

        dim_df = drill_long_df[drill_long_df["dim_key"] == dim_key]
        if dim_df.empty: continue

        rows = []
        for dim_value in dim_df["dim_value"].unique():
            cohort = dim_df[dim_df["dim_value"] == dim_value]

            # 每个指标的 N 期系列（按窗口顺序）
            values_by_metric: dict[str, list] = {}
            for metric_id, col, _do_light in SECTION_METRIC_MAP:
                ser = []
                for plabel in period_labels:
                    sub = cohort[cohort["period"] == plabel]
                    # D1 回退：非 team/salesman 维度的达成率列强制 None
                    if metric_id == "plan_completion_pct" and dim_key not in ("team", "salesman"):
                        ser.append(None)
                    else:
                        ser.append(_safe(sub.iloc[0].get(col)) if not sub.empty else None)
                values_by_metric[metric_id] = ser

            n_ytd = 0
            ytd_sub = cohort[cohort["period"] == period_labels[YTD_IDX]]
            if not ytd_sub.empty:
                n_ytd = int(_safe(ytd_sub.iloc[0].get("policy_count")) or 0)

            # 各指标 YTD 亮灯
            sev_by_metric: dict[str, str] = {}
            for metric_id, col, do_light in SECTION_METRIC_MAP:
                if not do_light:
                    continue
                v = values_by_metric[metric_id][YTD_IDX] if YTD_IDX < len(values_by_metric[metric_id]) else None
                if v is not None:
                    cls, _ = light(col, v, n_ytd)
                    sev_by_metric[metric_id] = cls

            vcr_series = values_by_metric.get("variable_cost_ratio_pct", [])
            sev = sev_by_metric.get("variable_cost_ratio_pct", "")
            prem_ytd = _safe(ytd_sub.iloc[0].get("premium")) if not ytd_sub.empty else None

            rows.append({
                "name": str(dim_value),
                "spark6": vcr_series,
                "sev": sev,
                "values_by_metric": values_by_metric,
                "sev_by_metric": sev_by_metric,
                "_prem_ytd": prem_ytd or 0,
            })

        # salesman：按 YTD 保费降序取 Top N；其余段：按 YTD 变率降序
        if sec_id == "salesman":
            rows.sort(key=lambda r: r["_prem_ytd"], reverse=True)
            rows = rows[:SALESMAN_TOP_N]
        else:
            rows.sort(
                key=lambda r: r["spark6"][YTD_IDX]
                if YTD_IDX < len(r.get("spark6", [])) and r["spark6"][YTD_IDX] is not None
                else 0,
                reverse=True,
            )

        details.append(SectionDetail(
            id=sec_id, label=sec_def["label"], kind=sec_def["kind"],
            rows=rows, section_index=len(details) + 1,
        ))

    return details


def _org_tbody_dim(
    rows: list[dict],
    sec_id: str,
    period_order: list[str],
    ytd_label: str,
) -> str:
    """org-weekly 专属维度段表体（修正 dashboard._section_tbody_dim 两处 DPT-vs-org 不兼容）。

    1. VCR key 用 "variable_cost_ratio_pct"（DPT 用 "variable_cost_ratio"）
    2. data-kinds 对齐 ORG_METRIC_TABS 9 指标顺序（DPT 硬编码 6 指标）
    """
    from lib import sparkline as _spark  # noqa: PLC0415
    po = period_order
    n_cols = len(po)
    body_rows = []
    for r in rows:
        vm = r.get("values_by_metric", {})
        vcr_vals = vm.get("variable_cost_ratio_pct", [None] * n_cols)
        spark_svg = _spark(vcr_vals, color_mode="trend", width=100, height=28)
        data_attrs = []
        for col, _lbl, _kind in ORG_METRIC_TABS:
            vals = vm.get(col, [None] * n_cols)
            vals_str = "/".join(
                "" if v is None or (isinstance(v, float) and math.isnan(v))
                else f"{float(v):.6g}"
                for v in vals
            )
            data_attrs.append(f'data-vals-{col.replace("_", "-")}="{vals_str}"')
        for col, sev_cls in r.get("sev_by_metric", {}).items():
            data_attrs.append(f'data-sev-{col.replace("_", "-")}="{sev_cls}"')
        data_attrs.append(f'data-kinds="{_ORG_METRIC_KINDS}"')
        raw_v = _e(str(r.get("name", "")))
        cells = "".join(
            f'<td class="cell-{i}{" tdcur" if po[i] == ytd_label else ""}">'
            f'<span class="num">{_fmt(vcr_vals[i] if i < len(vcr_vals) else None, "pct")}</span>'
            f'</td>'
            for i in range(n_cols)
        )
        body_rows.append(
            f'<tr {" ".join(data_attrs)}>'
            f'<td class="tdlt obj-name drill-trigger" '
            f'data-sec="{sec_id}" data-rawval="{raw_v}" data-disp="{raw_v}">'
            f'{raw_v}</td>'
            f'<td class="tdlt trend-cell">{spark_svg}</td>{cells}</tr>'
        )
    return f'<tbody>{"".join(body_rows)}</tbody>'


# ── 主入口 ────────────────────────────────────────────────────────

def _build_org_drill_dims(level: str = "org") -> dict:
    """构造各段可下钻目标维度定义。

    org 层：salesman 不作下钻入口，team→salesman。
    branch 层：org3（三级机构）作下钻入口并可钻到全部业务维；其他业务维亦可钻到 org3。
    """
    _ALL = [
        ("customer", "客户类别"), ("insurance", "险类"), ("combo", "险别组合"),
        ("energy", "能源类型"), ("newused", "新旧车"), ("transfer", "是否过户"),
        ("renewal", "是否续保"), ("team", "销售团队"),
    ]
    section_defs = build_section_defs(level)
    if level == "branch":
        _ALL = _ALL + [("org3", "三级机构")]
        skip = ("overall",)  # org3 是下钻入口，team 保留
    else:
        skip = ("overall", "salesman")
    drill_dims: dict[str, list] = {}
    for sec_def in section_defs:
        sec_id = sec_def["id"]
        if sec_id in skip:
            continue
        targets = [(s2_id, s2_lbl) for s2_id, s2_lbl in _ALL if s2_id != sec_id]
        if level != "branch" and sec_id == "team":
            targets.append(("salesman", "Top 业务员"))
        drill_dims[sec_id] = targets
    return drill_dims


def render_v1(ctx, drill_long_df, args):
    """生成 V1 驾驶舱 HTML。"""
    import json as _json  # noqa: PLC0415
    from lib import light  # noqa: PLC0415
    from lib.render.dashboard import (
        render_topbar, render_rail, render_kpi_strip,
        render_anomaly_grid, render_section_detail,
        render_metric_tabs, render_drill_panel,
        dashboard_interact_js, DRILL_PANEL_CSS,
    )  # noqa: PLC0415

    org = ctx.org
    cutoff = ctx.cutoff
    cs = cutoff.isoformat()
    out_dir = Path(args.output)
    level = getattr(args, "level", "org")
    skip = getattr(args, "skip_sections", None) or set()
    section_defs = build_section_defs(level, skip=skip)
    dim_key_to_sec = build_dim_key_to_sec(level)

    # 1. KPI 卡
    kpi_cards = _extract_kpi_cards(ctx)
    kpi_html = render_kpi_strip(kpi_cards)

    # 2. 异常卡（含 sec_ids → data-secid → openDrawer 定位段）
    anomalies, anom_sec_ids = _extract_anomalies(
        ctx, drill_long_df, section_defs=section_defs, dim_key_to_sec=dim_key_to_sec,
    )
    anomaly_html = render_anomaly_grid(anomalies, sec_ids=anom_sec_ids) if anomalies else ""

    # 3. 折叠段（含指标切换 tabs + 下钻 panel）
    import re as _re  # noqa: PLC0415
    org_drill_dims = _build_org_drill_dims(level)
    default_metric = "variable_cost_ratio_pct"
    section_details = _extract_section_details(ctx, drill_long_df, section_defs=section_defs)
    detail_parts = []
    for s in section_details:
        base_html = render_section_detail(s, period_order=PERIOD_ORDER_ORG, ytd_label="当周")
        if s.kind != "overall":
            # 替换 DPT-style tbody → org-weekly 专属版（修正 vcr key + data-kinds）
            new_tbody = _org_tbody_dim(s.rows, s.id, PERIOD_ORDER_ORG, "当周")
            base_html = _re.sub(r'<tbody>[\s\S]*?</tbody>', new_tbody, base_html, count=1)
            tabs_html = render_metric_tabs(ORG_METRIC_TABS, default_metric, s.id)
            drill_html = render_drill_panel(s.id, org_drill_dims.get(s.id, []))
            # 将 tabs + drill 注入到 det-body 前
            base_html = base_html.replace(
                '<table class="dtab">',
                f'{tabs_html}<table class="dtab">',
            ).replace(
                '</div>\n</div>',  # 最后一个 det-body 关闭
                f'{drill_html}\n</div>\n</div>',
                1,
            )
        detail_parts.append(base_html)
    detail_html = "\n".join(detail_parts)

    # 4. 亮灯统计
    section_counts = {}
    for s in section_details:
        red = sum(1 for r in s.rows if r.get("sev") == "alert-red")
        org_n = sum(1 for r in s.rows if r.get("sev") == "alert-yellow")
        section_counts[s.id] = {"red": red, "yellow": org_n}

    # 5. 导航 Rail
    rail_html = render_rail(section_counts, len(anomalies), section_defs=section_defs)

    # 6. Topbar
    n_pol = ctx.sample_n[YTD_IDX] if YTD_IDX < len(ctx.sample_n) else 0
    prem = ctx.total_premiums[YTD_IDX] if YTD_IDX < len(ctx.total_premiums) else 0
    meta = {
        "policies": f"{n_pol / 10000:,.2f}" if n_pol else "—",
        "premium": f"{prem / 10000:,.0f}" if prem else "—",
    }

    # 7. 主题 CSS + JS——从基座取（ADR-002：themes_v2 已下沉 chexian-report-shell，不再借道 DPT）
    from lib.themes_v2 import (  # report-shell 根已由 cli.py 注入 sys.path
        FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
        THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn,
    )

    # 带主题切换按钮的 topbar + 跨视图切换链接（驾驶舱为当前页，链到叙事/超表）
    toggle_btn = theme_toggle_btn()
    narrative_href = f"{org}_{ctx.year}_narrative.html"
    table_href = f"{org}_{ctx.year}_table.html"
    topbar_html = render_topbar(
        cutoff=cutoff, meta=meta,
        brand_mark=org[0], brand_text=f"{org} · 经营诊断周报",
        title=f"{org} {ctx.year} 驾驶舱",
        view_links=[(narrative_href, "叙事"), (table_href, "超表")],
        theme_toggle_btn=toggle_btn,
    )

    full_css = BASE_CSS + DARK_CSS + THEME_TOGGLE_CSS + V1_PAGE_CSS + DRILL_PANEL_CSS

    # 8. DD JSON + 交互 JS
    dd_data = ctx.org_dd or {}
    dd_js = f"const DD = {_json.dumps(dd_data, ensure_ascii=False, separators=(',', ':'))};"
    interact_js = dashboard_interact_js(
        metric_defs=ORG_METRIC_TABS,
        drill_dims=org_drill_dims,
        period_order=PERIOD_ORDER_ORG,
        ytd_idx=YTD_IDX,
        drill_metric_defs=ORG_DRILL_PANEL_METRICS,  # DD 仅含 4 series，独立列表防超界
    )

    # 9. 组装完整 HTML
    page = f"""<!doctype html>
<html lang="zh-CN" data-theme="ink">
<head>
<meta charset="utf-8"/>
<title>{_e(org)} {ctx.year} 驾驶舱 · {cs}</title>
<meta name="viewport" content="width=1440, initial-scale=1"/>
{FONT_LINKS}
<style>{full_css}</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{topbar_html}
<div class="shell">
  {rail_html}
  <main class="main">
    <div id="top"></div>
    <div class="section-tag"><span class="bar"></span>整体状态 · 5 KPI</div>
    {kpi_html}
    {anomaly_html}
    <div id="details"></div>
    <div class="section-tag" style="margin-top:8px;"><span class="bar"></span>分维度明细 · {len(section_details)} 段</div>
    <h2 class="h-section">从概览下钻</h2>
    {detail_html}
  </main>
</div>
<script>{THEME_TOGGLE_JS}</script>
<script>{dd_js}</script>
<script>{interact_js}</script>
</body>
</html>"""

    out_path = out_dir / f"{org}_{ctx.year}_cockpit.html"
    out_path.write_text(page, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"      [v1] 已写入：{out_path}（{size_kb:.1f} KB）")
