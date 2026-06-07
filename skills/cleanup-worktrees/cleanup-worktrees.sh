#!/usr/bin/env bash
# cleanup-worktrees v2.0 — 多来源 git worktree 安全回收器
# 用法: bash cleanup-worktrees.sh [--dry-run|--archive]
# 抽为独立脚本(非内联 SKILL.md)：避免 skill 模板渲染插值掉位置参数 $1/$2/$3

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
echo ""; echo "================ 清理报告（MODE=${MODE:-默认安全}, BASE=${BASE}）================"
echo "清理 ${#REMOVED[@]} 个:"; printf '  ✓ %s\n' "${REMOVED[@]:-（无）}"
echo "待定 ${#LISTED[@]} 个（建议加 --archive）:"; printf '  • %s\n' "${LISTED[@]:-（无）}"
echo "跳过 ${#SKIPPED[@]} 个:"; printf '  - %s\n' "${SKIPPED[@]:-（无）}"
echo ""; git worktree list
