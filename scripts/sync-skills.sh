#!/usr/bin/env bash
#
# sync-skills.sh — 让本仓自研技能「改源即生效」的开发期同步器。
#
# 背景：本仓的技能此前经 `npx skills add` 拉成 ~/.agents/skills 下的快照副本，
# 再由 ~/.claude/skills 软链暴露给 Claude。快照是手动、滞后的——改完 git 源
# 不重跑 npx 就不生效，新技能甚至完全没装。本脚本把 ~/.claude/skills/<技能>
# 直接软链到 git 工作树 skills/<技能>，彻底绕过 .agents 快照层与 npx：
# 唯一真理源 = git 工作树，改源即生效，永不漂移。push 仅用于发布给别人。
#
# 用法：
#   scripts/sync-skills.sh            # = link，建/修软链（幂等，可反复跑）
#   scripts/sync-skills.sh link
#   scripts/sync-skills.sh doctor     # 只读体检，列出漂移项；有漂移则退出码 1
#   scripts/sync-skills.sh unlink     # 解除直连，删除本仓技能在可见层的软链（不碰实体/源）
#
# 兼容 macOS 自带 bash 3.2；realpath 走 python3（系统自带）。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="$REPO/skills"
DEST="$HOME/.claude/skills"
ARCHIVE="$DEST/_archive"
CMD="${1:-link}"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
chg()  { printf "  \033[36m→\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$*"; }

realpath_of() { python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"; }

[ -d "$SKILLS_SRC" ] || { echo "找不到技能源目录: $SKILLS_SRC"; exit 1; }
mkdir -p "$DEST"

linked=0; fixed=0; already=0; issues=0; removed=0

for d in "$SKILLS_SRC"/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  src="${d%/}"
  dst="$DEST/$name"

  # 期望状态：dst 是软链，且最终指向 == git 源
  is_direct=0
  if [ -L "$dst" ]; then
    [ "$(realpath_of "$dst")" = "$src" ] && is_direct=1
  fi

  case "$CMD" in
    unlink)
      if [ "$is_direct" = 1 ]; then rm "$dst"; chg "$name 已解除直连软链"; removed=$((removed + 1));
      else [ -e "$dst" ] || [ -L "$dst" ] && warn "$name 非本脚本所建直连，跳过"; fi
      ;;

    doctor)
      if [ "$is_direct" = 1 ]; then already=$((already + 1)); ok "$name 已直连";
      elif [ -L "$dst" ]; then warn "$name 软链指向别处 → $(readlink "$dst")"; issues=$((issues + 1));
      elif [ -d "$dst" ]; then warn "$name 是实体副本（非直连，可能为旧 npx 快照）"; issues=$((issues + 1));
      elif [ -e "$dst" ]; then warn "$name 被非目录文件占用"; issues=$((issues + 1));
      else warn "$name 未安装"; issues=$((issues + 1)); fi
      ;;

    link)
      if [ "$is_direct" = 1 ]; then already=$((already + 1)); continue; fi
      if [ -L "$dst" ]; then
        rm "$dst"; ln -s "$src" "$dst"; chg "$name 软链重指向 git 源"; fixed=$((fixed + 1))
      elif [ -d "$dst" ]; then
        mkdir -p "$ARCHIVE"; mv "$dst" "$ARCHIVE/$name.$(date +%s)"
        ln -s "$src" "$dst"; chg "$name 实体副本已归档并改为直连"; fixed=$((fixed + 1))
      elif [ -e "$dst" ]; then
        warn "$name 被非目录文件占用，跳过（请手动处理）"; issues=$((issues + 1))
      else
        ln -s "$src" "$dst"; chg "$name 新建直连软链"; linked=$((linked + 1))
      fi
      ;;

    *) echo "未知命令: $CMD（可用: link | doctor | unlink）"; exit 2 ;;
  esac
done

echo "—— 汇总 ——"
case "$CMD" in
  doctor) echo "已直连 $already · 需处理 $issues"; [ "$issues" -gt 0 ] && exit 1 || exit 0 ;;
  unlink) echo "解除 $removed" ;;
  link)   echo "新建 $linked · 修复 $fixed · 已直连 $already"
          [ "$issues" -gt 0 ] && echo "另有 $issues 项需手动处理" || true ;;
esac
