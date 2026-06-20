---
name: ppt-agent
description: Turns raw material into a presentation-ready deck by orchestrating humanize-ppt (brief), guizang-ppt-skill (default HTML render), and academic-pptx-skill (formal .pptx render). Use when 用户说"帮我做 PPT / 演讲 / 分享 / 答辩 / deck / slides / 把材料做成 PPT / 做一份汇报"时触发。
user_invocable: true
version: "0.1.0"
---

# PPT Agent — Orchestrator

When the user wants to turn raw material into a presentation, run this skill instead of jumping straight to any renderer.

## Required upstream skills

- `humanize-ppt` — narrative brief director (LearnPrompt/humanize-ppt)
- `guizang-ppt-skill` — default magazine-style HTML renderer (op7418)
- `academic-pptx-skill` — formal / academic .pptx renderer (Gabberflast)

If any skill is missing, stop and print the install one-liner from README before proceeding.

## Workflow

### Step 1 — Brief (always, never skip)

Hand off to `humanize-ppt`. Produce the AST output contract:
- `deck_brief.md`
- `ast_outline.md` (hook → conflict → method → proof → takeaway)
- `slide_plan.json`
- `speaker_intent.md`

Block on humanize-ppt's 6 acceptance questions. Question 6 ("which renderer") is answered by Step 2 below.

### Step 2 — Route

**Default: guizang-ppt-skill.**

Switch to `academic-pptx-skill` if ANY signal hits:
- Keywords: 学术 / academic / 论文 / 答辩 / thesis / seminar / conference / grant / 评审 / 监管 / 合规 / SOX / 审计 / 董事会
- Audience: 教授 / 评审委员 / 监管 / 审计 / 董事
- Output must be `.pptx` (not HTML)
- Citations required

Ambiguous → ask ONE question:
> "严肃风（.pptx，action title + 引用规范）还是杂志风（HTML 单文件，强叙事节奏）？"

### Step 3 — Render

Pass brief artifacts to the chosen renderer. Map AST roles to layout:

**guizang path:**

| AST role | Layout candidates |
|---|---|
| hook | 开场封面 / 悬念问题 / 大引用 |
| conflict | 数据大字报 / Before-After |
| method | Pipeline / 左文右图 |
| proof | Before-After / 数据大字报 / 图片网格 |
| takeaway | 章节幕封 / 大引用 |

Run guizang's 6-question clarification ONLY for fields not in brief (theme color, hard constraints). Run `references/checklist.md` P0 before delivery.

**academic path:**
- Rewrite every title as action title (complete sentence stating the takeaway)
- Apply SCR (situation → complication → resolution) on top of AST
- Ghost deck test on title sequence
- One exhibit per results slide; in-text citations

### Step 4 — Speech check (mandatory)

For every slide, verify the brief's `speaker_intent` still holds against the rendered page. Flag "viewable but unspeakable" pages. Send fixes back to the renderer, not to the user.

## Handoff contract

The brief is the single source of truth. If a renderer's own clarification conflicts with the brief, the brief wins. Renderers fill, not author.

## Failure modes

- **Brief skipped on user insist**: continue but mark output `no-brief`, warn quality risk.
- **Schema drift**: humanize-ppt iterates fast; if `slide_plan.json` schema breaks the renderer, fall back to passing `ast_outline.md` as plain markdown.
- **Renderer disagrees with brief**: don't let it rewrite intent; ask user to amend brief first.

## Trigger phrases

- "帮我做 PPT / 演讲 / slides / deck"
- "我要做分享 / 答辩 / 汇报"
- "把这份材料做成 PPT"

## Rules

1. Never skip Step 1, even for "quick decks".
2. Never let a renderer ingest raw material directly.
3. Route by signal, not by guess.
4. The brief wins. Renderers fill, not author.
5. Speech check is mandatory; unspeakable pages are defects.
