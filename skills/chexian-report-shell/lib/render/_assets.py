"""跨子模块共享的 HTML/CSS/JS 字符串模板。"""

PAGE_HEAD = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="ink">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
  /* 主题：墨水经典（默认） */
  :root {
    --ink: #1f2937;
    --ink-rgb: 31, 41, 55;
    --paper: #f1efea;
    --paper-rgb: 241, 239, 234;
    --card-bg: #ffffff;
    --card-shadow: 0 2px 14px rgba(20, 24, 32, .07);
    --rule: rgba(31, 41, 55, .14);
    --muted: #6b7280;
    --muted-strong: #4b5563;
    --th-bg: #ece9e1;
    --th-text: #374151;
    --row-border: #e5e0d3;
    --pill-bg: #e1ddd0;
    --pill-text: #3a3528;
    --pill-warn-bg: #fef3c7;
    --pill-warn-text: #92400e;
    --kicker: #94785a;
    --link: #2563eb;
    --alert-blue: #2563eb;
    --alert-green: #047857;
    --alert-yellow: #b45309;
    --alert-red: #b91c1c;
    --alert-gray: #9ca3af;
    --formula-bg: #f5f3ec;
    --formula-border: #d6d0bc;
    --tip-bg: #1f2937;
    --tip-text: #f9fafb;
  }
  /* 主题：午夜（暗色） */
  html[data-theme="midnight"] {
    --ink: #e2e8f0;
    --ink-rgb: 226, 232, 240;
    --paper: #0b1220;
    --paper-rgb: 11, 18, 32;
    --card-bg: #131b2c;
    --card-shadow: 0 2px 16px rgba(0, 0, 0, .35);
    --rule: rgba(226, 232, 240, .14);
    --muted: #94a3b8;
    --muted-strong: #cbd5e1;
    --th-bg: #1c2540;
    --th-text: #cbd5e1;
    --row-border: #1e2a47;
    --pill-bg: #1e2a47;
    --pill-text: #cbd5e1;
    --pill-warn-bg: #422c10;
    --pill-warn-text: #fbbf24;
    --kicker: #a78668;
    --link: #60a5fa;
    --alert-blue: #60a5fa;
    --alert-green: #34d399;
    --alert-yellow: #fbbf24;
    --alert-red: #f87171;
    --alert-gray: #64748b;
    --formula-bg: #0e1626;
    --formula-border: #1e2a47;
    --tip-bg: #f1efea;
    --tip-text: #1f2937;
  }

  /* 字体栈 */
  :root {
    --serif-zh: "Noto Serif SC", "PingFang SC", "Microsoft YaHei", serif;
    --sans-zh: "Noto Sans SC", -apple-system, "PingFang SC", sans-serif;
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: var(--sans-zh);
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 0 40px;
    color: var(--ink);
    line-height: 1.6;
    background: var(--paper);
    display: grid;
    grid-template-columns: 195px 1fr;  /* v1.25：左 TOC 195px 即够装最长 section 名 */
    grid-template-areas: "toc main";
    gap: 24px;  /* v1.25：32→24，让 8px 给主区 */
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    transition: background .35s ease, color .35s ease;
  }

  /* 顶部状态条（粘性） */
  .status-bar {
    position: sticky; top: 0; z-index: 50;
    background: var(--card-bg);
    border: 1px solid var(--rule);
    border-radius: 12px;
    padding: 10px 18px;
    margin-bottom: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    align-items: center;
    font-size: 13px;
    box-shadow: var(--card-shadow);
  }
  .status-bar .item strong {
    color: var(--muted);
    font-weight: 400;
    margin-right: 6px;
    font-size: 12px;
  }
  .status-bar .item .v {
    color: var(--ink);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
  }
  .status-bar .toggle-threshold {
    margin-left: auto;
    background: var(--pill-warn-bg);
    color: var(--pill-warn-text);
    padding: 5px 12px;
    border-radius: 999px;
    border: 0;
    font-family: var(--sans-zh);
    font-size: 12px;
    cursor: pointer;
  }
  .status-bar .toggle-threshold:hover { opacity: .85; }

  /* 卡片 */
  .card {
    background: var(--card-bg);
    border-radius: 14px;
    padding: 24px 28px;
    box-shadow: var(--card-shadow);
    margin-bottom: 16px;
    transition: background .35s ease;
    scroll-margin-top: 64px;  /* 锚点跳转时为 sticky toolbar 让位（v1.23 toolbar 已缩小） */
  }
  h1 {
    font-family: var(--serif-zh);
    font-size: 26px;
    font-weight: 700;
    margin: 0 0 8px;
    color: var(--ink);
  }
  h2 {
    font-family: var(--serif-zh);
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 6px;
    color: var(--ink);
  }
  .subtitle {
    font-size: 13px;
    color: var(--muted);
    margin: 0 0 12px;
  }

  /* kicker 中文小标 */
  .kicker {
    font-family: var(--sans-zh);
    font-size: 11px;
    letter-spacing: .12em;
    color: var(--kicker);
    margin: 0 0 6px;
    font-weight: 500;
  }

  /* 顶部头部彩签 */
  .pill {
    display: inline-block;
    padding: 5px 13px;
    border-radius: 999px;
    background: var(--pill-bg);
    color: var(--pill-text);
    font-size: 12px;
    margin: 0 6px 4px 0;
  }

  .meta {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    font-size: 12.5px;
    color: var(--muted-strong);
    margin: 12px 0 4px;
  }
  .meta strong { color: var(--ink); font-weight: 500; margin-right: 2px; }

  /* 数据表格 */
  .data-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 13px;
  }
  .data-table th, .data-table td {
    text-align: left;
    padding: 9px 12px;
    border-bottom: 1px solid var(--row-border);
  }
  .data-table th {
    background: var(--th-bg);
    color: var(--th-text);
    font-weight: 600;
    font-size: 12px;
    letter-spacing: .02em;
  }
  .data-table th.num-th { text-align: right; }
  .data-table td.num {
    text-align: right;
    font-family: var(--sans-zh);
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
    font-weight: 500;
    color: var(--ink);
    white-space: nowrap;
  }
  /* 带色块的单元格：数字右对齐到内边距边界，色块绝对定位到右边缘 */
  .data-table td.num.has-dot {
    position: relative;
    padding-right: 28px;
  }
  .data-table td.num.has-dot .num-val {
    display: inline-block;
  }
  .data-table td.num.has-dot .dot {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    margin: 0;
  }
  .data-table td.dim-cell { font-weight: 500; }
  .data-table .dim-sample {
    color: var(--alert-gray);
    font-size: 11px;
    margin-left: 4px;
    cursor: help;
  }

  /* 四级亮灯色块（CSS 圆点）— v1.25：仅黄/红显示，绿/蓝/灰隐藏减视觉噪声 */
  .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
    transform: translateY(-1px);
  }
  /* 主表格仅高亮异常（黄/红），健康状态不显示圆点 */
  .data-table .dot-green,
  .data-table .dot-blue,
  .data-table .dot-gray { display: none; }
  .dot-green { background: var(--alert-green); }
  .dot-blue { background: var(--alert-blue); }
  .dot-yellow { background: var(--alert-yellow); }
  .dot-red { background: var(--alert-red); }
  .dot-gray { background: var(--alert-gray); }

  .alert-blue { color: var(--alert-blue); }
  .alert-green { color: var(--alert-green); font-weight: 700; }
  .alert-yellow { color: var(--alert-yellow); font-weight: 700; }
  .alert-red { color: var(--alert-red); font-weight: 700; }
  .alert-gray { color: var(--alert-gray); }

  /* Tooltip：表头小问号 */
  .info {
    display: inline-block;
    width: 14px; height: 14px;
    line-height: 12px;
    text-align: center;
    border: 1px solid var(--muted);
    border-radius: 50%;
    color: var(--muted);
    font-size: 10px;
    font-weight: 400;
    cursor: help;
    margin-left: 5px;
    position: relative;
    vertical-align: middle;
  }
  .info:hover { color: var(--ink); border-color: var(--ink); }
  .info::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--tip-bg);
    color: var(--tip-text);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.5;
    width: max-content;
    max-width: 320px;
    white-space: normal;
    text-align: left;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transition: opacity .15s ease;
    z-index: 200;
    font-weight: 400;
    letter-spacing: 0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, .15);
  }
  .info:hover::after { opacity: 1; visibility: visible; }

  /* 引用框（v1.20：竖线再降 50% 亮度 → alpha 0.25） */
  .callout {
    padding: 14px 18px;
    border-left: 3px solid rgba(var(--ink-rgb), .25);
    background: rgba(var(--ink-rgb), .04);
    margin: 12px 0;
    font-family: var(--serif-zh);
    font-size: 14px;
    line-height: 1.65;
  }
  .callout-warn { border-left-color: rgba(180, 83, 9, .25); background: rgba(180, 83, 9, .06); }
  .callout-danger { border-left-color: rgba(185, 28, 28, .25); background: rgba(185, 28, 28, .06); }
  /* v1.27：午夜模式下"深底+浅色"视觉感知更强，竖线 alpha 再降一档（0.25 → ~0.12） */
  html[data-theme="midnight"] .callout { border-left-color: rgba(var(--ink-rgb), .10); }
  html[data-theme="midnight"] .callout-warn { border-left-color: rgba(251, 191, 36, .14); }
  html[data-theme="midnight"] .callout-danger { border-left-color: rgba(248, 113, 113, .14); }

  /* 说明浮窗（v1.22：ⓘ 图标 + hover 弹出气泡，CSS-only 零 JS） */
  .hover-note {
    position: relative;
    display: inline-block;
    margin-left: 6px;
    vertical-align: middle;
    font-weight: 400;
    cursor: help;
  }
  .hover-note-icon { color: var(--muted); font-size: 14px; }
  .hover-note:hover .hover-note-icon { color: var(--ink); }
  .hover-note-body {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    width: max-content;
    max-width: 460px;
    background: var(--tip-bg);
    color: var(--tip-text);
    padding: 10px 14px;
    border-radius: 6px;
    font-family: var(--sans-zh);
    font-size: 13px;
    font-weight: 400;
    line-height: 1.65;
    letter-spacing: 0;
    text-align: left;
    white-space: normal;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transition: opacity .15s ease;
    z-index: 200;
    box-shadow: 0 4px 12px rgba(0, 0, 0, .15);
  }
  .hover-note:hover .hover-note-body { opacity: 1; visibility: visible; }
  .hover-note-body strong { color: var(--tip-text); font-weight: 600; }
  @media print { .hover-note-body { position: static; opacity: 1; visibility: visible; display: block; box-shadow: none; margin-top: 6px; } }
  .callout strong { color: var(--ink); font-weight: 600; }
  .callout .cite {
    display: block;
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--muted);
    font-family: var(--sans-zh);
    letter-spacing: .02em;
  }

  .rule { border: 0; border-top: 1px solid var(--rule); margin: 14px 0; }

  /* 阈值对照表 */
  .threshold-card {
    border: 1px solid var(--rule);
  }
  .threshold-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 13px;
  }
  .threshold-table th, .threshold-table td {
    padding: 9px 12px;
    border-bottom: 1px solid var(--row-border);
    text-align: left;
  }
  .threshold-table th {
    background: var(--th-bg);
    color: var(--th-text);
    font-weight: 600;
    font-size: 12px;
    white-space: nowrap;
  }
  .threshold-table td.th-name { font-weight: 600; white-space: nowrap; }
  .threshold-table td.th-unit { color: var(--muted-strong); font-size: 12px; text-align: center; }
  .threshold-table td.th-formula { color: var(--muted-strong); font-size: 12px; line-height: 1.5; min-width: 240px; }
  .threshold-table td.th-scope { color: var(--muted); font-size: 11.5px; line-height: 1.5; min-width: 280px; }
  .threshold-table td.th-direction { color: var(--muted); font-size: 12px; }
  /* 周报横向时序表 */
  .weekly-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
  .weekly-table th, .weekly-table td {
    padding: 9px 12px; border-bottom: 1px solid var(--row-border);
    font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; white-space: nowrap;
  }
  /* v1.7：列头一律居中（指标列保持左对齐） */
  .weekly-table th {
    background: var(--th-bg); color: var(--th-text);
    font-weight: 600; font-size: 12px; text-align: center;
  }
  .weekly-table th.th-name { text-align: left; }
  .weekly-table td.td-name { text-align: left; font-weight: 500; }
  .weekly-table td.spark { text-align: center; padding: 4px 12px; min-width: 120px; }
  .weekly-table td.spark svg { display: block; margin: 0 auto; }
  .weekly-table td.num {
    text-align: right; font-weight: 500; color: var(--ink);
    position: relative; padding-right: 28px;
  }
  .weekly-table td.num .num-val { display: inline-block; }
  .weekly-table td.num .dot { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); margin: 0; }
  .weekly-table td.placeholder { color: var(--muted); font-style: italic; text-align: right; padding-right: 28px; }

  /* sparkline 默认（蓝色）+ 4 级亮灯变体（v1.7：随当周状态着色） */
  .weekly-table .spark-line { fill: none; stroke: var(--alert-blue); stroke-width: 1.5; }
  .weekly-table .spark-area { fill: var(--alert-blue); fill-opacity: 0.08; }
  .weekly-table .spark-dot  { fill: var(--alert-blue); }
  .weekly-table .spark-dot.last { r: 2.5; stroke: var(--card-bg); stroke-width: 1; }

  .weekly-table .spark-line.spark-green  { stroke: var(--alert-green); }
  .weekly-table .spark-line.spark-blue   { stroke: var(--alert-blue); }
  .weekly-table .spark-line.spark-yellow { stroke: var(--alert-yellow); }
  .weekly-table .spark-line.spark-red    { stroke: var(--alert-red); }
  .weekly-table .spark-line.spark-gray   { stroke: var(--alert-gray); }

  .weekly-table .spark-area.spark-area-green  { fill: var(--alert-green); fill-opacity: 0.10; }
  .weekly-table .spark-area.spark-area-blue   { fill: var(--alert-blue); fill-opacity: 0.10; }
  .weekly-table .spark-area.spark-area-yellow { fill: var(--alert-yellow); fill-opacity: 0.10; }
  .weekly-table .spark-area.spark-area-red    { fill: var(--alert-red); fill-opacity: 0.10; }
  .weekly-table .spark-area.spark-area-gray   { fill: var(--alert-gray); fill-opacity: 0.08; }

  .weekly-table .spark-dot.spark-dot-green  { fill: var(--alert-green); }
  .weekly-table .spark-dot.spark-dot-blue   { fill: var(--alert-blue); }
  .weekly-table .spark-dot.spark-dot-yellow { fill: var(--alert-yellow); }
  .weekly-table .spark-dot.spark-dot-red    { fill: var(--alert-red); }
  .weekly-table .spark-dot.spark-dot-gray   { fill: var(--alert-gray); }

  /* 概述段（render_metric_narrative）— v1.17 去左侧竖线，靠背景区分 */
  .narrative {
    margin: 6px 0 14px; padding: 14px 16px; background: var(--formula-bg);
    border-radius: 8px;
    font-size: 13.5px; line-height: 1.7;
  }
  .narrative .narr-summary { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
  .narrative .narr-label { color: var(--muted-strong); font-weight: 500; }
  .narrative .narr-baseline { color: var(--muted); font-size: 12px; margin-left: 4px; }
  .narrative .narr-line { margin: 4px 0; color: var(--ink); }
  .narrative .narr-line strong { color: var(--ink); margin-right: 4px; }
  .narrative .narr-improve strong { color: var(--alert-green); }
  .narrative .narr-worsen  strong { color: var(--alert-red); }
  .narrative .narr-fact { color: var(--muted-strong); font-size: 12.5px; }
  .narrative .narr-pill {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: 11.5px; font-weight: 600;
    background: var(--card-bg); border: 1px solid var(--rule);
  }
  .narrative .narr-green  { color: var(--alert-green); border-color: var(--alert-green); }
  .narrative .narr-blue   { color: var(--alert-blue); border-color: var(--alert-blue); }
  .narrative .narr-yellow { color: var(--alert-yellow); border-color: var(--alert-yellow); }
  .narrative .narr-red    { color: var(--alert-red); border-color: var(--alert-red); }
  .narrative .narr-gray   { color: var(--muted); }

  /* threshold-card 顶部口径前言（v1.7） */
  .threshold-preface {
    margin: 8px 0 16px; padding: 12px 14px;
    background: var(--formula-bg); border-left: 3px solid var(--formula-border);
    font-size: 13px; line-height: 1.65; color: var(--muted-strong);
  }
  .threshold-preface strong { color: var(--ink); }

  /* v1.17：可下钻行 → 整行 onclick + 维度文字蓝色暗示（取代旧 › caret） */
  .data-table tr.expandable { cursor: pointer; transition: background .12s; }
  .data-table tr.expandable:hover { background: var(--th-bg); }
  .data-table .dim-link { color: var(--link); font-weight: 600; }
  .data-table tr.expandable:hover .dim-link { text-decoration: underline; }

  /* v1.11 问题导向叙述（嵌入卡片顶部）— v1.17 去左侧竖线，靠背景区分 */
  .problem-narrative {
    margin: 6px 0 14px; padding: 12px 16px;
    background: var(--formula-bg);
    border-radius: 8px; font-size: 13px; line-height: 1.85;
  }
  .problem-narrative .prob-line { margin: 4px 0; color: var(--ink); }
  .problem-narrative .prob-line strong { color: var(--ink); margin-right: 6px; font-weight: 600; }
  .problem-narrative .prob-ok { color: var(--muted); }
  .problem-narrative .prob-ok strong { color: var(--alert-green); }
  /* v1.12：问题诊断条目：名字纯色、数字着色，无边框无背景 */
  .prob-item {
    display: inline-block; margin-right: 14px;
    font-size: 13px; line-height: 1.9;
    white-space: nowrap;
  }
  .prob-name { color: var(--ink); font-weight: 400; }
  .prob-num {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
    margin-left: 2px;
  }
  .prob-num-yellow { color: var(--alert-yellow); }
  .prob-num-red    { color: var(--alert-red); }
  .prob-num-blue   { color: var(--alert-blue); }
  .prob-num-gray   { color: var(--muted); }

  /* v1.16：飞书文档式三栏布局 = 左 TOC | 中内容 | 右上 fixed 浮按钮 */
  .page { display: block; }
  .page[hidden] { display: none; }

  /* 左：常驻 TOC */
  .app-toc {
    grid-area: toc;
    position: sticky; top: 24px;
    align-self: start;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    padding: 24px 0 24px 22px;
    font-size: 13px;
  }
  .app-toc-title {
    font-size: 11px; letter-spacing: .12em;
    color: var(--muted); text-transform: uppercase;
    padding: 0 16px 8px; margin: 0;
  }
  .app-toc ul { list-style: none; padding: 0; margin: 0; }
  .app-toc a {
    display: block; padding: 10px 16px;
    color: var(--muted-strong); text-decoration: none;
    border-left: 2px solid transparent;
    font-weight: 500; line-height: 1.4;
  }
  .app-toc a:hover:not(.active) { background: var(--th-bg); color: var(--ink); }
  .app-toc a.active {
    border-left-color: var(--alert-blue);
    background: rgba(37, 99, 235, .05);
    color: var(--alert-blue);
    font-weight: 700;
  }

  /* 中：主内容列 */
  .app-main {
    grid-area: main;
    max-width: 940px; min-width: 0;  /* v1.25：886→940，吸收 TOC -42 + gap -8 = 50px 让出空间 */
    padding: 24px 22px 40px;
  }
  /* 说明页（参考表场景）需要更宽布局；主报告/下钻保留 880 阅读宽度 */
  .app-main:has(#page-info:not([hidden])) {
    max-width: 1140px;
  }
  /* 子页（说明/下钻）：隐藏 TOC + 汉堡，main 占满，与 @media 规则正交 */
  body:has(#page-main[hidden]) {
    grid-template-columns: 1fr;
    grid-template-areas: "main";
  }
  body:has(#page-main[hidden]) .app-toc,
  body:has(#page-main[hidden]) .toc-burger {
    display: none !important;
  }
  body:has(#page-main[hidden]) .app-main {
    justify-self: center;  /* 子页 main 在单列 grid 中水平居中 */
  }

  /* 右上：fixed 浮按钮组（全局唯一）— 顺序：主题 → 说明 → 反馈 */
  .app-actions {
    position: fixed; top: 14px; right: 11px; z-index: 100;  /* v1.24：14→11，往右靠 3px */
    display: flex; flex-direction: column; gap: 6px;
  }
  .app-actions button,
  .app-actions .btn-feedback {
    background: var(--card-bg); border: 1px solid var(--rule);
    border-radius: 999px;
    font-family: var(--sans-zh); font-size: 11.5px; font-weight: 500;
    color: var(--muted-strong); cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center;
    line-height: 1; white-space: nowrap;
    box-shadow: var(--card-shadow);
    text-decoration: none;
  }
  .app-actions button:hover,
  .app-actions .btn-feedback:hover { color: var(--ink); border-color: var(--ink); }
  .app-actions .btn-info { padding: 6px 14px; min-width: 64px; }
  .app-actions .btn-theme,
  .app-actions .btn-feedback { padding: 6px 10px; min-width: 64px; }
  .app-actions .btn-theme svg,
  .app-actions .btn-feedback svg { width: 16px; height: 16px; color: var(--muted-strong); }
  .app-actions .btn-theme:hover svg,
  .app-actions .btn-feedback:hover svg { color: var(--ink); }

  /* 标题容器（v1.23：全断点 sticky + 缩小 + 毛玻璃，不抢戏永远可见） */
  .page-toolbar {
    position: sticky;
    top: 0;
    z-index: 50;
    padding: 8px 0;
    margin: 0 0 14px;
    background: rgba(var(--paper-rgb), .85);
    backdrop-filter: saturate(180%) blur(10px);
    -webkit-backdrop-filter: saturate(180%) blur(10px);
    border-bottom: 1px solid var(--rule);
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .toolbar-title { min-width: 0; overflow: hidden; flex: 1; }
  .toolbar-title .kicker { margin: 0 0 2px; }
  .toolbar-title h1, .toolbar-title h2 {
    margin: 0;
    font-family: var(--serif-zh);
    font-weight: 600;
    color: var(--ink);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .toolbar-title h1 { font-size: 16px; font-weight: 600; }
  .toolbar-title h2 { font-size: 15px; }
  /* v1.22：H1 旁的关键指标 meta（替代独立状态条卡片，省一行） */
  .toolbar-title h1 .page-meta {
    margin-left: 12px;
    font-family: var(--sans-zh);
    font-size: 12px;
    font-weight: 400;
    color: var(--muted);
    letter-spacing: 0;
    vertical-align: middle;
    font-variant-numeric: tabular-nums;
  }

  /* 子页返回按钮（紧邻标题左侧） */
  .toolbar-back {
    background: var(--ink); color: var(--paper);
    border: 0; border-radius: 999px;
    padding: 9px 18px;
    font-family: var(--sans-zh); font-size: 13px; font-weight: 600;
    cursor: pointer; box-shadow: var(--card-shadow);
    white-space: nowrap; flex-shrink: 0;
    display: inline-flex; align-items: center; gap: 4px;
  }
  .toolbar-back:hover { opacity: .85; }

  /* 汉堡按钮（中等屏 + 移动端可见） */
  .toc-burger {
    display: none;
    background: var(--card-bg); border: 1px solid var(--rule);
    border-radius: 999px;
    padding: 7px 12px; font-size: 12px; cursor: pointer;
    color: var(--muted-strong); flex-shrink: 0;
    font-family: var(--sans-zh);
    align-items: center; gap: 4px;
  }
  .toc-burger:hover { color: var(--ink); border-color: var(--ink); }
  .toc-overlay {
    display: none;
    position: fixed; inset: 0; background: rgba(0,0,0,.35); z-index: 199;
  }

  /* 中等屏：TOC 折叠为浮层 */
  @media (max-width: 1024px) {
    body { grid-template-columns: 1fr; grid-template-areas: "main"; padding: 0 0 30px; }
    .app-toc {
      position: fixed; top: 0; left: 0; bottom: 0; width: 280px;
      transform: translateX(-100%); transition: transform .25s ease;
      background: var(--paper); z-index: 200;
      padding: 60px 0 24px 0;
      border-right: 1px solid var(--rule);
      max-height: 100vh;
    }
    .app-toc.open { transform: translateX(0); }
    .app-toc.open ~ .toc-overlay { display: block; }
    .toc-burger { display: inline-flex; }
    .app-main { padding: 16px 22px 30px; max-width: 100%; }
  }

  /* 移动端：进一步压缩 */
  @media (max-width: 720px) {
    .app-main { padding: 12px 14px 24px; }
    .app-actions {
      top: 8px; right: 8px;
      flex-direction: row; gap: 4px;
    }
    .app-actions .btn-info,
    .app-actions .btn-theme,
    .app-actions .btn-feedback { padding: 4px 10px; min-width: 52px; font-size: 11px; }
    .page-toolbar { padding: 6px 0; gap: 10px; }
    .toolbar-title h1 { font-size: 14px; }
    .toolbar-title h2 { font-size: 13px; }
    .toolbar-title h1 .page-meta { display: none; }  /* 移动端隐藏 meta，给标题让位 */
    .toolbar-title .kicker { display: none; }
    .toolbar-back { padding: 7px 13px; font-size: 12px; }
    .toc-burger { padding: 5px 10px; font-size: 11px; }
  }

  /* 打印：隐藏导航与浮按钮 */
  @media print {
    body { display: block; max-width: 100%; padding: 0; }
    .app-toc, .app-actions, .toc-burger, .toc-overlay { display: none !important; }
    .app-main { max-width: 100%; padding: 0; }
    .page-toolbar { position: static; }
  }
  /* 阈值对照单元格：数值占左侧自然宽度，色块绝对定位贴右边缘，整列自动对齐 */
  .threshold-table .th-cell {
    position: relative;
    padding-right: 28px;
    white-space: nowrap;
  }
  .threshold-table .th-cell .th-val {
    display: inline-block;
  }
  .threshold-table .th-cell .dot {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    margin: 0;
  }
  .threshold-note {
    margin-top: 12px;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.7;
  }
  .formula-list {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .formula-item {
    display: flex;
    gap: 14px;
    padding: 8px 12px;
    background: var(--formula-bg);
    border-left: 3px solid var(--formula-border);
    font-size: 12.5px;
    line-height: 1.55;
  }
  .formula-name {
    flex: 0 0 130px;
    font-weight: 600;
    color: var(--ink);
  }
  .formula-text {
    color: var(--muted-strong);
  }
  @media (max-width: 720px) {
    .formula-item { flex-direction: column; gap: 4px; padding: 8px 10px; }
    .formula-name { flex: none; }
  }

  footer {
    grid-column: 1 / -1;
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    margin-top: 28px;
  }

  .empty-data { color: var(--alert-gray); font-style: italic; margin: 12px 0; }

  /* 移动端：卡片 + 表格 + 状态条 */
  @media (max-width: 720px) {
    .card { padding: 18px 18px; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; }
    .data-table { font-size: 12px; }
    .data-table th, .data-table td { padding: 7px 8px; }
    .status-bar { padding: 8px 12px; gap: 12px; font-size: 12px; }
    .status-bar .toggle-threshold { margin-left: 0; }
    .info::after { max-width: 240px; }
  }

  /* v1.18：表头一键排序（合计行 .row-total 固定第一行不参与排序，全局视觉锚点） */
  .data-table th.sortable {
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
    transition: color .15s ease;
  }
  .data-table th.sortable:hover { color: var(--ink); }
  .data-table th.sortable .sort-ind {
    display: inline-block;
    width: 0;
    height: 0;
    margin-left: 4px;
    vertical-align: middle;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    opacity: 0;  /* v1.25：默认隐藏，hover 列头时浮现 */
    transition: opacity .15s ease, transform .15s ease;
  }
  .data-table th.sortable:hover .sort-ind { opacity: .5; }
  .data-table th.sortable[data-sort-dir="asc"] .sort-ind {
    border-bottom: 5px solid var(--alert-blue);
    opacity: 1;
  }
  .data-table th.sortable[data-sort-dir="desc"] .sort-ind {
    border-top: 5px solid var(--alert-blue);
    opacity: 1;
  }
  .data-table th.sortable:not([data-sort-dir]) .sort-ind {
    border-bottom: 5px solid currentColor;
  }
  /* 合计行视觉强调：粗体 + 顶部对比色（与可排序行区分） */
  .data-table tr.row-total td {
    font-weight: 700;
    background: var(--th-bg);
  }
  /* v1.19：下钻页内置 sticky TOC（drill-toc）+ 主区双栏布局 ──
     借鉴 diagnose-period-trend 的子页视觉，宽度 / 间距与主页 .app-toc 对齐 */
  .drill-layout {
    display: grid;
    grid-template-columns: 180px 1fr;
    gap: 16px;
    align-items: start;
  }
  .drill-toc {
    position: sticky;
    top: 24px;
    align-self: start;
    padding: 12px 12px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 13px;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
  }
  .drill-toc-title {
    font-weight: 700;
    color: var(--text);
    padding-bottom: 8px;
    margin-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }
  .drill-toc ol {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .drill-toc li {
    margin: 2px 0;
  }
  .drill-toc a {
    display: block;
    padding: 6px 8px;
    color: var(--muted-strong, var(--text));
    text-decoration: none;
    border-left: 2px solid transparent;
    border-radius: 4px;
  }
  .drill-toc a:hover {
    background: var(--th-bg);
    color: var(--text);
  }
  .drill-toc a.active {
    color: var(--accent);
    border-left-color: var(--accent);
    background: var(--th-bg);
  }
  .drill-main {
    min-width: 0;
  }
  @media (max-width: 1024px) {
    .drill-layout {
      grid-template-columns: 1fr;
    }
    .drill-toc {
      position: static;
      max-height: none;
    }
  }
</style>
</head>
<body>
<script>
  // v1.16：主题切换 + 多页面切换 + 三栏布局 TOC（IntersectionObserver + 浮层）
  const SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
  const MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

  function themeIcon(theme) {
    return theme === 'midnight' ? SUN_SVG : MOON_SVG;
  }
  function syncThemeButtons(theme) {
    const tip = theme === 'midnight' ? '切换墨水主题' : '切换午夜主题';
    document.querySelectorAll('.btn-theme').forEach(b => {
      b.innerHTML = themeIcon(theme);
      b.title = tip;
      b.setAttribute('aria-label', tip);
    });
  }
  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'midnight' ? 'ink' : 'midnight';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('diag-theme', next); } catch(e) {}
    syncThemeButtons(next);
  }
  function showPage(pageId) {
    document.querySelectorAll('section.page').forEach(p => {
      p.hidden = (p.id !== pageId);
    });
    window.scrollTo(0, 0);
    // 切到子页时清除 TOC active；observer 在回到主页后自然恢复
    if (pageId !== 'page-main') {
      document.querySelectorAll('.app-toc a.active').forEach(a => a.classList.remove('active'));
    }
  }
  function toggleToc() {
    document.querySelector('.app-toc')?.classList.toggle('open');
  }
  function toggleInfo() {
    const info = document.getElementById('page-info');
    showPage(info && !info.hidden ? 'page-main' : 'page-info');
  }
  function navJump(href) {
    document.querySelector('.app-toc')?.classList.remove('open');
    showPage('page-main');
    setTimeout(() => {
      const el = document.querySelector(href);
      if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
    }, 50);
    return false;
  }
  // 点 overlay 关闭浮层
  document.addEventListener('click', (e) => {
    if (e.target && e.target.classList && e.target.classList.contains('toc-overlay')) {
      document.querySelector('.app-toc')?.classList.remove('open');
    }
  });
  // 当前板块高亮：IntersectionObserver 监听 .card[id^="section-"]
  (function initTocObserver() {
    function attach() {
      const links = new Map();
      document.querySelectorAll('.app-toc a[href^="#section-"]').forEach(a => {
        links.set(a.getAttribute('href').slice(1), a);
      });
      if (!links.size) return;
      const obs = new IntersectionObserver((entries) => {
        const main = document.getElementById('page-main');
        if (main && main.hidden) return;  // 仅主页生效
        entries.forEach(e => {
          if (e.isIntersecting) {
            links.forEach(a => a.classList.remove('active'));
            const link = links.get(e.target.id);
            if (link) link.classList.add('active');
          }
        });
      }, { rootMargin: '-10% 0px -70% 0px', threshold: 0 });
      document.querySelectorAll('.card[id^="section-"]').forEach(c => obs.observe(c));
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', attach);
    } else {
      attach();
    }
  })();
  // v1.19：下钻页内置 drill-toc 高亮（每个 drill 子页独立 IntersectionObserver）
  function initDrillToc(tocEl) {
    const links = Array.from(tocEl.querySelectorAll('.drill-toc-link'));
    if (!links.length) return;
    const linkByTarget = {};
    links.forEach(a => {
      const t = a.getAttribute('data-target');
      if (t) linkByTarget[t] = a;
    });
    const scope = tocEl.closest('.page') || document;
    const cards = links
      .map(a => scope.querySelector('#' + CSS.escape(a.getAttribute('data-target'))))
      .filter(Boolean);
    if (!cards.length) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        const id = e.target.getAttribute('id');
        const a = linkByTarget[id];
        if (!a) return;
        if (e.isIntersecting) {
          links.forEach(l => l.classList.remove('active'));
          a.classList.add('active');
        }
      });
    }, { rootMargin: '-80px 0px -60% 0px', threshold: 0 });
    cards.forEach(c => io.observe(c));
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.drill-toc').forEach(initDrillToc);
  });

  // 启动恢复主题 + 同步图标
  (function initTheme() {
    let theme = 'ink';
    try {
      theme = localStorage.getItem('diag-theme') || 'ink';
    } catch(e) {}
    document.documentElement.setAttribute('data-theme', theme);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => syncThemeButtons(theme));
    } else {
      syncThemeButtons(theme);
    }
  })();

  // v1.18：表头一键排序（合计行 .row-total 固定第一行不参与排序，全局视觉锚点）
  function sortTable(th) {
    const table = th.closest('table.data-table');
    if (!table) return;
    const tbody = table.tBodies[0];
    if (!tbody) return;

    const headerCells = Array.from(th.parentNode.children);
    const colIndex = headerCells.indexOf(th);
    const colType = th.dataset.colType || 'text';

    // 切换排序方向：未排序 → 降序 → 升序 → 降序（默认 DESC，符合"大头优先"直觉）
    const cur = th.dataset.sortDir || '';
    const next = (cur === 'desc') ? 'asc' : 'desc';

    // 清除其它列的方向标记，仅当前列保留
    headerCells.forEach(h => { if (h !== th) delete h.dataset.sortDir; });
    th.dataset.sortDir = next;

    // 分离合计行（视觉锚点，不参与排序）
    const allRows = Array.from(tbody.rows);
    const totalRows = allRows.filter(r => r.classList.contains('row-total'));
    const sortable = allRows.filter(r => !r.classList.contains('row-total'));

    // 单元格值解析：从 .num-val 优先取数字文本，否则取 textContent
    function parseCell(td, type) {
      const node = td.querySelector('.num-val') || td;
      const raw = (node.textContent || '').trim();
      if (raw === '' || raw === '—') {
        // 空值排序时统一沉到最末（无论升降序）—— 用 ±Infinity 不易处理，用大数标记 + dir 一起判
        return null;
      }
      if (type === 'text') return raw;
      // 去千分位 + 百分号；保留负号
      const num = parseFloat(raw.replace(/,/g, '').replace('%', ''));
      return isNaN(num) ? null : num;
    }

    sortable.sort((rowA, rowB) => {
      const va = parseCell(rowA.cells[colIndex], colType);
      const vb = parseCell(rowB.cells[colIndex], colType);
      // 空值（null）统一沉底，与方向无关
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      if (colType === 'text') {
        return next === 'asc' ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
      }
      return next === 'asc' ? va - vb : vb - va;
    });

    // 重组：合计行先（保持锚点），再排序后的数据行
    const frag = document.createDocumentFragment();
    totalRows.forEach(r => frag.appendChild(r));
    sortable.forEach(r => frag.appendChild(r));
    tbody.appendChild(frag);
  }
  // 暴露到全局，方便 onclick 调用
  window.sortTable = sortTable;
