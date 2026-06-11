#!/usr/bin/env node
/*
 * 视觉卡片验收 driver（零 npm 依赖，需 Node ≥ 21 内置 WebSocket/fetch + 系统 Chrome）
 * 用法: node driver.mjs <视觉卡片.html> [期望页数] [--min 80] [--max 100] [--pdf out.pdf]
 * 检查: ① 每页填充率落在 [min,max]% ② 零溢出 ③ 真实 PDF 页数 == 期望
 * 退出码: 0=全部通过, 1=有不达标项, 2=运行错误
 */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { writeFileSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { extname, resolve, dirname, basename, join } from 'node:path';

const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const file = argv.find(a => !a.startsWith('--') && a !== flag('--min') && a !== flag('--max') && a !== flag('--pdf'));
if (!file) { console.error('用法: node driver.mjs <视觉卡片.html> [期望页数] [--min 80] [--max 100] [--pdf out.pdf]'); process.exit(2); }
const positional = argv.filter(a => !a.startsWith('--'));
const expectPages = positional[1] ? Number(positional[1]) : null;
const MIN = Number(flag('--min', 80)), MAX = Number(flag('--max', 100));
const pdfOut = flag('--pdf', null);

const abs = resolve(file);
const dir = dirname(abs), name = basename(abs);
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg' };

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  // 逐一探测：macOS 安装位（existsSync）→ Linux/通用 PATH 内名称；
  // 全失败回退 mac 默认路径（spawn 失败报「Chrome CDP 未就绪」，与原版一致）
  const macApps = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const p of macApps) if (existsSync(p)) return p;
  const names = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'];
  for (const d of (process.env.PATH || '').split(':')) {
    if (!d) continue;
    for (const n of names) if (existsSync(join(d, n))) return join(d, n);
  }
  return macApps[0];
}

const log = (...a) => console.log(...a);
let server, chrome, ws, cdpId = 0;
const pending = new Map();
const cleanup = () => { try { ws?.close(); } catch {} try { chrome?.kill('SIGKILL'); } catch {} try { server?.close(); } catch {} };

function cdp(method, params = {}, sessionId) {
  const id = ++cdpId;
  return new Promise((res, rej) => {
    pending.set(id, { res, rej });
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('CDP timeout: ' + method)); } }, 30000);
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  // 1) 静态 server
  server = createServer(async (req, res) => {
    try {
      const p = resolve(dir, decodeURIComponent(req.url.split('?')[0]).replace(/^\//, ''));
      if (!p.startsWith(dir)) { res.writeHead(403).end(); return; }
      const body = await readFile(p);
      res.writeHead(200, { 'Content-Type': MIME[extname(p)] || 'application/octet-stream' });
      res.end(body);
    } catch { res.writeHead(404).end(); }
  });
  const port = await new Promise(r => server.listen(0, '127.0.0.1', () => r(server.address().port)));
  const url = `http://127.0.0.1:${port}/${encodeURIComponent(name)}`;

  // 2) 系统 Chrome + CDP
  const dbg = 9000 + Math.floor((Date.now() % 900));
  const udd = `/tmp/cardverify-${process.pid}`;
  chrome = spawn(findChrome(), [
    '--headless=new', `--remote-debugging-port=${dbg}`, `--user-data-dir=${udd}`,
    '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--hide-scrollbars',
  ], { stdio: 'ignore' });

  let wsUrl;
  for (let i = 0; i < 60; i++) {
    try { const v = await (await fetch(`http://127.0.0.1:${dbg}/json/version`)).json(); wsUrl = v.webSocketDebuggerUrl; break; }
    catch { await sleep(250); }
  }
  if (!wsUrl) throw new Error('Chrome CDP 未就绪');

  ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = e => rej(new Error('ws error')); });
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(m.error.message)) : res(m.result); }
  };

  // 3) 开 tab 导航
  const { targetId } = await cdp('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp('Target.attachToTarget', { targetId, flatten: true });
  await cdp('Page.enable', {}, sessionId);
  await cdp('Page.navigate', { url }, sessionId);
  await sleep(1500); // 等 load + deck 脚本(4s 内的 fit) 渲染稳定

  // 4) 填充率
  const fillExpr = `(()=>{const ps=[...document.querySelectorAll('.page')];return ps.map((p,i)=>{const inner=p.querySelector('.inner');const ir=inner.getBoundingClientRect();let mb=0;inner.querySelectorAll('*').forEach(c=>{const b=c.getBoundingClientRect().bottom-ir.top;if(b>mb)mb=b;});return{p:i+1,fill:Math.round(mb/ir.height*100),overflow:mb>ir.height+2};});})()`;
  const ev = await cdp('Runtime.evaluate', { expression: fillExpr, returnByValue: true }, sessionId);
  const rows = ev.result.value;

  // 5) 真实 PDF
  const pdf = await cdp('Page.printToPDF', { preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false, marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0 }, sessionId);
  const buf = Buffer.from(pdf.data, 'base64');
  const pdfPages = (buf.toString('latin1').match(/\/Type\s*\/Page[^s]/g) || buf.toString('latin1').match(/\/MediaBox/g) || []).length;
  if (pdfOut) writeFileSync(pdfOut, buf);

  // 6) 报告
  log(`\n  视觉卡片验收 · ${name}`);
  log('  ' + '─'.repeat(46));
  let bad = 0;
  for (const r of rows) {
    const okFill = r.fill >= MIN && r.fill <= MAX;
    const okOver = !r.overflow;
    const ok = okFill && okOver;
    if (!ok) bad++;
    log(`  P${String(r.p).padStart(2)}  填充 ${String(r.fill).padStart(3)}%  ${r.overflow ? '溢出!' : '无溢出'}  ${ok ? '✓' : '✗ ' + (!okFill ? `需 ${MIN}-${MAX}%` : '有溢出')}`);
  }
  log('  ' + '─'.repeat(46));
  const okPages = expectPages == null || pdfPages === expectPages;
  log(`  PDF 页数 = ${pdfPages}${expectPages != null ? ` / 期望 ${expectPages}  ${okPages ? '✓' : '✗'}` : ''}`);
  log(`  ${rows.length} 页中 ${rows.length - bad} 页达标` + (pdfOut ? ` · PDF→ ${pdfOut}` : ''));
  log('  ' + (bad === 0 && okPages ? 'PASS ✅' : 'FAIL ❌') + '\n');

  cleanup();
  process.exit(bad === 0 && okPages ? 0 : 1);
}

main().catch(e => { console.error('错误:', e.message); cleanup(); process.exit(2); });
