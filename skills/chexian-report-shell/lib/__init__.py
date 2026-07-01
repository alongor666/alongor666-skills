"""车险诊断报告 HTML 渲染共享库。

把任意 diagnose_* 脚本的 DataFrame 结果渲染成统一风格的 HTML 报告。
关键原则：
  - 4 级亮灯阈值取自项目 diagnose_common.py（手动同步，参 alerts.py 顶部注释）
  - 率值禁加权平均：调用方传入 DataFrame 时已应保证 SUM 聚合后重算
  - 全中文展示，禁出英文字段名（除已锁定的占位符 FEEDBACK_URL / __SOURCE_LABEL__）
"""

from .alerts import (
    light, TH, LIGHT_METRICS, LEVEL_LABEL,
    THRESHOLD_TABLE_ROWS, filter_threshold_rows, SMALL_SAMPLE_N,
)
from .format import (
    fmt_num, fmt_wan, fmt_pct, fmt_int,
    short_agent_name, short_salesman_name, short_team_name,
)
from .labels import (
    SHORT_LABEL, FULL_LABEL, short_label, full_label,
    SHORT_CATEGORY_LABEL, short_category_label,
)
from .render import (
    render_table, render_card, render_callout, render_rule, render_red_flag,
    render_weekly_table, render_metric_narrative, render_problem_narrative,
    render_threshold_card, render_threshold_table,
    render_status_bar,
    render_page, HEADERS_8METRIC,
    sparkline,
    # v1.21 新增
    render_topbar, render_rail, render_kpi_strip,
    render_anomaly_grid, render_section_detail,
    trend_svg, scatter_svg,
    render_toolbar, render_cover, render_chapter,
    render_resp_cards, render_watchlist, render_apx_table,
    DECK_CSS,
    SUPERTABLE_CSS, SUPERTABLE_JS,
    render_controls, render_footer, render_table_shell,
)
from .push import push_to_im
from .queries import (
    standard_query, auto_cutoff, build_base_cte, register_udfs,
    make_weekly_windows,
    DIM_EXPR, PRICE_BUCKETS, POLICY_GLOB, CLAIMS_GLOB,
)
from .report_queries import (
    claims_glob_for_branch,
    renewal_parquet_for_branch,
    policy_glob_for_branch,
    plan_parquet_for_branch,
    fetch_standard_window, fetch_household_share, fetch_premium_growth,
    fetch_renewal_rate, fetch_cross_sell_completion, fetch_plan_completion,
    fetch_team_salesman_periods,
    fetch_dim_growth_rates, fetch_renewal_by_dim,
    PLAN_PARQUET, RENEWAL_PARQUET, CROSS_SELL_PARQUET,
)
from .context import SectionContext
from .contract import validate_metrics_df, assert_threshold_in_sync, ContractError
from .dimensions import (
    DrillDimension, ValueDef,
    ALL_DIMENSIONS, DIMENSIONS_BY_KEY, ORG_DIMENSIONS, BUSINESS_DIMENSIONS,
    get_dimension, safe_basename, all_grouping_keys,
)
from .grouping_sets import (
    multi_dim_periods_query, pivot_for_drill, collect_extra_fields,
    DIMENSION_EXTRA_FIELDS,
)
from .drill_body import build_drill_body, build_all_drill_pages
from .page_ids import drill_page_id
from .time_windows import Period, build_periods, TREND_KEYS, WEEKLY_KEYS
from .anomaly_base import Anomaly, SEV_WEIGHT, rank_anomalies
from .anomaly_cross import (
    Anomaly as CrossAnomaly,
    compute_top_anomalies,
    build_drilldown_data,
    build_org_drilldown_data,
)
from .report_queries import fetch_org_cross_data, fetch_org_team_cross_data  # noqa: E402 (後補導出)
from .loader import load_shell
# 主题资源子模块显式导出（ADR-002）：themes_v2 已下沉本基座，作为 V1/V3/V4 三视图
# 共享 CSS token 的单一声明出口。消费者据各自 bootstrap 取 `dhr_lib.themes_v2`
# （period-trend）或 `lib.themes_v2`（org-weekly，cli.py 注入 SHELL_ROOT），均指向此处。
# themes_v2 零依赖（纯字符串常量 + 函数），eager 导入成本可忽略。
from . import themes_v2  # noqa: F401


