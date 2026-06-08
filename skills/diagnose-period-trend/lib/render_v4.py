"""V4 · 超表（分析师视角）渲染器。

设计来源：/tmp/design_pkg/untitled/project/V4 超表.html + v4-table-app.jsx
本项目化要点：
  - Python SSR：数据嵌入 JSON，JS 渲染表格 + 交互（无 React/Babel）
  - 左 3 列冻结：# / 对象 / 6 期趋势 sparkline
  - 5 指标组 × 6 期列 + Δ 列，默认展示 变率 + 赔付率
  - 对比口径切换：vs 上年同期 / vs 滚动12月 / vs 警戒线
  - ?focus=<keyword> URL 参数预填搜索框
  - 行点击展开全指标快照（5 张 ex-card + sparkline）
  - 底部粘性状态栏：红/黄/绿/灰数量
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
    from .anomalies import (AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER, YTD_LABEL, YOY_LABEL,
                            build_drilldown_data, DRILL_SEC_LIST, _SEC_FIELD)
except ImportError:
    from anomalies import (AUX_DIM_LABELS, AUX_VALUE_LABELS, PERIOD_ORDER, YTD_LABEL, YOY_LABEL,  # type: ignore[no-redef]
                           build_drilldown_data, DRILL_SEC_LIST, _SEC_FIELD)

# 主题资源下沉到基座（ADR-002）
from dhr_lib.themes_v2 import (
    FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
    THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn,
)


def _get_th() -> dict:
    if hasattr(dhr_lib, "TH"):
        return dhr_lib.TH
    import importlib
    return importlib.import_module("dhr_lib.alerts").TH


_TH = _get_th()

# ── 5 指标定义（id, label, col, kind, th-css-class, warn-key） ──────────────
METRIC_DEFS = [
    ("vcr",  "变率",     "variable_cost_ratio",    "pct",   "g-var", "variable_cost_ratio_pct"),
    ("lr",   "赔付率",   "earned_claim_ratio",      "pct",   "g-pay", "earned_loss_ratio_pct"),
    ("freq", "出险率",   "earned_loss_frequency",   "pct",   "g-clm", "earned_loss_freq_pct"),
    ("avg",  "案均",     "avg_claim_amount",        "money", "g-amt", None),
    ("coef", "自主系数", "weighted_pricing_factor", "coef",  "g-pre", None),
]

# ── 6 期顺序（与 PERIOD_ORDER 同步）──────────────────────────────────────────
PERIOD_HEADERS = [
    ("滚动36个月", "36月"),
    ("滚动24个月", "24月"),
    ("上年同期",   "上年"),
    ("滚动12个月", "12月"),
    ("滚动6个月",  "6月"),
    ("当年起保",   "本年"),  # idx=5, YTD
]
YTD_IDX = 5
YOY_IDX = 2
M12_IDX = 3

# ── 10 维度组 ─────────────────────────────────────────────────────────────────
GROUPS = [
    {"group": "整体",    "kind": "overall", "field": None},
    {"group": "客户类别","kind": "cat",     "field": "customer_category"},
    {"group": "三级机构","kind": "org",     "field": "org_level_3"},
    {"group": "险类",    "kind": "aux",     "field": "insurance_type"},
    {"group": "险别组合","kind": "aux",     "field": "coverage_combination"},
    {"group": "能源类型","kind": "aux",     "field": "is_nev"},
    {"group": "新旧车",  "kind": "aux",     "field": "is_new_car"},
    {"group": "是否过户","kind": "aux",     "field": "is_transfer"},
    {"group": "是否续保","kind": "aux",     "field": "is_renewal"},
    {"group": "是否电销","kind": "aux",     "field": "is_telemarketing"},
]


# ===== 数据切片（与 render_v1.py 同族，不跨模块引用内部函数） ================

AUX_FIELDS = list(AUX_DIM_LABELS.keys())


def _safe_f(v) -> Optional[float]:
    if v is None: return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _all_aux_mask(df: pd.DataFrame, exclude: Optional[str] = None) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for f in AUX_FIELDS:
        if f == exclude: continue
        mask &= (df[f] == "__ALL__")
    return mask


def _slice_overall(df: pd.DataFrame) -> pd.DataFrame:
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
    return df[is_all_cat & is_all_org & is_active & is_real & _all_aux_mask(df, exclude=field)].copy()


def _pv(cohort: pd.DataFrame, period: str, col: str) -> Optional[float]:
    sub = cohort[cohort["period_label"] == period]
    if sub.empty: return None
    return _safe_f(sub.iloc[0][col])


# ===== 构建行数据 =============================================================

def _build_rows(df: pd.DataFrame) -> tuple[list[dict], dict]:
    """返回 (rows, meta)。
    rows 是 JSON 可序列化的 list[dict]。
    meta 含 policies / premium / categories 供 topbar 显示。
    """
    overall_df = _slice_overall(df)
    ytd_row = overall_df[overall_df["period_label"] == YTD_LABEL]
    overall_prem = _safe_f(ytd_row.iloc[0]["premium_sum"]) if not ytd_row.empty else 0.0
    overall_prem = overall_prem or 0.0
    n_policy_overall = _safe_f(ytd_row.iloc[0]["policy_count"]) if not ytd_row.empty else 0
    meta = {
        "policies": f"{(n_policy_overall or 0)/10000:.2f}",
        "premium": f"{(overall_prem)/10000:,.0f}",
        "categories": str(_slice_by_cat(df)[_slice_by_cat(df)["period_label"] == YTD_LABEL]["customer_category"].nunique()),
    }

    # 警戒线值（供 vs 警戒线 Δ 模式）
    warn_vals = {
        m_id: (_TH.get(wk, (0, 0, 0))[1] if wk else None)
        for m_id, _, _, _, _, wk in METRIC_DEFS
    }

    rows: list[dict] = []

    for g in GROUPS:
        gkind = g["kind"]
        gfield = g["field"]
        glabel = g["group"]

        # cohort_list: [(raw_val, display_name, cohort_df)]
        if gkind == "overall":
            cohort_list = [("__overall__", "四川", overall_df)]
        elif gkind == "cat":
            cat_df = _slice_by_cat(df)
            cohort_list = [
                (v, short_category_label(v), cat_df[cat_df["customer_category"] == v])
                for v in sorted(cat_df["customer_category"].unique()) if v != "__ALL__"
            ]
        elif gkind == "org":
            org_df = _slice_by_org(df)
            cohort_list = [
                (v, v, org_df[org_df["org_level_3"] == v])
                for v in sorted(org_df["org_level_3"].unique()) if v != "__ALL__"
            ]
        else:  # aux
            aux_df = _slice_by_aux(df, gfield)
            val_labels = AUX_VALUE_LABELS.get(gfield, {})
            cohort_list = [
                (str(v), val_labels.get(str(v), str(v)), aux_df[aux_df[gfield] == v])
                for v in sorted(aux_df[gfield].unique())
                if v not in ("__ALL__", "__NULL__")
            ]

        for raw_val_str, name, cohort in cohort_list:
            ytd_c = cohort[cohort["period_label"] == YTD_LABEL]
            n_pol = int(_safe_f(ytd_c.iloc[0]["policy_count"]) or 0) if not ytd_c.empty else 0
            prem_ytd = _safe_f(ytd_c.iloc[0]["premium_sum"]) if not ytd_c.empty else None
            prem_share = round(prem_ytd / overall_prem * 100, 1) if (prem_ytd and overall_prem > 0) else None

            metrics: dict[str, list] = {}
            for m_id, _, m_col, _, _, _ in METRIC_DEFS:
                series = []
                for p_key, _ in PERIOD_HEADERS:
                    v = _pv(cohort, p_key, m_col)
                    series.append(round(v, 3) if v is not None else None)
                metrics[m_id] = series

            # YTD 变率的亮灯 → row sev
            vcr_ytd = metrics["vcr"][YTD_IDX]
            sev_cls, _ = light("variable_cost_ratio_pct", vcr_ytd, n_pol) if vcr_ytd is not None else ("alert-gray", "")
            sev_short = sev_cls.replace("alert-", "")  # red/yellow/blue/green/gray

            # 预计算 3 种 Δ 模式
            deltas: dict[str, dict] = {}
            for m_id, _, _, _, _, wk in METRIC_DEFS:
                ytd_v = metrics[m_id][YTD_IDX]
                yoy_v = metrics[m_id][YOY_IDX]
                m12_v = metrics[m_id][M12_IDX]
                warn_v = warn_vals.get(m_id)
                deltas[m_id] = {
                    "yoy": round(ytd_v - yoy_v, 2) if (ytd_v is not None and yoy_v is not None) else None,
                    "m12": round(ytd_v - m12_v, 2) if (ytd_v is not None and m12_v is not None) else None,
                    "warn": round(ytd_v - warn_v, 2) if (ytd_v is not None and warn_v is not None) else None,
                }

            rows.append({
                "group": glabel,
                "name": name,
                "key": f"{gkind}_{name}",
                "raw_val": raw_val_str,
                "sev": sev_short,
                "prem": prem_share,
                "metrics": metrics,
                "deltas": deltas,
                "n_pol": n_pol,
            })

    return rows, meta


# ===== CSS (V4-specific supplement) ==========================================

V4_CSS = """
/* ── topbar ─────────────────────────────── */
.topbar{position:sticky;top:0;z-index:60;background:var(--paper);border-bottom:1px solid var(--line);padding:10px 24px;display:flex;align-items:center;gap:12px;flex-wrap:nowrap;}
.brand{display:flex;align-items:center;gap:7px;}
.brand-mark{width:22px;height:22px;border-radius:4px;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;}
.topbar h1{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:500;margin:0;}
.date-pill{padding:4px 10px;border:1px solid var(--line);background:var(--surface);border-radius:6px;font-size:12px;color:var(--ink-soft);display:inline-flex;align-items:center;gap:5px;}
.meta{color:var(--ink-mute);font-size:12px;}
.meta b{color:var(--ink-soft);font-weight:500;}
.nav-tabs{display:flex;align-items:center;gap:2px;padding:2px;background:var(--surface);border:1px solid var(--line);border-radius:7px;margin-left:auto;}
.nav-tabs a,.nav-tabs span{padding:4px 10px;font-size:12px;color:var(--ink-soft);text-decoration:none;border-radius:5px;white-space:nowrap;}
.nav-tabs .active{background:var(--ink);color:var(--paper);font-weight:500;}
.icon-btn{height:29px;padding:0 10px;border-radius:6px;border:1px solid var(--line);background:var(--surface);display:inline-flex;align-items:center;gap:5px;color:var(--ink-soft);cursor:pointer;font-size:12px;font-family:inherit;}
.icon-btn:hover{background:var(--surface-soft);border-color:var(--line-strong);color:var(--ink);}