</script>
"""

# ── 主题模块导出（供其他 skill 复用）───────────────────────────────────────────────
# 提取自上面的 <style> 块（行 13-72），供非 render_page() 路径复用
THEME_CSS = """
  /* 主题：墨水经典（默认） */
  :root {
    --ink: #1f2937;
    --ink-rgb: 31, 41, 55;
    --paper: #f1efea;
    --paper-rgb: 241, 239, 234;
    --card-bg: #ffffff;
    --card-shadow: 0 2px 14px rgba(20, 24, 32, .07);
    --rule: rgba(31, 41, 55, .14);
    --muted: #6b7280;
    --muted-strong: #4b5563;
    --th-bg: #ece9e1;
    --th-text: #374151;
    --row-border: #e5e0d3;
    --pill-bg: #e1ddd0;
    --pill-text: #3a3528;
    --pill-warn-bg: #fef3c7;
    --pill-warn-text: #92400e;
    --kicker: #94785a;
    --link: #2563eb;
    --alert-blue: #2563eb;
    --alert-green: #047857;
    --alert-yellow: #b45309;
    --alert-red: #b91c1c;
    --alert-gray: #9ca3af;
    --formula-bg: #f5f3ec;
    --formula-border: #d6d0bc;
    --tip-bg: #1f2937;
    --tip-text: #f9fafb;
  }
  /* 主题：午夜（暗色） */
  html[data-theme="midnight"] {
    --ink: #e2e8f0;
    --ink-rgb: 226, 232, 240;
    --paper: #0b1220;
    --paper-rgb: 11, 18, 32;
    --card-bg: #131b2c;
    --card-shadow: 0 2px 16px rgba(0, 0, 0, .35);
    --rule: rgba(226, 232, 240, .14);
    --muted: #94a3b8;
    --muted-strong: #cbd5e1;
    --th-bg: #1c2540;
    --th-text: #cbd5e1;
    --row-border: #1e2a47;
    --pill-bg: #1e2a47;
    --pill-text: #cbd5e1;
    --pill-warn-bg: #422c10;
    --pill-warn-text: #fbbf24;
    --kicker: #a78668;
    --link: #60a5fa;
    --alert-blue: #60a5fa;
    --alert-green: #34d399;
    --alert-yellow: #fbbf24;
    --alert-red: #f87171;
    --alert-gray: #64748b;
    --formula-bg: #0e1626;
    --formula-border: #1e2a47;
    --tip-bg: #f1efea;
    --tip-text: #1f2937;
  }
