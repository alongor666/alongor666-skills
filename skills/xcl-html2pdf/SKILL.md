---
name: xcl-html2pdf
description: >-
  把任意 HTML 报告做成印刷级 PDF（A4 纵向）或演示级 PPT（16:9）——屏幕一屏一页横向翻页、
  导出一页一张、内容不跨页；含标准皮肤（国家地理风 / 经营仪表盘风二选一）、零依赖验收
  driver、bundle 自包含单文件分发。触发词：html2pdf、xcl_html2pdf、做成 PDF、做成 PPT、
  印刷级报告、演示版、16:9、大屏卡片、投影、keynote、一页一张、横向翻页卡片、A4 卡片、
  打印成 PDF、标准报告、report to pdf、build report、verify card、诊断报告、经营仪表盘、
  KPI 看板、dashboard、机构盯盘、自包含单文件、跨平台适配、Windows 打不开、手机翻页、
  文字错位。内容专属模板（如涡旋诊断卡片）见 company-vortex-card。
user_invocable: true
version: "1.7.1"
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
> 翻页脚本两套不同：**PPT 用 `deck-16x9.js`**（演示导向：GPU transform 推入过渡 + ← →／↑ ↓／空格(Shift 回退)／PageUp·Down 翻页 + Home·End 跳首末 + **触摸滑动** + 序号条直达 + Esc/▦ 缩略图总览（总览内方向键移动所选页、回车/空格进入）+ ⛶ 全屏演示；滑动让手机与不熟键盘的用户也能翻），**PDF 用 `deck.js`**（← → / 点击左右 / 滚轮），互不影响。
>
> 两套**共用 report-skin.css**（配色/字体/组件单一真相源），视觉天然一致；**同一个 `driver.mjs` 验收**（填充率比例法 + `preferCSSPageSize`，画幅无关）。
>
> ## ⚑ PPT 皮肤二选一：国家地理风 / 经营仪表盘风
> PPT 版式下视觉皮肤再二选一（机制层 deck-16x9.css + 翻页脚本不变）：
>
> | 皮肤 | 何时用 | 用哪套 |
> |---|---|---|
> | **国家地理风（默认）** | 对外发布、品牌叙事、文化感 | `deck-16x9.css` + `report-skin.css` + `skin-16x9.css` + `deck-16x9.js` + `skeleton-16x9.html` |
> | **经营仪表盘风** | 经营诊断盯盘、KPI 复盘、图表为主 | `deck-16x9.css` + `report-skin-dashboard.css` + `deck-16x9.js` + `skeleton-dashboard-16x9.html`（仪表盘皮肤自带演示字号，**不叠 skin-16x9.css**） |
>
> 仪表盘风组件语汇 + 「进度口径≠最终留存」编码铁律见 [`references/dashboard-deck.md`](references/dashboard-deck.md)。诊断报告（机构盯盘 / 续保 / 赔付 / 渠道复盘）默认用仪表盘风。
>
> ## ⚑ 分发必做：bundle 成「自包含单文件」（治跨平台/换电脑打不开）
> 本基座是**分离式四件套**（`.html` + 外链 css/js，相对路径）。**只把那个 `.html` 发到别的电脑（微信/邮件/U盘）→ 外链 404 → 文字错位（无机制 CSS、不缩放）+ 翻不动（无翻页 JS）**——这是「本机正常、Windows 打开崩」的头号原因，与浏览器无关。
>
> 验收全 PASS 后，**分发前先打包**：
> ```bash
> node bundle.mjs your.html                 # → your.standalone.html（内联 css/js，发这一个文件即可）
> node bundle.mjs your.html out.html --webfont   # 额外内联思源黑/宋 web 字体（要跨平台像素级一致时）
> ```
> 自包含单文件在 **Edge / Chrome / Safari · PC 与手机**都一致显示并翻页。翻页已支持 **方向键 + 触摸滑动 + 底部序号条**（手机无键盘也能翻）。字体走跨平台 CJK 栈（mac/iOS→PingFang、Windows→微软雅黑、Android/Linux→思源黑），不加 `--webfont` 也能跨平台可读；要像素级一致再加 `--webfont`（依赖 Google 中国镜像，断网退化到系统字体仍可读）。
> **开发态仍保留多文件**（便于改皮肤/机制）；`bundle.mjs` 只在分发那一刻把它压成单文件，两者不冲突。

