---
name: sync-skills
description: >
  Use when 用户说"技能没同步 / 技能改了不生效 / 同步技能 / sync skills / 技能软链 /
  直连技能仓 / 给技能仓装钩子"，或新机器要让某个 git 技能仓对 Claude 生效、
  或误跑 `npx skills add --all` 后要把直连修回时。项目无关：把任意 git 技能仓的
  `<subdir>/*` 直连软链到 `~/.claude/skills`，改源即生效；并可装 git 钩子自动补链。
user_invocable: true
version: "1.1.0"
---

# sync-skills：技能仓「改源即生效」直连同步器

## Overview

自研技能常经 `npx skills add` 拉成快照副本再暴露给 Claude——快照手动滞后，改完
git 源不重跑 npx 就不生效，新技能甚至完全没装。本 skill 把 `~/.claude/skills/<name>`
**直接软链到 git 工作树** `<repo>/<subdir>/<name>`，绕过快照层：**Claude 读到的就是
git 工作树本身，改源即生效、永不漂移**。push 仅用于发布给别人。

项目无关——靠 `--repo/--dest/--subdir` 适配任意技能仓，不写死路径。

**环境依赖**：git；python3（realpath 解析）。

## When to Use

- 改了技能源码却不生效、或新增技能没出现在列表里
- 新机器克隆技能仓后，要一次性让它对 Claude 生效
- 误跑 `npx skills add --all`，直连被覆盖回旧快照，要修回
- 给一个技能仓装「合并/切分支自动补链」的 git 钩子

**NOT for**：发布技能给别人/别的机器（那用 `npx skills add`）；装第三方仓的技能。

## Quick Reference

脚本：`sync-skills.sh`（与本文件同目录）。子命令：

| 命令 | 作用 |
|------|------|
| `link`（默认） | 建/修直连软链，幂等可反复跑 |
| `doctor` | 只读体检，列出漂移项（指向别处/实体副本/未安装），有漂移退出码 1 |
| `unlink` | 解除本脚本所建的直连软链（不碰实体与源） |
| `install-hooks` | 给目标仓装 `post-merge`/`post-checkout` 钩子并设 `core.hooksPath` |

选项（通用）：`--repo R`（默认当前 git 仓库根）、`--dest D`（默认 `~/.claude/skills`）、
`--subdir S`（默认 `skills`）、`--quiet`（link 无变化时静默，钩子用）。

```bash
# 体检当前技能仓
skills/sync-skills/sync-skills.sh doctor
# 建/修直连
skills/sync-skills/sync-skills.sh link
# 给当前仓装自动补链钩子（一次性）
skills/sync-skills/sync-skills.sh install-hooks
# 同步另一个技能仓（技能放在仓库根而非 skills/ 子目录）
skills/sync-skills/sync-skills.sh link --repo ~/other-skills --subdir .
```

## 工作原理

```
git 工作树 <repo>/<subdir>/<name>  ──软链──→  <dest>/<name>  → Claude 发现
```

- `doctor` 用 realpath 比对每个技能的可见层条目是否正好指回 git 源，四态归类。
- `link` 幂等：已正确直连则跳过；旧软链重指向；实体副本先归档到 `<dest>/_archive/` 再改直连。
- `install-hooks` 生成的钩子调用本脚本（绝对路径，install 时固化）做 `link --quiet`，
  失败绝不阻断 git；`core.hooksPath` 是本机配置，不随 clone，**新机克隆后重跑一次本命令**。
- **防劫持护栏（v1.1.0，双层）**：① 脚本层——`--repo`（或默认推导）落在 linked worktree 时，
  自动用 `git-common-dir` 改指主仓根并提示，全部子命令生效；② 钩子层——生成的钩子在
  linked worktree 内直接跳过。背景：worktree 创建会触发 post-checkout，曾把全局软链整体
  指进 worktree，worktree 一删 19 条链全断（2026-06-11 实测）。测试见 `tests/test_worktree_guard.py`。

## Common Mistakes

- **改完技能仍跑旧版** → 多半是可见层仍是 `.agents` 旧快照而非直连；跑 `doctor` 确认、`link` 修回。
- **`npx skills add --all` 之后又不同步** → `--all` 会把直连覆盖回快照；`doctor` 会报「指向别处」，`link` 一键修回。
- **新仓技能不在 `skills/` 子目录** → 用 `--subdir` 指定（技能在仓库根则 `--subdir .`）。
- **新机器钩子不触发** → `core.hooksPath` 是本机配置；克隆后重跑 `install-hooks`。
- **开过 worktree 后技能全失效 / doctor 报"指向别处"且目标在 `.claude/worktrees/`** → 旧版钩子被 worktree 劫持所致（v1.1.0 护栏已根治）；从主仓跑 `link` 一键修回；若 `core.hooksPath` 被 worktree 工具改走，重跑 `install-hooks` 恢复。

相关 memory：技能同步模型见 `skills-install-via-npx`。
