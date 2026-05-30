---
name: chexian-ops-review
description: Use when conducting a full city-level auto insurance operating review for Hua'an Insurance — combining market, pricing, and channel analysis into a complete diagnosis with resource allocation recommendations. 当用户说"城市经营复盘/华安城市级诊断/市场+渠道+承保+理赔合并视图"时使用。
version: 1.1.0
user_invocable: true
---

# 车险城市经营诊断

## Overview

城市级"三合一"编排 skill：串接市场（market）、渠道（channel）、定价（pricing）三个子协议，
完成一份覆盖市场 + 渠道 + 承保 + 理赔合并视图的城市级完整经营诊断，产出含资源配置建议的统一 8 段结论。
遵循七步接口与字段分层规范，详见 [references/decision-protocol.md](references/decision-protocol.md)。

## When to Use

适用场景（出现以下任一即触发本编排）：

- 需要市场 + 渠道 + 承保 + 理赔的合并视图，而非单一维度
- 城市级经营复盘 / 华安城市级诊断
- 要在一份报告里同时给出市场结论、渠道分层、定价策略，并落到资源配置优先级

何时不用（直接跑对应子 skill，不必走本编排）：

- 只需市场竞争结构 / 进入判断 → 直接 `/chexian-market-analysis`
- 只需渠道分层 / 合作模式评估 → 直接 `/chexian-channel`
- 只需定价 / 核保决策 → 直接 `/chexian-pricing-decision`

## 执行流程（checklist）

- [ ] **Step 1** 载入城市数据摘要表
      → 字段三类分层标注（直接可用 / 可推导 / 暂缺）见 [references/decision-protocol.md](references/decision-protocol.md) 第八条
- [ ] **Step 2** `/chexian-market-analysis` → 市场结论（四选一）
- [ ] **Step 3** `/chexian-channel` → 渠道分层与合作模式建议
- [ ] **Step 4** `/chexian-pricing-decision` → 分渠道 / 分车型定价策略
- [ ] **Step 5** 整合输出主导矛盾（统一 8 段格式第 3 段）
- [ ] **Step 6** 策略选择（统一 8 段格式第 5 段）
- [ ] **Step 7** 风险提示与可验证预测（统一 8 段格式第 6/7 段）

> **并行提示（Opus 4.8）**：Step 2 市场分析与 Step 3 渠道分层在数据载入后相对独立，
> 可并行子代理 fan-out 同时跑；Step 4 定价依赖前两者结论，故置后串行整合。

## 人机门控（硬性约束）

| 步骤 | AI置信度 | 交接方式 |
|------|---------|---------|
| Step 1-4 | 高-中 | AI主导，人确认/修正 |
| **Step 5 主导矛盾** | **低** | **⛔ AI出3候选，人判断，AI禁止代填** |
| **Step 6 策略选择** | **低** | **⛔ AI出3候选，人拍板，AI禁止代填** |
| Step 7 风险提示 | 高 | AI主导，人审核监控指标 |

> Step 5 是全流程最高风险节点。因果推断是 AI 最弱的能力，主导矛盾必须由人判断。
> **结构化思考（Opus 4.8）**：Step 5 先产出 3 候选主导矛盾的结构化对比
> （每条含 证据 / 反证 / 置信度）作为中间产物 → 再交人判断，不要跳过候选直接下单一结论。

## 统一输出格式

1. **本质判断**（一句话）
2. **关键证据**（含数据质量标注：可信/估算/缺失）
3. **主导矛盾**（human_selection，人工确认项）
4. **经营含义**
5. **策略建议**（human_choice，人工选定项）
6. **可验证预测**：`[指标] 预计在 [时间] 后 [方向] [幅度]`
7. **风险提示**
8. **需补充数据**

## 反馈闭环

每次分析生成三元记录：
- **AI输出**：主导矛盾 + 推荐策略 + 可验证预测（指标/方向/幅度/复审日期）
- **人工决策**：是否采纳 + 实际策略 + 偏差原因
- **实际结果**：复审日填写，标注准确/偏高/偏低

**触发规则**：连续3次同方向偏差 → 触发市场认知前提版本升级。

## 核心指标（10项，每项须标注存量值+趋势+数据质量）

保费 / 件数 / 件均 / 赔付率 / 费用率 / 变动成本率 / 商业险投保率 / 套单占比 / 续保率 / 渠道产能

## 分析铁律

1. 不准只看规模，不看成本
2. 不准只看价格，不看成交
3. 不准只看赔付，不看费用
4. 不准只看客户，不看渠道
5. 赔付率异常时必须拆解频度与案均

---

> 七步接口 JSON 骨架、第六条接口与第八条字段规范详见 [references/decision-protocol.md](references/decision-protocol.md)。
> 沿革：2026-05-18 由 auto-ops-review 改名归入 chexian 簇。
