"""CLI 主入口：解析参数 → 查询 → QC 摘要 → 渲染 HTML → 写文件。

可作为脚本调用（python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py）
或编程调用（from diagnose_period_trend import run）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import date
from html import escape
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd

# 把本 skill 自己的 lib 目录加到 sys.path[0]，确保 absolute import 命中本 skill 而非
# 其它 skill 的 lib/ 子目录（如 chexian-report-shell）
_SELF_LIB = Path(__file__).resolve().parent
if str(_SELF_LIB) not in sys.path:
    sys.path.insert(0, str(_SELF_LIB))


# 把 chexian-report-shell 的 lib 注册为独立顶层包 dhr_lib（避免 sys.path 加目录导致
# 本 skill 的 render.py 与对方的 render.py 撞车）
# 2026-05-17 重命名：原 diagnose-html-render → chexian-report-shell
def _load_dhr_lib():
    import importlib.util
    if "dhr_lib" in sys.modules:
        return sys.modules["dhr_lib"]
    dhr_lib_path = Path.home() / ".claude/skills/chexian-report-shell/lib"
    spec = importlib.util.spec_from_file_location(
        "dhr_lib", str(dhr_lib_path / "__init__.py"),
        submodule_search_locations=[str(dhr_lib_path)],
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["dhr_lib"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_dhr = _load_dhr_lib()
render_card = _dhr.render_card
render_page = _dhr.render_page

# 本 skill 内部模块（绝对 import；上面已把本 skill lib/ 放到 sys.path[0]）
from periods import build_periods, PERIOD_KEYS  # type: ignore[import-not-found]  # noqa: E402
from query import (  # type: ignore[import-not-found]  # noqa: E402
    build_sql, build_max_date_sql, derive_metrics,
    METRIC_DEFS, METRIC_DEFS_T23, CUSTOMER_CATEGORIES_REGISTERED, short_category,
    AUX_DIMENSIONS, aux_short_label, aux_is_multi, aux_valid_values, aux_default_order,
)
from render import (  # type: ignore[import-not-found]  # noqa: E402
    render_table_1, render_table_2, render_table_3,
    render_drill_overview, render_callout,
    INTERACT_JS, build_info_card_html,
)
from org_groups import (  # type: ignore[import-not-found]  # noqa: E402
    SAME_CITY, REMOTE, GROUP_LABELS,
)


# 表 3 聚合时需要按 period_label 求和的原始量列（率值不参与求和，由 derive_metrics 重算）
_RAW_AGG_COLS = [
    "policy_count", "reported_claims_sum", "earned_premium_sum",
    "fee_sum", "premium_sum", "commercial_premium_sum",
    "baseline_premium_sum", "claim_cases_sum", "annualized_claim_cases_sum",
]

# 副标题用：标记"超出健康"分位（仅作展示提示，不再用于过滤）
DRILL_VCR_THRESHOLD = 89.0


def _vcr_at(rows: pd.DataFrame, period_label: str) -> Optional[float]:
    """取该维度值在指定 period_label 下的变动成本率（找不到或 NaN 返回 None）。"""
    hit = rows[rows["period_label"] == period_label]
    if hit.empty:
        return None
    v = hit.iloc[0]["variable_cost_ratio"]
    return None if pd.isna(v) else float(v)


def _make_drill_page_id(prefix: str, name: str) -> str:
    """生成稳定唯一的下钻子页 ID（与维度值一对一）。"""
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    return f"page-drill-{prefix}-{h}"


# ── 中心化 page_id 生成（9 维度 × 各值 → page_id） ──
# 9 维度：customer_category / org_level_3 + 7 aux
# prefix 用 field 名（短）；name 用维度值（如 "家自车" / "true" / "商业保险"）
def _dim_page_id(field: str, value) -> str:
    """通用维度值 → page_id。field=维度字段名，value=该维度的原始值。"""
    # prefix 简短化：customer_category → cat, org_level_3 → org, 其余取最后一段
    prefix_map = {
        "customer_category": "cat",
        "org_level_3":       "org",
        "insurance_type":    "ins",
        "is_nev":            "nev",
        "is_new_car":        "new",
        "is_transfer":       "tfr",
        "is_renewal":        "rnw",
        "is_telemarketing":  "tel",
        "coverage_combination": "cov",
    }
    prefix = prefix_map.get(field, field[:4])
    return _make_drill_page_id(prefix, f"{field}::{value}")


def _make_instance_id(prefix: str, name: str) -> str:
    """同一 page_id 派生出的多个表实例需要 unique instance_id。
    复用 page_id 的 hash 后缀即可。
    """
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def build_table_3_data(by_org_subset: pd.DataFrame,
                       overall_subset: pd.DataFrame,
                       share_denominator: Optional[pd.DataFrame] = None) -> tuple:
    """从 (period, org) 长表 + 该 subset 的整体行构造表 3 所需的 7 个 DataFrame。

    主页：overall_subset = overall, by_org_subset = by_org
    下钻：overall_subset = by_cat[cat==X], by_org_subset = by_cat_org[cat==X]
    share_denominator：份额分母（默认 None → 用 overall_subset；推荐传主页 overall 保持跨页可比）

    返回 (sichuan_agg, sc_agg, rm_agg, other_agg, sc_rows, rm_rows, other_rows)
    所有 7 个 DataFrame 都已派生 premium_share / claim_share。
    """
    denom = share_denominator if share_denominator is not None else overall_subset

    sc_rows    = by_org_subset[by_org_subset["org_level_3"].isin(SAME_CITY)].copy()
    rm_rows    = by_org_subset[by_org_subset["org_level_3"].isin(REMOTE)].copy()
    other_rows = by_org_subset[~by_org_subset["org_level_3"].isin(SAME_CITY + REMOTE)].copy()

    # 子行也派生 share（每行 / 同期 denom）
    sc_rows    = _compute_share_metrics(sc_rows,    denom)
    rm_rows    = _compute_share_metrics(rm_rows,    denom)
    other_rows = _compute_share_metrics(other_rows, denom)

    sichuan_agg = _compute_share_metrics(
        overall_subset.assign(org_level_3="四川"), denom
    )
    sc_agg      = aggregate_group(sc_rows,    GROUP_LABELS["same-city"], denom)
    rm_agg      = aggregate_group(rm_rows,    GROUP_LABELS["remote"],    denom)
    other_agg   = aggregate_group(other_rows, GROUP_LABELS["other"],     denom)

    return sichuan_agg, sc_agg, rm_agg, other_agg, sc_rows, rm_rows, other_rows


def _describe_dual_change(d_lr: float, d_er: float, intensity: str = "normal") -> str:
    """根据双端变化方向 + 量级生成短语（智能措辞，不硬编码）。

    intensity: "normal" (vs yoy) / "strong" (vs 12m，短窗对比变化通常更显著，词汇加重)
    返回："赔付端推升变率" / "费用端拉低变率" / "双成本飙升" / "双成本上涨" /
          "双成本上行" / "双成本骤降" / "双成本下降" / "双成本回落" /
          "双成本基本持平" / "成本结构分化"
    """
    denom = abs(d_lr) + abs(d_er)
    # 单端主导（>=70% 且 >=0.5 PP）
    if denom > 0 and abs(d_lr) >= 0.7 * denom and abs(d_lr) >= 0.5:
        verb = "推升变率" if d_lr > 0 else "拉低变率"
        return f"赔付端{verb}"
    if denom > 0 and abs(d_er) >= 0.7 * denom and abs(d_er) >= 0.5:
        verb = "推升变率" if d_er > 0 else "拉低变率"
        return f"费用端{verb}"
    # 双端基本持平
    if abs(d_lr) < 0.3 and abs(d_er) < 0.3:
        return "双成本基本持平"
    # 双端同向（同涨）
    if d_lr > 0 and d_er > 0:
        max_d = max(d_lr, d_er)
        if intensity == "strong" and max_d >= 2.0:
            return "双成本飙升"
        if max_d >= 1.0:
            return "双成本上涨"
        return "双成本上行"
    # 双端同向（同跌）
    if d_lr < 0 and d_er < 0:
        min_d = min(d_lr, d_er)
        if intensity == "strong" and min_d <= -2.0:
            return "双成本骤降"
        if min_d <= -1.0:
            return "双成本下降"
        return "双成本回落"
    # 一正一负
    return "成本结构分化"


def build_insights_table_1(overall: pd.DataFrame) -> str:
    """从已派生指标的 overall DataFrame 生成 3 句洞察（健康度 / 趋势 / 同比归因）。

    事实来源：仅使用 overall（cli 主流程已 derive_metrics），不重算明细，不引入表外数据。

    句 ①：YTD 变率 + 亮灯 + 距 dhr_lib.TH 警戒线（warn=89）的距离
    句 ②：短中长期 变率 6m/12m/24m/36m 单调或差值描述
    句 ③：YTD vs 上年同期 变率拆解为「赔付端 / 费用端 / 双端共振」

    输出顺序遵守：率值用 %，差值用 PP；不出现"持续关注/加强管理"等无锚点措辞；
    callout level 跟随句 ① 的级别（red→danger, yellow→warn, 其它→info）。
    """
    idx = overall.set_index("period_label")

    def _val(period: str, col: str) -> Optional[float]:
        if period not in idx.index:
            return None
        v = idx.loc[period, col]
        return None if pd.isna(v) else float(v)

    # ── 读数 ──
    ytd_vcr = _val("当年起保",  "variable_cost_ratio")
    ytd_lr  = _val("当年起保",  "earned_claim_ratio")
    ytd_er  = _val("当年起保",  "expense_ratio")
    ytd_n_v = _val("当年起保",  "policy_count")
    ytd_n   = int(ytd_n_v) if ytd_n_v is not None else 0
    yoy_lr  = _val("上年同期",  "earned_claim_ratio")
    yoy_er  = _val("上年同期",  "expense_ratio")
    m12_lr  = _val("滚动12个月", "earned_claim_ratio")
    m12_er  = _val("滚动12个月", "expense_ratio")
    vcr_6m  = _val("滚动6个月",  "variable_cost_ratio")
    vcr_12m = _val("滚动12个月", "variable_cost_ratio")
    vcr_24m = _val("滚动24个月", "variable_cost_ratio")
    vcr_36m = _val("滚动36个月", "variable_cost_ratio")

    items: list[str] = []

    # ── 句 ① 健康度 ──
    if ytd_vcr is not None:
        cls, _label = _dhr.light("variable_cost_ratio_pct", ytd_vcr, ytd_n)
        # TH 真实结构：tuple(notice=84, warn=89, danger=93)。"警戒线"=黄线下界=warn=89
        _notice, warn, _danger = _dhr.TH["variable_cost_ratio_pct"]
        diff_to_warn = ytd_vcr - float(warn)
        if cls in ("alert-red", "alert-yellow"):
            tail = f"已超警戒线 <b>{diff_to_warn:+.1f}</b> PP"
        else:
            tail = f"距警戒线 <b>{abs(diff_to_warn):.1f}</b> PP"
        items.append(
            f"当年起保变率 <strong>{ytd_vcr:.1f}%</strong>，{tail}"
        )

    # ── 句 ② 趋势 ──
    if all(v is not None for v in (vcr_6m, vcr_12m, vcr_24m, vcr_36m)):
        strictly_up   = vcr_6m > vcr_12m > vcr_24m > vcr_36m
        strictly_down = vcr_6m < vcr_12m < vcr_24m < vcr_36m
        diff_6_36 = vcr_6m - vcr_36m
        if strictly_up:
            trend_txt = f"短期承压、连续抬升 <b>{diff_6_36:+.1f}</b> PP（6m→36m）"
        elif strictly_down:
            trend_txt = f"短期改善、连续回落 <b>{diff_6_36:+.1f}</b> PP（6m→36m）"
        elif diff_6_36 >= 2.0:
            trend_txt = f"近期压力高于长期中枢 <b>{diff_6_36:+.1f}</b> PP"
        elif diff_6_36 <= -2.0:
            trend_txt = f"近期压力低于长期中枢 <b>{diff_6_36:+.1f}</b> PP"
        elif abs(diff_6_36) < 1.0:
            trend_txt = f"短长期相对稳定（差值 <b>{diff_6_36:+.1f}</b> PP）"
        else:
            trend_txt = f"短长期分化温和（差值 <b>{diff_6_36:+.1f}</b> PP）"
        items.append(trend_txt)

    # ── 句 ③ 与上年同期比（智能措辞）──
    if all(v is not None for v in (ytd_lr, ytd_er, yoy_lr, yoy_er)):
        d_lr = ytd_lr - yoy_lr
        d_er = ytd_er - yoy_er
        phrase = _describe_dual_change(d_lr, d_er, intensity="normal")
        items.append(
            f"与上年同期比，{phrase}"
            f"（赔付率 <b>{d_lr:+.1f}</b> PP / 费用率 <b>{d_er:+.1f}</b> PP）"
        )
    else:
        items.append("与上年同期比：上年同期数据不全，暂不展示")

    # ── 句 ④ 与滚动12个月比（短窗对比，措辞强度更高）──
    if all(v is not None for v in (ytd_lr, ytd_er, m12_lr, m12_er)):
        d_lr = ytd_lr - m12_lr
        d_er = ytd_er - m12_er
        phrase = _describe_dual_change(d_lr, d_er, intensity="strong")
        items.append(
            f"与滚动12个月比，{phrase}"
            f"（赔付率 <b>{d_lr:+.1f}</b> PP / 费用率 <b>{d_er:+.1f}</b> PP）"
        )

    # ── callout level：跟随句 ① 级别 ──
    callout_level = "info"
    if ytd_vcr is not None:
        cls, _ = _dhr.light("variable_cost_ratio_pct", ytd_vcr, ytd_n)
        callout_level = {"alert-red": "danger", "alert-yellow": "warn"}.get(cls, "info")

    body = (
        '<div class="callout-title"><strong>关键发现</strong></div>'
        '<ul class="insights-list">'
        + "".join(f"<li>{i}</li>" for i in items)
        + "</ul>"
    )
    return render_callout(body, level=callout_level)


def _safe_float(v) -> Optional[float]:
    """pd.NaN / None → None；其他 → float（避免 NaN 参与算术污染）"""
    if v is None or pd.isna(v):
        return None
    return float(v)


def _fmt_metric_value(v: Optional[float], kind: str) -> str:
    """格式化指标值：pct → "X.X%"; money0 → "X,XXX"; coef → "0.XXX"; wan2 → "X.XX 万"。"""
    if v is None or pd.isna(v):
        return "—"
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "money0":
        return f"{v:,.0f}"
    if kind == "coef":
        return f"{v:.3f}"
    if kind == "wan2":
        return f"{v / 10000:,.2f} 万"
    return f"{v:.2f}"


def _fmt_metric_delta(d: Optional[float], kind: str) -> str:
    """格式化指标差值（带 + 号）：pct → "+X.X PP"; money0 → "+X,XXX 元"; coef → "+0.XXX"; wan2 → "+X.XX 万"。"""
    if d is None or pd.isna(d):
        return "—"
    if kind == "pct":
        return f"{d:+.1f} PP"
    if kind == "money0":
        return f"{d:+,.0f} 元"
    if kind == "coef":
        return f"{d:+.3f}"
    if kind == "wan2":
        return f"{d / 10000:+,.2f} 万"
    return f"{d:+.2f}"


def _warn_tail_for_metric(alert_key: Optional[str], v: float, n: int) -> str:
    """非 None alert_key → 返回"已超/距警戒线 X PP"；None → 空串。"""
    if alert_key is None:
        return ""
    cls, _ = _dhr.light(alert_key, v, int(n))
    th = _dhr.TH.get(alert_key)
    if th is None:
        return ""
    _notice, warn, _danger = th
    diff = v - float(warn)
    if cls in ("alert-red", "alert-yellow"):
        return f"，已超警戒线 <b>{diff:+.1f}</b> PP"
    return f"，距警戒线 <b>{abs(diff):.1f}</b> PP"


def build_insight_for_metric(
    by_dim: pd.DataFrame, dim_order: list,
    metric_key: str, dim_kind: str = "cat",
    dim_col: Optional[str] = None,
    label_func=None,
) -> str:
    """通用洞察生成器（适用除变率外的 6 指标）。

    dim_kind: "cat" / "org" / "aux"
      - "cat"  → dim_col=customer_category, label_func=short_category
      - "org"  → dim_col=org_level_3,      label_func=str
      - "aux"  → 调用方必须显式传 dim_col + label_func
    生成 4 句固定模板：YTD 最高 / YTD 最低 / vs YoY 升幅最大 / vs 12m 升幅最大。
    返回 callout HTML。
    """
    info = next((m for m in METRIC_DEFS_T23 if m[0] == metric_key), None)
    if info is None:
        return ""
    key, name, kind, alert_key = info

    # dim_col / label_func 默认解析（向后兼容 cat/org）
    if dim_col is None:
        dim_col = "customer_category" if dim_kind == "cat" else "org_level_3"
    if label_func is None:
        label_func = short_category if dim_kind == "cat" else str

    bd = by_dim.set_index([dim_col, "period_label"])

    def _val(d, period: str, col: str = key) -> Optional[float]:
        try:
            return _safe_float(bd.loc[(d, period), col])
        except KeyError:
            return None

    def _label(d) -> str:
        return label_func(d)

    items: list[str] = []
    head_v: Optional[float] = None
    head_n: int = 0

    # 句 ① YTD 最高 / 句 ② YTD 最低
    ytd_data: list[dict] = []
    for d in dim_order:
        v = _val(d, "当年起保")
        if v is None:
            continue
        n = _val(d, "当年起保", "policy_count")
        ytd_data.append({"dim": d, "v": v, "n": int(n) if n is not None else 0})
    if ytd_data:
        worst = max(ytd_data, key=lambda r: r["v"])
        head_v, head_n = worst["v"], worst["n"]
        v_str = _fmt_metric_value(worst["v"], kind)
        items.append(
            f"YTD {name}最高：<strong>{_label(worst['dim'])}</strong> "
            f"<b>{v_str}</b>{_warn_tail_for_metric(alert_key, worst['v'], worst['n'])}"
        )
        best = min(ytd_data, key=lambda r: r["v"])
        v_str = _fmt_metric_value(best["v"], kind)
        items.append(
            f"YTD {name}最低：<strong>{_label(best['dim'])}</strong> <b>{v_str}</b>"
        )

    # 句 ③ vs 上年同期 升幅最大
    yoy_diffs: list[dict] = []
    for d in dim_order:
        ytd = _val(d, "当年起保")
        yoy = _val(d, "上年同期")
        if ytd is None or yoy is None:
            continue
        yoy_diffs.append({"dim": d, "delta": ytd - yoy})
    if yoy_diffs:
        worst = max(yoy_diffs, key=lambda r: r["delta"])
        if worst["delta"] > 0:
            d_str = _fmt_metric_delta(worst["delta"], kind)
            items.append(
                f"与上年同期比，{name}升幅最大：<strong>{_label(worst['dim'])}</strong> <b>{d_str}</b>"
            )
        else:
            best = min(yoy_diffs, key=lambda r: r["delta"])
            d_str = _fmt_metric_delta(best["delta"], kind)
            items.append(
                f"与上年同期比，{name}降幅最大：<strong>{_label(best['dim'])}</strong> <b>{d_str}</b>"
            )
    else:
        items.append(f"与上年同期比：上年同期数据不全，暂不展示")

    # 句 ④ vs 滚动12个月 升幅最大
    m12_diffs: list[dict] = []
    for d in dim_order:
        ytd = _val(d, "当年起保")
        m12 = _val(d, "滚动12个月")
        if ytd is None or m12 is None:
            continue
        m12_diffs.append({"dim": d, "delta": ytd - m12})
    if m12_diffs:
        worst = max(m12_diffs, key=lambda r: r["delta"])
        if worst["delta"] > 0:
            d_str = _fmt_metric_delta(worst["delta"], kind)
            items.append(
                f"与滚动12个月比，{name}升幅最大：<strong>{_label(worst['dim'])}</strong> <b>{d_str}</b>"
            )
        else:
            best = min(m12_diffs, key=lambda r: r["delta"])
            d_str = _fmt_metric_delta(best["delta"], kind)
            items.append(
                f"与滚动12个月比，{name}降幅最大：<strong>{_label(best['dim'])}</strong> <b>{d_str}</b>"
            )

    if not items:
        items.append("数据不足，无法生成洞察")

    # callout level：仅变率敏感（其他指标无亮灯依据）
    callout_level = _vcr_callout_level(head_v, head_n) if alert_key == "variable_cost_ratio_pct" else "info"

    body = (
        '<div class="callout-title"><strong>关键发现</strong></div>'
        '<ul class="insights-list">'
        + "".join(f"<li>{i}</li>" for i in items)
        + "</ul>"
    )
    return render_callout(body, level=callout_level)


def _wrap_insights_blocks(by_dim: pd.DataFrame, dim_order: list[str],
                          dim_kind: str,
                          vcr_block_html: str,
                          instance_id: str, table_num: int) -> str:
    """为 7 指标各生成 1 个 insights-block（默认显示变率），用 wrapper 包裹供 JS 切换。

    JS 切换指标时通过 data-instance + data-table 定位 wrapper，
    把 data-metric=key 的 block 显示，其它 hidden。
    """
    blocks: list[str] = []
    for i, (key, _name, _kind, _alert) in enumerate(METRIC_DEFS_T23):
        if key == "variable_cost_ratio":
            html = vcr_block_html
        else:
            html = build_insight_for_metric(by_dim, dim_order, key, dim_kind)
        hidden = "" if i == 0 else " hidden"
        blocks.append(
            f'<div class="insights-block" data-metric="{key}"{hidden}>{html}</div>'
        )
    return (
        f'<div class="insights-wrapper" '
        f'data-instance="{instance_id}" data-table="{table_num}">'
        f'{"".join(blocks)}</div>'
    )


def _vcr_warn_tail(vcr: float, n: int) -> str:
    """生成 "已超警戒线 +N PP" / "距警戒线 N PP" 短语。"""
    cls, _ = _dhr.light("variable_cost_ratio_pct", vcr, int(n))
    _notice, warn, _danger = _dhr.TH["variable_cost_ratio_pct"]
    diff = vcr - float(warn)
    if cls in ("alert-red", "alert-yellow"):
        return f"已超警戒线 <b>{diff:+.1f}</b> PP"
    return f"距警戒线 <b>{abs(diff):.1f}</b> PP"


def _vcr_callout_level(vcr: Optional[float], n: int) -> str:
    """从 YTD 变率推导 callout level（alert-red→danger / alert-yellow→warn / 其他→info）。"""
    if vcr is None:
        return "info"
    cls, _ = _dhr.light("variable_cost_ratio_pct", vcr, int(n))
    return {"alert-red": "danger", "alert-yellow": "warn"}.get(cls, "info")


def _build_insights_t2_vcr(by_cat: pd.DataFrame, overall: pd.DataFrame,
                           category_order: list[str]) -> str:
    """变率深度版（4 句含双端归因）— 表 2 默认显示块。

    句 ①：YTD 变率最高类别（最毒）+ 警戒线距离 + 保费贡献
    句 ②：YTD 变率最低类别（最优）+ 健康水位 + 保费贡献
    句 ③：与上年同期比，变率恶化幅度最大类别（智能措辞，normal）
    句 ④：与滚动12个月比，变率恶化幅度最大类别（智能措辞，strong）

    callout level 跟随句 ① 的 YTD 变率亮灯。
    """
    bc = by_cat.set_index(["customer_category", "period_label"])

    def _val(cat: str, period: str, col: str) -> Optional[float]:
        try:
            return _safe_float(bc.loc[(cat, period), col])
        except KeyError:
            return None

    # 收集每个 cat 在 当年起保 的 vcr / n / share
    cats_data: list[dict] = []
    for cat in category_order:
        ytd_vcr = _val(cat, "当年起保", "variable_cost_ratio")
        if ytd_vcr is None:
            continue
        n = _val(cat, "当年起保", "policy_count")
        share = _val(cat, "当年起保", "premium_share")
        cats_data.append({
            "cat": cat, "vcr": ytd_vcr,
            "n": int(n) if n is not None else 0,
            "share": share,
        })

    items: list[str] = []
    head_n = 0
    head_vcr: Optional[float] = None

    # 句 ① 最毒类别（YTD vcr 最高）
    if cats_data:
        worst = max(cats_data, key=lambda r: r["vcr"])
        head_vcr, head_n = worst["vcr"], worst["n"]
        share_txt = f"，保费贡献 <b>{worst['share']:.1f}%</b>" if worst["share"] is not None else ""
        items.append(
            f"YTD 变率最高：<strong>{short_category(worst['cat'])}</strong> "
            f"<b>{worst['vcr']:.1f}%</b>，{_vcr_warn_tail(worst['vcr'], worst['n'])}{share_txt}"
        )

    # 句 ② 最优类别（YTD vcr 最低）
    if cats_data:
        best = min(cats_data, key=lambda r: r["vcr"])
        share_txt = f"，保费贡献 <b>{best['share']:.1f}%</b>" if best["share"] is not None else ""
        items.append(
            f"YTD 变率最低：<strong>{short_category(best['cat'])}</strong> "
            f"<b>{best['vcr']:.1f}%</b>，{_vcr_warn_tail(best['vcr'], best['n'])}{share_txt}"
        )

    # 句 ③ vs 上年同期 恶化最快
    yoy_diffs: list[dict] = []
    for cat in category_order:
        ytd = _val(cat, "当年起保", "variable_cost_ratio")
        yoy = _val(cat, "上年同期", "variable_cost_ratio")
        if ytd is None or yoy is None:
            continue
        d_lr = (_val(cat, "当年起保", "earned_claim_ratio") or 0) - (_val(cat, "上年同期", "earned_claim_ratio") or 0)
        d_er = (_val(cat, "当年起保", "expense_ratio")     or 0) - (_val(cat, "上年同期", "expense_ratio")     or 0)
        yoy_diffs.append({"cat": cat, "delta": ytd - yoy, "d_lr": d_lr, "d_er": d_er})
    if yoy_diffs:
        worst = max(yoy_diffs, key=lambda r: r["delta"])
        if worst["delta"] > 0.5:
            phrase = _describe_dual_change(worst["d_lr"], worst["d_er"], "normal")
            items.append(
                f"与上年同期比，恶化最快：<strong>{short_category(worst['cat'])}</strong> "
                f"变率 <b>{worst['delta']:+.1f}</b> PP（{phrase}）"
            )
        else:
            best = min(yoy_diffs, key=lambda r: r["delta"])
            items.append(
                f"与上年同期比，整体改善：最大降幅类别 <strong>{short_category(best['cat'])}</strong> "
                f"变率 <b>{best['delta']:+.1f}</b> PP"
            )
    else:
        items.append("与上年同期比：上年同期数据不全，暂不展示")

    # 句 ④ vs 滚动12个月 恶化最快
    m12_diffs: list[dict] = []
    for cat in category_order:
        ytd = _val(cat, "当年起保", "variable_cost_ratio")
        m12 = _val(cat, "滚动12个月", "variable_cost_ratio")
        if ytd is None or m12 is None:
            continue
        d_lr = (_val(cat, "当年起保", "earned_claim_ratio") or 0) - (_val(cat, "滚动12个月", "earned_claim_ratio") or 0)
        d_er = (_val(cat, "当年起保", "expense_ratio")     or 0) - (_val(cat, "滚动12个月", "expense_ratio")     or 0)
        m12_diffs.append({"cat": cat, "delta": ytd - m12, "d_lr": d_lr, "d_er": d_er})
    if m12_diffs:
        worst = max(m12_diffs, key=lambda r: r["delta"])
        if worst["delta"] > 0.5:
            phrase = _describe_dual_change(worst["d_lr"], worst["d_er"], "strong")
            items.append(
                f"与滚动12个月比，恶化最快：<strong>{short_category(worst['cat'])}</strong> "
                f"变率 <b>{worst['delta']:+.1f}</b> PP（{phrase}）"
            )

    if not items:
        items.append("数据不足，无法生成洞察")

    body = (
        '<div class="callout-title"><strong>关键发现</strong></div>'
        '<ul class="insights-list">'
        + "".join(f"<li>{i}</li>" for i in items)
        + "</ul>"
    )
    return render_callout(body, level=_vcr_callout_level(head_vcr, head_n))


def _build_insights_t3_vcr(sc_rows: pd.DataFrame, rm_rows: pd.DataFrame,
                           other_rows: pd.DataFrame,
                           sc_agg: pd.DataFrame, rm_agg: pd.DataFrame,
                           other_agg: pd.DataFrame,
                           overall: pd.DataFrame) -> str:
    """变率深度版（4 句含双端归因）— 表 3 默认显示块。

    句 ①：同城 vs 异地（聚合行）变率对比 + 谁更差 + 该侧保费贡献
    句 ②：YTD 变率最高子机构 + 警戒线距离 + 保费贡献
    句 ③：与上年同期比，子机构变率恶化最快（智能措辞，normal）
    句 ④：与滚动12个月比，子机构变率恶化最快（智能措辞，strong）
    """
    def _at(df, period: str, col: str) -> Optional[float]:
        if df is None or df.empty:
            return None
        try:
            return _safe_float(df.set_index("period_label").loc[period, col])
        except KeyError:
            return None

    items: list[str] = []
    head_n = 0
    head_vcr: Optional[float] = None

    # 句 ① 同城 vs 异地
    sc_ytd = _at(sc_agg, "当年起保", "variable_cost_ratio")
    rm_ytd = _at(rm_agg, "当年起保", "variable_cost_ratio")
    sc_share = _at(sc_agg, "当年起保", "premium_share")
    rm_share = _at(rm_agg, "当年起保", "premium_share")
    if sc_ytd is not None and rm_ytd is not None:
        d = sc_ytd - rm_ytd
        if abs(d) < 0.5:
            items.append(
                f"同城 <b>{sc_ytd:.1f}%</b> vs 异地 <b>{rm_ytd:.1f}%</b>，差距 <b>{d:+.1f}</b> PP（基本持平）"
            )
        else:
            worse = "同城" if d > 0 else "异地"
            sh = (sc_share if d > 0 else rm_share) or 0
            items.append(
                f"同城 <b>{sc_ytd:.1f}%</b> vs 异地 <b>{rm_ytd:.1f}%</b>，差距 <b>{d:+.1f}</b> PP"
                f"（{worse}更差，保费贡献 <b>{sh:.1f}%</b>）"
            )

    # 收集所有子机构数据
    rows_list = [df for df in (sc_rows, rm_rows, other_rows) if df is not None and not df.empty]
    all_rows = pd.concat(rows_list, ignore_index=True) if rows_list else pd.DataFrame()

    if not all_rows.empty:
        bo = all_rows.set_index(["org_level_3", "period_label"])
        orgs = sorted(all_rows["org_level_3"].unique().tolist())

        def _vo(org: str, period: str, col: str) -> Optional[float]:
            try:
                return _safe_float(bo.loc[(org, period), col])
            except KeyError:
                return None

        # 句 ② 最毒机构
        org_ytd: list[dict] = []
        for org in orgs:
            v = _vo(org, "当年起保", "variable_cost_ratio")
            if v is None:
                continue
            n = _vo(org, "当年起保", "policy_count")
            share = _vo(org, "当年起保", "premium_share")
            org_ytd.append({"org": org, "vcr": v,
                            "n": int(n) if n is not None else 0,
                            "share": share})
        if org_ytd:
            worst = max(org_ytd, key=lambda r: r["vcr"])
            head_vcr, head_n = worst["vcr"], worst["n"]
            share_txt = f"，保费贡献 <b>{worst['share']:.1f}%</b>" if worst["share"] is not None else ""
            items.append(
                f"YTD 变率最高机构：<strong>{worst['org']}</strong> "
                f"<b>{worst['vcr']:.1f}%</b>，{_vcr_warn_tail(worst['vcr'], worst['n'])}{share_txt}"
            )

        # 句 ③ vs 上年同期 恶化最快机构
        yoy_diffs: list[dict] = []
        for org in orgs:
            ytd = _vo(org, "当年起保", "variable_cost_ratio")
            yoy = _vo(org, "上年同期", "variable_cost_ratio")
            if ytd is None or yoy is None:
                continue
            d_lr = (_vo(org, "当年起保", "earned_claim_ratio") or 0) - (_vo(org, "上年同期", "earned_claim_ratio") or 0)
            d_er = (_vo(org, "当年起保", "expense_ratio")     or 0) - (_vo(org, "上年同期", "expense_ratio")     or 0)
            yoy_diffs.append({"org": org, "delta": ytd - yoy, "d_lr": d_lr, "d_er": d_er})
        if yoy_diffs:
            worst = max(yoy_diffs, key=lambda r: r["delta"])
            if worst["delta"] > 0.5:
                phrase = _describe_dual_change(worst["d_lr"], worst["d_er"], "normal")
                items.append(
                    f"与上年同期比，恶化最快：<strong>{worst['org']}</strong> "
                    f"变率 <b>{worst['delta']:+.1f}</b> PP（{phrase}）"
                )
            else:
                best = min(yoy_diffs, key=lambda r: r["delta"])
                items.append(
                    f"与上年同期比，整体改善：最大降幅机构 <strong>{best['org']}</strong> "
                    f"变率 <b>{best['delta']:+.1f}</b> PP"
                )
        else:
            items.append("与上年同期比：上年同期数据不全，暂不展示")

        # 句 ④ vs 滚动12个月 恶化最快机构
        m12_diffs: list[dict] = []
        for org in orgs:
            ytd = _vo(org, "当年起保",   "variable_cost_ratio")
            m12 = _vo(org, "滚动12个月", "variable_cost_ratio")
            if ytd is None or m12 is None:
                continue
            d_lr = (_vo(org, "当年起保", "earned_claim_ratio") or 0) - (_vo(org, "滚动12个月", "earned_claim_ratio") or 0)
            d_er = (_vo(org, "当年起保", "expense_ratio")     or 0) - (_vo(org, "滚动12个月", "expense_ratio")     or 0)
            m12_diffs.append({"org": org, "delta": ytd - m12, "d_lr": d_lr, "d_er": d_er})
        if m12_diffs:
            worst = max(m12_diffs, key=lambda r: r["delta"])
            if worst["delta"] > 0.5:
                phrase = _describe_dual_change(worst["d_lr"], worst["d_er"], "strong")
                items.append(
                    f"与滚动12个月比，恶化最快：<strong>{worst['org']}</strong> "
                    f"变率 <b>{worst['delta']:+.1f}</b> PP（{phrase}）"
                )

    if not items:
        items.append("数据不足，无法生成洞察")

    body = (
        '<div class="callout-title"><strong>关键发现</strong></div>'
        '<ul class="insights-list">'
        + "".join(f"<li>{i}</li>" for i in items)
        + "</ul>"
    )
    return render_callout(body, level=_vcr_callout_level(head_vcr, head_n))


def build_insights_table_2(by_cat: pd.DataFrame, overall: pd.DataFrame,
                           category_order: list[str],
                           instance_id: str = "main") -> str:
    """表 2 多指标洞察分发器：7 个 insights-block（每指标 1 个），切换由 JS 处理。

    默认显示 variable_cost_ratio（双端归因深度版）；其他 6 指标用通用模板。
    """
    vcr_html = _build_insights_t2_vcr(by_cat, overall, category_order)
    return _wrap_insights_blocks(
        by_cat, category_order, "cat", vcr_html, instance_id, table_num=2
    )


def build_insights_table_3(sc_rows: pd.DataFrame, rm_rows: pd.DataFrame,
                           other_rows: pd.DataFrame,
                           sc_agg: pd.DataFrame, rm_agg: pd.DataFrame,
                           other_agg: pd.DataFrame,
                           overall: pd.DataFrame,
                           instance_id: str = "main") -> str:
    """表 3 多指标洞察分发器：7 个 insights-block。

    by_dim 用 sc_rows + rm_rows + other_rows concat（子机构作为行）。
    默认显示 variable_cost_ratio。
    """
    vcr_html = _build_insights_t3_vcr(
        sc_rows, rm_rows, other_rows, sc_agg, rm_agg, other_agg, overall
    )
    rows_list = [df for df in (sc_rows, rm_rows, other_rows) if df is not None and not df.empty]
    by_org_all = pd.concat(rows_list, ignore_index=True) if rows_list else pd.DataFrame()
    orgs_order = sorted(by_org_all["org_level_3"].unique().tolist()) if not by_org_all.empty else []
    return _wrap_insights_blocks(
        by_org_all, orgs_order, "org", vcr_html, instance_id, table_num=3
    )


def build_insights_aux(by_aux: pd.DataFrame, dim_order: list,
                       dim_def: dict, instance_id: str) -> str:
    """aux 维度（二值）多指标洞察分发器：7 个 insights-block。

    与 _wrap_insights_blocks 区别：aux 维度只有 2 行，不用变率深度版（双端归因对 2 行没必要），
    所有 7 指标都用通用 build_insight_for_metric 模板。
    """
    field = dim_def["field"]
    label_fn = lambda v: aux_short_label(field, v)
    blocks: list[str] = []
    for i, (key, _name, _kind, _alert) in enumerate(METRIC_DEFS_T23):
        html = build_insight_for_metric(
            by_aux, dim_order, key, dim_kind="aux",
            dim_col=field, label_func=label_fn,
        )
        hidden = "" if i == 0 else " hidden"
        blocks.append(
            f'<div class="insights-block" data-metric="{key}"{hidden}>{html}</div>'
        )
    # 使用 table_num=2 让 switchMetric2 触发的 toggleInsightsBlock 能找到此 wrapper
    return (
        f'<div class="insights-wrapper" '
        f'data-instance="{instance_id}" data-table="2">'
        f'{"".join(blocks)}</div>'
    )


def build_aux_card(dim_def: dict, by_aux_filtered: pd.DataFrame,
                   periods: list, instance_id_prefix: str,
                   parent_label: str,
                   drillable_dims: Optional[dict] = None,
                   slice_overall: Optional[pd.DataFrame] = None) -> str:
    """单个 aux 维度卡片：复用 render_table_2（2 行表）+ insights（7 指标可切换）。

    by_aux_filtered：已按 parent_dim（cat 或 org）过滤的子集，应只含 2 个维度值 × 6 周期。
    parent_label：用于卡标题（如 "家自车" 或 "天府"）。
    drillable_dims：{aux_value: page_id} 让该 aux 值蓝色行可点击下钻；None=不可下钻
    slice_overall：可选；该切片的整体行（period_label × 指标），传入则在表顶插入"整体"对照行
    返回 render_card HTML，空数据时返回 ""。
    """
    field = dim_def["field"]
    if by_aux_filtered is None or by_aux_filtered.empty:
        return ""

    inst = f"{instance_id_prefix}-{field}"
    dim_order = aux_default_order(dim_def)
    label_fn = lambda v: aux_short_label(field, v)

    table_html = render_table_2(
        by_aux_filtered, periods, dim_order,
        drillable_dims=drillable_dims,
        instance_id=inst,
        metric_defs=METRIC_DEFS_T23,
        dim_col=field,
        dim_header=dim_def["label"],
        label_func=label_fn,
        overall=slice_overall,
    )
    insights_html = build_insights_aux(by_aux_filtered, dim_order, dim_def, inst)

    # subtitle：兼容二值（true_label/false_label）与多值（values 列表）
    if aux_is_multi(dim_def):
        labels_str = " / ".join(v["label"] for v in dim_def["values"])
        subtitle = f"按「{labels_str}」拆分"
    else:
        subtitle = f"按「{dim_def['true_label']} / {dim_def['false_label']}」二值拆分"

    return render_card(
        title=f"{parent_label} · {dim_def['label']}",
        subtitle=subtitle,
        body=insights_html + table_html,
        card_id=f"section-{inst}",
    )


def aggregate_group(by_org_subset: pd.DataFrame, group_label: str,
                    overall: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """对子集按 period_label SUM 原始量后调 derive_metrics 重算指标。

    率值聚合铁律：SUM(分子)/SUM(分母)，禁加权 / 均值 / 二次汇总。
    返回 DataFrame 含 period_label + 全部聚合中间量 + 派生指标 + org_level_3。
    overall：传入则补 premium_share / claim_share（占整体百分比）。
    """
    from query import derive_metrics  # type: ignore[import-not-found]
    if by_org_subset.empty:
        return pd.DataFrame()
    grouped = by_org_subset.groupby("period_label", as_index=False)[_RAW_AGG_COLS].sum()
    out = derive_metrics(grouped)
    out["org_level_3"] = group_label
    if overall is not None:
        out = _compute_share_metrics(out, overall)
    return out


def _compute_share_metrics(df: pd.DataFrame, overall: pd.DataFrame) -> pd.DataFrame:
    """给子维度 DataFrame（by_cat / by_org / by_cat_org / 聚合行）派生：
       - premium_share = premium_sum / overall.premium_sum_at_period * 100
       - claim_share   = reported_claims_sum / overall.reported_claims_sum_at_period * 100

    分母 = 同期整体（overall），而非该子维度的子合计——保证「占整体百分比」语义。
    分母为 0 或缺失 → NaN（render 显示 —）。
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    overall_idx = overall.set_index("period_label")
    prem_total  = out["period_label"].map(overall_idx["premium_sum"])
    claim_total = out["period_label"].map(overall_idx["reported_claims_sum"])
    out["premium_share"] = (out["premium_sum"] / prem_total.where(prem_total > 0)) * 100
    out["claim_share"]   = (out["reported_claims_sum"] / claim_total.where(claim_total > 0)) * 100
    return out


