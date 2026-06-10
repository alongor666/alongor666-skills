---
name: cleanup-worktrees
description: >
  Use when 用户说"清理 worktree / cleanup worktrees / 回收已合并的 worktree /
  worktree 太多清一下"，或 PR 合并后要批量回收对应 worktree 与本地分支、阶段性回收
  磁盘时。项目无关的通用 git worktree 安全回收器：识别多来源 worktree（人工 /
  sub-agent / codex CLI）、陈旧锁、squash 落地、脏残留，默认只删零损失项。
user_invocable: true
version: "2.0.1"
---

# cleanup-worktrees：多来源 git worktree 安全回收器

## Overview

批量回收**已落地到默认分支**的 git worktree 与本地分支。核心洞察：worktree 是
**多生产者**的（人工 `claude/`·`chore/`、sub-agent `worktree-agent-*`、codex `codex/`），
单一前缀 + 单一目录的假设会让清理器在真实仓库近乎失效。本 skill 用
**「纳管路径 ∩ 分支前缀白名单」二维判定 + 陈旧锁感知 + 语义(非拓扑)落地判定**回收。

**永不动**：codex CLI 的 `.codex/worktrees/`（自管）、当前 / 主 worktree、
**运行中会话持有的 locked worktree**、含未落地工作的脏 worktree。

**环境依赖**：git；gh CLI（可选，用于 squash-merge PR 落地判定，缺失自动降级）。

## When to Use

- PR 合并后回收对应 worktree（含兄弟目录、sub-agent `worktree-agent-*`、locked 残留）
- worktree 堆积、阶段性回收磁盘
- 清理前先盘点（`--dry-run`）

**NOT for**：codex CLI 自管的 `.codex/worktrees/`；远程分支删除（PR 合并时平台自管）；
含未落地工作的脏 / 未合并 WIP（用户须先合并或手动 `git branch -D`）。

## 三种模式

| 调用 | 行为 |
|------|------|
| 默认（无参） | **默认安全**：只自动清理「明确零损失」项（clean + 已落地）。需备份 / 有疑虑的项**只列建议不删**。 |
| `--dry-run` | 全部只列不动（含会被自动清理的）。 |
| `--archive` | 激进回收：对「已合并脏残留」「判不出落地但有领先 commit」的项，**先导出 patch 到 `$WT_ARCHIVE`(默认 `~/.worktree-archive`) 再清理**。 |

## 决策矩阵（每个候选 worktree）

| locked? | 工作区 | 落地判定 | 默认模式 | `--archive` |
|---------|--------|----------|----------|-------------|
| 活进程 | — | — | **SKIP**（保护运行中） | SKIP |
| 死/无锁 | clean | 拓扑祖先 ✓ | **REMOVE** | REMOVE |
| 死/无锁 | clean | cherry/PR 已落地 | **REMOVE**（提示依据） | REMOVE |
| 死/无锁 | clean | 有领先 commit、判不出 | LIST（建议 `--archive`） | **备份→REMOVE** |
| 死/无锁 | 纯 mode 退化 | — | **恢复后按 clean 重判** | 同左 |
| 死/无锁 | 脏 + 拓扑祖先 | （脏是残留） | LIST（建议 `--archive`） | **备份脏→REMOVE** |
| 死/无锁 | 脏 + 未落地 | — | **SKIP**（可能有未保存工作） | SKIP（仅提示手动） |

## 执行

脚本抽为**独立文件** `cleanup-worktrees.sh`（与本 SKILL.md 同目录）。

> **为什么不内联**：skill 加载时 SKILL.md 被当模板渲染，bash 脚本里的位置参数
> `$1`/`$2`/`$3`（函数参数）会被插值成空字符串 → helper 函数全部收不到参数、脚本失效。
> 独立 `.sh` 文件不经此渲染，`$N` 安全。**禁止把脚本重新内联回 SKILL.md。**

AI 直接执行本 skill 目录下的脚本（路径取加载时告知的 Base directory，
Claude Code 下为 `~/.claude/skills/cleanup-worktrees/`），再贴出脚本输出的报告：

