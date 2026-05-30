"""V3 · 叙事周报（A4 打印视角）渲染器。

设计来源：/tmp/design_pkg/untitled/project/V3 叙事报告.html
本项目化要点：
  - A4 单页叙事风格，4 章节 + 附录表
  - Chapter 01: KPI Strip + 趋势 SVG（3 条折线：变率/赔付率/出险率）
  - Chapter 02: 响应卡（Top 异常 × 机构/类别下钻）
  - Chapter 03: 散点图（赔付率 × 出险率，气泡大小=保费占比）
  - Chapter 04: 重点关注清单（警戒机构/类别）
  - Appendix: 6 期 VCR 数据表
  - @page + @media print：A4 打印零碎片
"""
from __future__ import annotations

import html as _html
import json
import math
from datetime import date
from typing import Optional

import pandas as pd

try:
    from ._dhr_bootstrap import dhr as dhr_lib
except ImportError:
    from _dhr_bootstrap import dhr as dhr_lib  # type: ignore[no-redef]

light = dhr_lib.light
short_category_label = dhr_lib.short_category_label
fmt_num = dhr_lib.fmt_num

try:
    from .anomalies import (
        AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER,
        YTD_LABEL, YOY_LABEL, Anomaly,
    )
    from .themes_v2 import (
        FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
        THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn,
    )
    from .render_v4 import (
        _safe_f, _all_aux_mask, AUX_FIELDS,
        _slice_overall, _slice_by_cat, _slice_by_org,
        _pv, _get_th, METRIC_DEFS, PERIOD_HEADERS,
        YTD_IDX, YOY_IDX, M12_IDX,
    )
except ImportError:
    from anomalies import (  # type: ignore[no-redef]
        AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER,
        YTD_LABEL, YOY_LABEL, Anomaly,
    )
    from themes_v2 import (  # type: ignore[no-redef]
        FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
        THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn,
    )
    from render_v4 import (  # type: ignore[no-redef]
        _safe_f, _all_aux_mask, AUX_FIELDS,
        _slice_overall, _slice_by_cat, _slice_by_org,
        _pv, _get_th, METRIC_DEFS, PERIOD_HEADERS,
        YTD_IDX, YOY_IDX, M12_IDX,
    )

_TH = _get_th()

# ── 期标签简称 ────────────────────────────────────────────────────────────────
_P_SHORT = [h for _, h in PERIOD_HEADERS]          # ["36月","24月","上年","12月","6月","本年"]
_P_FULL  = [h for h, _ in PERIOD_HEADERS]          # ["滚动36个月",...]


# ===== SVG 工具 ================================================================

def _lin(v_min: float, v_max: float, px_lo: float, px_hi: float, v: float) -> float:
    """线性映射 v → px，v_min/v_max 对应 px_lo/px_hi（注意 SVG y 轴向下）。"""
    if v_max == v_min:
        return (px_lo + px_hi) / 2
    return px_lo + (v - v_min) / (v_max - v_min) * (px_hi - px_lo)


