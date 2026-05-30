import math
from html import escape
from typing import Literal

from ..alerts import light
from ..format import fmt_num

def _sparkline_svg(values: list, width: int = 110, height: int = 28,
                   margin: int = 3, alert_class: str = "") -> str:
    """生成内嵌 SVG sparkline。

    Args:
      values: 5 个数（按时序从早到晚），None 表示缺失
      width/height/margin: SVG 视口
      alert_class: 当周亮灯 class（"alert-green/blue/yellow/red/gray"），
                   用于决定线条与圆点颜色；空字符串走默认色（蓝）
    """
    valid = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(valid) < 2:
        return '<span class="spark-empty">—</span>'
    xs = [p[0] for p in valid]
    ys = [float(p[1]) for p in valid]
    n = len(values)
    y_min, y_max = min(ys), max(ys)
    rng = y_max - y_min if y_max > y_min else 1.0
    inner_w = width - 2 * margin
    inner_h = height - 2 * margin

    def px(i): return margin + (i / (n - 1)) * inner_w if n > 1 else margin + inner_w / 2
    def py(v): return margin + inner_h - ((v - y_min) / rng) * inner_h

    points = [(px(i), py(v)) for i, v in zip(xs, ys)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = (f"M {points[0][0]:.1f},{points[0][1]:.1f} "
            + " ".join(f"L {x:.1f},{y:.1f}" for x, y in points[1:])
            + f" L {points[-1][0]:.1f},{height - margin:.1f}"
            + f" L {points[0][0]:.1f},{height - margin:.1f} Z")

    # 颜色变体：把 alert-* 转成 spark-* 后缀
    color_suffix = alert_class.replace("alert-", "") if alert_class else ""
    line_cls  = f"spark-line spark-{color_suffix}"  if color_suffix else "spark-line"
    area_cls  = f"spark-area spark-area-{color_suffix}" if color_suffix else "spark-area"
    dot_color = f"spark-dot-{color_suffix}" if color_suffix else ""

    dots = []
    for idx, (x, y) in enumerate(points):
        last = "last" if idx == len(points) - 1 else ""
        cls = f"spark-dot {dot_color} {last}".strip()
        dots.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="1.8"/>')

    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<path class="{area_cls}" d="{area}"/>'
            f'<polyline class="{line_cls}" points="{poly}"/>'
            f'{"".join(dots)}'
            f'</svg>')


def sparkline(values: list,
              color_mode: Literal["alert", "trend"] = "alert",
              alert_class: str = "",
              width: int = 160,
              height: int = 40,
              area: bool = True,
              show_dots: bool = True) -> str:
    """增强版 sparkline（综合壳库与 DPT 能力）。

    Args:
        values: 数值列表，None 表示缺失（跳过）
        color_mode: "alert" 按亮灯等级着色（壳库原有语义）；"trend" 按终点涨跌着色（DPT 语义）
        alert_class: 当 color_mode="alert" 时，亮灯 class（如 "alert-red"）
        width/height: SVG 尺寸
        area: 是否填充线下区域
        show_dots: 是否显示数据点（圆点）

    Returns:
        SVG HTML 字符串；有效点 < 2 时返回占位符
    """
    # 清洗缺失值
    cleaned: list[tuple[int, float]] = []
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        cleaned.append((i, float(v)))

    if len(cleaned) < 2:
        return '<span style="color:var(--ink-light);font-size:11px;">趋势数据不足</span>'

    ys = [v for _, v in cleaned]
    y_min, y_max = min(ys), max(ys)
    y_range = (y_max - y_min) if y_max > y_min else 1.0
    n_steps = max(1, len(values) - 1)
    pad = 6

    # 计算点位
    pts = []
    for i, v in cleaned:
        x = pad + (i / n_steps) * (width - 2 * pad)
        y = (height - pad) - ((v - y_min) / y_range) * (height - 2 * pad)
        pts.append((x, y))

    # 决定颜色
    if color_mode == "trend":
        # 按终点涨跌着色
        stroke = "var(--red)" if cleaned[-1][1] >= cleaned[0][1] else "var(--green)"
    else:
        # 按亮灯等级着色
        color_suffix = alert_class.replace("alert-", "") if alert_class else ""
        stroke = (
            f"var(--alert-{color_suffix})" if color_suffix else "var(--ink-soft)"
        )

    # 生成 SVG
    line_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts: list[str] = []

    if area and len(pts) >= 2:
        area_pts = (f"{pts[0][0]:.1f},{height-pad} {line_pts} "
                    f"{pts[-1][0]:.1f},{height-pad}")
        parts.append(
            f'<polygon points="{area_pts}" fill="{stroke}" fill-opacity="0.07"/>'
        )

    parts.append(
        f'<polyline points="{line_pts}" stroke="{stroke}" stroke-width="1.6" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    if show_dots:
        for i, (x, y) in enumerate(pts):
            r = 2.6 if i == len(pts) - 1 else 1.6
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{stroke}"/>')

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:block" aria-hidden="true">'
        f'{"".join(parts)}</svg>'
    )


