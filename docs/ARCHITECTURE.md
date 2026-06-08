# alongor666-skills 架构文档

> 架构师评审与目标态设计。落盘日期：2026-06-08。
> 配套决策记录见 [`docs/adr/`](./adr/)。

## 1. 概述

个人单人维护的 Claude Code 技能集，**平铺命名空间**，覆盖三大领域（车险经营 / 上市公司诊断 / 工程治理）+ 一个可视化横切层。技能之间通过**运行时 `sys.path` 注入**复用共享 Python 库，并已建立单一事实源（SSOT）下沉的良好实践。

本文档把一次结构性审计的发现，连同对"复用机制"的代码级尽调，固化为可追溯的架构决策与分步迁移路线。

## 2. 需求与约束

| 非功能性需求（NFR） | 现状 | 目标 |
|---|---|---|
| 可发现性（AI 选对技能） | A · 优秀（`Use when` + 中英双触发词） | 保持 |
| 可复用性（基座被多技能用） | 已建 3 基座 + SSOT 下沉 | 强化、显式化 |
| 安装健壮性（多途径都能跑） | ⚠️ 脆弱（见 ADR-001） | 修复 |
| 可维护性（改一处不连锁） | ⚠️ 被硬编码路径 + 横向耦合拖累 | 修复 |
| 可测试性（枢纽回归） | 仅基座有 tests/ | 枢纽全覆盖 |
| 运维复杂度 | 低（单人） | **必须保持低** |

> **首要约束（防过度工程化）**：单人个人项目。任何"声明式依赖管理器""插件框架"级别方案都属过度设计。所有决策以**最小机制 + 零新增运行时依赖**为准绳。

## 3. 现状架构

```
┌─────────────────────────────────────────────────────────────┐
│  L2 编排层      chexian-ops-review        company-vortex-card │
│                  (合并 3 分析)      │        (诊断→卡片)        │
└───────────┬──────────────────────┼──────────────┬───────────┘
            │                      │              │
┌───────────▼──────────────────────▼──────────────▼───────────┐
│  L1 业务层                                                    │
│   chexian-{channel,pricing,market,ir-diagnosis}              │
│   diagnose-{org-weekly ──┐ period-trend, loss-development}   │
│   company-vortex          │ rewrite-conclusion               │
│        ❌ 横向耦合 ────────┘ org-weekly 注入 period-trend/lib │
└───────────┬──────────────────────────────────┬──────────────┘
            │ sys.path.insert(硬编码绝对路径)    │
┌───────────▼──────────────────────────────────▼──────────────┐
│  L0 基础设施基座（复用枢纽）                                   │
│   chexian-report-shell(lib: 渲染/亮灯/SSOT标签/时间窗/查询)   │
│   xcl-html2pdf(版面/翻页/driver)    commit-push-pr-core      │
└──────────────────────────────────────────────────────────────┘

  横切通用工具（不分层）：cleanup-worktrees · sync-skills ·
                        extract-backlog-governance · ui-redesign ·
                        crystallize-skill（已正名）
```

### 3.1 尽调暴露的三个真问题

1. **🔴 安装方式与依赖路径不一致**：README 提供 `npx skills add -g`（装到 `~/.claude/skills` 或 `~/.agents`）与 `git clone … ~/.claude/plugins/alongor666-skills` 两种安装；但代码硬编码 `Path.home()/".claude/skills/chexian-report-shell/lib"`。→ 走 git clone 方式安装时，全部 `diagnose-*` 因找不到基座而崩。**这是可复现缺陷，非洁癖。** → ADR-001
2. **🟠 业务层横向耦合**：`diagnose-org-weekly` 的 `render_v1/v3/v4_org.py` 注入 `diagnose-period-trend/lib`。业务技能依赖另一个业务技能，违反分层。 → ADR-002
3. **🟡 隐式依赖图**：依赖只存在于散落的 `sys.path` 字符串里，无声明。`diagnose-html-render → chexian-report-shell`（2026-05-17 重命名）已实际付出"全局改 path 字符串"的维护税。 → ADR-001 / ADR-005

### 3.2 做得好的（目标态须保留）

- **SSOT 下沉**：亮灯阈值、客户类别标签、时间窗口构造集中在 `chexian-report-shell/lib`，业务技能用 thin shim 委托。
- 基座 `user_invocable: false` 主动隐藏基础设施层。
- 语义化版本号普遍规范。

