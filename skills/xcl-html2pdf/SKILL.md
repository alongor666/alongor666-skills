---
name: xcl-html2pdf
description: >
  把任意 HTML 报告做成两种版式：印刷级 PDF（A4 纵向、密排打印）或演示级 PPT（16:9 大字号、屏幕/投影）。
  两者都屏幕一屏一页横向翻页、导出一页一张、无半空白页、内容不跨页。
  提供版面盒 CSS（page-deck.css=A4 / deck-16x9.css=16:9）+ 固化字体/字号分级/字色的标准皮肤（report-skin.css）
  + PPT 演示字号叠加（skin-16x9.css）+ 横向翻页脚本，和一个零依赖的验收 driver（实测每页填充率/溢出/真实页数，画幅无关）。
  套标准 class 即得统一的国家地理风视觉，无需自调样式。两套共用 report-skin.css，PDF 与 PPT 视觉天然一致。
  触发词：html2pdf、xcl_html2pdf、做成 PDF、做成 PPT、印刷级报告、演示版、16:9、大屏卡片、投影、keynote、一页一张、横向翻页卡片、A4 卡片、打印成 PDF、标准报告、report to pdf、build report、verify card。
  内容专属的模板（如涡旋诊断卡片）见 company-vortex-card，它在本基座之上。
version: 1.4.0
user_invocable: true
---

# xcl-html2pdf：HTML → 印刷级 PDF / 演示级 PPT 基座

> ## ⚑ 启用时必做：先问用户要 PDF 还是 PPT（默认 PPT）
> A4 PDF 是为打印密排设计的，字号小，放屏幕/投影上太小太挤；PPT（16:9 大字号）才适合屏幕演示。
> **每次启用本技能、动手前先问一句版式选择**，用户没明说就按 **PPT** 走：
>
> | 版式 | 何时用 | 用哪套（四/五件套） | 画幅 |
> |---|---|---|---|
> | **PPT（默认）** | 屏幕 / 投影 / 大屏 / 演讲 | `deck-16x9.css` + `report-skin.css` + `skin-16x9.css` + `deck-16x9.js` + `skeleton-16x9.html` | 16:9（1280×720px） |
> | **PDF** | 打印 / 密排长报告 / 归档 | `page-deck.css` + `report-skin.css` + `deck.js` + `skeleton.html` | A4 纵向（210×297mm） |
>
> 翻页脚本两套不同：**PPT 用 `deck-16x9.js`**（演示导向：← → 翻页 + 底部序号一键直达 + ▦ 缩略图总览、Esc 退出），**PDF 用 `deck.js`**（← → / 点击左右 / 滚轮），互不影响。
>
> 两套**共用 report-skin.css**（配色/字体/组件单一真相源），视觉天然一致；**同一个 `driver.mjs` 验收**（填充率比例法 + `preferCSSPageSize`，画幅无关）。

把任意 HTML 报告做成**屏幕横向一屏一页、导出一页一张**的印刷/演示级文档。分离式架构：

- **版面机制（二选一，勿改）** — `page-deck.css`（A4 纵向盒）或 `deck-16x9.css`（16:9 演示盒）；都含横向翻页 + 导出一页一张。
- **report-skin.css** — 标准视觉：字体、字号分级、语义字色、通用组件，全部**固化**（勿改；改规范只改这一处，PDF/PPT 同步生效）。
- **skin-16x9.css** — 仅 PPT 用的演示字号叠加层：把字号/留白放大到屏幕可读尺度（**叠加在 report-skin 之上，勿改**）。
- **你的 .html** — 只管内容；套标准 class 即得统一的中国国家地理风视觉。

涡旋诊断专属组件（stage/triad/shape/vortex）不在本基座，见 company-vortex-card。

驱动方式：用 `driver.mjs`（Node ≥21 内置 WebSocket/fetch + 系统 Chrome 走 CDP，**零 npm 依赖、无需下载 chromium**）实测每页填充率、溢出、真实 PDF 页数。路径均相对本 skill 目录。

## Prerequisites

```bash
node --version   # 需 ≥ 21（内置全局 WebSocket / fetch；实测 v22.16.0）
# 系统已装 Chrome/Chromium。macOS 默认路径已内置；其它平台用 CHROME 覆盖：
# export CHROME=/usr/bin/google-chrome   (Linux)
```

## 起一个新报告（agent 主路径）

