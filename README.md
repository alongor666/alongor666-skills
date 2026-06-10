# alongor666-skills

个人自建的 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 技能集。

## 安装

使用 [skills CLI](https://github.com/vercel-labs/skills)（基于 `npx`）一行安装：

```bash
# 安装全部技能（全局）
npx skills add alongor666/alongor666-skills -g --all

# 安装单个技能
npx skills add alongor666/alongor666-skills -g --skill company-vortex

# 查看仓库中有哪些技能
npx skills add alongor666/alongor666-skills -l
```

### 替代方式：git clone

```bash
git clone https://github.com/alongor666/alongor666-skills.git ~/.claude/plugins/alongor666-skills
```

> **维护者注意**：本机开发走 `skills/sync-skills/sync-skills.sh link` 软链直连（改源即生效）；
> `npx skills add --all` 会把直连软链覆盖为快照拷贝——误跑后用 `doctor` 检测、`link` 修回。

## 质量巡检

```bash
python3 scripts/validate_skills.py   # 全仓技能巡检（frontmatter/依赖声明/死链/分层红线/明文凭据），0 错误为提交门槛
python3 -m pytest skills/chexian-report-shell/tests/ skills/extract-backlog-governance/tests/ scripts/test_validate_skills.py -q
```

## 技能

### 车险业务分析

| 技能 | 说明 |
|------|------|
| **chexian-channel** | 渠道评估 — 评估是否应该投入、继续或退出一个分销渠道（4S 店、二级经销商、经纪人、代理人等） |
| **chexian-ir-diagnosis** | 出险率诊断 — 诊断车险出险率恶化，调查出险率上升原因，对赔付频率进行根因分析 |
| **chexian-market-analysis** | 市场分析 — 分析车险市场的竞争格局、增长机会和风险评估 |
| **chexian-ops-review** | 经营复盘 — 结合市场、定价和渠道分析，形成完整诊断与资源配置建议 |
| **chexian-pricing-decision** | 定价决策 — 商业车险保费报价、核保决策、费率水平判断 |

### 车险诊断报告（HTML 报告族）

| 技能 | 说明 |
|------|------|
| **diagnose-org-weekly** | 三级机构经营诊断周报 — 一键单文件 SPA HTML（10 板块 + 22 下钻子页），支持分公司层聚合 |
| **diagnose-period-trend** | 短中长期对照 — YTD / 上年同期 / 滚动 6/12/24/36 月，三视图（驾驶舱 / 叙事周报 / 分析师超表） |
| **diagnose-loss-development** | 多年保单赔付发展三角形 — 保单年度 × 观察期 × 6 指标 × 12 维度，交互式成熟曲线 |
| **chexian-report-shell** | 报告渲染基座（不面向用户直接调用）— render_page / 四级亮灯 / SPA 拼装 / 多维多窗 DuckDB 查询，被 diagnose-* 复用 |

### 通用工具

| 技能 | 说明 |
|------|------|
| **commit-push-pr-core** | 提交建 PR 工作流基座 — 项目无关的 commit→push→PR 流程，含跨项目通用 git 护栏（大文件拦截 / unrelated-histories / rebase 后 lockfile 同步 / push 后回主干）+ 可挂载的项目红线自审与自进化机制；设计为被各项目薄 wrapper 复用 |
| **company-vortex** | 涡旋分析 — 通过结构动力学/涡旋模型分析上市公司，生成全生命周期诊断报告 |
| **xcl-html2pdf** | HTML→印刷级 PDF 基座 — 把任意 HTML 报告做成屏幕横向一屏一页翻页、打印一页一张 A4 的印刷级文档；提供与内容无关的版面盒 CSS、翻页脚本和零依赖验收 driver（实测每页填充率/溢出/真实 PDF 页数）。「方法复用，非内容复用」 |
| **company-vortex-card** | 涡旋诊断视觉卡片 — 在 `xcl-html2pdf` 基座之上，把 `company-vortex` 的 `结构诊断.md` 做成中国国家地理风格 12 页视觉卡片（涡旋三才结构 + 物理隐喻 SVG），打印为一页一张 PDF |
| **rewrite-conclusion** | 诊断结论重写 — 将 L1 脚本产出的规则化数据提炼为管理层可直接阅读的结构化判断 |
| **ui-redesign** | 页面/模块视觉重做编排 — 配合 Claude Design，项目无关（现场发现技术栈/设计系统），含确定性验收与自进化 |
| **extract-backlog-governance** | backlog 治理提取 — 对照 6 条普适原则（唯一队列/意图先于执行/原子可逆/顺序有据/完成即证明/同步现实）审计任意仓库的待办与流程治理；内置零依赖脚本自动拉 PR 历史、算"规则命中率"找出死规则（过度设计）与缺口。证据优先、判原则不判机制 |
| **sync-skills** | 技能仓「改源即生效」直连同步器 — 把任意 git 技能仓软链到 `~/.claude/skills`，含 doctor 体检与 git 钩子自动补链 |
| **cleanup-worktrees** | 多来源 git worktree 安全回收器 — 识别人工 / sub-agent / codex 三类 worktree、陈旧锁、squash 落地，默认只删零损失项 |
| **crystallize-skill** | 把重复流程沉淀为可复用 skill 的元流程编排 — 判归属 → 查重叠 → 唯一事实源 → 发布 → 登记 |

## 变更记录

- **2026-05-18**: `auto-*` → `chexian-*` 重命名归簇（auto-channel → chexian-channel, auto-ir-diagnosis → chexian-ir-diagnosis, auto-market-analysis → chexian-market-analysis, auto-ops-review → chexian-ops-review, auto-pricing → chexian-pricing-decision）
- **2026-05-29**: 全量同步本地最新版本到仓库
- **2026-05-30**: 新增 `commit-push-pr-core` — 从 chexian 项目 `commit-push-pr` 抽象出的项目无关基座（L1 骨架 + L2 通用护栏 + L3 方法层），「方法复用，非内容复用」
- **2026-06-04**: 新增 `xcl-html2pdf`（HTML→印刷级 PDF 基座，含零依赖 CDP 验收 driver）+ `company-vortex-card`（在基座之上的涡旋诊断 12 页视觉卡片）。由本地命令 `xcl_html2pdf` 升级、抽象分层而来——基座不限于涡旋诊断，可做任意印刷级报告
- **2026-06-04**: `xcl-html2pdf` 把字体/字号分级/字色规范上提固化为 `report-skin.css`（标准报告皮肤，单一真相源——改规范只改一处，所有报告同步生效）；skeleton 改用标准 class，`company-vortex-card` 模板与之同源
- **2026-06-07**: 新增 `extract-backlog-governance` — 项目无关的 backlog 治理审计技能。固定 6 条普适原则（由 backlog 的 6 种固有失败模式反推，非照搬大厂机制）+ 零依赖 `governance_stats.py`（有 `gh` 拉 PR 历史算结构化指标与规则命中率，无则回退 `git log`，降级显式注明不静默）。「方法复用，非内容复用」
- **2026-06-09**: 全仓技能治理重构 — 新增 `scripts/validate_skills.py` 自动巡检器（frontmatter 模式 / requires_skills 声明↔代码双向核对 / L1 横向边 / 死链 / 明文凭据，12 类错误 3 类警告）+ 18 项契约测试；19 个技能 frontmatter 统一（字段序 / version 引号 / 约定外字段清零）；压缩超长 description、消除 description 工作流摘要反模式；`crystallize-skill`/`ui-redesign` 安装指引由 npx 快照模型更正为 sync-skills 直连模型；脱敏文档中泄漏的生产凭据
