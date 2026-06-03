"""HTML 渲染层：PY × DW 发展三角形 + 5 指标切换器 + 维度卡片。

复用 chexian-report-shell/lib 的 render_card / render_callout / render_page / light。
"""
from __future__ import annotations

import hashlib
import html
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# 导入 dhr_lib（2026-05-17 重命名：原 diagnose-html-render → chexian-report-shell）
_DHR_PATH = Path.home() / ".claude/skills/chexian-report-shell"
if str(_DHR_PATH) not in sys.path:
    sys.path.insert(0, str(_DHR_PATH))
from lib import (  # type: ignore[no-redef]
    light, fmt_pct, fmt_num,
    render_card, render_callout, render_page,
    short_team_name,
    SHORT_CATEGORY_LABEL,
)

try:
    from .query import DIM_FIELDS, DW_ANCHORS, METRIC_DEFS
except ImportError:  # pragma: no cover
    from query import DIM_FIELDS, DW_ANCHORS, METRIC_DEFS  # type: ignore[no-redef]


# 完成度阈值：≥ COMPLETE_TH 算 ✓ 完整；< MISSING_TH 算 — 未到；中间为 △ 部分
COMPLETE_TH = 0.95
MISSING_TH = 0.05


def drill_slug(dim_value: str) -> str:
    """下钻子页文件名 slug：MD5 前 8 位（避免中文 URL 编码兼容问题）。"""
    return hashlib.md5(str(dim_value).encode("utf-8")).hexdigest()[:8]


def select_top_dim_values(
    derived: pd.DataFrame, dim_cfg: dict, current_py: int,
) -> list[str]:
    """选取该维度在 current_py 下用于展示的维度值（按满期保费规模排序，应用 top_n）。

    与 render_dim_card 内部逻辑保持一致，便于 cli.py 在生成下钻页时复用同一组维度值。
    """
    key = dim_cfg["key"]
    top_n = dim_cfg.get("top_n")
    cur_sub = derived[(derived["dim_key"] == key) & (derived["py"] == current_py)]
    if cur_sub.empty:
        return []
    sort_anchor_dw = next(
        (dw for dw in (365, 270, 180, 90, 30) if dw in cur_sub["dw_days"].unique()),
        None,
    )
    if sort_anchor_dw:
        sort_df = (
            cur_sub[cur_sub["dw_days"] == sort_anchor_dw]
            .set_index("dim_value")["earned_premium_sum"]
            .sort_values(ascending=False)
        )
        values = sort_df.index.tolist()
    else:
        values = cur_sub["dim_value"].unique().tolist()
    if top_n:
        values = values[:top_n]
    return [str(v) for v in values]

# DW 列中文标签（30/90/180/270 天 + 满 1 年 / 满 2 年）
DW_LABELS: dict[int, str] = {
    30: "30 天", 90: "90 天", 180: "180 天", 270: "270 天",
    365: "满 1 年", 730: "满 2 年",
}

# ── mini 趋势图（借鉴 diagnose-period-trend 96×28 polyline + circles 风格） ──
_SPARK_W, _SPARK_H, _SPARK_MARGIN = 96, 28, 3


def _min_range_for_kind(kind: str) -> float:
    """最小可视范围：防止小波动被放大成"剧烈"曲线。"""
    if kind == "pct":
        return 5.0      # 5 个百分点
    if kind == "coef":
        return 0.05
    return 0.0          # money0 等不限制


def _sparkline_svg(values: list, alert_class: str, min_range: float = 0.0) -> str:
    """渲染 6 期趋势 SVG。values 按时序从早到晚（30→730 天）；None/NaN 表示缺失。

    alert_class: "alert-green/blue/yellow/red/gray" → 决定曲线颜色（与末值亮灯一致）
    末值圆点放大（r=2.4 vs 1.4），视觉上突出"当前位置"。
    """
    cleaned: list[tuple[int, float]] = []
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        cleaned.append((i, float(v)))
    if len(cleaned) < 2:
        return '<span class="spark-empty">—</span>'

    ys = [v for _, v in cleaned]
    y_min, y_max = min(ys), max(ys)
    if min_range > 0 and (y_max - y_min) < min_range:
        mid = (y_max + y_min) / 2
        y_min = mid - min_range / 2
        y_max = mid + min_range / 2
    y_rng = y_max - y_min if y_max > y_min else 1.0
    n_steps = max(1, len(values) - 1)

    def coord(i: int, v: float) -> tuple[float, float]:
        x = _SPARK_MARGIN + (i / n_steps) * (_SPARK_W - 2 * _SPARK_MARGIN)
        y = _SPARK_H - _SPARK_MARGIN - ((v - y_min) / y_rng) * (_SPARK_H - 2 * _SPARK_MARGIN)
        return (x, y)

    points = " ".join(f"{coord(i, v)[0]:.1f},{coord(i, v)[1]:.1f}" for i, v in cleaned)
    last_idx = cleaned[-1][0]
    circles = "".join(
        f'<circle cx="{coord(i, v)[0]:.1f}" cy="{coord(i, v)[1]:.1f}" r="{2.4 if i == last_idx else 1.4}"/>'
        for i, v in cleaned
    )
    spark_cls = alert_class.replace("alert-", "spark-") if alert_class else "spark-gray"
    return (
        f'<svg class="sparkline" viewBox="0 0 {_SPARK_W} {_SPARK_H}" '
        f'width="{_SPARK_W}" height="{_SPARK_H}" preserveAspectRatio="none">'
        f'<g class="spark-group {spark_cls}">'
        f'<polyline points="{points}" fill="none"/>{circles}</g></svg>'
    )


