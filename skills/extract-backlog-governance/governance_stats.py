#!/usr/bin/env python3
"""governance_stats.py — 为 extract-backlog-governance 技能采集证据。

只产出"数字与证据",不下判断(判原则是否满足是模型的事)。
纯标准库,无第三方依赖。

数据源优先级:
  1. 有 `gh` CLI 且在 git 仓库内 → 拉最近 N 个已合并 PR(标题/正文/改动文件/评审/CI/关联 issue)。
  2. 否则 → 回退到 `git log`(只能拿到 commit 消息与改动文件数)。

产出(JSON 到 stdout):
  - meta:           仓库、数据源、样本量
  - structural:     原子性/可追溯/完成验证的结构化指标(均值、比例)
  - rule_hits:      若给了 --rules-file,统计每条编号规则在历史中被引用的次数
                    (命中率低=候选"死规则",过度设计信号)
  - principle_signals: 6 条原则各自词汇在过程历史中的出现频次(证据,非判定)
  - governance_files:  仓库内发现的 backlog/治理类文件(唯一队列的存在性证据)

用法:
  python3 governance_stats.py --repo . --rules-file docs/backlog.md --limit 50
  python3 governance_stats.py --repo /path/to/repo --md   # 附带 markdown 摘要
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 6 条原则的词汇信号(中英双语,小写匹配)。命中=该原则的"语汇"在过程历史里出现,属证据非判定。
PRINCIPLE_KEYWORDS = {
    "1_single_queue": ["backlog", "roadmap", "队列", "待办", "single source"],
    "2_intent_first": ["why", "为什么", "目的", "验收", "acceptance", "goal", "目标", "intent"],
    "3_atomic_reversible": ["revert", "回退", "rollback", "拆分", "split", "atomic", "feature flag"],
    "4_justified_order": ["blocked", "阻塞", "依赖", "depends", "前序", "prerequisite", "priority", "优先级"],
    "5_done_proven": ["ci", "gate", "门禁", "校验", "verify", "dod", "check", "契约", "invariant", "不变量", "test"],
    "6_sync_prune": ["归档", "archive", "prune", "stale", "陈旧", "过时", "deprecat", "清理", "grooming", "评审"],
}

GOVERNANCE_GLOBS = ["backlog*", "ROADMAP*", "roadmap*", "governance*", "*治理*", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING*"]

# 样本不足这条线以下,不下"死规则"结论(commit 标题/小样本本就少按编号引用规则,易误报)
MIN_SAMPLE_FOR_DEAD_RULE = 20


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return 1, ""


def gh_present(cwd: Path) -> bool:
    """只做轻量、无网络的存在性检查(`gh --version`)。
    不再探 `gh repo view`——那条在 gh 冷启动时会抖,导致静默降级到 git。"""
    rc, _ = run(["gh", "--version"], cwd)
    return rc == 0


def collect_prs_gh(cwd: Path, limit: int) -> tuple[list[dict], str]:
    """返回 (PR 列表, 状态)。状态 ∈ {ok, empty, error}:
      ok    = 成功取到 PR;empty = 命令成功但无 merged PR;error = 两次调用均失败。
    带一次重试以容忍 gh 冷启动抖动。"""
    fields = "number,title,body,files,reviews,closingIssuesReferences,statusCheckRollup,mergedAt"
    for _ in range(2):  # 一次重试
        rc, out = run(["gh", "pr", "list", "--state", "merged", "--limit", str(limit), "--json", fields], cwd)
        if rc == 0:
            if not out.strip():
                return [], "empty"
            try:
                return json.loads(out), "ok"
            except json.JSONDecodeError:
                return [], "error"
    return [], "error"


def collect_commits_git(cwd: Path, limit: int) -> list[dict]:
    rc, out = run(["git", "log", f"-n{limit}", "--pretty=format:%H%x1f%s%x1f%b%x1e"], cwd)
    if rc != 0:
        return []
    commits = []
    for rec in out.split("\x1e"):
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split("\x1f")
        sha = parts[0] if len(parts) > 0 else ""
        subj = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        nfiles = 0
        if sha:
            rc2, files = run(["git", "show", "--name-only", "--pretty=format:", sha], cwd)
            nfiles = len([f for f in files.splitlines() if f.strip()])
        commits.append({"text": f"{subj}\n{body}", "files": nfiles})
    return commits


def extract_rules(rules_file: Path) -> list[dict]:
    """从治理文档抓编号规则:形如 `1. **标题**:...` 或 `1. 标题`。"""
    if not rules_file.exists():
        return []
    rules = []
    pat = re.compile(r"^\s*(\d+)\.\s+(?:\*\*(.+?)\*\*[^:：]*|(.+?))(?:[:：]|$)")
    for line in rules_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.match(line)
        if m:
            num = int(m.group(1))
            title = (m.group(2) or m.group(3) or "").strip()
            rules.append({"num": num, "title": title})
    # 去重(保留首次),按编号
    seen, uniq = set(), []
    for r in rules:
        if r["num"] not in seen:
            seen.add(r["num"])
            uniq.append(r)
    return sorted(uniq, key=lambda r: r["num"])


def resolve_and_extract_rules(rules_arg: str, repo: Path) -> tuple[list[dict], str | None]:
    """解析 --rules-file 并抽规则。绝对路径直接用;相对路径先按 cwd 再按 --repo 找。
    给了路径却找不到、或找到却没编号规则 → 返回显式警告(与 gh 降级一样不静默)。"""
    if not rules_arg:
        return [], None
    p = Path(rules_arg)
    candidates = [p] if p.is_absolute() else [p, repo / p]
    for c in candidates:
        if c.exists():
            rules = extract_rules(c)
            if not rules:
                return [], f"治理文档已找到({c})但未解析出编号规则,规则命中率为空"
            return rules, None
    tried = " / ".join(dict.fromkeys(str(c) for c in candidates))
    return [], f"指定的 --rules-file 未找到(试过:{tried}),规则命中率分析已跳过"


def count_rule_hits(rules: list[dict], corpus: list[str]) -> list[dict]:
    blob = "\n".join(corpus).lower()
    total = max(len(corpus), 1)
    reliable = len(corpus) >= MIN_SAMPLE_FOR_DEAD_RULE
    results = []
    for r in rules:
        n = r["num"]
        # 引用形式:规则5 / 规则 5 / rule 5 / r5。用否定前瞻 (?!\d) 代替 \b——
        # \b 在「规则5规定」这类中文紧跟数字处会失效(漏统计→死规则假阳性);
        # (?!\d) 既容中文又能避免把「规则5」误命中进「规则50」。
        ref_pats = [rf"规则\s*{n}(?!\d)", rf"rule\s*{n}(?!\d)", rf"(?<![A-Za-z0-9])r{n}(?!\d)"]
        ref_hits = sum(len(re.findall(p, blob)) for p in ref_pats)
        title_tokens = [t for t in re.split(r"[\s/、,，]+", r["title"].lower()) if len(t) >= 2]
        title_hits = sum(blob.count(t) for t in title_tokens[:3]) if title_tokens else 0
        prs_with_ref = sum(1 for c in corpus if any(re.search(p, c.lower()) for p in ref_pats))
        results.append({
            "num": n,
            "title": r["title"],
            "explicit_ref_hits": ref_hits,
            "title_keyword_hits": title_hits,
            "prs_or_commits_referencing": prs_with_ref,
            "reference_rate": round(prs_with_ref / total, 3),
            # 样本不足时返回 None(模型勿据此判死规则);足够时才给布尔判断
            "dead_rule_candidate": (ref_hits == 0 and prs_with_ref == 0) if reliable else None,
        })
    return results


def _kw_occurrences(blob: str, k: str) -> int:
    """ASCII 关键词加左词边界(防 'ci' 命中 decision/social/precise 等词中子串、
    'test' 命中 latest/contest);中文无词边界仍用子串;不收右边界以保留
    'deprecat'→deprecated/deprecation 这类有意的前缀匹配。"""
    k = k.lower()
    if k.isascii():
        return len(re.findall(rf"\b{re.escape(k)}", blob))
    return blob.count(k)


def _kw_present(text: str, k: str) -> bool:
    k = k.lower()
    if k.isascii():
        return re.search(rf"\b{re.escape(k)}", text) is not None
    return k in text


def principle_signals(corpus: list[str]) -> dict:
    blob = "\n".join(corpus).lower()
    total = max(len(corpus), 1)
    out = {}
    for key, kws in PRINCIPLE_KEYWORDS.items():
        occ = sum(_kw_occurrences(blob, k) for k in kws)
        items = sum(1 for c in corpus if any(_kw_present(c.lower(), k) for k in kws))
        out[key] = {"keyword_occurrences": occ, "items_with_signal": items, "coverage_rate": round(items / total, 3)}
    return out


def structural_metrics(prs: list[dict], source: str) -> dict:
    if not prs:
        return {}
    if source == "gh":
        file_counts = [len(pr.get("files") or []) for pr in prs]
        reviewed = sum(1 for pr in prs if (pr.get("reviews") or []))
        linked = sum(1 for pr in prs if (pr.get("closingIssuesReferences") or []))
        with_ci = 0
        for pr in prs:
            roll = pr.get("statusCheckRollup") or []
            if roll:
                with_ci += 1
        n = len(prs)
        fc_sorted = sorted(file_counts)
        return {
            "sample_prs": n,
            "avg_files_per_pr": round(sum(file_counts) / n, 2) if n else 0,
            "median_files_per_pr": fc_sorted[n // 2] if n else 0,
            "max_files_per_pr": max(file_counts) if file_counts else 0,
            "pct_atomic_le5_files": round(sum(1 for c in file_counts if c <= 5) / n, 3) if n else 0,
            "pct_reviewed_before_merge": round(reviewed / n, 3) if n else 0,
            "pct_with_linked_issue": round(linked / n, 3) if n else 0,
            "pct_with_ci_checks": round(with_ci / n, 3) if n else 0,
        }
    # git fallback
    file_counts = [c.get("files", 0) for c in prs]
    n = len(prs)
    return {
        "sample_commits": n,
        "avg_files_per_commit": round(sum(file_counts) / n, 2) if n else 0,
        "max_files_per_commit": max(file_counts) if file_counts else 0,
        "pct_atomic_le5_files": round(sum(1 for c in file_counts if c <= 5) / n, 3) if n else 0,
        "note": "gh 不可用,已回退 git log;评审/CI/关联issue 指标无法采集",
    }


def find_governance_files(repo: Path) -> list[str]:
    found = []
    for g in GOVERNANCE_GLOBS:
        for p in repo.rglob(g):
            if ".git/" in str(p):
                continue
            try:
                rel = p.relative_to(repo)
            except ValueError:
                rel = p
            found.append(str(rel))
    return sorted(set(found))


def to_markdown(data: dict) -> str:
    m = data["meta"]
    lines = [f"# governance_stats — {m['repo']}", "",
             f"- 数据源:`{m['source']}`  样本:{m['sample_size']}", ""]
    if m.get("source_note"):
        lines.append(f"- ⚠️ 降级说明:{m['source_note']}")
        lines.append("")
    if m.get("rules_note"):
        lines.append(f"- ⚠️ 规则说明:{m['rules_note']}")
        lines.append("")
    s = data.get("structural") or {}
    if s:
        lines.append("## 结构化指标")
        for k, v in s.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    rh = data.get("rule_hits") or []
    if rh:
        lines.append("## 规则命中率(命中率低=候选死规则)")
        lines.append("| # | 规则 | 引用次数 | 命中条目率 | 死规则候选 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in rh:
            dc = r["dead_rule_candidate"]
            flag = "⚠️ 是" if dc is True else ("样本不足" if dc is None else "")
            lines.append(f"| {r['num']} | {r['title'][:24]} | {r['explicit_ref_hits']} | {r['reference_rate']} | {flag} |")
        lines.append("")
    ps = data.get("principle_signals") or {}
    if ps:
        lines.append("## 六原则词汇信号(证据,非判定)")
        for k, v in ps.items():
            lines.append(f"- {k}: 覆盖率 {v['coverage_rate']}(出现 {v['keyword_occurrences']} 次)")
        lines.append("")
    gf = data.get("governance_files") or []
    lines.append("## 治理类文件")
    lines += [f"- {f}" for f in gf] or ["- (未发现)"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="采集仓库 backlog 治理证据(数字,不判定)")
    ap.add_argument("--repo", default=".", help="仓库路径(默认当前目录)")
    ap.add_argument("--rules-file", default="", help="含编号规则的治理文档,用于算规则命中率")
    ap.add_argument("--limit", type=int, default=50, help="分析最近 N 个已合并 PR / commit")
    ap.add_argument("--md", action="store_true", help="附带输出 markdown 摘要到 stderr")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(json.dumps({"error": f"不是 git 仓库: {repo}"}, ensure_ascii=False))
        return 2

    note = None
    if gh_present(repo):
        prs, status = collect_prs_gh(repo, args.limit)
        if status == "ok":
            source = "gh"
            corpus = [f"{pr.get('title','')}\n{pr.get('body','')}\n" +
                      "\n".join((rv.get("body", "") for rv in (pr.get("reviews") or []))) for pr in prs]
        else:  # empty(无 merged PR) 或 error(拉取异常)——均回退 git,但显式注明,不静默
            source = "git"
            note = ("gh 可用但无 merged PR,已用 git log" if status == "empty"
                    else "gh 可用但 PR 拉取异常(重试后仍失败),已回退 git log——评审/CI 指标缺失")
            prs = collect_commits_git(repo, args.limit)
            corpus = [c["text"] for c in prs]
    else:
        source = "git"
        note = "未检测到 gh CLI,已用 git log——评审/CI/关联issue 指标无法采集"
        prs = collect_commits_git(repo, args.limit)
        corpus = [c["text"] for c in prs]

    rules, rules_note = resolve_and_extract_rules(args.rules_file, repo)

    meta = {"repo": str(repo), "source": source, "sample_size": len(prs)}
    if note:
        meta["source_note"] = note
    if rules_note:
        meta["rules_note"] = rules_note
    data = {
        "meta": meta,
        "structural": structural_metrics(prs, source),
        "rule_hits": count_rule_hits(rules, corpus) if rules else [],
        "principle_signals": principle_signals(corpus),
        "governance_files": find_governance_files(repo),
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if args.md:
        sys.stderr.write(to_markdown(data) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