def get_threshold(metric_key: str, index: int) -> float:
    """阈值单点入口（v1.20）：替代散落在各 skill 的 TH[...] 直接访问。

    Args:
        metric_key: TH 字典的键，如 "variable_cost_ratio_pct"
        index:      0 = 优秀线 / 1 = 健康线 / 2 = 危险线
                    （TH[key] 是三元组 (优秀线, 健康线, 危险线)）

    Returns:
        对应阈值（float）

    Raises:
        KeyError:   metric_key 不存在时
        IndexError: index 超出 0-2 范围时
    """
    from .alerts import TH
    return TH[metric_key][index]


__all__ = [
    "light", "TH", "LIGHT_METRICS", "LEVEL_LABEL",
    "THRESHOLD_TABLE_ROWS", "filter_threshold_rows", "SMALL_SAMPLE_N",
    "fmt_num", "fmt_wan", "fmt_pct", "fmt_int",
    "short_agent_name", "short_salesman_name", "short_team_name",
    "SHORT_LABEL", "FULL_LABEL", "short_label", "full_label",
    "SHORT_CATEGORY_LABEL", "short_category_label",
    "render_table", "render_card", "render_callout", "render_rule",
    "render_red_flag", "render_weekly_table", "render_metric_narrative",
    "render_problem_narrative", "render_threshold_card", "render_threshold_table",
    "render_status_bar",
    "render_page", "HEADERS_8METRIC",
    "push_to_im",
    "standard_query", "auto_cutoff", "build_base_cte", "register_udfs",
    "make_weekly_windows",
    "DIM_EXPR", "PRICE_BUCKETS", "POLICY_GLOB", "CLAIMS_GLOB",
    "claims_glob_for_branch",
    "renewal_parquet_for_branch",
    "policy_glob_for_branch",
    "plan_parquet_for_branch",
    "fetch_standard_window", "fetch_household_share", "fetch_premium_growth",
    "fetch_renewal_rate", "fetch_cross_sell_completion", "fetch_plan_completion",
    "fetch_team_salesman_periods",
    "fetch_dim_growth_rates", "fetch_renewal_by_dim",
    "PLAN_PARQUET", "RENEWAL_PARQUET", "CROSS_SELL_PARQUET",
    "SectionContext",
    "validate_metrics_df", "assert_threshold_in_sync", "ContractError",
    # v1.18 新增
    "DrillDimension", "ValueDef",
    "ALL_DIMENSIONS", "DIMENSIONS_BY_KEY", "ORG_DIMENSIONS", "BUSINESS_DIMENSIONS",
    "get_dimension", "safe_basename", "all_grouping_keys",
    "multi_dim_periods_query", "pivot_for_drill", "collect_extra_fields",
    "DIMENSION_EXTRA_FIELDS",
    # v1.19 SPA 模式
    "build_drill_body", "build_all_drill_pages", "drill_page_id",
    # v1.20 新增
    "Period", "build_periods", "TREND_KEYS", "WEEKLY_KEYS",
    "Anomaly", "SEV_WEIGHT", "rank_anomalies",
    # v1.21 新增（P3 跨维异常排名）
    "CrossAnomaly", "compute_top_anomalies", "build_drilldown_data",
    "build_org_drilldown_data", "fetch_org_cross_data", "fetch_org_team_cross_data",
    "load_shell", "get_threshold",
    # v1.21 新增（P2 sparkline 增强版）
    "sparkline",
    # v1.21 新增（P4 驾驶舱布局）
    "render_topbar", "render_rail", "render_kpi_strip",
    "render_anomaly_grid", "render_section_detail",
    # v1.21 新增（P5 叙事周报布局）
    "trend_svg", "scatter_svg",
    "render_toolbar", "render_cover", "render_chapter",
    "render_resp_cards", "render_watchlist", "render_apx_table",
    "DECK_CSS",
    # v1.21 新增（P6 超表）
    "SUPERTABLE_CSS", "SUPERTABLE_JS",
    "render_controls", "render_footer", "render_table_shell",
    # P1（ADR-002）：主题资源子模块下沉基座，显式导出
    "themes_v2",
]