0. **先确认版式**（见顶部 ⚑）：用户没明说默认 **PPT**。下面按版式复制对应骨架与样式表。
1. 复制对应套件到工作目录（`*-deck.css` / `report-skin.css` / `deck.js` 等都**勿改**——版面、视觉规范、翻页机制都在里面）：
   - **PPT（默认）**：`assets/skeleton-16x9.html`、`assets/deck-16x9.css`、`assets/report-skin.css`、`assets/skin-16x9.css`、`assets/deck-16x9.js`。
   - **PDF**：`assets/skeleton.html`、`assets/page-deck.css`、`assets/report-skin.css`、`assets/deck.js`。
2. 把骨架里每个 `<section class="page">` 换成你的内容，按需增删页。**直接套标准 class**（`sec-head` / `lede` / `table.data` / `note` / `quote` / `verdict` / `dossier` / `calc` / `bar-row` …）即得统一字体/字号/字色——不要在自己的 `<style>` 里重定义这些；只有本页特有的图形样式才另写。
3. 版面规则（铁律）：
   - 每页 = 一个 `.page`，内容放进 `.inner`（`overflow:hidden`）。**可用高（填充率分母）：PDF ≈ 1005px@96dpi（A4 210×297mm）；PPT ≈ 604px（16:9 1280×720px）。**
   - 封面用 `.page.cover-page`；要让一张图撑满下半页/下半屏，用 `.inner.flexcol` + 给图加 `class="grow"`。
   - **每页填充率 80–100%、零溢出、内容不跨页。** PPT 可用高更矮、字更大，每页内容量约为 PDF 的六成——每页只讲一件事；不足就补实质内容（小表/说明/引言），不靠拉间距充数。
4. 反复跑 driver 验收到全 PASS（同一个 driver，画幅无关）。**全 PASS 后即开**：agent 跑最终验收时带 `--open`，driver 会在全 PASS 时自动用系统默认浏览器打开成品给用户预览（FAIL 不开）。

## 验收 driver（核心 harness）

```bash
# 用法: node driver.mjs <html> [期望页数] [--min 80] [--max 100] [--pdf out.pdf] [--open]
node driver.mjs assets/skeleton.html 4              # PDF（A4）骨架
node driver.mjs assets/skeleton-16x9.html 4        # PPT（16:9）骨架——同一 driver，画幅无关
node driver.mjs your.html 10 --open                # 全 PASS 后自动在浏览器打开（完成即开）
```

实测输出（本 skill 自带的 skeleton，本机已跑通）：

```
  视觉卡片验收 · skeleton.html
  ──────────────────────────────────────────────
  P 1  填充  95%  无溢出  ✓
  P 2  填充  83%  无溢出  ✓
  P 3  填充 100%  无溢出  ✓
  P 4  填充  85%  无溢出  ✓
  ──────────────────────────────────────────────
  PDF 页数 = 4 / 期望 4  ✓
  4 页中 4 页达标
  PASS ✅
```

PPT（16:9）骨架同样本机跑通：

```
  视觉卡片验收 · skeleton-16x9.html
  ──────────────────────────────────────────────
  P 1  填充  93%  无溢出  ✓
  P 2  填充  90%  无溢出  ✓
  P 3  填充 100%  无溢出  ✓
  P 4  填充  91%  无溢出  ✓
  ──────────────────────────────────────────────
  PDF 页数 = 4 / 期望 4  ✓
  4 页中 4 页达标
  PASS ✅
```

- driver 自启静态 http server + 系统 Chrome（CDP），导航后测每页 `.inner` 子元素底部 / 可用高 = 填充率，再用 `Page.printToPDF`（`preferCSSPageSize`）数真实页数。
- **退出码**：`0`=全部达标、`1`=有页不达标/页数不符、`2`=运行错误。可直接接脚本或 CI。
- 想留存 PDF：`node driver.mjs your.html N --pdf out.pdf`。
- **完成即开**：`--open` 让验收**全 PASS 后**自动用系统默认浏览器打开该 html（FAIL 不开）；跨平台（macOS `open` / Linux `xdg-open` / Windows `start`）。这就是 v1.1.0 约定的"通过后即开"，现已落到 driver。
- 想看真实渲染（截图自查）：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --screenshot=/tmp/preview.png --window-size=1280,1810 --hide-scrollbars \
  "file://$PWD/assets/skeleton.html"
```

## 标准报告皮肤（report-skin.css）

字体/字号分级/字色**全部固化**在这一张样式表里，是单一真相源——改规范只改这里，所有报告同步生效。覆盖：

- **配色**：朱红 `--cng-red #9e1813`、吸积金 `--gold #bd9b52`、玉绿 `--jade #2f6b4f`、铁锈 `--rust #a8431f`（语义色：金=向心、绿=利好、橙/朱红=压力）
- **字体**：正文思源黑（`page-deck.css` 设）、衬线 `.serif` 思源宋
- **字号分级**：封面 h1 60px / sec-title 28px / lede 15px / note 14px / table 13.5px / caption 12px …
- **通用组件**：`rhead`/`rfoot` 页眉脚、`sec-head`+`sec-no` 章节号、`rule` 分隔线、`cover-page` 封面、`dossier` 档案、`table.data` 数据表、`bar-row` 数据条、`verdict`/`vbox` 评分框、`opt-row`/`badge` 对比、`calc` 量级、`quote`/`note` 引文说明、`seal` 印章

