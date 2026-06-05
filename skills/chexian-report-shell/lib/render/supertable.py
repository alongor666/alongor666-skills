"""V4 超表组件（自 diagnose-period-trend/lib/render_v4.py 移植）。

提供：
  - SUPERTABLE_CSS：列冻结 + 全字段超表 CSS
  - SUPERTABLE_JS：客户端渲染 JS（搜索/排序/行展开/交叉下钻）
  - render_topbar()：顶部导航栏
  - render_controls()：控制条（对比口径/指标列/排序/搜索）
  - render_footer()：粘性页脚（亮灯统计）
  - render_table_shell()：表格外壳（rows 数据需替换 __ROWS_JSON__）

依赖：
  - 无 pandas（纯 HTML + JS 模板生成）
"""
from __future__ import annotations

import html
import json
from datetime import date
from typing import Literal


# ===== 常量定义 =====

# 默认 5 指标定义
DEFAULT_METRIC_DEFS = [
    ("vcr",  "变率",     "variable_cost_ratio",    "pct",   "g-var", "variable_cost_ratio_pct"),
    ("lr",   "赔付率",   "earned_claim_ratio",      "pct",   "g-pay", "earned_loss_ratio_pct"),
    ("freq", "出险率",   "earned_loss_frequency",   "pct",   "g-clm", "earned_loss_freq_pct"),
    ("avg",  "案均",     "avg_claim_amount",        "money", "g-amt", None),
    ("coef", "自主系数", "weighted_pricing_factor", "coef",  "g-pre", None),
]

# 默认 6 期顺序
DEFAULT_PERIOD_HEADERS = [
    ("滚动36个月", "36月"),
    ("滚动24个月", "24月"),
    ("上年同期",   "上年"),
    ("滚动12个月", "12月"),
    ("滚动6个月",  "6月"),
    ("当年起保",   "本年"),
]

YTD_IDX = 5
YOY_IDX = 2
M12_IDX = 3


# ===== CSS 样式 =====

