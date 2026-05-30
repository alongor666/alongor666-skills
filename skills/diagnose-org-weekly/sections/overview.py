"""板块 1：经营指标概况（8 项核心 KPI × 5 时间窗口 + 趋势 sparkline）。

设计原则（用户决策 2026-05-13）：
  - 时间窗口 5 列：当周 / 上周 / 上上周 / 上月 / 上季度（均 YTD 累计，截至日不同）
  - 趋势 sparkline：5 个点按时序从早到晚连线
  - 9 项指标：变动成本率/费用率/满期赔付率/满期出险率/计划达成率/保费增长率
              /家自车占比/续保率/交叉销售
"""
from __future__ import annotations

import pandas as pd

from lib import (
    render_card, render_weekly_table, render_metric_narrative,
    fetch_household_share, fetch_premium_growth, fetch_plan_completion,
    fetch_renewal_rate, fetch_cross_sell_completion,
    short_label,
)


def build(con, ctx) -> tuple[str, list, dict]:
    """渲染板块 1，返回 (card_html, drill_pages, nav_entry)。"""
    org = ctx.org
    time_field = ctx.time_field
    windows = ctx.windows
    time_labels = ctx.time_labels
    standard_rows = ctx.standard_rows
    sample_n = ctx.sample_n

    def get(rows, col):
        return [(float(r[col]) if r is not None and pd.notna(r.get(col)) else None)
                for r in rows]

    variable_cost = get(standard_rows, "variable_cost_ratio_pct")
    earned_lr     = get(standard_rows, "earned_loss_ratio_pct")
    earned_freq   = get(standard_rows, "earned_loss_freq_pct")
    expense_ratio = get(standard_rows, "expense_ratio_pct")

    household_share = [fetch_household_share(con, org, time_field, s, e)
                       for _, s, e in windows]
    plan_completion = [fetch_plan_completion(con, org, time_field, s, e)
                       for _, s, e in windows]
    premium_growth  = [fetch_premium_growth(con, org, time_field, s, e)
                       for _, s, e in windows]
    renewal_rate    = [fetch_renewal_rate(con, org, e) for _, _, e in windows]
    cross_sell      = [fetch_cross_sell_completion(con, org, e) for _, _, e in windows]

    # v1.18：指标名一律从 SHORT_LABEL 派生（防止换行 + 与其他板块对齐）
    metrics_spec = [
        (short_label("variable_cost_ratio_pct"),    "variable_cost_ratio_pct",  "pct", variable_cost,   False),
        (short_label("expense_ratio_pct"),          "expense_ratio_pct",        "pct", expense_ratio,   False),
        (short_label("earned_loss_ratio_pct"),      "earned_loss_ratio_pct",    "pct", earned_lr,       False),
        (short_label("earned_loss_freq_pct"),       "earned_loss_freq_pct",     "pct", earned_freq,     False),
        (short_label("plan_completion_pct"),        "plan_completion_pct",      "pct", plan_completion, False),
        (short_label("premium_growth_pct"),         "premium_growth_pct",       "pct", premium_growth,  False),
        (short_label("household_share_pct"),        "household_share_pct",      "pct", household_share, False),
        (short_label("renewal_rate_pct"),           "renewal_rate_pct",         "pct", renewal_rate,    False),
        (short_label("cross_sell_completion_pct"),  "cross_sell_completion_pct","pct", cross_sell,      False),
    ]

    max_n = max(sample_n) if sample_n else 999
    metrics = []
    for name, mkey, kind, values, placeholder in metrics_spec:
        metrics.append({
            "name": name,
            "metric_key": mkey,
            "kind": kind,
            "values": values,
            "trend_values": values,
            "sample_n": max_n,
            "placeholder": placeholder,
        })

    weekly_table_html = render_weekly_table(metrics, time_labels)
    narrative_html = render_metric_narrative(metrics, time_labels)

    card = render_card(
        "经营指标概况",
        "",  # v1.11：副标题留空，所有说明迁至「说明」页
        narrative_html + weekly_table_html,
        card_id="section-overview",
    )

    return card, [], {"anchor": "section-overview", "label": "经营指标概况"}