def _build_trend_svg(series: dict[str, list]) -> str:
    """生成趋势折线 SVG（变率蓝/赔付率红/出险率绿虚线），6 期 X 轴。
    series: {period_label: {vcr, lr, freq}} 按 PERIOD_ORDER 排序
    """
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 720, 220, 48, 20, 20, 36
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B

    # 按 PERIOD_ORDER 取有序数据
    ordered: list[dict] = []
    for p in _P_FULL:
        row = series.get(p, {})
        ordered.append({
            "label": _P_SHORT[_P_FULL.index(p)],
            "vcr":  row.get("vcr"),
            "lr":   row.get("lr"),
            "freq": row.get("freq"),
        })

    n = len(ordered)
    xs = [PAD_L + i * inner_w / (n - 1) for i in range(n)] if n > 1 else [PAD_L + inner_w / 2]

    # 收集非 None 值计算 Y 范围
    def _valid(key: str) -> list[float]:
        return [r[key] for r in ordered if r[key] is not None]

    all_vals = _valid("vcr") + _valid("lr")
    freq_vals = _valid("freq")
    # 两个 Y 轴：左轴 vcr/lr，右轴 freq（出险率量级差 10x）
    y1_min = min(all_vals) if all_vals else 50.0
    y1_max = max(all_vals) if all_vals else 100.0
    y1_pad = max((y1_max - y1_min) * 0.12, 2)
    y1_lo, y1_hi = y1_min - y1_pad, y1_max + y1_pad

    y2_min = min(freq_vals) if freq_vals else 0.0
    y2_max = max(freq_vals) if freq_vals else 20.0
    y2_pad = max((y2_max - y2_min) * 0.12, 1)
    y2_lo, y2_hi = y2_min - y2_pad, y2_max + y2_pad

    def pts1(key: str) -> list[tuple[float, float]]:
        return [
            (xs[i], PAD_T + _lin(y1_lo, y1_hi, inner_h, 0, r[key]))
            for i, r in enumerate(ordered) if r[key] is not None
        ]

    def pts2(key: str) -> list[tuple[float, float]]:
        return [
            (xs[i], PAD_T + _lin(y2_lo, y2_hi, inner_h, 0, r[key]))
            for i, r in enumerate(ordered) if r[key] is not None
        ]

    def polyline(pts: list[tuple[float, float]], stroke: str, dash: str = "") -> str:
        if not pts: return ""
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="2.5"'
                f' stroke-linejoin="round" stroke-linecap="round"{da}/>')

    def dots(pts: list[tuple[float, float]], fill: str) -> str:
        return "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{fill}" stroke="white" stroke-width="1.5"/>'
                       for x, y in pts)

    vcr_pts  = pts1("vcr")
    lr_pts   = pts1("lr")
    freq_pts = pts2("freq")

    lines = [
        polyline(vcr_pts,  "#1c4878"),
        polyline(lr_pts,   "#b8392b"),
        polyline(freq_pts, "#3a7a4b", dash="5,3"),
        dots(vcr_pts,  "#1c4878"),
        dots(lr_pts,   "#b8392b"),
        dots(freq_pts, "#3a7a4b"),
    ]

    # X 轴标签
    x_labels = "".join(
        f'<text x="{xs[i]:.1f}" y="{H - 6}" text-anchor="middle" font-size="11" fill="#8c8478">'
        f'{r["label"]}</text>'
        for i, r in enumerate(ordered)
    )
    # Y 轴左侧 3 刻度
    y_ticks = ""
    for frac in (0, 0.5, 1.0):
        yv = y1_lo + frac * (y1_hi - y1_lo)
        ypx = PAD_T + (1 - frac) * inner_h
        y_ticks += (f'<line x1="{PAD_L - 4}" y1="{ypx:.1f}" x2="{W - PAD_R}" y2="{ypx:.1f}"'
                    f' stroke="#e6dfcf" stroke-width="1"/>')
        y_ticks += (f'<text x="{PAD_L - 7}" y="{ypx + 4:.1f}" text-anchor="end" font-size="10"'
                    f' fill="#8c8478">{yv:.0f}</text>')

    legend_y = PAD_T - 8
    legend = (
        f'<circle cx="{PAD_L}" cy="{legend_y}" r="4" fill="#1c4878"/>'
        f'<text x="{PAD_L+8}" y="{legend_y+4}" font-size="11" fill="#1c4878">变率</text>'
        f'<circle cx="{PAD_L+52}" cy="{legend_y}" r="4" fill="#b8392b"/>'
        f'<text x="{PAD_L+60}" y="{legend_y+4}" font-size="11" fill="#b8392b">赔付率</text>'
        f'<circle cx="{PAD_L+120}" cy="{legend_y}" r="4" fill="#3a7a4b"/>'
        f'<text x="{PAD_L+128}" y="{legend_y+4}" font-size="11" fill="#3a7a4b">出险率（右轴）</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%;max-width:{W}px;height:auto;display:block;">'
        f'{y_ticks}{"".join(lines)}{x_labels}{legend}</svg>'
    )
    return svg


