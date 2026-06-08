"""技能路径解析器（ADR-001）。

跨技能复用时定位兄弟技能根，消除硬编码 ``~/.claude/skills`` 绝对路径，
兼容三种安装方式：

  · ``~/.claude/skills``                              （npx -g 实体 / sync-skills 软链直连）
  · ``~/.claude/plugins/alongor666-skills/skills``    （git clone）
  · ``~/.agents/skills``                              （npx 快照）

策略：先相对调用文件回溯到 ``skills/`` 取兄弟（``resolve()`` 已穿透软链，
软链直连场景同样命中 git 工作树里的兄弟），再用 ``$CLAUDE_SKILLS_DIR`` 与
已知安装根兜底。详见 docs/adr/ADR-001-skill-path-resolver.md。
"""
from __future__ import annotations

import os
from pathlib import Path


def _known_roots() -> list[Path]:
    """环境变量 + 已知安装根（兜底用，覆盖病态混装/独立 import 场景）。"""
    roots: list[Path] = []
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    if env:
        roots.append(Path(env).expanduser())
    home = Path.home()
    roots += [
        home / ".claude" / "skills",
        home / ".claude" / "plugins" / "alongor666-skills" / "skills",
        home / ".agents" / "skills",
    ]
    return roots


def skill_path(name: str) -> Path:
    """返回兄弟技能 ``name`` 的根目录；找不到抛 ``FileNotFoundError``。"""
    # 1) 相对自身回溯：同一 skills/ 下的兄弟（resolve() 已穿透软链）
    for parent in Path(__file__).resolve().parents:
        if parent.name == "skills":
            cand = parent / name
            if cand.is_dir():
                return cand
            break
    # 2) 环境变量 + 已知安装根兜底
    for root in _known_roots():
        cand = root / name
        if cand.is_dir():
            return cand
    raise FileNotFoundError(
        f"未找到技能 {name!r}；已尝试相对回溯与已知安装根("
        + ", ".join(str(r) for r in _known_roots())
        + ")。可设环境变量 CLAUDE_SKILLS_DIR 指定技能安装根。"
    )


def skill_lib(name: str) -> Path:
    """返回兄弟技能 ``name`` 的 ``lib/`` 目录。"""
    return skill_path(name) / "lib"