/* ── controls ──────────────────────────── */
.controls{position:sticky;top:50px;z-index:50;background:var(--paper);padding:9px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:9px;flex-wrap:wrap;}
.ctl-grp{display:flex;align-items:center;gap:5px;}
.ctl-lbl{font-size:11px;color:var(--ink-mute);margin-right:2px;}
.divider{width:1px;height:16px;background:var(--line);margin:0 3px;}
.pill{padding:3px 9px;border:1px solid var(--line);background:var(--surface);border-radius:999px;font-size:11.5px;color:var(--ink-soft);cursor:pointer;transition:all .1s;user-select:none;}
.pill:hover{border-color:var(--line-strong);color:var(--ink);}
.pill.on{background:var(--ink);color:var(--paper);border-color:var(--ink);}
.pill.dim.on{background:var(--navy);border-color:var(--navy);}
.toggle-btn{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;color:var(--ink-soft);padding:3px 9px;border:1px solid var(--line);border-radius:6px;background:var(--surface);cursor:pointer;user-select:none;}
.toggle-btn.on{border-color:var(--orange);color:var(--orange);background:var(--orange-soft);}
.toggle-dot{width:7px;height:7px;border-radius:50%;background:var(--ink-light);}
.toggle-btn.on .toggle-dot{background:var(--orange);}
.search-box{margin-left:auto;display:flex;align-items:center;gap:5px;padding:4px 10px;background:var(--surface);border:1px solid var(--line);border-radius:6px;color:var(--ink-mute);}
.search-box input{border:none;outline:none;background:transparent;width:170px;font-size:12px;font-family:inherit;color:var(--ink);}
.ctl-info{width:100%;height:0;font-size:0;}

