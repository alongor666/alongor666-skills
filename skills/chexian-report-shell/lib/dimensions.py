"""9 维下钻元数据单一事实源（v1.18 新增）。

设计目标：
  - 集中定义经营诊断周报支持的全部下钻维度
  - 每维包含：机器键 / 中文短标签 / SQL 表达式 / 取值集合 / 文件名规则
  - grouping_sets.py、drill_writer.py、sections/* 全部从此处取定义，禁止硬编码

维度分类（用户 2026-05-17 决策：drilldown-dimensions.ts 4/17 收敛规则失效）：
  组织/客户类（3 维，已锁 org_level_3=<某机构>，故不参与下钻）：
    team / salesman / customer_category
  业务属性（6 维，重新启用下钻）：
    insurance_type / coverage_combination / is_nev / is_new_car /
    is_transfer / is_renewal
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ============== 数据结构 ==============

@dataclass(frozen=True)
class ValueDef:
    """单个维度值的展示定义。

    Attributes:
      sql_value: SQL 表达式输出的值（CAST 后字符串形式，与 DuckDB 输出对齐）
      display: 展示用中文（出现在表头/卡片/链接锚文本）
      basename: 文件名 stem（< 30 字符 / 不含路径分隔符，URL 安全）
    """
    sql_value: str
    display: str
    basename: str


@dataclass(frozen=True)
class DrillDimension:
    """单维下钻定义。

    Attributes:
      key: 机器键（如 "insurance_type"），与 SHORT_LABEL/FULL_LABEL 对齐
      short_label: 卡片标题/链接简称（窄列）
      full_label: 说明页全称
      sql_expr: GROUPING SETS 用的维度 SQL 表达式（已含 CAST 到 VARCHAR）
      values: 静态取值集合；None 表示运行时动态收集（如 team/salesman）
      narrative_template: 下钻页 header 简介模板，占位符 `{value}` 替换
    """
    key: str
    short_label: str
    full_label: str
    sql_expr: str
    values: Optional[list[ValueDef]] = None
    narrative_template: str = "本页为 {dim}={value} 的下钻明细。"


# ============== 9 维注册表 ==============

# --- 组织/客户类（3 维，值动态/静态混合）---

DIM_TEAM = DrillDimension(
    key="team",
    short_label="团队",
    full_label="销售团队",
    sql_expr="COALESCE(NULLIF(short_team_name(team), ''), '未知')",
    values=None,  # 动态：运行时取 DISTINCT team
    narrative_template="本页为销售团队「{value}」的下钻明细。",
)

DIM_SALESMAN = DrillDimension(
    key="salesman",
    short_label="业务员",
    full_label="业务员",
    sql_expr="COALESCE(NULLIF(short_salesman_name(salesman_name), ''), '未知')",
    values=None,  # 动态：Top 20 + 关注名单
    narrative_template="本页为业务员「{value}」的下钻明细。",
)

DIM_ORG_LEVEL_3 = DrillDimension(
    key="org_level_3",
    short_label="三级机构",
    full_label="三级机构",
    sql_expr="org_level_3",
    values=None,  # 动态：分公司层全部三级机构（分公司层替代 salesman 维度）
    narrative_template="本页为三级机构「{value}」的下钻明细。",
)

DIM_CUSTOMER_CATEGORY = DrillDimension(
    key="customer_category",
    short_label="客户类别",
    full_label="客户类别",
    sql_expr="customer_category",
    values=[
        ValueDef("非营业个人客车", "家自车",   "家自车"),
        ValueDef("摩托车",         "摩托车",   "摩托车"),
        ValueDef("非营业货车",     "非营货",   "非营货"),
        ValueDef("非营业企业客车", "非营企",   "非营企"),
        ValueDef("营业货车",       "营货",     "营货"),
        ValueDef("营业出租租赁",   "出租租赁", "出租租赁"),
        ValueDef("特种车",         "特种车",   "特种车"),
        ValueDef("营业公路客运",   "公路客运", "公路客运"),
        ValueDef("挂车",           "挂车",     "挂车"),
        ValueDef("非营业机关客车", "机关车",   "机关车"),
        ValueDef("营业城市公交",   "城市公交", "城市公交"),
    ],
    narrative_template="本页为客户类别「{value}」的下钻明细。",
)

# --- 业务属性（6 维，全部静态二值/多值）---

DIM_INSURANCE_TYPE = DrillDimension(
    key="insurance_type",
    short_label="险类",
    full_label="保险类别",
    sql_expr="insurance_type",
    values=[
        ValueDef("交强险",   "交强险",   "交强险"),
        ValueDef("商业保险", "商业保险", "商业保险"),
    ],
    narrative_template="本页为险类「{value}」的下钻明细。",
)

DIM_COVERAGE = DrillDimension(
    key="coverage_combination",
    short_label="险别组合",
    full_label="险别组合",
    sql_expr="coverage_combination",
    values=[
        ValueDef("单交", "单交", "单交"),
        ValueDef("交三", "交三", "交三"),
        ValueDef("主全", "主全", "主全"),
        ValueDef("其他", "其他", "其他"),
    ],
    narrative_template="本页为险别组合「{value}」的下钻明细。",
)

DIM_IS_NEV = DrillDimension(
    key="is_nev",
    short_label="能源",
    full_label="能源类型",
    sql_expr="CASE WHEN is_nev THEN '新能源' ELSE '燃油' END",
    values=[
        ValueDef("新能源", "新能源", "新能源"),
        ValueDef("燃油",   "燃油",   "燃油"),
    ],
    narrative_template="本页为能源类型「{value}」的下钻明细。",
)

DIM_IS_NEW_CAR = DrillDimension(
    key="is_new_car",
    short_label="新旧车",
    full_label="新旧车",
    sql_expr="CASE WHEN is_new_car THEN '新车' ELSE '旧车' END",
    values=[
        ValueDef("新车", "新车", "新车"),
        ValueDef("旧车", "旧车", "旧车"),
    ],
    narrative_template="本页为新旧车「{value}」的下钻明细。",
)

DIM_IS_TRANSFER = DrillDimension(
    key="is_transfer",
    short_label="过户",
    full_label="是否过户",
    sql_expr="CASE WHEN is_transfer THEN '过户' ELSE '非过户' END",
    values=[
        ValueDef("过户",   "过户",   "过户"),
        ValueDef("非过户", "非过户", "非过户"),
    ],
    narrative_template="本页为是否过户「{value}」的下钻明细。",
)

DIM_IS_RENEWAL = DrillDimension(
    key="is_renewal",
    short_label="续保",
    full_label="是否续保",
    sql_expr="CASE WHEN is_renewal THEN '续保' ELSE '非续保' END",
    values=[
        ValueDef("续保",   "续保",   "续保"),
        ValueDef("非续保", "非续保", "非续保"),
    ],
    narrative_template="本页为是否续保「{value}」的下钻明细。",
)


# ============== 全维注册表 ==============

ALL_DIMENSIONS: list[DrillDimension] = [
    DIM_TEAM,
    DIM_SALESMAN,
    DIM_ORG_LEVEL_3,
    DIM_CUSTOMER_CATEGORY,
    DIM_INSURANCE_TYPE,
    DIM_COVERAGE,
    DIM_IS_NEV,
    DIM_IS_NEW_CAR,
    DIM_IS_TRANSFER,
    DIM_IS_RENEWAL,
]

# 按 key 索引（O(1) 查找）
DIMENSIONS_BY_KEY: dict[str, DrillDimension] = {d.key: d for d in ALL_DIMENSIONS}

# 分组（与 PLAN §1 D1 一致）
ORG_DIMENSIONS = [DIM_TEAM, DIM_SALESMAN, DIM_ORG_LEVEL_3, DIM_CUSTOMER_CATEGORY]
BUSINESS_DIMENSIONS = [
    DIM_INSURANCE_TYPE, DIM_COVERAGE, DIM_IS_NEV,
    DIM_IS_NEW_CAR, DIM_IS_TRANSFER, DIM_IS_RENEWAL,
]


# ============== 工具函数 ==============

# 文件名安全字符：中英文、数字、连字符、下划线
_SAFE_BASENAME_RE = re.compile(r"[^\w一-鿿\-]")


def safe_basename(name: str, max_len: int = 30) -> str:
    """把任意字符串转为 URL/文件系统安全的 basename。

    规则：
      - 非法字符（路径分隔符 / 空白 / 标点）替换为 `_`
      - 截断到 max_len 字符
      - 空串退回 `unknown`

    用于 team/salesman 等动态维度值（运行时才知道）。
    """
    if not name or not name.strip():
        return "unknown"
    cleaned = _SAFE_BASENAME_RE.sub("_", name.strip())
    return cleaned[:max_len] if len(cleaned) > max_len else cleaned


def get_dimension(key: str) -> DrillDimension:
    """按 key 取 DrillDimension，缺失抛 KeyError（不静默兜底）。"""
    if key not in DIMENSIONS_BY_KEY:
        raise KeyError(
            f"未知下钻维度: {key!r}; 可用键: {sorted(DIMENSIONS_BY_KEY)}"
        )
    return DIMENSIONS_BY_KEY[key]


def all_grouping_keys() -> list[str]:
    """返回 GROUPING SETS 所需的全部维度键序列。"""
    return [d.key for d in ALL_DIMENSIONS]


# ============== 启动断言（防止维护漂移）==============

# 1. key 唯一
assert len({d.key for d in ALL_DIMENSIONS}) == len(ALL_DIMENSIONS), \
    "ALL_DIMENSIONS 存在重复 key"

# 2. 静态值集合中 basename 在维内唯一
for _d in ALL_DIMENSIONS:
    if _d.values:
        _basenames = [v.basename for v in _d.values]
        assert len(set(_basenames)) == len(_basenames), \
            f"维度 {_d.key} 的 basename 重复: {_basenames}"

# 3. 10 维与 PLAN §1 D1 一致（org_level_3 为分公司层维度，2026-05-29 新增）
_EXPECTED_KEYS = {
    "team", "salesman", "org_level_3", "customer_category",
    "insurance_type", "coverage_combination",
    "is_nev", "is_new_car", "is_transfer", "is_renewal",
}
assert set(DIMENSIONS_BY_KEY) == _EXPECTED_KEYS, \
    f"维度集合与 PLAN §1 D1 不一致: 多 {set(DIMENSIONS_BY_KEY) - _EXPECTED_KEYS}, 缺 {_EXPECTED_KEYS - set(DIMENSIONS_BY_KEY)}"
