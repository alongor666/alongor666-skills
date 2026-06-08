"""governance_stats.py 单测（ADR-004：枢纽技能的纯函数回归契约）。

    pytest skills/extract-backlog-governance/tests/test_governance_stats.py -v

只测纯函数与文件 I/O 函数（用 tmp_path 隔离），不触网络、不依赖真实 gh/git。
重点覆盖源码里带「修复注释」的微妙逻辑——正则边界、样本阈值、降级警告——
这些恰是回归最易悄悄破掉、肉眼最难发现的地方。
"""
import sys
from pathlib import Path

# 技能脚本在技能根目录（非 lib/ 下），把根加进 path 直接加载
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import governance_stats as gs  # noqa: E402


# ── count_rule_hits：引用正则的 (?!\d) / (?<![A-Za-z0-9]) 边界（源码注释明确点名的坑）──

def _rule(num, title=""):
    return {"num": num, "title": title}


def test_rule_ref_chinese_adjacent_digit_counts():
    """「规则5规定」中文紧跟数字处，\\b 会失效漏统计；(?!\\d) 必须命中。"""
    hits = gs.count_rule_hits([_rule(5)], ["规则5规定了拆分粒度"])
    r5 = hits[0]
    assert r5["explicit_ref_hits"] >= 1
    assert r5["prs_or_commits_referencing"] == 1


def test_rule_ref_does_not_bleed_into_longer_number():
    """「规则50」不得误命中规则 5（(?!\\d) 阻止前缀串号）。"""
    hits = gs.count_rule_hits([_rule(5), _rule(50)], ["本次遵循规则50归档陈旧分支"])
    by_num = {h["num"]: h for h in hits}
    assert by_num[5]["explicit_ref_hits"] == 0
    assert by_num[50]["explicit_ref_hits"] == 1


def test_rule_ref_english_and_rN_forms():
    """rule 5 / r5 两种英文引用都算；r5 的左侧字母数字边界防止 'cr5' 误命中。"""
    hit_rule = gs.count_rule_hits([_rule(5)], ["This follows rule 5 strictly"])
    assert hit_rule[0]["explicit_ref_hits"] >= 1

    hit_r = gs.count_rule_hits([_rule(5)], ["see r5 above"])
    assert hit_r[0]["explicit_ref_hits"] >= 1

    hit_glued = gs.count_rule_hits([_rule(5)], ["variable cr5 unrelated"])
    assert hit_glued[0]["explicit_ref_hits"] == 0


def test_dead_rule_candidate_none_below_sample_threshold():
    """样本 < MIN_SAMPLE_FOR_DEAD_RULE 时不下死规则结论，须为 None（防小样本假阳性）。"""
    small_corpus = ["无任何规则引用的提交"] * 5
    assert len(small_corpus) < gs.MIN_SAMPLE_FOR_DEAD_RULE
    hits = gs.count_rule_hits([_rule(9)], small_corpus)
    assert hits[0]["dead_rule_candidate"] is None


def test_dead_rule_candidate_true_when_sample_enough_and_unreferenced():
    """样本足够且零引用 → 死规则候选为 True。"""
    big_corpus = ["completely unrelated commit message"] * gs.MIN_SAMPLE_FOR_DEAD_RULE
    hits = gs.count_rule_hits([_rule(9, "永不被引用的规则")], big_corpus)
    assert hits[0]["dead_rule_candidate"] is True
    assert hits[0]["reference_rate"] == 0.0


def test_reference_rate_is_ratio_of_items():
    """reference_rate = 命中条目数 / 总条目数。"""
    corpus = ["规则3 已遵守", "规则3 再次", "无关提交", "无关提交"]
    hits = gs.count_rule_hits([_rule(3)], corpus)
    assert hits[0]["prs_or_commits_referencing"] == 2
    assert hits[0]["reference_rate"] == round(2 / 4, 3)


# ── _kw_occurrences / _kw_present：ASCII 左词边界 + 'deprecat' 前缀 + 中文子串 ──

def test_kw_ascii_left_boundary_blocks_substring():
    """'ci' 不得命中 decision/social/precise（左词边界 \\b）。"""
    assert gs._kw_occurrences("a wise decision on social precise topics", "ci") == 0


def test_kw_ascii_matches_standalone_word():
    assert gs._kw_occurrences("the ci pipeline and ci gate", "ci") == 2


def test_kw_prefix_match_kept_for_deprecat():
    """'deprecat' 有意不收右边界，须命中 deprecated / deprecation。"""
    assert gs._kw_occurrences("this api is deprecated, see deprecation note", "deprecat") == 2


def test_kw_chinese_substring_match():
    """中文无词边界，子串命中。"""
    assert gs._kw_occurrences("已归档归档完成", "归档") == 2


def test_kw_present_boolean_semantics():
    assert gs._kw_present("we added a feature flag", "feature flag") is True
    assert gs._kw_present("precision matters", "ci") is False


# ── extract_rules：编号规则解析 + 去重 + 排序（tmp 文件）──

def test_extract_rules_bold_and_plain(tmp_path):
    doc = tmp_path / "backlog.md"
    doc.write_text(
        "# 治理\n"
        "1. **唯一队列**：所有待办进同一处\n"
        "2. 意图优先\n"
        "随便一行不是规则\n"
        "3. **可回退**：拆小、可 revert\n",
        encoding="utf-8",
    )
    rules = gs.extract_rules(doc)
    assert [r["num"] for r in rules] == [1, 2, 3]
    assert rules[0]["title"] == "唯一队列"
    assert rules[1]["title"] == "意图优先"