def _fmt_cell(value: Optional[float], kind: str) -> str:
    """根据指标 kind 格式化值。"""
    if value is None or pd.isna(value):
        return "—"
    if kind == "pct":
        return f"{value:.1f}%"
    if kind == "money0":
        return f"{value:,.0f}"
    if kind == "wan":
        # 满期保费等大额绝对值：折万元、保 1 位小数，避免 cell 过宽
        return f"{value / 10000:,.1f}"
    if kind == "coef":
        return f"{value:.3f}"
    return str(value)


def render_dev_triangle(
    overall_df: pd.DataFrame,
    *,
    show_overall_row: bool = False,
    table_id: str = "card1-triangle",
    active_metric: str = "mature_loss_ratio",
) -> str:
    """渲染 Card 1 / Card N 整体三角形（PY 行 × DW 列）。

    输入 DataFrame 列必须包含：
      py, dw_days, policy_count, completeness_ratio,
      mature_loss_ratio, mature_incident_rate, avg_claim_amount,
      bi_case_ratio_pct, bi_amount_ratio_pct
    """
    df = overall_df.copy().sort_values(["py", "dw_days"], ascending=[False, True])

    # 全局控制栏驱动：年度成行、指标由顶部统一切换；本表不再自带切换器
    # 表头（趋势列放在第 2 位，先看趋势再看具体数字）
    head_cells = (
        '<th class="dim-col">保单年度</th>'
        + '<th class="trend-th">趋势</th>'
        + "".join(f'<th class="num-th">{DW_LABELS[d]}</th>' for d in DW_ANCHORS)
    )
    thead = f'<thead><tr>{head_cells}</tr></thead>'

    # 表体
    py_order = sorted(df["py"].unique(), reverse=True)
    rows_html: list[str] = []
    for py in py_order:
        py_int = int(py)
        py_rows = df[df["py"] == py].set_index("dw_days")
        # 该 PY 的总保单数（同一 PY 在不同 DW 行的 policy_count 相同）
        n = int(py_rows["policy_count"].max() or 0)

        cells = [f'<td class="dim-cell">{py_int}</td>']
        # 收集每个指标的 6 期数据序列 + 365d 亮灯（用于趋势列）
        trend_series: dict[str, list[Optional[float]]] = {mid: [] for mid, *_ in METRIC_DEFS}
        trend_light: dict[str, str] = {}

        for dw in DW_ANCHORS:
            if dw not in py_rows.index:
                cells.append('<td class="cell-missing">—</td>')
                for mid, *_ in METRIC_DEFS:
                    trend_series[mid].append(None)
                continue
            r = py_rows.loc[dw]
            completeness = float(r.get("completeness_ratio") or 0.0)

            def render_cell(v: Optional[float], kind: str, mid: str) -> tuple[str, str, str]:
                """返回 (展示文本, cell CSS class, alert class for trend)。"""
                if v is None or pd.isna(v) or completeness < MISSING_TH:
                    return ("—", "cell-missing", "alert-gray")
                num_text = _fmt_cell(v, kind)
                th_key = {
                    "mature_loss_ratio":    "earned_loss_ratio_pct",
                    "mature_incident_rate": "earned_loss_freq_pct",
                }.get(mid)
                alert = "alert-gray"
                if th_key:
                    light_cls, _ = light(th_key, v, n)
                    alert = light_cls or "alert-gray"
                if completeness < COMPLETE_TH:
                    return (
                        f'{num_text} <span class="cell-marker">△</span>',
                        "cell-partial", alert,
                    )
                cls = "cell-complete" + (f" {alert}" if alert != "alert-gray" else "")
                return (num_text, cls, alert)

            data_attrs = []
            for mid, _name, kind, _th in METRIC_DEFS:
                v = r.get(mid)
                text, cls, alert = render_cell(v, kind, mid)
                data_attrs.append(f'data-{mid}-text="{html.escape(text, quote=True)}"')
                data_attrs.append(f'data-{mid}-cls="{cls}"')
                # 累积趋势序列（用原始数值，None 表示缺失）
                trend_series[mid].append(float(v) if v is not None and not pd.isna(v) else None)
                # 365 天作为亮灯锚点（精算最经典满期口径）
                if dw == 365:
                    trend_light[mid] = alert

            # 默认显示 active_metric
            active_kind = next(k for mid, _, k, _ in METRIC_DEFS if mid == active_metric)
            active_text, active_cls, _ = render_cell(
                r.get(active_metric), active_kind, active_metric,
            )

            tooltip = (
                f"保单 {n:,} 单 · 完成度 {completeness*100:.1f}%"
                if completeness < COMPLETE_TH
                else f"保单 {n:,} 单 · 完整观察"
            )
            cells.append(
                f'<td class="dev-cell {active_cls}" '
                f'title="{html.escape(tooltip, quote=True)}" '
                f'{" ".join(data_attrs)}>{active_text}</td>'
            )

        # 趋势 cell：5 指标 trend 数据嵌入 + 默认渲染 active_metric SVG
        trend_attrs: list[str] = []
        for mid, _name, kind, _th in METRIC_DEFS:
            seq = trend_series[mid]
            seq_str = "/".join("" if v is None else f"{v:.4f}" for v in seq)
            light_cls = trend_light.get(mid, "alert-gray")
            trend_attrs.append(f'data-{mid}-trend="{seq_str}"')
            trend_attrs.append(f'data-{mid}-light="{light_cls}"')
            trend_attrs.append(f'data-{mid}-minrange="{_min_range_for_kind(kind)}"')

        active_seq = trend_series[active_metric]
        active_alert = trend_light.get(active_metric, "alert-gray")
        active_kind = next(k for mid, _, k, _ in METRIC_DEFS if mid == active_metric)
        active_spark = _sparkline_svg(
            active_seq, active_alert, _min_range_for_kind(active_kind),
        )
        # 趋势 cell 放在第 2 位（紧跟维度列），便于先看趋势再看细节数字
        cells.insert(
            1,
            f'<td class="trend-cell" {" ".join(trend_attrs)}>{active_spark}</td>',
        )
        rows_html.append(f'<tr>{"".join(cells)}</tr>')

    tbody = f'<tbody>{"".join(rows_html)}</tbody>'
    table_html = (
        f'<table class="data-table dev-triangle" id="{table_id}" '
        f'data-triangle-kind="overall">'
        f'{thead}{tbody}</table>'
    )

    return f'<div class="dev-triangle-wrap">{table_html}</div>'