```bash
bash <skill目录>/cleanup-worktrees.sh             # 默认安全模式
bash <skill目录>/cleanup-worktrees.sh --dry-run   # 只盘点不动
bash <skill目录>/cleanup-worktrees.sh --archive   # 激进回收 + 自动备份
```

脚本一次执行完成「探测默认分支 → 枚举候选 → 逐个判定 → 清理 / 备份 → prune 收尾 →
结构化报告」。逻辑已在 bash 3.2 沙箱 7 场景 + `--archive` 实测验证。

## 红线

| 红线 | 做法 |
|------|------|
| 永不动 `.codex/worktrees/` | `in_scope()` 第一条硬排除 |
| 永不动当前 / 主 worktree | `$P = $MAIN_WT` 静默跳过 |
| 永不动 detached HEAD | `__detached__` → SKIP |
| **永不动运行中会话的 locked worktree** | 解析 pid + `ps` 判存活，**活则 SKIP**，只对陈旧锁解锁 |
| **脏 + HEAD 未落地永不自动删** | 唯一可能含未保存工作的情形，恒 SKIP 待人工 |
| 删「有内容」前必备份 | `--archive` 下 `format-patch` + `diff HEAD` 落盘 `$WT_ARCHIVE`，**备份失败拒删** |
| 落地判定不止拓扑祖先 | `merge-base` → `git cherry` → `gh pr merged` 三级，识别 squash/rebase merge |
| `--force remove` 仅限已备份脏残留 | `do_remove ... --force` 只在备份成功后调用 |
| 永不用 `git branch --merged` | 它对 worktree 持有分支漏判，用 `merge-base --is-ancestor` |
| 永不在 webhook/cron 自动跑 | 必须用户主动触发 |

## Common Mistakes（设计教训 · 真实回归案例）

某真实仓库一次清理中，`.claude/worktrees/` + 兄弟目录共 **10 个**待清理对象：
1×人工(locked) + 3×sub-agent `worktree-agent-*`(locked) + 1×`codex/`(在 `.claude/` 下)
+ 4×兄弟目录 + 1×prunable 死引用。

- **前代清理器（单 `claude/` 前缀 + 单 `.claude/worktrees/` 目录假设）实际有效清理 = 0**：
  唯一匹配项因 locked、且 `git worktree remove` 无 unlock / 无 `--force` / 无失败处理而直接失败，
  其余 9 个被前缀 / 路径过滤全漏。
- **本版覆盖全部 10 个**：陈旧锁自动解锁、兄弟目录纳管、前缀白名单、squash 落地判定、
  脏残留 `--archive` 备份、prunable 收尾 prune。

**踩过的坑**：
1. **worktree 是多生产者的**——单一理想前缀 + 单一目录的假设会让清理器在真实仓库近乎失效。
   判定须「路径 ∩ 前缀」二维 + 陈旧锁感知 + 落地的**语义**(非拓扑)判定。
2. **`bash -n` 通过 ≠ 正确**——`set -u` 下单行 `local a=$1 d="$x/$a"` 会触发 unbound
   而静默跳过备份；这类运行时坑只有真实执行（沙箱跑 `--archive`）才暴露，必须实测。
3. **skill 脚本禁止内联**——SKILL.md 模板渲染会插值掉脚本里的 `$1`/`$2`/`$3`，
   必须抽独立 `.sh`。dogfooding（真实加载 skill 执行）才暴露此坑，沙箱直接跑文件不会。

## changelog

- **2.0.1**：脚本抽为独立 `cleanup-worktrees.sh`，修复 SKILL.md 模板渲染插值掉位置参数
  `$N` 致脚本失效的缺陷（dogfooding 暴露）。
- **2.0.0**：实战驱动重构。修复前代「多目标命中少、locked 清不掉」的零有效命中问题。
  新增陈旧锁自动解锁、兄弟目录纳管、前缀×路径二维判定、squash/cherry/gh 落地判定、
  纯 mode 退化恢复 + 脏残留备份、prunable prune、`--dry-run`/`--archive` 双开关。
