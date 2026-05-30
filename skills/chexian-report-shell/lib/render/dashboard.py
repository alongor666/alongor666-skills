"""V1 驾驶舱布局组件（自 diagnose-period-trend/lib/render_v1.py 移植）。

提供：
  - render_topbar()：顶部导航栏
  - render_rail()：左侧维度导航
  - render_kpi_strip()：5 KPI 卡横排
  - render_anomaly_grid()：Top 异常卡片网格
  - render_section_detail()：可展开分维度明细

依赖：
  - sparkline：壳库 render.weekly.sparkline()
  - fmt_value/fmt_delta：本模块工具函数
  - SECTION_DEFS/METRIC_TABS：本模块常量
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from ..format import fmt_num
from .weekly import sparkline


# ===== 常量定义 =====

# 时间窗顺序
PERIOD_ORDER = ["滚动36个月", "滚动24个月", "上年同期", "滚动12个月", "滚动6个月", "当年起保"]
YTD_LABEL = "当年起保"
YOY_LABEL = "上年同期"

# 10 段定义
SECTION_DEFS: list[dict] = [
    {"id": "overall",   "label": "整体品质", "kind": "overall"},
    {"id": "customer",  "label": "客户类别", "kind": "cat"},
    {"id": "branch",    "label": "三级机构", "kind": "org"},
    {"id": "insurance", "label": "险类",     "kind": "aux", "field": "insurance_type"},
    {"id": "combo",     "label": "险别组合", "kind": "aux", "field": "coverage_combination"},
    {"id": "energy",    "label": "能源类型", "kind": "aux", "field": "is_nev"},
    {"id": "newused",   "label": "新旧车",   "kind": "aux", "field": "is_new_car"},
    {"id": "transfer",  "label": "是否过户", "kind": "aux", "field": "is_transfer"},
    {"id": "renewal",   "label": "是否续保", "kind": "aux", "field": "is_renewal"},
    {"id": "telesales", "label": "是否电销", "kind": "aux", "field": "is_telemarketing"},
]

# 折叠明细中可切换的 6 个指标 tab
METRIC_TABS: list[tuple[str, str, str, Optional[str]]] = [
    ("variable_cost_ratio",     "变率",     "pct",    "variable_cost_ratio_pct"),
    ("earned_claim_ratio",      "赔付率",   "pct",    "earned_loss_ratio_pct"),
    ("earned_loss_frequency",   "出险率",   "pct",    "earned_loss_freq_pct"),
    ("avg_claim_amount",        "案均",     "money",  None),
    ("weighted_pricing_factor", "自主系数", "coef",   None),
    ("premium_sum",             "保费贡献", "wan",    None),
]

_SEV_COLOR = {
    "alert-red":    "var(--red)",
    "alert-yellow": "var(--orange)",
    "alert-blue":   "var(--navy)",
    "alert-green":  "var(--green)",
}

# 指标 kind 序列（供 JS data-kinds 属性）
_METRIC_KINDS = "/".join(kind for _, _, kind, _ in METRIC_TABS)


# ===== 工具函数 =====

def _safe_float(v) -> Optional[float]:
    if v is None: return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _e(s: str) -> str:
    """HTML 转义。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_value(v: Optional[float], kind: str) -> str:
    """格式化指标值。kind: pct/coef/money/wan/int"""
    f = _safe_float(v)
    if f is None: return "—"
    if kind == "pct":   return f"{f:.1f}%"
    if kind == "coef":  return f"{f:.3f}"
    if kind == "money": return f"¥{f:,.0f}"
    if kind == "wan":   return f"{f/10000:,.0f}"
    if kind == "int":   return f"{f:,.0f}"
    return f"{f:.2f}"


def fmt_delta(d: Optional[float], kind: str) -> str:
    f = _safe_float(d)
    if f is None: return "—"
    if kind == "pct":   return f"{f:+.1f} PP"
    if kind == "coef":  return f"{f:+.3f}"
    if kind == "money": return f"{f:+,.0f} 元"
    if kind == "wan":   return f"{f/10000:+,.0f}"
    return f"{f:+.2f}"


# ===== 组件渲染 =====

