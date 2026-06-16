---
name: evidence-loop-core
description: >-
  项目无关的「证据驱动复杂工作」协议基座。把"做完一件复杂工作"的定义交给外部证据
  而不是模型感觉。Use when 用户说"按证据闭环做"、"evidence loop"、"先建 harness 再动手"、
  "证明做成了再合并"，或在性能优化 / SQL 口径修改 / 重构 / 新功能 / 安全加固 /
  数据 ETL 等复杂工作开工前需要先定义合同与证据要求时。设计为被各项目薄 wrapper
  import 复用（如 `<project>/.claude/commands/<project>-evidence-loop.md`），
  wrapper 只填项目专属 §4 harness 映射表与停止-回滚条件。
user_invocable: false
version: "1.0.0"
---

# evidence-loop-core：证据驱动复杂工作的协议基座

把"做一次复杂工作"升级为"在可验证闭环里工作"。本 skill 提供**项目无关**的协议骨架；
各项目通过薄 wrapper 注入 §4 的项目专属 harness 映射表。

> **复用模型**：本 skill = L1 协议骨架 + L2 通用阈值 + L3 verifier 模板。
> 各项目建一个薄 wrapper（命令 + rule），只补 §4 的**内容**（harness 命令、oracle、回归门禁、发布安全机制）。
> 这是「方法复用，非内容复用」——禁止把任何单一项目的脚本路径硬写进本文件。

---

## 1. 合同六要素（开工前必须写出来）

> 业务目标 + 可度量终止条件 + 证据要求 + loop 迭代协议 + 独立 verifier + 停止/回滚条件

**缺任一项 = 不是闭环**，会退化成"看起来专业的自然语言报告"。
开工前写不出"什么证据能证明做成了"就**先别动代码**。

每项的最小要求：

| 要素 | 最小内容 |
|---|---|
| 业务目标 | 一句话，含可量化的"做成"标准（数字 + 单位） |
| 终止条件 | §7 默认阈值 或 项目特例阈值（必须明示） |
| 证据要求 | §3 完整七项 |
| loop 协议 | §2 八步固定步骤 |
| 独立 verifier | fresh-context、read-only、按合同重跑核对（§5） |
| 停止/回滚 | §6 任一命中即报 BLOCKED |

---

## 2. 通用 loop（八步固定）

1. 建立 / 确认基线（baseline）
2. 改动前先定义正确性不变量（correctness invariants）
3. 提出瓶颈 / 缺陷假设，绑定到代码路径或工具产物
4. 实现**最小有用改动**（只改假设必需文件，无无关重构）
5. 跑正确性验证 + 该任务类型的回归 / 度量
6. 同命令、同数据、同环境做前后对比
7. 决策：promote / rollback / continue
8. 结论沉淀到项目约定位置（`.claude/shared-memory/` 或同等机制），**不为单次结论新建 docs/ 目录**

---

## 3. 证据要求（每条声明都要挂证据）

```
命令 + 文件路径 + 运行输出 + 前后度量 + 数据规模 + 环境 +
commit/工作树状态 + 回归结果 + 风险与回滚条件
```

任何声明若无 工具结果 / 测试输出 / 度量输出 / 日志 / 文件 diff / 已提交产物 支撑
→ 必须显式标 **"未验证"**。**禁止凭记忆总结、从代码结构推断效果**。

---

## 4. 任务类型 → 项目现成 harness（wrapper 必填）

本节是 **wrapper 注入点**。基座只给空表 + 填法说明；wrapper 必须在项目 rule 中
覆盖此表，把空表替换为项目实际命令。

**填法说明**：每个任务类型给出该项目的**现成**脚本路径或命令，不另造。
找不到现成 harness 才提议新建，并先说明缺口。

| 任务类型 | 基线 / 度量 | 正确性 oracle | 回归门禁 | 发布安全 |
|---|---|---|---|---|
| 性能优化 | _wrapper 填_：bench 脚本 + golden baseline + profiler | _wrapper 填_：影子对账 / 黄金基线零差异 | _wrapper 填_：项目 verify:full | _wrapper 填_：灰度 flag / sentinel |
| SQL / 口径修改 | _wrapper 填_：API 返回前后对比命令 | _wrapper 填_：直查数据源 vs API + 项目专项校验脚本 | _wrapper 填_：项目治理 + 单测 | _wrapper 填_：灰度 flag |
| 重构 | 无（行为不变） | _wrapper 填_：黄金基线零差异 | _wrapper 填_：项目 verify:full | — |
| 新功能 | — | _wrapper 填_：新增测试 + §3 证据 | _wrapper 填_：项目 verify:full + 契约测试 | _wrapper 填_：灰度 flag |
| 安全加固 | — | **修补不拆除**（项目红线兜底） | _wrapper 填_：项目治理 | — |
| 数据 ETL | _wrapper 填_：转换质量报告 | _wrapper 填_：直查值域 / 对账容差 | _wrapper 填_：数据就绪检查 | _wrapper 填_：sentinel |

> 度量与门禁脚本以项目实际为准，跑前 `--help` 确认签名；找不到现成 harness 才提议新建，并先说明缺口。

---

## 5. verifier 隔离原则

- 实现 agent **不得**作为自己工作的唯一验证者。
- correctness / 度量 / 发布风险优先交给**确定性脚本**（影子对账 / bench / 治理 / sentinel），
  不用 LLM subagent 去做。
- 探索用只读 subagent；收尾用 **1 个 fresh-context verifier** 试图证伪。
  **不要 7 个 verifier**——多数验证已是脚本。

