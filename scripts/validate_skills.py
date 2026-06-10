#!/usr/bin/env python3
"""技能仓自动巡检器 — 把 CLAUDE.md / ADR-001/002/005 / 官方 Skill 规范中可机检的约定固化为脚本。

用法：
    python3 scripts/validate_skills.py            # 巡检全部技能，错误退出码 1
    python3 scripts/validate_skills.py --strict   # 警告也视为失败

规则一览（E=错误，W=警告）：
    E001 SKILL.md 缺失 / frontmatter 不可解析
    E002 缺必填字段（name / description / user_invocable / version）
    E003 name 与目录名不一致，或含非法字符
    E004 description 超 1024 字符（官方硬上限，超出会被截断影响触发）
    E005 version 不符合语义化版本 x.y.z
    E006 frontmatter 出现约定外字段（白名单见 ALLOWED_FIELDS）
    E007 SKILL.md 正文超 500 行（官方建议上限，应做渐进披露拆分）
    E008 requires_skills 声明了某依赖，但代码中无对应 import 边（死声明）
    E009 代码存在跨技能 import 边，但 requires_skills 未声明（ADR-005）
    E010 SKILL.md 的 markdown 链接指向仓内不存在的文件（死链）
    E011 L1 业务技能之间出现横向 import 边（ADR-002 红线）
    E012 文档/脚本疑似明文凭据（password=… / api_key=… / 形如 Xxx@2026! 的密码）
    W101 description 超 500 字符（进 system prompt 常驻，建议压缩）
    W102 description 缺触发条件信号（Use when / 当用户 / 时使用 / 时触发 / 触发词）
    W103 frontmatter 字段顺序偏离约定（name → description → user_invocable → version → requires_skills）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

ALLOWED_FIELDS = ("name", "description", "user_invocable", "version", "requires_skills")

# 触发条件信号：description 必须告诉 AI「什么时候选我」
TRIGGER_SIGNALS = ("Use when", "use when", "当用户", "时使用", "时触发", "触发词", "Use for")

# 分层表（ADR-002）：仅 L1↔L1 横向 import 是红线
LAYER_L0 = {"chexian-report-shell", "xcl-html2pdf", "commit-push-pr-core"}
LAYER_L2 = {"chexian-ops-review", "company-vortex-card"}
LAYER_CROSSCUT = {
    "cleanup-worktrees", "sync-skills", "extract-backlog-governance",
    "ui-redesign", "crystallize-skill",
}

# 外部技能（不在本仓，存在性不做检查；可出现在 requires_skills）
EXTERNAL_SKILLS = {"chexian-im-push"}

# 明文凭据高置信模式（2026-06-09 真实事故：公开仓 SKILL.md 写入生产 admin 密码）
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"，。）)]{6,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"\b[A-Za-z]\w{2,}@\d{4}!"),  # 形如 CxAdmin@2026! 的密码惯用形
)


def parse_frontmatter(text: str) -> tuple[dict | None, list[str], str]:
    """解析 SKILL.md 顶部 YAML frontmatter。

    返回 (字段字典 | None, 字段出现顺序, 正文)。解析失败时字典为 None。
    """
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None, [], text
    raw, body = m.group(1), text[m.end():]
    try:
        import yaml  # 本机已有（PyYAML），仅此处使用，缺失时给出明确指引

        data = yaml.safe_load(raw)
    except ImportError:
        sys.exit("缺少 PyYAML：请先 `pip3 install pyyaml` 再运行巡检")
    except Exception:
        return None, [], body
    if not isinstance(data, dict):
        return None, [], body
    order = re.findall(r"^([A-Za-z_][\w]*):", raw, re.M)
    return data, order, body


def layer_of(skill: str) -> str:
    if skill in LAYER_L0:
        return "L0"
    if skill in LAYER_L2:
        return "L2"
    if skill in LAYER_CROSSCUT:
        return "横切"
    return "L1"


def _dep_patterns(name: str) -> tuple[re.Pattern, ...]:
    """某技能名作为「真实依赖目标」在源码行中的三种出现形态。

    注释 / 文档字符串里的叙事提及（"借鉴 X/lib/y.py"）不带引号紧贴技能名，
    天然不命中，因此无需做完整的 AST 分析。
    """
    n = re.escape(name)
    return (
        re.compile(rf"skill_(?:path|lib)\(\s*[\"']{n}[\"']"),   # skill_path("X")
        re.compile(rf"[\"'][^\"'\n]*skills/{n}(?=[\"'/])"),       # "…/skills/X" 路径
        re.compile(rf"[\"']{n}(?:/[^\"'\n]*)?[\"']"),             # "X" 或 "X/…" 字面量
    )


def infer_import_edges(skill_dir: Path, all_skills: set[str]) -> set[str]:
    """从非测试 .py 源码推断跨技能 import 边（逐行，跳过 # 注释行）。"""
    edges: set[str] = set()
    me = skill_dir.name
    candidates = {n: _dep_patterns(n) for n in (all_skills | EXTERNAL_SKILLS) if n != me}
    for py in skill_dir.rglob("*.py"):
        if "tests" in py.parts:
            continue
        for line in py.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("#"):
                continue
            for name, patterns in candidates.items():
                if name not in line or name in edges:
                    continue
                if any(p.search(line) for p in patterns):
                    edges.add(name)
    return edges