def render_topbar(
    cutoff: date,
    meta: dict,
    brand_mark: str = "川",
    brand_text: str = "四川分公司 · 业务诊断",
    title: str = "多期车险保单品质对比",
    view_links: Optional[list[tuple[str, str]]] = None,
    theme_toggle_btn: Optional[str] = None,
) -> str:
    """顶部导航栏。

    Args:
        cutoff: 数据截止日期
        meta: 元数据字典，含 keys: policies/premium/categories
        brand_mark: 品牌标记文字
        brand_text: 品牌副标题
        title: 主标题
        view_links: 视图切换链接列表 [(href, label), ...]，默认驾驶舱/周报/超表
        theme_toggle_btn: 主题切换按钮 HTML（从壳库主题模块获取）
    """
    if view_links is None:
        view_links = [
            (f"{cutoff.isoformat()}-weekly.html", "周报"),
            (f"{cutoff.isoformat()}-table.html", "超表"),
        ]

    view_tabs = (
        f'<span style="padding:4px 10px; font-size:12px; background:var(--ink); color:var(--paper); border-radius:5px; font-weight:500;">驾驶舱</span>'
    )
    for href, label in view_links:
        view_tabs += (
            f'<a href="{href}" style="padding:4px 10px; font-size:12px; color:var(--ink-soft); text-decoration:none; border-radius:5px;">{label}</a>'
        )

    toggle_html = theme_toggle_btn or ""

    return f"""
<div class="topbar">
  <div class="brand">
    <span class="brand-mark">{brand_mark}</span>
    <span style="font-size:13px; color:var(--ink-soft);">{_e(brand_text)}</span>
  </div>
  <div style="width:1px; height:18px; background:var(--line);"></div>
  <h1>{_e(title)}</h1>
  <div class="date-pill">
    <span>{cutoff.isoformat()}</span>
    <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>
  </div>
  <span class="meta"><b class="num">{_e(meta.get('policies', ''))}</b> 万单 · <b class="num">{_e(meta.get('premium', ''))}</b> 万元 · <b class="num">{_e(meta.get('categories', ''))}</b> 类客户</span>
  <div style="margin-left:auto; display:flex; align-items:center; gap:6px;">
    {toggle_html}
    <div style="display:flex; align-items:center; gap:6px; padding:2px; background:var(--surface); border:1px solid var(--line); border-radius:7px;">
      {view_tabs}
    </div>
  </div>
</div>
"""


def render_rail(
    section_counts: dict[str, dict[str, int]],
    anomaly_count: int,
    section_defs: Optional[list[dict]] = None,
) -> str:
    """左侧维度导航 Rail。

    Args:
        section_counts: 每段亮灯统计 {"sec_id": {"red": n, "yellow": n}}
        anomaly_count: Top 异常总数
        section_defs: 段定义列表，默认使用 SECTION_DEFS
    """
    if section_defs is None:
        section_defs = SECTION_DEFS

    items = []
    for s in section_defs:
        c = section_counts.get(s["id"], {})
        red = c.get("red", 0)
        org = c.get("yellow", 0)
        chip = ""
        chips = []
        if red > 0: chips.append(f'<span class="alert">{red}</span>')
        if org > 0: chips.append(f'<span class="alert org">{org}</span>')
        if chips: chip = '<span style="display:flex;gap:3px;">' + "".join(chips) + "</span>"
        items.append(
            f'<li onclick="document.getElementById(\'det-{s["id"]}\').scrollIntoView({{behavior:\'smooth\',block:\'start\'}})">'
            f'<span>{_e(s["label"])}</span>{chip}</li>'
        )

    return f"""
<aside class="rail">
  <h6>导航</h6>
  <ul>
    <li onclick="document.getElementById('top').scrollIntoView({{behavior:'smooth'}})"><span>关键发现</span></li>
    <li onclick="document.getElementById('anom').scrollIntoView({{behavior:'smooth'}})"><span>Top 异常</span><span class="alert">{anomaly_count}</span></li>
    <li onclick="document.getElementById('details').scrollIntoView({{behavior:'smooth'}})"><span>分维度明细</span></li>
  </ul>
  <h6 style="margin-top:20px;">{len(section_defs)} 个维度</h6>
  <ul>
    {"".join(items)}
  </ul>
</aside>
"""


