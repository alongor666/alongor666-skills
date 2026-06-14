---
name: company-vortex-card
description: >
  把 company-vortex 产出的「{公司}_{代码}_结构诊断.md」做成中国国家地理风格的 12 页视觉卡片——
  默认 16:9 大屏演示版（大字号，投影/大屏/手机可读），调用 xcl-html2pdf 基座五件套渲染；
  A4 纵向密排版保留为可选（打印/归档）。涡旋三才结构 + 物理隐喻 SVG + 印刷级排版铁律。
  触发词：视觉卡片、做成卡片、结构诊断卡片、涡旋卡片、xcl_html2pdf、html2pdf 公司、诊断做成 PDF、
  诊断做成 PPT、16:9 大屏卡片、把诊断报告做成卡片、company vortex card。
  机制层（16:9/A4 版面、横向翻页、导出一页一张、bundle 自包含、验收 driver）全部复用 xcl-html2pdf；
  本 skill 只提供涡旋诊断专属内容层：12 页结构、三才（天/人/地）、物理隐喻 SVG、组件 CSS。
user_invocable: true
version: "2.0.0"
---

# company-vortex-card：涡旋诊断视觉卡片（16:9 大屏 / A4 可选）

把 `company-vortex` 的产物 `{公司名}_{股票代码}_结构诊断.md` 做成**12 页视觉卡片**：中国国家地理杂志风、屏幕横向一屏一页翻页、导出一页一张。

> **默认产 16:9 大屏演示版**（1280×720px，大字号、留白大气，投影 / 大屏 / 手机都看得清）。
> A4 纵向是为打印密排设计的，字号小、放屏幕上太挤——只在用户明确要「打印 / 归档 / 密排长报告」时才走 A4 可选路径。

## 架构：调用 xcl-html2pdf 基座，本 skill 只补涡旋专属层

机制 / 视觉 / 字号全部来自基座 `xcl-html2pdf`，本 skill **不再内联整套 CSS**，只提供涡旋诊断专属的两块：

| 来源 | 文件 | 职责 |
|---|---|---|
| `xcl-html2pdf/assets` | `deck-16x9.css` | 16:9 版面盒 + 横向翻页 + 导出一页一张（勿改） |
| `xcl-html2pdf/assets` | `report-skin.css` | 配色 / 字体 / 通用组件（cover/dossier/table/verdict/calc/quote/note/seal，勿改） |
| `xcl-html2pdf/assets` | `skin-16x9.css` | 把通用组件字号放大到演示尺度（勿改） |
| `xcl-html2pdf/assets` | `deck-16x9.js` | 演示翻页：方向键 / 序号条 / 缩略图总览 / 全屏 / 触摸滑动（勿改） |
| **本 skill** `assets` | **`vortex-16x9.css`** | 涡旋专属组件 `.stage-* / .triad / .shape / .vortex`（16:9 演示字号已调校） |
| **本 skill** `assets` | **`card-template-16x9.html`** | 16:9 骨架，外链上面 5 个文件，演示全部页型 archetype |

> 基座 `report-skin.css` 顶部已声明「涡旋诊断专属组件见 company-vortex-card」——`vortex-16x9.css` 正是补这块。引入顺序务必：`deck-16x9.css → report-skin.css → skin-16x9.css → vortex-16x9.css`。

`<xcl>` 在下文统一指基座目录 `~/.claude/skills/xcl-html2pdf`；`driver.mjs`、`bundle.mjs` 在其根，样式表在其 `assets/`。

## Prerequisites

```bash
node --version   # ≥ 21（实测 v22.16.0+）；系统已装 Chrome（macOS 默认路径内置，其它平台用 CHROME 覆盖）
```

## 执行步骤 · 16:9 大屏（默认主路径）

1. **定位源文件**：按公司名/代码/路径找到 `{公司名}_{股票代码}_结构诊断.md`；有 `_AI*专题.md` 等补充报告一并读入。找不到先确认诊断报告是否已生成（那是 company-vortex 的活）。