# ---------- Card 2-10：维度卡片（当前 PY 切片） ----------

# 12 维度卡片配置（v1.1：删 terminal_source；加 team / insurance_type / is_new_car / is_telemarketing）
# 顺序对应 Card 2-13；去除 kicker（UI 中文化）
DIM_CARDS: list[dict] = [
    {"key": "customer_category",    "label": "客户类别",
     "value_labels": SHORT_CATEGORY_LABEL},
    {"key": "org_level_3",          "label": "三级机构"},
    {"key": "team",                 "label": "团队", "top_n": 10,
     "value_shortener": short_team_name},
    {"key": "salesman_chinese",     "label": "业务员", "top_n": 15},
    {"key": "insurance_grade",      "label": "风险等级"},
    {"key": "insurance_type",       "label": "险类"},
    {"key": "coverage_combination", "label": "险别组合"},
    {"key": "is_nev",               "label": "是否新能源",
     "value_labels": {"true": "新能源", "false": "燃油", "__NULL__": "未知"}},
    {"key": "is_new_car",           "label": "是否新车",
     "value_labels": {"true": "新车", "false": "旧车", "__NULL__": "未知"}},
    {"key": "is_transfer",          "label": "是否过户车",
     "value_labels": {"true": "过户", "false": "非过户", "__NULL__": "未知"}},
    {"key": "is_renewal",           "label": "是否续保",
     "value_labels": {"true": "续保", "false": "新保", "__NULL__": "未知"}},
    {"key": "is_telemarketing",     "label": "是否电销",
     "value_labels": {"true": "电销", "false": "非电销", "__NULL__": "未知"}},
]


def _classify_cell(
    value: Optional[float], kind: str, mid: str,
    completeness: float, n_policies: int,
) -> tuple[str, str]:
    """单元格分类：返回 (展示文本, CSS class)。完成度决定 ✓/△/— 标记 + 亮灯。"""
    if value is None or pd.isna(value) or completeness < MISSING_TH:
        return ("—", "cell-missing")
    num_text = _fmt_cell(value, kind)
    if completeness < COMPLETE_TH:
        return (f'{num_text} <span class="cell-marker">△</span>', "cell-partial")
    th_key = {
        "mature_loss_ratio":    "earned_loss_ratio_pct",
        "mature_incident_rate": "earned_loss_freq_pct",
    }.get(mid)
    cls = "cell-complete"
    if th_key:
        light_cls, _ = light(th_key, value, n_policies)
        if light_cls:
            cls = f"cell-complete {light_cls}"
    return (num_text, cls)


def _cell_alert_class(
    value: Optional[float], mid: str,
    completeness: float, n_policies: int,
) -> str:
    """单独提取 alert 类（用于 sparkline 染色），不打 △/cell-* 标记。"""
    if value is None or pd.isna(value) or completeness < MISSING_TH:
        return "alert-gray"
    th_key = {
        "mature_loss_ratio":    "earned_loss_ratio_pct",
        "mature_incident_rate": "earned_loss_freq_pct",
    }.get(mid)
    if not th_key:
        return "alert-gray"
    light_cls, _ = light(th_key, value, n_policies)
    return light_cls or "alert-gray"


