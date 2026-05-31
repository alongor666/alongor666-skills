# Claude Design 高效协作规范（context-spec）

> 目的：让 Claude Design（claude.ai/design）一次产出贴合需求的稿，少来回。来源见文末。

## 1. Claude Design 是什么 / 吃什么 / 吐什么

- **是什么**：Anthropic Labs 的可视化设计产品（research preview，Pro/Max/Team/Enterprise），Opus 级模型驱动。描述需求→出初版→**内联批注**具体元素 / **直接改文字** / **调整旋钮**实时调间距·配色·布局，再让它套用到全稿。
- **接受的输入**：自然语言描述；**上传参考**（当前页 HTML、截图/图片、wireframe、slide、品牌资料）；**链接代码仓库**（让它读真实组件/架构/样式，产出更接近可上线）；**自动继承组织设计系统**（建项目时带入品牌色/字体/组件）；长上下文里粘贴竞品/材料。
- **打磨方式**：**内联批注**=组件级精改（padding/按钮/间距，点哪改哪，比口述定位快）；**Chat**=结构级改（配色/布局重排/要 2-3 个备选方向）。批注不被采纳时把反馈直接贴进 chat。
- **导出**：ZIP、PDF、PPTX、Canva、standalone **HTML**、**直接 Handoff 给 Claude Code**（本地 agent 或 web）、可分享链接（看/评/编权限）。→ 本 skill 默认要 **standalone HTML**；若用户愿意,也可走 **Handoff 给 Claude Code** 直接交接落地（见 SKILL.md Phase B/C）。
- **AI 边界**：claude.ai/design 要用户登录态、在浏览器内操作，**AI 不能代驱动**；目标站点/该产品常被运行环境 egress 白名单挡。

## 2. 它高效工作所需的 context（简报必须覆盖）

最大原则：**2026 年模型够强，结构 > 措辞**。把它原本会"访谈你"的问题，在简报里**预先答完**。

| context 维度 | 为什么 | 简报里怎么给 |
|---|---|---|
| **目标受众 + 核心用例** | 它据此区分"真痛点"与"边缘情况" | 一句话画像 + 2-3 个主用例 |
| **当前状态参考** | 有起点比凭空强 | 上传 current-page.html / 截图；文字说清现状痛点 |
| **逐维度方向**（排版/配色/动效/背景分开点名） | 笼统"好看"会回退到平庸默认 | 每维度给倾向 + 约束（见下） |
| **要避免的默认** | 模型有惰性默认，需显式否决 | 列黑名单：忌 Arial/Inter 等通用字体、忌怯懦配色、忌无意义渐变/阴影/动效（按项目调） |
| **设计系统约束** | 产出要能落地 | 贴语义色板 + 字体栈 + 组件预设 + 数值/排版规则（来自 Phase 0 发现） |
| **必须保留的功能与交互** | 防止为美观砍数据/交互 | 逐条列区块 + 交互（下钻/联动/排序/筛选/Tab） |
| **红线（不要做）** | 一次说清省返工 | 不删维度、只用既有语义色、数值格式硬规则 |
| **交付物期望** | 对齐产出形态 | 桌面宽屏高保真 + 导出 standalone HTML（必要时响应式） |

## 3. 措辞策略

- **先给框架再给细节**：受众/用例/调性 → 区块/交互 → 设计系统 → 红线 → 交付物。
- **正反都给**：既说"要什么"也说"不要什么"（黑名单常比白名单更有效）。
- **承诺一致美学**：让它用 CSS 变量保持一致；主色明确 + 锐利点缀色，胜过平淡大杂色。
- **给参考但要求落地**：可参考某风格，但必须服从设计系统约束（避免它照搬参考站的色彩/字体）。
- **数据密集型工具要显式声明**：否则它易做成营销落地页（留白过度、装饰过多）。

## 4. 数据密集型经营/分析类页面的特别叮嘱

这类页面（dashboard/报表/明细表）翻车点固定，简报务必写死：
- 信息密度优先于留白美学；表格数字等宽右对齐；率值固定小数位、单位进列头；金额单位统一。
- 颜色=语义（红=差/超标、绿=好），禁装饰性上色；"差"要一眼可见但不过度。
- 排序有默认（主题指标从差到好）；下钻/联动层级要视觉化。

---
来源：
- [Prompting for frontend aesthetics — Claude Cookbook](https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics)
- [Prompting best practices — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Get started with Claude Design — Claude Help Center](https://support.claude.com/en/articles/14604416-get-started-with-claude-design)
- [Introducing Claude Design — Anthropic](https://www.anthropic.com/news/claude-design-anthropic-labs)
