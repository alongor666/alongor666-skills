---
name: chexian-ir-diagnosis
description: Use when diagnosing auto insurance incident rate deterioration, investigating why 出险率 is worsening, or performing root cause analysis on loss frequency. Trigger phrases — 分析出险率, 出险率恶化, 出险率诊断, 为什么出险率上升, incident rate drill-down. 2026-05-18 由 auto-ir-diagnosis 改名归入 chexian 簇（ir=Incident Rate 出险率）。
version: 1.1.0
user_invocable: true
---

# 出险率自主诊断

脚本做精确计算（零token），本Skill做智能判断。循环：运行脚本 → 读输出 → 判断下一步 → 直到所有🔴路径到达终点。

## 任务流（7步）

### Step 1 — 理解任务

确认范围：全省 / 单机构 / 单车型？默认全省。

可用工具：
- `python3 04_工程/脚本/生成出险率下钻_v2.py` → 出险率下钻MD + **诊断摘要JSON**
- `python3 04_工程/脚本/生成红绿灯仪表盘.py` → 全省KPI总览
- `python3 04_工程/脚本/生成费用率下钻.py` → 费用率交叉验证
- `python3 04_工程/脚本/生成车型深度分析.py --province 四川 --city X --label Y` → 月度趋势
- `04_工程/脚本/knowledge.py` → `scan_knowledge(keywords)` 知识库查询
- 保单级parquet → `~/Downloads/底层数据湖DUD/chexian-api/数据管理/warehouse/fact/policy/daily/`

### Step 2 — 运行主下钻脚本

```bash
cd /Users/alongor666/Desktop/私董会--车险作战地图
python3 04_工程/脚本/生成出险率下钻_v2.py
```

产出：`03_四川/下钻分析/出险率下钻_v2.md` + `出险率诊断摘要.json`

### Step 3 — 读JSON摘要，理解全局

读 `出险率诊断摘要.json`：
- `global.direction`：恶化→继续 / 改善→跳到Step 6报告"无显著恶化"
- `global.diagnosis`：频度驱动还是案均驱动→决定根因方向
- `why1_tracked`：🔴车型列表，按影响度从差到好

### Step 4 — 逐条路径智能决策

遍历 `why3_paths`，按 `next_action` 路由：

| next_action | 含义 | 行动 |
|-------------|------|------|
| `done` | 有区分维度，路径已收敛 | 提取findings，归入根因分类 |
| `policy_level_query` | 无区分度但样本充足 | 用pandas查保单级parquet（见下方模板） |
| `knowledge_query` | 需查内部知识 | 调用 `scan_knowledge([org, bt])` |

**区分度判断**（已由脚本计算，存于 `findings[].spread_pp`）：
- ≥20pp → 病灶已锁定，高置信
- 10-19pp → 有方向，中置信
- 5-9pp → 仅参考，低置信
- <5pp → 无区分度，脚本已标 `stop_reason`

**保单级查询模板**（当 next_action=policy_level_query）：

parquet有保单号+车架号，是真正的保单级数据。**用车架号（而非保单号）关联赔案**——保单号跨年格式可能不一致，车架号稳定。

```python
import pandas as pd, glob, sys
sys.path.insert(0, "04_工程/脚本")
from common import (derive_price_band, derive_plate_origin,
                    derive_customer_source_category, derive_seat_group)

files = sorted(glob.glob(
    "~/Downloads/底层数据湖DUD/chexian-api/数据管理/warehouse/fact/policy/daily/2026-*.parquet"
))[-30:]
df = pd.concat([pd.read_parquet(f) for f in files])
claims = pd.read_parquet(
    "~/Downloads/底层数据湖DUD/chexian-api/数据管理/warehouse/fact/claims/latest.parquet")

# 赔案按车架号聚合
claims_agg = claims.groupby("车架号").agg(总赔案件数=("赔案件数","sum")).reset_index()
claims_vins = set(claims_agg[claims_agg["总赔案件数"]>0]["车架号"])

# 筛选 + 车架号去重
subset = df[(df["三级机构"]=="<org>") & (df["客户类别"]=="<客户类别>")]
subset = subset.drop_duplicates(subset="车架号", keep="first").copy()
subset["has_claim"] = subset["车架号"].isin(claims_vins)

# 派生字段
subset["车辆类型"] = "旧车非过户"
subset.loc[subset["是否新车"]==True, "车辆类型"] = "新车"
subset.loc[subset["是否过户车"]==True, "车辆类型"] = "过户车"
subset["渠道"] = subset["终端来源"].apply(lambda x: "电销" if "融合" in str(x) else "非电销")
subset["价格段"] = subset["新车购置价"].apply(derive_price_band)
subset["车牌归属"] = subset.apply(lambda r: derive_plate_origin(r["车牌号码"], r["三级机构"]), axis=1)
subset["客户源分类"] = subset["客户源"].apply(derive_customer_source_category)
subset["座位分组"] = subset["座位数"].apply(derive_seat_group)

# 分析维度（按业务规则选择）
for dim in ["车辆类型", "渠道", "险别组合", "险类", "价格段", "车牌归属",
            "客户源分类", "座位分组"]:
    g = subset.groupby(dim).agg(n=("车架号","count"), c=("has_claim","sum"))
    g["出险频度"] = (g.c / g.n * 100).round(2)
    print(f"\\n按{dim}:"); print(g.sort_values("出险频度", ascending=False))

# 旧车非过户内看风险等级
old = subset[subset["车辆类型"]=="旧车非过户"]
print(old.groupby("车险风险等级").agg(n=("车架号","count"),c=("has_claim","sum")))

# 定位具体客户源（按出险频度排序，样本≥20）
cs = subset.groupby("客户源").agg(n=("车架号","count"), c=("has_claim","sum"))
cs["出险频度"] = (cs.c / cs.n * 100).round(2)
print(cs[cs.n >= 20].sort_values("出险频度", ascending=False).head(20))
```