def render_dim_card(
    derived: pd.DataFrame,
    *,
    dim_cfg: dict,
    current_py: int,
    overall_df: pd.DataFrame,
    py_options: list[int],
    active_metric: str = "mature_loss_ratio",
    enable_drill_link: bool = True,
    table_id_override: Optional[str] = None,
) -> str:
    """渲染单个维度卡片：5 PY × 6 DW × N 维度值（双切换器 + 整体基准行）。

    cell 嵌入 PY × 5 指标全套 data-* 矩阵；切 PY 通过 table.data-active-py 联动 cell innerHTML。
    Row 顺序按 current_py 切片排序固定（避免切 PY 时 top_n 跳变）。

    enable_drill_link: 主页传 True（dim_cell 加 <a> 链接进下钻子页）；
                      子页副维度 Card 传 False（v2.1 只一层下钻，避免多级树）。
    table_id_override: 子页副维度 Card 用此参数避免与主页 table_id 冲突。
    """
    key = dim_cfg["key"]
    label = dim_cfg["label"]
    value_labels = dim_cfg.get("value_labels", {})
    value_shortener = dim_cfg.get("value_shortener")  # 可选：原值 → 简称（如 "蒲江业务团队" → "蒲江"）
    top_n = dim_cfg.get("top_n")

    # 维度全集（所有 PY），用于 cell 嵌入；current_py 子集用于 row 排序
    full_sub = derived[derived["dim_key"] == key]
    cur_sub = full_sub[full_sub["py"] == current_py]
    if cur_sub.empty:
        return ""

    # 选 365d / 270d / ... 排序锚点（current_py 切片下）
    sort_anchor_dw = next(
        (dw for dw in (365, 270, 180, 90, 30) if dw in cur_sub["dw_days"].unique()),
        None,
    )
    if sort_anchor_dw:
        # 按满期保费规模（earned_premium_sum）从大到小排序——整体基准行另行钉在首行（见下方 rows_data）
        sort_df = (
            cur_sub[cur_sub["dw_days"] == sort_anchor_dw]
            .set_index("dim_value")["earned_premium_sum"]
            .sort_values(ascending=False)
        )
        dim_values = sort_df.index.tolist()
        if top_n:
            dim_values = dim_values[:top_n]
    else:
        dim_values = cur_sub["dim_value"].unique().tolist()

    # 行数据：(display_label, raw_value, {py_int: df}) — 整体行 raw_value=""
    rows_data: list[tuple[str, str, dict[int, pd.DataFrame]]] = []
    overall_by_py = {
        int(py): overall_df[overall_df["py"] == py].set_index("dw_days")
        for py in py_options
        if not overall_df[overall_df["py"] == py].empty
    }
    if overall_by_py:
        rows_data.append(("整体", "", overall_by_py))
    for dv in dim_values:
        dv_by_py: dict[int, pd.DataFrame] = {}
        for py in py_options:
            dvp = full_sub[(full_sub["py"] == py) & (full_sub["dim_value"] == dv)]
            if not dvp.empty:
                dv_by_py[int(py)] = dvp.set_index("dw_days")
        if dv_by_py:
            raw = str(dv)
            if value_shortener:
                display_label = value_shortener(raw) or raw
            else:
                display_label = value_labels.get(raw, raw)
            rows_data.append((display_label, raw, dv_by_py))

    card_id = table_id_override or f"card-{key}"  # 容器 div id（用于 nav anchor）
    table_id = f"{card_id}-table"  # table 自身 id（避免与 div 冲突）

    # 全局控制栏驱动：顶部「保单年度 + 指标」统一切换所有卡；本卡不再自带切换器
    # 表头（趋势列放在第 2 位，先看趋势再看具体数字；保单数信息已在 cell tooltip 中）
    head_cells = (
        f'<th class="dim-col">{html.escape(label)}</th>'
        + '<th class="trend-th">趋势</th>'
        + "".join(f'<th class="num-th">{DW_LABELS[d]}</th>' for d in DW_ANCHORS)
    )
    thead = f"<thead><tr>{head_cells}</tr></thead>"

    # 表体：每个 cell 嵌入 5 PY × 5 指标 × 2 attr = 50 attr；趋势 cell 嵌 5 PY × 5 metric × 3 attr = 75 attr
    active_kind = next(k for mid, _, k, _ in METRIC_DEFS if mid == active_metric)
    rows_html: list[str] = []
    for label_text, raw_value, by_py in rows_data:
        is_overall = (label_text == "整体")
        cur_pdf = by_py.get(current_py)
        n_cur = int(cur_pdf["policy_count"].max() or 0) if cur_pdf is not None else 0
        tr_cls = "row-total" if is_overall else ""
        # 非整体行 dim_cell 加下钻链接（仅主页表；子页副维度 Card 禁用 drill_link）
        if is_overall or not raw_value or not enable_drill_link:
            dim_cell_html = f'<td class="dim-cell">{html.escape(label_text)}</td>'
        else:
            drill_url = f"drill/{key}/{drill_slug(raw_value)}.html"
            dim_cell_html = (
                f'<td class="dim-cell">'
                f'<a class="drill-link" href="{drill_url}">{html.escape(label_text)}</a>'
                f'</td>'
            )
        cells = [dim_cell_html]

        # 每个 PY 的 6 期趋势序列（按 mid 归集） + 365 天亮灯
        trend_series: dict[int, dict[str, list[Optional[float]]]] = {
            py: {mid: [] for mid, *_ in METRIC_DEFS} for py in py_options
        }
        trend_light: dict[int, dict[str, str]] = {py: {} for py in py_options}

        for dw in DW_ANCHORS:
            data_attrs: list[str] = []
            for py_int in py_options:
                pdf = by_py.get(py_int)
                if pdf is None or dw not in pdf.index:
                    for mid, _name, _kind, _th in METRIC_DEFS:
                        data_attrs.append(f'data-py{py_int}-{mid}-text="—"')
                        data_attrs.append(f'data-py{py_int}-{mid}-cls="cell-missing"')
                        trend_series[py_int][mid].append(None)
                    continue
                r = pdf.loc[dw]
                completeness = float(r.get("completeness_ratio") or 0.0)
                n_py = int(pdf["policy_count"].max() or 0)
                for mid, _name, kind, _th in METRIC_DEFS:
                    v = r.get(mid)
                    text, cls = _classify_cell(v, kind, mid, completeness, n_py)
                    data_attrs.append(
                        f'data-py{py_int}-{mid}-text="{html.escape(text, quote=True)}"'
                    )
                    data_attrs.append(f'data-py{py_int}-{mid}-cls="{cls}"')
                    trend_series[py_int][mid].append(
                        float(v) if v is not None and not pd.isna(v) else None
                    )
                    if dw == 365:
                        trend_light[py_int][mid] = _cell_alert_class(
                            v, mid, completeness, n_py,
                        )

            # 默认显示 current_py × active_metric
            default_text, default_cls = "—", "cell-missing"
            tooltip = f"{label_text} · {current_py} 年 · 暂无数据"
            if cur_pdf is not None and dw in cur_pdf.index:
                r = cur_pdf.loc[dw]
                completeness = float(r.get("completeness_ratio") or 0.0)
                n_py = int(cur_pdf["policy_count"].max() or 0)
                default_text, default_cls = _classify_cell(
                    r.get(active_metric), active_kind, active_metric,
                    completeness, n_py,
                )
                tooltip = (
                    f"{label_text} · {current_py} 年 · {n_py:,} 单 · 完成度 {completeness*100:.1f}%"
                    if completeness < COMPLETE_TH
                    else f"{label_text} · {current_py} 年 · {n_py:,} 单 · 完整观察"
                )

            cells.append(
                f'<td class="dev-cell {default_cls}" '
                f'title="{html.escape(tooltip, quote=True)}" '
                f'{" ".join(data_attrs)}>{default_text}</td>'
            )

        # 趋势 cell：5 PY × 5 metric 数据嵌入 + 默认渲染 current_py × active_metric SVG
        trend_attrs: list[str] = []
        for py_int in py_options:
            for mid, _name, kind, _th in METRIC_DEFS:
                seq = trend_series[py_int][mid]
                seq_str = "/".join("" if v is None else f"{v:.4f}" for v in seq)
                alert_cls = trend_light[py_int].get(mid, "alert-gray")
                trend_attrs.append(f'data-py{py_int}-{mid}-trend="{seq_str}"')
                trend_attrs.append(f'data-py{py_int}-{mid}-light="{alert_cls}"')
                trend_attrs.append(f'data-py{py_int}-{mid}-minrange="{_min_range_for_kind(kind)}"')

        active_seq = trend_series[current_py][active_metric]
        active_alert = trend_light[current_py].get(active_metric, "alert-gray")
        active_spark = _sparkline_svg(
            active_seq, active_alert, _min_range_for_kind(active_kind),
        )
        # 趋势 cell 放在第 2 位（紧跟维度列）
        cells.insert(
            1,
            f'<td class="trend-cell" {" ".join(trend_attrs)}>{active_spark}</td>',
        )

        rows_html.append(f'<tr class="{tr_cls}">{"".join(cells)}</tr>')

    tbody = f"<tbody>{''.join(rows_html)}</tbody>"
    table_html = (
        f'<table class="data-table dev-triangle" id="{table_id}" '
        f'data-triangle-kind="dim" data-active-py="{current_py}">'
        f'{thead}{tbody}</table>'
    )

    body = f'<div class="dev-triangle-wrap">{table_html}</div>'
    subtitle = (
        f"<strong>{label} · 跟随顶部全局年度（默认 {current_py}）× 指标</strong>。"
        "首行<strong>整体</strong>为同期基准，"
        f"其余各行按 {current_py} 年满期保费从大到小排序。"
        + (f" 仅显示前 {top_n} 名。" if top_n else "")
    )
    return render_card(
        title=f"{label} · 发展曲线",
        subtitle=subtitle,
        body=body,
        card_id=card_id,
    )


