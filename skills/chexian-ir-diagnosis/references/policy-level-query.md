# 保单级查询（policy_level_query 路径专用）

> 仅当 `why3_paths[].next_action == policy_level_query`（无区分度但样本充足）时载入本文件。常态诊断路径不需要。

## Contents

- [关联铁律](#关联铁律)
- [pandas 模板](#pandas-模板)
- [维度体系（两层数据对应关系）](#维度体系两层数据对应关系)
- [注意事项](#注意事项)

## 关联铁律

parquet 有保单号+车架号，是真正的保单级数据。**用车架号（而非保单号）关联赔案**——保单号跨年格式可能不一致，车架号稳定。

## pandas 模板

> **维度顺序非固定**：先按 `global.diagnosis` 与 `why1_tracked` 的车型特征判断哪些维度最可能有区分度，再决定遍历哪几个，不必全跑。下方 8 维 for 循环是参考全集，按业务语境选路。

```python
import glob, os, sys
import pandas as pd
sys.path.insert(0, "04_工程/脚本")
from common import (derive_price_band, derive_plate_origin,
                    derive_customer_source_category, derive_seat_group)

# glob 不展开 ~，必须 expanduser，否则静默返回空列表；数据湖根可经 CHEXIAN_DATA_ROOT 覆盖
DATA_ROOT = os.path.expanduser(os.environ.get(
    "CHEXIAN_DATA_ROOT", "~/Downloads/底层数据湖DUD/chexian-api"))
files = sorted(glob.glob(
    f"{DATA_ROOT}/数据管理/warehouse/fact/policy/daily/2026-*.parquet"
))[-30:]
assert files, f"未找到保单 parquet：检查 {DATA_ROOT} 是否存在或设置 CHEXIAN_DATA_ROOT"
df = pd.concat([pd.read_parquet(f) for f in files])
claims = pd.read_parquet(
    f"{DATA_ROOT}/数据管理/warehouse/fact/claims/latest.parquet")

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

# 分析维度（按业务规则选择，不必全遍历）
for dim in ["车辆类型", "渠道", "险别组合", "险类", "价格段", "车牌归属",
            "客户源分类", "座位分组"]:
    g = subset.groupby(dim).agg(n=("车架号","count"), c=("has_claim","sum"))
    g["出险频度"] = (g.c / g.n * 100).round(2)
    print(f"\n按{dim}:"); print(g.sort_values("出险频度", ascending=False))

# 旧车非过户内看风险等级
old = subset[subset["车辆类型"]=="旧车非过户"]
print(old.groupby("车险风险等级").agg(n=("车架号","count"),c=("has_claim","sum")))

# 定位具体客户源（按出险频度排序，样本≥20）
cs = subset.groupby("客户源").agg(n=("车架号","count"), c=("has_claim","sum"))
cs["出险频度"] = (cs.c / cs.n * 100).round(2)
print(cs[cs.n >= 20].sort_values("出险频度", ascending=False).head(20))
```

## 维度体系（两层数据对应关系）

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

## 注意事项

- `是否新能源`、`是否过户车`、`是否新车` 在parquet中是bool类型
- parquet无`业务类别`字段，用`客户类别`代替
- 终端来源只区分电销（终端含"融合"或`是否电销==True`）vs 非电销
- parquet无满期保费，**算出的是车辆出险频度，不是精确满期出险率**
- 小货车评分、吨位分段仅适用于货车类别，非营业客车不使用