def _resolve_project_root(arg: str | None) -> Path:
    """优先级：--project-root > $CHEXIAN_PROJECT_ROOT > cwd"""
    if arg:
        return Path(arg).resolve()
    env = os.environ.get("CHEXIAN_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def _resolve_cutoff(arg: str | None, project_root: Path, con: duckdb.DuckDBPyConnection) -> date:
    """若未传 --cutoff，查 DuckDB 取 MAX(insurance_start_date)。"""
    if arg:
        return date.fromisoformat(arg)
    print("[0/4] 未提供 --cutoff，从 Parquet 查询 MAX(insurance_start_date) …")
    df = con.execute(build_max_date_sql(project_root)).fetchdf()
    max_d = df.iloc[0]["max_date"]
    if pd.isna(max_d):
        raise SystemExit("❌ 无法从 Parquet 获取最大日期，请显式指定 --cutoff")
    if hasattr(max_d, "date"):
        max_d = max_d.date()
    print(f"      MAX(insurance_start_date) = {max_d}")
    return max_d


def _filter_period_keys(arg: str | None) -> list[str]:
    if not arg:
        return [k for k, _ in PERIOD_KEYS]
    requested = [k.strip() for k in arg.split(",") if k.strip()]
    valid = {k for k, _ in PERIOD_KEYS}
    invalid = [k for k in requested if k not in valid]
    if invalid:
        raise SystemExit(f"❌ 未知 --periods key: {invalid}（可选：{sorted(valid)}）")
    return requested


def _filter_metric_keys(arg: str | None) -> list[str]:
    if not arg:
        return [k for k, *_ in METRIC_DEFS]
    requested = [k.strip() for k in arg.split(",") if k.strip()]
    valid = {k for k, *_ in METRIC_DEFS}
    invalid = [k for k in requested if k not in valid]
    if invalid:
        raise SystemExit(f"❌ 未知 --metrics key: {invalid}（可选：{sorted(valid)}）")
    return requested


def run(
    cutoff: str | None = None,
    project_root: str | None = None,
    output_dir: str | None = None,
    output: str | None = None,
    metrics: str | None = None,
    exclude_categories: str | None = None,
    periods_arg: str | None = None,
    push_im: bool = False,
    feishu_doc: str | None = None,
    wecom_chat: str | None = None,
) -> dict[str, Any]:
    """生成 HTML 报告，返回 {output_path, qc_summary}。"""
    root = _resolve_project_root(project_root)
    con = duckdb.connect(":memory:")

    cutoff_date = _resolve_cutoff(cutoff, root, con)
    period_keys = _filter_period_keys(periods_arg)
    metric_keys = _filter_metric_keys(metrics)
    exclude_cats = {c.strip() for c in (exclude_categories or "").split(",") if c.strip()}

    # 输出路径
    if output:
        out_path = Path(output).resolve()
    else:
        out_dir = Path(output_dir).resolve() if output_dir else (
            root / "public/reports/diagnose-period-trend"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{cutoff_date.isoformat()}.html"

    periods = build_periods(cutoff_date, period_keys)
    print(f"[1/4] 时间窗（{len(periods)} 个）：")
    for p in periods:
        print(f"      {p.label:>12}  ({p.start_excl} , {p.end_incl}]")

    print(f"[2/4] 执行 DuckDB 查询 …")
    df = con.execute(build_sql(cutoff_date, periods, root)).fetchdf()
    con.close()
    print(f"      返回 {len(df)} 行")

    df_metrics = derive_metrics(df)

    # 4 种 GROUPING SET 输出拆分（每个组合锁定其他维度 = __ALL__ 或 != __ALL__）：
    #   overall    : cat=__ALL__,  org=__ALL__
    #   by_cat     : cat=类别,     org=__ALL__
    #   by_org     : cat=__ALL__,  org=机构
    #   by_cat_org : cat=类别,     org=机构      （二维交叉，下钻第 2 张表用）
    is_all_cat = df_metrics["customer_category"] == "__ALL__"
    is_all_org = df_metrics["org_level_3"] == "__ALL__"

    # is_all_aux: 6 个新增 aux 字段全部 == "__ALL__"（避免新增的 12 个 grouping set 行污染原 4 个拆分）
    def _all_aux_mask(df: pd.DataFrame, exclude_field: Optional[str] = None) -> pd.Series:
        mask = pd.Series(True, index=df.index)
        for d in AUX_DIMENSIONS:
            if d["field"] != exclude_field:
                mask &= (df[d["field"]] == "__ALL__")
        return mask

    is_all_aux = _all_aux_mask(df_metrics)

    overall    = df_metrics[is_all_cat  & is_all_org  & is_all_aux].copy()
    by_cat     = df_metrics[(~is_all_cat) & is_all_org  & is_all_aux].copy()
    by_org     = df_metrics[is_all_cat  & (~is_all_org) & is_all_aux].copy()
    by_cat_org = df_metrics[(~is_all_cat) & (~is_all_org) & is_all_aux].copy()

    if exclude_cats:
        by_cat     = by_cat[~by_cat["customer_category"].isin(exclude_cats)]
        by_cat_org = by_cat_org[~by_cat_org["customer_category"].isin(exclude_cats)]
        print(f"      排除类别：{sorted(exclude_cats)}（剩余 {by_cat['customer_category'].nunique()} 类）")

    # 子维度派生 premium_share / claim_share（分母 = 主整体 overall，跨页可比）
    by_cat     = _compute_share_metrics(by_cat,     overall)
    by_org     = _compute_share_metrics(by_org,     overall)
    by_cat_org = _compute_share_metrics(by_cat_org, overall)

    # ── 12 个新 aux grouping set 拆分：by_cat_aux[field] / by_org_aux[field] ──
    by_cat_aux: dict[str, pd.DataFrame] = {}
    by_org_aux: dict[str, pd.DataFrame] = {}
    for d in AUX_DIMENSIONS:
        f = d["field"]
        mask_others_all = _all_aux_mask(df_metrics, exclude_field=f)
        ca = df_metrics[
            (~is_all_cat) & is_all_org &
            (df_metrics[f] != "__ALL__") & mask_others_all
        ].copy()
        oa = df_metrics[
            is_all_cat & (~is_all_org) &
            (df_metrics[f] != "__ALL__") & mask_others_all
        ].copy()
        # 排除：1) 客户类别排除集；2) NULL 行 / __NULL__ 标记
        if exclude_cats:
            ca = ca[~ca["customer_category"].isin(exclude_cats)]
        # 合法值集（二值或多值统一接口）
        valid_vals = aux_valid_values(d)
        ca = ca[ca[f].isin(valid_vals)]
        oa = oa[oa[f].isin(valid_vals)]
        ca = _compute_share_metrics(ca, overall)
        oa = _compute_share_metrics(oa, overall)
        by_cat_aux[f] = ca
        by_org_aux[f] = oa

    # ── 7 个 aux 单维拆分（主页 aux 卡用）──
    # by_aux[field] = period × aux_value 数据（cat = ALL, org = ALL, 其他 aux = ALL）
    by_aux: dict[str, pd.DataFrame] = {}
    for d in AUX_DIMENSIONS:
        f = d["field"]
        mask_others_all = _all_aux_mask(df_metrics, exclude_field=f)
        df_one = df_metrics[
            is_all_cat & is_all_org &
            (df_metrics[f] != "__ALL__") & mask_others_all
        ].copy()
        valid_vals = aux_valid_values(d)
        df_one = df_one[df_one[f].isin(valid_vals)]
        df_one = _compute_share_metrics(df_one, overall)
        by_aux[f] = df_one

    # ── 21 个 aux × aux 二维拆分（aux 下钻页的其他 aux 卡用）──
    # 对称组合 C(7,2) = 21；key = frozenset({f1, f2})；DataFrame 含 f1 + f2 两列
    by_aux_aux: dict[frozenset, pd.DataFrame] = {}
    aux_fields = [d["field"] for d in AUX_DIMENSIONS]
    for i in range(len(aux_fields)):
        for j in range(i + 1, len(aux_fields)):
            f1, f2 = aux_fields[i], aux_fields[j]
            # 该 (f1, f2) 组合：其它 aux 字段 = ALL，cat/org 都 ALL
            mask_others = pd.Series(True, index=df_metrics.index)
            for d in AUX_DIMENSIONS:
                if d["field"] not in (f1, f2):
                    mask_others &= (df_metrics[d["field"]] == "__ALL__")
            df_pair = df_metrics[
                is_all_cat & is_all_org &
                (df_metrics[f1] != "__ALL__") & (df_metrics[f2] != "__ALL__") &
                mask_others
            ].copy()
            vv1 = aux_valid_values(next(d for d in AUX_DIMENSIONS if d["field"] == f1))
            vv2 = aux_valid_values(next(d for d in AUX_DIMENSIONS if d["field"] == f2))
            df_pair = df_pair[df_pair[f1].isin(vv1) & df_pair[f2].isin(vv2)]
            df_pair = _compute_share_metrics(df_pair, overall)
            by_aux_aux[frozenset([f1, f2])] = df_pair

    # ── QC 摘要 ──
    print("[3/4] 质检摘要：")
    print("      ── 整体行（表 1 数据源）──")
    qc_cols = ["period_label", "policy_count", "variable_cost_ratio",
               "earned_claim_ratio", "earned_loss_frequency",
               "avg_claim_amount", "claim_cases", "weighted_pricing_factor"]
    qc = overall[qc_cols].copy()
    qc["weighted_pricing_factor"] = qc["weighted_pricing_factor"].round(3)
    for c in ["variable_cost_ratio", "earned_claim_ratio", "earned_loss_frequency"]:
        qc[c] = qc[c].round(2)
    qc["avg_claim_amount"] = qc["avg_claim_amount"].round(0)
    qc["policy_count_wan"] = (qc["policy_count"] / 10000).round(2)
    qc["claim_cases_wan"]  = (qc["claim_cases"] / 10000).round(2)
    qc_display = qc[["period_label", "policy_count_wan", "variable_cost_ratio",
                     "earned_claim_ratio", "earned_loss_frequency",
                     "avg_claim_amount", "claim_cases_wan", "weighted_pricing_factor"]]
    qc_display = qc_display.set_index("period_label").reindex([p.label for p in periods]).reset_index()
    print(qc_display.to_string(index=False))

    # 滚动窗保单件数单调性
    rolling = qc[qc.period_label.str.startswith("滚动")].copy()
    rolling = rolling.set_index("period_label").reindex(
        [p.label for p in periods if p.label.startswith("滚动")]
    )
    rolling_counts = rolling["policy_count"].fillna(0).astype(int).tolist()
    # 周期顺序：起点早→晚（长窗在前 → 短窗在后），保单件数应单调"不增"
    monotonic_ok = all(rolling_counts[i] >= rolling_counts[i+1] for i in range(len(rolling_counts)-1))
    print(f"      滚动窗保单件数：{rolling_counts} → " +
          ("单调不增 ✓（长窗 → 短窗，件数递减）" if monotonic_ok else "⚠ 非单调（数据问题？）"))

    # 自主系数越界
    facs = qc["weighted_pricing_factor"].dropna().tolist()
    factor_ok = True
    if facs:
        if min(facs) < 0.5 or max(facs) > 1.5:
            print(f"      ⚠ 自主系数越界：{facs}")
            factor_ok = False
        else:
            print(f"      自主系数范围：[{min(facs):.3f}, {max(facs):.3f}] ✓")

    # 客户类别完整性
    cats_seen = sorted(by_cat["customer_category"].unique().tolist())
    missing_in_ts = [c for c in cats_seen if c not in CUSTOMER_CATEGORIES_REGISTERED]
    print(f"      客户类别（数据中实际出现）：{len(cats_seen)} 类")
    if missing_in_ts:
        print(f"      ⚠ TS 枚举缺：{missing_in_ts}（已按数据顺序追加到末尾）")

    # 表 3 数据源：三级机构聚合 + 跨表对账
    orgs_seen = sorted(by_org["org_level_3"].unique().tolist())
    print(f"      机构（数据实际出现）：{len(orgs_seen)} 个 → {orgs_seen}")

    sichuan_agg, sc_agg, rm_agg, other_agg, sc_rows, rm_rows, other_rows = \
        build_table_3_data(by_org, overall, share_denominator=overall)

    # 对账 1：四川行 ≡ 表 1 整体行（变动成本率应 byte-equal）
    s_idx = sichuan_agg.set_index("period_label")["variable_cost_ratio"]
    o_idx = overall.set_index("period_label")["variable_cost_ratio"]
    delta1 = (s_idx - o_idx).abs().max()
    flag1 = "✓" if (pd.notna(delta1) and delta1 < 1e-9) else "⚠"
    print(f"      对账 1 · 四川 vs 整体（变动成本率最大偏差）：{delta1:.6g} {flag1}")

    # 对账 2：同城聚合保单件数 == 7 子机构求和（绝对值类应 == 0）
    if not sc_agg.empty:
        sc_sum = sc_rows.groupby("period_label")["policy_count"].sum()
        sc_a   = sc_agg.set_index("period_label")["policy_count"]
        delta2 = (sc_sum - sc_a).abs().max()
        flag2 = "✓" if delta2 == 0 else "⚠"
        print(f"      对账 2 · 同城保单件数（子和 vs 聚合）：偏差 {int(delta2)} {flag2}")
    else:
        print("      对账 2 · 同城聚合无数据，跳过")

    # 对账 3：每个 aux 维度（cat 视角，YTD）所有合法值之和 + NULL ≈ 该 cat 整体
    print(f"      ── {len(AUX_DIMENSIONS)} 个 aux 维度 NULL 标注情况（保单件数，YTD）──")
    is_ytd = df_metrics["period_label"] == "当年起保"
    n_overall = int(overall[overall["period_label"] == "当年起保"]["policy_count"].sum())
    for d_aux in AUX_DIMENSIONS:
        f = d_aux["field"]
        ml = _all_aux_mask(df_metrics, exclude_field=f)
        rows_in_set = df_metrics[
            (~is_all_cat) & is_all_org & is_ytd &
            (df_metrics[f] != "__ALL__") & ml
        ]
        n_null = int(rows_in_set[rows_in_set[f] == "__NULL__"]["policy_count"].sum())
        # 各合法值分别统计
        bucket_parts: list[str] = []
        n_valid_total = 0
        for v in aux_default_order(d_aux):
            n = int(rows_in_set[rows_in_set[f] == v]["policy_count"].sum())
            n_valid_total += n
            bucket_parts.append(f"{aux_short_label(f, v)}={n}")
        delta = n_valid_total + n_null - n_overall
        flag = "✓" if delta == 0 else "⚠"
        print(f"        {d_aux['label']:8s} ({f:20s}): {' / '.join(bucket_parts)} / NULL={n_null} | 合 vs 整体偏差={delta} {flag}")

    # ── 生成 HTML ──
    print("[4/4] 渲染 HTML …")
    category_order = CUSTOMER_CATEGORIES_REGISTERED + [
        c for c in cats_seen if c not in CUSTOMER_CATEGORIES_REGISTERED
    ]
    category_order = [c for c in category_order if c in cats_seen]

    # H1 旁 inline meta（v1.22：替代独立状态条卡片，三项关键指标贴在标题右侧）
    ytd_row = overall.loc[overall.period_label == "当年起保"]
    if not ytd_row.empty:
        r = ytd_row.iloc[0]
        total_premium = float(r["premium_sum"] or 0)
        total_policies = int(r["policy_count"] or 0)
    else:
        total_premium, total_policies = 0.0, 0
    page_meta_text = (
        f"{total_policies / 10000:,.2f} 万单 · "
        f"{total_premium / 10000:,.0f} 万元 · "
        f"{len(category_order)} 类客户"
    )

    # 若 metric_keys 不完整，剔除 METRIC_DEFS 中未选中的项（影响表 1 行与表 2 切换按钮）
    if set(metric_keys) != {k for k, *_ in METRIC_DEFS}:
        print(f"      仅渲染指标：{metric_keys}")
        # 此功能保留为未来扩展点；当前实现仍渲染全部 7 指标以与 ad-hoc 对账
        # TODO: 支持 --metrics 裁剪渲染（需将 METRIC_DEFS 传参给 render_table_1/2）

    # ── 卡片 1：整体经营 · 多期对照 ──
    table_1_html = render_table_1(overall, periods, instance_id="main")
    insights_html = build_insights_table_1(overall)
    card_1 = render_card(
        title="整体品质",
        subtitle=(
            "<strong>整体业务在 6 个时间窗下的 7 个核心指标。</strong>"
            "时间窗从左到右按起点早到晚排列：滚动 36/24 个月 → 上年同期 → 滚动 12/6 个月 → 当年起保。"
            "点击 <strong>⇄ 行列转置</strong> 切换「指标×时间窗」与「时间窗×指标」两种视角。"
        ),
        body=insights_html + table_1_html,
        card_id="section-table-1",
    )
    # ── 9 维度全局可下钻映射（drillable_map[field][value] = page_id）──
    # 任意维度卡的每个值都可点击进入对应下钻页，达成"任意两维度互相下钻"
    drill_pages: list[tuple[str, str, str]] = []
    drillable_cats: dict[str, str] = {cat: _dim_page_id("customer_category", cat)
                                       for cat in category_order
                                       if not by_cat[by_cat["customer_category"] == cat].empty}
    drillable_orgs: dict[str, str] = {org: _dim_page_id("org_level_3", org)
                                       for org in orgs_seen}
    drillable_map: dict[str, dict] = {
        "customer_category": drillable_cats,
        "org_level_3":       drillable_orgs,
    }
    for d_aux in AUX_DIMENSIONS:
        f = d_aux["field"]
        # 该 aux 字段下所有合法值都生成可下钻链接（即使该值在数据中暂无行，链接仍渲染——稳定 UX）
        drillable_map[f] = {v: _dim_page_id(f, v) for v in aux_default_order(d_aux)}

    # ① 客户类别下钻：每个 cat 一个 page，Card 2 = 表 3 形态（该 cat × 机构）
    for cat, page_id in drillable_cats.items():
        cat_overall = by_cat[by_cat["customer_category"] == cat]
        cat_by_org  = by_cat_org[by_cat_org["customer_category"] == cat]
        cat_short = short_category(cat)
        # 构造该 cat 在表 3 层次（同城/异地/其他）下的 7 个 DataFrame
        d_sichuan, d_sc_agg, d_rm_agg, d_other_agg, d_sc_rows, d_rm_rows, d_other_rows = \
            build_table_3_data(cat_by_org, cat_overall, share_denominator=overall)
        inst = _make_instance_id("drill-cat", cat)
        table_3_html = render_table_3(
            d_sichuan, d_sc_agg, d_rm_agg, d_other_agg,
            d_sc_rows, d_rm_rows, d_other_rows, periods,
            drillable_dims=drillable_orgs,  # 全维度互通：机构名也可下钻到对应 org 页
            instance_id=inst,
            metric_defs=METRIC_DEFS_T23,
        )
        # 下钻页：表 1 用切片整体生成固定洞察；表 3 用切片机构数据生成 7 指标洞察
        first_insights  = build_insights_table_1(cat_overall)
        second_insights = build_insights_table_3(
            d_sc_rows, d_rm_rows, d_other_rows,
            d_sc_agg, d_rm_agg, d_other_agg,
            overall, instance_id=inst,
        )
        # aux 维度卡：从 by_cat_aux[field] 按 customer_category == cat 过滤
        inst_prefix = f"drill-cat-{cat[:8]}"
        card_1_id = f"section-{inst}-overall"
        card_2_id = f"section-{inst}-org"
        drill_nav_items: list[tuple[str, str]] = [
            (card_1_id, "保单品质"),
            (card_2_id, "三级机构"),
        ]
        aux_cards_html = ""
        for d_aux in AUX_DIMENSIONS:
            f = d_aux["field"]
            sub = by_cat_aux[f][by_cat_aux[f]["customer_category"] == cat]
            card_html = build_aux_card(
                d_aux, sub, periods,
                instance_id_prefix=inst_prefix,
                parent_label=cat_short,
                drillable_dims=drillable_map[f],
                slice_overall=cat_overall,  # v1.26：aux 卡表顶加该 cat 整体行作对照
            )
            if card_html:
                aux_cards_html += card_html
                drill_nav_items.append((f"section-{inst_prefix}-{f}", d_aux["label"]))
        body = render_drill_overview(
            dim_label="客户类别",
            dim_val=cat_short,
            slice_overall=cat_overall,
            second_table_html=table_3_html,
            second_table_title=f"{cat_short} · 三级机构",
            second_table_subtitle="该客户类别在三级机构维度的拆分（四川 / 同城 / 异地 / 其他 四级层次）；切换指标动态重排（仅本卡片内）。",
            periods=periods,
            instance_id=inst,
            ytd_vcr=_vcr_at(cat_overall, "当年起保"),
            m12_vcr=_vcr_at(cat_overall, "滚动12个月"),
            first_insights_html=first_insights,
            second_insights_html=second_insights,
            extra_cards_html=aux_cards_html,
            drill_nav_items=drill_nav_items,
            card_1_id=card_1_id,
            card_2_id=card_2_id,
        )
        drill_pages.append((page_id, f"客户类别 · {cat_short}", body))

    # ② 三级机构下钻：每个 org 一个 page，Card 2 = 表 2 形态（该 org × 客户类别）
    for org, page_id in drillable_orgs.items():
        org_overall = by_org[by_org["org_level_3"] == org]
        org_by_cat  = by_cat_org[by_cat_org["org_level_3"] == org]
        # 该 org 在数据中出现的客户类别（按主页 category_order 顺序保留）
        cats_in_org = [c for c in category_order
                       if c in set(org_by_cat["customer_category"].unique())]
        inst = _make_instance_id("drill-org", org)
        table_2_html = render_table_2(
            org_by_cat, periods, cats_in_org,
            drillable_dims=drillable_cats,  # 全维度互通：类别名也可下钻到对应 cat 页
            instance_id=inst,
            metric_defs=METRIC_DEFS_T23,
            overall=org_overall,  # v1.26：表顶加该 org 整体行作基线
        )
        # 下钻页：表 1 固定洞察；表 2 多指标洞察
        first_insights  = build_insights_table_1(org_overall)
        second_insights = build_insights_table_2(
            org_by_cat, overall, cats_in_org, instance_id=inst,
        )
        # aux 维度卡：从 by_org_aux[field] 按 org_level_3 == org 过滤
        inst_prefix = f"drill-org-{org[:8]}"
        card_1_id = f"section-{inst}-overall"
        card_2_id = f"section-{inst}-cat"
        drill_nav_items: list[tuple[str, str]] = [
            (card_1_id, "保单品质"),
            (card_2_id, "客户类别"),
        ]
        aux_cards_html = ""
        for d_aux in AUX_DIMENSIONS:
            f = d_aux["field"]
            sub = by_org_aux[f][by_org_aux[f]["org_level_3"] == org]
            card_html = build_aux_card(
                d_aux, sub, periods,
                instance_id_prefix=inst_prefix,
                parent_label=org,
                drillable_dims=drillable_map[f],
                slice_overall=org_overall,  # v1.26：aux 卡表顶加该 org 整体行作对照
            )
            if card_html:
                aux_cards_html += card_html
                drill_nav_items.append((f"section-{inst_prefix}-{f}", d_aux["label"]))
        body = render_drill_overview(
            dim_label="三级机构",
            dim_val=org,
            slice_overall=org_overall,
            second_table_html=table_2_html,
            second_table_title=f"{org} · 客户类别",
            second_table_subtitle="该三级机构在客户类别维度的拆分；默认展示变率，切换指标刷新单元格与亮灯（仅本卡片内）。",
            periods=periods,
            instance_id=inst,
            ytd_vcr=_vcr_at(org_overall, "当年起保"),
            m12_vcr=_vcr_at(org_overall, "滚动12个月"),
            first_insights_html=first_insights,
            second_insights_html=second_insights,
            extra_cards_html=aux_cards_html,
            drill_nav_items=drill_nav_items,
            card_1_id=card_1_id,
            card_2_id=card_2_id,
        )
        drill_pages.append((page_id, f"三级机构 · {org}", body))

    # ── ③ 7 aux 维度互相下钻：每个 aux 值一页（共 ≈ 16 页）──
    # 每页 9 卡：保单品质 + 客户类别 + 三级机构 + 6 其他 aux（排除自己，达成"不能下钻到自己"）
    n_aux_pages = 0
    for d_aux in AUX_DIMENSIONS:
        f = d_aux["field"]
        for aux_val in aux_default_order(d_aux):
            slice_overall = by_aux[f][by_aux[f][f] == aux_val].copy()
            if slice_overall.empty:
                continue  # 该值无数据
            page_id = drillable_map[f][aux_val]
            inst = _make_instance_id(f"drill-{f[:4]}", aux_val)
            inst_prefix = inst
            aux_val_label = aux_short_label(f, aux_val)

            # 卡 1: 保单品质（小表 1）
            card_1_id = f"section-{inst_prefix}-overall"
            t1_html = render_table_1(slice_overall, periods, instance_id=inst)
            first_insights = build_insights_table_1(slice_overall)
            card_1_html = render_card(
                title=f"{aux_val_label} · 保单品质",
                subtitle=f"该 {d_aux['label']} 切片在 6 个时间窗的整体行",
                body=first_insights + t1_html,
                card_id=card_1_id,
            )

            # 卡 2: 客户类别
            card_2_id = f"section-{inst_prefix}-cat"
            slice_by_cat = by_cat_aux[f][by_cat_aux[f][f] == aux_val].copy()
            cats_here = [c for c in category_order
                         if c in set(slice_by_cat["customer_category"].unique())]
            cat_table_html = render_table_2(
                slice_by_cat, periods, cats_here,
                drillable_dims=drillable_cats,
                instance_id=inst,
                metric_defs=METRIC_DEFS_T23,
                overall=slice_overall,  # v1.26：表顶加该 aux 切片整体行作基线
            ) if not slice_by_cat.empty else ""
            cat_insights = build_insights_table_2(
                slice_by_cat, overall, cats_here, instance_id=inst,
            ) if not slice_by_cat.empty else ""
            card_2_html = render_card(
                title=f"{aux_val_label} · 客户类别",
                subtitle="按客户类别拆分；点击蓝色类别名下钻",
                body=cat_insights + cat_table_html,
                card_id=card_2_id,
            ) if cat_table_html else ""

            # 卡 3: 三级机构（4 层）
            card_3_id = f"section-{inst_prefix}-org"
            slice_by_org = by_org_aux[f][by_org_aux[f][f] == aux_val].copy()
            if not slice_by_org.empty:
                d_sichuan, d_sc_agg, d_rm_agg, d_other_agg, d_sc_rows, d_rm_rows, d_other_rows = \
                    build_table_3_data(slice_by_org, slice_overall, share_denominator=overall)
                org_table_html = render_table_3(
                    d_sichuan, d_sc_agg, d_rm_agg, d_other_agg,
                    d_sc_rows, d_rm_rows, d_other_rows, periods,
                    drillable_dims=drillable_orgs,
                    instance_id=inst,
                    metric_defs=METRIC_DEFS_T23,
                )
                org_insights = build_insights_table_3(
                    d_sc_rows, d_rm_rows, d_other_rows,
                    d_sc_agg, d_rm_agg, d_other_agg,
                    overall, instance_id=inst,
                )
                card_3_html = render_card(
                    title=f"{aux_val_label} · 三级机构",
                    subtitle="四川 / 同城 / 异地 / 其他 四层；点击蓝色机构名下钻",
                    body=org_insights + org_table_html,
                    card_id=card_3_id,
                )
            else:
                card_3_html = ""

            # drill-toc 起始 3 项（仅当对应卡有内容时加）
            drill_nav_items: list[tuple[str, str]] = [(card_1_id, "保单品质")]
            if card_2_html: drill_nav_items.append((card_2_id, "客户类别"))
            if card_3_html: drill_nav_items.append((card_3_id, "三级机构"))

            # 卡 4-9: 6 个其他 aux（排除自己）
            other_aux_html = ""
            for d_other in AUX_DIMENSIONS:
                of = d_other["field"]
                if of == f: continue
                pair_key = frozenset([f, of])
                sub = by_aux_aux[pair_key][by_aux_aux[pair_key][f] == aux_val].copy()
                c_html = build_aux_card(
                    d_other, sub, periods,
                    instance_id_prefix=inst_prefix,
                    parent_label=aux_val_label,
                    drillable_dims=drillable_map[of],
                    slice_overall=slice_overall,  # v1.26：aux 卡表顶加该 aux 值整体行作对照
                )
                if c_html:
                    other_aux_html += c_html
                    drill_nav_items.append((f"section-{inst_prefix}-{of}", d_other["label"]))

            # 装配 body：drill-layout (toc + main)
            items_html = "".join(
                f'<li><a href="#{escape(sid)}" class="drill-toc-link" data-target="{escape(sid)}">{escape(label)}</a></li>'
                for sid, label in drill_nav_items
            )
            toc_html = (
                f'<nav class="drill-toc" aria-label="目录">'
                f'<div class="drill-toc-title">目录</div>'
                f'<ol>{items_html}</ol>'
                f'</nav>'
            )
            all_cards = card_1_html + card_2_html + card_3_html + other_aux_html
            body = (
                f'<div class="drill-layout">'
                f'{toc_html}'
                f'<div class="drill-main">{all_cards}</div>'
                f'</div>'
            )
            drill_pages.append((page_id, f"{d_aux['label']} · {aux_val_label}", body))
            n_aux_pages += 1

    print(f"      下钻入口：客户类别 {len(drillable_cats)} 个 / 机构 {len(drillable_orgs)} 个 / aux {n_aux_pages} 个"
          f" → 共 {len(drill_pages)} 个子页")

    # ── 卡片 2：客户类别 × 时间窗 · 点击下钻机构拆分 ──
    table_2_html = render_table_2(
        by_cat, periods, category_order,
        drillable_dims=drillable_cats,
        instance_id="main",
        metric_defs=METRIC_DEFS_T23,
        overall=overall,  # v1.25 P5：表顶加"整体"基准行
    )
    insights_2_html = build_insights_table_2(by_cat, overall, category_order)
    card_2 = render_card(
        title="客户类别",
        subtitle=(
            "<strong>11 个客户类别在 6 个时间窗下的横向对照。</strong>"
            "顶部按钮切换 7 个指标，亮灯随之刷新；<strong>点击列头按该列降/升序排列</strong>"
            "（按当前指标）；<strong>蓝色类别名可点击下钻</strong>看该类别在三级机构维度的拆分。"
        ),
        body=insights_2_html + table_2_html,
        card_id="section-table-2",
    )

    # ── 卡片 3：分机构 · 同城 vs 异地 · 可下钻 ──
    table_3_html = render_table_3(
        sichuan_agg, sc_agg, rm_agg, other_agg,
        sc_rows, rm_rows, other_rows, periods,
        drillable_dims=drillable_orgs,
        instance_id="main",
        metric_defs=METRIC_DEFS_T23,
    )
    insights_3_html = build_insights_table_3(
        sc_rows, rm_rows, other_rows,
        sc_agg, rm_agg, other_agg,
        overall,
    )
    card_3 = render_card(
        title="三级机构",
        subtitle=(
            "<strong>三级机构按「四川 / 同城 / 异地 / 其他」四层结构展示。</strong>"
            "同城 7 机构（成都本部各支）+ 异地 7 机构（中支）默认折叠，"
            "<strong>点击聚合行展开</strong>；切换指标后子机构按当前指标降序自动重排；"
            "<strong>点击列头按该列排序</strong>；<strong>蓝色机构名可点击下钻</strong>看该机构在客户类别维度的拆分。"
        ),
        body=insights_3_html + table_3_html,
        card_id="section-table-3",
    )

    # ── 主页 7 aux 卡（与下钻页同结构，蓝色行可下钻到对应 aux 值的页面）──
    main_aux_cards_html = ""
    main_aux_nav: list[tuple[str, str]] = []
    for d_aux in AUX_DIMENSIONS:
        f = d_aux["field"]
        # build_aux_card 用 "main" 作为 instance_id_prefix 区别下钻页
        card_html = build_aux_card(
            d_aux, by_aux[f], periods,
            instance_id_prefix="main",
            parent_label="整体",
            drillable_dims=drillable_map[f],
            slice_overall=overall,  # v1.26：主页 aux 卡表顶加全局整体行作基线
        )
        if card_html:
            main_aux_cards_html += card_html
            main_aux_nav.append((f"section-main-{f}", d_aux["label"]))

    cards_html = card_1 + card_2 + card_3 + main_aux_cards_html + INTERACT_JS
    info_html = build_info_card_html(
        cutoff_date.isoformat(), cutoff_date.year, cutoff_date.month, cutoff_date.day
    )

    # 左侧目录导航：10 项（3 主维度 + 7 aux）
    nav_items = [
        ("section-table-1", "整体品质"),
        ("section-table-2", "客户类别"),
        ("section-table-3", "三级机构"),
    ] + main_aux_nav

    html = render_page(
        title=f"多期车险保单品质对比 · {cutoff_date.isoformat()}",
        cards_html=cards_html,
        info_html=info_html,
        drill_pages=drill_pages,
        nav_items=nav_items,
        meta_text=page_meta_text,
        footer_text=f"数据截止 {cutoff_date.isoformat()} · 由 skill diagnose-period-trend 生成",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"      已写入：{out_path}（{len(html):,} 字符）")
    print(f"      浏览器打开：open {out_path}")

    # 推送 IM（仅在显式 --push-im 时）
    if push_im:
        print(f"      [TODO] push-im 链路待接入 chexian-im-push skill（feishu_doc={feishu_doc} wecom_chat={wecom_chat}）")

    return {
        "output_path": str(out_path),
        "cutoff": cutoff_date.isoformat(),
        "period_count": len(periods),
        "category_count": len(category_order),
        "qc_monotonic_ok": monotonic_ok,
        "qc_factor_ok": factor_ok,
    }


_NEW_VIEW_CHOICES = ("all", "v1", "v3", "v4")


def run_multi_view(
    cutoff: str | None = None,
    project_root: str | None = None,
    output_dir: str | None = None,
    view: str = "all",
) -> dict[str, str]:
    """生成 V1 驾驶舱 / V3 叙事周报 / V4 超表（三视图）。

    view: "all" 生成全部三个；"v1"/"v3"/"v4" 仅生成指定视图。
    返回 {view_name: output_path}。
    """
    from anomalies import compute_top_anomalies  # type: ignore[import-not-found]
    from render_v1 import render_v1_page         # type: ignore[import-not-found]
    from render_v3 import render_v3_page         # type: ignore[import-not-found]
    from render_v4 import render_v4_page         # type: ignore[import-not-found]

    root = _resolve_project_root(project_root)
    con  = duckdb.connect(":memory:")

    cutoff_date = _resolve_cutoff(cutoff, root, con)

    out_dir = Path(output_dir).resolve() if output_dir else (
        root / "public/reports/diagnose-period-trend"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # 固定用全部 6 个时间窗（新三视图设计的基准）
    periods = build_periods(cutoff_date, [k for k, _ in PERIOD_KEYS])
    print(f"[1/3] 时间窗（{len(periods)} 个）：{[p.label for p in periods]}")

    print("[2/3] 执行 DuckDB 查询 …")
    df_raw     = con.execute(build_sql(cutoff_date, periods, root)).fetchdf()
    con.close()
    print(f"      返回 {len(df_raw)} 行")
    df = derive_metrics(df_raw)

    views_to_run = _NEW_VIEW_CHOICES[1:] if view == "all" else [view]
    results: dict[str, str] = {}

    print(f"[3/3] 渲染视图：{views_to_run}")
    for v in views_to_run:
        if v == "v1":
            anomalies = compute_top_anomalies(df, n=8)
            html = render_v1_page(df, cutoff_date, anomalies)
            fname = f"{cutoff_date.isoformat()}-dashboard.html"
        elif v == "v3":
            anomalies = compute_top_anomalies(df, n=8)
            html = render_v3_page(df, cutoff_date, anomalies)
            fname = f"{cutoff_date.isoformat()}-weekly.html"
        elif v == "v4":
            html = render_v4_page(df, cutoff_date)
            fname = f"{cutoff_date.isoformat()}-table.html"
        else:
            print(f"      跳过未知视图：{v}")
            continue

        path = out_dir / fname
        path.write_text(html, encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"      [{v}] 已写入：{path}（{size_kb:.1f} KB）")
        print(f"      浏览器预览：open {path}")
        results[v] = str(path)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="多期车险保单品质对比（diagnose-period-trend skill）"
    )
    parser.add_argument("--cutoff", default=None,
                        help="数据截止日 YYYY-MM-DD；默认动态查 MAX(insurance_start_date)")
    parser.add_argument("--project-root", default=None,
                        help="项目根路径；默认 $CHEXIAN_PROJECT_ROOT 或 cwd")
    parser.add_argument("--output-dir", default=None,
                        help="输出目录；默认 <project_root>/public/reports/diagnose-period-trend/")
    parser.add_argument("--output", default=None,
                        help="完整输出文件路径（覆盖 --output-dir，仅 legacy 模式生效）")
    parser.add_argument("--view", default="legacy",
                        choices=("legacy", "all", "v1", "v3", "v4"),
                        help=(
                            "渲染视图：legacy=旧多期对照（默认）；"
                            "v1=驾驶舱；v3=叙事周报；v4=超表；all=三新视图全部生成"
                        ))
    parser.add_argument("--metrics", default=None,
                        help=f"逗号分隔指标 key 白名单（可选：{','.join(k for k,*_ in METRIC_DEFS)}）")
    parser.add_argument("--exclude-categories", default=None,
                        help="逗号分隔的客户类别黑名单（如 摩托车,挂车）")
    parser.add_argument("--periods", default=None, dest="periods_arg",
                        help=f"逗号分隔时间窗 key（可选：{','.join(k for k,_ in PERIOD_KEYS)}）")
    parser.add_argument("--push-im", action="store_true", help="跑完是否推 IM")
    parser.add_argument("--feishu-doc", default=None, help="飞书文档 token")
    parser.add_argument("--wecom-chat", default=None, help="企微目标 chat id")
    args = parser.parse_args()

    if args.view in _NEW_VIEW_CHOICES:
        run_multi_view(
            cutoff=args.cutoff,
            project_root=args.project_root,
            output_dir=args.output_dir,
            view=args.view,
        )
    else:
        # legacy：传入 run() 支持的全部参数
        run(
            cutoff=args.cutoff,
            project_root=args.project_root,
            output_dir=args.output_dir,
            output=args.output,
            metrics=args.metrics,
            exclude_categories=args.exclude_categories,
            periods_arg=args.periods_arg,
            push_im=args.push_im,
            feishu_doc=args.feishu_doc,
            wecom_chat=args.wecom_chat,
        )


if __name__ == "__main__":
    main()
