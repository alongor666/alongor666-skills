"""一行加载 shell 全量 API（含 importlib 隔离 + sys.modules 注册）。

用法（新建 diagnose-* skill 推荐入口）：
    from chexian_report_shell.loader import load_shell
    shell = load_shell()
    TH, light, render_page = shell.TH, shell.light, shell.render_page

已存在 skill（旧 sys.path.insert + from lib import ... 方式）无需迁移，继续有效。
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path
from types import ModuleType

_SHELL_ROOT = Path(__file__).resolve().parent.parent  # ~/.claude/skills/chexian-report-shell


def load_shell(*, alias: str = "dhr_lib") -> ModuleType:
    """加载 chexian-report-shell 全量 API 到独立命名空间。

    使用 importlib 隔离加载，避免 sys.path 污染，兼容多 skill 并存场景
    （diagnose-period-trend / diagnose-org-weekly 等已各自用 importlib 加载）。
    重复调用幂等——第二次直接返回 sys.modules 中缓存的模块。

    Args:
        alias:  sys.modules 注册键名（默认 "dhr_lib"，与 period-trend 的惯例一致）

    Returns:
        已加载的 lib 模块（等同于 import lib）
    """
    if alias in _sys.modules:
        return _sys.modules[alias]

    lib_init = _SHELL_ROOT / "lib" / "__init__.py"
    if not lib_init.exists():
        raise FileNotFoundError(
            f"chexian-report-shell not found at {_SHELL_ROOT}. "
            "Please ensure ~/.claude/skills/chexian-report-shell/ is present."
        )

    spec = _ilu.spec_from_file_location(
        alias,
        str(lib_init),
        submodule_search_locations=[str(_SHELL_ROOT / "lib")],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法为 {lib_init} 创建 ModuleSpec")

    mod = _ilu.module_from_spec(spec)
    _sys.modules[alias] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod
