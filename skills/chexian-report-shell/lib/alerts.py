"""四级亮灯阈值与判定函数（分公司经营口径，独立事实源）。

历史背景：
  v1.5 之前 TH 字典与项目 diagnose_common.py 严格 sync。
  v1.6（2026-05-13）起，本技能脱离项目源独立维护，因为：
    - 项目源是全国/总公司口径
    - 分公司经营口径需要更紧的阈值（如固定经营成本约 7 个点，
      变动成本率从 (85,91,94) 收紧为 (84,89,93)）
    - 综合成本率从 (99,101,105) 调整为 (91,96,100)
  contract.assert_threshold_in_sync 仅作"参考性差异提示"，不再阻断。

最近修订：2026-05-13（用户决策："这是最新最准的规则"）
"""

from typing import Optional, Tuple

import pandas as pd

# 四级亮灯阈值表 (关注, 预警, 危险) — 分公司经营口径
# 越高越差的指标：(优秀线, 健康线, 异常线) → val>异常线 红 / >健康线 黄 / >优秀线 蓝 / 否则 绿
# 越低越差的指标：(优秀线, 健康线, 异常线) → val<异常线 红 / <健康线 黄 / <优秀线 蓝 / 否则 绿
TH: dict[str, tuple[float, float, float]] = {
    "earned_loss_freq_pct":     (8, 10, 12),
    "earned_loss_ratio_pct":    (60, 70, 75),
    "variable_cost_ratio_pct":  (84, 89, 93),       # v1.6 改：分公司含固定成本 7pt
    "combined_cost_ratio_pct":  (91, 96, 100),      # v1.6 改：分公司经营底线
    "edge_contribution_pct":    (15, 9, 6),
    "avg_claim_cargo":          (8000, 10000, 12000),
    # v1.7 新增（用户决策 2026-05-13）：
    "premium_growth_pct":       (10, 5, 2),         # 同比保费增长率：≥10 优 / 5-10 健 / 2-5 异 / <2 险
    "plan_completion_pct":      (110, 100, 95),     # 计划达成率（含时间进度）：≥110 优 / 100-110 健 / 95-100 异 / <95 险
    "household_share_pct":      (70, 65, 60),       # 家自车占比：≥70 优 / 65-70 健 / 60-65 异 / <60 险
    # v1.9 新增（用户决策 2026-05-13）：
    "expense_ratio_pct":        (15, 16, 16.5),     # 费用率（越高越差）：≤15 优 / 15-16 健 / 16-16.5 异 / >16.5 险
                                                    # 刚性约束：综合费用率 > 25% 即停业 10 天 → 费用率 ≤ 25% − 7% − 1.5% = 16.5%
    "cross_sell_completion_pct": (110, 100, 95),    # 交叉销售达成率（越低越差）：与计划达成率同语义
    "renewal_rate_pct":          (65, 60, 55),      # 商业险续保率（越低越差）：≥65 优 / 60-65 健 / 55-60 异 / <55 险
}

# 越低越差的指标白名单（其余默认越高越差）
LOWER_WORSE = {
    "edge_contribution_pct",
    "premium_growth_pct",
    "plan_completion_pct",
    "household_share_pct",
    "cross_sell_completion_pct",
    "renewal_rate_pct",
}

# 参与打灯的指标集合
LIGHT_METRICS = set(TH.keys())

# 小样本阈值
SMALL_SAMPLE_N = 30

# 等级文字标签（全词，不省略）
LEVEL_LABEL = {
    "alert-green":  "优秀",
    "alert-blue":   "健康",
    "alert-yellow": "异常",
    "alert-red":    "危险",
    "alert-gray":   "样本不足",
}


def light(metric: str, val: Optional[float], n: int) -> Tuple[str, str]:
    """完全复刻 diagnose_common.py:light()。

    返回 (CSS 类名, 文字标签)：
      - alert-green / 优
      - alert-blue  / 良
      - alert-yellow/ 警
      - alert-red   / 险
      - alert-gray  / 样本不足
      - 空 / 空（缺值或非打灯指标）
    """
    if val is None or pd.isna(val):
        return "", ""
    if n < SMALL_SAMPLE_N:
        return "alert-gray", LEVEL_LABEL["alert-gray"]
    if metric not in TH:
        return "", ""

    notice, warn, danger = TH[metric]
    higher_worse = metric not in LOWER_WORSE

    if higher_worse:
        if val > danger: cls = "alert-red"
        elif val > warn:   cls = "alert-yellow"
        elif val > notice: cls = "alert-blue"
        else:              cls = "alert-green"
    else:
        if val < danger: cls = "alert-red"
        elif val < warn:   cls = "alert-yellow"
        elif val < notice: cls = "alert-blue"
        else:              cls = "alert-green"

    return cls, LEVEL_LABEL[cls]