# ---------- 下钻子页（单维度值的 5 PY × 6 DW 三角形） ----------


def render_drill_page(
    derived: pd.DataFrame,
    *,
    dim_key: str,
    dim_value: str,
    display_label: str,
    dim_card_label: str,
    sub_data: dict[str, pd.DataFrame],
    cutoff,
    current_py: int,
    py_options: list[int],
    dim_cards: list[dict],
    main_page_filename: str = "preview-mvp.html",
) -> str:
    """渲染单个维度值的 v2.1 下钻子页 HTML。

    Args:
      dim_key/dim_value: 父维度（如 team='宜宾业务二部'）
      display_label: 父维度值显示标签（如 '宜宾二部'，已 short_team_name 处理）
      dim_card_label: 父维度名称（如 '团队'）
      sub_data: cli.py 用 build_subdim_batch_sql 跑完的副维度数据字典
                {child_dim: derived_df(含 dim_key/dim_value + 5 指标 + completeness)}
      current_py: 当前激活的保单年度（与主页一致，默认 2025）
      py_options: PY 选项列表（用于副维度 Card 双切换器）
      dim_cards: 全部 12 维度配置（用于循环生成 11 副维度 Card）
    """
    # 该维度值的总体三角形数据：从主 derived 取一维 GROUPING SET 行
    overall_sub = derived[
        (derived["dim_key"] == dim_key) & (derived["dim_value"] == dim_value)
    ].copy()
    if overall_sub.empty:
        return ""

    n_total = int(overall_sub["policy_count"].max() or 0)
    py_count = overall_sub["py"].nunique()

    # Section 1：总体三角形
    overall_triangle = render_dev_triangle(overall_sub, table_id="drill-overall")
    overall_card = render_card(
        title=f"{html.escape(display_label)} · 总体发展三角形",
        subtitle=(
            f"<strong>{html.escape(dim_card_label)} · {html.escape(display_label)}</strong>"
            " 在 5 个保单年度 × 6 个观察期 × 5 指标的整体表现。"
            "趋势列按满 1 年（365 天）亮灯色染。"
        ),
        body=overall_triangle,
        card_id="drill-overall-card",
    )

    # Section 2：11 副维度 Card（沿其他维度的内部分布；数据由 cli.py 通过 batch SQL 预查）
    sub_cards_html: list[str] = []
    nav_items: list[tuple[str, str]] = [
        ("drill-overall-card", f"{display_label} · 总体")
    ]
    for child_cfg in dim_cards:
        child_key = child_cfg["key"]
        if child_key == dim_key:
            continue
        pair_sub = sub_data.get(child_key)
        if pair_sub is None or pair_sub.empty:
            continue
        sub_card_id = f"drill-sub-{child_key}"
        card_html = render_dim_card(
            pair_sub,
            dim_cfg=child_cfg,
            current_py=current_py,
            overall_df=overall_sub,  # 父维度值在 5 PY × 6 DW 的整体行作基准
            py_options=py_options,
            enable_drill_link=False,  # v2.1 不做多级下钻
            table_id_override=sub_card_id,
        )
        if card_html:
            sub_cards_html.append(card_html)
            nav_items.append((sub_card_id, child_cfg["label"]))

    # 返回主页链接：从 drill/{key}/{slug}.html 回到主页 = ../../{main}
    back_link = (
        f'<a class="back-link" href="../../{main_page_filename}">← 返回主页</a>'
    )

    cards_html = (
        back_link + EXTRA_CSS
        + render_global_controls(py_options, current_py)
        + overall_card
        + "".join(sub_cards_html)
        + METRIC_SWITCHER_JS
    )

    return render_page(
        title=f"{display_label} · 多维度归因分析",
        cards_html=cards_html,
        meta_text=(
            f"{n_total / 10000:,.2f} 万单（PY 峰值）· "
            f"{py_count} 个保单年度 · {len(sub_cards_html)} 个副维度 · "
            f"截止 {cutoff.isoformat()}"
        ),
        footer_text=f"数据截止 {cutoff.isoformat()} · 由 skill diagnose-loss-development 生成",
        nav_items=nav_items,
    )