def _build_scatter_svg(points: list[dict]) -> str:
    """散点图：X=出险率, Y=赔付率, 气泡面积=保费占比。
    points: [{name, lr, freq, prem_share, sev}]
    """
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 720, 300, 55, 30, 30, 40

    freq_vals = [p["freq"] for p in points if p.get("freq") is not None]
    lr_vals   = [p["lr"]   for p in points if p.get("lr")   is not None]
    if not freq_vals or not lr_vals:
        return "<p style='color:#8c8478;font-size:12px'>数据不足，无法绘制散点图</p>"

    x_min, x_max = min(freq_vals), max(freq_vals)
    y_min, y_max = min(lr_vals),   max(lr_vals)
    x_pad = max((x_max - x_min) * 0.15, 1)
    y_pad = max((y_max - y_min) * 0.15, 2)
    x_lo, x_hi = x_min - x_pad, x_max + x_pad
    y_lo, y_hi = y_min - y_pad, y_max + y_pad

    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B

    def to_px(freq: float, lr: float) -> tuple[float, float]:
        px = PAD_L + (freq - x_lo) / (x_hi - x_lo) * inner_w
        py = PAD_T + (1 - (lr - y_lo) / (y_hi - y_lo)) * inner_h
        return px, py

    sev_color = {
        "red":    "#b8392b",
        "yellow": "#c97826",
        "blue":   "#1c4878",
        "green":  "#3a7a4b",
        "gray":   "#8c8478",
    }

    # 警戒线：出险率阈值（中档）
    th_freq = _TH.get("earned_loss_freq_pct", (0, 10, 12))[1]
    th_lr   = _TH.get("earned_loss_ratio_pct", (0, 70, 75))[1]
    warn_x  = PAD_L + (th_freq - x_lo) / (x_hi - x_lo) * inner_w
    warn_y  = PAD_T + (1 - (th_lr - y_lo) / (y_hi - y_lo)) * inner_h

    # 网格
    grid = ""
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        ypx = PAD_T + frac * inner_h
        xpx = PAD_L + frac * inner_w
        grid += (f'<line x1="{PAD_L}" y1="{ypx:.1f}" x2="{W-PAD_R}" y2="{ypx:.1f}"'
                 f' stroke="#e6dfcf" stroke-width="1"/>')
        grid += (f'<line x1="{xpx:.1f}" y1="{PAD_T}" x2="{xpx:.1f}" y2="{H-PAD_B}"'
                 f' stroke="#e6dfcf" stroke-width="1"/>')

    # 警戒象限阴影（右上 = 高出险率 + 高赔付率）
    quad_rect = (
        f'<rect x="{warn_x:.1f}" y="{PAD_T}" width="{W-PAD_R-warn_x:.1f}" height="{warn_y-PAD_T:.1f}"'
        f' fill="rgba(184,57,43,0.05)"/>'
    )
    warn_lines = (
        f'<line x1="{warn_x:.1f}" y1="{PAD_T}" x2="{warn_x:.1f}" y2="{H-PAD_B}"'
        f' stroke="#b8392b" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<line x1="{PAD_L}" y1="{warn_y:.1f}" x2="{W-PAD_R}" y2="{warn_y:.1f}"'
        f' stroke="#b8392b" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    # 气泡 + 标签
    bubbles = ""
    labels  = ""
    max_prem = max((p.get("prem_share") or 1.0) for p in points) or 1.0
    for p in points:
        if p.get("freq") is None or p.get("lr") is None:
            continue
        cx, cy = to_px(p["freq"], p["lr"])
        prem = p.get("prem_share") or 0
        r = max(5.0, min(22.0, 5 + (prem / max_prem) ** 0.5 * 17))
        col = sev_color.get(p.get("sev", "gray"), "#8c8478")
        bubbles += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"'
            f' fill="{col}" fill-opacity="0.22" stroke="{col}" stroke-width="1.5"/>'
        )
        # 简短名称
        nm = p.get("name", "")[:6]
        labels += (
            f'<text x="{cx:.1f}" y="{cy - r - 3:.1f}" text-anchor="middle"'
            f' font-size="9.5" fill="{col}">{_html.escape(nm)}</text>'
        )

    # 轴标签
    x_labels = ""
    for frac in (0, 0.5, 1.0):
        v = x_lo + frac * (x_hi - x_lo)
        xpx = PAD_L + frac * inner_w
        x_labels += (f'<text x="{xpx:.1f}" y="{H - 6}" text-anchor="middle"'
                     f' font-size="10" fill="#8c8478">{v:.1f}%</text>')
    y_labels = ""
    for frac in (0, 0.5, 1.0):
        v = y_lo + frac * (y_hi - y_lo)
        ypx = PAD_T + (1 - frac) * inner_h
        y_labels += (f'<text x="{PAD_L - 7}" y="{ypx + 4:.1f}" text-anchor="end"'
                     f' font-size="10" fill="#8c8478">{v:.1f}%</text>')
    axis_title = (
        f'<text x="{PAD_L + inner_w/2}" y="{H - 1}" text-anchor="middle"'
        f' font-size="11" fill="#5a5048">出险率 →</text>'
        f'<text x="12" y="{PAD_T + inner_h/2}" text-anchor="middle"'
        f' font-size="11" fill="#5a5048" transform="rotate(-90,12,{PAD_T + inner_h/2})">赔付率 →</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%;max-width:{W}px;height:auto;display:block;">'
        f'{grid}{quad_rect}{warn_lines}{bubbles}{labels}{x_labels}{y_labels}{axis_title}</svg>'
    )
    return svg


# ===== 数据提取 ================================================================

def _extract_overall_series(df: pd.DataFrame) -> dict[str, dict]:
    """返回 {period_label: {vcr, lr, freq, avg, coef, prem}} 整体行各期数据。"""
    overall_df = _slice_overall(df)
    out: dict[str, dict] = {}
    for p in _P_FULL:
        row = {}
        for m_id, _, m_col, _, _, _ in METRIC_DEFS:
            row[m_id] = _pv(overall_df, p, m_col)
        row["prem"] = _pv(overall_df, p, "premium_sum")
        out[p] = row
    return out