# 阈值对照表数据（结构化，render 层用它生成对照仪表盘）
# v1.6：每行新增 metric_key（与 TH 字典 / SQL 字段对应）和 formula、scope（口径），便于按白名单过滤渲染
THRESHOLD_TABLE_ROWS: list[dict] = [
    {
        "metric_key": "earned_loss_ratio_pct",
        "name": "满期赔付率",
        "优": "≤60", "良": "60-70", "警": "70-75", "险": ">75",
        "unit": "%", "direction": "越高越差",
        "formula": "已报告赔款合计 × 100 ÷ 满期保费合计",
        "scope":   "满期口径；满期保费 = 保费 × 满期天数 ÷ 保险期限天数（闰年感知）",
    },
    {
        "metric_key": "variable_cost_ratio_pct",
        "name": "变动成本率",
        "优": "≤84", "良": "84-89", "警": "89-93", "险": ">93",
        "unit": "%", "direction": "越高越差",
        "formula": "满期赔付率 + 费用率",
        "scope":   "分公司专用阈值（综合成本率底线 100% − 固定经营成本 7pt = 变动成本率 93%）",
    },
    {
        "metric_key": "combined_cost_ratio_pct",
        "name": "综合成本率",
        "优": "≤91", "良": "91-96", "警": "96-100", "险": "≥100",
        "unit": "%", "direction": "越高越差",
        "formula": "综合费用率 + 综合赔付率",
        "scope":   "派生指标，无总公司刚性约束；≥100 即承保亏损（仅经验阈值，非刚性）",
    },
    {
        "metric_key": "earned_loss_freq_pct",
        "name": "满期出险率",
        "优": "≤8", "良": "8-10", "警": "10-12", "险": ">12",
        "unit": "%", "direction": "越高越差",
        "formula": "赔案件数合计 × 365 ÷ 满期天数合计 × 100",
        "scope":   "年化口径；不年化会因未满期被严重低估",
    },
    {
        "metric_key": "edge_contribution_pct",
        "name": "边际贡献率",
        "优": "≥15", "良": "9-15", "警": "6-9", "险": "<6",
        "unit": "%", "direction": "越低越差",
        "formula": "(满期保费 − 已报告赔款 − 费用金额) × 100 ÷ 签单保费",
        "scope":   "分公司视角下的可调节贡献（不含固定经营成本）",
    },
    {
        "metric_key": "avg_claim_cargo",
        "name": "案均赔款·货车",
        "优": "≤8,000", "良": "8,000-10,000", "警": "10,000-12,000", "险": ">12,000",
        "unit": "元", "direction": "越高越差",
        "formula": "已报告赔款合计 ÷ 赔案件数",
        "scope":   "仅货车单独管控，其他车型不打灯",
    },
    {
        "metric_key": "premium_growth_pct",
        "name": "保费增长率",
        "优": "≥10", "良": "5-10", "警": "2-5", "险": "<2",
        "unit": "%", "direction": "越低越差",
        "formula": "(本期签单保费 − 去年同期签单保费) × 100 ÷ 去年同期签单保费",
        "scope":   "同比口径（YoY）；YTD 列对比去年同 YTD",
    },
    {
        "metric_key": "plan_completion_pct",
        "name": "计划达成率",
        "优": "≥110", "良": "100-110", "警": "95-100", "险": "<95",
        "unit": "%", "direction": "越低越差",
        "formula": "实际签单保费 × 100 ÷ (年计划保费 × 时间进度)",
        "scope":   "时间进度 = day_of_year(end) ÷ 全年天数；100% 即按时间进度均匀达成",
    },
    {
        "metric_key": "household_share_pct",
        "name": "家自车占比",
        "优": "≥70", "良": "65-70", "警": "60-65", "险": "<60",
        "unit": "%", "direction": "越低越差",
        "formula": "客户类别为「非营业个人客车」的保单数 × 100 ÷ 全部保单数",
        "scope":   "结构性指标，反映业务质量底色（家自车赔付与续保表现普遍优于其他车型）",
    },
    {
        "metric_key": "expense_ratio_pct",
        "name": "费用率",
        "优": "≤15", "良": "15-16", "警": "16-16.5", "险": ">16.5",
        "unit": "%", "direction": "越高越差",
        "formula": "费用金额 × 100 ÷ 签单保费（保单明细域 fee_amount）",
        "scope":   "刚性约束：综合费用率 = 费用率 + 固定成本(7%) + 附加税费(1.5%)，"
                   "总公司规定 > 25% 即停止全省商业险业务 10 天，倒推费用率上限 16.5%",
    },
    {
        "metric_key": "cross_sell_completion_pct",
        "name": "交叉销售",
        "优": "≥110", "良": "100-110", "警": "95-100", "险": "<95",
        "unit": "%", "direction": "越低越差",
        "formula": "实际驾意保费 × 100 ÷ (年计划驾意保费 × 时间进度)",
        "scope":   "项目「交叉销售保费计划达成率」口径；本地以 plan_personal 替代 KpiPlanConfig.driver",
    },
    {
        "metric_key": "renewal_rate_pct",
        "name": "商业险续保率",
        "优": "≥65", "良": "60-65", "警": "55-60", "险": "<55",
        "unit": "%", "direction": "越低越差",
        "formula": "已续件数 × 100 ÷ 应续件数（VIN 去重）",
        "scope":   "项目「续保率」口径；应续 = 上年商业险起保 + 交商同保 − 摩托/挂车",
    },
]


def filter_threshold_rows(metric_keys: Optional[list] = None) -> list[dict]:
    """按指标白名单过滤阈值对照表（render_threshold_card 用）。

    Args:
      metric_keys: 想展示的 metric_key 列表；None 表示全部
    """
    if metric_keys is None:
        return THRESHOLD_TABLE_ROWS
    keep = set(metric_keys)
    return [r for r in THRESHOLD_TABLE_ROWS if r.get("metric_key") in keep]