把任意 HTML 报告做成**屏幕横向一屏一页、导出一页一张**的印刷/演示级文档。分离式架构：

- **版面机制（二选一，勿改）** — `page-deck.css`（A4 纵向盒）或 `deck-16x9.css`（16:9 演示盒）；都含横向翻页 + 导出一页一张。
- **report-skin.css** — 标准视觉（国家地理风）：字体、字号分级、语义字色、通用组件，全部**固化**（勿改；改规范只改这一处，PDF/PPT 同步生效）。
- **report-skin-dashboard.css** — 第二套皮肤（经营仪表盘风，仅 PPT/16:9）：现代浅色 + KPI 卡片 / 条形 / 帕累托 / 进度推进 / 行动卡 / 紧凑附录表，**自带演示字号**（不叠 skin-16x9.css）。与 report-skin.css 互斥二选一，勿改；组件与铁律见 `references/dashboard-deck.md`。
- **skin-16x9.css** — 仅"国家地理风 PPT"用的演示字号叠加层：把字号/留白放大到屏幕可读尺度（**叠加在 report-skin 之上，勿改**；仪表盘皮肤不需要它）。
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
   - **PPT · 国家地理风（默认）**：`assets/skeleton-16x9.html`、`assets/deck-16x9.css`、`assets/report-skin.css`、`assets/skin-16x9.css`、`assets/deck-16x9.js`。
   - **PPT · 经营仪表盘风**：`assets/skeleton-dashboard-16x9.html`、`assets/deck-16x9.css`、`assets/report-skin-dashboard.css`、`assets/deck-16x9.js`（**不要** skin-16x9.css；皮肤自带演示字号）。组件语汇见 `references/dashboard-deck.md`，套 `.kpis`/`.bars`(+亮灯色类)/`.bench`/`.cards`/`.prog`/`.dt` 等仪表盘 class。
   - **PDF**：`assets/skeleton.html`、`assets/page-deck.css`、`assets/report-skin.css`、`assets/deck.js`。
2. 把骨架里每个 `<section class="page">` 换成你的内容，按需增删页。**直接套标准 class**（`sec-head` / `lede` / `table.data` / `note` / `quote` / `verdict` / `dossier` / `calc` / `bar-row` …）即得统一字体/字号/字色——不要在自己的 `<style>` 里重定义这些；只有本页特有的图形样式才另写。
3. 版面规则（铁律）：
   - 每页 = 一个 `.page`，内容放进 `.inner`（`overflow:hidden`）。**可用高（填充率分母）：PDF ≈ 1005px@96dpi（A4 210×297mm）；PPT ≈ 604px（16:9 1280×720px）。**
   - 封面用 `.page.cover-page`；要让一张图撑满下半页/下半屏，用 `.inner.flexcol` + 给图加 `class="grow"`。
   - **每页填充率 80–100%、零溢出、内容不跨页。** PPT 可用高更矮、字更大，每页内容量约为 PDF 的六成——每页只讲一件事；不足就补实质内容（小表/说明/引言），不靠拉间距充数。
