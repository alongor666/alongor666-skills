# 技能逐一优化队列（唯一权威入口）

> 工作流约定：**一次一个技能、一个 PR**，按下表顺序推进。本文件是该工作流的唯一待办队列
> （对应 extract-backlog-governance 六原则：唯一队列 / 意图先行 / 原子可逆 / 顺序有据 /
> 完成即证明 / 同步现实）。每轮收尾更新状态列；过尺无发现的技能标"✅ 过尺通过·免刨"，
> **不发空 PR**——不为显得干了活而多刨。

## 每轮任务流（固定六步）

1. **同步**：`git fetch origin main && git merge origin/main`
2. **过尺**：机检 `python3 scripts/validate_skills.py --strict` + 正文行数；人检五项——
   私人路径/基础设施信息暴露、硬编码安装位（ADR-001）、SSOT 复制粘贴（应委托
   chexian-report-shell/lib）、requires_skills 口径（ADR-005）、文档命令可跑性（活体尺：
   模板/命令照抄能不能跑通）
3. **慢刨**：只修证据确凿项，单技能边界内；动 L0 基座先跑其 `tests/`（ADR-004）
4. **验证门**：`--strict` 0 错误 0 警告 + 全套 pytest 全绿 + 默认行为实测不变，三者齐过才保留
5. **交活**：单技能单 PR（draft），PR 描述写"过尺发现 → 改动 → 验证"，同轮更新本队列状态
6. **下一个**：等当前 PR 合并后才开下一轮（归因单位 = PR）

## 队列（顺序有据：隐私/正确性 P0 → 架构一致性 P1 → 重资产活体对账 P2 → 轻量收尾）

| # | 技能 | 意图（为什么排这里 / 已知线索） | 状态 |
|--:|------|--------------------------------|------|
| 1 | chexian-ir-diagnosis | P0：保单级模板 `glob("~/...")` 不展开波浪号必然空跑（静默失败）；数据湖路径未接 `CHEXIAN_DATA_ROOT` 单一事实源 | 🔨 本轮 |
| 2 | chexian-report-shell | P0：push.py 写死 VPS IP 与部署用户名，应下沉环境变量（v1.22 只收敛了数据湖路径） | ⏳ |
| 3 | company-vortex | P1：`$WORKDIR` 私人默认值散布多处（已可覆盖）；外部脚本依赖的降级路径需活体核对 | ⏳ |
| 4 | diagnose-org-weekly | P2：重资产 L1，README/SKILL 与渲染器入口不变量（SHELL_ROOT 注入）对账 | ⏳ |
| 5 | diagnose-period-trend | P2：重资产 L1，同上口径对账 | ⏳ |
| 6 | diagnose-loss-development | P2：重资产 L1，同上口径对账 | ⏳ |
| 7 | xcl-html2pdf | P2：L0 基座，driver/bundle 文档命令活体对账，三套皮肤引用完整性 | ⏳ |
| 8 | chexian-channel | 轻量：description 触发词与正文一致性 | ⏳ |
| 9 | chexian-market-analysis | 轻量：同上 | ⏳ |
| 10 | chexian-pricing-decision | 轻量：同上 | ⏳ |
| 11 | chexian-ops-review | L2：编排边（调 market/channel/pricing）记录在正文而非 requires_skills 的口径核对 | ⏳ |
| 12 | company-vortex-card | L2：产物消费边（读 vortex 的 .md）口径核对 | ⏳ |
| 13 | rewrite-conclusion | 轻量 | ⏳ |
| 14 | commit-push-pr-core | L0：与实际提交流程对账 | ⏳ |
| 15 | sync-skills | 轻量（v1.1 护栏刚收口） | ⏳ |
| 16 | cleanup-worktrees | 轻量 | ⏳ |
| 17 | crystallize-skill | 轻量 | ⏳ |
| 18 | ui-redesign | 轻量 | ⏳ |
| 19 | extract-backlog-governance | 轻量 | ⏳ |
| 20 | luban | — | ✅ 已完成（#22 安装 / #23 描述压缩 / #24 渐进披露拆分） |

## 完成记录（完成即证明：PR 链接 = 凭证）

- luban：#22、#23、#24（均已合并）