def _extract_scatter_data(df: pd.DataFrame, overall_prem: float) -> list[dict]:
    """三级机构散点数据：{name, lr, freq, vcr, prem_share, sev}。"""
    org_df = _slice_by_org(df)
    points: list[dict] = []
    for org in sorted(org_df["org_level_3"].unique()):
        if org == "__ALL__": continue
        cohort = org_df[org_df["org_level_3"] == org]
        lr   = _pv(cohort, YTD_LABEL, "earned_claim_ratio")
        freq = _pv(cohort, YTD_LABEL, "earned_loss_frequency")
        vcr  = _pv(cohort, YTD_LABEL, "variable_cost_ratio")
        prem = _pv(cohort, YTD_LABEL, "premium_sum")
        prem_share = round(prem / overall_prem * 100, 1) if (prem and overall_prem > 0) else None
        n_pol = int(_pv(cohort, YTD_LABEL, "policy_count") or 0)
        sev_cls, _ = light("variable_cost_ratio_pct", vcr, n_pol) if vcr is not None else ("alert-gray", "")
        points.append({
            "name": org,
            "lr":   lr,
            "freq": freq,
            "vcr":  vcr,
            "prem_share": prem_share,
            "sev":  sev_cls.replace("alert-", ""),
        })
    return points


def _extract_watchlist(df: pd.DataFrame) -> list[dict]:
    """提取三级机构中变率超警戒的列表（YTD），按变率降序排列。"""
    th_warn = _TH.get("variable_cost_ratio_pct", (0, 89, 93))[1]
    org_df = _slice_by_org(df)
    items: list[dict] = []
    for org in sorted(org_df["org_level_3"].unique()):
        if org == "__ALL__": continue
        cohort = org_df[org_df["org_level_3"] == org]
        vcr  = _pv(cohort, YTD_LABEL, "variable_cost_ratio")
        lr   = _pv(cohort, YTD_LABEL, "earned_claim_ratio")
        freq = _pv(cohort, YTD_LABEL, "earned_loss_frequency")
        prem = _pv(cohort, YTD_LABEL, "premium_sum")
        n_pol = int(_pv(cohort, YTD_LABEL, "policy_count") or 0)
        if vcr is None: continue
        sev_cls, _ = light("variable_cost_ratio_pct", vcr, n_pol)
        if sev_cls in ("alert-red", "alert-yellow"):
            items.append({
                "name": org,
                "vcr":  vcr,
                "lr":   lr,
                "freq": freq,
                "prem": prem,
                "n_pol": n_pol,
                "sev":  sev_cls,
            })
    items.sort(key=lambda x: -(x["vcr"] or 0))
    return items


def _extract_apx_table(df: pd.DataFrame) -> list[dict]:
    """附录表：整体 + 三级机构 × 6 期 VCR。"""
    overall_df = _slice_overall(df)
    org_df     = _slice_by_org(df)

    rows: list[dict] = []

    # 整体行
    vcr_series = [_pv(overall_df, p, "variable_cost_ratio") for p in _P_FULL]
    prem_series = [_pv(overall_df, p, "premium_sum") for p in _P_FULL]
    rows.append({"name": "四川整体", "vcr": vcr_series, "prem": prem_series, "is_overall": True})

    for org in sorted(org_df["org_level_3"].unique()):
        if org == "__ALL__": continue
        cohort = org_df[org_df["org_level_3"] == org]
        vcr_series  = [_pv(cohort, p, "variable_cost_ratio") for p in _P_FULL]
        prem_series = [_pv(cohort, p, "premium_sum") for p in _P_FULL]
        rows.append({"name": org, "vcr": vcr_series, "prem": prem_series, "is_overall": False})

    return rows


# ===== 格式化工具 ==============================================================

def _fmt_pct(v: Optional[float], digits: int = 1) -> str:
    if v is None: return "—"
    return f"{v:.{digits}f}%"

def _fmt_money(v: Optional[float]) -> str:
    if v is None: return "—"
    return f"{v/10000:,.0f}万"

def _fmt_delta(v: Optional[float]) -> str:
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}pp"

def _sev_dot(sev: str) -> str:
    colors = {
        "alert-red":    "#b8392b",
        "alert-yellow": "#c97826",
        "alert-blue":   "#1c4878",
        "alert-green":  "#3a7a4b",
        "alert-gray":   "#8c8478",
    }
    c = colors.get(sev, "#8c8478")
    return f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{c};margin-right:5px;"></span>'