verifier 提示词模板见 `verifier-agent-template.md`，由 wrapper 复制到
`<project>/.claude/agents/evidence-verifier.md` 或 `~/.claude/agents/evidence-verifier.md`
启用（agent 文件不通过 sync-skills 自动加载，需手工放置）。

---

## 6. 停止 / 回滚条件（命中即报 BLOCKED，不硬推进）

- 无法建立稳定基线
- 正确性无法验证（oracle 失效）
- 度量噪声过大（CV > 10% 标"噪声大"）
- 测试数据缺失
- 权限不足跑不了必要命令
- 下一步需未授权的破坏性 / 生产改动（部署 / 数据库 / 外部服务 / 生产配置）——
  除非任务明确授权，且优先用现有灰度 / 回滚机制

---

## 7. 默认阈值（可改，不可没有）

- 无正确性回归
- 无 route / 测试回归
- 目标 median 或 p95 改善 **≥ 20%**（性能类）
- 内存峰值增幅 **≤ +10%**（否则需说明）
- 度量 **CV ≤ 10%**

**没阈值 = loop 没刹车**。wrapper 可基于项目实际调整数值，但不可省略阈值本身。

---

## 8. 三阶段执行编排（命令侧建议）

wrapper 命令实现"三阶段执行器"，每阶段输出固定结构：

### 阶段 A — HARNESS 就绪报告（只读，不改代码）

1. **当前状态**：已实现 / 部分 / 未实现 / 未知（每项附文件路径或命令输出）
2. **harness 现状核对**：按 §4 表逐项确认能否跑、最近产物在哪、容差 / 阈值是多少
3. **证据表**：每条结论附 路径 / 命令输出 / 测试结果 / commit，否则标"未验证"
4. **缺口清单**：缺什么才能诚实声称做成了
5. **最小有用实验**：1 个假设 + 用哪个命令验证 + 通过阈值

铁律：凭记忆总结 / 从代码结构推断效果 / 无基线就建议改代码 —— 一律禁止。
**说不出"什么证据能证明做成了"就停在阶段 A**。

### 阶段 B — LOOP 迭代（每轮固定 checkpoint）

按 §2 八步走。每轮结束**只输出**这个 checkpoint，避免长程漂移：

```
轮次：
假设：
改动文件：
跑的命令：
正确性结果：
度量结果：
基线 vs 候选：
verifier 结果：
决策：continue / promote / rollback / blocked
下一步：
未验证声明：
```

阶段性证据必须显式打出命令输出（verifier 只看会话里已呈现的证据）。

### 阶段 C — 收尾

1. 跑项目回归门禁（§4 对应列），贴输出
2. 调 `evidence-verifier` agent（fresh context）试图证伪本轮改进
3. 发布安全评估：现有灰度 / 健康检查 / sentinel / rollback 能否支撑；无机制则报"推进受阻"
4. scorecard 写入项目约定位置（基线 / 候选 / 测试 / 风险 / 决策 / 下一实验），**不新建目录**

---

## 9. 配套 /goal 模板（按项目类型替换 §4 的命令）

```
/goal <任务> 的证据闭环完成，当且仅当 transcript 含工具证据满足：
1 基线已建/取回（命令+环境+数据规模+≥3 次重复，或说明为何不能重复）
2 正确性 oracle 通过（该类型对应的脚本/测试）
3 瓶颈假设绑定到代码路径或工具产物，纯猜测标未验证
4 最小改动，无无关重构
5 前后同命令/同数据/同环境并排打印
6 回归门禁通过（项目 verify:full 或 governance）
7 发布安全：灰度/sentinel/rollback 可支撑，否则报推进受阻
8 scorecard 写入项目约定位置
遇 无法建基线/正确性不过/噪声过大/数据缺失/需未授权破坏性改动 → 报 BLOCKED。
无命令输出或产物路径不得宣称成功。
```

---

## 10. wrapper 接入清单（项目侧一次性配置）

把本 skill 落到某项目时，wrapper 需要提供：

| 挂载点 | 项目路径示例 | 作用 |
|---|---|---|
| 项目 rule | `.claude/rules/<project>-evidence-loop.md` | §4 项目专属 harness 映射表 + 项目特例 + 引用基座 |
| 项目命令 | `.claude/commands/<project>-evidence-loop.md` | §8 三阶段执行器，调用本基座 + 项目 rule |
| verifier agent | `.claude/agents/evidence-verifier.md` 或 `~/.claude/agents/evidence-verifier.md` | 复制本仓 `verifier-agent-template.md` 即可 |
| scorecard 落位 | `.claude/shared-memory/` 或同等 | 阶段 C 步骤 4 写入位置 |

**薄 wrapper 写法**：
> 「执行 evidence-loop-core 协议（§1 合同 / §2 loop / §5 verifier 隔离 / §6 停止 / §7 阈值）。
> 本项目 §4 harness 映射表见 `.claude/rules/<project>-evidence-loop.md`，
> verifier agent 见 `.claude/agents/evidence-verifier.md`。」
> ——不重复骨架，只声明挂载点。

---

## 11. 不做什么（范围纪律）

- ❌ 不规定项目脚本路径（§4 表内容由 wrapper 注入，基座只给空表）
- ❌ 不替代项目治理（`bun run governance` / `pnpm lint` / `pytest` 之类是项目侧 §3.3，本协议调用它们不替换）
- ❌ 不要求一次性写完所有阶段——A 阶段产物允许是"缺口报告"，告诉用户什么没就绪
- ❌ 不强制 verifier 是 LLM agent——确定性脚本能验证的优先用脚本，verifier agent 是兜底