2. **复制套件到工作目录**（与诊断 MD 同目录，记为 `$OUT`）：
   ```bash
   XCL=~/.claude/skills/xcl-html2pdf; SELF=~/.claude/skills/company-vortex-card
   cp "$XCL"/assets/{deck-16x9.css,report-skin.css,skin-16x9.css,deck-16x9.js} "$OUT"/
   cp "$SELF"/assets/vortex-16x9.css "$OUT"/
   cp "$SELF"/assets/card-template-16x9.html "$OUT/{公司名}_{股票代码}_视觉卡片.html"
   ```
   这 5 个样式/脚本文件**勿改**——它们与输出 HTML 同目录，外链才不 404。

3. **逐页填充 12 页**（骨架已给出每种页型 archetype，阶段页复制 5 次填 5 阶段）：
   - P1 封面 `.cover-page`：公司名 + 一句话物理隐喻标题 + `.defn` 总定义
   - P2 档案 `.dossier`（8–10 项）+ 五阶段总览 `table.data`
   - P3–P7 五个阶段：`.stage-tag`（临界阶段加 `.crit`）`/ .stage-h / .stage-yr / .triad`（天/人/地）`/ .shape` + 一张 SVG（`.inner.flexcol` 内，图加 `class="vortex grow"` 撑满下半屏）
   - P8 财务 `.bar-row` + `table.data`
   - P9 竞争格局 `table.data` + `.note` + `.quote`
   - P10 专题（该公司核心矛盾，如「光度≠温度」「看涨期权 vs 主引擎」「研发热核悖论」）：`.opt-row`/`.badge` + `.quote`
   - P11 量级测算 `.calc` 三块 + 该跟踪的矢量 `table.data`
   - P12 终局判断 `.verdict` 四维（核心密度/边界扩张力/抗熵增/相变概率，★评分）+ 收尾 `.quote`
   - **直接套基座标准 class**，不要在卡片里重定义字体/字号/字色；涡旋组件已在 `vortex-16x9.css`。

4. **演示风铁律（16:9 比 A4 矮一半，每页内容量约六成）**：可用高 `.inner`≈604px、宽≈1152px。**每页只讲一件事、大字、留白**；阶段页三才文字务必精简（每才 ≤3 行、形态 ≤2 行），否则必溢出。不足补实质内容（小表/说明/引言），不靠拉间距充数。

5. **重画 SVG 涡旋图**：每阶段一张，**契合该公司专属物理隐喻**（不照抄范例的恒星/吸积盘/透镜/结晶）。语义色固定——向心/吸积金 `#7a6433/#bd9b52`、离心/利好玉绿 `#2f6b4f/#3f8a66`、外部压力橙 `#a8541f/#c06a3a`、警示朱红 `#a8341f`，核心暖色径向渐变。浅底深字，标注力量方向/关键节点/矛盾点。
   - **关键坑**：flexcol 页的 `grow` SVG 会被纵向拉伸。16:9 下半屏 ≈ 宽:高 ≈ 3.8:1，故 `viewBox` 取 `0 0 1152 300` 量级（用 driver 反复测，stretch→1.0）。SVG 内字号也要放大到演示尺度（标注 16–22px，不是 A4 的 10–13px）。

6. **强制验收**（排版铁律，不可跳过）：
   ```bash
   node "$XCL"/driver.mjs "$OUT/{公司名}_{股票代码}_视觉卡片.html" 12 --open
   ```
   要求**每页填充率 80–100%、零溢出、PDF 页数 = 12**；`--open` 在全 PASS 后自动用浏览器打开预览（FAIL 不开）。不足补内容、超出精简。同一个 driver 画幅无关（16:9 也用它）。

7. **分发前打包自包含单文件**（治跨平台「换电脑打不开 / 文字错位 / 翻不动」）：
   ```bash
   node "$XCL"/bundle.mjs "$OUT/{公司名}_{股票代码}_视觉卡片.html"   # → *.standalone.html
   ```
   只发标准 HTML 会因外链 404 在别的电脑崩；要发微信/邮件/U 盘就交付 `*.standalone.html` 这一个文件，并对它再跑一次 driver 确认仍全 PASS。

屏幕翻页：`← →`／`↑ ↓`／空格 / 序号条直达 / `Esc` 缩略图总览 / `⛶` 全屏 / 手机触摸滑动。导出 PDF：`Cmd/Ctrl+P` → 另存为 PDF → **取消「页眉和页脚」** → 一页一张 16:9。