# ---------- 关键发现自动生成 ----------

def auto_insight_card1(overall_df: pd.DataFrame) -> str:
    """Card 1 自动洞察：找出最近完整 PY 365d 与上年同期的差异，给出方向判断。"""
    df = overall_df.copy()
    # 只看完整观察（completeness ≥ 0.95）的格子
    df_complete = df[df["completeness_ratio"] >= COMPLETE_TH]
    if df_complete.empty:
        return ""

    # 找最近的"PY × 365d 完整"
    df_365 = df_complete[df_complete["dw_days"] == 365].sort_values("py", ascending=False)
    if len(df_365) < 2:
        return ""

    cur = df_365.iloc[0]
    prev = df_365.iloc[1]
    cur_py = int(cur["py"])
    prev_py = int(prev["py"])
    delta = float(cur["mature_loss_ratio"]) - float(prev["mature_loss_ratio"])
    direction = "改善" if delta < 0 else "恶化"
    level = "info" if delta < 0 else ("warn" if delta < 3 else "danger")
    arrow = "↘" if delta < 0 else "↗"

    # 人伤金额占比对比
    bi_cur = float(cur["bi_amount_ratio_pct"])
    bi_prev = float(prev["bi_amount_ratio_pct"])
    bi_delta = bi_cur - bi_prev

    text = (
        f"<strong>{cur_py} 年满 1 年满期赔付率 {cur['mature_loss_ratio']:.1f}%</strong>，"
        f"较 {prev_py} 年同口径 {direction} {abs(delta):.1f}pp {arrow}。"
        f"人伤金额占比 {bi_cur:.1f}% "
        f"（较 {prev_py} 年 {'上升' if bi_delta > 0 else '下降'} {abs(bi_delta):.1f}pp）。"
    )
    cite = f"取自 {cur_py} 年 vs {prev_py} 年同满 1 年锚点（完整观察 ≥ 95%）"
    return render_callout(text, cite=cite, level=level)


# ---------- 全局控制栏（年度 + 指标，sticky，驱动所有表）----------

def render_global_controls(
    py_options: "list[int]",
    current_py: int,
    active_metric: str = "mature_loss_ratio",
) -> str:
    """页面级 sticky 控制栏：一组「保单年度 + 指标」按钮联动整体三角 + 全部维度卡。

    - 年度按钮：仅作用于"维度卡"（data-triangle-kind=dim）；整体三角按年成行，不受年度切换影响。
    - 指标按钮：作用于所有表（整体三角 + 维度卡）。
    数据已全量嵌入各 cell 的 data 属性，切换为纯前端联动、零取数。
    """
    py_btns = "".join(
        f'<button type="button" class="btn-py{" active" if py == current_py else ""}" '
        f'data-py="{py}">{py}</button>'
        for py in py_options
    )
    metric_btns = "".join(
        f'<button type="button" class="btn-metric{" active" if mid == active_metric else ""}" '
        f'data-metric="{mid}">{html.escape(name)}</button>'
        for mid, name, _kind, _th in METRIC_DEFS
    )
    return (
        '<div class="global-controls" id="dev-global-controls">'
        f'<div class="gc-group gc-py"><span class="gc-label">保单年度</span>{py_btns}</div>'
        f'<div class="gc-group gc-metric"><span class="gc-label">指标</span>{metric_btns}</div>'
        '</div>'
    )