SUPERTABLE_CSS = """
/* ── topbar ─────────────────────────────── */
.topbar{position:sticky;top:0;z-index:60;background:var(--paper);border-bottom:1px solid var(--line);padding:10px 24px;display:flex;align-items:center;gap:12px;flex-wrap:nowrap;}
.brand{display:flex;align-items:center;gap:7px;}
.brand-mark{width:22px;height:22px;border-radius:4px;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;}
.topbar h1{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:500;margin:0;}
.date-pill{padding:4px 10px;border:1px solid var(--line);background:var(--surface);border-radius:6px;font-size:12px;color:var(--ink-soft);display:inline-flex;align-items:center;gap:5px;}
.meta{color:var(--ink-mute);font-size:12px;}
.meta b{color:var(--ink-soft);font-weight:500;}
.nav-tabs{display:flex;align-items:center;gap:4px;padding:3px;background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-left:auto;}
.nav-tabs a,.nav-tabs span{padding:5px 12px;font-size:12px;color:var(--ink);font-weight:500;text-decoration:none;border-radius:6px;white-space:nowrap;border:1px solid transparent;transition:background .15s, border-color .15s;}
.nav-tabs a{cursor:pointer;}
.nav-tabs a:hover{background:var(--paper);border-color:var(--line);}
.nav-tabs .active{background:var(--ink);color:var(--paper);border-color:var(--ink);cursor:default;}
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


# ===== JS 渲染脚本 =====

SUPERTABLE_JS = r"""
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
const PERIOD_LABELS = __PERIOD_LABELS__;
const YTD_IDX = __YTD_IDX__, YOY_IDX = __YOY_IDX__, M12_IDX = __M12_IDX__;

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
  if (['pct'].includes(kind)) return d > 5 ? 'd-up' : d < -3 ? 'd-dn' : d > 0 ? 'd-mid' : '';
  if (kind === 'money') return d > 500 ? 'd-up' : d < -300 ? 'd-dn' : '';
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
const GROUP_TO_SEC_ID = __GROUP_TO_SEC_ID__;
const DRILL_DIMS_V4 = __DRILL_DIMS_V4__;
const CD_METRIC_TABS = [
  {label:'变率',    kind:'pct',   idx:2},
  {label:'赔付率',  kind:'pct',   idx:3},
  {label:'出险率',  kind:'pct',   idx:4},
  {label:'案均',    kind:'money', idx:5},
  {label:'自主系数',kind:'coef',  idx:6},
];
const CD_SEV_COLORS = ['var(--ink-mute)','var(--green)','var(--navy)','var(--orange)','var(--red)'];
const CD_PERIOD_LABELS = __PERIOD_LABELS__;

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
  const groups = [];
  let cur = null;
  visible.forEach(r => {
    if (!cur || cur.g !== r.group) { cur = {g:r.group, rows:[]}; groups.push(cur); }
    cur.rows.push(r);
  });

  const compareKey = state.compare;
  const compareLabel = (__CMP_LABELS__)[compareKey];
  const am = [...state.activeMetrics];
  const totalCols = 3 + am.length * 7 + 1;

  let head = `<thead>
<tr class="r1">
  <th rowspan="2" class="frz f0">#</th>
  <th rowspan="2" class="frz f1" style="text-align:left;padding-left:10px;">对象</th>
  <th rowspan="2" class="frz f2">${PERIOD_LABELS.length} 期趋势</th>`;
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

      // expand row
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

  ['vcr','lr','freq','avg','coef'].forEach(mid => {
    tbl.classList.toggle('hide-'+mid, !state.activeMetrics.has(mid));
  });

  const c = getCounts(visible);
  document.getElementById('cnt-red').textContent  = '● ' + (c.red||0) + ' 严重';
  document.getElementById('cnt-org').textContent  = '● ' + (c.yellow||0) + ' 关注';
  document.getElementById('cnt-gn').textContent   = '● ' + (c.green||0) + ' 健康';
  document.getElementById('cnt-gy').textContent   = '● ' + ((c.blue||0)+(c.gray||0)) + ' 中性';
  document.getElementById('cnt-total').textContent = visible.length + ' 行 / 共 ' + ROWS.length + ' 行';

  state.expanded.forEach(k => {
    const expRow = tbl.querySelector(`[data-exp="${k}"]`);
    if (expRow) expRow.style.display = '';
  });
}

function toggleExpand(key, rowEl) {
  const tbl = document.getElementById('main-table');
  const expRow = tbl.querySelector(`[data-exp="${key}"]`);
  if (!expRow) return;
  const isShown = expRow.style.display !== 'none';
  expRow.style.display = isShown ? 'none' : '';
  if (isShown) state.expanded.delete(key); else state.expanded.add(key);
}

