#!/usr/bin/env node
/* ===========================================================================
 * bundle.mjs —— 把分离式 deck（html + 外链 css/js）打包成「自包含单文件」用于分发
 *
 *   为什么需要：本基座是分离式四件套（.html + deck-16x9.css + report-skin*.css + deck-16x9.js），
 *   外链是相对路径。只把那个 .html 发到别的电脑（微信/邮件/U盘）时，外链 404 →
 *   ① 无机制 CSS：每页 1280px 不缩放、撑爆窗口 → 文字「错位」；② 无翻页 JS → 「翻不动」。
 *   本脚本把所有本地 css/js 内联进单个 .html，发这一个文件到任意浏览器/设备都一致、能翻页。
 *
 *   用法：
 *     node bundle.mjs <input.html> [output.html] [--webfont]
 *       input.html  分离式成品（外链 css/js 与它同目录）
 *       output.html 可选，默认 <input>.standalone.html（同目录）
 *       --webfont   额外注入思源黑/宋 web 字体（Google 中国官方镜像，国内可达）——
 *                   想要跨平台「像素级」一致时加；不加则依赖系统字体栈（无网络依赖、仍跨平台可读）。
 *   零 npm 依赖（仅 Node 内置 fs/path）。http(s)/data: 外链一律保留不动。
 * ========================================================================= */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve, basename, join } from 'node:path';

const args = process.argv.slice(2);
const flags = new Set(args.filter(a => a.startsWith('--')));
const pos = args.filter(a => !a.startsWith('--'));
const input = pos[0];
if (!input) {
  console.error('用法: node bundle.mjs <input.html> [output.html] [--webfont]');
  process.exit(2);
}
const inPath = resolve(input);
if (!existsSync(inPath)) { console.error('找不到输入文件: ' + inPath); process.exit(2); }

const baseDir = dirname(inPath);
let html = readFileSync(inPath, 'utf8');

const isLocal = (u) => u && !/^(https?:)?\/\//i.test(u) && !/^data:/i.test(u);
let cssCount = 0, jsCount = 0;
const missing = [];

// 关键：内联进 <style>/<script> 时，内容里若出现字面 </style> / </script> 会提前闭合标签，
// 把其后内容溢出成页面可见文本（曾导致多出一页 + 脚本半残）。转义闭合序列即可（CSS/JS 语义等价）。
const safeCss = (s) => s.replace(/<\/style>/gi, '<\\/style>');
const safeJs  = (s) => s.replace(/<\/script>/gi, '<\\/script>');

// —— 内联本地 <link rel="stylesheet" href="x.css"> → <style> ——
html = html.replace(/<link\b[^>]*>/gi, (tag) => {
  if (!/rel\s*=\s*["']?stylesheet/i.test(tag)) return tag;       // 只动样式表 link
  const m = tag.match(/href\s*=\s*["']([^"']+)["']/i);
  if (!m || !isLocal(m[1])) return tag;                          // http/data 外链保留
  const p = resolve(baseDir, m[1]);
  if (!existsSync(p)) { missing.push(m[1]); return tag; }
  cssCount++;
  return `<style data-inlined-from="${m[1]}">\n${safeCss(readFileSync(p, 'utf8'))}\n</style>`;
});

// —— 内联本地 <script src="x.js"></script> → <script> ——
html = html.replace(/<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*><\/script>/gi, (tag, src) => {
  if (!isLocal(src)) return tag;
  const p = resolve(baseDir, src);
  if (!existsSync(p)) { missing.push(src); return tag; }
  jsCount++;
  return `<script data-inlined-from="${src}">\n${safeJs(readFileSync(p, 'utf8'))}\n</script>`;
});

// —— 可选：注入跨平台 web 字体（思源黑/宋 · Google 中国镜像；fallback 栈保证无网仍可读）——
if (flags.has('--webfont')) {
  const wf =
    '<link rel="preconnect" href="https://fonts.googleapis.cn">\n' +
    '<link rel="preconnect" href="https://fonts.gstatic.cn" crossorigin>\n' +
    '<link href="https://fonts.googleapis.cn/css2?family=Noto+Sans+SC:wght@400;500;700;900&family=Noto+Serif+SC:wght@700;900&display=swap" rel="stylesheet">';
  html = /<\/head>/i.test(html) ? html.replace(/<\/head>/i, wf + '\n</head>') : (wf + '\n' + html);
}

const outName = pos[1] || join(baseDir, basename(inPath).replace(/\.html?$/i, '') + '.standalone.html');
const outPath = resolve(outName);
writeFileSync(outPath, html, 'utf8');

const kb = (n) => (n / 1024).toFixed(1) + ' KB';
console.log('  自包含打包 · bundle.mjs');
console.log('  ──────────────────────────────');
console.log('  内联 CSS  : ' + cssCount + ' 个');
console.log('  内联 JS   : ' + jsCount + ' 个');
if (flags.has('--webfont')) console.log('  Web 字体  : 已注入（思源黑/宋 · Google 中国镜像）');
if (missing.length) console.log('  ⚠ 未找到（已保留原样，可能仍缺资源）: ' + missing.join(', '));
console.log('  输出      : ' + outPath + '  (' + kb(Buffer.byteLength(html)) + ')');
console.log('  ✅ 单文件已生成——发这一个文件到任意电脑 / 手机 / 浏览器即可一致显示并翻页。');