# ---------- 全局联动 JS（驱动整体三角 + 全部维度卡）+ 配套 CSS ----------

METRIC_SWITCHER_JS = """
<script>
(function() {
  var SPARK_W = 96, SPARK_H = 28, SPARK_M = 3;

  // 与 Python _sparkline_svg 同规格的 JS 端重绘
  function drawSparkline(values, sparkClass, minRange) {
    minRange = minRange || 0;
    var cleaned = [];
    values.forEach(function(v, i) { if (v !== null && !isNaN(v)) cleaned.push([i, v]); });
    if (cleaned.length < 2) return '<span class="spark-empty">—</span>';
    var ys = cleaned.map(function(p){return p[1];});
    var yMin = Math.min.apply(null, ys), yMax = Math.max.apply(null, ys);
    if (minRange > 0 && (yMax - yMin) < minRange) {
      var mid = (yMax + yMin) / 2;
      yMin = mid - minRange / 2; yMax = mid + minRange / 2;
    }
    var yRng = yMax > yMin ? (yMax - yMin) : 1.0;
    var nSteps = Math.max(1, values.length - 1);
    function coord(i, v) {
      var x = SPARK_M + (i / nSteps) * (SPARK_W - 2 * SPARK_M);
      var y = SPARK_H - SPARK_M - ((v - yMin) / yRng) * (SPARK_H - 2 * SPARK_M);
      return [x, y];
    }
    var points = cleaned.map(function(p){
      var c = coord(p[0], p[1]); return c[0].toFixed(1) + ',' + c[1].toFixed(1);
    }).join(' ');
    var lastIdx = cleaned[cleaned.length - 1][0];
    var circles = cleaned.map(function(p){
      var c = coord(p[0], p[1]);
      var r = p[0] === lastIdx ? 2.4 : 1.4;
      return '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + r + '"/>';
    }).join('');
    return '<svg class="sparkline" viewBox="0 0 ' + SPARK_W + ' ' + SPARK_H +
           '" width="' + SPARK_W + '" height="' + SPARK_H + '" preserveAspectRatio="none">' +
           '<g class="spark-group ' + sparkClass + '">' +
           '<polyline points="' + points + '" fill="none"/>' + circles + '</g></svg>';
  }

  // 刷新单张表到 (py, mid)：
  //   整体三角(kind=overall，年度成行) 用 data-{mid}-*；维度卡(kind=dim) 用 data-py{py}-{mid}-*
  function refreshTable(table, py, mid) {
    var isDim = table.getAttribute('data-triangle-kind') === 'dim';
    var prefix = isDim ? ('data-py' + py + '-' + mid) : ('data-' + mid);
    table.querySelectorAll('td.dev-cell').forEach(function(td) {
      var text = td.getAttribute(prefix + '-text');
      var cls  = td.getAttribute(prefix + '-cls');
      if (text == null) { text = '—'; cls = 'cell-missing'; }
      td.innerHTML = text;
      td.className = 'dev-cell ' + (cls || '');
    });
    table.querySelectorAll('td.trend-cell').forEach(function(td) {
      var raw = td.getAttribute(prefix + '-trend') || '';
      var values = raw.split('/').map(function(s){ return s === '' ? NaN : parseFloat(s); });
      var alertCls = td.getAttribute(prefix + '-light') || 'alert-gray';
      var sparkCls = alertCls.replace('alert-', 'spark-');
      var mrAttr = td.getAttribute(prefix + '-minrange');
      var minRange = mrAttr ? parseFloat(mrAttr) : 0;
      td.innerHTML = drawSparkline(values, sparkCls, minRange);
    });
    if (isDim) table.setAttribute('data-active-py', py);
  }

  // 全局联动：一次刷新页面上所有发展三角表
  function applyAll(py, mid) {
    document.querySelectorAll('table.dev-triangle').forEach(function(t) {
      refreshTable(t, py, mid);
    });
  }

  var controls = document.getElementById('dev-global-controls');
  if (!controls) return;
  function activeVal(sel, attr) {
    var b = controls.querySelector(sel + '.active');
    return b ? b.getAttribute(attr) : null;
  }
  var gPy = activeVal('.btn-py', 'data-py');
  var gMetric = activeVal('.btn-metric', 'data-metric') || 'mature_loss_ratio';

  function setActive(groupSel, btn) {
    controls.querySelectorAll(groupSel).forEach(function(b){ b.classList.remove('active'); });
    btn.classList.add('active');
  }

  controls.addEventListener('click', function(e) {
    var pyBtn = e.target.closest('.btn-py');
    var mBtn = e.target.closest('.btn-metric');
    if (pyBtn) {
      gPy = pyBtn.getAttribute('data-py'); setActive('.btn-py', pyBtn);
      applyAll(gPy, gMetric);
    } else if (mBtn) {
      gMetric = mBtn.getAttribute('data-metric'); setActive('.btn-metric', mBtn);
      applyAll(gPy, gMetric);
    }
  });

  // 初始对齐：把所有表同步到全局默认（年度 = current_py，指标 = 满期赔付率）
  if (gPy) applyAll(gPy, gMetric);
})();
</script>
"""

