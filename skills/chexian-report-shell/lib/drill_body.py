"""下钻页 body 生成器（v1.19 新增）。

每个 (dim_key, dim_value) 对应一个下钻页，body 内含：
  1. 该值的 9 KPI × 5 时间窗（横切自 ctx.drill_long_df）
  2. 该值下的 6 业务属性 6 卡（其他 5 维 + 自身值的 customer_category 拆解）

借鉴 diagnose-period-trend/lib/render.py:render_drill_overview 的 drill-toc 视觉，
但这里只走 ctx.drill_long_df 共享数据，不再额外发 SQL。

设计约束：
  - 不与外部 standard_query 二次取数（性能 / 单次取数原则）
  - 表头 / 卡片标题 / 颜色与主页保持一致（复用 render_table / render_card）
  - 维度内部排序遵循 DrillDimension.values 顺序，动态维（team/salesman）按保费倒序
"""
from __future__ import annotations

from typing import Optional
from html import escape

import pandas as pd

from .dimensions import (
    DrillDimension, get_dimension,
    BUSINESS_DIMENSIONS, DIM_CUSTOMER_CATEGORY,
)
from .labels import short_label
from .render import render_card, render_table, render_weekly_table
from .page_ids import drill_page_id


# 5 时间窗 × 单维单值的 9 指标小表头
KPI_METRICS_SPEC = [
    ("policy_count",             "int",    None),
    ("premium",                  "wan",    None),
    ("variable_cost_ratio_pct",  "pct",    "variable_cost_ratio_pct"),
    ("expense_ratio_pct",        "pct",    "expense_ratio_pct"),
    ("earned_loss_ratio_pct",    "pct",    "earned_loss_ratio_pct"),
    ("earned_loss_freq_pct",     "pct",    "earned_loss_freq_pct"),
    ("avg_claim",                "money0", None),
]


HEADERS_DRILL_DIM = [
    ("dim",                      "",                                       "left", None,     None),
    ("policy_count",             short_label("policy_count"),              "num",  "int",    None),
    ("premium",                  short_label("premium"),                   "num",  "wan",    None),
    ("variable_cost_ratio_pct",  short_label("variable_cost_ratio_pct"),   "num",  "pct",    None),
    ("expense_ratio_pct",        short_label("expense_ratio_pct"),         "num",  "pct",    None),
    ("earned_loss_ratio_pct",    short_label("earned_loss_ratio_pct"),     "num",  "pct",    None),
    ("earned_loss_freq_pct",     short_label("earned_loss_freq_pct"),      "num",  "pct",    None),
    ("avg_claim",                short_label("avg_claim"),                 "num",  "money0", None),
]


def _value_display(dim: DrillDimension, sql_value: str) -> str:
    """SQL 原值 → 展示名（如 '非营业个人客车' → '家自车'）。"""
    if dim.values:
        for v in dim.values:
            if v.sql_value == sql_value:
                return v.display
    return sql_value


def _kpi_table_html(df_long: pd.DataFrame, dim_key: str, dim_value: str,
                    time_labels: list[str], periods_labels: list[str]) -> str:
    """该 (dim_key, dim_value) 在 5 个时间窗的 7 项 KPI 矩阵（render_weekly_table）。

    Args:
      df_long: ctx.drill_long_df
      dim_key/dim_value: 切片键
      time_labels: 完整列头（如 "上季度 03-31"），与主页一致
      periods_labels: 原始 period 名（"上季度" / ... / "当周"），与 df_long.period 同
    """
    sub = df_long[
        (df_long["dim_key"] == dim_key) & (df_long["dim_value"] == dim_value)
    ].set_index("period")
    if sub.empty:
        return '<p class="empty-data">该维度下该值无数据。</p>'

    max_n = 0
    for p in periods_labels:
        if p in sub.index:
            n = sub.loc[p].get("policy_count", 0)
            try:
                max_n = max(max_n, int(n) if pd.notna(n) else 0)
            except (TypeError, ValueError):
                pass

    metrics = []
    for metric_key, kind, alert_key in KPI_METRICS_SPEC:
        values = []
        for p in periods_labels:
            if p in sub.index and pd.notna(sub.loc[p].get(metric_key)):
                values.append(float(sub.loc[p][metric_key]))
            else:
                values.append(None)
        metrics.append({
            "name": short_label(metric_key),
            "metric_key": alert_key,
            "kind": kind,
            "values": values,
            "trend_values": values,
            "sample_n": max_n or 999,
            "placeholder": False,
        })
    return render_weekly_table(metrics, time_labels)