**维度体系（两层数据对应关系）**：

| 维度 | 聚合数据（下钻脚本） | parquet（保单级） | 说明 |
|------|-------------------|-----------------|------|
| 车型 | business_type_category | 客户类别 | WHY-1层 |
| 机构 | third_level_organization | 三级机构 | WHY-2层 |
| 能源 | is_new_energy_vehicle | 是否新能源 | bool |
| 过户/新车 | is_transferred_vehicle | 是否过户车/是否新车 | 分层关键 |
| 续保状态 | renewal_status | 是否续保 | 转保/续保/新保 |
| 渠道 | channel_type（派生） | 是否电销 / 终端含"融合" | 电销/非电销 |
| 风险等级 | vehicle_insurance_grade | 车险风险等级 | 仅旧车非过户可用 |
| **险别组合** | coverage_type | 险别组合 | 单交/交三/主全 |
| **险种类** | insurance_type | 险类 | 交强险/商业保险 |
| **价格段** | ❌ 无 | derive_price_band() | 10万以下/10-20万/20-50万/50万以上 |
| **座位数** | ❌ 无 | derive_seat_group() | 4座以下/5座/6-7座/8座以上 |
| **客户源** | ❌ 无 | derive_customer_source_category() | 个人直客/自营/修理厂·车行/4S·经销商/其他 |
| **客户源明细** | ❌ 无 | 客户源（原始值） | 定位到具体修理厂/经代 |
| **车牌归属** | ❌ 无 | derive_plate_origin() | 本地/本省外地/外省 |

注意：
- `是否新能源`、`是否过户车`、`是否新车` 在parquet中是bool类型
- parquet无`业务类别`字段，用`客户类别`代替
- 终端来源只区分电销（终端含"融合"或`是否电销==True`）vs 非电销
- parquet无满期保费，**算出的是车辆出险频度，不是精确满期出险率**
- 小货车评分、吨位分段仅适用于货车类别，非营业客车不使用

### Step 5 — 判断是否追加脚本

| 触发条件 | 追加脚本 |
|---------|---------|
| 恶化车型含家自车且月度趋势不明 | `生成车型深度分析.py --label 家自车` |
| 变动成本率是否超91%不确定 | `生成红绿灯仪表盘.py` |
| 费用率与出险率同时恶化 | `生成费用率下钻.py` |
| 无现成脚本但有数据 | **自己写Python片段**，存到 `04_工程/脚本/`，下次复用 |
| 无法判断 | **向人类报告**，列出具体问题 |

### Step 6 — 输出一页纸诊断报告

按下方输出模板生成。每条路径必须归入根因分类。

### Step 7 — 存档

写入 `03_四川/下钻分析/出险率诊断报告_YYYYMMDD.md`

## 根因分类（每条路径必归其一）

| 分类 | 特征 | 行动方向 |
|------|------|---------|
| **承保端** | 转保占比高、特定车辆类型集中（如过户车）、电销渠道占比高 | 收紧核保规则，调整承保条件 |
| **定价端** | 案均高、赔付率恶化、过户车/新车缺乏定价因子 | 优化定价模型，补充定价因子 |
| **渠道端** | 电销vs非电销有显著差异 | 调整渠道策略 |
| **待确认** | 无区分维度 / 矛盾信号 / 样本不足 | 明确标注，列出具体问题 |

注意：定价系数是**定价工具**，不是出险率的原因。系数低→可能吸引高风险业务（推断），但不能说"系数低导致出险率高"。

## 人机交接节点（必须停止等人）

- ir>60% 且无知识库解释 → 🚨 是否存在批量异常承保？
- 频度+案均均恶化且幅度>15% → 提3个候选根因，人拍板
- 知识库说A但数据说非A → 展示矛盾，请人判断
- 任何"收紧核保"或"限制渠道"建议 → 标注"建议，需人确认执行"

## 满期出险率公式（CRITICAL — 必须理解后才能分析）

```
满期出险率 = (赔案件数 / 保单件数) / (满期保费 / 跟单保费) × 100%
           = 签单出险率 / 满期系数
```

