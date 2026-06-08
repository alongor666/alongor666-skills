"""技能路径解析器（ADR-001）。

定位兄弟技能根，消除硬编码 ``~/.claude/skills`` 绝对路径，兼容三种安装方式：

  · ``~/.claude/skills``                              （npx -g 实体 / sync-skills 软链直连）
  · ``~/.claude/plugins/alongor666-skills/skills``    （git clone）
  · ``~/.agents/skills``                              （npx 快照）

候选优先级（与 docs/adr/ADR-001 一致）：

  1. ``$CLAUDE_SKILLS_DIR`` —— 显式覆盖，最高优先（运维旋钮）
  2. 相对调用文件回溯到 ``skills/`` 取兄弟（``resolve()`` 穿透软链，覆盖软链直连 / 同根安装）
  3. 已知安装根兜底（``~/.claude/skills`` → git clone plugins → ``~/.agents``）

注：HOME 不可解析的沙箱环境下，与 home 相关的候选自动跳过，最终抛 ``FileNotFoundError``
（而非 ``RuntimeError``），以便调用方稳定捕获。详见 docs/adr/ADR-001-skill-path-resolver.md。
"""
from __future__ import annotations

import os
from pathlib import Path


def _home():
    """``Path.home()`` 的安全封装：病态环境（无 HOME / 无 passwd 条目）返回 None 而非抛错。"""
    try:
        return Path.home()
    except (RuntimeError, KeyError):
        return None


def _env_root():
    """``$CLAUDE_SKILLS_DIR`` 显式覆盖根（未设返回 None）。"""
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    return Path(env).expanduser() if env else None


def _fallback_roots():
    """已知安装根（home 不可用时为空，避免 ``Path.home()`` 抛错）。"""
    home = _home()
    if home is None:
        return []
    return [
        home / ".claude" / "skills",
        home / ".claude" / "plugins" / "alongor666-skills" / "skills",
        home / ".agents" / "skills",
    ]


def skill_path(name: str) -> Path:
    """返回兄弟技能 ``name`` 的根目录；找不到抛 ``FileNotFoundError``。"""
    # 1) 显式覆盖：$CLAUDE_SKILLS_DIR（最高优先）
    env = _env_root()
    if env is not None and (env / name).is_dir():
        return env / name
    # 2) 相对自身回溯：同一 skills/ 下的兄弟（resolve() 穿透软链）
    for parent in Path(__file__).resolve().parents:
        if parent.name == "skills":
            cand = parent / name
            if cand.is_dir():
                return cand
            break
    # 3) 已知安装根兜底
    fallbacks = _fallback_roots()
    for root in fallbacks:
        if (root / name).is_dir():
            return root / name
    tried = ([str(env)] if env is not None else []) + [str(r) for r in fallbacks]
    raise FileNotFoundError(
        f"未找到技能 {name!r}；已尝试 $CLAUDE_SKILLS_DIR、兄弟回溯与已知安装根("
        + (", ".join(tried) if tried else "无可用根")
        + ")。可设环境变量 CLAUDE_SKILLS_DIR 指定技能安装根。"
    )


def skill_lib(name: str) -> Path:
    """返回兄弟技能 ``name`` 的 ``lib/`` 目录；技能在但缺 ``lib/`` 时抛 ``FileNotFoundError``。"""
    lib = skill_path(name) / "lib"
    if not lib.is_dir():
        raise FileNotFoundError(f"技能 {name!r} 存在但缺少 lib/ 目录：{lib}")
    return lib
