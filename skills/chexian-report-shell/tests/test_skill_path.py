"""skill_path 解析器测试（ADR-001 / ADR-004：枢纽新 API 必须有回归）。

    pytest ~/.claude/skills/chexian-report-shell/tests/test_skill_path.py -v
"""
import sys
from pathlib import Path

import pytest

# 只把 lib/ 加进 path 单独加载 skill_path 模块，避免触发 lib/__init__.py 的重依赖
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from skill_path import skill_path, skill_lib  # noqa: E402


def test_resolves_self_via_sibling_walkup():
    """report-shell 能经兄弟回溯解析到自身。"""
    p = skill_path("chexian-report-shell")
    assert p.is_dir()
    assert p.name == "chexian-report-shell"


def test_resolves_sibling_skill():
    """能解析到兄弟业务技能（diagnose-period-trend 与本基座同在 skills/ 下）。"""
    p = skill_path("diagnose-period-trend")
    assert p.is_dir()
    assert (p / "lib").is_dir()


def test_skill_lib_appends_lib():
    assert skill_lib("chexian-report-shell") == skill_path("chexian-report-shell") / "lib"


def test_missing_skill_raises():
    with pytest.raises(FileNotFoundError):
        skill_path("no-such-skill-zzz")