- **赔案件数/保单件数** = 签单口径出险率（出险频度）
- **满期保费/跟单保费** = 满期系数（满期率），反映保单"过期"程度
- 满期率=100%时（如2024年已全部到期），满期出险率=签单出险率
- 满期率<100%（如2026年大量保单尚未到期），需用满期系数折算为可比口径

**满期出险率衡量的是"出险频率"——多少保单出了险。它独立于保费定价。**

### 出险率与定价系数的关系（CRITICAL — 禁止混淆因果）

- ❌ "定价系数低→出险率高"——错。定价系数影响保费收入，不直接影响是否出险
- ❌ "定价系数下移导致出险率恶化"——错。系数是定价工具，不是出险原因
- ✅ 定价系数低→可能吸引高风险客户（逆选择）→间接影响出险率，但这只是**推断**，非必然
- ✅ 定价系数影响的是**赔付率**（=已报告赔款/满期保费），而非出险率
- 分析时：出险率和定价系数是两个独立观察维度，不要暗示因果

### 聚合数据 vs 保单级数据的出险率计算

| 数据源 | 计算方式 | 适用场景 |
|--------|---------|---------|
| CSV/XLSX聚合 | `calc_ir(d)` — 有满期保费，可算精确满期出险率 | 下钻脚本（WHY-1/2/3） |
| parquet保单级 | 车架号去重后，出险车辆数/承保车辆数 — **无满期保费，只能算车辆出险频度** | 保单级追溯、多年同期对比 |

保单级分析用parquet时，输出说明为"车辆粒度出险频度"而非"满期出险率"（因缺少满期系数无法精确折算）。

## 业务领域规则（CRITICAL — 违反即分析无效）

### 终端来源的正确理解
终端来源字段（0202APP、0106移动展业、0201PC、0101柜面、0112AI出单等）只是保单录入工具/方式，**不是销售渠道**。唯一有渠道含义的是 `0110融合销售`（=电销渠道）。分析时：
- ✅ 按"电销 vs 非电销"区分——终端含"融合"即电销
- ❌ 把0202APP、0106移动展业当作不同"渠道"比较——这只是录单习惯差异
- 车架号三年同期验证：电销满期出险率持续高于非电销（差距2-5pp），有实质区分力

### 风险等级的正确理解
车险风险等级基于历史出险数据评定。**过户车和新车由于没有历史数据，结构性无法评分**——不是"漏评"、不是"绕过"、不是"系统漏洞"。分析时：
- ✅ 先按过户车/新车 vs 旧车非过户分层，再在旧车非过户内看风险等级区分度
- ✅ 过户车/新车无评分 → 归因为"定价因子不足"，行动方向是优化定价模型
- ❌ 将"无风险等级"笼统归为"评分缺失"或"核保漏洞"

### 数据层次区分
| 数据层 | 来源 | 颗粒度 | 用途 |
|--------|------|--------|------|
| 聚合数据 | CSV/XLSX变动成本清单 | 按维度字段聚合 | 脚本下钻（WHY-1/2/3） |
| 保单级数据 | parquet数据湖 | 有保单号+车架号，细到每台车 | 逐单追溯、品牌拆解、大案分析 |

说"保单级分析"时**必须用parquet**（有保单号+车架号）。CSV/XLSX本质是聚合报表，不算保单级。

## 分析铁律

1. 频度恶化+案均改善 → 核保端，不是定价端
2. 频度+案均同向恶化 → 优先锁定频度端
3. 摩托车高出险率是结构性特征，看vs25变化而非绝对值
4. policy<30不得下结论，只标"⚠️ 样本不足"
5. 知识库未记载的不能当确定结论，必须标"假设"
6. 终端来源只区分"电销 vs 非电销"，不把录单工具当渠道
7. 过户车/新车无风险等级是结构性事实，不是漏评
8. 满期出险率独立于定价系数——系数是定价工具，不决定出险与否
9. 保单级分析用车架号（非保单号）关联赔案——保单号跨年格式可能不一致

## 输出模板

```markdown
# 出险率诊断报告（YYYY-MM-DD）

## 一句话结论
> [恶化/改善]：全省出险率X.X%（vs25 +/-X.Xpp），[频度/案均]驱动，
> 核心病灶在[车型×机构×维度]，属[承保/定价/渠道]端问题。

## 病灶清单（按影响度，从差到好）
| 关注 | 路径 | 出险率 | 影响度 | 病灶维度 | 根因 | 置信度 |
|------|------|-------:|-------:|---------|------|--------|

## 病灶详情（每个🔴一段）
### [车型×机构]（影响度+X.XX）
- **发现**：[维度]区分度Xpp
- **根因**：一句话
- **行动**：一句话，含具体对象/阈值
- **置信度**：高/中/低

## 行动建议汇总
| 优先级 | 行动 | 对象 | 预期效果 |

## 未解决问题
- [ ] 具体问题 + 建议查询指令
```

## 排版规则

- 结论上优先（标题下表格上）、关注列左优先（第一列）
- 所有排序从差到好（影响度降序）
- 文字中提及机构/车型也按差到好排列