def render_kpi_strip(kpi_cards: list[dict]) -> str:
    """5 KPI 卡横排。

    Args:
        kpi_cards: KPI 卡片列表，每项含：
            - label: 指标名称
            - value: YTD 值
            - delta: 同比差值
            - sub: 副标题（如"同比上年"）
            - sev: 亮灯 CSS 类（alert-red/yellow/blue/green）
            - spark6: 6 期趋势值（供 sparkline）
    """
    parts = []
    for c in kpi_cards:
        sev = c.get("sev", "")
        alert_class = ""
        delta_class = ""
        if sev == "alert-red":
            alert_class = " alert red"
            delta_class = "red"
        elif sev == "alert-yellow":
            alert_class = " alert"
            delta_class = "org"
        elif sev == "alert-green":
            delta_class = "gn"
        elif sev == "alert-blue":
            delta_class = ""

        spark_color = _SEV_COLOR.get(sev, "var(--ink-soft)")
        spark_svg = sparkline(c.get("spark6", []), color_mode="trend", width=210, height=36)

        sev_dot = ""
        if sev == "alert-red":
            sev_dot = '<span class="sev-dot" style="background:var(--red);"></span>'
        elif sev == "alert-yellow":
            sev_dot = '<span class="sev-dot" style="background:var(--orange);"></span>'

        parts.append(f"""
<div class="kpi{alert_class}">
  <div class="label">{sev_dot}{_e(c.get('label', ''))}</div>
  <div class="value-row">
    <span class="value num">{_e(c.get('value', ''))}</span>
    <span class="delta {delta_class}">{_e(c.get('delta', ''))}</span>
  </div>
  <div class="sub">{_e(c.get('sub', ''))}</div>
  <div class="spark">{spark_svg}</div>
</div>
""")
    return f'<div class="kpi-grid">{"".join(parts)}</div>'


@dataclass
class AnomalyCard:
    """异常卡片数据（简化版，用于渲染）。"""
    rank: int
    metric_label: str
    dim_display: str
    value: float
    delta_vs_yoy: float
    spark6: list[float]
    note: str
    premium_share: float
    sev: str


def render_anomaly_grid(
    anomalies: list[AnomalyCard],
    sec_ids: Optional[list[str]] = None,
) -> str:
    """Top 异常卡片网格。

    Args:
        anomalies: 异常卡片列表
        sec_ids:   与 anomalies 等长的段 ID 列表（如 ["team","customer",...]），
                   注入到 data-secid 属性，供 openDrawer JS 定位并展开对应段。
    """
    cards = []
    for i, a in enumerate(anomalies):
        sev_color = _SEV_COLOR.get(a.sev, "var(--ink-soft)")
        spark_svg = sparkline(a.spark6, color_mode="trend", width=210, height=40)

        value_style = f"color:{sev_color};"
        delta_class = "red" if a.sev == "alert-red" else ("org" if a.sev == "alert-yellow" else "")

        # note 格式："🔴 摩托车 变率 88.5%，同比上升 12.3 pt（恶化）"
        note_parts = a.note.split(maxsplit=1) if len(a.note.split()) > 1 else ["", a.note]
        reason = note_parts[1] if len(note_parts) > 1 else ""

        secid_attr = f' data-secid="{sec_ids[i]}"' if sec_ids and i < len(sec_ids) else ""
        cards.append(f"""
<div class="anom-card"{secid_attr} onclick="openDrawer({a.rank - 1})">
  <span class="rank">No.{a.rank:02d}</span>
  <div class="head">
    <span class="dim">{_e(a.metric_label)} · YTD</span>
  </div>
  <div class="tag">{_e(a.dim_display)}</div>
  <div class="value-row">
    <span class="value num" style="{value_style}">{fmt_value(a.value, "pct")}</span>
    <span class="delta {delta_class}">{fmt_delta(a.delta_vs_yoy, "pct")}</span>
  </div>
  <div class="spark">{spark_svg}</div>
  <div class="foot">
    <div class="reason">{_e(reason)}</div>
    <div class="prem">保费贡献 {a.premium_share:.1f}%</div>
  </div>
  <div class="drill-hint">查看明细 →</div>
</div>
""")

    return f"""
<div id="anom"></div>
<div class="section-tag" style="margin-top:8px;"><span class="bar"></span>Top 异常 · {len(anomalies)} 项</div>
<h2 class="h-section">今天需要关注的</h2>
<div class="anom-grid">{"".join(cards)}</div>
"""


