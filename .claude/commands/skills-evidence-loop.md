---
description: 在本技能集仓执行 evidence-loop-core 证据闭环（三阶段执行器 wrapper）
argument-hint: <任务，如「让 X 技能自进化」>
---

# /skills-evidence-loop：alongor666-skills 证据闭环执行器

执行 `evidence-loop-core` 协议（§1 合同 / §2 八步 loop / §5 verifier 隔离 / §6 停止 / §7 阈值），
按 §8 三阶段编排：**A 痛点调研 + harness 就绪报告 → B loop 迭代 → C 收尾 + verifier + scorecard**。

## 本项目挂载点

- §4 harness 映射表 + 项目特例 + scorecard 落位 → `.claude/rules/skills-evidence-loop.md`
- verifier agent → `.claude/agents/evidence-verifier.md`（fresh context，read-only，按基座 §5.1 九项白名单证伪）
- 协议骨架 → `skills/evidence-loop-core/SKILL.md`（不重复，按需查阅）

## 用法

`/skills-evidence-loop <任务>`，例如「让 X 技能自进化」「给 Y 技能补回归 oracle」「重构 Z 基座 lib」。

## 铁律（本仓特化，详见 rule）

- **阶段 A 必先做 user friction 调研**（grep git log / 项目 memory / SKILL.md changelog 找真实痛点），
  找不到痛点先 `AskUserQuestion`，**禁止跳过直接给候选清单**。
- **改技能前先有 oracle**（该技能 `skills/<name>/tests/` pytest）；无 `tests/` 的技能，
  **第一轮 loop 先补 oracle** 再改行为。
- 收尾必跑 `python3 scripts/validate_skills.py`（0 错误）+ 相关 pytest，**贴命令输出**。
- 收尾召 `evidence-verifier`（fresh context）试图证伪。**B3 必填输入**：
  ① git 状态（committed / staged-not-committed / dirty / mixed）
  ② 是否依赖未导入资源
  ③ wrapper 名 = `skills-evidence-loop`（让 verifier 用 rule 项目特例阈值，而非基座 §7 数字阈值）
  ④ baseline 与 after 命令输出的取数时点。
- scorecard 落位见 rule「scorecard 落位」节——**禁止写入 `~/.claude/projects/**/memory/`**（user-only）。
- 协议短板速记追加 `skills/evidence-loop-core/IMPROVEMENTS.md`（不阻塞本轮 promote）。

## 薄 wrapper 声明

> 执行 evidence-loop-core 协议。本项目 §4 harness 映射表与特例见 `.claude/rules/skills-evidence-loop.md`，
> verifier agent 见 `.claude/agents/evidence-verifier.md`。不重复骨架，只声明挂载点。