def _build_cross_dim_card(df_long: pd.DataFrame, other_dim: DrillDimension,
                          base_dim_key: str, base_dim_value: str,
                          last_period_label: str, card_id: str) -> str:
    """子维度交叉表卡片：在固定 base (dim_key=value) 切片下，按 other_dim 拆解。

    注意：drill_long_df 的设计是"主维度独立切片"——单条记录只含一个 dim_key 的切片。
    因此严格的 base ∩ other 交叉切片需要原始数据二次查询。
    本简化版在数据可用时直接展示 other_dim 在 last_period_label 的全机构横切，
    并在 subtitle 注明范围（不缩到 base）；后续 Phase 6 可补 SQL 升级精度。
    """
    sub = df_long[
        (df_long["dim_key"] == other_dim.key)
        & (df_long["period"] == last_period_label)
    ].copy()
    if sub.empty:
        body = f'<p class="empty-data">{last_period_label}口径下「{other_dim.short_label}」无数据。</p>'
        return render_card(other_dim.full_label, "", body, card_id=card_id)

    # 排序 + 展示名映射
    if other_dim.values:
        value_order = {v.sql_value: i for i, v in enumerate(other_dim.values)}
        display_map = {v.sql_value: v.display for v in other_dim.values}
        sub["__order"] = sub["dim_value"].map(
            lambda x: value_order.get(str(x), 999)
        )
        sub["dim"] = sub["dim_value"].map(
            lambda x: display_map.get(str(x), str(x))
        )
        sub = sub.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    else:
        sub["dim"] = sub["dim_value"].astype(str)
        sub = sub.sort_values("premium", ascending=False,
                              na_position="last").reset_index(drop=True)

    headers = list(HEADERS_DRILL_DIM)
    headers[0] = ("dim", other_dim.short_label, "left", None, None)

    table_html = render_table(sub, dim_label=other_dim.short_label, headers=headers)
    note = (
        f'<p class="callout callout-info" style="margin-bottom:8px;">'
        f'本卡为<strong>{last_period_label}口径</strong>下「{other_dim.short_label}」'
        f'全机构横切，<em>非</em> 与当前维度交叉切片。Phase 6 将补 SQL 升级为精确交叉。'
        f'</p>'
    )
    return render_card(other_dim.full_label, "", note + table_html, card_id=card_id)


def _drill_toc_html(nav_items: list[tuple[str, str]]) -> str:
    """下钻页内置 sticky TOC（借鉴 period-trend 的 drill-toc 视觉）。"""
    items = "".join(
        f'<li><a href="#{escape(sid)}" class="drill-toc-link" '
        f'data-target="{escape(sid)}">{escape(label)}</a></li>'
        for sid, label in nav_items
    )
    return (
        f'<nav class="drill-toc" aria-label="目录">'
        f'<div class="drill-toc-title">目录</div>'
        f'<ol>{items}</ol>'
        f'</nav>'
    )


def build_drill_body(dim_key: str, dim_value: str, ctx) -> tuple[str, str]:
    """生成下钻页 body html + 标题。

    Returns:
      (body_html, page_title)
        body_html — 直接喂给 render_page(drill_pages=[(page_id, title, body), ...])
        page_title — 用于 sub_toolbar 的 h2（如 "客户类别 · 家自车"）
    """
    dim = get_dimension(dim_key)
    df_long = getattr(ctx, "drill_long_df", None)
    if df_long is None or df_long.empty:
        return ('<p class="empty-data">下钻数据未初始化。</p>',
                f"{dim.short_label} · {dim_value}")

    display_value = _value_display(dim, dim_value)
    page_title = f"{dim.short_label} · {display_value}"

    periods_labels = [w[0] for w in ctx.windows]
    last_period_label = periods_labels[-1] if periods_labels else "当周"

    # ── Card 1：9 KPI × 5 时间窗 ──
    kpi_html = _kpi_table_html(
        df_long, dim_key, dim_value, ctx.time_labels, periods_labels,
    )
    card_kpi_id = f"drill-kpi-{dim.key}"
    card_kpi = render_card(
        f"{display_value} · 经营指标矩阵",
        f"{dim.full_label}={display_value} · 5 时间窗 YTD 累计",
        kpi_html,
        card_id=card_kpi_id,
    )

    nav_items: list[tuple[str, str]] = [(card_kpi_id, "经营指标矩阵")]

    # ── Card 2：客户类别拆解（若当前维度不是 customer_category） ──
    extra_cards = []
    if dim_key != DIM_CUSTOMER_CATEGORY.key:
        card_cc_id = f"drill-cc-{dim.key}"
        extra_cards.append(_build_cross_dim_card(
            df_long, DIM_CUSTOMER_CATEGORY,
            dim_key, dim_value, last_period_label, card_cc_id,
        ))
        nav_items.append((card_cc_id, DIM_CUSTOMER_CATEGORY.short_label))

    # ── Cards 3-8：6 业务属性 6 卡（跳过自身） ──
    for biz_dim in BUSINESS_DIMENSIONS:
        if biz_dim.key == dim_key:
            continue
        card_id = f"drill-biz-{biz_dim.key}-{dim.key}"
        extra_cards.append(_build_cross_dim_card(
            df_long, biz_dim, dim_key, dim_value, last_period_label, card_id,
        ))
        nav_items.append((card_id, biz_dim.short_label))

    cards_html = card_kpi + "".join(extra_cards)
    toc_html = _drill_toc_html(nav_items)

    body = (
        f'<div class="drill-layout">'
        f'{toc_html}'
        f'<div class="drill-main">{cards_html}</div>'
        f'</div>'
    )
    return body, page_title


def build_all_drill_pages(ctx) -> list[tuple[str, str, str]]:
    """为 ctx.drill_long_df 中出现的全部 (dim_key, dim_value) 对生成 drill_pages list。

    Returns:
      [(page_id, page_title, body_html), ...] 供 render_page(drill_pages=...) 使用
    """
    df_long = getattr(ctx, "drill_long_df", None)
    if df_long is None or df_long.empty:
        return []

    last_period_label = ctx.windows[-1][0] if ctx.windows else "当周"
    # 只取 last_period 出现过的 (dim_key, dim_value)；其他周期共享数据由 _kpi_table_html 取
    seen = df_long[df_long["period"] == last_period_label][["dim_key", "dim_value"]] \
        .drop_duplicates().values.tolist()

    pages: list[tuple[str, str, str]] = []
    for dim_key, dim_value in seen:
        body, title = build_drill_body(dim_key, str(dim_value), ctx)
        pid = drill_page_id(dim_key, dim_value)
        pages.append((pid, title, body))
    return pages