def _gen_tldr(series: dict[str, dict]) -> str:
    """基于 YTD vs 上年同期生成一句 TL;DR。"""
    ytd = series.get(YTD_LABEL, {})
    yoy = series.get("上年同期", {})
    vcr_ytd = ytd.get("vcr")
    vcr_yoy = yoy.get("vcr")
    lr_ytd  = ytd.get("lr")
    lr_yoy  = yoy.get("lr")

    if vcr_ytd is None:
        return "当年数据暂缺，待更新。"

    vcr_msg = f"变率 {vcr_ytd:.1f}%"
    delta_vcr = round(vcr_ytd - vcr_yoy, 1) if vcr_yoy is not None else None
    if delta_vcr is not None:
        direction = "上升" if delta_vcr > 0 else "下降"
        vcr_msg += f"，同比{direction} {abs(delta_vcr):.1f}pp"

    lr_msg = ""
    if lr_ytd is not None:
        lr_msg = f"赔付率 {lr_ytd:.1f}%"
        delta_lr = round(lr_ytd - lr_yoy, 1) if lr_yoy is not None else None
        if delta_lr is not None:
            direction = "上升" if delta_lr > 0 else "下降"
            lr_msg += f"，同比{direction} {abs(delta_lr):.1f}pp"

    # 综合判断
    th_warn = _TH.get("variable_cost_ratio_pct", (0, 89, 93))[1]
    if vcr_ytd >= th_warn:
        conclusion = "整体经营压力较大，需重点关注高变率机构。"
    elif delta_vcr is not None and delta_vcr < -1:
        conclusion = "整体改善明显，延续优化态势。"
    else:
        conclusion = "整体经营稳定，关注局部异常机构。"

    parts = [p for p in [vcr_msg, lr_msg] if p]
    return "；".join(parts) + "。" + conclusion


# ===== HTML 渲染区块 ===========================================================

def _render_kpi_strip(series: dict[str, dict]) -> str:
    """5 格 KPI Strip：YTD 核心指标 + 同比变化箭头。"""
    ytd = series.get(YTD_LABEL, {})
    yoy = series.get("上年同期", {})

    kpi_defs = [
        ("变率",    "vcr",  "pct"),
        ("赔付率",  "lr",   "pct"),
        ("出险率",  "freq", "pct"),
        ("案均赔款","avg",  "money"),
        ("自主系数","coef", "coef"),
    ]

    def _cell(label: str, key: str, kind: str) -> str:
        v    = ytd.get(key)
        yoy_v = yoy.get(key)
        if kind == "pct":
            val_s = _fmt_pct(v, 1)
        elif kind == "money":
            val_s = _fmt_money(v)
        else:
            val_s = f"{v:.3f}" if v is not None else "—"

        delta_s = ""
        if v is not None and yoy_v is not None:
            d = v - yoy_v
            if kind == "pct":
                sign  = "▲" if d > 0 else "▼"
                col   = "var(--red)" if d > 0 else "var(--green)"
                delta_s = f'<span style="font-size:11px;color:{col};margin-left:4px;">{sign}{abs(d):.1f}pp</span>'

        sev_cls, _ = light("variable_cost_ratio_pct", ytd.get("vcr"), 1) if key == "vcr" else ("", "")
        alert_cls = sev_cls if key == "vcr" else ""

        return (
            f'<div class="kpi-cell {alert_cls}" style="flex:1;padding:12px 14px;">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val_s}{delta_s}</div>'
            f'</div>'
        )

    cells = "".join(_cell(label, key, kind) for label, key, kind in kpi_defs)
    return f'<div class="kpi-strip">{cells}</div>'


def _render_resp_cards(anomalies: list) -> str:
    """Chapter 02: Top 异常响应卡。"""
    if not anomalies:
        return '<p style="color:var(--ink-mute);font-size:13px;">本期无显著异常。</p>'

    cards = []
    for a in anomalies:
        # Anomaly dataclass 字段：dim_label, value_label, period_label, metric_label, value, delta, sev_cls, rank
        sev_cls  = getattr(a, "sev_cls", "alert-gray")
        dim_l    = getattr(a, "dim_label", "")
        val_l    = getattr(a, "value_label", "")
        period_l = getattr(a, "period_label", "")
        metric_l = getattr(a, "metric_label", "")
        val      = getattr(a, "value", None)
        delta    = getattr(a, "delta", None)

        val_s    = _fmt_pct(val, 1) if val is not None else "—"
        delta_s  = _fmt_delta(delta) if delta is not None else ""
        dot      = _sev_dot(sev_cls)

        cards.append(
            f'<div class="resp-card {sev_cls}">'
            f'<div class="resp-card-head">{dot}<strong>{_html.escape(str(val_l))}</strong>'
            f'<span class="resp-card-dim">｜{_html.escape(str(dim_l))}</span></div>'
            f'<div class="resp-card-body">'
            f'<span class="resp-metric">{_html.escape(str(metric_l))}</span>'
            f' <span class="resp-period">{_html.escape(str(period_l))}</span>'
            f'</div>'
            f'<div class="resp-card-foot">'
            f'<span class="resp-val">{val_s}</span>'
            f'<span class="resp-delta">{delta_s}</span>'
            f'</div>'
            f'</div>'
        )
    return f'<div class="resp-cards">{"".join(cards)}</div>'