/* ── table ──────────────────────────────── */
.table-wrap{overflow-x:auto;background:var(--surface);border-bottom:1px solid var(--line);}
table.t{border-collapse:separate;border-spacing:0;font-size:12px;min-width:1200px;}
table.t th,table.t td{border-right:1px solid var(--line-soft);border-bottom:1px solid var(--line-soft);padding:4px 7px;text-align:right;white-space:nowrap;background:var(--surface);}
table.t thead th{background:var(--surface-soft);color:var(--ink-mute);font-weight:500;font-size:11px;text-align:center;position:sticky;z-index:30;}
table.t thead tr.r1 th{top:0;}
table.t thead tr.r2 th{top:28px;border-bottom:1px solid var(--line);}
table.t thead .g-var{background:rgba(28,72,120,0.07);color:var(--navy);}
table.t thead .g-pay{background:rgba(184,57,43,0.07);color:var(--red);}
table.t thead .g-clm{background:rgba(58,122,75,0.09);color:var(--green);}
table.t thead .g-amt{background:rgba(201,120,38,0.07);color:var(--orange);}
table.t thead .g-pre{background:var(--paper-soft);color:var(--ink-soft);}
table.t thead .cur{background:var(--navy);color:#fff;font-weight:600;}
/* frozen left cols */
table.t .frz{position:sticky;z-index:20;background:var(--surface);}
table.t .frz.f0{left:0;min-width:38px;max-width:38px;}
table.t .frz.f1{left:38px;min-width:130px;max-width:140px;}
table.t .frz.f2{left:168px;min-width:88px;max-width:88px;box-shadow:4px 0 6px -3px rgba(0,0,0,0.07);border-right:1px solid var(--line);}
table.t thead .frz{z-index:40;background:var(--surface-soft);}
/* row styles */
table.t tbody tr{cursor:pointer;}
table.t tbody tr:hover td{background:var(--surface-soft);}
table.t tbody tr.grp-hdr td{background:var(--paper-soft);color:var(--ink-mute);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);text-align:left;padding:5px 10px;cursor:default;}
table.t tbody tr.grp-hdr td.frz{background:var(--paper-soft);}
table.t tbody tr.overall-row td{background:rgba(255,232,154,0.10);font-weight:600;}
table.t tbody tr.overall-row td.frz{background:rgba(255,232,154,0.14);}
table.t td.lt{text-align:left;}
table.t td.cur{background:rgba(28,72,120,0.04)!important;font-weight:600;}
table.t td.d-up{color:var(--red);}
table.t td.d-dn{color:var(--green);}
table.t td.d-mid{color:var(--orange);}
table.t td.spark-cell{padding:2px 5px;}
.obj-name{font-weight:500;}
.row-rank{color:var(--ink-light);font-variant-numeric:tabular-nums;font-family:'Noto Serif SC',serif;font-size:11px;text-align:center;}
.sev-dot{display:inline-block;width:6px;height:6px;border-radius:50%;vertical-align:middle;margin-left:3px;}
.sev-dot.red{background:var(--red);}
.sev-dot.yellow{background:var(--orange);}
.sev-dot.blue{background:var(--navy);}
.sev-dot.green{background:var(--green);}
.prem-bar{display:inline-flex;align-items:center;gap:5px;justify-content:flex-end;}
.prem-bar .bg{width:34px;height:5px;background:rgba(0,0,0,0.06);border-radius:2px;overflow:hidden;}
.prem-bar .fill{height:100%;background:var(--navy);border-radius:2px;}
/* expand row */
table.t tr.exp-row td{background:var(--paper)!important;padding:0!important;border-top:1px solid var(--line);}
.exp-inner{padding:12px 22px;}
.exp-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;}
.ex-card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:11px 13px;}
.ex-card .lbl{font-size:10px;color:var(--ink-mute);margin-bottom:3px;text-transform:uppercase;letter-spacing:1px;}
.ex-card .val{font-family:'Noto Serif SC',serif;font-size:20px;font-weight:500;line-height:1.1;}
.ex-card .val.red{color:var(--red);}
.ex-card .val.org{color:var(--orange);}
.ex-card .sub{font-size:11px;color:var(--ink-mute);margin-top:3px;}
/* footer */
.footer{position:sticky;bottom:0;z-index:50;background:var(--paper);border-top:1px solid var(--line);padding:9px 24px;display:flex;align-items:center;gap:12px;font-size:11.5px;color:var(--ink-mute);}
.b-count{padding:2px 8px;border-radius:999px;font-weight:500;}
.b-count.red{background:var(--red-soft);color:var(--red);}
.b-count.org{background:var(--orange-soft);color:var(--orange);}
.b-count.gn{background:var(--green-soft);color:var(--green);}
.b-count.gy{background:var(--paper-soft);color:var(--ink-soft);}
.footer-grow{flex:1;}
.footer a{color:var(--navy);text-decoration:none;}
.footer a:hover{text-decoration:underline;}
/* column-hide helpers — toggled by JS on table element */
table.t.hide-vcr  .m-vcr  { display:none; }
table.t.hide-lr   .m-lr   { display:none; }
table.t.hide-freq .m-freq { display:none; }
table.t.hide-avg  .m-avg  { display:none; }
table.t.hide-coef .m-coef { display:none; }
/* ── 跨维度下钻（expand row 内部）─────────────────── */
.exp-cross{margin-top:14px;border:1px solid var(--line);border-radius:6px;overflow:hidden;}
.exp-cross-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:7px 12px;background:rgba(28,72,120,0.05);border-bottom:1px solid var(--line);}
.exp-cross-title{font-size:11px;color:var(--navy);font-weight:500;text-transform:uppercase;letter-spacing:1px;white-space:nowrap;}
.cdim-tabs{display:flex;gap:4px;flex-wrap:wrap;}
.cdim-tab{padding:3px 9px;border-radius:4px;font-size:11.5px;color:var(--navy);cursor:pointer;border:1px solid var(--navy-line);background:transparent;}
.cdim-tab.on{background:var(--navy);color:var(--paper);border-color:var(--navy);}
.cdim-wrap{padding:10px 12px;background:var(--paper);overflow-x:auto;}
.cdim-tbl{border-collapse:collapse;font-size:12px;min-width:360px;}
.cdim-tbl th,.cdim-tbl td{padding:5px 8px;border-bottom:1px solid var(--line-soft);text-align:right;white-space:nowrap;}
.cdim-tbl th{font-weight:500;font-size:11px;color:var(--ink-mute);}
.cdim-tbl th.lt,.cdim-tbl td.lt{text-align:left;}
.cdim-tbl tbody tr:hover{background:var(--surface-soft);}
"""

# ===== JavaScript =============================================================

V4_JS = r"""
// ── data ──────────────────────────────────────────────────────────
const ROWS = __ROWS_JSON__;
const WARN = __WARN_JSON__;
const DD   = __DD_JSON__;
const METRIC_DEFS = [
  {id:'vcr',  label:'变率',    kind:'pct',   thCls:'g-var'},
  {id:'lr',   label:'赔付率',  kind:'pct',   thCls:'g-pay'},
  {id:'freq', label:'出险率',  kind:'pct',   thCls:'g-clm'},
  {id:'avg',  label:'案均',    kind:'money', thCls:'g-amt'},
  {id:'coef', label:'自主系数',kind:'coef',  thCls:'g-pre'},
];
const PERIOD_LABELS = ['36月','24月','上年','12月','6月','本年'];
const YTD_IDX = 5, YOY_IDX = 2, M12_IDX = 3;