## 执行步骤 · A4 纵向（可选，仅打印/归档/密排长报告）

用户明确要 A4 时走这条：以本 skill `assets/card-template.html`（自包含单文件，已内联全套 A4 CSS 与翻页脚本）为模板，**CSS / 翻页脚本原样保留，只换 `.page` 正文与 SVG**；A4 可用高 ≈1005px，每页可塞约 16:9 的 1.6 倍内容；SVG `viewBox` 高度取 286/300 量级。保存 `{公司名}_{股票代码}_视觉卡片_A4.html`，验收 `node "$SELF"/driver.mjs 该文件 12`。

## 注意

- **禁止同页双标题（页眉 ≠ 页内主标题）**：页眉 `rhead` 左栏只放「板块栏目名 + 英文」（刊物层级，同板块各页可相同），页内大标题（`sec-head` 的 `sec-title` / 阶段页 `stage-tag`）才是本页具体标题；二者文字**不得相同或互相包含**。典型修正——① 阶段页 rhead 用「结构演化 / STRUCTURAL EVOLUTION」，`PHASE 0X` 序号只出现在 stage-tag，不在 rhead 重复；② 财务页 rhead「财务地层」则 sec-title 用「营收与盈利剖面」，不再复述「财务地层」；③ 终局页 rhead 用「诊断收束 / SYNTHESIS」，sec-title 才是「终局判断」。注：文字与 SVG 互为补充强调（同一隐喻、一个画一个写）**不算**重复——禁的是同一页把同一个标题写两遍。
- 数据只用一手/可交叉验证来源，每个关键数字至少 2 源；存疑标注。
- 隐喻、阶段划分、SVG 形态都要为该公司量身定制——范例（京东方=恒星、工业富联=吸积盘、理想=透镜、恒生电子=结晶/反应堆）只示范深度与手法，不可套壳。
- 横向翻页（屏幕）与一页一张（导出）由基座机制保证，正文填充不要破坏；不要在卡片 `<style>` 里重定义基座已固化的字体/字号/字色。
- 16:9 的 `.bar-peak` 在基座是玉绿（峰值/利好语义），与 A4 旧版的朱红不同——按基座语义用即可，不要为峰值另写死红色。

## 与 xcl-html2pdf 的关系（v2 起：真·调用，不再内联）

- `xcl-html2pdf` = 通用基座：任意 HTML → 16:9 演示 PPT 或 A4 印刷 PDF；`deck-16x9.css`/`page-deck.css` 版面 + `report-skin.css` 固化视觉 + `skin-16x9.css` 演示字号 + 翻页脚本 + `driver.mjs` 验收 + `bundle.mjs` 打包。
- `company-vortex-card` = 专用层：**只提供涡旋诊断专属的 `vortex-16x9.css`（组件）与 `card-template-16x9.html`（骨架）**，其余全部外链基座。v1 曾把整套 A4 CSS 内联进 `card-template.html`（自包含），v2 改为默认 16:9 + 真·调用基座；A4 自包含模板保留为可选路径。
- 做**非诊断类**的其它印刷/演示级报告，直接用 `xcl-html2pdf` 的骨架 + 皮肤即可，自动继承同一套视觉。

## Gotchas / Troubleshooting

- 继承基座（详见 xcl-html2pdf 的 Gotchas）：16:9 `.inner` 可用高 ≈604px 是填充率分母（A4 ≈1005px）；SVG 无 `offsetHeight` 要用 `getBoundingClientRect`；`file://` 被自动化拦截故 driver 内置 http；导出必须取消页眉页脚。
- **本 skill 最高频两坑**：① 阶段页 `grow` SVG 纵向拉伸 → 调 `viewBox` 高度到 ≈ 渲染比；② 把 A4 的信息密度照搬到 16:9 → 必溢出，三才文字要砍到六成。
- **换电脑/手机文字错位、翻不动**：只发了标准 HTML、漏传同目录 5 个外链 → 404。用 `bundle.mjs` 发自包含单文件（非浏览器兼容问题）。
- driver 偶发假 FAIL（报「连续文档 / 0 页」）：冷启动竞态，先 `pkill -f "Google Chrome.*--headless"` 再重跑 2–3 次，见到「P 3」才采信。