@dataclass
class SectionDetail:
    """折叠段数据。"""
    id: str
    label: str
    kind: Literal["overall", "cat", "org", "aux"]
    rows: list[dict]
    section_index: int
    default_open: bool = False


def render_section_detail(
    sec: SectionDetail,
    period_order: Optional[list[str]] = None,
    ytd_label: Optional[str] = None,
) -> str:
    """可展开分维度明细。

    Args:
        sec: 折叠段数据
        period_order: 期标签顺序，默认 PERIOD_ORDER（DPT 6 期）。
                      org-weekly 等 5 期场景可传入 ["上季度",...,"当周"]。
        ytd_label: 当期（最新列）标签，默认 YTD_LABEL（"当年起保"）。
                   决定表头/表体哪一列加高亮。
    """
    po = period_order or PERIOD_ORDER
    yl = ytd_label or YTD_LABEL
    red   = sum(1 for r in sec.rows if r.get("sev") == "alert-red")
    org   = sum(1 for r in sec.rows if r.get("sev") == "alert-yellow")
    blue  = sum(1 for r in sec.rows if r.get("sev") == "alert-blue")
    green = sum(1 for r in sec.rows if r.get("sev") == "alert-green")

    chips = []
    if red   > 0: chips.append(f'<span class="chip warn">{red} 危险</span>')
    if org   > 0: chips.append(f'<span class="chip mid">{org} 异常</span>')
    if blue  > 0: chips.append(f'<span class="chip ok">{blue} 健康</span>')
    if green > 0: chips.append(f'<span class="chip ok">{green} 优秀</span>')

    if sec.kind == "overall":
        finding_html = f"{yl} 各指标见下表，标红项需要重点关注"
    elif sec.rows:
        worst = sec.rows[0]
        worst_ytd_vcr = (
            worst["spark6"][-1]
            if worst.get("spark6") else None
        )
        finding_html = (
            f'最差 <b>{_e(worst.get("name", ""))}</b> · YTD 变率 '
            f'<b>{fmt_value(worst_ytd_vcr, "pct")}</b>'
        )
    else:
        finding_html = "—"

    # tbody
    if sec.kind == "overall":
        tbody_html = _section_tbody_overall(sec.rows, po, yl)
    else:
        tbody_html = _section_tbody_dim(sec.rows, sec.id, po, yl)

    open_class = " open" if sec.default_open else ""
    return f"""
<div id="det-{sec.id}" class="det-card{open_class}">
  <div class="det-head" onclick="this.parentElement.classList.toggle('open')">
    <span class="idx">{sec.section_index:02d}</span>
    <span class="name">{_e(sec.label)}</span>
    <span class="status">{"".join(chips)}</span>
    <span class="findings">{finding_html}</span>
    <span class="caret">▾</span>
  </div>
  <div class="det-body">
    <table class="dtab">{_section_thead_overall(po, yl)}{tbody_html}</table>
  </div>
</div>
"""


def _section_thead_overall(period_order: list[str], ytd_label: str) -> str:
    """整体段表头。"""
    th_periods = "".join(
        f'<th class="{"thcur" if p == ytd_label else ""}">{_e(p)}</th>'
        for p in period_order
    )
    return (
        f'<thead><tr><th class="thlt">指标</th>'
        f'<th class="thlt">{len(period_order)} 期趋势</th>{th_periods}</tr></thead>'
    )


def _section_tbody_overall(rows: list[dict], period_order: list[str], ytd_label: str) -> str:
    """整体段表体。"""
    body_rows = []
    for r in rows:
        spark_color = _SEV_COLOR.get(r.get("sev", ""), "var(--ink-mute)")
        spark_svg = sparkline(r.get("spark6", []), color_mode="alert", width=100, height=28)
        row_kind = r.get("kind", "pct")  # 每行按自身指标 kind 格式化（保费=wan，赔付率=pct…）

        cells = "".join(
            f'<td class="{"tdcur" if period_order[i] == ytd_label else ""}">'
            f'<span class="num">{fmt_value(v, row_kind)}</span></td>'
            for i, v in enumerate(r.get("spark6", []))
        )
        body_rows.append(
            f'<tr><td class="tdlt obj-name muted">{_e(r.get("name", ""))}</td>'
            f'<td class="tdlt">{spark_svg}</td>{cells}</tr>'
        )
    return f'<tbody>{"".join(body_rows)}</tbody>'


