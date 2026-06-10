"""validate_skills.py 契约测试。

运行：python3 -m pytest scripts/test_validate_skills.py -q
重点回归：import 边推断（真实形态命中 / 叙事提及不命中）、凭据检测、frontmatter 解析。
"""

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_skills as vs


# ── parse_frontmatter ─────────────────────────────────────────────

def test_parse_frontmatter_standard():
    fm, order, body = vs.parse_frontmatter(
        '---\nname: foo\ndescription: bar\nuser_invocable: true\nversion: "1.0.0"\n---\n正文\n'
    )
    assert fm == {"name": "foo", "description": "bar", "user_invocable": True, "version": "1.0.0"}
    assert order == ["name", "description", "user_invocable", "version"]
    assert body == "正文\n"


def test_parse_frontmatter_folded_description():
    fm, _, _ = vs.parse_frontmatter(
        "---\nname: foo\ndescription: >-\n  第一行\n  第二行\nuser_invocable: true\nversion: \"1.0.0\"\n---\n"
    )
    assert "第一行 第二行" == fm["description"]


def test_parse_frontmatter_missing():
    fm, order, body = vs.parse_frontmatter("# 没有 frontmatter\n")
    assert fm is None and order == []


# ── infer_import_edges ────────────────────────────────────────────

def _make_skill(tmp_path: Path, name: str, py_source: str) -> Path:
    d = tmp_path / "skills" / name
    d.mkdir(parents=True)
    (d / "code.py").write_text(textwrap.dedent(py_source), encoding="utf-8")
    return d


ALL = {"a-skill", "chexian-report-shell", "diagnose-period-trend"}


def test_edge_via_skill_path_call(tmp_path):
    d = _make_skill(tmp_path, "a-skill", 'root = skill_path("chexian-report-shell")\n')
    assert vs.infer_import_edges(d, ALL) == {"chexian-report-shell"}


def test_edge_via_quoted_path(tmp_path):
    d = _make_skill(
        tmp_path, "a-skill",
        'from pathlib import Path\nP = Path.home() / ".claude/skills/chexian-report-shell"\n',
    )
    assert vs.infer_import_edges(d, ALL) == {"chexian-report-shell"}


def test_edge_via_bare_name_literal(tmp_path):
    # org-weekly 真实形态：p / "chexian-report-shell"
    d = _make_skill(tmp_path, "a-skill", 'hit = p / "chexian-report-shell" / "lib"\n')
    assert vs.infer_import_edges(d, ALL) == {"chexian-report-shell"}


def test_narrative_mention_not_an_edge(tmp_path):
    # 叙事提及（docstring / 注释）不构成 import 边
    d = _make_skill(
        tmp_path, "a-skill",
        '"""跨维度异常排名（v1.20 下沉自 diagnose-period-trend/lib/anomalies.py）。"""\n'
        "# 设计参考 chexian-report-shell 的渲染范式\n",
    )
    assert vs.infer_import_edges(d, ALL) == set()


def test_tests_dir_excluded(tmp_path):
    d = tmp_path / "skills" / "a-skill"
    (d / "tests").mkdir(parents=True)
    (d / "tests" / "test_x.py").write_text('p = skill_path("chexian-report-shell")\n', encoding="utf-8")
    assert vs.infer_import_edges(d, ALL) == set()


# ── md_link_targets ───────────────────────────────────────────────

def test_md_link_targets_filters():
    body = (
        "[内部](references/a.md) [外链](https://x.com/y) [锚点](#sec) "
        "[绝对](/etc/hosts) [家目录](~/x) [占位符](./{源文件})"
    )
    assert vs.md_link_targets(body) == ["references/a.md"]


# ── layer_of ──────────────────────────────────────────────────────

def test_layers():
    assert vs.layer_of("chexian-report-shell") == "L0"
    assert vs.layer_of("chexian-ops-review") == "L2"
    assert vs.layer_of("sync-skills") == "横切"
    assert vs.layer_of("diagnose-org-weekly") == "L1"


# ── check_skill 集成 ──────────────────────────────────────────────

