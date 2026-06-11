---
name: company-vortex-card
description: >
  把 company-vortex 产出的「{公司}_{代码}_结构诊断.md」做成中国国家地理风格的 12 页视觉卡片 HTML——
  屏幕一屏一页横向翻页，打印为一页一张 A4 PDF。涡旋三才结构 + 物理隐喻 SVG + 印刷级排版铁律。
  触发词：视觉卡片、做成卡片、结构诊断卡片、涡旋卡片、xcl_html2pdf、html2pdf 公司、诊断做成 PDF、把诊断报告做成卡片、company vortex card。
  机制层（A4 版面/横向翻页/打印/验收）复用 xcl-html2pdf；本 skill 在其之上提供涡旋诊断专属的 12 页模板与填充规范。
user_invocable: true
version: "1.0.1"
---

# company-vortex-card：涡旋诊断视觉卡片

把 `company-vortex` 的产物 `{公司名}_{股票代码}_结构诊断.md` 做成**印刷级视觉卡片**：中国国家地理杂志风格、12 页、屏幕横向一屏一页翻页、打印一页一张 A4。

机制与内容分层：**版面盒 / 横向翻页 / 打印一页一张 / 验收 driver** 来自基座 `xcl-html2pdf`（这里已把同款机制内联进 `assets/card-template.html`，并自带同一份 `driver.mjs`，本 skill 单独安装也能用）。本 skill 负责的是涡旋诊断**专属内容层**：12 页结构、三才（天/人/地）、物理隐喻 SVG、语义配色。

驱动：`driver.mjs`（Node ≥21 + 系统 Chrome 走 CDP，零 npm 依赖）实测每页填充率/溢出/PDF 页数。路径相对本 skill 目录。

## Prerequisites

```bash
node --version   # ≥ 21（实测 v22.16.0）；系统已装 Chrome（macOS 默认路径内置，其它平台用 CHROME 覆盖）
```

## 执行步骤（agent 主路径）

1. **定位源文件**：按用户给的公司名/代码/路径找到 `{公司名}_{股票代码}_结构诊断.md`；若有 `_AI*专题.md` 等补充报告一并读入作素材。找不到先确认诊断报告是否已生成（那是 company-vortex 的活）。

2. **以 `assets/card-template.html` 为模板**：CSS、`@media screen` 横向翻页、`@media print` 分页、页尾 `<script>` **一律原样保留，绝不改动**——只替换 `<body>` 内每个 `.page` 的正文与 SVG。

3. **逐页填充 12 页**（与模板一一对应）：
   - P1 封面：公司名 + 一句话物理隐喻标题 + `.defn` 总定义
   - P2 档案 `.dossier`（10 项）+ 五阶段总览表
   - P3–P7 五个阶段：每页 `.stage-tag / .stage-h / .triad`（天/人/地）`/ .shape` + 一张 SVG 涡旋图（放进 `.inner.flexcol`，`.vortex` 自动撑满下半页）
   - P8 财务 `.bar-row` 柱 + `table.data`（近 12 年 + 单季数据）
   - P9 竞争格局表 + 注 + `.quote`
   - P10 专题（该公司核心矛盾，如「光度≠温度」「看涨期权 vs 主引擎」）
   - P11 量级测算 `.calc` 三块 + 该跟踪的矢量表
   - P12 终局判断 `.verdict` 四维（核心密度/边界扩张力/抗熵增/相变概率，★评分）+ 收尾 `.quote`

4. **重画 SVG 涡旋图**：每阶段一张，**契合该公司专属物理隐喻**（不要照抄范例的恒星/吸积盘/透镜）。语义色固定——向心/吸积金 `#7a6433/#bd9b52`、离心/利好玉绿 `#2f6b4f/#3f8a66`、外部压力橙 `#a8541f/#c06a3a`、警示朱红 `#a8341f`，核心暖色径向渐变。浅底深字，标注力量方向/关键节点/矛盾点。
   - **关键坑**：flexcol 页的 SVG 会被 `flex` 纵向拉伸，内容少的页可达 2–3 倍变形。把每张 SVG 的 `viewBox` 高度调到 ≈ 实际渲染比（用 driver 反复测，stretch→1.0）。

5. **保存**：`{公司名}_{股票代码}_视觉卡片.html`

6. **强制验收**（排版铁律，不可跳过）：

```bash
node driver.mjs "{公司名}_{股票代码}_视觉卡片.html" 12
```

要求**每页填充率 80–100%、零溢出、PDF 页数 = 12**。不足就补实质内容（小数据表/补充说明/引言），不靠拉间距充数；超出就精简。实测（英伟达 AI PC 供应链卡片，本机已跑通）：

```
  P 1  填充  95%  无溢出  ✓     P 7  填充  81%  无溢出  ✓
  P 2  填充  83%  无溢出  ✓     P 8  填充  83%  无溢出  ✓
  P 3  填充 100%  无溢出  ✓     P 9  填充  84%  无溢出  ✓
  P 4  填充  80%  无溢出  ✓     P10  填充  86%  无溢出  ✓
  P 5  填充 100%  无溢出  ✓     P11  填充  82%  无溢出  ✓
  P 6  填充 100%  无溢出  ✓     P12  填充  84%  无溢出  ✓
  PDF 页数 = 12 / 期望 12  ✓   →  PASS ✅
```

7. 完成 `open {文件}.html`。屏幕上 `← →` / 点击左右 / 滚轮 翻页；`Cmd/Ctrl+P` → 另存为 PDF → **取消「页眉和页脚」** → 一页一张。

## 注意

- 数据只用一手/可交叉验证来源，每个关键数字至少 2 源；存疑标注。
- 隐喻、阶段划分、SVG 形态都要为该公司量身定制——范例（京东方=恒星、工业富联=吸积盘、理想=透镜、英伟达 AIPC=探照光束）只示范深度与手法，不可套壳。
- 横向翻页（屏幕）与一页一张（打印）由模板内置机制保证，正文填充不要破坏这两套规则。

## 与 xcl-html2pdf 的关系

- `xcl-html2pdf` = 通用基座：任意 HTML → 印刷级 PDF（`page-deck.css` 版面 + `report-skin.css` 固化字体/字号/字色 + 翻页 + 验收），不绑定内容。
- `company-vortex-card` = 专用层：在基座之上，给「涡旋结构诊断」一套现成的 12 页模板。`card-template.html` 内联的视觉规范与基座 `report-skin.css` **同源**（国家地理风、同一套语义色与字号分级），并额外内联涡旋专属组件（stage/triad/shape/vortex）——所以本模板自包含、可独立验收。
- 两者各自自带 `driver.mjs`（同一份验收工具），单独安装均可用。做**非诊断类**的其它印刷级报告时，直接用 `xcl-html2pdf` 的 skeleton + `report-skin.css` 即可，自动继承同一套视觉。

## Gotchas / Troubleshooting

继承基座（见 xcl-html2pdf）：`.inner` 可用高 ≈1005px 是填充率分母；SVG 无 `offsetHeight` 要用 `getBoundingClientRect`；`file://` 被自动化拦截故 driver 内置 http；打印必须取消页眉页脚。本 skill 最高频的坑是**第 4 步的 SVG 纵向拉伸**——务必用 driver 实测后调 viewBox 高度。
