"""V3 叙事周报布局组件（自 diagnose-period-trend/lib/render_v3.py 移植）。

提供：
  - trend_svg()：趋势折线 SVG（变率/赔付率/出险率三线）
  - scatter_svg()：散点图 SVG（赔付率 × 出险率，气泡=保费占比）
  - render_toolbar()：顶部导航栏
  - render_cover()：封面带
  - render_chapter()：章节包装器
  - render_kpi_strip()：5 格 KPI 横排
  - render_resp_cards()：Top 异常响应卡
  - render_watchlist()：重点关注清单（机构警戒）
  - render_apx_table()：附录数据表
  - DECK_CSS：A4 打印 CSS 样式

依赖：
  - 无 pandas（纯 SVG + HTML 生成）
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional


# ===== SVG 工具 =====

def _lin(v_min: float, v_max: float, px_lo: float, px_hi: float, v: float) -> float:
    """线性映射 v → px，v_min/v_max 对应 px_lo/px_hi（注意 SVG y 轴向下）。"""
    if v_max == v_min:
        return (px_lo + px_hi) / 2
    return px_lo + (v - v_min) / (v_max - v_min) * (px_hi - px_lo)


@dataclass
class TrendPoint:
    """趋势数据点（单期）。"""
    label: str      # 期标签简称
    vcr: Optional[float]   # 变率
    lr: Optional[float]    # 赔付率
    freq: Optional[float]  # 出险率


def trend_svg(
    points: list[TrendPoint],
    width: int = 720,
    height: int = 220,
    color_vcr: str = "#1c4878",
    color_lr: str = "#b8392b",
    color_freq: str = "#3a7a4b",
) -> str:
    """生成趋势折线 SVG（变率蓝/赔付率红/出险率绿虚线）。

    Args:
        points: 按 X 轴顺序排列的数据点列表
        width/height: SVG 尺寸
        color_vcr/lr/freq: 三条线颜色

    Returns:
        SVG HTML 字符串
    """
    PAD_L, PAD_R, PAD_T, PAD_B = 48, 20, 20, 36
    inner_w = width - PAD_L - PAD_R
    inner_h = height - PAD_T - PAD_B

    n = len(points)
    xs = [PAD_L + i * inner_w / (n - 1) for i in range(n)] if n > 1 else [PAD_L + inner_w / 2]

    # 收集非 None 值计算 Y 范围
    def _valid(key: str) -> list[float]:
        return [getattr(p, key) for p in points if getattr(p, key) is not None]

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
            (xs[i], PAD_T + _lin(y1_lo, y1_hi, inner_h, 0, getattr(p, key)))
            for i, p in enumerate(points) if getattr(p, key) is not None
        ]

    def pts2(key: str) -> list[tuple[float, float]]:
        return [
            (xs[i], PAD_T + _lin(y2_lo, y2_hi, inner_h, 0, getattr(p, key)))
            for i, p in enumerate(points) if getattr(p, key) is not None
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
        polyline(vcr_pts,  color_vcr),
        polyline(lr_pts,   color_lr),
        polyline(freq_pts, color_freq, dash="5,3"),
        dots(vcr_pts,  color_vcr),
        dots(lr_pts,   color_lr),
        dots(freq_pts, color_freq),
    ]

    # Y 轴标签（左轴）
    y_ticks = ""
    for frac in (0, 0.5, 1.0):
        v = y1_lo + frac * (y1_hi - y1_lo)
        ypx = PAD_T + (1 - frac) * inner_h
        y_ticks += f'<text x="{PAD_L - 7}" y="{ypx + 4:.1f}" text-anchor="end" font-size="10" fill="#8c8478">{v:.0f}%</text>'

    # X 轴标签
    x_labels = ""
    for i, p in enumerate(points):
        x_labels += (
            f'<text x="{xs[i]:.1f}" y="{height - 6}" text-anchor="middle"'
            f' font-size="10" fill="#8c8478">{html.escape(p.label)}</text>'
        )

    # 图例
    legend = (
        f'<g transform="translate({width - 180}, {PAD_T + 6})">'
        f'<line x1="0" y1="0" x2="20" y2="0" stroke="{color_vcr}" stroke-width="2.5"/>'
        f'<circle cx="10" cy="0" r="3" fill="{color_vcr}" stroke="white" stroke-width="1.5"/>'
        f'<text x="26" y="4" font-size="10" fill="#8c8478">变动成本率</text>'

        f'<line x1="0" y1="16" x2="20" y2="16" stroke="{color_lr}" stroke-width="2.5"/>'
        f'<circle cx="10" cy="16" r="3" fill="{color_lr}" stroke="white" stroke-width="1.5"/>'
        f'<text x="26" y="20" font-size="10" fill="#8c8478">满期赔付率</text>'

        f'<line x1="0" y1="32" x2="20" y2="32" stroke="{color_freq}" stroke-width="2.5" stroke-dasharray="5,3"/>'
        f'<circle cx="10" cy="32" r="3" fill="{color_freq}" stroke="white" stroke-width="1.5"/>'
        f'<text x="26" y="36" font-size="10" fill="#8c8478">满期出险率</text>'
        f'</g>'
    )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%;max-width:{width}px;height:auto;display:block;">'
        f'{y_ticks}{"".join(lines)}{x_labels}{legend}</svg>'
    )
    return svg


@dataclass
class ScatterPoint:
    """散点数据点。"""
    name: str
    lr: Optional[float]       # 赔付率
    freq: Optional[float]     # 出险率
    prem_share: Optional[float]  # 保费占比
    sev: Literal["red", "yellow", "blue", "green", "gray"] = "gray"


def scatter_svg(
    points: list[ScatterPoint],
    warn_threshold_freq: float = 10.0,
    warn_threshold_lr: float = 70.0,
    width: int = 720,
    height: int = 300,
    colors: Optional[dict[str, str]] = None,
) -> str:
    """散点图：X=出险率, Y=赔付率, 气泡面积=保费占比。

    Args:
        points: 散点列表
        warn_threshold_freq: 出险率警戒线（中档）
        warn_threshold_lr: 赔付率警戒线（中档）
        width/height: SVG 尺寸
        colors: 亮灯颜色映射，默认红/橙/蓝/绿/灰

    Returns:
        SVG HTML 字符串
    """
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 30, 30, 40

    freq_vals = [p.freq for p in points if p.freq is not None]
    lr_vals   = [p.lr for p in points if p.lr is not None]
    if not freq_vals or not lr_vals:
        return "<p style='color:#8c8478;font-size:12px'>数据不足，无法绘制散点图</p>"

    x_min, x_max = min(freq_vals), max(freq_vals)
    y_min, y_max = min(lr_vals),   max(lr_vals)
    x_pad = max((x_max - x_min) * 0.15, 1)
    y_pad = max((y_max - y_min) * 0.15, 2)
    x_lo, x_hi = x_min - x_pad, x_max + x_pad
    y_lo, y_hi = y_min - y_pad, y_max + y_pad

    inner_w = width - PAD_L - PAD_R
    inner_h = height - PAD_T - PAD_B

    def to_px(freq: float, lr: float) -> tuple[float, float]:
        px = PAD_L + (freq - x_lo) / (x_hi - x_lo) * inner_w
        py = PAD_T + (1 - (lr - y_lo) / (y_hi - y_lo)) * inner_h
        return px, py

    if colors is None:
        colors = {
            "red":    "#b8392b",
            "yellow": "#c97826",
            "blue":   "#1c4878",
            "green":  "#3a7a4b",
            "gray":   "#8c8478",
        }

    # 警戒线位置
    warn_x  = PAD_L + (warn_threshold_freq - x_lo) / (x_hi - x_lo) * inner_w
    warn_y  = PAD_T + (1 - (warn_threshold_lr - y_lo) / (y_hi - y_lo)) * inner_h

    # 网格
    grid = ""
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        ypx = PAD_T + frac * inner_h
        xpx = PAD_L + frac * inner_w
        grid += (f'<line x1="{PAD_L}" y1="{ypx:.1f}" x2="{width-PAD_R}" y2="{ypx:.1f}"'
                 f' stroke="#e6dfcf" stroke-width="1"/>')
        grid += (f'<line x1="{xpx:.1f}" y1="{PAD_T}" x2="{xpx:.1f}" y2="{height-PAD_B}"'
                 f' stroke="#e6dfcf" stroke-width="1"/>')

    # 警戒象限阴影（右上 = 高出险率 + 高赔付率）
    quad_rect = (
        f'<rect x="{warn_x:.1f}" y="{PAD_T}" width="{width-PAD_R-warn_x:.1f}" height="{warn_y-PAD_T:.1f}"'
        f' fill="rgba(184,57,43,0.05)"/>'
    )
    warn_lines = (
        f'<line x1="{warn_x:.1f}" y1="{PAD_T}" x2="{warn_x:.1f}" y2="{height-PAD_B}"'
        f' stroke="#b8392b" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<line x1="{PAD_L}" y1="{warn_y:.1f}" x2="{width-PAD_R}" y2="{warn_y:.1f}"'
        f' stroke="#b8392b" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    # 气泡 + 标签
    bubbles = ""
    labels  = ""
    max_prem = max((p.prem_share or 1.0) for p in points) or 1.0
    for p in points:
        if p.freq is None or p.lr is None:
            continue
        cx, cy = to_px(p.freq, p.lr)
        prem = p.prem_share or 0
        r = max(5.0, min(22.0, 5 + (prem / max_prem) ** 0.5 * 17))
        col = colors.get(p.sev, "#8c8478")
        bubbles += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"'
            f' fill="{col}" fill-opacity="0.22" stroke="{col}" stroke-width="1.5"/>'
        )
        nm = p.name[:6]
        labels += (
            f'<text x="{cx:.1f}" y="{cy - r - 3:.1f}" text-anchor="middle"'
            f' font-size="9.5" fill="{col}">{html.escape(nm)}</text>'
        )

    # 轴标签
    x_labels = ""
    for frac in (0, 0.5, 1.0):
        v = x_lo + frac * (x_hi - x_lo)
        xpx = PAD_L + frac * inner_w
        x_labels += (f'<text x="{xpx:.1f}" y="{height - 6}" text-anchor="middle"'
                     f' font-size="10" fill="#8c8478">{v:.1f}%</text>')
    y_labels = ""
    for frac in (0, 0.5, 1.0):
        v = y_lo + frac * (y_hi - y_lo)
        ypx = PAD_T + (1 - frac) * inner_h
        y_labels += (f'<text x="{PAD_L - 7}" y="{ypx + 4:.1f}" text-anchor="end"'
                     f' font-size="10" fill="#8c8478">{v:.1f}%</text>')
    axis_title = (
        f'<text x="{PAD_L + inner_w/2}" y="{height - 1}" text-anchor="middle"'
        f' font-size="11" fill="#5a5048">出险率 →</text>'
        f'<text x="12" y="{PAD_T + inner_h/2}" text-anchor="middle"'
        f' font-size="11" fill="#5a5048" transform="rotate(-90,12,{PAD_T + inner_h/2})">赔付率 →</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%;max-width:{width}px;height:auto;display:block;">'
        f'{grid}{quad_rect}{warn_lines}{bubbles}{labels}{x_labels}{y_labels}{axis_title}</svg>'
    )
    return svg


# ===== 工具函数 =====

def _fmt_pct(v: Optional[float], digits: int = 1) -> str:
    if v is None: return "—"
    return f"{v:.{digits}f}%"


def _fmt_money(v: Optional[float]) -> str:
    if v is None: return "—"
    return f"¥{v:,.0f}"


def _fmt_delta(v: Optional[float]) -> str:
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}pp"


def _sev_dot(sev: Literal["alert-red", "alert-yellow", "alert-blue", "alert-green", "alert-gray", ""]) -> str:
    """亮灯小圆点 HTML。"""
    colors = {
        "alert-red":    "#b8392b",
        "alert-yellow": "#c97826",
        "alert-blue":   "#1c4878",
        "alert-green":  "#3a7a4b",
        "alert-gray":   "#8c8478",
    }
    c = colors.get(sev, "#8c8478")
    return f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{c};margin-right:5px;"></span>'


# ===== HTML 渲染组件 =====

def render_toolbar(
    cutoff: date,
    view_links: Optional[list[tuple[str, str]]] = None,
    title: str = "周期趋势诊断",
    brand_mark: str = "C",
    theme_toggle_btn: Optional[str] = None,
    show_print: bool = True,
) -> str:
    """顶部导航栏。

    Args:
        cutoff: 数据截止日期
        view_links: 视图切换链接列表 [(href, label), ...]，默认驾驶舱/超表
        title: 主标题
        brand_mark: 品牌标记文字
        theme_toggle_btn: 主题切换按钮 HTML
        show_print: 是否显示打印按钮
    """
    if view_links is None:
        view_links = [
            (f"{cutoff.isoformat()}-cockpit.html", "驾驶舱"),
            (f"{cutoff.isoformat()}-table.html", "超表"),
        ]

    nav_items = f'<span class="active">叙事</span>'
    for href, label in view_links:
        nav_items += f'<a href="{href}">{label}</a>'

    toggle_html = theme_toggle_btn or ""
    print_btn = f'<button class="print-btn" onclick="window.print()">打印 / PDF</button>' if show_print else ""

    return (
        f'<div class="toolbar">'
        f'<div class="brand"><div class="brand-mark">{html.escape(brand_mark)}</div>'
        f'<h1>{html.escape(title)}</h1></div>'
        f'<span class="date-pill">{cutoff.isoformat()}</span>'
        f'<nav class="nav-tabs">{nav_items}</nav>'
        f'{toggle_html}'
        f'{print_btn}'
        f'</div>'
    )


def render_cover(
    tldr: str,
    kpi_strip: str,
    cutoff: date,
    title: str = "周期趋势诊断",
    subtitle: str = "",
    week_label: str = "",
    cover_label: str = "Vehicle Insurance · Period Trend Report",
) -> str:
    """封面带（标题 + 摘要 + KPI）。

    Args:
        tldr: 摘要文字
        kpi_strip: KPI 条 HTML（由 render_kpi_strip 生成）
        cutoff: 数据截止日期
        title: 主标题
        subtitle: 副标题
        week_label: 周期标签（如"第 21 周"）
        cover_label: 封面顶部英文标签
    """
    sub_text = subtitle or f"截至 {cutoff.isoformat()}"
    if week_label:
        sub_text += f"（{week_label}）"

    return (
        f'<div class="cover-band"></div>'
        f'<div class="cover-label">{html.escape(cover_label)}</div>'
        f'<h1 class="cover-h1">{html.escape(title)}</h1>'
        f'<p class="cover-sub">{html.escape(sub_text)}</p>'
        f'<div class="tldr"><strong>摘要：</strong>{html.escape(tldr)}</div>'
        f'{kpi_strip}'
    )


def render_chapter(
    num: str,
    title: str,
    body: str,
    sub: str = "",
    num_style: str = "",
) -> str:
    """章节包装器。

    Args:
        num: 章节编号（如 "01"）
        title: 章节标题
        body: 章节内容 HTML
        sub: 副标题
        num_style: 编号自定义样式
    """
    ns = f' style="{num_style}"' if num_style else ""
    return (
        f'<div class="ch">'
        f'<div class="ch-head">'
        f'<div class="ch-num"{ns}>{html.escape(num)}</div>'
        f'<div class="ch-title">{html.escape(title)}</div>'
        f'<div class="ch-sub">{html.escape(sub)}</div>'
        f'</div>{body}</div>'
    )


@dataclass
class KpiCell:
    """KPI 单元数据。"""
    label: str
    value: Optional[float]
    delta_yoy: Optional[float]  # 同比差值
    kind: Literal["pct", "money", "coef"]
    alert: Literal["alert-red", "alert-yellow", "alert-blue", "alert-green", ""] = ""


def render_kpi_strip(cells: list[KpiCell]) -> str:
    """5 格 KPI 横排。

    Args:
        cells: KPI 单元列表

    Returns:
        HTML 字符串
    """
    def _cell(c: KpiCell) -> str:
        if c.kind == "pct":
            val_s = _fmt_pct(c.value, 1)
        elif c.kind == "money":
            val_s = _fmt_money(c.value)
        else:
            val_s = f"{c.value:.3f}" if c.value is not None else "—"

        delta_s = ""
        if c.value is not None and c.delta_yoy is not None:
            d = c.delta_yoy
            if c.kind == "pct":
                sign  = "▲" if d > 0 else "▼"
                col   = "var(--red)" if d > 0 else "var(--green)"
                delta_s = f'<span style="font-size:11px;color:{col};margin-left:4px;">{sign}{abs(d):.1f}pp</span>'

        return (
            f'<div class="kpi-cell {c.alert}" style="flex:1;padding:12px 14px;">'
            f'<div class="kpi-label">{html.escape(c.label)}</div>'
            f'<div class="kpi-value">{val_s}{delta_s}</div>'
            f'</div>'
        )

    return f'<div class="kpi-strip">{"".join(_cell(c) for c in cells)}</div>'


@dataclass
class RespCard:
    """响应卡数据（Top 异常）。"""
    value_label: str
    dim_label: str
    metric_label: str
    period_label: str
    value: Optional[float]
    delta: Optional[float]
    sev: Literal["alert-red", "alert-yellow", "alert-blue", "alert-green", "alert-gray", ""] = "alert-gray"


def render_resp_cards(cards: list[RespCard]) -> str:
    """Top 异常响应卡网格。

    Args:
        cards: 响应卡列表
    """
    if not cards:
        return '<p style="color:var(--ink-mute);font-size:13px;">本期无显著异常。</p>'

    items = []
    for c in cards:
        val_s   = _fmt_pct(c.value, 1)
        delta_s = _fmt_delta(c.delta)
        dot     = _sev_dot(c.sev)

        items.append(
            f'<div class="resp-card {c.sev}">'
            f'<div class="resp-card-head">{dot}<strong>{html.escape(c.value_label)}</strong>'
            f'<span class="resp-card-dim">｜{html.escape(c.dim_label)}</span></div>'
            f'<div class="resp-card-body">'
            f'<span class="resp-metric">{html.escape(c.metric_label)}</span>'
            f' <span class="resp-period">{html.escape(c.period_label)}</span>'
            f'</div>'
            f'<div class="resp-card-foot">'
            f'<span class="resp-val">{val_s}</span>'
            f'<span class="resp-delta">{delta_s}</span>'
            f'</div>'
            f'</div>'
        )
    return f'<div class="resp-cards">{"".join(items)}</div>'


@dataclass
class WatchItem:
    """关注清单项。"""
    name: str
    vcr: Optional[float]
    lr: Optional[float]
    freq: Optional[float]
    prem: Optional[float]
    sev: Literal["alert-red", "alert-yellow", "alert-blue", "alert-green", "alert-gray", ""] = "alert-gray"


def render_watchlist(items: list[WatchItem], header_label: str = "机构") -> str:
    """重点关注清单（警戒）。

    Args:
        items: 关注清单列表
        header_label: 首列表头文字，默认"机构"。org-weekly 用于客户类别时传"客户类别"。
    """
    if not items:
        return (
            f'<p style="color:var(--ink-mute);font-size:13px;">'
            f'当前无{header_label}超过警戒线。</p>'
        )

    rows = []
    for it in items:
        dot = _sev_dot(it.sev)
        rows.append(
            f'<tr class="{it.sev}">'
            f'<td style="text-align:left;">{dot}{html.escape(it.name)}</td>'
            f'<td>{_fmt_pct(it.vcr, 1)}</td>'
            f'<td>{_fmt_pct(it.lr, 1)}</td>'
            f'<td>{_fmt_pct(it.freq, 1)}</td>'
            f'<td>{_fmt_money(it.prem)}</td>'
            f'</tr>'
        )

    return (
        '<table class="watch-table">'
        '<thead><tr>'
        f'<th style="text-align:left;">{html.escape(header_label)}</th>'
        '<th>变率</th><th>赔付率</th><th>出险率</th><th>保费(本年)</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
    )


@dataclass
class ApTableRow:
    """附录表行。"""
    name: str
    values: list[Optional[float]]  # 6 期值
    is_overall: bool = False


def render_apx_table(rows: list[ApTableRow], headers: list[str]) -> str:
    """附录数据表。

    Args:
        rows: 行数据列表
        headers: 期标签简称列表（如 ["36月","24月","上年","12月","6月","本年"]）
    """
    body = ""
    for r in rows:
        style = ' style="font-weight:600;background:var(--surface-soft);"' if r.is_overall else ""
        cells = "".join(f'<td>{_fmt_pct(v, 1)}</td>' for v in r.values)
        body += f'<tr{style}><td style="text-align:left;">{html.escape(r.name)}</td>{cells}</tr>'

    head_cells = "".join(f'<th>{html.escape(h)}</th>' for h in headers)

    return (
        '<table class="apx-table">'
        f'<thead><tr><th style="text-align:left;">对象</th>{head_cells}</tr></thead>'
        f'<tbody>{body}</tbody>'
        '</table>'
    )


# ===== CSS 样式 =====

DECK_CSS = """
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