GOOD_FM = textwrap.dedent("""\
    ---
    name: {name}
    description: Use when 用户说"测试"时使用。
    user_invocable: true
    version: "1.0.0"
    ---
    # 正文
""")


def test_check_skill_clean(tmp_path):
    d = tmp_path / "skills" / "good-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(GOOD_FM.format(name="good-skill"), encoding="utf-8")
    errors, warnings = vs.check_skill(d, {"good-skill"})
    assert errors == [] and warnings == []


def test_check_skill_violations(tmp_path):
    d = tmp_path / "skills" / "bad-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\n"
        "name: other-name\n"               # E003 与目录名不一致
        "description: 一个没有触发信号的描述。\n"  # W102
        "user_invocable: true\n"
        "version: v1\n"                     # E005 非语义化
        "requires: [git]\n"                 # E006 约定外字段
        "---\n"
        "[死链](references/missing.md)\n",
        encoding="utf-8",
    )
    errors, warnings = vs.check_skill(d, {"bad-skill"})
    codes = {e.split()[0] for e in errors} | {w.split()[0] for w in warnings}
    assert {"E003", "E005", "E006", "W102"} <= codes


def test_check_skill_dead_requires_declaration(tmp_path):
    d = tmp_path / "skills" / "a-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: Use when 测试时使用。\n"
        "user_invocable: true\nversion: \"1.0.0\"\n"
        "requires_skills:\n  - chexian-report-shell\n---\n",
        encoding="utf-8",
    )
    errors, _ = vs.check_skill(d, {"a-skill", "chexian-report-shell"})
    assert any(e.startswith("E008") for e in errors)


def test_check_skill_undeclared_edge(tmp_path):
    d = tmp_path / "skills" / "a-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(GOOD_FM.format(name="a-skill"), encoding="utf-8")
    (d / "code.py").write_text('p = skill_path("chexian-report-shell")\n', encoding="utf-8")
    errors, _ = vs.check_skill(d, {"a-skill", "chexian-report-shell"})
    assert any(e.startswith("E009") for e in errors)


def test_check_skill_lateral_l1_edge(tmp_path):
    d = tmp_path / "skills" / "diagnose-org-weekly"   # L1
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: diagnose-org-weekly\ndescription: Use when 测试时使用。\n"
        "user_invocable: true\nversion: \"1.0.0\"\n"
        "requires_skills:\n  - diagnose-period-trend\n---\n",
        encoding="utf-8",
    )
    (d / "code.py").write_text('p = skill_path("diagnose-period-trend")\n', encoding="utf-8")
    errors, _ = vs.check_skill(d, {"diagnose-org-weekly", "diagnose-period-trend"})
    assert any(e.startswith("E011") for e in errors)


def test_check_skill_secret_detection(tmp_path):
    d = tmp_path / "skills" / "a-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        GOOD_FM.format(name="a-skill") + "\n登录用 admin/CxAdmin@2026! 即可。\n",
        encoding="utf-8",
    )
    errors, _ = vs.check_skill(d, {"a-skill"})
    assert any(e.startswith("E012") for e in errors)


def test_base_skill_exempt_from_trigger_signal(tmp_path):
    d = tmp_path / "skills" / "a-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: a-skill\ndescription: 渲染基础设施层，不直接面向用户。\n"
        "user_invocable: false\nversion: \"1.0.0\"\n---\n",
        encoding="utf-8",
    )
    _, warnings = vs.check_skill(d, {"a-skill"})
    assert not any(w.startswith("W102") for w in warnings)


# ── 真仓全量回归（确保仓库当前状态保持全绿）──────────────────────

def test_real_repo_is_clean():
    total_errors = []
    all_skills = {p.name for p in vs.SKILLS_DIR.iterdir() if p.is_dir()}
    for skill_dir in sorted(vs.SKILLS_DIR.iterdir()):
        if skill_dir.is_dir():
            errors, _ = vs.check_skill(skill_dir, all_skills)
            total_errors += [f"{skill_dir.name}: {e}" for e in errors]
    assert total_errors == [], f"技能仓存在巡检错误：{total_errors}"
