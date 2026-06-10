---
name: chexian-ir-diagnosis
description: Use when diagnosing auto insurance incident rate deterioration, investigating why 出险率 is worsening, or performing root cause analysis on loss frequency (ir = Incident Rate 出险率). Trigger phrases — 分析出险率, 出险率恶化, 出险率诊断, 为什么出险率上升, incident rate drill-down.
user_invocable: true
version: "1.1.0"
---

# 出险率自主诊断

## Overview

脚本做精确计算（零 token），本 Skill 做智能判断。核心循环：**运行脚本 → 读输出 → 判断下一步 → 直到所有 🔴 路径到达终点**。中间产物链是推荐工作流：`下钻 JSON 摘要 → 校验区分度 → 归入根因分类 → 生成一页纸报告`。

## When to Use

- 出险率 vs 上年同期（vs25）恶化，需要找原因
- 单机构 / 单车型出现异常，需要归因
- 需要把恶化归因到 车型 × 机构 × 维度（渠道/风险等级/价格段/客户源…）

## When NOT to Use

- 已知改善路径、无需诊断 → 直接跳到报告写"无显著恶化"
- 纯保费 / 赔付率 / 定价策略问题（不是出险频率问题）→ 转 `chexian-pricing-decision`

## 任务流 checklist

复制到回复中逐项打勾：

- [ ] **Step 1 — 理解任务**：确认范围（全省 / 单机构 / 单车型？默认全省）
- [ ] **Step 2 — 运行主下钻脚本**
- [ ] **Step 3 — 读 JSON 摘要，理解全局**
- [ ] **Step 4 — 逐条路径智能决策**
- [ ] **Step 5 — 判断是否追加脚本**
- [ ] **Step 6 — 输出一页纸诊断报告**
- [ ] **Step 7 — 存档**

### Step 1 — 理解任务

可用工具：
- `python3 04_工程/脚本/生成出险率下钻_v2.py` → 出险率下钻 MD + **诊断摘要 JSON**
- `python3 04_工程/脚本/生成红绿灯仪表盘.py` → 全省 KPI 总览
- `python3 04_工程/脚本/生成费用率下钻.py` → 费用率交叉验证
- `python3 04_工程/脚本/生成车型深度分析.py --province 四川 --city X --label Y` → 月度趋势
- `04_工程/脚本/knowledge.py` → `scan_knowledge(keywords)` 知识库查询
- 保单级 parquet → `~/Downloads/底层数据湖DUD/chexian-api/数据管理/warehouse/fact/policy/daily/`

### Step 2 — 运行主下钻脚本

```bash
# 工作目录可经 ZSD_ROOT 环境变量覆盖（默认本机作战地图项目根）
cd "${ZSD_ROOT:-/Users/alongor666/Desktop/私董会--车险作战地图}"
python3 04_工程/脚本/生成出险率下钻_v2.py
```

产出：`03_四川/下钻分析/出险率下钻_v2.md` + `出险率诊断摘要.json`

### Step 3 — 读 JSON 摘要，理解全局

读 `出险率诊断摘要.json`：
- `global.direction`：恶化 → 继续 / 改善 → 跳到 Step 6 报告"无显著恶化"
- `global.diagnosis`：频度驱动还是案均驱动 → 决定根因方向
- `why1_tracked`：🔴 车型列表，按影响度从差到好

### Step 4 — 逐条路径智能决策

遍历 `why3_paths`，按 `next_action` 路由：

| next_action | 含义 | 行动 |
|-------------|------|------|
| `done` | 有区分维度，路径已收敛 | 提取 findings，归入根因分类 |
| `policy_level_query` | 无区分度但样本充足 | 见 [references/policy-level-query.md](references/policy-level-query.md) |
| `knowledge_query` | 需查内部知识 | 调用 `scan_knowledge([org, bt])` |

**区分度判断**（已由脚本计算，存于 `findings[].spread_pp`）：
- ≥20pp → 病灶已锁定，高置信
- 10-19pp → 有方向，中置信
- 5-9pp → 仅参考，低置信
- <5pp → 无区分度，脚本已标 `stop_reason`

**并行提示**：多条 🔴 路径的 `policy_level_query` 与追加脚本相互独立，可并行 fan-out（并发 Bash / 子代理）而非逐条串行。

### Step 5 — 判断是否追加脚本

| 触发条件 | 追加脚本 |
|---------|---------|
| 恶化车型含家自车且月度趋势不明 | `生成车型深度分析.py --label 家自车` |
| 变动成本率是否超 91% 不确定 | `生成红绿灯仪表盘.py` |
| 费用率与出险率同时恶化 | `生成费用率下钻.py` |
| 无现成脚本但有数据 | **自己写 Python 片段**，存到 `04_工程/脚本/`，下次复用 |
| 无法判断 | **向人类报告**，列出具体问题 |

多条独立追加脚本无依赖，可并行触发。

### Step 6 — 输出一页纸诊断报告

按 [references/output-template.md](references/output-template.md) 的模板与排版规则生成。每条路径必须归入根因分类。

### Step 7 — 存档

写入 `03_四川/下钻分析/出险率诊断报告_YYYYMMDD.md`

## 根因分类（每条路径必归其一）

| 分类 | 特征 | 行动方向 |
|------|------|---------|
| **承保端** | 转保占比高、特定车辆类型集中（如过户车）、电销渠道占比高 | 收紧核保规则，调整承保条件 |
| **定价端** | 案均高、赔付率恶化、过户车/新车缺乏定价因子 | 优化定价模型，补充定价因子 |
| **渠道端** | 电销 vs 非电销有显著差异 | 调整渠道策略 |
| **待确认** | 无区分维度 / 矛盾信号 / 样本不足 | 明确标注，列出具体问题 |

注意：定价系数是**定价工具**，不是出险率的原因。系数低 → 可能吸引高风险业务（推断），但不能说"系数低导致出险率高"。

## 人机交接节点（必须停止等人）

在这些节点下结论前，**先列出候选假设与各自证据，再下判断**（Opus 长程推理点）：

- ir>60% 且无知识库解释 → 🚨 是否存在批量异常承保？
- 频度+案均均恶化且幅度>15% → 先列候选假设+证据，再提 3 个候选根因，人拍板
- 知识库说 A 但数据说非 A → 展示矛盾，请人判断
- 任何"收紧核保"或"限制渠道"建议 → 标注"建议，需人确认执行"

## 分析铁律

1. 频度恶化+案均改善 → 核保端，不是定价端
2. 频度+案均同向恶化 → 优先锁定频度端
3. 摩托车高出险率是结构性特征，看 vs25 变化而非绝对值
4. policy<30 不得下结论，只标"⚠️ 样本不足"
5. 知识库未记载的不能当确定结论，必须标"假设"
6. 终端来源只区分"电销 vs 非电销"，不把录单工具当渠道
7. 过户车/新车无风险等级是结构性事实，不是漏评
8. 满期出险率独立于定价系数——系数是定价工具，不决定出险与否
9. 保单级分析用车架号（非保单号）关联赔案——保单号跨年格式可能不一致

## 领域规则（CRITICAL）

满期出险率公式、出险率 vs 定价系数因果禁忌、聚合 vs 保单级口径、终端来源/风险等级理解、数据层次区分 — 全部见 [references/domain-rules.md](references/domain-rules.md)。**违反即分析无效，分析前必读。**
