"""Bootstrap：把 chexian-report-shell/lib 加载为 'dhr_lib'，供 diagnose-period-trend 各模块复用。

用法：
    try:
        from ._dhr_bootstrap import dhr
    except ImportError:
        from _dhr_bootstrap import dhr  # type: ignore[no-redef]
    light = dhr.light
    fmt_num = dhr.fmt_num
"""
from __future__ import annotations

import importlib.util as _iu
import sys
from pathlib import Path

# 引导期无法 import 基座的 skill_path（鸡生蛋），内联同一套三级优先级（ADR-001）：
#   $CLAUDE_SKILLS_DIR 显式覆盖 > 兄弟目录回溯 > 已知安装根兜底（病态 HOME 自动跳过）
def _resolve_shell_lib():
    import os
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    if env:
        cand = Path(env).expanduser() / "chexian-report-shell" / "lib"
        if cand.is_dir():
            return cand
    for p in Path(__file__).resolve().parents:
        if p.name == "skills" and (p / "chexian-report-shell" / "lib").is_dir():
            return p / "chexian-report-shell" / "lib"
    try:
        home = Path.home()
    except (RuntimeError, KeyError):
        return None
    for root in (home / ".claude" / "skills",
                 home / ".claude" / "plugins" / "alongor666-skills" / "skills",
                 home / ".agents" / "skills"):
        if (root / "chexian-report-shell" / "lib").is_dir():
            return root / "chexian-report-shell" / "lib"
    return None


_SHELL_LIB = _resolve_shell_lib()
if _SHELL_LIB is None:
    raise FileNotFoundError(
        "未找到渲染层依赖 chexian-report-shell/lib：已尝试 $CLAUDE_SKILLS_DIR、"
        "兄弟回溯与已知安装根；可设 CLAUDE_SKILLS_DIR 指定技能安装根"
    )
_ALIAS = "dhr_lib"


def _load():
    if _ALIAS in sys.modules:
        return sys.modules[_ALIAS]
    spec = _iu.spec_from_file_location(
        _ALIAS, str(_SHELL_LIB / "__init__.py"),
        submodule_search_locations=[str(_SHELL_LIB)],
    )
    mod = _iu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[_ALIAS] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


dhr = _load()