def md_link_targets(body: str) -> list[str]:
    """提取 markdown 链接目标，排除外链 / 锚点 / 绝对与家目录路径。"""
    targets = re.findall(r"\]\(([^)]+)\)", body)
    return [
        t.split("#", 1)[0].strip()
        for t in targets
        if not re.match(r"^(https?:|mailto:|#|/|~)", t.strip())
        and t.strip()
        and "{" not in t and "<" not in t  # 模板占位符不是链接
    ]


def check_skill(skill_dir: Path, all_skills: set[str]) -> tuple[list[str], list[str]]:
    """巡检单个技能，返回 (错误列表, 警告列表)。"""
    errors: list[str] = []
    warnings: list[str] = []
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return [f"E001 缺少 SKILL.md"], []

    fm, order, body = parse_frontmatter(md.read_text(encoding="utf-8"))
    if fm is None:
        return [f"E001 frontmatter 缺失或不可解析"], []

    for field in ("name", "description", "user_invocable", "version"):
        if field not in fm:
            errors.append(f"E002 缺必填字段 `{field}`")

    name = str(fm.get("name", ""))
    if name and name != skill_dir.name:
        errors.append(f"E003 name `{name}` 与目录名 `{skill_dir.name}` 不一致")
    if name and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        errors.append(f"E003 name `{name}` 含小写字母/数字/连字符以外的字符")

    desc = " ".join(str(fm.get("description", "")).split())
    if len(desc) > 1024:
        errors.append(f"E004 description {len(desc)} 字符，超官方 1024 上限")
    elif len(desc) > 500:
        warnings.append(f"W101 description {len(desc)} 字符（>500，常驻 system prompt，建议压缩）")
    # 基座（user_invocable: false）不面向用户触发，豁免触发信号检查
    if desc and fm.get("user_invocable") is not False and not any(sig in desc for sig in TRIGGER_SIGNALS):
        warnings.append("W102 description 缺触发条件信号（Use when / 当用户…时 等）")

    version = str(fm.get("version", ""))
    if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"E005 version `{version}` 不符合语义化版本 x.y.z")

    unknown = [f for f in fm if f not in ALLOWED_FIELDS]
    if unknown:
        errors.append(f"E006 约定外字段 {unknown}（白名单：{list(ALLOWED_FIELDS)}）")

    body_lines = len(body.splitlines())
    if body_lines > 500:
        errors.append(f"E007 正文 {body_lines} 行，超 500 行上限（应渐进披露拆分）")

    declared = set(fm.get("requires_skills") or [])
    inferred = infer_import_edges(skill_dir, all_skills)
    for dead in sorted(declared - inferred):
        errors.append(f"E008 requires_skills 声明 `{dead}` 但代码无 import 边（死声明）")
    for missing in sorted(inferred - declared):
        errors.append(f"E009 代码存在 → `{missing}` 的 import 边但未声明 requires_skills（ADR-005）")

    for target in md_link_targets(body):
        resolved = (skill_dir / target).resolve()
        if REPO_ROOT not in resolved.parents and resolved != REPO_ROOT:
            continue  # 指向仓外（文档型引用），不做存在性检查
        if not resolved.exists():
            errors.append(f"E010 死链 `{target}`")

    if layer_of(skill_dir.name) == "L1":
        for target in sorted(inferred):
            if target in all_skills and layer_of(target) == "L1":
                errors.append(f"E011 L1 横向 import 边 → `{target}`（ADR-002 红线）")

    for src in [md, *skill_dir.rglob("*.py"), *skill_dir.rglob("*.sh"), *skill_dir.rglob("*.mjs")]:
        for i, line in enumerate(src.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(p.search(line) for p in SECRET_PATTERNS):
                errors.append(f"E012 疑似明文凭据 {src.relative_to(skill_dir)}:{i}")

    expected = [f for f in ALLOWED_FIELDS if f in order]
    if order != expected:
        warnings.append(f"W103 字段顺序 {order}，约定为 {expected}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="技能仓自动巡检")
    parser.add_argument("--strict", action="store_true", help="警告也视为失败")
    args = parser.parse_args()

    if not SKILLS_DIR.is_dir():
        sys.exit(f"找不到技能目录：{SKILLS_DIR}")

    all_skills = {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}
    total_e = total_w = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        errors, warnings = check_skill(skill_dir, all_skills)
        total_e += len(errors)
        total_w += len(warnings)
        for e in errors:
            print(f"✗ {skill_dir.name}: {e}")
        for w in warnings:
            print(f"⚠ {skill_dir.name}: {w}")

    print(f"\n巡检完成：{len(all_skills)} 个技能，{total_e} 错误，{total_w} 警告")
    if total_e or (args.strict and total_w):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
