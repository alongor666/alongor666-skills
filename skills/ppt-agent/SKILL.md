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

### Step 0 — Preflight（数据与受众收口 · 阻断式，先于 Brief）

**用 TodoWrite 为下列每项各建一条 todo；未全部完成不得进入 Step 1。**

1. **数据真实性 gate** — 盘点项目内真实数据源（parquet / API / DB / 报告文件 / 用户提供的截图）。
   - 有真实数据源 → **必须接入真实数据**；**禁止先用编造/占位数据做完再换**。
   - 确无数据源、或用户明确要占位 → 必须在产物上显式标注「示意数据」并取得用户确认。
2. **受众·价值·取舍** — 产出一句话价值主张 + 「讲什么 / 不讲什么」清单，渲染前与用户对齐一次。
3. **数据口径登记** — 多源拼装时登记每块的口径 / 范围 / 时点 / 地域；同一份 deck 禁混口径。
4. **硬约束确认** — 主题色、单文件与否、是否需离线、脱敏要求、报告语言红线。

> **违反代价（真实事故）**：先用 mock 假数据做完三张界面图 → 用户「使用生产端的图，而不是虚假的」→ 全部重做；且假数据推出的结论与真相相反（编"缺口在没报价"，真实是"报价了没成交"才是大头）。

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

### Step 5 — Postflight（交付自检 · 阻断式）

产物落盘后，**必须跑校验脚本，PASS 才算交付**（机械约束代码兜底，不靠记性）：

```bash
node {skill_dir}/scripts/ppt-postflight.mjs <deck.html>
```

- `exit 1`（占位符残留 / 页码错乱 / 手机号未脱敏）→ 修复后重跑，**不得声称完成**。
- 警告（非白名单 emoji / 节奏连续 ≥3 / 英文术语 / 车牌 / 本地依赖）→ 逐条人工确认或修复。

脚本测不了的判断项，人工核对：
- 逐页截图核对版式（溢出 / 标题换行 / 缩放清晰度）。
- 数据与 Step 0 口径登记一致、无编造、来源已标注。
- 与 Step 4 speech check 合并确认。

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
6. Step 0（preflight）与 Step 5（postflight）同样不可跳过；postflight 脚本 PASS 才算交付。
7. 真实数据优先：有数据源必接真，占位数据须显式标注 + 用户确认。

## 反合理化（防跳过 Preflight / 用假数据）

| 借口 | 现实 |
|---|---|
| "快速做个 deck，跳过 preflight" | 跳过 = 后面返工。"假数据 → 真数据"全部重做就是代价。 |
| "先用占位数据搭版式，回头换真的" | "回头"= 用户打回重做；真实数据常推翻你的假设（本次结论直接反转）。 |
| "项目数据不好取，先编一个" | 有 parquet / API / 报告 / PAT 就能取；取不到也要标「示意」+ 问用户，不能默默编。 |
| "postflight 脚本太麻烦，肉眼看过了" | 肉眼漏占位符 / 页码错 / 手机号；脚本 10 秒，Prompt 遵从率不稳须代码兜底。 |
| "emoji / 术语是小问题" | 报告语言红线是硬约束；脚本会标，逐条清。 |

## Red Flags — 停下重来

- 冒出"先编点数据占位"的念头 → 停。先接真实数据源，或标「示意」+ 问用户。
- 想把原始材料直接丢给渲染器 → 停。先过 Step 0 + Step 1。
- 想跳过 postflight 脚本就说"完成" → 停。脚本 PASS 才算 DONE。
- 产物里出现真名 / 车牌 / 手机号却没问脱敏 → 停。

**违反字面 = 违反精神**：上面任何一条想绕过，都是在破坏机制本身。