def _render_watchlist(items: list[dict]) -> str:
    """Chapter 04: 重点关注清单（机构警戒）。"""
    if not items:
        return '<p style="color:var(--ink-mute);font-size:13px;">当前无机构超过警戒线。</p>'

    rows_html = ""
    for it in items:
        sev = it.get("sev", "alert-gray")
        dot = _sev_dot(sev)
        vcr_s  = _fmt_pct(it.get("vcr"),  1)
        lr_s   = _fmt_pct(it.get("lr"),   1)
        freq_s = _fmt_pct(it.get("freq"), 1)
        prem_s = _fmt_money(it.get("prem"))
        rows_html += (
            f'<tr class="{sev}">'
            f'<td style="text-align:left;">{dot}{_html.escape(it["name"])}</td>'
            f'<td>{vcr_s}</td><td>{lr_s}</td><td>{freq_s}</td><td>{prem_s}</td>'
            f'</tr>'
        )

    return (
        '<table class="watch-table">'
        '<thead><tr>'
        '<th style="text-align:left;">机构</th>'
        '<th>变率</th><th>赔付率</th><th>出险率</th><th>保费(本年)</th>'
        '</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )


def _render_apx_table(rows: list[dict]) -> str:
    """附录：6 期 VCR 数据表。"""
    headers = "".join(f'<th>{h}</th>' for h in _P_SHORT)
    body = ""
    for r in rows:
        is_overall = r.get("is_overall", False)
        style = ' style="font-weight:600;background:var(--surface-soft);"' if is_overall else ""
        vcr_cells = "".join(
            f'<td>{_fmt_pct(v, 1)}</td>' for v in r.get("vcr", [])
        )
        body += f'<tr{style}><td style="text-align:left;">{_html.escape(r["name"])}</td>{vcr_cells}</tr>'

    return (
        '<table class="apx-table">'
        f'<thead><tr><th style="text-align:left;">对象</th>{headers}</tr></thead>'
        f'<tbody>{body}</tbody>'
        '</table>'
    )


# ===== CSS =====================================================================

V3_CSS = """
/* ── 打印 + A4 ─────────────────────────────────────────────────── */
@page { size: A4; margin: 14mm 14mm 18mm 14mm; }
@media print {
  .toolbar, .nav-tabs, .print-btn { display:none !important; }
  body { background:#fff; }
  .page { box-shadow:none; margin:0; border-radius:0; }
  .ch { page-break-inside: avoid; }
}

/* ── 布局 ───────────────────────────────────────────────────── */
body { background: var(--paper-soft); }
.toolbar {
  position:sticky; top:0; z-index:60;
  background:var(--paper); border-bottom:1px solid var(--line);
  padding:9px 24px; display:flex; align-items:center; gap:12px;
}
.brand { display:flex; align-items:center; gap:7px; }
.brand-mark {
  width:22px; height:22px; border-radius:4px;
  background:var(--navy); color:#fff;
  display:flex; align-items:center; justify-content:center;
  font-size:12px; font-weight:700;
}
.toolbar h1 { font-family:'Noto Serif SC',serif; font-size:15px; font-weight:500; margin:0; }
.date-pill {
  padding:4px 10px; border:1px solid var(--line);
  background:var(--surface); border-radius:6px;
  font-size:12px; color:var(--ink-soft);
}
.nav-tabs {
  display:flex; align-items:center; gap:2px; padding:2px;
  background:var(--surface); border:1px solid var(--line);
  border-radius:7px; margin-left:auto;
}
.nav-tabs a, .nav-tabs span {
  padding:4px 10px; font-size:12px; color:var(--ink-soft);
  text-decoration:none; border-radius:5px; white-space:nowrap;
}
.nav-tabs .active { background:var(--ink); color:var(--paper); font-weight:500; }
.print-btn {
  height:29px; padding:0 12px; border-radius:6px;
  border:1px solid var(--line); background:var(--surface);
  font-size:12px; cursor:pointer; color:var(--ink-soft); font-family:inherit;
}
.print-btn:hover { background:var(--surface-soft); color:var(--ink); }

.page-wrap { max-width:820px; margin:0 auto; padding:20px; }
.page {
  background:var(--surface); border-radius:8px;
  box-shadow:0 2px 12px rgba(29,24,19,0.08), 0 0 0 1px var(--line);
  padding:32px 40px; position:relative;
}

/* ── 封面带 + 标题 ───────────────────────────────────────────── */
.cover-band {
  height:5px; background:linear-gradient(90deg,var(--navy) 0%,var(--navy-deep) 100%);
  border-radius:4px 4px 0 0; margin:-32px -40px 28px; position:relative; top:0;
}
.cover-label {
  font-size:11px; font-weight:600; letter-spacing:.08em;
  color:var(--ink-mute); text-transform:uppercase; margin-bottom:8px;
}
.cover-h1 {
  font-family:'Noto Serif SC',serif; font-size:26px; font-weight:600;
  color:var(--ink); margin:0 0 6px; line-height:1.3;
}
.cover-sub { font-size:13px; color:var(--ink-soft); margin-bottom:20px; }

/* ── TL;DR ───────────────────────────────────────────────────── */
.tldr {
  padding:12px 16px; background:var(--navy-soft);
  border-left:3px solid var(--navy); border-radius:0 6px 6px 0;
  font-size:13px; color:var(--ink); margin-bottom:28px;
}
.tldr strong { color:var(--navy); }

/* ── KPI Strip ───────────────────────────────────────────────── */
.kpi-strip {
  display:flex; gap:0; border:1px solid var(--line);
  border-radius:8px; overflow:hidden; margin-bottom:24px;
}
.kpi-cell { border-right:1px solid var(--line-soft); flex:1; padding:12px 14px; }
.kpi-cell:last-child { border-right:none; }
.kpi-label { font-size:11px; color:var(--ink-mute); margin-bottom:4px; }
.kpi-value { font-family:'Noto Serif SC',serif; font-size:18px; font-weight:600; color:var(--ink); }
.kpi-cell.alert-red    { background:var(--red-soft); }
.kpi-cell.alert-yellow { background:var(--orange-soft); }
.kpi-cell.alert-blue   { background:var(--navy-soft); }
.kpi-cell.alert-green  { background:var(--green-soft); }

/* ── 章节 ──────────────────────────────────────────────────── */
.ch { margin-bottom:32px; }
.ch-head {
  display:flex; align-items:center; gap:10px;
  margin-bottom:14px; padding-bottom:8px;
  border-bottom:1px solid var(--line);
}
.ch-num {
  width:24px; height:24px; border-radius:50%;
  background:var(--navy); color:#fff;
  display:flex; align-items:center; justify-content:center;
  font-size:11px; font-weight:700; flex-shrink:0;
}
.ch-title { font-family:'Noto Serif SC',serif; font-size:15px; font-weight:600; color:var(--ink); }
.ch-sub   { font-size:12px; color:var(--ink-mute); margin-left:auto; }

/* ── 响应卡 ──────────────────────────────────────────────────── */
.resp-cards { display:flex; flex-wrap:wrap; gap:10px; }
.resp-card {
  flex:0 0 calc(25% - 8px); min-width:160px;
  border:1px solid var(--bg,var(--line)); border-radius:8px;
  padding:10px 12px; background:var(--bg,var(--surface-soft));
}
.resp-card-head { display:flex; align-items:center; font-size:12px; margin-bottom:6px; flex-wrap:wrap; gap:2px; }
.resp-card-dim  { color:var(--ink-mute); font-size:11px; }
.resp-card-body { font-size:11px; color:var(--ink-soft); margin-bottom:6px; }
.resp-metric    { font-weight:500; }
.resp-period    { color:var(--ink-mute); }
.resp-card-foot { display:flex; align-items:baseline; gap:6px; }
.resp-val       { font-family:'Noto Serif SC',serif; font-size:16px; font-weight:600; color:var(--fg,var(--ink)); }
.resp-delta     { font-size:11px; color:var(--fg,var(--ink-soft)); }

/* ── 关注清单 ────────────────────────────────────────────────── */
.watch-table { width:100%; border-collapse:collapse; font-size:12px; }
.watch-table th, .watch-table td {
  padding:6px 10px; border:1px solid var(--line-soft);
  text-align:right; white-space:nowrap;
}
.watch-table thead th { background:var(--surface-soft); color:var(--ink-mute); font-weight:500; }
.watch-table tr.alert-red td    { background:var(--red-soft); color:var(--red); }
.watch-table tr.alert-yellow td { background:var(--orange-soft); color:var(--orange); }

/* ── 附录表 ──────────────────────────────────────────────────── */
.apx-table { width:100%; border-collapse:collapse; font-size:11.5px; }
.apx-table th, .apx-table td {
  padding:5px 9px; border:1px solid var(--line-soft); text-align:right; white-space:nowrap;
}
.apx-table thead th { background:var(--surface-soft); color:var(--ink-mute); font-size:11px; font-weight:500; }

/* ── 签注 ──────────────────────────────────────────────────── */
.signoff {
  margin-top:36px; padding-top:14px;
  border-top:1px solid var(--line);
  font-size:11px; color:var(--ink-mute);
  display:flex; justify-content:space-between;
}
"""


# ===== 主入口辅助函数 ===========================================================

def _v3_toolbar(cutoff_s: str, dash_href: str, table_href: str) -> str:
    nav = (
        f'<nav class="nav-tabs">'
        f'<span class="active">叙事</span>'
        f'<a href="{dash_href}">驾驶舱</a>'
        f'<a href="{table_href}">超表</a>'
        f'</nav>'
    )
    return (
        f'<div class="toolbar">'
        f'<div class="brand"><div class="brand-mark">C</div><h1>周期趋势诊断</h1></div>'
        f'<span class="date-pill">{cutoff_s}</span>'
        f'{nav}'
        f'{theme_toggle_btn()}'
        f'<button class="print-btn" onclick="window.print()">打印 / PDF</button>'
        f'</div>'
    )


def _v3_cover(cutoff_s: str, week_s: str, tldr: str, kpi_strip: str) -> str:
    return (
        f'<div class="cover-band"></div>'
        f'<div class="cover-label">Vehicle Insurance · Period Trend Report</div>'
        f'<h1 class="cover-h1">四川分公司周期趋势诊断</h1>'
        f'<p class="cover-sub">截至 {cutoff_s}（{week_s}）· 变率 / 赔付率 / 出险率多周期走势</p>'
        f'<div class="tldr"><strong>摘要：</strong>{_html.escape(tldr)}</div>'
        f'{kpi_strip}'
    )


def _v3_chapter(num: str, title: str, sub: str, body: str, num_style: str = "") -> str:
    ns = f' style="{num_style}"' if num_style else ""
    return (
        f'<div class="ch">'
        f'<div class="ch-head">'
        f'<div class="ch-num"{ns}>{num}</div>'
        f'<div class="ch-title">{title}</div>'
        f'<div class="ch-sub">{sub}</div>'
        f'</div>{body}</div>'
    )


# ===== 主入口 ==================================================================

def render_v3_page(df: pd.DataFrame, cutoff: date, anomalies: Optional[list] = None) -> str:
    """渲染 V3 叙事周报 HTML。"""
    anomalies    = anomalies or []
    series       = _extract_overall_series(df)
    overall_prem = (series.get(YTD_LABEL) or {}).get("prem") or 0.0

    tldr        = _gen_tldr(series)
    kpi_strip   = _render_kpi_strip(series)
    trend_svg   = _build_trend_svg(series)
    resp_cards  = _render_resp_cards(anomalies)
    scatter_svg = _build_scatter_svg(_extract_scatter_data(df, overall_prem))
    watch_html  = _render_watchlist(_extract_watchlist(df))
    apx_html    = _render_apx_table(_extract_apx_table(df))

    cs       = cutoff.strftime("%Y-%m-%d")
    week_s   = cutoff.strftime("%Y年第%W周")
    dash_href  = f"{cutoff.isoformat()}-dashboard.html"
    table_href = f"{cutoff.isoformat()}-table.html"

    chapters = (
        _v3_chapter("01", "多周期趋势走势", "变率 · 赔付率 · 出险率 — 6 期对比", trend_svg)
        + _v3_chapter("02", "关键异常响应", f"Top {len(anomalies)} 异常信号", resp_cards)
        + _v3_chapter("03", "赔付率 × 出险率 散点图", "气泡大小 = 保费占比 · 红色虚线 = 警戒值", scatter_svg)
        + _v3_chapter("04", "重点关注机构", "变率超警戒 · 本年起保口径", watch_html)
        + _v3_chapter("附", "6 期变率数据明细", "三级机构 · 变率(%)", apx_html,
                      num_style="background:var(--ink-mute);")
    )
    signoff = (
        f'<div class="signoff">'
        f'<span>四川华安 · 车险数据分析平台</span>'
        f'<span>生成时间：{cs}</span>'
        f'</div>'
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>周期趋势叙事周报 · {cs}</title>
{FONT_LINKS}
<style>
{BASE_CSS}
{DARK_CSS}
{THEME_TOGGLE_CSS}
{V3_CSS}
</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{_v3_toolbar(cs, dash_href, table_href)}
<div class="page-wrap"><div class="page">
{_v3_cover(cs, week_s, tldr, kpi_strip)}
{chapters}
{signoff}
</div></div>
<script>{THEME_TOGGLE_JS}</script>
</body>
</html>"""

    return html