## 4. 关键架构决策（ADR 索引）

| 编号 | 决策 | 阶段 | 状态 |
|---|---|---|---|
| [ADR-001](./adr/ADR-001-skill-path-resolver.md) | 统一技能路径解析器，消除硬编码安装路径 | P0 | Accepted |
| [ADR-002](./adr/ADR-002-layering-no-lateral-deps.md) | 三层 + 横切，禁止业务层横向 import | P1 | Accepted |
| [ADR-003](./adr/ADR-003-naming-crystallize-rename.md) | 命名规范 + `crystallize-skill` 正名 | P0 | Accepted |
| [ADR-004](./adr/ADR-004-hub-test-version-contract.md) | 复用枢纽的测试与版本契约 | P1 | Accepted |
| [ADR-005](./adr/ADR-005-dependency-declaration.md) | 依赖声明与文档模板约定 | P2 | Accepted |

## 5. 目标态架构

```
L2 编排   ops-review · vortex-card        ┐
L1 业务   chexian-* · diagnose-* · vortex │  仅向下依赖
          rewrite-conclusion             │  （L1↔L1 已禁止）
L0 基座   report-shell · xcl-html2pdf · commit-push-pr-core
              ▲ 全部经 skill_path() 解析，安装位置无关（ADR-001）
横切      cleanup · sync · governance · ui-redesign · crystallize-skill
```

干净的**星形依赖**：所有箭头指向 L0，无横向边，路径解析与安装方式解耦。

## 6. 风险与迁移路线图

| 阶段 | 动作 | ADR | 风险 | 工作量 | 状态 |
|---|---|---|---|---|---|
| **P0 立即** | 加 `skill_path()` 解析器，替换所有硬编码 `sys.path` | 001 | 低（向后兼容） | 半天 | ✅ 已交付（PR #14） |
| **P0 立即** | `crystallize-skill` 正名 + 归簇 | 003 | 低 | 1 小时 | ✅ 已交付（PR #14） |
| **P1 短期** | 下沉 org-weekly↔period-trend 共享码到基座，断横向边 | 002 | 中（需回归两报告） | 1 天 | ✅ 已交付（`themes_v2` 下沉基座 `dhr_lib`，6 消费者改走基座取法，横向注入消除） |
| **P1 短期** | `governance_stats.py` 等纯逻辑脚本补最小单测 | 004 | 低 | 半天 | ✅ 已交付（25 项纯函数回归，覆盖正则边界/样本阈值/降级警告） |
| **P2 持续** | SKILL.md 加 `requires_skills` 声明 + 重资产补 README | 005 | 低 | 增量 | ⏳ 待办 |

> P1 遗留（独立后续 PR，中风险）：`diagnose-period-trend` 的 4 处 bootstrap 入口仍内联基座定位逻辑（链式依赖渲染核）。其正确性修正（惰性兜底 + `is_dir`）已在先前提交（PR #14）完成；**本 PR 仅做横向解耦**（`themes_v2` 下沉基座 + 6 消费者改基座取法），未触及这 4 个文件，import 链重构留待后续。

**迁移安全保证**：兄弟回溯优先、原硬编码作**惰性兜底**，每步可独立回滚。注：兄弟回溯优先于旧硬编码（短路），在 sync-skills「软链=消费态」模型下解析目标一致；当工作树兄弟与已安装版本内容不同时目标会变，故不宣称严格"零行为变化"。

## 7. 维护说明

- 新增跨技能依赖时：调用 `chexian-report-shell` 的 `skill_path(name)` 解析依赖根，禁止再写硬编码 `~/.claude/skills/...`。
- 新增技能时：领域技能用领域前缀；项目无关通用工具不强加前缀。
- 修改 L0 基座对外 API 前：先过基座 tests/（见 ADR-004）。
- **不变量（org-weekly 渲染器入口）**：`render_v{1,3,4}_org.py` 的 `from lib.themes_v2 import ...` 无兜底，依赖 `cli.py` 在导入渲染器前已把 `SHELL_ROOT` 注入 `sys.path`。现状下 `cli.py` 是这些渲染器的唯一入口（已核：仅 `cli.py` import 它们）。**若日后新增非 `cli.py` 入口**（如直接脚本调用渲染器），必须在该入口同样注入 `SHELL_ROOT`，或给该 import 补回退——否则 `lib.themes_v2` 解析失败。