def test_extract_rules_dedup_keeps_first(tmp_path):
    doc = tmp_path / "dup.md"
    doc.write_text("1. 首次标题\n1. 重复编号应被丢弃\n2. 第二条\n", encoding="utf-8")
    rules = gs.extract_rules(doc)
    assert [r["num"] for r in rules] == [1, 2]
    assert rules[0]["title"] == "首次标题"


def test_extract_rules_missing_file_returns_empty(tmp_path):
    assert gs.extract_rules(tmp_path / "nope.md") == []


# ── resolve_and_extract_rules：路径解析与显式警告（不静默）──

def test_resolve_rules_empty_arg_no_warning(tmp_path):
    rules, note = gs.resolve_and_extract_rules("", tmp_path)
    assert rules == [] and note is None


def test_resolve_rules_found_but_no_numbered_rules_warns(tmp_path):
    doc = tmp_path / "empty_rules.md"
    doc.write_text("# 标题\n没有任何编号规则的正文\n", encoding="utf-8")
    rules, note = gs.resolve_and_extract_rules("empty_rules.md", tmp_path)
    assert rules == []
    assert note is not None and "未解析出编号规则" in note


def test_resolve_rules_not_found_warns_with_tried_paths(tmp_path):
    rules, note = gs.resolve_and_extract_rules("docs/missing.md", tmp_path)
    assert rules == []
    assert note is not None and "未找到" in note


def test_resolve_rules_relative_resolved_against_repo(tmp_path):
    doc = tmp_path / "rules.md"
    doc.write_text("1. **唯一队列**：x\n", encoding="utf-8")
    rules, note = gs.resolve_and_extract_rules("rules.md", tmp_path)
    assert note is None
    assert [r["num"] for r in rules] == [1]


# ── principle_signals：覆盖率聚合 ──

def test_principle_signals_coverage_and_keys():
    corpus = ["backlog 已建立唯一队列", "本次有 ci 门禁 + test 校验", "无关提交"]
    sig = gs.principle_signals(corpus)
    assert set(sig.keys()) == set(gs.PRINCIPLE_KEYWORDS.keys())
    # 第 1 条「唯一队列」与第 5 条「完成验证」各被 1 条命中
    assert sig["1_single_queue"]["items_with_signal"] == 1
    assert sig["5_done_proven"]["items_with_signal"] == 1
    assert sig["1_single_queue"]["coverage_rate"] == round(1 / 3, 3)


def test_principle_signals_empty_corpus_no_div_by_zero():
    sig = gs.principle_signals([])
    assert sig["1_single_queue"]["coverage_rate"] == 0.0


# ── structural_metrics：gh / git 两源分支 + 原子性比例 ──

def test_structural_metrics_empty_returns_empty():
    assert gs.structural_metrics([], "gh") == {}


def test_structural_metrics_gh_source():
    prs = [
        {"files": [1, 2], "reviews": [{"body": "lgtm"}], "closingIssuesReferences": [{"number": 1}],
         "statusCheckRollup": [{"state": "SUCCESS"}]},
        {"files": list(range(8)), "reviews": [], "closingIssuesReferences": [], "statusCheckRollup": []},
    ]
    m = gs.structural_metrics(prs, "gh")
    assert m["sample_prs"] == 2
    assert m["avg_files_per_pr"] == round((2 + 8) / 2, 2)
    assert m["max_files_per_pr"] == 8
    assert m["pct_atomic_le5_files"] == round(1 / 2, 3)   # 只有第一个 ≤5
    assert m["pct_reviewed_before_merge"] == round(1 / 2, 3)
    assert m["pct_with_linked_issue"] == round(1 / 2, 3)
    assert m["pct_with_ci_checks"] == round(1 / 2, 3)


def test_structural_metrics_git_fallback_has_note_and_no_review_keys():
    commits = [{"text": "feat: x", "files": 3}, {"text": "fix: y", "files": 9}]
    m = gs.structural_metrics(commits, "git")
    assert m["sample_commits"] == 2
    assert m["avg_files_per_commit"] == round((3 + 9) / 2, 2)
    assert m["pct_atomic_le5_files"] == round(1 / 2, 3)
    assert "note" in m
    assert "pct_reviewed_before_merge" not in m


# ── find_governance_files：发现治理文件、跳过 .git ──

def test_find_governance_files_detects_and_skips_git(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    (tmp_path / "backlog.md").write_text("x", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x", encoding="utf-8")
    gitdir = tmp_path / ".git"
    gitdir.mkdir()
    (gitdir / "CLAUDE.md").write_text("x", encoding="utf-8")  # 应被跳过

    found = gs.find_governance_files(tmp_path)
    assert "CLAUDE.md" in found
    assert "backlog.md" in found
    assert all(".git/" not in f for f in found)
    assert "src/main.py" not in found


# ── to_markdown：含 None 死规则候选时输出「样本不足」，不崩 ──

def test_to_markdown_smoke_with_none_dead_rule():
    data = {
        "meta": {"repo": "/x", "source": "git", "sample_size": 3, "source_note": "未检测到 gh CLI"},
        "structural": {"sample_commits": 3, "pct_atomic_le5_files": 0.667},
        "rule_hits": [
            {"num": 1, "title": "唯一队列", "explicit_ref_hits": 0,
             "title_keyword_hits": 0, "prs_or_commits_referencing": 0,
             "reference_rate": 0.0, "dead_rule_candidate": None},
        ],
        "principle_signals": {"1_single_queue": {"keyword_occurrences": 2, "items_with_signal": 1, "coverage_rate": 0.333}},
        "governance_files": ["CLAUDE.md"],
    }
    md = gs.to_markdown(data)
    assert "# governance_stats — /x" in md
    assert "样本不足" in md            # None 死规则候选的渲染
    assert "降级说明" in md            # source_note 透出
    assert "CLAUDE.md" in md
