"""V1 · 诊断驾驶舱（默认首页）渲染器。

设计来源：/tmp/design_pkg/untitled/project/V1 诊断驾驶舱.html + v1-cockpit-app.jsx
本项目化要点：
  - 时间窗 6 个（36m/24m/yoy/12m/6m/ytd）— 不是设计稿描述的 7 个
  - 客户类别 11 类 / 三级机构 14 家 — 实测值
  - 亮灯统一从 chexian-report-shell/lib/alerts.py:light() 取，禁止硬编码阈值
  - 警戒线显示用项目阈值（变率 89% / 赔付率 70% / 出险率 10%）— 不是设计稿 90%/70%/12%

组件结构（按设计稿顺序）：
  TopBar → Shell (Rail + Main:
    Hero Alert
    KPI Strip (5 指标)
    Anomaly Grid (Top 8)
    Section Detail × 10
  ) → Drawers (HTML 预渲染，JS show/hide)
"""
from __future__ import annotations

import html
import json
import math
from dataclasses import asdict
from datetime import date
from typing import Any, Optional

import pandas as pd

try:
    from ._dhr_bootstrap import dhr as dhr_lib
except ImportError:
    from _dhr_bootstrap import dhr as dhr_lib  # type: ignore[no-redef]

light = dhr_lib.light
short_category_label = dhr_lib.short_category_label
fmt_num = dhr_lib.fmt_num

# ---- 同 skill lib 内部 import ----
try:
    from .anomalies import (  # type: ignore
        Anomaly, AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER,
        YTD_LABEL, YOY_LABEL, RANKED_METRICS, compute_top_anomalies,
        build_drilldown_data, DRILL_SEC_LIST, _SEC_FIELD,
    )
except ImportError:  # pragma: no cover — 脚本式调用 fallback
    from anomalies import (  # type: ignore[no-redef]
        Anomaly, AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER,
        YTD_LABEL, YOY_LABEL, RANKED_METRICS, compute_top_anomalies,
        build_drilldown_data, DRILL_SEC_LIST, _SEC_FIELD,
    )

# 主题资源下沉到基座（ADR-002：themes_v2 移入 chexian-report-shell，断 DPT↔org-weekly 横向依赖）
from dhr_lib.themes_v2 import (
    style_block, BASE_CSS, FONT_LINKS,
    THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn,
    DARK_CSS, THEME_TOGGLE_CSS,
)


# ============== KPI 指标定义（首屏 5 卡） ==============
# (label, value_col, value_kind, alert_key, sub_kind)
# sub_kind: "warn_line"=从 alerts.TH 派生警戒线显示；"yoy_pct"=同比百分比；"limit_15"=自主系数上限
KPI_DEFS: list[tuple[str, str, str, Optional[str], str]] = [
    ("变动成本率",   "variable_cost_ratio",   "pct",   "variable_cost_ratio_pct", "warn_line"),
    ("满期赔付率",   "earned_claim_ratio",    "pct",   "earned_loss_ratio_pct",   "warn_line"),
    ("满期出险率",   "earned_loss_frequency", "pct",   "earned_loss_freq_pct",    "warn_line"),
    ("案均赔款",     "avg_claim_amount",      "money", None,                       "yoy_pct"),
    ("自主系数",     "weighted_pricing_factor","coef", None,                       "factor_limit"),
]


def _get_alerts_th() -> dict:
    """从 chexian-report-shell/lib/alerts.py 取阈值字典（避免本模块硬编码）。"""
    if hasattr(dhr_lib, 'TH'):
        return dhr_lib.TH
    import importlib
    alerts_mod = importlib.import_module('dhr_lib.alerts')
    return alerts_mod.TH


_TH = _get_alerts_th()

# 10 段定义：section_id / 段头中文 / 切片函数 key
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


# ============== 工具函数 ==============

def _safe_float(v) -> Optional[float]:
    if v is None: return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


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


