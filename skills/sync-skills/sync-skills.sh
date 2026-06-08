#!/usr/bin/env bash
#
# sync-skills.sh — 让任意 git 技能仓「改源即生效」的项目无关同步器。
#
# 把 <repo>/<subdir>/<name> 直接软链到 <dest>/<name>，绕过 npx 快照层：
# Claude 读到的就是 git 工作树本身，改源即生效、永不漂移。push 仅用于发布给别人。
#
# 用法：
#   sync-skills.sh [link]          建/修直连软链（默认，幂等可反复跑）
#   sync-skills.sh doctor          只读体检，列出漂移项；有漂移则退出码 1
#   sync-skills.sh unlink          解除本脚本所建的直连软链（不碰实体/源）
#   sync-skills.sh install-hooks   给目标仓装 post-merge/post-checkout 钩子并设 core.hooksPath
#
# 选项（任意子命令通用）：
#   --repo R     技能仓路径（默认：当前 git 仓库根）
#   --dest D     安装目录（默认：~/.claude/skills）
#   --subdir S   技能在仓库内的子目录（默认：skills）
#   --quiet      link 无变化时静默（钩子用）
#
# 兼容 macOS 自带 bash 3.2；realpath 走 python3（系统自带）。
set -euo pipefail

CMD="link"; REPO=""; DEST="$HOME/.claude/skills"; SUBDIR="skills"; QUIET=0

usage() { sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    link|doctor|unlink|install-hooks) CMD="$1" ;;
    --repo)   REPO="${2:-}"; shift ;;
    --dest)   DEST="${2:-}"; shift ;;
    --subdir) SUBDIR="${2:-}"; shift ;;
    --quiet)  QUIET=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1"; usage; exit 2 ;;
  esac
  shift
done

if [ -t 1 ]; then C_OK=$'\033[32m'; C_CH=$'\033[36m'; C_WN=$'\033[33m'; C_RS=$'\033[0m';
else C_OK=''; C_CH=''; C_WN=''; C_RS=''; fi
ok()   { printf "  %s✓%s %s\n" "$C_OK" "$C_RS" "$*"; }
chg()  { printf "  %s→%s %s\n" "$C_CH" "$C_RS" "$*"; }
warn() { printf "  %s⚠%s %s\n" "$C_WN" "$C_RS" "$*"; }
realpath_of() { python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"; }

# --repo 默认 = 当前 git 仓库根
if [ -z "$REPO" ]; then
  REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$REPO" ] || { echo "未指定 --repo 且当前不在 git 仓库内"; exit 2; }
fi
REPO="$(cd "$REPO" && pwd)"
SKILLS_SRC="$REPO/$SUBDIR"
ARCHIVE="$DEST/_archive"

install_hooks() {
  local hooks_dir="$REPO/.githooks" self
  self="$(realpath_of "$0")"
  mkdir -p "$hooks_dir"
  cat > "$hooks_dir/post-merge" <<HOOK
#!/usr/bin/env bash
# 由 sync-skills install-hooks 生成。合并/pull 后补齐技能直连软链（幂等零网络，失败不阻断 git）。
"$self" link --repo "\$(git rev-parse --show-toplevel)" --dest "$DEST" --subdir "$SUBDIR" --quiet || true
HOOK
  cat > "$hooks_dir/post-checkout" <<HOOK
#!/usr/bin/env bash
# 由 sync-skills install-hooks 生成。仅分支切换（第三参=1）时补齐技能直连软链。
[ "\${3:-0}" = "1" ] || exit 0
"$self" link --repo "\$(git rev-parse --show-toplevel)" --dest "$DEST" --subdir "$SUBDIR" --quiet || true
HOOK
  chmod +x "$hooks_dir/post-merge" "$hooks_dir/post-checkout"
  git -C "$REPO" config core.hooksPath .githooks
  ok "钩子已装入 ${hooks_dir}，并设 core.hooksPath=.githooks"
  echo "  （core.hooksPath 是本机 git 配置，不随 clone；新机克隆后重跑本命令即可）"
}

[ -d "$SKILLS_SRC" ] || { echo "找不到技能源目录: ${SKILLS_SRC}（用 --subdir 指定）"; exit 1; }

if [ "$CMD" = "install-hooks" ]; then install_hooks; exit 0; fi

mkdir -p "$DEST"
linked=0; fixed=0; already=0; issues=0; removed=0

for d in "$SKILLS_SRC"/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"; src="${d%/}"; dst="$DEST/$name"

  is_direct=0
  if [ -L "$dst" ]; then [ "$(realpath_of "$dst")" = "$src" ] && is_direct=1; fi

  case "$CMD" in
    unlink)
      if [ "$is_direct" = 1 ]; then rm "$dst"; chg "$name 已解除直连"; removed=$((removed + 1)); fi ;;
    doctor)
      if [ "$is_direct" = 1 ]; then already=$((already + 1)); ok "$name 已直连";
      elif [ -L "$dst" ]; then warn "$name 软链指向别处 → $(readlink "$dst")"; issues=$((issues + 1));
      elif [ -d "$dst" ]; then warn "$name 是实体副本（非直连）"; issues=$((issues + 1));
      elif [ -e "$dst" ]; then warn "$name 被非目录文件占用"; issues=$((issues + 1));
      else warn "$name 未安装"; issues=$((issues + 1)); fi ;;
    link)
      if [ "$is_direct" = 1 ]; then already=$((already + 1)); continue; fi
      if [ -L "$dst" ]; then rm "$dst"; ln -s "$src" "$dst"; chg "$name 软链重指向 git 源"; fixed=$((fixed + 1));
      elif [ -d "$dst" ]; then mkdir -p "$ARCHIVE"; mv "$dst" "$ARCHIVE/$name.$(date +%s)"; ln -s "$src" "$dst"; chg "$name 实体副本已归档并改为直连"; fixed=$((fixed + 1));
      elif [ -e "$dst" ]; then warn "$name 被非目录文件占用，跳过"; issues=$((issues + 1));
      else ln -s "$src" "$dst"; chg "$name 新建直连软链"; linked=$((linked + 1)); fi ;;
  esac
done

case "$CMD" in
  doctor) echo "—— 汇总 ——"; echo "已直连 $already · 需处理 $issues"; [ "$issues" -gt 0 ] && exit 1 || exit 0 ;;
  unlink) echo "—— 汇总 ——"; echo "解除 $removed" ;;
  link)
    if [ "$QUIET" = 1 ] && [ "$linked" = 0 ] && [ "$fixed" = 0 ] && [ "$issues" = 0 ]; then exit 0; fi
    echo "—— 汇总 ——"; echo "新建 $linked · 修复 $fixed · 已直连 $already"
    [ "$issues" -gt 0 ] && echo "另有 $issues 项需手动处理" || true ;;
esac
