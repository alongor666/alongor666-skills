"""skill_path 解析器测试（ADR-001 / ADR-004：枢纽 API 回归 + 候选优先级/健壮性）。

    pytest ~/.claude/skills/chexian-report-shell/tests/test_skill_path.py -v

设计：用 tmp_path + CLAUDE_SKILLS_DIR 构造隔离的假技能树，
不反向硬依赖任何 L1 业务技能（呼应 ADR-002「基座独立」）。
"""
import sys
from pathlib import Path

import pytest

# 只把 lib/ 加进 path 单独加载 skill_path 模块，避免触发 lib/__init__.py 的重依赖
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import skill_path as sp  # noqa: E402
from skill_path import skill_path, skill_lib  # noqa: E402


def test_resolves_self_via_sibling_walkup(monkeypatch):
    """无 env 时经兄弟回溯解析到基座自身（解析器就在其 lib/ 下，不依赖业务技能）。"""
    monkeypatch.delenv("CLAUDE_SKILLS_DIR", raising=False)
    p = skill_path("chexian-report-shell")
    assert p.is_dir() and p.name == "chexian-report-shell"


def test_env_override(tmp_path, monkeypatch):
    """$CLAUDE_SKILLS_DIR 命中时按其解析（解耦：用隔离假技能，不依赖真实业务技能）。"""
    (tmp_path / "foo-skill" / "lib").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_SKILLS_DIR", str(tmp_path))
    assert skill_path("foo-skill") == tmp_path / "foo-skill"
    assert skill_lib("foo-skill") == tmp_path / "foo-skill" / "lib"


def test_env_override_beats_sibling(tmp_path, monkeypatch):
    """env 为最高优先：即便兄弟里有同名技能，也走 env（ADR-001 候选①，呼应文档↔码对齐）。"""
    (tmp_path / "chexian-report-shell" / "lib").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_SKILLS_DIR", str(tmp_path))
    assert skill_path("chexian-report-shell") == tmp_path / "chexian-report-shell"


def test_skill_lib_requires_lib(tmp_path, monkeypatch):
    """技能存在但缺 lib/ 时 skill_lib 抛 FileNotFoundError（守卫查 lib，呼应 #5）。"""
    (tmp_path / "bar-skill").mkdir()  # 无 lib/
    monkeypatch.setenv("CLAUDE_SKILLS_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        skill_lib("bar-skill")


def test_missing_skill_raises(monkeypatch):
    monkeypatch.delenv("CLAUDE_SKILLS_DIR", raising=False)
    with pytest.raises(FileNotFoundError):
        skill_path("no-such-skill-zzz")


def test_missing_raises_on_broken_home(monkeypatch):
    """病态 HOME：_home() 返回 None，最终抛 FileNotFoundError 而非 RuntimeError（#10）。"""
    monkeypatch.delenv("CLAUDE_SKILLS_DIR", raising=False)
    monkeypatch.setattr(sp, "_home", lambda: None)
    with pytest.raises(FileNotFoundError):
        skill_path("no-such-skill-zzz")
