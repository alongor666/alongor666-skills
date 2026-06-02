---
name: cleanup-worktrees
description: >
  Use when 用户说"清理 worktree / cleanup worktrees / 回收已合并的 worktree /
  worktree 太多清一下"，或 PR 合并后要批量回收对应 worktree 与本地分支、阶段性回收
  磁盘时。项目无关的通用 git worktree 安全回收器：识别多来源 worktree（人工 /
  sub-agent / codex CLI）、陈旧锁、squash 落地、脏残留，默认只删零损失项。
version: 2.0.0
user_invocable: true
requires:
  - git
  - gh CLI（可选：squash-merge PR 落地判定，缺失自动降级）
---

# cleanup-worktrees：多来源 git worktree 安全回收器

## Overview

批量回收**已落地到默认分支**的 git worktree 与本地分支。核心洞察：worktree 是
**多生产者**的（人工 `claude/`·`chore/`、sub-agent `worktree-agent-*`、codex `codex/`），
单一前缀 + 单一目录的假设会让清理器在真实仓库近乎失效。本 skill 用
**「纳管路径 ∩ 分支前缀白名单」二维判定 + 陈旧锁感知 + 语义(非拓扑)落地判定**回收。

**永不动**：codex CLI 的 `.codex/worktrees/`（自管）、当前 / 主 worktree、
**运行中会话持有的 locked worktree**、含未落地工作的脏 worktree。

## When to Use

- PR 合并后回收对应 worktree（含兄弟目录、sub-agent `worktree-agent-*`、locked 残留）
- worktree 堆积、阶段性回收磁盘
- 清理前先盘点（`--dry-run`）

**NOT for**：codex CLI 自管的 `.codex/worktrees/`；远程分支删除（PR 合并时平台自管）；
含未落地工作的脏 / 未合并 WIP（用户须先合并或手动 `git branch -D`）。

## 三种模式

| 调用 | 行为 |
|------|------|
| `/cleanup-worktrees` | **默认安全**：只自动清理「明确零损失」项（clean + 已落地）。需备份 / 有疑虑的项**只列建议不删**。 |
| `/cleanup-worktrees --dry-run` | 全部只列不动（含会被自动清理的）。 |
| `/cleanup-worktrees --archive` | 激进回收：对「已合并脏残留」「判不出落地但有领先 commit」的项，**先导出 patch 到 `$WT_ARCHIVE`(默认 `~/.worktree-archive`) 再清理**。 |

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

## 执行（单一自包含脚本，一次执行）

> v1 分块导致跨 shell 函数丢失，已废弃。AI 按下方脚本一次执行，再贴出报告。
> 模式经 `$1` 传入：空 = 默认安全 / `--dry-run` / `--archive`。

