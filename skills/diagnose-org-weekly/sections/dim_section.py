"""单维 card 工厂（v1.19 新增）— 6 业务属性 + 客户类别共用。

替代 v1.18 的 business_attrs.py（一张大平表）。每维独立一个 card：
  - 表头：维度值 + 8 项核心指标（policy_count / premium / variable_cost_ratio /
    expense_ratio / earned_loss_ratio / earned_loss_freq / avg_claim）
  - 每行 dim 单元格 onclick="showPage('<page_id>')" 触发 SPA 切换
  - drill_pages 由 build_drill_body 在主入口外部一次性生成

设计原则：
  - 不重新跑 SQL：完全从 ctx.drill_long_df 切片，保证与主入口一次取数共享
  - 不渲染 problem_narrative（避免每个维度都有黄红 chip 的 chip 风暴；
    问题诊断聚焦在客户类型 / 销售团队两个主板块）
"""
from __future__ import annotations

import pandas as pd

from lib import (
    render_card, render_table, short_label,
    get_dimension, DrillDimension,
)
from lib.alerts import LOWER_WORSE
from lib.page_ids import drill_page_id


# 分维度卡默认排序指标:与 render_v1_org.py default_metric 对齐(变动成本率)
# VCR 不在 LOWER_WORSE 中 → 数值越高越差 → DESC 排序从差到好
DEFAULT_SORT_METRIC = "variable_cost_ratio_pct"


HEADERS_DIM = [
    ("dim",                      "",                                       "left", None,     None),
    ("policy_count",             short_label("policy_count"),              "num",  "int",    None),
    ("premium",                  short_label("premium"),                   "num",  "wan",    None),
    ("variable_cost_ratio_pct",  short_label("variable_cost_ratio_pct"),   "num",  "pct",    None),
    ("expense_ratio_pct",        short_label("expense_ratio_pct"),         "num",  "pct",    None),
    ("earned_loss_ratio_pct",    short_label("earned_loss_ratio_pct"),     "num",  "pct",    None),
    ("earned_loss_freq_pct",     short_label("earned_loss_freq_pct"),      "num",  "pct",    None),
    ("avg_claim",                short_label("avg_claim"),                 "num",  "money0", None),
]


def _slice_last_window(df_long: pd.DataFrame, dim: DrillDimension,
                       period_label: str) -> pd.DataFrame:
    """从长表抽出 dim 在 period_label 窗口的横切表，已按维度定义顺序排列。"""
    sub = df_long[
        (df_long["dim_key"] == dim.key) & (df_long["period"] == period_label)
    ].copy()
    if sub.empty:
        return sub

    # 把 sql_value → display 映射(枚举维度需保留 dim 显示名)
    if dim.values:
        display_map = {v.sql_value: v.display for v in dim.values}
        sub["dim"] = sub["dim_value"].map(
            lambda x: display_map.get(str(x), str(x))
        )
    else:
        sub["dim"] = sub["dim_value"].astype(str)

    # 统一按"所选指标 = 变动成本率"从差到好排序;
    # VCR 不在 LOWER_WORSE → DESC(数值越高越差);
    # 若 default_metric 改为 LOWER_WORSE 指标(如续保率) → ASC(数值越低越差)。
    asc = DEFAULT_SORT_METRIC in LOWER_WORSE
    if DEFAULT_SORT_METRIC in sub.columns:
        sub = sub.sort_values(DEFAULT_SORT_METRIC, ascending=asc,
                              na_position="last").reset_index(drop=True)
    else:
        # 兜底:列缺失则按保费倒序(避免抛异常,极少触发)
        sub = sub.sort_values("premium", ascending=False,
                              na_position="last").reset_index(drop=True)

    return sub


def build_dim_card(dim_key: str, ctx, *,
                   card_id_prefix: str = "section-dim") -> tuple[str, dict]:
    """生成单维 card 的 (html, nav_entry)。

    Args:
      dim_key: 维度键（must in DIMENSIONS_BY_KEY）
      ctx: SectionContext（含 drill_long_df 与 windows）
      card_id_prefix: card DOM id 前缀，最终 id = f"{prefix}-{dim_key}"

    Returns:
      (card_html, nav_entry)，nav_entry = {"anchor": card_id, "label": dim.short_label}
    """
    dim = get_dimension(dim_key)
    card_id = f"{card_id_prefix}-{dim.key}"
    nav = {"anchor": card_id, "label": dim.short_label}

    df_long = getattr(ctx, "drill_long_df", None)
    if df_long is None or df_long.empty:
        body = '<p class="empty-data">业务属性数据未初始化（需主入口启用 drill_long_df）。</p>'
        return render_card(dim.full_label, "", body, card_id=card_id), nav

    last_label = ctx.windows[-1][0] if ctx.windows else "当周"
    df = _slice_last_window(df_long, dim, last_label)

    if df.empty:
        body = f'<p class="empty-data">{last_label}口径下「{dim.short_label}」无数据。</p>'
        return render_card(dim.full_label, "", body, card_id=card_id), nav

    # 每行 dim_value → page_id；主入口侧 build_drill_pages 用同函数保持 id 一致
    targets = {row["dim"]: drill_page_id(dim.key, row["dim_value"])
               for _, row in df.iterrows()}

    headers = list(HEADERS_DIM)
    headers[0] = ("dim", dim.short_label, "left", None, None)

    table_html = render_table(
        df, dim_label=dim.short_label, headers=headers,
        drilldown_target_by_dim=targets,
    )
    card = render_card(
        dim.full_label,
        f"{last_label}口径 · 点击维度值进入下钻",
        table_html,
        card_id=card_id,
    )
    return card, nav