"""

# 提取防 FOUC 脚本（行 1012-1023），放在 <head> 末尾
THEME_INIT_SCRIPT = """<script>
(function initTheme() {
  let theme = 'ink';
  try { theme = localStorage.getItem('diag-theme') || 'ink'; } catch(e) {}
  document.documentElement.setAttribute('data-theme', theme);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => syncThemeButtons(theme));
  } else {
    syncThemeButtons(theme);
  }
})();
</script>"""

# 提取主题切换 JS（行 900-920），包括 SVG 图标定义
THEME_JS = """
const SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
const MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

function themeIcon(theme) {
  return theme === 'midnight' ? SUN_SVG : MOON_SVG;
}
function syncThemeButtons(theme) {
  const tip = theme === 'midnight' ? '切换墨水主题' : '切换午夜主题';
  document.querySelectorAll('.btn-theme').forEach(b => {
    b.innerHTML = themeIcon(theme);
    b.title = tip;
    b.setAttribute('aria-label', tip);
  });
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'midnight' ? 'ink' : 'midnight';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('diag-theme', next); } catch(e) {}
  syncThemeButtons(next);
}
"""

# SVG 按钮工厂（返回带 onclick 的按钮 HTML）
def theme_toggle_btn() -> str:
    """返回主题切换按钮 HTML（SVG 图标版，ink↔midnight）。"""
    return ('<button class="btn-theme" onclick="toggleTheme()" '
            'title="切换午夜主题" aria-label="切换午夜主题"></button>')