```bash
set -uo pipefail
MODE="${1:-}"                                   # ''|--dry-run|--archive
ARCHIVE_ROOT="${WT_ARCHIVE:-$HOME/.worktree-archive}/orphan-worktrees-$(date +%Y%m%d)"
# 纳管分支前缀白名单（可按需增删；codex/ 仅在非 .codex/ 路径下纳管，见 in_scope）
PREFIXES=("claude/" "worktree-agent-" "codex/" "chore/")

# 探测默认分支（支持 main/master/develop；本地读优先，缺失回落 main）
BASE="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
BASE="${BASE:-main}"
git fetch origin "$BASE" 2>/dev/null || true
MAIN_WT="$(git rev-parse --show-toplevel)"
REPO="$(basename "$MAIN_WT")"
PARENT="$(dirname "$MAIN_WT")"

# ——— helper ———
prefix_ok() { local b="$1"; for p in "${PREFIXES[@]}"; do case "$b" in "$p"*) return 0;; esac; done; return 1; }
in_scope() {  # $1=path  纳管: .claude/worktrees/ 内 或 兄弟目录 <parent>/<repo>-*; 硬排除 .codex/
  local p="$1"
  case "$p" in */.codex/worktrees/*) return 1;; esac
  case "$p" in */.claude/worktrees/*) return 0;; esac
  case "$p" in "$PARENT/$REPO"-*) return 0;; esac
  return 1
}
lock_pid() { local wt="$1" gd lf; gd="$(git -C "$wt" rev-parse --git-dir 2>/dev/null)"; lf="$gd/locked"
  [ -f "$lf" ] && grep -oE 'pid [0-9]+' "$lf" | grep -oE '[0-9]+' | head -1; }
landed() {  # echo 依据并 return 0 = 已落地（拓扑祖先 → cherry patch-id → gh PR squash）
  local wt="$1" head="$2" br="$3"
  git merge-base --is-ancestor "$head" "origin/$BASE" 2>/dev/null && { echo "ancestor"; return 0; }
  [ "$(git -C "$wt" cherry "origin/$BASE" HEAD 2>/dev/null | grep -c '^+')" = "0" ] && { echo "cherry-equiv"; return 0; }
  if command -v gh >/dev/null 2>&1; then
    local n; n="$(gh pr list --head "$br" --state merged --json number -q '.[0].number' 2>/dev/null)"
    [ -n "$n" ] && { echo "pr#$n"; return 0; }
  fi; return 1
}
mode_only_dirty() {  # 仅文件 mode 退化、内容 0 改动、无 untracked
  local wt="$1"
  [ -n "$(git -C "$wt" status --porcelain)" ] || return 1
  [ -z "$(git -C "$wt" status --porcelain | grep '^??')" ] || return 1
  [ -z "$(git -C "$wt" diff --shortstat)" ]
}
archive_wt() {  # 成功才 echo 归档路径并 return 0；任何一步失败 return 1（调用方据此拒删）
  local wt="$1" br="$2" tag="$3"
  local d="$ARCHIVE_ROOT/$tag"                 # 拆行：bash 3.2 下 set -u 不允许同一 local 引用未声明完的 $tag
  mkdir -p "$d" || return 1
  git -C "$wt" format-patch "origin/$BASE..HEAD" -o "$d" >/dev/null 2>&1
  git -C "$wt" diff HEAD > "$d/dirty.patch" || return 1
  { echo "branch=$br"; echo "HEAD=$(git -C "$wt" rev-parse HEAD)"; echo "archived=$(date +%Y-%m-%dT%H:%M:%S)"; } > "$d/meta.txt"
  [ -s "$d/meta.txt" ] && echo "$d"           # meta 落盘=备份链全过，输出路径
}
do_remove() { local wt="$1" br="$2" force="${3:-}"
  [ "$MODE" = "--dry-run" ] && { echo "  (dry-run 不执行)"; return 0; }
  git worktree unlock "$wt" 2>/dev/null || true
  git worktree remove ${force:+--force} "$wt" && git branch -D "$br" 2>/dev/null; }

REMOVED=(); SKIPPED=(); LISTED=()

while IFS= read -r line; do
  case "$line" in
    "worktree "*) P="${line#worktree }"; H=""; B=""; LK=0; PR=0 ;;
    "HEAD "*)     H="${line#HEAD }" ;;
    "branch "*)   B="${line#branch refs/heads/}" ;;
    "detached")   B="__detached__" ;;
    "locked"*)    LK=1 ;;
    "prunable"*)  PR=1 ;;
    "")  # —— 块结束，开始判定 ——
      [ -z "${P:-}" ] && continue
      name="$(basename "$P")"
      if [ "$PR" = 1 ] || [ ! -d "$P" ]; then SKIPPED+=("$name: prunable/工作树丢失 → 由收尾 prune 处理"); P=""; continue; fi
      if [ "$P" = "$MAIN_WT" ]; then P=""; continue; fi                       # 主/当前 worktree 静默跳过
      if ! in_scope "$P"; then SKIPPED+=("$name: 路径不纳管($P)"); P=""; continue; fi
      if [ "$B" = "__detached__" ]; then SKIPPED+=("$name: detached HEAD"); P=""; continue; fi
      if ! prefix_ok "$B"; then SKIPPED+=("$name: 分支前缀'$B'不在白名单"); P=""; continue; fi
      if [ "$LK" = 1 ]; then
        pid="$(lock_pid "$P")"
        if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
          SKIPPED+=("$name: locked 且持锁进程 pid $pid 存活 → 保护运行中会话"); P=""; continue
        fi
        echo "ℹ $name: 陈旧锁(pid ${pid:-?} 已死)，可安全解锁"
      fi
      # 纯 mode 退化 → 恢复后继续按 clean
      if mode_only_dirty "$P"; then
        echo "ℹ $name: 仅文件 mode 退化、内容 0 改动 → 恢复"
        [ "$MODE" != "--dry-run" ] && git -C "$P" checkout -- . 2>/dev/null || true
      fi
      DIRTY="$(git -C "$P" status --porcelain)"
      if [ -z "$DIRTY" ]; then
        if why="$(landed "$P" "$H" "$B")"; then
          echo "REMOVE $name (branch=$B, head=${H:0:8}, 落地依据=$why)"
          do_remove "$P" "$B"; REMOVED+=("$name [$why]")
        else
          if [ "$MODE" = "--archive" ]; then
            if d="$(archive_wt "$P" "$B" "$name")" && [ -n "$d" ]; then
              echo "ARCHIVE+REMOVE $name → $d"; do_remove "$P" "$B"; REMOVED+=("$name [archived: 有领先commit]")
            else
              SKIPPED+=("$name: 备份失败，拒绝删除（安全网）")
            fi
          else
            LISTED+=("$name: clean 但未判定落地、有领先 commit → 加 --archive 备份后清理")
          fi
        fi
      else
        if git merge-base --is-ancestor "$H" "origin/$BASE" 2>/dev/null; then
          if [ "$MODE" = "--archive" ]; then
            if d="$(archive_wt "$P" "$B" "$name")" && [ -n "$d" ]; then
              echo "ARCHIVE+REMOVE $name (脏残留, HEAD已合并) → $d"; do_remove "$P" "$B" --force; REMOVED+=("$name [archived: 脏残留]")
            else
              SKIPPED+=("$name: 备份失败，拒绝删除（安全网）")
            fi
          else
            LISTED+=("$name: HEAD 已合并但有脏残留 → 加 --archive 备份后清理")
          fi
        else
          SKIPPED+=("$name: 脏 + HEAD 未落地 → 可能有未保存工作，需人工确认")
        fi
      fi
      P="" ;;
  esac
done < <(git worktree list --porcelain; echo)

# —— 收尾：prune 死引用 + 结构化报告 ——
[ "$MODE" != "--dry-run" ] && git worktree prune -v
echo ""; echo "================ 清理报告（MODE=${MODE:-默认安全}, BASE=$BASE）================"
echo "清理 ${#REMOVED[@]} 个:"; printf '  ✓ %s\n' "${REMOVED[@]:-（无）}"
echo "待定 ${#LISTED[@]} 个（建议加 --archive）:"; printf '  • %s\n' "${LISTED[@]:-（无）}"
echo "跳过 ${#SKIPPED[@]} 个:"; printf '  - %s\n' "${SKIPPED[@]:-（无）}"
echo ""; git worktree list
```

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

> **教训**：worktree 是**多生产者**的。单一理想前缀 + 单一目录的假设会让清理器在真实
> 仓库近乎失效。判定须「路径 ∩ 前缀」二维 + 陈旧锁感知 + 落地的**语义**(非拓扑)判定。
> 另：`bash -n` 语法通过 ≠ 正确——`set -u` 下单行 `local a=$1 d="$x/$a"` 会触发 unbound
> 而静默跳过备份；这类运行时坑只有真实执行（沙箱跑 `--archive`）才暴露，必须实测。