// ── state ─────────────────────────────────────────────────────────
let state = {
  compare: 'yoy',            // yoy / m12 / warn
  activeMetrics: new Set(['vcr','lr']),
  onlyAlert: false,
  search: '',
  expanded: new Set(),
  sortBy: 'default',         // default / ytd-desc / delta-desc / prem-desc / name
};

// ── utils ─────────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fv(v, kind) {
  if (v == null || isNaN(v)) return '—';
  if (kind === 'pct')   return v.toFixed(1) + '%';
  if (kind === 'coef')  return v.toFixed(3);
  if (kind === 'money') return '¥' + Math.round(v).toLocaleString();
  return v.toFixed(1);
}
function fd(d, kind) {
  if (d == null || isNaN(d)) return '—';
  const sign = d >= 0 ? '+' : '';
  if (kind === 'pct')   return sign + d.toFixed(1) + ' PP';
  if (kind === 'coef')  return sign + d.toFixed(3);
  if (kind === 'money') return sign + Math.round(d).toLocaleString() + ' 元';
  return sign + d.toFixed(1);
}
function sevColor(sev) {
  return {red:'var(--red)', yellow:'var(--orange)', blue:'var(--navy)', green:'var(--green)'}[sev] || 'var(--ink-mute)';
}
function deltaClass(d, kind) {
  if (d == null) return '';
  // 出险率/变率/赔付率：升=恶化=红；降=好转=绿
  if (['pct'].includes(kind)) return d > 5 ? 'd-up' : d < -3 ? 'd-dn' : d > 0 ? 'd-mid' : '';
  // 案均：升=恶化=红
  if (kind === 'money') return d > 500 ? 'd-up' : d < -300 ? 'd-dn' : '';
  // 自主系数：升=恶化（过高）
  if (kind === 'coef')  return d > 0.05 ? 'd-up' : d < -0.05 ? 'd-dn' : '';
  return '';
}

