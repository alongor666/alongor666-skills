---
name: xcl-html2pdf
description: >
  把任意 HTML 报告做成印刷级 PDF——屏幕上一屏一页横向翻页，打印为一页一张 A4、无半空白页、内容不跨页。
  提供 A4 版面盒 CSS（page-deck.css）+ 固化字体/字号分级/字色的标准报告皮肤（report-skin.css）+ 横向翻页脚本，
  和一个零依赖的验收 driver（实测每页填充率/溢出/真实 PDF 页数）。套标准 class 即得统一的国家地理风视觉，无需自调样式。
  触发词：html2pdf、xcl_html2pdf、做成 PDF、印刷级报告、一页一张、横向翻页卡片、A4 卡片、打印成 PDF、标准报告、report to pdf、build report、verify card。
  内容专属的模板（如涡旋诊断卡片）见 company-vortex-card，它在本基座之上。
version: 1.0.0
user_invocable: true
---

# xcl-html2pdf：HTML → 印刷级 PDF 基座

把任意 HTML 报告做成**屏幕横向一屏一页、打印一页一张 A4** 的印刷级文档。三层分离：

- **page-deck.css** — 版面机制：A4 盒、横向翻页、打印一页一张（勿改）
- **report-skin.css** — 标准视觉：字体、字号分级、语义字色、通用组件，全部**固化**（勿改；改规范只改这一处，所有报告同步生效）
- **你的 .html** — 只管内容；套标准 class 即得统一的中国国家地理风视觉

涡旋诊断专属组件（stage/triad/shape/vortex）不在本基座，见 company-vortex-card。

驱动方式：用 `driver.mjs`（Node ≥21 内置 WebSocket/fetch + 系统 Chrome 走 CDP，**零 npm 依赖、无需下载 chromium**）实测每页填充率、溢出、真实 PDF 页数。路径均相对本 skill 目录。

## Prerequisites

```bash
node --version   # 需 ≥ 21（内置全局 WebSocket / fetch；实测 v22.16.0）
# 系统已装 Chrome/Chromium。macOS 默认路径已内置；其它平台用 CHROME 覆盖：
# export CHROME=/usr/bin/google-chrome   (Linux)
```

## 起一个新报告（agent 主路径）

1. 复制四件套到工作目录：`assets/skeleton.html`、`assets/page-deck.css`、`assets/report-skin.css`、`assets/deck.js`（后三个**勿改**——版面、视觉规范、翻页机制都在里面）。
2. 把 `skeleton.html` 里每个 `<section class="page">` 换成你的内容，按需增删页。**直接套标准 class**（`sec-head` / `lede` / `table.data` / `note` / `quote` / `verdict` / `dossier` / `calc` / `bar-row` …）即得统一字体/字号/字色——不要在自己的 `<style>` 里重定义这些；只有本页特有的图形样式才另写。
3. 版面规则（铁律）：
   - 每页 = 一个 `.page`（固定 210×297mm、`overflow:hidden`），内容放进 `.inner`（可用高 ≈ **1005px@96dpi**，即填充率分母）。
   - 封面用 `.page.cover-page`；要让一张图撑满下半页，用 `.inner.flexcol` + 给图加 `class="grow"`。
   - **每页填充率 80–100%、零溢出、内容不跨页。** 不足就补实质内容（小表/说明/引言），不靠拉间距充数。
4. 反复跑 driver 验收到全 PASS。

## 验收 driver（核心 harness）

```bash
# 用法: node driver.mjs <html> [期望页数] [--min 80] [--max 100] [--pdf out.pdf]
node driver.mjs assets/skeleton.html 4
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

- driver 自启静态 http server + 系统 Chrome（CDP），导航后测每页 `.inner` 子元素底部 / 可用高 = 填充率，再用 `Page.printToPDF`（`preferCSSPageSize`）数真实页数。
- **退出码**：`0`=全部达标、`1`=有页不达标/页数不符、`2`=运行错误。可直接接脚本或 CI。
- 想留存 PDF：`node driver.mjs your.html N --pdf out.pdf`。
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

## 导出 PDF（人工路径）

屏幕上：`← →` / 点击页面左右 / 滚轮 翻页。导出：浏览器打开 → `Cmd/Ctrl+P` → 另存为 PDF → **取消「页眉和页脚」**、边距默认 → 即得一页一张。无头等价命令：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --no-pdf-header-footer --print-to-pdf=out.pdf "file://$PWD/assets/skeleton.html"
```

## Gotchas（实战坑）

- **`.inner` 可用高 ≈ 1005px@96dpi**，是填充率分母；driver 用 `getBoundingClientRect` 比例法测，deck 把页面 transform 缩放也不影响比例。
- **flexcol 页的 SVG 会被 `flex` 纵向拉伸**：内容少的页 SVG 拉伸可达 2–3 倍（圆变椭圆、空旷）。修法——把 SVG 的 `viewBox` 高度设到 ≈ 渲染比（≈ 680×宽度对应的实际高），stretch 即回到 1.0。这是做这类卡片最容易翻车、也最不显眼的坑。
- **SVG 元素没有 `offsetHeight`**（返回 NaN）：用 `getBoundingClientRect` 量，别用 offset 系列遍历子元素求底部（会漏掉 SVG）。
- **`file://` 会被部分浏览器自动化（如 Playwright）拦截**：所以 driver 内置 http server。人工用 `file://` 截图/打印没问题。
- **打印必须取消页眉页脚**，否则每页顶部多出 URL/日期；无头用 `--no-pdf-header-footer`，CDP 用 `displayHeaderFooter:false`。
- **`preferCSSPageSize:true`** 是让 `@page{size:A4}` 生效、保证一页一张的关键；漏了会按默认 Letter 重新分页。

## Troubleshooting

| 症状 | 原因 / 修法 |
|---|---|
| `Chrome CDP 未就绪` | Chrome 路径不对 → `export CHROME=...`；或端口被占，重跑（driver 用随机端口）。 |
| 某页 `填充 NaN%` | 该 `.page` 缺 `.inner` 子节点；按骨架补上。 |
| PDF 页数 ≠ section 数 | 内容溢出导致某页被拆成两页 → 看 driver 哪页 `溢出!`，精简该页。 |
| 填充率全 100% 但视觉空旷 | flexcol 的 SVG 被拉伸撑满（见 Gotchas），调 viewBox 高度。 |
