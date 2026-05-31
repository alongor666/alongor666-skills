# Phase 0 发现手册（零硬编码，按指令现场探测）

> 目标：产出一份《项目设计上下文》，让备料/落地都基于项目自己的事实，不假设、不硬编码。

## 1. 技术栈识别

| 探测 | 命中物 | 推断 |
|---|---|---|
| `package.json` deps | `react`/`vue`/`svelte`/`next`/`nuxt`/`solid` | 框架 |
| 同上 | `tailwindcss`/`unocss`/`@emotion`/`styled-components`/`*.module.css` | CSS 方案 |
| 同上 | `antd`/`@mui`/`chakra`/`element-plus`/`shadcn` | 组件库 |
| `scripts` 段 | `build`/`typecheck`/`lint`/`test`/`dev` | 构建/验收命令（验收用） |
| 其它 | `pyproject.toml`/`go.mod`/`Gemfile` | 非前端栈，按需适配 |

记录：框架、CSS 方案、组件库、构建命令、类型检查命令、测试命令、本地启动命令。

## 2. 设计系统 SSOT（按优先级找，找到即停止下一级）

1. **设计文档**：`DESIGN.md` / `STYLEGUIDE*` / `design-system*` / `docs/**/design*`。
2. **配置**：`tailwind.config.*`（取 theme.extend 的 colors/fontFamily/spacing/borderRadius/boxShadow）；`unocss.config.*`；CSS 变量定义文件（`:root{--...}`）。
3. **tokens**：`**/tokens.*` / `**/theme.*` / `src/**/styles/*` / `**/design-tokens*`。
4. **约定**：`CLAUDE.md` / `AGENTS.md` / `.cursorrules` / `.claude/rules/*` 里关于颜色/字体/格式/组件封装的规则。

提取并记录：
- 语义色（primary/success/warning/danger/info…）+ 中性色阶 + 暗色模式策略。
- 字体栈（正文/数字/标题）。
- 组件预设的**封装方式与导入路径**（如 `colorClasses.*`/`cardStyles.*` from `@/shared/styles`，或 shadcn 的 `cn()`+变体）——落地时必须照用。
- 数值/排版规则（率值小数位、单位、千分位、对齐、排序默认）。

> 找不到任何设计系统：明确告知用户"未发现设计系统",采用"通用克制 + 数据密集型"基线(白/灰底、语义色仅传意、等宽数字右对齐),并请用户给参考。**不要静默编造一套色彩。**

## 3. 目标模块代码定位

用搜索 agent（轻模型）grep 模块关键词，分组返回：
- 前端：页面入口、子组件、hooks、types、样式。
- 数据层：API client 方法、查询 hook、状态管理。
- 后端（若同仓）：路由、查询/SQL 生成、配置。

**交互清单（关键产物）**：逐一记录该模块的每个交互——下钻/展开折叠、左右联动、列排序、筛选器、Tab 切换、分页、hover/选中态、键盘可达性。这份清单是 Phase C 不丢交互的对照基线，也是验收项。

## 4. 提交流程发现

- 找 `*-commit-push-pr` skill / `CONTRIBUTING.md` / `.github/PULL_REQUEST_TEMPLATE*` / 项目 CLAUDE.md 的提交约定。
- 记录：分支策略、提交信息格式、治理/校验命令、PR 要求。落地后按此提交。

## 5. 输出：《项目设计上下文》小结

把上面四块汇成一段结构化笔记（可存进专项文件夹 README 顶部），供 Phase A 简报与 Phase C 落地直接引用。