def _dot_html(sev: str) -> str:
    """YTD 严重性小圆点，仅红/橙/绿显示。"""
    if sev in ("", "alert-gray", "alert-blue"):
        return ""
    bg = "var(--red)" if sev == "alert-red" else (
        "var(--orange)" if sev == "alert-yellow" else "var(--green)"
    )
    return (
        f'<span class=sev style="display:inline-block;width:6px;height:6px;'
        f'border-radius:50%;margin-left:4px;background:{bg};"></span>'
    )


def render_metric_tabs(
    metric_defs: list[tuple],
    default_metric: str,
    sec_id: str,
) -> str:
    """生成指标切换 tabs HTML（对应 switchMetric JS）。

    Args:
        metric_defs: [(col_id, label, kind), ...] 与 SECTION_METRIC_MAP 对齐
        default_metric: 默认选中的 col_id
        sec_id: 段 ID，供 onclick 绑定
    Returns:
        .metric-tabs div HTML 字符串
    """
    tab_items = [
        f'<span class="tab{" on" if col == default_metric else ""}" '
        f'data-metric="{col}" onclick="switchMetric(this, \'{sec_id}\')">'
        f'{_e(label)}</span>'
        for col, label, _kind in metric_defs
    ]
    return (
        f'<div class="metric-tabs"><span class="lbl">切换指标</span>'
        f'{"".join(tab_items)}</div>'
    )


def render_drill_panel(sec_id: str, drill_sec_list: list[tuple]) -> str:
    """生成下钻面板 HTML（对应 openDrill/closeDrill JS）。

    Args:
        sec_id: 段 ID（如 "customer"）
        drill_sec_list: [(sec2_id, label), ...] 可下钻目标维度
    Returns:
        .drill-panel div HTML 字符串
    """
    return f"""<div class="drill-panel" id="drp-{sec_id}">
  <div class="drill-bar">
    <span class="drill-crumb">下钻: <span class="drill-pname"></span></span>
    <div class="drill-dim-tabs" id="drp-dims-{sec_id}"></div>
    <div class="drill-metric-tabs" id="drp-mtabs-{sec_id}"></div>
    <button class="drill-close" onclick="closeDrill('{sec_id}')">关闭</button>
  </div>
  <div class="drill-wrap" id="drp-wrap-{sec_id}"></div>
</div>"""