def render_weekly_table(metrics: list, time_labels: list) -> str:
    """渲染"经营指标概况"周报横向时序表。

    通用规则（v1.7）：
      - 列头一律居中（除指标名列保持左对齐外）
      - 趋势线颜色与「当周」（values[0]）的亮灯状态一致
      - 占位行（placeholder=True）显示"待接入"灰色徽章

    Args:
      metrics: 每项是 dict，键：
        name           指标中文名
        unit           单位（仅供 tooltip）
        values         按 time_labels 顺序排列（当周, 上周, 上上周, 上月, 上季度）
        trend_values   sparkline 用，按时序从早到晚排列；缺省用 reversed(values)
        metric_key     对应 alerts.TH 字典的键名（用于亮灯）；缺则不打灯
        kind           fmt_num kind（pct/wan/int/money0/raw），默认 pct
        sample_n       整体样本量（用于亮灯小样本判定）
        placeholder    True 时整行显示"待接入"
      time_labels: 列标题列表
    """
    if not metrics:
        return '<p class="empty-data">无指标</p>'

    th_cells = [f'<th class="th-name">指标</th>',
                f'<th class="th-spark">趋势</th>']
    for lbl in time_labels:
        th_cells.append(f'<th class="th-num">{escape(lbl)}</th>')

    rows_html = []
    for m in metrics:
        name = m["name"]
        kind = m.get("kind", "pct")
        values = m.get("values") or []
        metric_key = m.get("metric_key")
        sample_n = m.get("sample_n", 999)
        placeholder = m.get("placeholder", False)

        # v1.8：列已按时序从早到晚排序，"当周/最新"在最后一列（values[-1]）
        current_val = values[-1] if values else None
        current_cls = ""
        if metric_key and current_val is not None and not placeholder:
            current_cls, _ = light(metric_key, current_val, sample_n)

        # 趋势：默认直接用 values（已是时序从早到晚），不再 reversed
        trend_vals = m.get("trend_values") or values
        spark_html = _sparkline_svg(trend_vals, alert_class=current_cls)

        cells = [f'<td class="td-name">{escape(name)}</td>',
                 f'<td class="spark">{spark_html}</td>']
        for v in values:
            if placeholder:
                cells.append('<td class="placeholder">待接入</td>')
                continue
            if v is None:
                cells.append('<td class="placeholder">—</td>')
                continue
            cls, _ = light(metric_key, v, sample_n) if metric_key else ("", "")
            dot = (f'<span class="dot {cls.replace("alert-", "dot-")}" aria-hidden="true"></span>'
                   if cls else '')
            cells.append(
                f'<td class="num {cls}">'
                f'<span class="num-val">{fmt_num(v, kind)}</span>'
                f'{dot}'
                f'</td>'
            )
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
<table class="weekly-table">
  <thead><tr>{''.join(th_cells)}</tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>"""
