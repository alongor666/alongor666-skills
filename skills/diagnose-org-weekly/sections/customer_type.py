"""板块 2：分客户类型（变动成本率异常自动下钻独立页）。

取数：
  - fetch_customer_breakdown(con, org, time_field, end)
      按 customer_category 分组的 YTD 8 指标 + 同比保费增长 + 续保率 + 占比
  - fetch_customer_drilldown_at(con, org, customer_category, time_field, end, total_premium)
      单类别 × 单截止日的 9 个细节（含变动成本率/出险率/出险频度/案均赔款/自主系数）

触发：变动成本率 alert ∈ {yellow, red} 的客户类型 → 自动生成 page-drill-* 独立页
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from lib import (
    render_card, render_table, render_weekly_table, render_problem_narrative,
    standard_query, POLICY_GLOB, CLAIMS_GLOB, RENEWAL_PARQUET,
    short_label,
)
from lib.alerts import light
from lib.page_ids import drill_page_id


def fetch_customer_breakdown(con, org, time_field, end):
    """按客户类型分组的 8 列指标 DataFrame。

    YTD 至 end，自动叠加：
      - 当前 YTD 8 指标（standard_query 走 customer_category 分组）
      - 去年同期 YTD 保费（用于增长率分母）
      - renewal_tracker 续保率（VIN 去重，应续口径排除摩托）
      - 占比（该类保费 ÷ 全部客户类型合计）

    返回 DataFrame 列：
      dim, policy_count, premium, share_pct, premium_growth_pct,
      variable_cost_ratio_pct, expense_ratio_pct, earned_loss_ratio_pct,
      avg_claim, renewal_rate_pct
    """
    year_start = date(end.year, 1, 1)

    # 1) 当前 YTD 各客户类型 8 指标
    where_curr = f"org_level_3=? AND {time_field} BETWEEN ? AND ?"
    df_curr = standard_query(
        con, where_clause=where_curr,
        params=[org, year_start.isoformat(), end.isoformat()],
        cutoff=end.isoformat(),
        extra_fields=["customer_category"],
        dim_expr="customer_category",
        order="premium DESC NULLS LAST",
    )

    # 2) 去年同期 YTD 保费（增长率分母）
    base_end = end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29) \
                else end.replace(year=end.year - 1, day=28)
    base_start = date(base_end.year, 1, 1)
    df_base = standard_query(
        con, where_clause=where_curr,
        params=[org, base_start.isoformat(), base_end.isoformat()],
        cutoff=base_end.isoformat(),
        extra_fields=["customer_category"],
        dim_expr="customer_category",
        order="premium DESC NULLS LAST",
    )[["dim", "premium"]].rename(columns={"premium": "base_premium"})

    # 3) 续保率 by customer_category
    sql_renewal = f"""
    SELECT
      customer_category AS dim,
      100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? THEN vehicle_frame_no END)
            / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS renewal_rate_pct
    FROM read_parquet('{RENEWAL_PARQUET}')
    WHERE org_level_3=?
      AND expected_expiry_date >= DATE '{end.year}-01-01'
      AND expected_expiry_date <= ?
    GROUP BY customer_category
    """
    df_renewal = con.execute(sql_renewal,
                             [end.isoformat(), org, end.isoformat()]).df()

    # 4) merge + 计算占比 + 增长率
    df = df_curr.merge(df_base, on="dim", how="left") \
                .merge(df_renewal, on="dim", how="left")
    total = df["premium"].sum() or 0
    df["share_pct"] = df["premium"] * 100.0 / total if total > 0 else 0
    df["premium_growth_pct"] = df.apply(
        lambda r: ((r["premium"] - r["base_premium"]) * 100.0 / r["base_premium"])
                  if r.get("base_premium") and r["base_premium"] > 0 else None,
        axis=1,
    )

    # 5) 合计行（不分组重新跑 standard_query，率值率均按 SUM 重算非加权）
    df_total_curr = standard_query(
        con, where_clause=where_curr,
        params=[org, year_start.isoformat(), end.isoformat()],
        cutoff=end.isoformat(),
    )
    df_total_base = standard_query(
        con, where_clause=where_curr,
        params=[org, base_start.isoformat(), base_end.isoformat()],
        cutoff=base_end.isoformat(),
    )
    sql_total_renewal = f"""
    SELECT
      100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? THEN vehicle_frame_no END)
            / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS renewal_rate_pct
    FROM read_parquet('{RENEWAL_PARQUET}')
    WHERE org_level_3=?
      AND expected_expiry_date >= DATE '{end.year}-01-01'
      AND expected_expiry_date <= ?
    """
    total_renewal = con.execute(sql_total_renewal,
                                [end.isoformat(), org, end.isoformat()]).fetchone()
    tcr = df_total_curr.iloc[0]
    tb_premium = df_total_base.iloc[0]["premium"] if not df_total_base.empty else 0
    total_growth = ((tcr["premium"] - tb_premium) * 100.0 / tb_premium) if tb_premium > 0 else None
    total_row = pd.DataFrame([{
        "dim": "合计",
        "policy_count": int(tcr["policy_count"]),
        "premium": tcr["premium"],
        "share_pct": 100.0,
        "premium_growth_pct": total_growth,
        "variable_cost_ratio_pct": tcr["variable_cost_ratio_pct"],
        "expense_ratio_pct": tcr["expense_ratio_pct"],
        "earned_loss_ratio_pct": tcr["earned_loss_ratio_pct"],
        "avg_claim": tcr.get("avg_claim"),
        "renewal_rate_pct": total_renewal[0] if total_renewal else None,
    }])
    out = pd.concat([total_row, df], ignore_index=True)
    return out[[
        "dim", "policy_count", "premium",
        "share_pct", "premium_growth_pct",
        "variable_cost_ratio_pct", "expense_ratio_pct", "earned_loss_ratio_pct",
        "avg_claim", "renewal_rate_pct",
    ]]


def fetch_customer_drilldown_at(con, org, customer_category, time_field, end, total_premium):
    """单客户类型 × 单 YTD 截至日的 8 个细节指标。

    返回 dict {indicator_key: value}，含：
      premium / share_pct / policy_count / variable_cost_ratio_pct
      / earned_loss_freq_pct / incident_freq_pct / claim_count / pricing_coeff
      / avg_claim
    """
    year_start = date(end.year, 1, 1)
    sql = f"""
    WITH filtered AS (
      SELECT * FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
      WHERE org_level_3=? AND customer_category=?
        AND {time_field} BETWEEN ? AND ?
        AND insurance_start_date IS NOT NULL
    ),
    policy_dedup AS (
      SELECT
        policy_no,
        CAST(insurance_start_date AS DATE) AS sd,
        SUM(premium) AS premium,
        SUM(COALESCE(fee_amount, 0)) AS fee_amount,
        AVG(commercial_pricing_factor) AS coef
      FROM filtered
      GROUP BY policy_no, CAST(insurance_start_date AS DATE)
      HAVING SUM(premium) > 0
    ),
    claims_agg AS (
      -- 口径对齐项目 SSOT ClaimsAgg + 多窗口出险锚点（基准见 chexian-report-shell/lib/queries.py）
      SELECT
        policy_no,
        COUNT(DISTINCT claim_no) AS claim_cases,
        SUM(CASE
              WHEN COALESCE(liability_ratio, 100) > 0
               AND (case_type IS NULL OR case_type NOT IN ('零结', '注销', '拒赔'))
              THEN (CASE WHEN settlement_time IS NOT NULL THEN COALESCE(settled_amount, 0)
                         ELSE COALESCE(reserve_amount, 0) END)
              ELSE 0
            END) AS reported_claims
      FROM read_parquet('{CLAIMS_GLOB}', union_by_name=true)
      WHERE policy_no IS NOT NULL
        AND CAST(accident_time AS DATE) <= DATE '{end.isoformat()}'
      GROUP BY policy_no
    ),
    e AS (
      SELECT
        p.policy_no, p.sd, p.premium, p.fee_amount, p.coef,
        DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR) AS policy_term,
        LEAST(GREATEST(DATEDIFF('day', p.sd, DATE '{end.isoformat()}'), 0),
              DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR)) AS earned_days,
        COALESCE(c.claim_cases, 0) AS claim_cases,
        COALESCE(c.reported_claims, 0) AS reported_claims
      FROM policy_dedup p
      LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
    )
    SELECT
      SUM(premium) AS premium,
      COUNT(DISTINCT policy_no) AS policy_count,
      SUM(claim_cases) AS claim_count,
      CASE WHEN SUM(premium * earned_days::DOUBLE / policy_term::DOUBLE) > 0 AND SUM(premium) > 0
           THEN SUM(reported_claims) * 100.0 / SUM(premium * earned_days::DOUBLE / policy_term::DOUBLE)
              + SUM(fee_amount) * 100.0 / SUM(premium)
           ELSE NULL END AS variable_cost_ratio_pct,
      CASE WHEN SUM(earned_days) > 0
           THEN SUM(claim_cases) * 365.0 / SUM(earned_days) * 100
           ELSE NULL END AS earned_loss_freq_pct,
      CASE WHEN COUNT(DISTINCT policy_no) > 0
           THEN SUM(claim_cases) * 100.0 / COUNT(DISTINCT policy_no)
           ELSE NULL END AS incident_freq_pct,
      CASE WHEN SUM(premium) > 0
           THEN SUM(premium * COALESCE(coef, 1)) / SUM(premium)
           ELSE NULL END AS pricing_coeff,
      CASE WHEN SUM(claim_cases) > 0
           THEN SUM(reported_claims) / CAST(SUM(claim_cases) AS DOUBLE)
           ELSE NULL END AS avg_claim
    FROM e
    """
    r = con.execute(sql, [org, customer_category, year_start.isoformat(), end.isoformat()]).fetchone()
    p = r[0] or 0
    return {
        "premium":                  p,
        "policy_count":             int(r[1] or 0),
        "claim_count":              int(r[2] or 0),
        "variable_cost_ratio_pct":  r[3],
        "earned_loss_freq_pct":     r[4],
        "incident_freq_pct":        r[5],
        "pricing_coeff":            r[6],
        "avg_claim":                r[7],
        "share_pct":                (p * 100.0 / total_premium) if total_premium and total_premium > 0 else None,
    }


# 表头/指标名一律从 SHORT_LABEL 派生（v1.18 唯一事实源）
HEADERS_CUSTOMER = [
    ("dim",                       short_label("dim_customer_type"),        "left", None,     None),
    ("premium",                   short_label("premium"),                  "num",  "wan",    None),
    ("share_pct",                 short_label("share_pct"),                "num",  "pct",    None),
    ("premium_growth_pct",        short_label("premium_growth_pct"),       "num",  "pct",    None),
    ("variable_cost_ratio_pct",   short_label("variable_cost_ratio_pct"),  "num",  "pct",    None),
    ("expense_ratio_pct",         short_label("expense_ratio_pct"),        "num",  "pct",    None),
    ("earned_loss_ratio_pct",     short_label("earned_loss_ratio_pct"),    "num",  "pct",    None),
    ("avg_claim",                 short_label("avg_claim"),                "num",  "money0", None),
    ("renewal_rate_pct",          short_label("renewal_rate_pct"),         "num",  "pct",    None),
]

DRILL_INDICATORS = [
    (short_label("premium"),                  "premium",                  None,                       "wan"),
    (short_label("share_pct"),                "share_pct",                None,                       "pct"),
    (short_label("policy_count"),             "policy_count",             None,                       "int"),
    (short_label("variable_cost_ratio_pct"),  "variable_cost_ratio_pct",  "variable_cost_ratio_pct",  "pct"),
    (short_label("earned_loss_freq_pct"),     "earned_loss_freq_pct",     "earned_loss_freq_pct",     "pct"),
    (short_label("incident_freq_pct"),        "incident_freq_pct",        None,                       "pct"),
    (short_label("claim_count"),              "claim_count",              None,                       "int"),
    (short_label("avg_claim"),                "avg_claim",                None,                       "money0"),
    (short_label("pricing_coeff"),            "pricing_coeff",            None,                       "coef"),
]


def build(con, ctx) -> tuple[str, list, dict]:
    """渲染板块 2，返回 (card_html, drill_pages, nav_entry)。"""
    org = ctx.org
    time_field = ctx.time_field
    cutoff_date = ctx.cutoff
    windows = ctx.windows
    time_labels = ctx.time_labels
    total_premiums = ctx.total_premiums

    print(">> 第 2 板块：分客户类型...")
    df_cust = fetch_customer_breakdown(con, org, time_field, cutoff_date)

    # 第 2 板块的问题诊断（按 3 类问题切片）
    cust_problem_narrative = render_problem_narrative(
        df_cust,
        checks=[
            ("variable_cost_ratio_pct", f"{short_label('variable_cost_ratio_pct')}超线", {"alert-yellow", "alert-red"}),
            ("premium_growth_pct",      f"{short_label('premium_growth_pct')}严重滞后", {"alert-yellow", "alert-red"}),
            ("renewal_rate_pct",        f"{short_label('renewal_rate_pct')}不足",       {"alert-yellow", "alert-red"}),
        ],
    )

    # v1.19：回归 SPA showPage 模式 — 每行 dim → page_id（与 drill_pages section id 对齐）
    # df_cust.dim 与 drill_long_df.dim_value 同源（standard_query 的 customer_category 原值）
    targets = {}
    for _, row in df_cust.iterrows():
        cust_name = row["dim"]
        if cust_name == "合计":
            continue
        targets[cust_name] = drill_page_id("customer_category", cust_name)

    cust_table_html = render_table(
        df_cust, dim_label=short_label("dim_customer_type"), headers=HEADERS_CUSTOMER,
        drilldown_target_by_dim=targets,
    )
    card = render_card(
        "分客户类型",
        "",  # v1.11：副标题留空
        cust_problem_narrative + cust_table_html,
        card_id="section-customer-type",
    )

    return card, [], {"anchor": "section-customer-type", "label": "分客户类型"}