4. 反复跑 driver 验收到全 PASS（同一个 driver，画幅无关）。**全 PASS 后即开**：agent 跑最终验收时带 `--open`，driver 会在全 PASS 时自动用系统默认浏览器打开成品给用户预览（FAIL 不开）。
5. **分发前打包成自包含单文件**（见顶部 ⚑ 分发铁律）：`node bundle.mjs your.html` → `your.standalone.html`。**只要会发给别的电脑/手机，就交付这个单文件**，不要只发原始 `.html`（外链 404 会导致对方文字错位 + 翻不动）。打包后建议再跑一次 `node driver.mjs your.standalone.html N` 确认单文件也全 PASS。

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
- **完成即开**：`--open` 让验收**全 PASS 后**自动用系统默认浏览器打开该 html（FAIL 不开）；跨平台（macOS `open` / Linux `xdg-open` / Windows `start`）。
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
- **PPT（`deck-16x9.js`）**：键盘 `← →`／`↑ ↓`／`空格`(Shift+空格回退)／`PageUp·Down` 翻页、`Home·End` 跳首末（不绑点击页面左右/滚轮以免误触）；**触摸左右滑动**（手机/平板）；底部**序号条**点任意页码一键直达；**缩略图总览内方向键移动所选页、回车/空格进入**；**Esc 两级退出**——在页面上按 `Esc` 进**缩略图总览**（无序号、纯缩略图），在总览里按 `Esc` 退出全屏；也可点序号条的 **`▦`** 开总览、**`⛶`** 进入/退出全屏演示。⚠️ 真·浏览器全屏态下，首个 `Esc` 由浏览器强制退出全屏（JS 拦不住），此时总览改用 `▦` 打开。

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
- **仪表盘皮肤 · 附录密表溢出**：`.dt` 表默认继承 body 的 `line-height:1.7`，双表/页（~28 行）必溢出；把附录页 `.inner` 加 `dense2` 类（皮肤已定义收紧行高），单表页不用。
- **仪表盘皮肤 · 进度口径误读**：未到期/在途的率值用中性 `a-prog`（不亮灯），只有已成熟最终值用 `a-ok/watch/warn/bad` 四级亮灯——混用会让管理层把"进度"当"最终结果"。详见 `references/dashboard-deck.md`。
- **换台电脑/手机就「文字错位 + 没翻页」**：分离式外链是相对路径，单发 `.html` 到别处 → css/js 404 → 无机制 CSS（1280px 不缩放撑爆 → 文字错位）+ 无翻页 JS。**不是浏览器兼容问题，是漏传外链**。分发前用 `node bundle.mjs your.html` 打成自包含单文件（见顶部 ⚑）。本机正常是因为同目录有那几个文件。
- **bundle 内联 JS/CSS 时 `</script>`/`</style>` 提前闭合**：被内联的文件内容里若含字面 `</script>`（如注释示例 `<script src=...></script>`），会在 `<style>/<script>` 内提前闭合标签，把其后内容溢出成页面可见文本（曾导致多出一页 + 脚本半残）。`bundle.mjs` 已对内联内容转义这两个闭合序列；自己手写内联时务必同样转义。
- **跨平台 CJK 字体**：字体栈打头保持 `"Noto Sans SC","PingFang SC","Microsoft YaHei"`（每平台都有合适中文字体），改动打头会让 mac 渲染度量变化、破坏既调好的填充率。要跨平台**像素级**一致用 `bundle.mjs --webfont`（嵌思源黑/宋）并对 standalone 重跑 driver；否则各平台用各自系统字体，字宽微差但填充率留有余量可吸收。

## Troubleshooting

| 症状 | 原因 / 修法 |
|---|---|
| `Chrome CDP 未就绪` | Chrome 路径不对 → `export CHROME=...`；或端口被占，重跑（driver 用随机端口）。 |
| driver 报「连续文档 / 0 页 / flow 模式」但 html 没问题（假 FAIL） | **冷启动竞态**：driver 每次用全新 user-data-dir + 1500ms settle，冷 Chrome 没在 settle 内加载完 → 误判 0 个 `.page` → 落「连续文档」模式报假 FAIL（也可能是 `Page.printToPDF` CDP 超时）。修法：先 `pkill -f "Google Chrome.*--headless"` 杀残留进程，再循环重跑 2–3 次，直到输出现「P 3 」（已落入 deck 模式）才采信；**别把假 FAIL 当真 bug**。 |
| 某页 `填充 NaN%` | 该 `.page` 缺 `.inner` 子节点；按骨架补上。 |
| PDF 页数 ≠ section 数 | 内容溢出导致某页被拆成两页 → 看 driver 哪页 `溢出!`，精简该页。**或**：bundle 内联的 JS/CSS 含字面 `</script>`/`</style>` 提前闭合 → 其后内容溢出成额外页（用最新 `bundle.mjs`，已转义）。 |
| 填充率全 100% 但视觉空旷 | flexcol 的 SVG 被拉伸撑满（见 Gotchas），调 viewBox 高度。 |
| 别人电脑/手机打开文字错位、翻不动 | 只发了 `.html`、漏传外链 css/js（404）。用 `node bundle.mjs your.html` 发自包含单文件；非浏览器兼容问题。 |
| 手机上翻不动页 | 旧版只绑方向键。最新 `deck-16x9.js` 已加触摸滑动；确认用的是最新版（重装 skill / 重新 bundle）。 |