// ── sparkline SVG ─────────────────────────────────────────────────
function sparkSvg(vals, color, w, h) {
  const pts = vals.map((v, i) => [i, v]).filter(p => p[1] != null && !isNaN(p[1]));
  if (pts.length < 2) return '';
  const ys = pts.map(p => p[1]);
  const mn = Math.min(...ys), mx = Math.max(...ys), rng = (mx-mn) || 1;
  const pad = 2;
  const xs = (i) => pad + (i / (vals.length-1)) * (w - pad*2);
  const ys2 = (v) => (h - pad) - ((v - mn) / rng) * (h - pad*2);
  const mapped = pts.map(p => [xs(p[0]), ys2(p[1])]);
  const lpts = mapped.map(p => p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
  const last = mapped[mapped.length-1];
  return `<svg width="${w}" height="${h}" style="display:block;overflow:visible">
    <polygon points="${mapped[0][0].toFixed(1)},${h-pad} ${lpts} ${last[0].toFixed(1)},${h-pad}" fill="${color}" fill-opacity="0.10"/>
    <polyline points="${lpts}" stroke="${color}" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.2" fill="${color}"/>
  </svg>`;
}

// ── cross-dim drill (expand row) ──────────────────────────────────
const GROUP_TO_SEC_ID = {
  '客户类别':'customer','三级机构':'branch','险类':'insurance',
  '险别组合':'combo','能源类型':'energy','新旧车':'newused',
  '是否过户':'transfer','是否续保':'renewal','是否电销':'telesales',
};
const DRILL_DIMS_V4 = {
  customer: [['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  branch:   [['customer','客户类别'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  insurance:[['customer','客户类别'],['branch','三级机构'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  combo:    [['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  energy:   [['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['newused','新旧车'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  newused:  [['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['transfer','过户'],['renewal','续保'],['telesales','电销']],
  transfer: [['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['renewal','续保'],['telesales','电销']],
  renewal:  [['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['telesales','电销']],
  telesales:[['customer','客户类别'],['branch','三级机构'],['insurance','险类'],['combo','险别组合'],['energy','能源'],['newused','新旧车'],['transfer','过户'],['renewal','续保']],
};
const CD_METRIC_TABS = [
  {label:'变率',    kind:'pct',   idx:2},
  {label:'赔付率',  kind:'pct',   idx:3},
  {label:'出险率',  kind:'pct',   idx:4},
  {label:'案均',    kind:'money', idx:5},
  {label:'自主系数',kind:'coef',  idx:6},
];
const CD_SEV_COLORS = ['var(--ink-mute)','var(--green)','var(--navy)','var(--orange)','var(--red)'];
const CD_PERIOD_LABELS = ['36月','24月','上年','12月','6月','本年'];

function buildCDimTable(subRows, metricIdx, metricKind) {
  if (!subRows || !subRows.length) {
    return '<div style="padding:14px;color:var(--ink-mute);font-size:12px">无交叉数据</div>';
  }
  let html = '<table class="cdim-tbl"><thead><tr><th class="lt">对象</th>';
  CD_PERIOD_LABELS.forEach(l => { html += `<th>${l}</th>`; });
  html += '</tr></thead><tbody>';
  subRows.forEach(row => {
    const disp = row[0], sev = row[1], series = row[metricIdx];
    const dotColor = CD_SEV_COLORS[sev] || 'var(--ink-mute)';
    const dot = sev >= 3
      ? `<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:${dotColor};vertical-align:middle;margin-left:4px"></span>`
      : '';
    html += `<tr><td class="lt">${escapeHtml(disp)}${dot}</td>`;
    series.forEach(v => {
      const fmt = v == null ? '—' :
        metricKind === 'pct'   ? v.toFixed(1) + '%' :
        metricKind === 'money' ? '¥' + Math.round(v).toLocaleString() :
        metricKind === 'coef'  ? v.toFixed(3) : String(v);
      html += `<td>${fmt}</td>`;
    });
    html += '</tr>';
  });
  return html + '</tbody></table>';
}

function buildCrossDimSection(r) {
  const secId = GROUP_TO_SEC_ID[r.group];
  if (!secId) return '';
  const dims = DRILL_DIMS_V4[secId] || [];
  if (!dims.length) return '';
  const rkey   = r.key;
  const rawval = r.raw_val;
  const dimTabsHtml = dims.map((d, i) =>
    `<span class="cdim-tab${i===0?' on':''}" data-role="dim" data-dim="${d[0]}" data-sec="${secId}" data-rawval="${escapeHtml(rawval)}" data-rkey="${escapeHtml(rkey)}" onclick="cdimSel(this,event)">${d[1]}</span>`
  ).join('');
  const metricTabsHtml = CD_METRIC_TABS.map((m, i) =>
    `<span class="cdim-tab${i===0?' on':''}" data-role="metric" data-midx="${m.idx}" data-mtype="${m.kind}" data-rkey="${escapeHtml(rkey)}" onclick="cdimSel(this,event)">${m.label}</span>`
  ).join('');
  const ddKey   = `${secId}|||${rawval}|||${dims[0][0]}`;
  const tblHtml = buildCDimTable(DD[ddKey] || [], 2, 'pct');
  return `<div class="exp-cross">
    <div class="exp-cross-bar">
      <span class="exp-cross-title">交叉下钻</span>
      <div class="cdim-tabs">${dimTabsHtml}</div>
      <div style="width:1px;height:16px;background:var(--line);margin:0 4px"></div>
      <div class="cdim-tabs">${metricTabsHtml}</div>
    </div>
    <div class="cdim-wrap" id="cdwrap-${escapeHtml(rkey)}">${tblHtml}</div>
  </div>`;
}

function cdimSel(tabEl, evt) {
  evt.stopPropagation();
  const rkey = tabEl.dataset.rkey;
  const role = tabEl.dataset.role;
  const bar  = tabEl.closest('.exp-cross-bar');
  if (!bar) return;
  bar.querySelectorAll(`.cdim-tab[data-role="${role}"]`).forEach(t => t.classList.remove('on'));
  tabEl.classList.add('on');
  const activeDim = bar.querySelector('.cdim-tab[data-role="dim"].on');
  const activeMet = bar.querySelector('.cdim-tab[data-role="metric"].on');
  if (!activeDim || !activeMet) return;
  const ddKey   = `${activeDim.dataset.sec}|||${activeDim.dataset.rawval}|||${activeDim.dataset.dim}`;
  const subRows = DD[ddKey] || [];
  const wrap = document.getElementById('cdwrap-' + rkey);
  if (wrap) wrap.innerHTML = buildCDimTable(subRows, parseInt(activeMet.dataset.midx), activeMet.dataset.mtype);
}

// ── filter + sort rows ────────────────────────────────────────────
function getVisibleRows() {
  let rows = ROWS.slice();
  if (state.onlyAlert) rows = rows.filter(r => r.sev === 'red' || r.sev === 'yellow');
  if (state.search.trim()) {
    const q = state.search.trim();
    rows = rows.filter(r => r.name.includes(q) || r.group.includes(q));
  }
  if (state.sortBy === 'ytd-desc') {
    rows.sort((a,b) => {
      const av = a.metrics.vcr[YTD_IDX], bv = b.metrics.vcr[YTD_IDX];
      if (av == null) return 1; if (bv == null) return -1; return bv - av;
    });
  } else if (state.sortBy === 'delta-desc') {
    rows.sort((a,b) => {
      const ak = state.compare, ad = a.deltas.vcr[ak], bd = b.deltas.vcr[ak];
      if (ad == null) return 1; if (bd == null) return -1; return bd - ad;
    });
  } else if (state.sortBy === 'prem-desc') {
    rows.sort((a,b) => {
      if (a.prem == null) return 1; if (b.prem == null) return -1; return b.prem - a.prem;
    });
  } else if (state.sortBy === 'name') {
    rows.sort((a,b) => a.name.localeCompare(b.name, 'zh'));
  }
  return rows;
}

// ── build table HTML ──────────────────────────────────────────────
function buildTable(visible) {
  // group by group label preserving order
  const groups = [];
  let cur = null;
  visible.forEach(r => {
    if (!cur || cur.g !== r.group) { cur = {g:r.group, rows:[]}; groups.push(cur); }
    cur.rows.push(r);
  });

  const compareKey = state.compare;
  const compareLabel = {yoy:'上年同期', m12:'滚动12月', warn:'警戒线'}[compareKey];
  const am = [...state.activeMetrics];
  const totalCols = 3 + am.length * 7 + 1;

  let head = `<thead>
<tr class="r1">
  <th rowspan="2" class="frz f0">#</th>
  <th rowspan="2" class="frz f1" style="text-align:left;padding-left:10px;">对象</th>
  <th rowspan="2" class="frz f2">6 期趋势</th>`;
  am.forEach(mid => {
    const m = METRIC_DEFS.find(d=>d.id===mid);
    const unit = m.kind==='money'?'(元)':m.kind==='coef'?'':' (%)';
    head += `<th colspan="7" class="m-${mid} ${m.thCls}" style="border-bottom:1px solid var(--line)">${m.label}${unit}</th>`;
  });
  head += `<th rowspan="2" class="g-pre" style="vertical-align:middle">保费<br/>占比</th></tr>
<tr class="r2">`;
  am.forEach(mid => {
    PERIOD_LABELS.forEach((pl, pi) => {
      head += `<th class="m-${mid}${pi===YTD_IDX?' cur':''}">${pl}</th>`;
    });
    head += `<th class="m-${mid}">Δ ${compareLabel}</th>`;
  });
  head += '</tr></thead>';

  let body = '<tbody>';
  let rank = 0;
  groups.forEach(({g, rows}) => {
    body += `<tr class="grp-hdr"><td colspan="${totalCols}" class="frz f0" style="left:0">${escapeHtml(g)} · ${rows.length} 项</td></tr>`;
    rows.forEach(r => {
      rank++;
      const isOverall = r.group === '整体';
      const color = sevColor(r.sev);
      const spark = sparkSvg(r.metrics.vcr, color, 76, 20);
      const sevDot = (r.sev === 'red' || r.sev === 'yellow') ?
        `<span class="sev-dot ${r.sev}"></span>` : '';
      const premCell = r.prem != null
        ? `<span class="prem-bar"><span class="bg"><span class="fill" style="width:${Math.min(100,r.prem)}%"></span></span><span style="min-width:28px;text-align:right">${r.prem.toFixed(1)}</span></span>`
        : '<span style="color:var(--ink-mute)">—</span>';

      let cells = '';
      am.forEach(mid => {
        const m = METRIC_DEFS.find(d=>d.id===mid);
        const series = r.metrics[mid];
        series.forEach((v, pi) => {
          const isCur = pi === YTD_IDX;
          cells += `<td class="m-${mid} num${isCur?' cur':''}">${fv(v, m.kind)}${isCur&&(r.sev==='red'||r.sev==='yellow')?`<span class="sev-dot ${r.sev}"></span>`:''}</td>`;
        });
        const d = r.deltas[mid][compareKey];
        const dc = deltaClass(d, m.kind);
        cells += `<td class="m-${mid} num${dc?' '+dc:''}">${fd(d, m.kind)}</td>`;
      });

      const rowCls = isOverall ? 'overall-row' : '';
      body += `<tr class="${rowCls}" data-key="${r.key}" onclick="toggleExpand('${r.key}',this)">
  <td class="frz f0 row-rank">${rank}</td>
  <td class="frz f1 lt" style="padding-left:10px"><span class="obj-name">${escapeHtml(r.name)}</span>${sevDot}</td>
  <td class="frz f2 spark-cell">${spark}</td>
  ${cells}
  <td class="num">${premCell}</td>
</tr>`;

      // expand row (hidden initially)
      const expCls = state.expanded.has(r.key) ? '' : ' style="display:none"';
      let exCards = '';
      METRIC_DEFS.forEach(m => {
        const sv = r.metrics[m.id];
        const ytdV = sv[YTD_IDX];
        const yoyV = sv[YOY_IDX];
        const dv = (ytdV!=null&&yoyV!=null) ? (ytdV-yoyV) : null;
        const spark2 = sparkSvg(sv, {vcr:'var(--navy)',lr:'var(--red)',freq:'var(--green)',avg:'var(--orange)',coef:'var(--ink-soft)'}[m.id]||'var(--ink-mute)', 160, 28);
        const valSev = m.id==='vcr'&&(r.sev==='red'||r.sev==='yellow') ? r.sev :
                       (m.id==='lr'&&ytdV>70)?'red':(m.id==='freq'&&ytdV>10)?'yellow':'';
        exCards += `<div class="ex-card">
  <div class="lbl">${m.label}</div>
  <div class="val${valSev?' '+valSev:''}">${fv(ytdV, m.kind)}${m.kind==='pct'?'':m.kind==='money'?'':''}</div>
  <div class="sub">Δ 同期 <b style="color:${dv!=null?(dv>0?'var(--red)':'var(--green)'):'var(--ink-mute)'}">${fd(dv,m.kind)}</b></div>
  <div style="margin-top:7px">${spark2}</div>
</div>`;
      });
      body += `<tr class="exp-row" data-exp="${r.key}"${expCls}>
  <td colspan="${totalCols}" class="frz f0" style="left:0">
    <div class="exp-inner">
      <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px">
        <span style="font-family:'Noto Serif SC',serif;font-size:15px;font-weight:500">${escapeHtml(r.name)}</span>
        <span style="font-size:11px;color:var(--ink-mute)">${escapeHtml(r.group)} · 全指标快照</span>
      </div>
      <div class="exp-grid">${exCards}</div>
      ${buildCrossDimSection(r)}
    </div>
  </td>
</tr>`;
    });
  });
  if (visible.length === 0) {
    body += `<tr><td colspan="${totalCols}" style="text-align:center;color:var(--ink-mute);padding:38px 0">没有匹配的对象 · 调整筛选或清除搜索</td></tr>`;
  }
  body += '</tbody>';

  return head + body;
}

// ── counts for footer ─────────────────────────────────────────────
function getCounts(visible) {
  const c = {red:0,yellow:0,green:0,blue:0,gray:0};
  visible.forEach(r => c[r.sev] = (c[r.sev]||0) + 1);
  return c;
}

// ── render ─────────────────────────────────────────────────────────
function render() {
  const visible = getVisibleRows();
  const tbl = document.getElementById('main-table');
  tbl.innerHTML = buildTable(visible);

  // apply column hide classes
  ['vcr','lr','freq','avg','coef'].forEach(mid => {
    tbl.classList.toggle('hide-'+mid, !state.activeMetrics.has(mid));
  });

  // footer counts
  const c = getCounts(visible);
  document.getElementById('cnt-red').textContent  = '● ' + (c.red||0) + ' 严重';
  document.getElementById('cnt-org').textContent  = '● ' + (c.yellow||0) + ' 关注';
  document.getElementById('cnt-gn').textContent   = '● ' + (c.green||0) + ' 健康';
  document.getElementById('cnt-gy').textContent   = '● ' + ((c.blue||0)+(c.gray||0)) + ' 中性';
  document.getElementById('cnt-total').textContent = visible.length + ' 行 / 共 ' + ROWS.length + ' 行';

  // re-restore expanded states
  state.expanded.forEach(k => {
    const expRow = tbl.querySelector(`[data-exp="${k}"]`);
    if (expRow) expRow.style.display = '';
  });
}

// ── toggle expand ─────────────────────────────────────────────────
function toggleExpand(key, rowEl) {
  const tbl = document.getElementById('main-table');
  const expRow = tbl.querySelector(`[data-exp="${key}"]`);
  if (!expRow) return;
  const isShown = expRow.style.display !== 'none';
  expRow.style.display = isShown ? 'none' : '';
  if (isShown) state.expanded.delete(key); else state.expanded.add(key);
}

// ── controls wiring ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  // ?focus= prefill
  try {
    const fp = new URLSearchParams(window.location.search).get('focus');
    if (fp) { state.search = fp; document.getElementById('search-input').value = fp; }
  } catch(e){}

  // compare pills
  document.querySelectorAll('[data-compare]').forEach(el => {
    el.addEventListener('click', () => {
      state.compare = el.dataset.compare;
      document.querySelectorAll('[data-compare]').forEach(e => e.classList.toggle('on', e.dataset.compare===state.compare));
      render();
    });
  });

  // metric pills
  document.querySelectorAll('[data-metric]').forEach(el => {
    el.addEventListener('click', () => {
      const mid = el.dataset.metric;
      if (state.activeMetrics.has(mid)) {
        if (state.activeMetrics.size <= 1) return; // keep at least 1
        state.activeMetrics.delete(mid);
        el.classList.remove('on');
      } else {
        state.activeMetrics.add(mid);
        el.classList.add('on');
      }
      render();
    });
  });

  // sort pills
  document.querySelectorAll('[data-sort]').forEach(el => {
    el.addEventListener('click', () => {
      state.sortBy = el.dataset.sort;
      document.querySelectorAll('[data-sort]').forEach(e => e.classList.toggle('on', e.dataset.sort===state.sortBy));
      render();
    });
  });

  // alert toggle
  document.getElementById('toggle-alert').addEventListener('click', function() {
    state.onlyAlert = !state.onlyAlert;
    this.classList.toggle('on', state.onlyAlert);
    render();
  });

  // search
  document.getElementById('search-input').addEventListener('input', function() {
    state.search = this.value;
    render();
  });

  render();
});
"""


# ===== Page render helpers ====================================================

_CMP_OPTS    = [("yoy","vs 上年同期"), ("m12","vs 滚动12月"), ("warn","vs 警戒线")]
_SORT_OPTS   = [("default","默认"), ("ytd-desc","本年值↓"), ("delta-desc","同期Δ↓"),
                ("prem-desc","保费↓"), ("name","名称")]


def _v4_topbar(cutoff: date, meta: dict, dash_href: str, week_href: str) -> str:
    cs = cutoff.isoformat()
    return f"""<div class="topbar">
  <div class="brand">
    <span class="brand-mark serif">川</span>
    <span style="font-size:12px;color:var(--ink-soft)">四川分公司 · 数据治理</span>
  </div>
  <div style="width:1px;height:18px;background:var(--line)"></div>
  <h1 class="serif">多期车险保单品质对比 · 全字段超表</h1>
  <span style="padding:2px 8px;border-radius:999px;background:var(--orange-soft);color:var(--orange);font-size:11px;font-weight:500">V4 · 分析师视角</span>
  <span class="date-pill">
    {cs}
    <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>
  </span>
  <span class="meta"><b class="num">{_html.escape(meta['policies'])}</b> 万单 · <b class="num">{_html.escape(meta['premium'])}</b> 万元</span>
  <div class="nav-tabs">
    <a href="{dash_href}">驾驶舱</a>
    <a href="{week_href}">周报</a>
    <span class="active">超表</span>
  </div>
  {theme_toggle_btn()}
</div>"""


def _v4_controls() -> str:
    cmp_pills = "".join(
        f'<span class="pill{" on" if k=="yoy" else ""}" data-compare="{k}">{lbl}</span>'
        for k, lbl in _CMP_OPTS
    )
    metric_pills = "".join(
        f'<span class="pill dim{" on" if mid in ("vcr","lr") else ""}" data-metric="{mid}">{lbl}</span>'
        for mid, lbl, *_ in METRIC_DEFS
    )
    sort_pills = "".join(
        f'<span class="pill{" on" if k=="default" else ""}" data-sort="{k}">{lbl}</span>'
        for k, lbl in _SORT_OPTS
    )
    return f"""<div class="controls">
  <div class="ctl-grp"><span class="ctl-lbl">对比口径</span>{cmp_pills}</div>
  <div class="divider"></div>
  <div class="ctl-grp"><span class="ctl-lbl">指标列</span>{metric_pills}</div>
  <div class="divider"></div>
  <div class="ctl-grp"><span class="ctl-lbl">排序</span>{sort_pills}</div>
  <div class="divider"></div>
  <div class="ctl-grp">
    <span class="toggle-btn" id="toggle-alert">
      <span class="toggle-dot"></span> 仅 ≥ 警戒线
    </span>
  </div>
  <div class="search-box">
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.4"/><path d="M10.5 10.5 L14 14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
    <input id="search-input" placeholder="搜索对象 · 自贡 / 摩托车…"/>
  </div>
</div>"""


def _v4_footer(dash_href: str, week_href: str) -> str:
    return f"""<div class="footer">
  <span class="b-count red" id="cnt-red">● 0 严重</span>
  <span class="b-count org" id="cnt-org">● 0 关注</span>
  <span class="b-count gn"  id="cnt-gn">● 0 健康</span>
  <span class="b-count gy"  id="cnt-gy">● 0 中性</span>
  <span id="cnt-total"></span>
  <span class="footer-grow"></span>
  <a href="{dash_href}">← 驾驶舱</a>
  <span style="color:var(--ink-light)">|</span>
  <a href="{week_href}">周报版 →</a>
</div>"""


# ===== Page render ============================================================

def render_v4_page(df: pd.DataFrame, cutoff: date, anomalies=None) -> str:
    """生成 V4 超表完整 HTML。"""
    rows, meta = _build_rows(df)
    warn_js = {
        m_id: (_TH.get(wk, (0, 0, 0))[1] if wk else None)
        for m_id, _, _, _, _, wk in METRIC_DEFS
    }
    rows_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    warn_json = json.dumps(warn_js, ensure_ascii=False)
    dd_json   = json.dumps(build_drilldown_data(df), ensure_ascii=False, separators=(",", ":"))
    js_code   = (V4_JS.replace("__ROWS_JSON__", rows_json)
                       .replace("__WARN_JSON__", warn_json)
                       .replace("__DD_JSON__", dd_json))

    cs        = cutoff.isoformat()
    dash_href = f"{cs}-dashboard.html"
    week_href = f"{cs}-weekly.html"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>多期车险保单品质对比 · 超表 · {cs}</title>
<meta name="viewport" content="width=1600, initial-scale=1"/>
{FONT_LINKS}
<style>
{BASE_CSS}
{DARK_CSS}
{THEME_TOGGLE_CSS}
{V4_CSS}
</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{_v4_topbar(cutoff, meta, dash_href, week_href)}
{_v4_controls()}
<div class="table-wrap">
  <table class="t" id="main-table"><!-- rendered by JS --></table>
</div>
{_v4_footer(dash_href, week_href)}
<script>{THEME_TOGGLE_JS}
{js_code}</script>
</body>
</html>"""