EXTRA_CSS = """
<style>
/* 发展三角形单元格 */
.data-table.dev-triangle td.dev-cell { text-align: right; font-variant-numeric: tabular-nums; }
.data-table.dev-triangle td.dim-cell { text-align: left; font-weight: 500; }
.data-table.dev-triangle .cell-marker {
  display: inline-block; margin-left: 4px; opacity: 0.55;
  font-size: 11px; font-weight: 600;
}
/* △ 部分完成：灰底斜纹 */
.data-table.dev-triangle td.cell-partial {
  background: repeating-linear-gradient(
    45deg,
    rgba(var(--ink-rgb), 0.04),
    rgba(var(--ink-rgb), 0.04) 4px,
    rgba(var(--ink-rgb), 0.10) 4px,
    rgba(var(--ink-rgb), 0.10) 8px
  );
  color: var(--muted-strong);
}
/* — 未到：浅灰文字 */
.data-table.dev-triangle td.cell-missing {
  color: var(--muted);
  text-align: right;
}
.dev-triangle-wrap { display: flex; flex-direction: column; gap: 12px; }

/* 趋势列：96×28 mini sparkline，借鉴 diagnose-period-trend 表 1 精髓 */
.data-table.dev-triangle th.trend-th {
  text-align: center; width: 100px;
  font-weight: 500; color: var(--muted);
}
.data-table.dev-triangle td.trend-cell {
  text-align: center; padding: 4px 6px;
  vertical-align: middle; line-height: 0;
}
.data-table.dev-triangle td.trend-cell .sparkline { display: inline-block; vertical-align: middle; }
.spark-group polyline { stroke-width: 1.5; fill: none; }
.spark-group circle { stroke: var(--paper, #fff); stroke-width: 0.5; }
.spark-group.spark-green  polyline { stroke: var(--alert-green-color,  #10b981); }
.spark-group.spark-blue   polyline { stroke: var(--alert-blue-color,   #3b82f6); }
.spark-group.spark-yellow polyline { stroke: var(--alert-yellow-color, #d97706); }
.spark-group.spark-red    polyline { stroke: var(--alert-red-color,    #dc2626); }
.spark-group.spark-gray   polyline { stroke: var(--alert-gray-color,   #9ca3af); }
.spark-group.spark-green  circle { fill: var(--alert-green-color,  #10b981); }
.spark-group.spark-blue   circle { fill: var(--alert-blue-color,   #3b82f6); }
.spark-group.spark-yellow circle { fill: var(--alert-yellow-color, #d97706); }
.spark-group.spark-red    circle { fill: var(--alert-red-color,    #dc2626); }
.spark-group.spark-gray   circle { fill: var(--alert-gray-color,   #9ca3af); }
.spark-empty { color: var(--muted, #999); font-size: 12px; }

/* 下钻链接：dim_cell 内的可点击维度值，hover 提示可深入 */
.drill-link {
  color: inherit; text-decoration: none;
  border-bottom: 1px dashed transparent;
  transition: color 120ms ease, border-color 120ms ease;
  cursor: pointer;
}
.drill-link:hover {
  color: var(--alert-blue-color, #3b82f6);
  border-bottom-color: var(--alert-blue-color, #3b82f6);
}
.back-link {
  display: inline-block;
  color: var(--muted, #999); text-decoration: none;
  font-size: 13px; margin-bottom: 12px;
  padding: 4px 10px; border-radius: 6px;
  transition: background 120ms ease, color 120ms ease;
}
.back-link:hover {
  color: var(--ink, #111);
  background: rgba(var(--ink-rgb, 17,17,17), 0.04);
}

/* 全局控制栏：sticky 常驻，年度 + 指标，一次驱动整体三角 + 全部维度卡。
   贴在 shell 的 .page-toolbar（sticky top:0, z-index:50, 高≈44px）正下方，
   形成两级粘性堆叠——滚到任何位置都可切换年度/指标（不再被标题栏遮住）。 */
.global-controls {
  position: sticky; top: 44px; z-index: 49;
  display: flex; gap: 24px; flex-wrap: wrap; align-items: center;
  padding: 12px 14px; margin: 0 0 18px 0;
  background: var(--paper);
  border: 1px solid rgba(var(--ink-rgb), 0.10);
  border-radius: 10px;
  box-shadow: 0 4px 14px -8px rgba(0, 0, 0, 0.22);
}
.gc-group {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px; border-radius: 8px;
  background: rgba(var(--ink-rgb), 0.03);
}
.gc-label {
  font-size: 12px; color: var(--muted);
  margin: 0 6px 0 8px; font-weight: 600; user-select: none;
}
@media (max-width: 768px) {
  .global-controls { gap: 10px; padding: 10px; }  /* top 继承 44px，仍贴标题栏下方 */
  .gc-group { flex-wrap: wrap; }
}

/* 按钮样式（全局控制栏 btn-py / btn-metric 复用）*/
.btn-metric, .btn-py {
  padding: 4px 10px; border: 1px solid transparent; border-radius: 6px;
  background: transparent; color: var(--muted);
  font-size: 13px; font-weight: 400; font-family: inherit;
  cursor: pointer; user-select: none;
  transition: background 120ms ease, color 120ms ease, box-shadow 120ms ease;
}
.btn-metric:hover, .btn-py:hover {
  color: var(--ink);
  background: rgba(var(--ink-rgb), 0.04);
}
.btn-metric.active, .btn-py.active {
  background: var(--paper);
  color: var(--ink);
  font-weight: 600;
  box-shadow: 0 0 0 1px rgba(var(--ink-rgb), 0.18),
              0 1px 2px rgba(0, 0, 0, 0.05);
}
</style>
"""
