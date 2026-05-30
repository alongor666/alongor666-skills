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

_SHELL_LIB = Path.home() / ".claude/skills/chexian-report-shell/lib"
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