document.addEventListener('DOMContentLoaded', function() {
  try {
    const fp = new URLSearchParams(window.location.search).get('focus');
    if (fp) { state.search = fp; document.getElementById('search-input').value = fp; }
  } catch(e){}

  document.querySelectorAll('[data-compare]').forEach(el => {
    el.addEventListener('click', () => {
      state.compare = el.dataset.compare;
      document.querySelectorAll('[data-compare]').forEach(e => e.classList.toggle('on', e.dataset.compare===state.compare));
      render();
    });
  });

  document.querySelectorAll('[data-metric]').forEach(el => {
    el.addEventListener('click', () => {
      const mid = el.dataset.metric;
      if (state.activeMetrics.has(mid)) {
        if (state.activeMetrics.size <= 1) return;
        state.activeMetrics.delete(mid);
        el.classList.remove('on');
      } else {
        state.activeMetrics.add(mid);
        el.classList.add('on');
      }
      render();
    });
  });

  document.querySelectorAll('[data-sort]').forEach(el => {
    el.addEventListener('click', () => {
      state.sortBy = el.dataset.sort;
      document.querySelectorAll('[data-sort]').forEach(e => e.classList.toggle('on', e.dataset.sort===state.sortBy));
      render();
    });
  });

  document.getElementById('toggle-alert').addEventListener('click', function() {
    state.onlyAlert = !state.onlyAlert;
    this.classList.toggle('on', state.onlyAlert);
    render();
  });

  document.getElementById('search-input').addEventListener('input', function() {
    state.search = this.value;
    render();
  });

  render();
});
"""


# ===== HTML 组件 =====

def render_topbar(
    cutoff: date,
    meta: dict,
    view_links: Optional[list[tuple[str, str]]] = None,
    title: str = "多期车险保单品质对比 · 全字段超表",
    brand_mark: str = "川",
    brand_text: str = "数据治理",
    version_label: str = "V4 · 分析师视角",
    theme_toggle_btn: Optional[str] = None,
) -> str:
    """顶部导航栏。

    Args:
        cutoff: 数据截止日期
        meta: 元数据字典，含 keys: policies/premium
        view_links: 视图切换链接列表 [(href, label), ...]，默认驾驶舱/周报
        title: 主标题
        brand_mark: 品牌标记文字
        brand_text: 品牌副标题
        version_label: 版本标签
        theme_toggle_btn: 主题切换按钮 HTML
    """
    if view_links is None:
        view_links = [
            (f"{cutoff.isoformat()}-dashboard.html", "驾驶舱"),
            (f"{cutoff.isoformat()}-weekly.html", "周报"),
        ]

    nav_items = ""
    for href, label in view_links:
        nav_items += f'<a href="{href}">{label}</a>'
    nav_items += '<span class="active">超表</span>'

    toggle_html = theme_toggle_btn or ""

    return f"""<div class="topbar">
  <div class="brand">
    <span class="brand-mark serif">{html.escape(brand_mark)}</span>
    <span style="font-size:12px;color:var(--ink-soft)">{html.escape(brand_text)}</span>
  </div>
  <div style="width:1px;height:18px;background:var(--line)"></div>
  <h1 class="serif">{html.escape(title)}</h1>
  <span style="padding:2px 8px;border-radius:999px;background:var(--orange-soft);color:var(--orange);font-size:11px;font-weight:500">{html.escape(version_label)}</span>
  <span class="date-pill">
    {cutoff.isoformat()}
    <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>
  </span>
  <span class="meta"><b class="num">{html.escape(str(meta.get('policies', '')))}</b> 万单 · <b class="num">{html.escape(str(meta.get('premium', '')))}</b> 万元</span>
  <div class="nav-tabs">
    {nav_items}
  </div>
  {toggle_html}