def dashboard_interact_js(
    metric_defs: list[tuple],
    drill_dims: dict,
    period_order: list[str],
    ytd_idx: int = 4,
    drill_metric_defs: Optional[list[tuple]] = None,
) -> str:
    """生成指标切换 + 交叉下钻交互 JS（从 DPT render_v1.py 参数化提炼）。

    Args:
        metric_defs: [(col_id, label, kind), ...] 与 SECTION_METRIC_MAP 对齐（段明细切换）
        drill_dims: {sec_id: [(sec2_id, label), ...]} 各段的可下钻目标维度
        period_order: 期标签列表（供下钻表头）
        ytd_idx: 当期（最新列）在 period_order 中的索引，默认 4
        drill_metric_defs: [(col_id, label, kind), ...] 下钻面板专属指标列表（默认同 metric_defs）。
            org-weekly 传 4 项（vcr/lr/freq/avg，对齐 DD series 顺序），seriesOffset=2+metricIdx 可用。
    Returns:
        <script> 内容（不含 <script> 标签）
    """
    import json as _json  # noqa: PLC0415
    _drill_metrics = drill_metric_defs if drill_metric_defs is not None else metric_defs
    # metric_defs → JS 数组（段明细指标切换）
    metric_tabs_js = _json.dumps(
        [[col, label, kind] for col, label, kind in metric_defs],
        ensure_ascii=False,
    )
    # 下钻面板指标（独立列表，避免 seriesOffset 超界）
    drill_metric_tabs_js = _json.dumps(
        [[col, label, kind] for col, label, kind in _drill_metrics],
        ensure_ascii=False,
    )
    # drill_dims → JS 对象
    drill_dims_js = _json.dumps(
        {sec_id: [[s2_id, s2_lbl] for s2_id, s2_lbl in targets]
         for sec_id, targets in drill_dims.items()},
        ensure_ascii=False,
    )
    period_labels_js = _json.dumps(period_order, ensure_ascii=False)
    sev_colors_js = "['var(--ink-mute)','var(--green)','var(--navy)','var(--orange)','var(--red)']"

    return f"""
// openDrawer: 异常卡片点击 → 定位并展开对应段
function openDrawer(idx) {{
  var cards = document.querySelectorAll('.anom-card');
  if (idx >= cards.length) return;
  var secId = cards[idx].dataset.secid;
  if (!secId) return;
  var det = document.getElementById('det-' + secId);
  if (!det) return;
  det.classList.add('open');
  det.scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}

// ===== 指标切换 tab =====
function switchMetric(tabEl, sectionId) {{
  const tabsContainer = tabEl.parentElement;
  tabsContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  tabEl.classList.add('on');
  const newMetric = tabEl.dataset.metric;
  const table = document.querySelector('#det-' + sectionId + ' table.dtab');
  if (!table) return;
  const rows = table.querySelectorAll('tbody tr');
  const tabsList = Array.from(tabsContainer.querySelectorAll('.tab')).map(t => t.dataset.metric);
  const metricIdx = tabsList.indexOf(newMetric);
  rows.forEach(row => {{
    const valsStr = row.dataset['vals' + _capitalize(newMetric)];
    if (!valsStr) return;
    const values = valsStr.split('/').map(s => s === '' ? null : parseFloat(s));
    const kindsAttr = (row.dataset.kinds || '').split('/');
    const kind = kindsAttr[metricIdx] || 'pct';
    const sev = row.dataset['sev' + _capitalize(newMetric)] || '';
    const cells = row.querySelectorAll('td[class*="cell-"]');
    cells.forEach((cell, i) => {{
      const n = cell.querySelector('.num');
      if (n) n.textContent = _fmtV(values[i], kind);
    }});
    const trendCell = row.querySelector('.trend-cell');
    if (trendCell) trendCell.innerHTML = _miniSparkline(values, _sevColor(sev));
  }});
}}
function _capitalize(s) {{ return s.split('_').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(''); }}
function _fmtV(v, kind) {{
  if (v === null || isNaN(v)) return '—';
  if (kind === 'pct')   return v.toFixed(1) + '%';
  if (kind === 'coef')  return v.toFixed(3);
  if (kind === 'money') return '¥' + Math.round(v).toLocaleString();
  if (kind === 'wan')   return Math.round(v/10000).toLocaleString();
  return v.toFixed(2);
}}
function _sevColor(sev) {{
  return {{'alert-red':'var(--red)','alert-yellow':'var(--orange)','alert-green':'var(--green)','alert-blue':'var(--navy)'}}[sev] || 'var(--ink-mute)';
}}
function _miniSparkline(values, color) {{
  const clean = values.map((v,i)=>{{if(v!==null&&!isNaN(v))return{{v,i}};return null;}}).filter(Boolean);
  if (clean.length < 2) return '<span style="color:var(--ink-light);">—</span>';
  const ys = clean.map(o=>o.v); const ymin=Math.min(...ys),ymax=Math.max(...ys),range=(ymax-ymin)||1;
  const w=100,h=28,pad=4,n=values.length-1;
  const pts=clean.map(o=>{{const x=pad+(o.i/n)*(w-2*pad);const y=(h-pad)-((o.v-ymin)/range)*(h-2*pad);return x.toFixed(1)+','+y.toFixed(1);}}).join(' ');
  return '<svg width="'+w+'" height="'+h+'"><polyline points="'+pts+'" stroke="'+color+'" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}}

// ===== 交叉下钻 =====
const _DRILL_DIMS = {drill_dims_js};
const _DRILL_METRIC_TABS = {drill_metric_tabs_js};
const _DRILL_PERIOD_LABELS = {period_labels_js};
const _DRILL_YTD_IDX = {ytd_idx};
const _DRILL_SEV_COLORS = {sev_colors_js};

document.addEventListener('click', function(e){{
  const el = e.target.closest('.drill-trigger');
  if (!el) return;
  const secId=el.dataset.sec, rawVal=el.dataset.rawval, dispName=el.dataset.disp;
  if (!secId) return;
  _openDrill(secId, rawVal, dispName, el);
}});

function _openDrill(secId, rawVal, dispName, triggerEl) {{
  const panel = document.getElementById('drp-' + secId);
  if (!panel) return;
  const table = triggerEl.closest('table');
  if (table) {{
    table.querySelectorAll('tr.drill-active').forEach(r=>r.classList.remove('drill-active'));
    triggerEl.closest('tr').classList.add('drill-active');
  }}
  panel.dataset.rawval = rawVal;
  panel.querySelector('.drill-pname').textContent = dispName;
  const dims = _DRILL_DIMS[secId] || [];
  document.getElementById('drp-dims-' + secId).innerHTML = dims.map((d,i) =>
    `<span class="drill-dim-tab${{i===0?' on':''}}" data-dim="${{d[0]}}" onclick="_selectDrillDim('${{secId}}',this)">${{_escH(d[1])}}</span>`
  ).join('');
  document.getElementById('drp-mtabs-' + secId).innerHTML = _DRILL_METRIC_TABS.map((m,i) =>
    `<span class="drill-metric-tab${{i===0?' on':''}}" data-midx="${{i}}" onclick="_selectDrillMetric('${{secId}}',this)">${{_escH(m[1])}}</span>`
  ).join('');
  panel.style.display = 'block';
  if (dims.length) _renderDrillTable(secId, rawVal, dims[0][0], 0);
  panel.scrollIntoView({{block:'nearest', behavior:'smooth'}});
}}
function closeDrill(secId) {{
  const p=document.getElementById('drp-'+secId);
  if(p)p.style.display='none';
  const d=document.getElementById('det-'+secId);
  if(d)d.querySelectorAll('tr.drill-active').forEach(r=>r.classList.remove('drill-active'));
}}
function _selectDrillDim(secId, tabEl) {{
  tabEl.parentElement.querySelectorAll('.drill-dim-tab').forEach(t=>t.classList.remove('on'));
  tabEl.classList.add('on');
  const p=document.getElementById('drp-'+secId);
  const raw=p.dataset.rawval;
  const mTab=document.querySelector('#drp-mtabs-'+secId+' .drill-metric-tab.on');
  _renderDrillTable(secId, raw, tabEl.dataset.dim, mTab?parseInt(mTab.dataset.midx):0);
}}
function _selectDrillMetric(secId, tabEl) {{
  tabEl.parentElement.querySelectorAll('.drill-metric-tab').forEach(t=>t.classList.remove('on'));
  tabEl.classList.add('on');
  const p=document.getElementById('drp-'+secId);
  const raw=p.dataset.rawval;
  const dimTab=document.querySelector('#drp-dims-'+secId+' .drill-dim-tab.on');
  _renderDrillTable(secId, raw, dimTab?dimTab.dataset.dim:'', parseInt(tabEl.dataset.midx));
}}
function _renderDrillTable(secId, rawVal, dimId, metricIdx) {{
  const key = secId+'|||'+rawVal+'|||'+dimId;
  const rows = (typeof DD !== 'undefined' && DD[key]) ? DD[key] : [];
  const wrap = document.getElementById('drp-wrap-'+secId);
  if(!wrap) return;
  if(!rows.length) {{
    wrap.innerHTML = '<p style="padding:8px 0;color:var(--ink-mute);font-size:12px;">该维度无交叉数据</p>';
    return;
  }}
  const [,, kind] = _DRILL_METRIC_TABS[metricIdx] || _DRILL_METRIC_TABS[0];
  const seriesOffset = 2 + metricIdx;
  const ytdIdx = _DRILL_YTD_IDX;
  let html = '<table class="dtab"><thead><tr><th class="thlt">细分</th>';
  _DRILL_PERIOD_LABELS.forEach((lbl,i) => {{
    html += `<th class="${{i===ytdIdx?'thcur':''}}">${{_escH(lbl)}}</th>`;
  }});
  html += '</tr></thead><tbody>';
  rows.forEach(r => {{
    const sev = _DRILL_SEV_COLORS[r[1]] || _DRILL_SEV_COLORS[0];
    const series = r[seriesOffset] || [];
    const ytdV = series[ytdIdx];
    html += `<tr><td class="tdlt obj-name" style="color:${{sev}}">${{_escH(String(r[0]))}}</td>`;
    series.forEach((v,i) => {{
      html += `<td class="${{i===ytdIdx?'tdcur':''}}">${{_fmtV(v, kind)}}</td>`;
    }});
    html += '</tr>';
  }});
  html += '</tbody></table>';
  wrap.innerHTML = html;
}}
function _escH(s) {{ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}
"""