> 套这些 class 即得统一视觉；**不要**在报告自己的 `<style>` 里重定义字体/字号/字色。涡旋诊断的额外组件（stage/triad/shape/vortex）由 company-vortex-card 提供。

**PPT 模式的字号在哪改**：`report-skin.css` 是 PDF/PPT 共用的配色/字体/组件单一真相源；PPT 只额外叠加 `skin-16x9.css`，它**只覆盖字号/留白**到演示尺度（正文 19px / 章标 36px / 封面 62px / 表格 18px …，分母 604px），不碰配色与组件结构。要调 PPT 字号只改 `skin-16x9.css` 一处；要调配色/字体仍只改 `report-skin.css`（两版同步生效）。

## 导出 PDF（人工路径）

屏幕翻页（两套脚本不同）：

- **PDF（`deck.js`）**：`← →` / 点击页面左右 / 滚轮 翻页。
- **PPT（`deck-16x9.js`）**：`← →` 翻页（**只认方向键**，去掉了点击左右/滚轮以免误触）；底部**序号条**点任意页码一键直达；点序号条右端 **▦** 打开**全部页缩略图总览**（无序号、纯缩略图），点缩略图进入该页；**Esc 退出**总览——总览没开时 Esc 不拦截、交还浏览器退出全屏。

导出：浏览器打开 → `Cmd/Ctrl+P` → 另存为 PDF → **取消「页眉和页脚」**、边距默认 → 即得一页一张（导航 chrome 仅屏幕显示，打印态已隐藏，不进 PDF）。无头等价命令：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --no-pdf-header-footer --print-to-pdf=out.pdf "file://$PWD/assets/skeleton.html"
```

PPT（16:9）把上面命令里的 `skeleton.html` 换成 `skeleton-16x9.html` 即可——画幅（A4 / 16:9）由各骨架引入的 `@page{size}` 决定，命令不变。

## Gotchas（实战坑）

- **`.inner` 可用高（填充率分母）：PDF ≈ 1005px@96dpi（A4），PPT ≈ 604px（16:9 1280×720px）**；driver 用 `getBoundingClientRect` 比例法测，deck 把页面 transform 缩放也不影响比例。PPT 分母矮一半，每页内容量约为 PDF 的六成，别照搬 A4 的信息密度。
- **flexcol 页的 SVG 会被 `flex` 纵向拉伸**：内容少的页 SVG 拉伸可达 2–3 倍（圆变椭圆、空旷）。修法——把 SVG 的 `viewBox` 高度设到 ≈ 渲染比（≈ 680×宽度对应的实际高），stretch 即回到 1.0。这是做这类卡片最容易翻车、也最不显眼的坑。
- **SVG 元素没有 `offsetHeight`**（返回 NaN）：用 `getBoundingClientRect` 量，别用 offset 系列遍历子元素求底部（会漏掉 SVG）。
- **`file://` 会被部分浏览器自动化（如 Playwright）拦截**：所以 driver 内置 http server。人工用 `file://` 截图/打印没问题。
- **打印必须取消页眉页脚**，否则每页顶部多出 URL/日期；无头用 `--no-pdf-header-footer`，CDP 用 `displayHeaderFooter:false`。
- **`preferCSSPageSize:true`** 是让 `@page{size:A4}`（PDF）/ `@page{size:1280px 720px}`（PPT 16:9）生效、保证一页一张的关键；漏了会按默认 Letter 重新分页。同一个 driver 因此对两种画幅都成立，无需改 driver。

## Troubleshooting

| 症状 | 原因 / 修法 |
|---|---|
| `Chrome CDP 未就绪` | Chrome 路径不对 → `export CHROME=...`；或端口被占，重跑（driver 用随机端口）。 |
| 某页 `填充 NaN%` | 该 `.page` 缺 `.inner` 子节点；按骨架补上。 |
| PDF 页数 ≠ section 数 | 内容溢出导致某页被拆成两页 → 看 driver 哪页 `溢出!`，精简该页。 |
| 填充率全 100% 但视觉空旷 | flexcol 的 SVG 被拉伸撑满（见 Gotchas），调 viewBox 高度。 |
