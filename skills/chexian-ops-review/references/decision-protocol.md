# 城市经营诊断 · 决策协议（最小自洽集）

> Contents
> 1. 第八条 — 数据字段分层标注规范（三类）
> 2. 第六条 — 七步接口 JSON 骨架
> 3. 七步 ↔ 统一 8 段输出 ↔ 人机门控 对照
>
> 本文件是 chexian-ops-review 自洽运行所需的最小协议片段，抽自 AI决策协议体系 v2.0
> （第六条接口、第八条字段规范）。完整协议体系由 chexian-api 项目侧维护，不随本 skill 分发；
> 本文件只保留本 skill 实际引用、且执行所必需的部分，保证 skill 可独立解析、独立执行。

---

## 1. 第八条 — 数据字段分层标注规范（三类）

载入城市数据摘要表时，每个字段（指标）必须按可得性归入三类之一，并在输出中显式标注。
这一标注贯穿统一 8 段输出第 2 段「关键证据」的数据质量列。

| 分层 | 含义 | 输出标注 | 处理方式 |
|------|------|---------|---------|
| **直接可用** | 摘要表中已有真实数值 | 可信 | 直接引用，作为结论锚点 |
| **可推导** | 摘要表无直接值，但可由已有字段按公式推算 | 估算 | 推算后标注口径与依赖字段；不可与"可信"混同 |
| **暂缺** | 既无直接值，也无法由现有字段推导 | 缺失 | 列入第 8 段「需补充数据」，标明影响哪段判断 |

> 铁律：可推导值永远标「估算」，禁止冒充「可信」。暂缺字段禁止 AI 凭经验代填数值。

---

## 2. 第六条 — 七步接口 JSON 骨架

每次城市经营诊断对外产出一份结构化记录，骨架如下。`human_selection` / `human_choice`
字段必须由人填写，AI 在这两处只能产出候选（见门控）。

```json
{
  "step_1_data_load": {
    "city": "",
    "as_of_date": "",
    "fields": [
      { "name": "", "tier": "直接可用|可推导|暂缺", "value": null, "quality": "可信|估算|缺失" }
    ]
  },
  "step_2_market": { "sub_skill": "chexian-market-analysis", "conclusion_4choice": "" },
  "step_3_channel": { "sub_skill": "chexian-channel", "tiers": [], "cooperation_mode": [] },
  "step_4_pricing": { "sub_skill": "chexian-pricing-decision", "by_channel_by_vehicle": [] },
  "step_5_dominant_contradiction": {
    "ai_candidates": [
      { "hypothesis": "", "evidence": "", "counter_evidence": "", "confidence": "" },
      { "hypothesis": "", "evidence": "", "counter_evidence": "", "confidence": "" },
      { "hypothesis": "", "evidence": "", "counter_evidence": "", "confidence": "" }
    ],
    "human_selection": null
  },
  "step_6_strategy": {
    "ai_candidates": ["", "", ""],
    "human_choice": null
  },
  "step_7_risk": {
    "monitoring_metrics": [],
    "verifiable_prediction": "[指标] 预计在 [时间] 后 [方向] [幅度]"
  },
  "feedback_loop": {
    "ai_output": { "dominant_contradiction": "", "recommended_strategy": "", "prediction": "" },
    "human_decision": { "adopted": null, "actual_strategy": "", "deviation_reason": "" },
    "actual_result": { "review_date": "", "label": "准确|偏高|偏低" }
  }
}
```

---

## 3. 七步 ↔ 统一 8 段输出 ↔ 人机门控 对照

| 步骤 | 七步接口字段 | 对应输出段 | 门控 |
|------|------|---------|------|
| Step 1 数据载入 | step_1_data_load | 第 2 段证据基底 | 高，AI 主导 |
| Step 2 市场（可并行） | step_2_market | 第 1/4 段 | 中-高，AI 主导 |
| Step 3 渠道（可并行） | step_3_channel | 第 4/5 段 | 中-高，AI 主导 |
| Step 4 定价（依赖 2/3） | step_4_pricing | 第 5 段 | 中，AI 主导 |
| **Step 5 主导矛盾** | step_5_dominant_contradiction | 第 3 段 | **低 ⛔ AI 出 3 候选，人判断** |
| **Step 6 策略选择** | step_6_strategy | 第 5 段 | **低 ⛔ AI 出 3 候选，人拍板** |
| Step 7 风险提示 | step_7_risk | 第 6/7 段 | 高，AI 主导，人审监控指标 |
