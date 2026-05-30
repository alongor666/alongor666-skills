"""render 子包 — 按组件拆分，此文件 re-export 所有公开符号，保持向后兼容。

兼容路径（三条均有效）：
  from lib import render_page                 # 经 lib/__init__.py 转发
  from lib.render import render_page          # 本文件 re-export
  from lib.render.page import render_page     # 直接引用子模块
"""
from .table import render_table, HEADERS_8METRIC
from .card import render_card, render_callout, render_rule
from .weekly import render_weekly_table, sparkline
from .narrative import render_metric_narrative, render_problem_narrative, render_red_flag
from .threshold import render_threshold_table, render_threshold_card
from .status import render_status_bar
from .page import render_page
from .dashboard import (
    render_topbar, render_rail, render_kpi_strip,
    render_anomaly_grid, render_section_detail,
    AnomalyCard, SectionDetail,
)
from .deck import (
    trend_svg, scatter_svg,
    render_toolbar, render_cover, render_chapter,
    render_kpi_strip as render_kpi_strip_deck,
    render_resp_cards, render_watchlist, render_apx_table,
    DECK_CSS,
    TrendPoint, ScatterPoint, KpiCell, RespCard, WatchItem, ApTableRow,
)
from .supertable import (
    SUPERTABLE_CSS, SUPERTABLE_JS,
    render_topbar as render_topbar_supertable,
    render_controls, render_footer, render_table_shell,
)

__all__ = [
    "render_table", "HEADERS_8METRIC",
    "render_card", "render_callout", "render_rule",
    "render_weekly_table", "sparkline",
    "render_metric_narrative", "render_problem_narrative", "render_red_flag",
    "render_threshold_table", "render_threshold_card",
    "render_status_bar",
    "render_page",
    # v1.21 新增（P4 驾驶舱布局）
    "render_topbar", "render_rail", "render_kpi_strip",
    "render_anomaly_grid", "render_section_detail",
    "AnomalyCard", "SectionDetail",
    # v1.21 新增（P5 叙事周报布局）
    "trend_svg", "scatter_svg",
    "render_toolbar", "render_cover", "render_chapter",
    "render_resp_cards", "render_watchlist", "render_apx_table",
    "DECK_CSS",
    "TrendPoint", "ScatterPoint", "KpiCell", "RespCard", "WatchItem", "ApTableRow",
    # v1.21 新增（P6 超表）
    "SUPERTABLE_CSS", "SUPERTABLE_JS",
    "render_controls", "render_footer", "render_table_shell",
]
