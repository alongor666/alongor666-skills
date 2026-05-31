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

## 技能

### 车险业务分析

| 技能 | 说明 |
|------|------|
| **chexian-channel** | 渠道评估 — 评估是否应该投入、继续或退出一个分销渠道（4S 店、二级经销商、经纪人、代理人等） |
| **chexian-ir-diagnosis** | 出险率诊断 — 诊断车险出险率恶化，调查出险率上升原因，对赔付频率进行根因分析 |
| **chexian-market-analysis** | 市场分析 — 分析车险市场的竞争格局、增长机会和风险评估 |
| **chexian-ops-review** | 经营复盘 — 结合市场、定价和渠道分析，形成完整诊断与资源配置建议 |
| **chexian-pricing-decision** | 定价决策 — 商业车险保费报价、核保决策、费率水平判断 |

### 通用工具

| 技能 | 说明 |
|------|------|
| **commit-push-pr-core** | 提交建 PR 工作流基座 — 项目无关的 commit→push→PR 流程，含跨项目通用 git 护栏（大文件拦截 / unrelated-histories / rebase 后 lockfile 同步 / push 后回主干）+ 可挂载的项目红线自审与自进化机制；设计为被各项目薄 wrapper 复用 |
| **company-vortex** | 涡旋分析 — 通过结构动力学/涡旋模型分析上市公司，生成全生命周期诊断报告 |
| **rewrite-conclusion** | 诊断结论重写 — 将 L1 脚本产出的规则化数据提炼为管理层可直接阅读的结构化判断 |
| **ui-redesign** | 页面/模块视觉重做编排 — 配合 Claude Design，项目无关（现场发现技术栈/设计系统），含确定性验收与自进化 |

## 变更记录

- **2026-05-18**: `auto-*` → `chexian-*` 重命名归簇（auto-channel → chexian-channel, auto-ir-diagnosis → chexian-ir-diagnosis, auto-market-analysis → chexian-market-analysis, auto-ops-review → chexian-ops-review, auto-pricing → chexian-pricing-decision）
- **2026-05-29**: 全量同步本地最新版本到仓库
- **2026-05-30**: 新增 `commit-push-pr-core` — 从 chexian 项目 `commit-push-pr` 抽象出的项目无关基座（L1 骨架 + L2 通用护栏 + L3 方法层），「方法复用，非内容复用」