DRILL_PANEL_CSS = """
.metric-tabs{ display:flex; align-items:center; gap:4px; margin-bottom:10px;
  border-bottom:1px solid var(--line); padding-bottom:8px; }
.metric-tabs .lbl{ font-size:11.5px; color:var(--ink-mute); margin-right:6px; }
.metric-tabs .tab{ padding:4px 10px; font-size:12.5px; color:var(--ink-soft);
  cursor:pointer; border-radius:var(--radius-sm); }
.metric-tabs .tab.on{ background:var(--surface-soft); color:var(--ink); font-weight:500; }
.metric-tabs .tab:hover:not(.on){ color:var(--ink); }
.drill-panel{ display:none; margin-top:12px; border:1px solid var(--line-soft);
  border-radius:var(--radius); background:var(--paper-soft); padding:12px 16px; }
.drill-bar{ display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
.drill-crumb{ font-size:12px; color:var(--ink-mute); }
.drill-crumb .drill-pname{ font-weight:500; color:var(--ink); }
.drill-dim-tabs,.drill-metric-tabs{ display:flex; gap:3px; }
.drill-dim-tab,.drill-metric-tab{ padding:2px 8px; font-size:11.5px; border:1px solid var(--line);
  border-radius:4px; cursor:pointer; color:var(--ink-soft); background:var(--surface); }
.drill-dim-tab.on,.drill-metric-tab.on{ background:var(--navy); color:#fff; border-color:var(--navy); }
.drill-close{ margin-left:auto; font-size:11px; padding:2px 8px; border:1px solid var(--line);
  border-radius:4px; cursor:pointer; background:var(--surface); color:var(--ink-mute); }
.drill-close:hover{ color:var(--ink); }
"""


