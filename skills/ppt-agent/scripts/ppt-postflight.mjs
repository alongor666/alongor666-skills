#!/usr/bin/env node
// ppt-agent · Postflight 校验闸（机械约束自动化 · 不靠 AI 自觉）
// 用法: node ppt-postflight.mjs <deck.html>
// 退出码: 0=PASS · 1=FAIL(阻断交付) · 2=用法/读取错误
//
// 为什么是脚本而非 SKILL.md 条款: Prompt 禁令遵从率不稳(~50%),机械可判定的约束必须代码兜底。
// 判断性约束(数据真实性/受众对齐)留在 SKILL.md gate,本脚本只管能 regex 判定的。

import { readFileSync } from 'node:fs';

const file = process.argv[2];
if (!file) { console.error('用法: node ppt-postflight.mjs <deck.html>'); process.exit(2); }
let html;
try { html = readFileSync(file, 'utf8'); }
catch { console.error(`✗ 读不到文件: ${file}`); process.exit(2); }
html = html.replace(/<!--[\s\S]*?-->/g, '');   // 去 HTML 注释,避免模板注释内的 <section>/[必填] 示例污染检查

const errors = [];   // 机械可判定 → 阻断
const warns  = [];   // 需人工确认 → 不阻断

// 1) 占位符残留（模板没填完）
for (const p of ['[必填]', 'SLIDES_HERE', 'PLACEHOLDER', 'replace_me', 'Lorem ipsum', '替换为 PPT', 'XXXX']) {
  if (html.includes(p)) errors.push(`占位符残留: "${p}"`);
}

// 2) 页面与节奏
const sections = [...html.matchAll(/<section class="slide([^"]*)"/g)].map(m => m[1]);
const nSlides = sections.length;
if (nSlides === 0) errors.push('未找到任何 <section class="slide">');
const tones = sections.map(s => /\bdark\b/.test(s) ? 'D' : 'L');
let run = 1;
for (let i = 1; i < tones.length; i++) {
  if (tones[i] === tones[i - 1]) { run++; if (run >= 3) warns.push(`连续 ${run} 页同色调(${tones[i]}) 约在第 ${i + 1} 页 → 检查 dark/light 节奏`); }
  else run = 1;
}

// 3) 页码连续性（chrome 右上 "NN / MM"）
const pages = [...html.matchAll(/(\d{1,2}) \/ (\d{1,2})/g)].map(m => [+m[1], +m[2]]);
if (pages.length) {
  const denoms = [...new Set(pages.map(p => p[1]))];
  if (denoms.length > 1) errors.push(`页码分母不统一: ${denoms.join(' / ')}`);
  else if (denoms[0] !== nSlides) errors.push(`页码分母 ${denoms[0]} ≠ 实际页数 ${nSlides}`);
  const nums = pages.map(p => p[0]);
  const bad = nums.findIndex((n, i) => n !== i + 1);
  if (bad !== -1) errors.push(`页码序号不连续: 第 ${bad + 1} 个应为 ${bad + 1}，实为 ${nums[bad]}`);
}

// 4) emoji 白名单（报告语言红线: 仅四级亮灯 🟢🔵🟡🔴）
const ALLOW = new Set(['🟢', '🔵', '🟡', '🔴']);
const badEmoji = new Set();
for (const m of html.matchAll(/\p{Extended_Pictographic}/gu)) if (!ALLOW.has(m[0])) badEmoji.add(m[0]);
if (badEmoji.size) warns.push(`非白名单 emoji(仅允许 🟢🔵🟡🔴): ${[...badEmoji].join(' ')}`);

// 5) 外部依赖 + 单文件自检
const cdnHosts = [...new Set([...html.matchAll(/https?:\/\/([^/"')\s]+)/g)]
  .map(m => m[1]).filter(h => /font|cdn|unpkg|jsdelivr|googleapis|gstatic/.test(h)))];
const localRefs = [...new Set([...html.matchAll(/(?:src|href)="(\.\/[^"]+|assets\/[^"]+|images\/[^"]+|[^":/]+\.(?:js|css))"/g)].map(m => m[1]))];
if (localRefs.length) warns.push(`本地文件引用(非单文件,file:// 下 CORS 可能失败,考虑内联): ${localRefs.join(', ')}`);

// 6) 报告语言红线（英文术语缩写堆砌）
const REDLINE = [' LR ', ' DW ', 'cohort', 'IBNR', 'emergence', 'burning cost', 'fallback', 'chain ladder', ' MoM', ' YoY', ' YTD', 'applied_LR'];
const termHits = REDLINE.filter(t => html.includes(t));
if (termHits.length) warns.push(`疑似英文术语(应中文全称,见 report-language-redline): ${termHits.map(s => s.trim()).join(', ')}`);

// 7) 敏感数据
const plates = html.match(/[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][·\-]?[A-Z0-9]{4,5}/g);
const phones = html.match(/\b1[3-9]\d{9}\b/g);
if (plates) warns.push(`含疑似车牌 ${[...new Set(plates)].length} 种 → 确认是否需脱敏`);
if (phones) errors.push(`含疑似手机号 ${[...new Set(phones)].length} 种 → 必须脱敏`);

// ── 输出 ──
console.log(`\n=== ppt-agent postflight: ${file} ===`);
console.log(`页数 ${nSlides} · 节奏 ${tones.join('')}`);
console.log(`外部依赖: ${cdnHosts.length ? cdnHosts.join(', ') : '无'}`);
console.log(`本地引用: ${localRefs.length ? localRefs.join(', ') : '无(单文件 ✓)'}`);
if (warns.length)  { console.log('\n⚠ 警告(人工确认,不阻断):'); warns.forEach(w => console.log('  · ' + w)); }
if (errors.length) {
  console.log('\n✗ 阻断错误:'); errors.forEach(e => console.log('  · ' + e));
  console.log('\n结果: FAIL — 修复后重跑,不得声称完成\n');
  process.exit(1);
}
console.log(`\n结果: PASS${warns.length ? '(带警告,逐条确认)' : ''}\n`);
process.exit(0);