</div>"""


def render_controls(
    compare_opts: Optional[list[tuple[str, str]]] = None,
    metric_defs: Optional[list[tuple]] = None,
    sort_opts: Optional[list[tuple[str, str]]] = None,
    default_metrics: Optional[list[str]] = None,
) -> str:
    """控制条（对比口径/指标列/排序/搜索）。

    Args:
        compare_opts: 对比选项 [(key, label), ...]，默认 yoy/m12/warn
        metric_defs: 指标定义，默认 DEFAULT_METRIC_DEFS
        sort_opts: 排序选项 [(key, label), ...]
        default_metrics: 默认选中的指标 id 列表，默认 ['vcr','lr']
    """
    if compare_opts is None:
        compare_opts = [("yoy", "vs 上年同期"), ("m12", "vs 滚动12月"), ("warn", "vs 警戒线")]
    if metric_defs is None:
        metric_defs = DEFAULT_METRIC_DEFS
    if sort_opts is None:
        sort_opts = [("default", "默认"), ("ytd-desc", "本年值↓"), ("delta-desc", "同期Δ↓"),
                     ("prem-desc", "保费↓"), ("name", "名称")]
    if default_metrics is None:
        default_metrics = ["vcr", "lr"]

    cmp_pills = "".join(
        f'<span class="pill{" on" if k=="yoy" else ""}" data-compare="{k}">{lbl}</span>'
        for k, lbl in compare_opts
    )
    metric_pills = "".join(
        f'<span class="pill dim{" on" if mid in default_metrics else ""}" data-metric="{mid}">{lbl}</span>'
        for mid, lbl, *_ in metric_defs
    )
    sort_pills = "".join(
        f'<span class="pill{" on" if k=="default" else ""}" data-sort="{k}">{lbl}</span>'
        for k, lbl in sort_opts
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


def render_footer(
    dash_href: str = "#",
    week_href: str = "#",
) -> str:
    """粘性页脚（亮灯统计）。

    Args:
        dash_href: 驾驶舱链接
        week_href: 周报链接
    """
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


def render_table_shell(
    rows_json: str,
    warn_json: str,
    dd_json: str,
    period_labels: Optional[list[str]] = None,
    group_to_sec_id: Optional[dict] = None,
    drill_dims_v4: Optional[dict] = None,
    ytd_idx: Optional[int] = None,
    yoy_idx: Optional[int] = None,
    m12_idx: Optional[int] = None,
    compare_labels: Optional[dict] = None,
) -> str:
    """表格外壳（含 JS 模板替换）。

    Args:
        rows_json: 行数据 JSON 字符串（需外部 json.dumps 生成）
        warn_json: 警戒线值 JSON 字符串
        dd_json: 下钻数据 JSON 字符串
        period_labels: 期标签简称列表，默认 ['36月','24月','上年','12月','6月','本年']
        group_to_sec_id: 组名→段 ID 映射，默认客户类别/三级机构等
        drill_dims_v4: 段 ID→可下钻维度映射
        ytd_idx: 当期（最新列）在期数组中的索引，默认 YTD_IDX（DPT 6 期=5）。
                 org-weekly 等 5 期场景传 4。
        yoy_idx: 对比基准列索引，默认 YOY_IDX（DPT 上年同期=2）。
                 无同比的 org 可复用为"上周"列（传 3）。
        m12_idx: 滚动 12 月列索引，默认 M12_IDX（=3）。org 不适用时随便传一个有效索引。
        compare_labels: Δ 列表头按对比口径 key 显示的中文，默认
                        {yoy:'上年同期', m12:'滚动12月', warn:'警戒线'}。
                        org 复用 yoy 表示"上周"时传 {'yoy':'上周','warn':'警戒线'}。

    Returns:
        HTML table 元素字符串
    """
    if period_labels is None:
        period_labels = [lbl for _, lbl in DEFAULT_PERIOD_HEADERS]
    _ytd = YTD_IDX if ytd_idx is None else ytd_idx
    _yoy = YOY_IDX if yoy_idx is None else yoy_idx
    _m12 = M12_IDX if m12_idx is None else m12_idx
    _cmp_labels = compare_labels or {"yoy": "上年同期", "m12": "滚动12月", "warn": "警戒线"}

    js_code = SUPERTABLE_JS \
        .replace("__ROWS_JSON__", rows_json) \
        .replace("__WARN_JSON__", warn_json) \
        .replace("__DD_JSON__", dd_json) \
        .replace("__PERIOD_LABELS__", str(period_labels)) \
        .replace("__YTD_IDX__", str(_ytd)) \
        .replace("__YOY_IDX__", str(_yoy)) \
        .replace("__M12_IDX__", str(_m12)) \
        .replace("__CMP_LABELS__", json.dumps(_cmp_labels, ensure_ascii=False)) \
        .replace("__GROUP_TO_SEC_ID__", str(group_to_sec_id or {})) \
        .replace("__DRILL_DIMS_V4__", str(drill_dims_v4 or {}))

    return f"""<table class="t" id="main-table"></table>
<script>{js_code}</script>"""
