"""chexian-report-shell 根定位（ADR-001，diagnose-loss-development 内集中一处）。

cli.py 与 render.py 都从这里取 SHELL_ROOT，避免路径探测散落两份。
策略与基座 chexian-report-shell/lib/skill_path.py 一致：兄弟回溯优先、标准安装位兜底；
守卫查 `chexian-report-shell/lib` 是否存在（而非仅技能根），避免裁剪 checkout 误命中。
"""
from pathlib import Path


def _resolve() -> Path:
    hit = next(
        (p / "chexian-report-shell" for p in Path(__file__).resolve().parents
         if p.name == "skills" and (p / "chexian-report-shell" / "lib").is_dir()),
        None,
    )
    if hit is not None:
        return hit
    try:
        return Path.home() / ".claude/skills/chexian-report-shell"  # 兜底：标准安装位
    except (RuntimeError, KeyError):  # 病态 HOME：相对占位，使用处自然报错
        return Path("chexian-report-shell")


SHELL_ROOT = _resolve()
