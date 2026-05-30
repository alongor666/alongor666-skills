"""字段中文名映射 — 唯一事实源（v1.18 新增）。

设计目的：
  把"机器键 → 中文展示名"集中在此文件，所有 sections/render 调用方通过
  short_label(key) / full_label(key) 间接取值，避免：
    1) 同一字段在多文件硬编码（如"满期赔付率"出现在 5 处）
    2) 简称错配（团队/团队简称/sales_team 三种说法混用）
    3) 表格列宽换行（"满期赔付率"5 字撑宽，改"赔付率"3 字即可）

设计原则：
  - SHORT_LABEL：表头 / chips / 窄列场景；越短越好但需保留专业性
  - FULL_LABEL：说明页 / 亮灯标准对照 / 公式段；保留全称便于教学
  - 缺 key 时退回 key 本身（不抛异常，便于增量演进）

新增字段：在两本字典同时登记即可（漏一个 KEY_INTEGRITY_CHECK 会断言失败）。
"""
from __future__ import annotations


# ============== 简称（窄列 / 表头 / chips）==============
SHORT_LABEL: dict[str, str] = {
    # 维度名（dim_<name>，render_table 的 dim_label 参数）
    "dim_sales_team":            "团队",
    "dim_customer_type":         "客户类型",
    "dim_agent":                 "经代",
    "dim_salesman":              "业务员",
    "dim_org":                   "机构",

    # 计数类
    "policy_count":              "保单数",
    "claim_count":               "案件数",

    # 金额类
    "premium":                   "保费",
    "reported_claims":           "已报赔款",
    "avg_claim":                 "案均",
    "per_policy_premium":        "件均",

    # 率值类
    "variable_cost_ratio_pct":   "变率",
    "earned_loss_ratio_pct":     "赔付率",
    "earned_loss_freq_pct":      "出险率",
    "expense_ratio_pct":         "费用率",
    "share_pct":                 "占比",
    "renewal_rate_pct":          "续保率",
    "plan_completion_pct":       "达成率",
    "premium_growth_pct":        "增长率",
    "household_share_pct":       "家自占比",
    "cross_sell_completion_pct": "交叉销售",
    "combined_cost_ratio_pct":   "综合成本率",
    "edge_contribution_pct":     "边际贡献率",

    # 频度类
    "incident_freq_pct":         "出险频度",
    "pricing_coeff":             "自主系数",
}


# ============== 全称（说明页 / 亮灯对照 / 公式）==============
FULL_LABEL: dict[str, str] = {
    # 维度名
    "dim_sales_team":            "销售团队",
    "dim_customer_type":         "客户类型",
    "dim_agent":                 "经代",
    "dim_salesman":              "业务员",
    "dim_org":                   "三级机构",

    # 计数类
    "policy_count":              "保单件数",
    "claim_count":               "赔案件数",

    # 金额类
    "premium":                   "保费",
    "reported_claims":           "已报告赔款",
    "avg_claim":                 "案均赔款",
    "per_policy_premium":        "件均保费",

    # 率值类
    "variable_cost_ratio_pct":   "变动成本率",
    "earned_loss_ratio_pct":     "满期赔付率",
    "earned_loss_freq_pct":      "满期出险率(年化)",
    "expense_ratio_pct":         "费用率",
    "share_pct":                 "占比",
    "renewal_rate_pct":          "商业险续保率",
    "plan_completion_pct":       "计划达成率",
    "premium_growth_pct":        "保费增长率",
    "household_share_pct":       "家自车占比",
    "cross_sell_completion_pct": "交叉销售",
    "combined_cost_ratio_pct":   "综合成本率",
    "edge_contribution_pct":     "边际贡献率",

    # 频度类
    "incident_freq_pct":         "出险频度",
    "pricing_coeff":             "自主系数",
}


def short_label(key: str) -> str:
    """取窄列简称；缺 key 退回 key 本身。"""
    return SHORT_LABEL.get(key, key)


def full_label(key: str) -> str:
    """取说明全称；缺 key 退回 key 本身。"""
    return FULL_LABEL.get(key, key)


# ============== 一致性校验（运行时断言）==============
# 两本字典 key 必须完全一致，否则维护时容易遗漏其中一处
_SHORT_KEYS = set(SHORT_LABEL.keys())
_FULL_KEYS = set(FULL_LABEL.keys())
assert _SHORT_KEYS == _FULL_KEYS, (
    f"SHORT_LABEL 与 FULL_LABEL key 不一致："
    f"仅 SHORT 有 {_SHORT_KEYS - _FULL_KEYS}, "
    f"仅 FULL 有 {_FULL_KEYS - _SHORT_KEYS}"
)


# ============== 客户类别简称（独立维度，原散落于 diagnose-period-trend / diagnose-loss-development）==============
# 数据层用全名（SQL/DataFrame key/page_id hash 均不变），渲染层用简称（表头/链接/下钻页名）。
# 11 类对齐 src/shared/config/customer-categories.ts CUSTOMER_CATEGORIES_REGISTERED。
SHORT_CATEGORY_LABEL: dict[str, str] = {
    "非营业个人客车":   "家自车",
    "摩托车":           "摩托车",
    "非营业货车":       "非营货",
    "非营业企业客车":   "非营企",
    "营业货车":         "营货",
    "营业出租租赁":     "出租租赁",
    "特种车":           "特种车",
    "营业公路客运":     "公路客运",
    "挂车":             "挂车",
    "非营业机关客车":   "机关车",
    "营业城市公交":     "城市公交",
}


def short_category_label(name: str) -> str:
    """客户类别简称；缺 key 退回原名（不抛异常，便于增量演进）。"""
    return SHORT_CATEGORY_LABEL.get(name, name)