def _sparkline(values: list, color: str = "var(--ink-soft)",
               width: int = 160, height: int = 40, area: bool = True,
               dots: bool = True) -> str:
    """轻量 sparkline（独立于旧 render.py）。

    values 为 6 期数值（None/NaN 视为缺失）。color 取 CSS 变量或 'auto'（终点上涨红/下降绿）。
    """
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

    pts = []
    for i, v in cleaned:
        x = pad + (i / n_steps) * (width - 2 * pad)
        y = (height - pad) - ((v - y_min) / y_range) * (height - 2 * pad)
        pts.append((x, y))

    if color == "auto":
        stroke = "var(--red)" if cleaned[-1][1] >= cleaned[0][1] else "var(--green)"
    else:
        stroke = color

    line_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts: list[str] = []
    if area and len(pts) >= 2:
        area_pts = f"{pts[0][0]:.1f},{height-pad} {line_pts} {pts[-1][0]:.1f},{height-pad}"
        parts.append(f'<polygon points="{area_pts}" fill="{stroke}" fill-opacity="0.07"/>')
    parts.append(
        f'<polyline points="{line_pts}" stroke="{stroke}" stroke-width="1.6" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    if dots:
        for i, (x, y) in enumerate(pts):
            r = 2.6 if i == len(pts) - 1 else 1.6
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{stroke}"/>')

    return (
        f'<svg width="{width}" height="{height}" style="display:block">'
        f'{"".join(parts)}</svg>'
    )


def _e(s: Any) -> str:
    """HTML 转义。"""
    return html.escape(str(s if s is not None else ""))


# ============== 数据切片 ==============

AUX_FIELDS = list(AUX_DIM_LABELS.keys())

def _all_aux_mask(df: pd.DataFrame, exclude_field: Optional[str] = None) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for f in AUX_FIELDS:
        if f == exclude_field: continue
        mask &= (df[f] == "__ALL__")
    return mask


def _slice_overall(df: pd.DataFrame) -> pd.DataFrame:
    """整体 6 期"""
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[is_all_cat & is_all_org & _all_aux_mask(df)].copy()


def _slice_by_cat(df: pd.DataFrame) -> pd.DataFrame:
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[(~is_all_cat) & is_all_org & _all_aux_mask(df)].copy()


def _slice_by_org(df: pd.DataFrame) -> pd.DataFrame:
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[is_all_cat & (~is_all_org) & _all_aux_mask(df)].copy()


def _slice_by_aux(df: pd.DataFrame, field: str) -> pd.DataFrame:
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    is_active  = df[field] != "__ALL__"
    is_real    = df[field] != "__NULL__"
    return df[is_all_cat & is_all_org & is_active & is_real & _all_aux_mask(df, exclude_field=field)].copy()


def _period_value(rows: pd.DataFrame, period: str, col: str) -> Optional[float]:
    """从 cohort 行中取指定 period 的 col。"""
    sub = rows[rows["period_label"] == period]
    if sub.empty: return None
    return _safe_float(sub.iloc[0][col])


def _period_n(rows: pd.DataFrame, period: str) -> int:
    sub = rows[rows["period_label"] == period]
    if sub.empty: return 0
    return int(_safe_float(sub.iloc[0]["policy_count"]) or 0)


def _build_overall_meta(df: pd.DataFrame) -> dict:
    """整体 YTD 顶栏元数据。"""
    overall = _slice_overall(df)
    ytd = overall[overall["period_label"] == YTD_LABEL]
    if ytd.empty:
        return {"policies": "—", "premium": "—", "categories": "—"}
    n_policy = _safe_float(ytd.iloc[0]["policy_count"]) or 0
    premium = _safe_float(ytd.iloc[0]["premium_sum"]) or 0
    # 客户类别去重数量（仅 YTD 期内）
    by_cat_ytd = _slice_by_cat(df)
    by_cat_ytd = by_cat_ytd[by_cat_ytd["period_label"] == YTD_LABEL]
    n_cat = by_cat_ytd["customer_category"].nunique()
    return {
        "policies": f"{n_policy/10000:,.2f}",
        "premium": f"{premium/10000:,.0f}",
        "categories": str(n_cat),
        "policy_raw": n_policy,
        "premium_raw": premium,
    }


# ============== 组件渲染 ==============

def _render_topbar(cutoff: date, meta: dict) -> str:
    return f"""
<div class="topbar">
  <div class="brand">
    <span class="brand-mark">川</span>
    <span style="font-size:13px; color:var(--ink-soft);">四川分公司 · 业务诊断</span>
  </div>
  <div style="width:1px; height:18px; background:var(--line);"></div>
  <h1>多期车险保单品质对比</h1>
  <div class="date-pill">
    <span>{cutoff.isoformat()}</span>
    <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>
  </div>
  <span class="meta"><b class="num">{_e(meta['policies'])}</b> 万单 · <b class="num">{_e(meta['premium'])}</b> 万元 · <b class="num">{_e(meta['categories'])}</b> 类客户</span>
  <div style="margin-left:auto; display:flex; align-items:center; gap:6px;">
    {theme_toggle_btn()}
    <div style="display:flex; align-items:center; gap:6px; padding:2px; background:var(--surface); border:1px solid var(--line); border-radius:7px;">
      <span style="padding:4px 10px; font-size:12px; background:var(--ink); color:var(--paper); border-radius:5px; font-weight:500;">驾驶舱</span>
      <a href="{cutoff.isoformat()}-weekly.html" style="padding:4px 10px; font-size:12px; color:var(--ink-soft); text-decoration:none; border-radius:5px;">周报</a>
      <a href="{cutoff.isoformat()}-table.html" style="padding:4px 10px; font-size:12px; color:var(--ink-soft); text-decoration:none; border-radius:5px;">超表</a>
    </div>
  </div>
</div>
"""


def _render_rail(section_counts: dict[str, dict[str, int]], anomaly_count: int) -> str:
    items = []
    for s in SECTION_DEFS:
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
  <h6 style="margin-top:20px;">10 个维度</h6>
  <ul>
    {"".join(items)}
  </ul>
</aside>
"""


def _render_hero_alert(anomalies: list[Anomaly], overall_ytd_summary: str) -> str:
    n_red = sum(1 for a in anomalies if a.sev == "alert-red")
    n_severe = sum(1 for a in anomalies if a.sev in ("alert-red", "alert-yellow") and a.delta_vs_yoy >= 50)

    # 主前 4 项 cohort 列表
    top4 = " / ".join(_e(a.dim_display) for a in anomalies[:4]) if anomalies else "—"

    return f"""
<div class="alert-banner">
  <span class="alert-icon">!</span>
  <div class="msg">
    <span><b>{n_red} 项</b>细分维度已超警戒线 · <b>{n_severe} 项</b>较上年同期恶化 ≥ 50 PP · 主要由<b>赔付端</b>推升</span>
    <span class="sub">{_e(overall_ytd_summary)} 建议优先处理 {top4}。</span>
  </div>
  <button class="cta" onclick="document.getElementById('anom').scrollIntoView({{behavior:'smooth'}})">查看异常详情 ↓</button>
</div>
"""


def _build_kpi_data(df: pd.DataFrame) -> list[dict]:
    """5 个 KPI 卡的数据（基于 overall 6 期）。"""
    overall = _slice_overall(df)
    if overall.empty: return []

    cards = []
    for label, col, kind, alert_key, sub_kind in KPI_DEFS:
        ytd_v = _period_value(overall, YTD_LABEL, col)
        yoy_v = _period_value(overall, YOY_LABEL, col)
        rolling12_v = _period_value(overall, "滚动12个月", col)
        n_ytd = _period_n(overall, YTD_LABEL)
        delta_yoy = (ytd_v - yoy_v) if (ytd_v is not None and yoy_v is not None) else None
        delta_12m = (ytd_v - rolling12_v) if (ytd_v is not None and rolling12_v is not None) else None

        # 亮灯
        if alert_key:
            sev_cls, sev_label = light(alert_key, ytd_v, n_ytd)
        else:
            sev_cls, sev_label = "", ""

        # 6 期 spark 数据
        spark6 = [_period_value(overall, p, col) for p in PERIOD_ORDER]

        # sub 文本（警戒线/同比/系数上限三种模板，全部从 alerts.TH 或数据派生）
        if sub_kind == "warn_line" and alert_key:
            warn_v = _TH.get(alert_key, (0, 0, 0))[1]  # 警戒线 = 健康/异常分界
            delta_txt = f"{delta_yoy:+.1f} PP" if delta_yoy is not None else "—"
            sub = f"警戒线 {warn_v:g}% · 同期 {delta_txt}"
        elif sub_kind == "yoy_pct" and yoy_v and yoy_v > 0 and delta_yoy is not None:
            sub = f"同比 {(delta_yoy / yoy_v * 100):+.1f}%"
        elif sub_kind == "factor_limit":
            # 自主系数监管上限（业务规则字典：燃油 1.5 / 新能源 1.45）
            delta_txt = f"{delta_yoy:+.3f}" if delta_yoy is not None else "—"
            sub = f"上限 1.5 · 同比 {delta_txt}"
        else:
            sub = "—"

        cards.append({
            "label": label,
            "value": fmt_value(ytd_v, kind),
            "delta": fmt_delta(delta_yoy, kind),
            "delta_12m": fmt_delta(delta_12m, kind),
            "sub": sub,
            "sev": sev_cls,
            "spark6": spark6,
            "kind": kind,
            "col": col,
        })
    return cards


def _render_kpi_strip(kpi_cards: list[dict]) -> str:
    parts = []
    for c in kpi_cards:
        sev = c["sev"]
        # alert-red / alert-yellow → 设计稿"alert red" / "alert org"
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

        # sparkline 颜色映射
        spark_color = {
            "alert-red": "var(--red)",
            "alert-yellow": "var(--orange)",
            "alert-blue": "var(--navy)",
            "alert-green": "var(--green)",
        }.get(sev, "var(--ink-soft)")

        spark_svg = _sparkline(c["spark6"], color=spark_color, width=210, height=36)
        sev_dot = ""
        if sev == "alert-red":
            sev_dot = '<span class="sev-dot" style="background:var(--red);"></span>'
        elif sev == "alert-yellow":
            sev_dot = '<span class="sev-dot" style="background:var(--orange);"></span>'

        parts.append(f"""
<div class="kpi{alert_class}">
  <div class="label">{sev_dot}{_e(c['label'])}</div>
  <div class="value-row">
    <span class="value num">{_e(c['value'])}</span>
    <span class="delta {delta_class}">{_e(c['delta'])}</span>
  </div>
  <div class="sub">{_e(c['sub'])}</div>
  <div class="spark">{spark_svg}</div>
</div>
""")
    return f'<div class="kpi-grid">{"".join(parts)}</div>'


def _render_anomaly_grid(anomalies: list[Anomaly]) -> str:
    cards = []
    for i, a in enumerate(anomalies, 1):
        sev_color = {
            "alert-red": "var(--red)",
            "alert-yellow": "var(--orange)",
            "alert-blue": "var(--navy)",
            "alert-green": "var(--green)",
        }.get(a.sev, "var(--ink-soft)")
        spark_svg = _sparkline(a.spark6, color=sev_color, width=210, height=40)
        # value color 取 sev
        value_style = f'color:{sev_color};'
        delta_class = "red" if a.sev == "alert-red" else ("org" if a.sev == "alert-yellow" else "")
        sub = a.dim_label.split("·")[0] if "·" in a.dim_label else a.dim_kind

        cards.append(f"""
<div class="anom-card" onclick="openDrawer({i-1})">
  <span class="rank">No.{i:02d}</span>
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
    <div class="reason">{_e(a.note.split(maxsplit=1)[1] if a.note else "")}</div>
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


# ============== 折叠明细 × 10 ==============

def _build_section_rows(df: pd.DataFrame, sec: dict) -> list[dict]:
    """为每段返回 rows: [{name, sev, metrics: {col → spark6}, n_ytd, ...}]

    sec.kind:
      - "overall": 1 行（特殊），按指标维度展开
      - "cat": by_cat → 11 行
      - "org": by_org → 14 行
      - "aux": by_aux_field → 2-4 行
    """
    if sec["kind"] == "overall":
        overall = _slice_overall(df)
        n_ytd = _period_n(overall, YTD_LABEL)
        # overall 段：每个 KPI_DEFS 一行
        rows = []
        for label, col, kind, alert_key, _ in KPI_DEFS:
            spark6 = [_period_value(overall, p, col) for p in PERIOD_ORDER]
            ytd_v = _period_value(overall, YTD_LABEL, col)
            sev_cls = ""
            if alert_key:
                sev_cls, _ = light(alert_key, ytd_v, n_ytd)
            rows.append({
                "name": label, "kind": kind, "col": col,
                "n_ytd": n_ytd, "sev": sev_cls,
                "spark6": spark6, "values_by_metric": None,
            })
        return rows

    # cohort 段（cat/org/aux）：每个 cohort 一行
    if sec["kind"] == "cat":
        sub = _slice_by_cat(df)
        groupby_col = "customer_category"
        label_fn = short_category_label
    elif sec["kind"] == "org":
        sub = _slice_by_org(df)
        groupby_col = "org_level_3"
        label_fn = lambda x: x
    else:  # aux
        field = sec["field"]
        sub = _slice_by_aux(df, field)
        groupby_col = field
        labels_map = AUX_VALUE_LABELS.get(field, {})
        label_fn = lambda x: labels_map.get(str(x), str(x))

    rows = []
    for val, grp in sub.groupby(groupby_col):
        n_ytd = _period_n(grp, YTD_LABEL)
        if n_ytd == 0: continue  # 空 cohort 跳过

        # 计算 6 指标 × 6 期的全部值（供切换 tab）
        values_by_metric: dict[str, list[Optional[float]]] = {}
        sev_by_metric: dict[str, str] = {}
        for metric_col, _, _, alert_key in METRIC_TABS:
            vals = [_period_value(grp, p, metric_col) for p in PERIOD_ORDER]
            values_by_metric[metric_col] = vals
            ytd_v = vals[-1]  # PERIOD_ORDER 最后是 ytd
            if alert_key:
                cls, _ = light(alert_key, ytd_v, n_ytd)
                sev_by_metric[metric_col] = cls
            else:
                sev_by_metric[metric_col] = ""

        # 默认按"变率"亮灯做 sev
        default_sev = sev_by_metric.get("variable_cost_ratio", "")

        rows.append({
            "name": label_fn(val),
            "raw_value": str(val),
            "n_ytd": n_ytd,
            "sev": default_sev,
            "values_by_metric": values_by_metric,
            "sev_by_metric": sev_by_metric,
            "premium_ytd": _period_value(grp, YTD_LABEL, "premium_sum") or 0,
        })

    # 排序：按 YTD 变率降序（最差在前）
    rows.sort(key=lambda r: r["values_by_metric"]["variable_cost_ratio"][-1] or 0, reverse=True)
    return rows


_SEV_COLOR = {
    "alert-red": "var(--red)",
    "alert-yellow": "var(--orange)",
    "alert-green": "var(--green)",
    "alert-blue": "var(--navy)",
}
_METRIC_KINDS = "/".join(kind for _, _, kind, _ in METRIC_TABS)


def _section_thead(sec: dict) -> str:
    th_periods = "".join(
        f'<th class="{"thcur" if p == YTD_LABEL else ""}">{_e(p)}</th>'
        for p in PERIOD_ORDER
    )
    obj_th = "指标" if sec["kind"] == "overall" else sec["label"]
    return (
        f'<thead><tr><th class="thlt">{_e(obj_th)}</th>'
        f'<th class="thlt">6 期趋势</th>{th_periods}</tr></thead>'
    )


def _section_tbody_overall(rows: list[dict]) -> str:
    body_rows = []
    for r in rows:
        spark_svg = _sparkline(
            r["spark6"],
            color=_SEV_COLOR.get(r["sev"], "var(--ink-mute)"),
            width=100, height=28, area=False, dots=False,
        )
        cells = "".join(
            f'<td class="{"tdcur" if PERIOD_ORDER[i] == YTD_LABEL else ""}">'
            f'<span class="num">{fmt_value(v, r["kind"])}</span></td>'
            for i, v in enumerate(r["spark6"])
        )
        body_rows.append(
            f'<tr><td class="tdlt obj-name muted">{_e(r["name"])}</td>'
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


def _section_tbody_dim(rows: list[dict], sec_id: str) -> str:
    body_rows = []
    for r in rows:
        spark_svg = _sparkline(
            r["values_by_metric"]["variable_cost_ratio"],
            color=_SEV_COLOR.get(r["sev"], "var(--ink-mute)"),
            width=100, height=28, area=False, dots=False,
        )
        data_attrs = []
        for col, vals in r["values_by_metric"].items():
            s = "/".join(
                "" if v is None or (isinstance(v, float) and math.isnan(v))
                else f"{float(v):.6g}"
                for v in vals
            )
            data_attrs.append(f'data-vals-{col.replace("_", "-")}="{s}"')
        for col, cls in r["sev_by_metric"].items():
            data_attrs.append(f'data-sev-{col.replace("_", "-")}="{cls}"')
        data_attrs.append(f'data-kinds="{_METRIC_KINDS}"')

        raw_v = _e(r.get("raw_value", r["name"]))
        disp_v = _e(r["name"])
        vcr_vals = r["values_by_metric"]["variable_cost_ratio"]
        cells = "".join(
            f'<td class="cell-{i}{" tdcur" if PERIOD_ORDER[i] == YTD_LABEL else ""}">'
            f'<span class="num">{fmt_value(v, "pct")}</span>'
            f'{_dot_html(r["sev"]) if PERIOD_ORDER[i] == YTD_LABEL else ""}'
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


def _render_section_detail(sec: dict, rows: list[dict], section_index: int,
                            default_open: bool = False) -> str:
    """渲染单个折叠段。"""
    red   = sum(1 for r in rows if r.get("sev") == "alert-red")
    org   = sum(1 for r in rows if r.get("sev") == "alert-yellow")
    blue  = sum(1 for r in rows if r.get("sev") == "alert-blue")
    green = sum(1 for r in rows if r.get("sev") == "alert-green")

    chips = []
    if red   > 0: chips.append(f'<span class="chip warn">{red} 危险</span>')
    if org   > 0: chips.append(f'<span class="chip mid">{org} 异常</span>')
    if blue  > 0: chips.append(f'<span class="chip ok">{blue} 健康</span>')
    if green > 0: chips.append(f'<span class="chip ok">{green} 优秀</span>')

    if sec["kind"] == "overall":
        finding_html = "当年起保 6 指标见下表，YTD vs 上年同期 / 滚动 12 月对比，标红项需要重点关注"
    elif rows:
        worst = rows[0]
        worst_ytd_vcr = (
            worst["values_by_metric"]["variable_cost_ratio"][-1]
            if worst.get("values_by_metric") else None
        )
        finding_html = (
            f'最差 <b>{_e(worst["name"])}</b> · YTD 变率 '
            f'<b>{fmt_value(worst_ytd_vcr, "pct")}</b>'
        )
    else:
        finding_html = "—"

    tabs_html = ""
    if sec["kind"] != "overall":
        tab_items = [
            f'<span class="tab{" on" if col == "variable_cost_ratio" else ""}" '
            f'data-metric="{col}" onclick="switchMetric(this, \'{sec["id"]}\')">'
            f'{_e(label)}</span>'
            for col, label, _, _ in METRIC_TABS
        ]
        tabs_html = (
            f'<div class="metric-tabs"><span class="lbl">切换指标</span>'
            f'{"".join(tab_items)}</div>'
        )

    tbody_html = (
        _section_tbody_overall(rows)
        if sec["kind"] == "overall"
        else _section_tbody_dim(rows, sec["id"])
    )

    # 下钻面板（非整体段）
    drill_html = ""
    if sec["kind"] != "overall":
        sid = sec["id"]
        drill_html = f"""
<div class="drill-panel" id="drp-{sid}">
  <div class="drill-bar">
    <span class="drill-crumb">下钻: <span class="drill-pname"></span></span>
    <div class="drill-dim-tabs" id="drp-dims-{sid}"></div>
    <div class="drill-metric-tabs" id="drp-mtabs-{sid}"></div>
    <button class="drill-close" onclick="closeDrill('{sid}')">关闭</button>
  </div>
  <div class="drill-wrap" id="drp-wrap-{sid}"></div>
</div>"""

    open_class = " open" if default_open else ""
    return f"""
<div id="det-{sec["id"]}" class="det-card{open_class}">
  <div class="det-head" onclick="this.parentElement.classList.toggle('open')">
    <span class="idx">{section_index:02d}</span>
    <span class="name">{_e(sec["label"])}</span>
    <span class="status">{"".join(chips)}</span>
    <span class="findings">{finding_html}</span>
    <span class="caret">▾</span>
  </div>
  <div class="det-body">
    {tabs_html}
    <table class="dtab">{_section_thead(sec)}{tbody_html}</table>
    {drill_html}
  </div>
</div>
"""


def _build_section_counts(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """每段 red/yellow 计数（供 rail 显示 chip）。"""
    counts: dict[str, dict[str, int]] = {}
    for sec in SECTION_DEFS:
        rows = _build_section_rows(df, sec)
        counts[sec["id"]] = {
            "red":    sum(1 for r in rows if r.get("sev") == "alert-red"),
            "yellow": sum(1 for r in rows if r.get("sev") == "alert-yellow"),
        }
    return counts


# ============== Drawer ==============

def _render_drawers(anomalies: list[Anomaly]) -> str:
    """HTML 预渲染 8 个抽屉（display:none，JS show/hide）。"""
    drawers = []
    for i, a in enumerate(anomalies):
        sev_color = {
            "alert-red": "var(--red)",
            "alert-yellow": "var(--orange)",
            "alert-green": "var(--green)",
            "alert-blue": "var(--navy)",
        }.get(a.sev, "var(--ink-mute)")
        spark_svg = _sparkline(a.spark6, color=sev_color, width=490, height=140, area=True, dots=True)
        delta_class = "red" if a.delta_vs_yoy > 0 else "gn"

        # 警戒线从 _TH 取（模块级常量，单一事实源 = alerts.TH）
        th_warn = _TH.get(a.alert_key, (0, 0, 0))[1]
        diff_to_warn = a.value - th_warn

        # 6 期 sparkline 下方的数值标签
        period_labels_html = "".join(
            f'<span style="text-align:center;">{_e(p)}<br>'
            f'<b class="num" style="color:{(sev_color if i==5 else "var(--ink-soft)")};">'
            f'{fmt_value(a.spark6[i], "pct")}</b></span>'
            for i, p in enumerate(PERIOD_ORDER)
        )

        drawers.append(f"""
<aside class="drawer" id="drawer-{i}">
  <div class="drawer-head">
    <div class="crumb">{_e(a.metric_label)} · YTD · No.{i+1:02d}</div>
    <h2>{_e(a.dim_label)}</h2>
    <div style="margin-top:6px; color:var(--ink-mute); font-size:13px;">{_e(a.note)}</div>
    <button class="close" onclick="closeDrawer()">×</button>
  </div>
  <div class="drawer-body">
    <div class="stat-row">
      <div class="stat-cell">
        <div class="lbl">YTD · {_e(a.metric_label)}</div>
        <div class="v num" style="color:{sev_color};">{fmt_value(a.value, "pct")}</div>
        <div class="d {delta_class}">{fmt_delta(a.delta_vs_yoy, "pct")}</div>
      </div>
      <div class="stat-cell">
        <div class="lbl">警戒线（异常起点）</div>
        <div class="v num">{th_warn:.1f}%</div>
        <div class="d {('red' if diff_to_warn > 0 else 'gn')}">{('超 +' if diff_to_warn>0 else '差 ')}{diff_to_warn:.1f} PP</div>
      </div>
      <div class="stat-cell">
        <div class="lbl">保费贡献</div>
        <div class="v num">{a.premium_share:.1f}%</div>
        <div class="d">{('影响整体显著' if a.premium_share > 5 else '影响整体有限')}</div>
      </div>
    </div>

    <h4>6 期趋势</h4>
    <div style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:14px 16px;">
      {spark_svg}
      <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:11px; color:var(--ink-mute);">
        {period_labels_html}
      </div>
    </div>

    <h4>归因路径 · 建议</h4>
    <ul style="padding-left:18px; font-size:13px; line-height:1.75; color:var(--ink-soft);">
      <li>{_e(a.metric_label)} YTD = {fmt_value(a.value, "pct")}，亮灯 {a.sev_label}</li>
      <li>保费贡献 {a.premium_share:.1f}% · {("规模型异常，须优先处理" if a.premium_share > 10 else "结构型异常，注意成因分析")}</li>
      <li>近 6 期趋势：{ "持续恶化" if (a.spark6[-1] is not None and a.spark6[0] is not None and a.spark6[-1] > a.spark6[0]) else "近期波动" }</li>
    </ul>

    <a class="deep-link" href="?focus={_e(a.dim_value)}" style="text-decoration:none;">
      <div class="l">在<b> 超表 </b>查看 {_e(a.dim_display)} 全字段明细 →</div>
      <span class="arr">→</span>
    </a>
  </div>
</aside>
""")
    return f'<div class="scrim" id="scrim" onclick="closeDrawer()"></div>{"".join(drawers)}'


# ============== JS 互动 ==============

JS_INTERACTIONS = r"""
<script>
// ── 共用工具 ──
function escapeHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// ===== 抽屉 =====
let _openDrawer = null;
function openDrawer(idx) {
  if (_openDrawer !== null) closeDrawer();
  const drawer = document.getElementById('drawer-' + idx);
  const scrim = document.getElementById('scrim');
  if (drawer) drawer.classList.add('on');
  if (scrim) scrim.classList.add('on');
  _openDrawer = idx;
  document.body.style.overflow = 'hidden';
}
function closeDrawer() {
  if (_openDrawer === null) return;
  const drawer = document.getElementById('drawer-' + _openDrawer);
  const scrim = document.getElementById('scrim');
  if (drawer) drawer.classList.remove('on');
  if (scrim) scrim.classList.remove('on');
  _openDrawer = null;
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

// ===== 切换指标 tab（折叠段内）=====
function switchMetric(tabEl, sectionId) {
  // tabs UI 切换
  const tabsContainer = tabEl.parentElement;
  tabsContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  tabEl.classList.add('on');
  const newMetric = tabEl.dataset.metric;

  // 取当前段所有数据行
  const table = document.querySelector('#det-' + sectionId + ' table.dtab');
  if (!table) return;
  const rows = table.querySelectorAll('tbody tr');
  rows.forEach(row => {
    const valsStr = row.dataset['vals' + capitalize(newMetric)];
    if (!valsStr) return;
    const values = valsStr.split('/').map(s => s === '' ? null : parseFloat(s));
    const kindsAttr = (row.dataset.kinds || '').split('/');
    const tabsList = Array.from(tabsContainer.querySelectorAll('.tab')).map(t => t.dataset.metric);
    const metricIdx = tabsList.indexOf(newMetric);
    const kind = kindsAttr[metricIdx] || 'pct';
    const sev = row.dataset['sev' + capitalize(newMetric)] || '';

    // 重绘 cell 文本
    const cells = row.querySelectorAll('td.cell-0, td.cell-1, td.cell-2, td.cell-3, td.cell-4, td.cell-5');
    cells.forEach((cell, i) => {
      const v = values[i];
      cell.querySelector('.num').textContent = fmtValue(v, kind);
    });
    // 重绘 trend sparkline
    const trendCell = row.querySelector('.trend-cell');
    if (trendCell) {
      const color = sevToColor(sev);
      trendCell.innerHTML = miniSparkline(values, color);
    }
  });
}
function capitalize(s) { return s.split('_').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(''); }
function fmtValue(v, kind) {
  if (v === null || isNaN(v)) return '—';
  if (kind === 'pct')   return v.toFixed(1) + '%';
  if (kind === 'coef')  return v.toFixed(3);
  if (kind === 'money') return '¥' + Math.round(v).toLocaleString();
  if (kind === 'wan')   return Math.round(v/10000).toLocaleString();
  return v.toFixed(2);
}
function sevToColor(sev) {
  return {'alert-red':'var(--red)', 'alert-yellow':'var(--orange)', 'alert-green':'var(--green)', 'alert-blue':'var(--navy)'}[sev] || 'var(--ink-mute)';
}
function miniSparkline(values, color) {
  const clean = values.map((v,i)=>({v,i})).filter(o=>o.v !== null && !isNaN(o.v));
  if (clean.length < 2) return '<span style="color:var(--ink-light);">—</span>';
  const ys = clean.map(o=>o.v);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const range = (ymax - ymin) || 1;
  const w = 100, h = 28, pad = 4, n = values.length - 1;
  const pts = clean.map(o => {
    const x = pad + (o.i/n)*(w-2*pad);
    const y = (h-pad) - ((o.v-ymin)/range)*(h-2*pad);
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  return '<svg width="'+w+'" height="'+h+'"><polyline points="'+pts+'" stroke="'+color+'" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}

// ===== ?focus= URL 路由（V4 超表用，V1 接受参数但不强制行为）=====
const urlParams = new URLSearchParams(window.location.search);
const focusParam = urlParams.get('focus');
if (focusParam) {
  console.log('focus param received:', focusParam);
}

// ===== 跨维度下钻 =====
// DD 由 Python 渲染时注入：const DD = {...};
// 格式：DD[key] = [[dispName, sevInt, [vcr×6], [lr×6], [freq×6], [avg×6], [coef×6]], ...]
const DRILL_DIMS = {
  customer: [["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  branch:   [["customer","客户类别"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  insurance:[["customer","客户类别"],["branch","三级机构"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  combo:    [["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  energy:   [["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["newused","新旧车"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  newused:  [["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["transfer","过户"],["renewal","续保"],["telesales","电销"]],
  transfer: [["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["renewal","续保"],["telesales","电销"]],
  renewal:  [["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["telesales","电销"]],
  telesales:[["customer","客户类别"],["branch","三级机构"],["insurance","险类"],["combo","险别组合"],["energy","能源"],["newused","新旧车"],["transfer","过户"],["renewal","续保"]]
};
// DD row 中各指标 series 的索引（索引 0=dispName, 1=sevInt, 2=vcr, 3=lr, 4=freq, 5=avg, 6=coef）
const DRILL_SERIES_IDX = {variable_cost_ratio:2, earned_claim_ratio:3, earned_loss_frequency:4, avg_claim_amount:5, weighted_pricing_factor:6};
const DRILL_METRIC_TABS_DEF = [
  ["variable_cost_ratio","变率","pct"],
  ["earned_claim_ratio","赔付率","pct"],
  ["earned_loss_frequency","出险率","pct"],
  ["avg_claim_amount","案均","money"],
  ["weighted_pricing_factor","自主系数","coef"]
];
const DRILL_PERIOD_LABELS = ['36月','24月','上年','12月','6月','本年'];
const DRILL_YTD_IDX = 5;
const DRILL_SEV_COLORS = ['var(--ink-mute)','var(--green)','var(--navy)','var(--orange)','var(--red)'];

// 行名点击→下钻
document.addEventListener('click', function(e){
  const el = e.target.closest('.drill-trigger');
  if (!el) return;
  const secId = el.dataset.sec, rawVal = el.dataset.rawval, dispName = el.dataset.disp;
  if (!secId) return;
  openDrill(secId, rawVal, dispName, el);
});

function openDrill(secId, rawVal, dispName, triggerEl) {
  const panel = document.getElementById('drp-' + secId);
  if (!panel) return;
  // 高亮当前行
  const table = triggerEl.closest('table');
  if (table) {
    table.querySelectorAll('tr.drill-active').forEach(r=>r.classList.remove('drill-active'));
    triggerEl.closest('tr').classList.add('drill-active');
  }
  panel.dataset.rawval = rawVal;
  panel.querySelector('.drill-pname').textContent = dispName;

  // 构建维度 tabs
  const dims = DRILL_DIMS[secId] || [];
  document.getElementById('drp-dims-' + secId).innerHTML = dims.map((d,i) =>
    `<span class="drill-dim-tab${i===0?' on':''}" data-dim="${d[0]}" onclick="selectDrillDim('${secId}',this)">${escapeHtml(d[1])}</span>`
  ).join('');

  // 构建指标 tabs
  document.getElementById('drp-mtabs-' + secId).innerHTML = DRILL_METRIC_TABS_DEF.map((m,i) =>
    `<span class="drill-metric-tab${i===0?' on':''}" data-midx="${i}" onclick="selectDrillMetric('${secId}',this)">${escapeHtml(m[1])}</span>`
  ).join('');

  panel.style.display = 'block';
  if (dims.length) renderDrillTable(secId, rawVal, dims[0][0], 0);
  panel.scrollIntoView({block:'nearest', behavior:'smooth'});
}

function closeDrill(secId) {
  const panel = document.getElementById('drp-' + secId);
  if (panel) panel.style.display = 'none';
  const det = document.getElementById('det-' + secId);
  if (det) det.querySelectorAll('tr.drill-active').forEach(r=>r.classList.remove('drill-active'));
}

function selectDrillDim(secId, tabEl) {
  tabEl.parentElement.querySelectorAll('.drill-dim-tab').forEach(t=>t.classList.remove('on'));
  tabEl.classList.add('on');
  const panel = document.getElementById('drp-' + secId);
  const rawVal = panel.dataset.rawval;
  const mTab = document.querySelector('#drp-mtabs-' + secId + ' .drill-metric-tab.on');
  renderDrillTable(secId, rawVal, tabEl.dataset.dim, mTab ? parseInt(mTab.dataset.midx) : 0);
}

function selectDrillMetric(secId, tabEl) {
  tabEl.parentElement.querySelectorAll('.drill-metric-tab').forEach(t=>t.classList.remove('on'));
  tabEl.classList.add('on');
  const panel = document.getElementById('drp-' + secId);
  const rawVal = panel.dataset.rawval;
  const dimTab = document.querySelector('#drp-dims-' + secId + ' .drill-dim-tab.on');
  renderDrillTable(secId, rawVal, dimTab ? dimTab.dataset.dim : '', parseInt(tabEl.dataset.midx));
}

function renderDrillTable(secId, rawVal, dimId, metricIdx) {
  const key = secId + '|||' + rawVal + '|||' + dimId;
  const rows = (typeof DD !== 'undefined' && DD[key]) ? DD[key] : [];
  const wrap = document.getElementById('drp-wrap-' + secId);
  if (!wrap) return;
  if (!rows.length) {
    wrap.innerHTML = '<p style="padding:8px 0;color:var(--ink-mute);font-size:12px;">该维度无交叉数据</p>';
    return;
  }
  const [metricCol, , kind] = DRILL_METRIC_TABS_DEF[metricIdx] || DRILL_METRIC_TABS_DEF[0];
  const sIdx = DRILL_SERIES_IDX[metricCol] || 2;

  let head = `<thead><tr><th class="thlt">对象</th><th class="thlt">趋势</th>${
    DRILL_PERIOD_LABELS.map((pl,i)=>`<th class="${i===DRILL_YTD_IDX?'thcur':''}">${pl}</th>`).join('')
  }</tr></thead>`;

  let body = '<tbody>';
  rows.forEach(r => {
    const name=r[0], sev=r[1], series=(r[sIdx]||r[2]||[]);
    const color = DRILL_SEV_COLORS[sev] || 'var(--ink-mute)';
    const spark = miniSparkline(series, color);
    const dot = sev>=3 ? `<span style="display:inline-block;width:6px;height:6px;border-radius:50%;margin-left:4px;background:${color};"></span>` : '';
    const cells = series.map((v,i) =>
      `<td class="${i===DRILL_YTD_IDX?'tdcur':''}">${fmtValue(v,kind)}${i===DRILL_YTD_IDX?dot:''}</td>`
    ).join('');
    body += `<tr><td class="tdlt obj-name">${escapeHtml(name)}</td><td class="tdlt">${spark}</td>${cells}</tr>`;
  });
  body += '</tbody>';
  wrap.innerHTML = `<table class="dtab drill-tbl">${head}${body}</table>`;
}
</script>
"""


# ============== V1 主入口 ==============

V1_PAGE_CSS = """
/* topbar */
.topbar{
  position: sticky; top: 0; z-index: 50;
  background: var(--paper);
  border-bottom: 1px solid var(--line);
  padding: 14px 32px;
  display: flex; align-items: center; gap: 18px;
}
.topbar .brand{ display: flex; align-items: center; gap: 8px; color: var(--ink); font-weight: 600; }
.topbar .brand-mark{
  width: 24px; height: 24px; border-radius: 5px;
  background: var(--navy);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 13px; font-weight: 700; letter-spacing: -.5px;
}
.topbar h1{
  font-family:'Noto Serif SC',serif;
  font-size: 18px; font-weight: 500; margin: 0;
  letter-spacing: 0.02em;
}
.topbar .date-pill{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border: 1px solid var(--line);
  background: var(--surface);
  border-radius: var(--radius); font-size: 13px; color: var(--ink-soft);
}
.topbar .meta{ color: var(--ink-mute); font-size: 13px; }
.topbar .meta b{ color: var(--ink-soft); font-weight: 500; }

/* shell */
.shell{ display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }
.rail{
  position: sticky; top: 53px; align-self: start;
  height: calc(100vh - 53px);
  padding: 20px 0;
  border-right: 1px solid var(--line);
  overflow-y: auto;
  background: var(--paper);
}
.rail h6{
  font-size: 11px; color: var(--ink-mute); text-transform: uppercase;
  letter-spacing: 1.5px; font-weight: 500; margin: 0 0 8px 26px;
}
.rail ul{ list-style: none; padding: 0; margin: 0; }
.rail li{
  padding: 7px 26px; font-size: 13.5px; color: var(--ink-soft); cursor: pointer;
  border-left: 2px solid transparent;
  display: flex; align-items: center; justify-content: space-between;
}
.rail li:hover{ color: var(--ink); background: var(--paper-soft); }
.rail li .alert{
  font-size: 11px; padding: 1px 6px; border-radius: 8px;
  background: var(--red-soft); color: var(--red); font-weight: 500;
}
.rail li .alert.org{ background: var(--orange-soft); color: var(--orange); }

.main{ padding: 24px 32px 60px; max-width: 1240px; }
.section-tag{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--ink-mute);
  text-transform: uppercase; letter-spacing: 1.5px; font-weight: 500;
  margin-bottom: 8px;
}
.section-tag .bar{ width: 18px; height: 1.5px; background: var(--ink-mute); }
.h-section{
  font-family:'Noto Serif SC',serif;
  font-size: 22px; font-weight: 500; margin: 0 0 16px;
}

/* KPI */
.kpi-grid{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi{
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px;
  position: relative; overflow: hidden;
}
.kpi .label{ font-size: 12px; color: var(--ink-mute); margin-bottom: 6px; display:flex; align-items:center; gap:6px; }
.kpi .value-row{ display: flex; align-items: baseline; gap: 8px; }
.kpi .value{ font-family:'Noto Serif SC',serif; font-size: 30px; font-weight: 500; line-height: 1; color: var(--ink); font-variant-numeric: tabular-nums; }
.kpi .delta{ font-size: 12px; padding: 2px 7px; border-radius: 3px; font-weight: 500; background: var(--paper-soft); color: var(--ink-soft); }
.kpi .delta.red{ background: var(--red-soft); color: var(--red); }
.kpi .delta.org{ background: var(--orange-soft); color: var(--orange); }
.kpi .delta.gn{  background: var(--green-soft); color: var(--green); }
.kpi .sub{ font-size: 11.5px; color: var(--ink-mute); margin-top: 6px; }
.kpi .spark{ margin-top: 10px; }
.kpi.alert::before{ content:''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--orange); }
.kpi.alert.red::before{ background: var(--red); }

/* hero alert */
.alert-banner{
  background: var(--surface);
  border: 1px solid var(--red-line);
  border-left: 3px solid var(--red);
  border-radius: var(--radius);
  padding: 14px 18px;
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 28px;
}
.alert-icon{
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--red-soft); color: var(--red);
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 14px; flex-shrink: 0;
}
.alert-banner .msg{ font-size: 14px; color: var(--ink); flex: 1; }
.alert-banner .msg b{ color: var(--red); font-weight: 600; }
.alert-banner .msg .sub{ display: block; font-size: 12.5px; color: var(--ink-mute); margin-top: 2px; }
.alert-banner .cta{
  padding: 7px 14px; background: var(--ink); color: var(--paper);
  border: none; border-radius: var(--radius-sm);
  font-size: 13px; cursor: pointer;
}
.alert-banner .cta:hover{ background: var(--navy-deep); }

/* anomaly card */
.anom-grid{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px; }
.anom-card{
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px;
  cursor: pointer; position: relative;
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

.metric-tabs{ display: flex; align-items: center; gap: 4px; margin-bottom: 10px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.metric-tabs .lbl{ font-size: 11.5px; color: var(--ink-mute); margin-right: 6px; }
.metric-tabs .tab{ padding: 4px 10px; font-size: 12.5px; color: var(--ink-soft); cursor: pointer; border-radius: var(--radius-sm); }
.metric-tabs .tab.on{ background: var(--surface-soft); color: var(--ink); font-weight: 500; }
.metric-tabs .tab:hover:not(.on){ color: var(--ink); }

.dtab{ width: 100%; border-collapse: collapse; font-size: 13px; }
.dtab th, .dtab td{ padding: 8px 10px; text-align: right; }
.dtab th{ font-weight: 500; font-size: 11.5px; color: var(--ink-mute); border-bottom: 1px solid var(--line); }
.dtab th.thlt, .dtab td.tdlt{ text-align: left; }
.dtab th.thcur{ background: var(--navy); color: var(--paper); font-weight: 600; }
.dtab td.tdcur{ background: var(--navy-soft); color: var(--ink); font-weight: 600; }
.dtab tbody tr{ border-bottom: 1px solid var(--line-soft); }
.dtab tbody tr:hover{ background: var(--surface-soft); }
.dtab .obj-name{ color: var(--navy); font-weight: 500; }

/* drawer */
.scrim{
  position: fixed; inset: 0; background: rgba(20,16,12,0.30);
  opacity: 0; pointer-events: none; transition: opacity .2s; z-index: 80;
}
.scrim.on{ opacity: 1; pointer-events: auto; }
.drawer{
  position: fixed; right: -560px; top: 0; bottom: 0; width: 540px;
  background: var(--paper); border-left: 1px solid var(--line-strong);
  box-shadow: var(--shadow-pop);
  z-index: 90; transition: right .25s cubic-bezier(.2,.7,.3,1);
  overflow-y: auto;
}
.drawer.on{ right: 0; }
.drawer-head{
  padding: 18px 22px 12px;
  border-bottom: 1px solid var(--line);
  position: sticky; top: 0; background: var(--paper); z-index: 2;
}
.drawer-head .crumb{ font-size: 11px; color: var(--ink-mute); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; }
.drawer-head h2{ font-family:'Noto Serif SC',serif; margin: 0; font-size: 24px; font-weight: 500; }
.drawer-head .close{
  position: absolute; right: 16px; top: 16px;
  width: 28px; height: 28px; border-radius: var(--radius-sm);
  background: transparent; border: none; cursor: pointer;
  font-size: 18px; color: var(--ink-soft);
}
.drawer-body{ padding: 18px 22px; }
.stat-row{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.stat-cell{
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 10px 12px;
}
.stat-cell .lbl{ font-size: 11.5px; color: var(--ink-mute); margin-bottom: 4px; }
.stat-cell .v{ font-family:'Noto Serif SC',serif; font-size: 22px; font-weight: 500; }
.stat-cell .d{ font-size: 11.5px; margin-top: 2px; }
.stat-cell .d.red{ color: var(--red); }
.stat-cell .d.gn{ color: var(--green); }
.drawer-body h4{ font-size: 13px; color: var(--ink-mute); font-weight: 500; margin: 18px 0 8px; text-transform: uppercase; letter-spacing: 1px; }
.drawer-body .deep-link{
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; margin-top: 16px;
  border: 1px solid var(--navy-line); background: var(--navy-soft); border-radius: var(--radius);
}
.drawer-body .deep-link:hover{ background: rgba(28,72,120,0.13); }
.drawer-body .deep-link .l{ font-size: 13px; color: var(--ink); }
.drawer-body .deep-link .l b{ color: var(--navy); }
.drawer-body .deep-link .arr{ color: var(--navy); font-size: 16px; }

.footnote{
  margin-top: 40px; padding: 16px 0;
  border-top: 1px solid var(--line);
  color: var(--ink-mute); font-size: 11.5px;
  display: flex; justify-content: space-between;
}

/* ── 行名下钻触发 ── */
.drill-trigger{ cursor:pointer; }
.drill-trigger:hover{ text-decoration:underline; text-decoration-style:dotted; color:var(--navy); }
tr.drill-active td.drill-trigger{ color:var(--navy); font-weight:600; }

/* ── 下钻面板 ── */
.drill-panel{
  display:none; margin-top:10px;
  border:1px solid var(--navy-line); border-radius:var(--radius);
  overflow:hidden;
}
.drill-bar{
  display:flex; align-items:center; gap:8px; flex-wrap:wrap;
  padding:8px 12px; background:rgba(28,72,120,0.06);
  border-bottom:1px solid var(--navy-line);
}
.drill-crumb{ font-size:12px; color:var(--navy); white-space:nowrap; }
.drill-crumb span{ font-weight:600; color:var(--ink); }
.drill-dim-tabs{ display:flex; gap:4px; flex-wrap:wrap; flex:1; }
.drill-dim-tab{
  padding:3px 9px; border-radius:var(--radius-sm);
  font-size:12px; color:var(--navy); cursor:pointer;
  border:1px solid var(--navy-line); background:transparent;
}
.drill-dim-tab.on{ background:var(--navy); color:var(--paper); border-color:var(--navy); }
.drill-metric-tabs{ display:flex; gap:3px; }
.drill-metric-tab{ padding:3px 8px; border-radius:var(--radius-sm); font-size:12px; color:var(--ink-soft); cursor:pointer; }
.drill-metric-tab.on{ background:var(--surface); color:var(--ink); font-weight:500; }
.drill-close{
  margin-left:auto; padding:2px 10px;
  background:transparent; border:1px solid var(--line);
  border-radius:var(--radius-sm); cursor:pointer;
  font-size:12px; color:var(--ink-soft); white-space:nowrap;
}
.drill-wrap{ padding:10px 14px; background:var(--paper); }
.drill-tbl{ width:100%; border-collapse:collapse; font-size:12.5px; }
.drill-tbl th,.drill-tbl td{ padding:6px 8px; text-align:right; }
.drill-tbl th{ font-weight:500; font-size:11px; color:var(--ink-mute); border-bottom:1px solid var(--line); }
.drill-tbl th.thlt,.drill-tbl td.tdlt{ text-align:left; }
.drill-tbl th.thcur{ background:var(--navy); color:var(--paper); }
.drill-tbl td.tdcur{ background:var(--navy-soft); font-weight:600; }
.drill-tbl tbody tr{ border-bottom:1px solid var(--line-soft); }
.drill-tbl tbody tr:hover{ background:var(--surface-soft); }
.drill-tbl .obj-name{ color:var(--ink); font-weight:500; }
"""


def render_v1_page(df: pd.DataFrame, cutoff: date,
                    anomalies: Optional[list[Anomaly]] = None) -> str:
    """V1 驾驶舱主入口。

    Args:
      df: derive_metrics 之后的完整 DataFrame
      cutoff: 截止日
      anomalies: Top n 异常列表（不传则自动 compute_top_anomalies n=8）

    Returns:
      完整 HTML 字符串
    """
    if anomalies is None:
        anomalies = compute_top_anomalies(df, n=8)

    overall_meta = _build_overall_meta(df)
    overall_ytd = _slice_overall(df)
    overall_ytd_row = overall_ytd[overall_ytd["period_label"] == YTD_LABEL]
    if not overall_ytd_row.empty:
        ytd_vcr = _safe_float(overall_ytd_row.iloc[0]["variable_cost_ratio"])
        ytd_lr  = _safe_float(overall_ytd_row.iloc[0]["earned_claim_ratio"])
        overall_summary = (
            f'整体 YTD 变率 {fmt_value(ytd_vcr, "pct")}、赔付率 {fmt_value(ytd_lr, "pct")}。'
        )
    else:
        overall_summary = ""

    section_counts = _build_section_counts(df)
    kpi_cards = _build_kpi_data(df)

    # 各段 HTML
    sections_html_list = []
    for i, sec in enumerate(SECTION_DEFS, 1):
        rows = _build_section_rows(df, sec)
        sec_html = _render_section_detail(sec, rows, i, default_open=(i == 1))
        sections_html_list.append(sec_html)

    drawers_html = _render_drawers(anomalies)

    # 跨维度下钻数据
    dd_json = json.dumps(build_drilldown_data(df), ensure_ascii=False, separators=(",", ":"))

    title = f"多期车险保单品质对比 · 诊断驾驶舱 · {cutoff.isoformat()}"
    full_css = BASE_CSS + DARK_CSS + THEME_TOGGLE_CSS + V1_PAGE_CSS

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{_e(title)}</title>
<meta name="viewport" content="width=1440, initial-scale=1" />
{FONT_LINKS}
<style>{full_css}</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{_render_topbar(cutoff, overall_meta)}
<div class="shell">
  {_render_rail(section_counts, len(anomalies))}
  <main class="main">
    <div id="top"></div>
    {_render_hero_alert(anomalies, overall_summary)}
    <div class="section-tag"><span class="bar"></span>整体状态 · 5 KPI</div>
    {_render_kpi_strip(kpi_cards)}
    {_render_anomaly_grid(anomalies)}
    <div id="details"></div>
    <div class="section-tag" style="margin-top:8px;"><span class="bar"></span>分维度明细 · 10 段</div>
    <h2 class="h-section">从概览下钻</h2>
    {"".join(sections_html_list)}
    <div class="footnote">
      <span>口径 · 整体保单维度统计；警戒线：变率 {_TH['variable_cost_ratio_pct'][1]:g}% / 赔付率 {_TH['earned_loss_ratio_pct'][1]:g}% / 出险率 {_TH['earned_loss_freq_pct'][1]:g}%（项目分公司经营口径）</span>
      <span>数据更新 · {cutoff.isoformat()} · 数据治理部</span>
    </div>
  </main>
</div>
{drawers_html}
<script>const DD={dd_json};{THEME_TOGGLE_JS}</script>
{JS_INTERACTIONS}
</body>
</html>
"""
