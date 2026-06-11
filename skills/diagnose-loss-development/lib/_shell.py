"""chexian-report-shell 根定位（ADR-001，diagnose-loss-development 内集中一处）。

cli.py 与 render.py 都从这里取 SHELL_ROOT，避免路径探测散落两份。
策略与基座 chexian-report-shell/lib/skill_path.py 一致（引导期无法 import 基座，故内联）：
$CLAUDE_SKILLS_DIR 显式覆盖 > 兄弟回溯 > 已知安装根兜底（病态 HOME 自动跳过）；
守卫查 `chexian-report-shell/lib` 是否存在（而非仅技能根），避免裁剪 checkout 误命中。
"""
import os
from pathlib import Path


def _resolve() -> Path:
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    if env:
        cand = Path(env).expanduser() / "chexian-report-shell"
        if (cand / "lib").is_dir():
            return cand
    hit = next(
        (p / "chexian-report-shell" for p in Path(__file__).resolve().parents
         if p.name == "skills" and (p / "chexian-report-shell" / "lib").is_dir()),
        None,
    )
    if hit is not None:
        return hit
    try:
        home = Path.home()
    except (RuntimeError, KeyError):  # 病态 HOME：相对占位，使用处自然报错
        return Path("chexian-report-shell")
    for root in (home / ".claude" / "skills",
                 home / ".claude" / "plugins" / "alongor666-skills" / "skills",
                 home / ".agents" / "skills"):
        if (root / "chexian-report-shell" / "lib").is_dir():
            return root / "chexian-report-shell"
    return home / ".claude/skills/chexian-report-shell"  # 兜底：标准安装位（保持原报错行为）


SHELL_ROOT = _resolve()
