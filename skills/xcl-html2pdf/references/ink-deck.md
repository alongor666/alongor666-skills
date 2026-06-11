# 墨水风 deck 规范（report-skin-ink.css）

> xcl-html2pdf 第三套 PPT 皮肤：暗色双色 · 编辑部克制美学。
> 机制层（16:9 版面 / 翻页 / 打印 / 验收）不变，仍是 `deck-16x9.css` + `deck-16x9.js` + `driver.mjs`。
> 套件：`skeleton-ink-16x9.html` + `deck-16x9.css` + `report-skin-ink.css` + `deck-16x9.js`（自带演示字号，**不叠 skin-16x9.css**）。

## 与 magazine-web-ppt 的分工边界

| | magazine-web-ppt（独立技能） | 墨水风皮肤（本基座） |
|---|---|---|
| 形态 | 在线 WebGL 流体背景网页 PPT，分享/发布会 | 离线静态 deck，driver 可验收、可导出 PDF |
| 背景 | WebGL shader 动态底噪 | 静态渐变 + 预光栅化 PNG 噪声贴片 |
| 验收 | 不可 driver 验收 | 填充率 80–100% / 零溢出 / 页数核对 |
| 分发 | 网页链接 | bundle 自包含单文件 / PDF |

美学同源（配色与字体层次移植自其「电子杂志 × 电子墨水」体系），但**零运行时依赖**：5 套主题 hex 已全量固化在本文件与皮肤 CSS，magazine-web-ppt 升级与本皮肤无关。
**归属说明**：magazine-web-ppt 不在本仓 19 个技能内——它是装在 `~/.claude/skills/magazine-web-ppt/` 的用户级外部技能（主题原始出处为其 `references/themes.md`）；此处引用是设计上的仓外美学来源，不是断链。

## 5 套主题（四变量一组，整体替换 :root，禁止混搭）

切主题 = 整体替换 `report-skin-ink.css` 顶部 `:root` 里这四个变量，一处全换。面板 / 发丝线 / 次级灰均由 `--paper-rgb` / `--ink-rgb` 加 alpha 推导，不需要额外表面色变量。

### 🖋 墨水经典（默认）——通用分享、商业发布，任何场景都安全

```css
--ink:#0a0a0b; --ink-rgb:10,10,11;
--paper:#f1efea; --paper-rgb:241,239,234;
```

### 🌊 靛蓝瓷 —— 科技 / 研究 / 数据分享、深度内容

```css
--ink:#0a1f3d; --ink-rgb:10,31,61;
--paper:#f1f3f5; --paper-rgb:241,243,245;
```

### 🌿 森林墨 —— 自然 / 可持续 / 文化 / 非虚构内容

```css
--ink:#1a2e1f; --ink-rgb:26,46,31;
--paper:#f5f1e8; --paper-rgb:245,241,232;
```

### 🍂 牛皮纸 —— 怀旧 / 人文 / 阅读 / 历史

```css
--ink:#2a1e13; --ink-rgb:42,30,19;
--paper:#eedfc7; --paper-rgb:238,223,199;
```

### 🌙 沙丘 —— 艺术 / 设计 / 创意、审美优先

```css
--ink:#1f1a14; --ink-rgb:31,26,20;
--paper:#f0e6d2; --paper-rgb:240,230,210;
```

**选择参考**：不知道选啥→墨水经典；技术/产品→靛蓝瓷；行业观察/文化→森林墨；书评/人文→牛皮纸；设计/艺术→沙丘。
**铁律**：一份 deck 只用一套主题；不允许混搭（ink 取 A 套、paper 取 B 套必违和）；不接受用户随手给的 hex（委婉展示 5 套预设让选）。

## 字体层次（四层，本地跨平台栈，离线可用）

| 变量 | 栈 | 用途 |
|---|---|---|
| `--serif-zh` | Noto Serif SC → 宋体系 | 章标 / 封面 h1 / display-zh 大字 / 引文 / 评分框标题 |
| `--sans-zh` | Noto Sans SC → PingFang / 微软雅黑 | 正文 / 表格 / note / lede |
| `--serif-en` | Playfair Display → Georgia（本地退化） | 数据大字（stat / calc .big / 页码），衬线数字的张力 |
| `--mono` | IBM Plex Mono → 系统等宽 | kicker / 页眉脚 / 表头 / 徽标 / caption / 档案键名 |

不在线引字体（离线 / PDF 铁律）。要真 Playfair / Plex 像素级一致，走 `bundle.mjs --webfont` 的后续扩展（注入的是 Google 中国镜像**在线 link**，并非内联字体数据，断网退化系统字体；扩展前需先验证镜像可达性）。

## 明暗规则

- **默认整 deck 暗色**：墨底（`--ink`）纸字（`--paper`），克制、专注、投影暗场友好。
- **呼吸节奏**：每 3–5 页可安排一页 `.page.light`（纸底墨字）；`.light` 也可加在页内容器上做局部对照块（样张/并排对比）。
- 舞台底（body / body.deck）随主题暗色，缩放不露机制层米色边。
- 背景质感 = 静态渐变 + 预光栅化 PNG 噪声贴片（96×96 低透明度，明暗页通吃）。**禁止换回 SVG feTurbulence data-uri**——它会让 `Page.printToPDF` 光栅化超时，driver 直接挂死（实测踩坑）。

## 语义三色（上下文自动换挡——本皮肤最重要的编码契约）

双色基底上只叠三个语义色，由 `.page`（暗）/ `.light`（亮）上下文变量自动换挡：

| 变量 | 暗页取值 | light 页取值 | 用途 |
|---|---|---|---|
| `--good` | `#8fc2a5`（提亮绿） | `#2f6b4f`（玉绿） | 利好 / 标杆 / 达标 |
| `--press` | `#d9926d`（提亮锈） | `#a8431f`（铁锈） | 压力 / 风险 / 落后 |
| `--neut` | 纸色 58% | 墨色 58% | 中性 / 不亮灯 |

**契约**：组件与内容只允许引用 `--good/--press/--neut`（或语义类 `.good/.press/.neut`、`table.data` 的 `.ok/.hot`、条形的 `bar-peak/bar-prof/bar-rev`、徽标 `b-eng/b-opt/b-zero`），**禁止写死 hex**——写死的颜色在 light 页 / 换主题后对比度必崩。不引入国家地理的红金玉锈四色，保双色杂志的克制感。

## 杂志版式三件套

- `.kicker` —— 等宽小标（大字距全大写），章节页 / 封面的"刊眉"语汇。
- `.display-zh` —— 中文衬线大字立题（52px），强调词用 `<span class="hot">`（压力色）。
- `.stats` + `.stat` —— 数据大字报：`.s-num`（西文衬线 56px）+ `.s-unit` + `.s-lbl`（等宽小标）；`stat.good / stat.press` 给数字着语义色。

其余组件沿用 xcl 标准 class（`sec-head / lede / table.data / quote / verdict / calc / dossier / bar-row / badge / seal …`），国家地理风的内容结构可直接换皮肤套用。

## 验收要点（在通用 driver 流程之上）

1. **切任何主题后先看样张页**（骨架 P5）：暗 / light 两栏 × 三语义色 + 徽标 + 条形一屏验全，任何一处发糊即停用该搭配。
2. bundle 后 **standalone 必须重跑 driver 全 PASS**（噪声 data-uri 走内联路径的回归项）。
3. 暗色导出 PDF 目视背景未丢（机制层已有 `print-color-adjust:exact` + driver `printBackground:true`，仅需确认）。
