---
name: guizang-dark-dashboard
description: 生成「深色仪表盘风」单文件 HTML 横向翻页 PPT —— 深底 + 高对比数据大字 + 电蓝/青强调色 + 带标签 SVG 系统图，工程/控制台气质。Use when 用户要做工程复盘、技术分享、架构介绍、数据汇报、loop/系统机制讲解，且明确要「深色 / 仪表盘 / 控制台 / dashboard / 暗色」风格时。是 guizang 家族继 A 杂志风、B 瑞士风之后的第三种风格，与 ppt-agent 编排器配合或独立使用。
user_invocable: true
version: "1.0.0"
---

# Guizang Dark Dashboard — 深色仪表盘风 PPT

生成一份**单文件 HTML**横向翻页 PPT。深色仪表盘基调：深底（近黑蓝灰）+ 高对比数据大字 + 一主一辅强调色（电蓝/青）+ 警示色仅用于红线与缺陷数 + 带标签的 SVG 系统图。**零外部依赖、可离线、Cmd+P 一页一屏导 PDF。**

美学锚点：像把 *Grafana / Linear 暗色控制台* 的冷静感，套进一份能站着讲的复盘 deck。

## 何时用 / 不用

**合适**：工程复盘、技术/架构分享、系统机制讲解、数据汇报、loop/pipeline 介绍、面向工程同行的内部讲话。
**不合适**：人文/故事/品牌发布（→ guizang 风格 A 电子杂志风）；学术答辩/监管合规/需 .pptx 与引用（→ academic-pptx-skill）；信息驱动的极简网格海报（→ guizang 风格 B 瑞士风）。

## 与 guizang / ppt-agent 的关系

- 这是**独立 skill**（guizang 是 op7418 外部仓，无法在其内加风格），但**设计语言承袭 guizang 的纪律**（单文件、横向翻页、节奏交替、emoji 白名单、字号双约束限高）。
- 由 **ppt-agent** 编排器在 Step 2 路由命中「深色/仪表盘/控制台」信号时选用；也可被用户直接触发。
- 上游仍走 **humanize-ppt** 出叙事合同（brief），下游交付前跑 ppt-agent 的 **ppt-postflight.mjs** 自检。

## 工作流

### Step 0 · 数据与受众收口（沿用 ppt-agent Preflight，阻断式）
有真实数据源必须接真，禁先用占位/编造数据；确无则显式标「示意数据」+ 用户确认。产一句话价值主张 + 「讲什么/不讲什么」+ 口径登记。

### Step 1 · 拷贝种子模板
```bash
mkdir -p "项目/XXX/ppt"
cp "<SKILL_ROOT>/assets/template-dark-dashboard.html" "项目/XXX/ppt/index.html"
```
模板是**完整可运行**文件：深色设计系统 CSS、翻页 JS（键盘 ←→ / 滚轮 / 触屏 / 数字键）、`@media print` 导 PDF、5 类示例版式、`<!-- SLIDES_HERE -->` 占位符全已就绪。
拷贝后立刻 grep `[必填]` 改掉 `<title>`。

### Step 2 · 填充内容（套版式 + 取 SVG 配方）
- 把示例版式留 1-2 张当样板，其余替换为你的内容。版式速查见模板顶部注释与组件类。
- 系统图去 `references/svg-patterns.md` 取现成配方（同心双环 / 冲突图独立集 / 纵向流水+三源汇入 / 自进化回环 / 九宫流水）。
- AST 角色 → 版式映射：

| AST 角色 | 版式 |
|---|---|
| hook 钩子 | 封面 / 大引用悬念 |
| conflict 冲突 | 数据大字报 / Before-After（`.panel` 对照）|
| method 方法 | 左文右图(SVG) / Pipeline 九宫 |
| proof 证据 | 数据大字报 / 2x2 网格 / Before-After |
| takeaway 收获 | 三栏教训 / 大引用收束 |

### Step 3 · 自检（references/checklist.md）
逐项过 P0（含本风格三条铁律）。

### Step 4 · 预览 + 交付自检
`open index.html`（无需服务器）。交付前跑 `node <ppt-agent>/scripts/ppt-postflight.mjs index.html`，PASS 才算完成。
> ppt-postflight 的「连续同色调(L)」警告对本风格是**误报**：深色风靠 `.alt` 背景微变制造节奏，非 light/dark 切换。可接受。

## 设计铁律（RED LINE · 含三条教训沉淀）

唯一事实源：本 skill `assets/template-dark-dashboard.html` 的 `:root` 与组件类。

1. **配色只用模板那一套**（深底 + `--accent` 电蓝主 / `--accent2` 青辅 / `--warn` 琥珀 + `--p0` 红仅红线与缺陷数）。不自定义 hex。
2. **L1 · 控件放右上**：`.navhint` 在右上角，绝不与页脚右侧栏目说明在右下角堆叠成团。（本风格诞生时的瑕疵 F1）
3. **L2 · 内容页填满**：短内容用「左文 + 右 SVG」双栏 `flex:1` 撑开，禁大片死白。（瑕疵 F2）
4. **L3 · SVG 必带标签+箭头；标题不折行/不孤字**：禁无标签圆点装饰图；中文大标题压到一行，禁孤字成行。（瑕疵 F3）
5. **emoji 白名单**：仅 🟢🔵🟡🔴 + 🔴（红线）。
6. **报告语言红线**：正文清晰中文；英文专名首次出现括注中文释义；图表标签中文。
7. **节奏交替**：相邻页 `slide` / `slide alt` 交替；每页 `.foot` 三件套（页码/栏目/注脚）。

## 资源导览
```
guizang-dark-dashboard/
├── SKILL.md
├── assets/template-dark-dashboard.html   ← 种子模板（设计系统 + 翻页 JS + 示例版式）
└── references/
    ├── svg-patterns.md                    ← 5 套带标签 SVG 系统图配方
    └── checklist.md                       ← P0/P1/P2 检查清单（含三条铁律）
```

## 范式来源
本风格从 chexian-api「Loop v2 工作流复盘」deck 沉淀而来（2026-06-21）。模板与配方即该 deck 优化定稿后的可复用抽取。