def _section_tbody_dim(rows: list[dict], sec_id: str,
                       period_order: list[str], ytd_label: str) -> str:
    """非整体段表体（cat/org/aux）。

    Args:
        rows: 每项含：
            - name: 显示名称
            - raw_value: 原始值（供下钻）
            - values_by_metric: {指标列: N期值列表}
            - sev_by_metric: {指标列: 亮灯class}
            - sev: 默认亮灯（按变率）
        sec_id: 段 ID（供下钻）
        period_order: 期标签顺序
        ytd_label: 当期标签（决定高亮列）
    """
    body_rows = []
    for r in rows:
        spark_color = _SEV_COLOR.get(r.get("sev", ""), "var(--ink-mute)")
        spark_svg = sparkline(
            r.get("values_by_metric", {}).get("variable_cost_ratio", []),
            color_mode="trend",
            width=100, height=28,
            area=False, show_dots=False,
        )

        # 构建 data-attrs：每个指标的 6 期值 + 亮灯 class
        data_attrs = []
        for col, vals in r.get("values_by_metric", {}).items():
            vals_str = "/".join(
                "" if v is None or (isinstance(v, float) and math.isnan(v))
                else f"{float(v):.6g}"
                for v in vals
            )
            data_key = col.replace("_", "-")
            data_attrs.append(f'data-vals-{data_key}="{vals_str}"')

        for col, cls in r.get("sev_by_metric", {}).items():
            data_key = col.replace("_", "-")
            data_attrs.append(f'data-sev-{data_key}="{cls}"')

        data_attrs.append(f'data-kinds="{_METRIC_KINDS}"')

        raw_v = _e(r.get("raw_value", r.get("name", "")))
        disp_v = _e(r.get("name", ""))
        vcr_vals = r.get("values_by_metric", {}).get("variable_cost_ratio", [])
        cells = "".join(
            f'<td class="cell-{i}{" tdcur" if period_order[i] == ytd_label else ""}">'
            f'<span class="num">{fmt_value(v, "pct")}</span>'
            f'{_dot_html(r.get("sev", "")) if period_order[i] == ytd_label else ""}'
            f'</td>'
            for i, v in enumerate(vcr_vals)
        )
        body_rows.append(
            f'<tr {" ".join(data_attrs)}>'
            f'<td class="tdlt obj-name drill-trigger" '
            f'data-sec="{sec_id}" data-rawval="{raw_v}" data-disp="{disp_v}">'
            f'{disp_v}</td>'
            f'<td class="tdlt trend-cell">{spark_svg}</td>{cells}</tr>'
        )
    return f'<tbody>{"".join(body_rows)}</tbody>'
