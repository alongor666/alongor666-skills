"""板块 4：TOP N 业务员（N = min(15, 实际业务员数)，按保费 DESC）。

字段（与板块 3「分销售团队」一致）：
  业务员 / 保费 / 达成率 / 增长率 / 续保率 / 变率 / 赔付率 / 出险率 / 案均 / 案件数

数据源与口径：
  - policy.parquet：保费 + 满期类率值（按 short_salesman_name(salesman_name) 分组）
  - plan.parquet（level='salesman'）：达成率（plan_vehicle×10000/年/业务员 / 时间进度）
  - renewal_tracker.parquet：续保率（按 salesman_name 分组，UDF 双侧 normalize）
  - 增长率：同比 YTD policy.premium / 业务员

合计行不展示（TOP N 没有合计概念；机构合计已在板块 3 行 1 提供）。
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from lib import (
    render_card, render_table, render_problem_narrative,
    POLICY_GLOB, CLAIMS_GLOB, PLAN_PARQUET, RENEWAL_PARQUET,
    short_label,
)
from lib.queries import register_udfs


TOP_N_CAP = 15  # 最多展示前 15 名业务员；不足按实际


def _fetch_metrics_by_salesman(con, org, time_field, end):
    """按业务员分组的 8 项核心指标（policy + claims）。"""
    register_udfs(con)
    year_start = date(end.year, 1, 1)
    sql = f"""
    WITH filtered AS (
      SELECT
        p.policy_no,
        CAST(p.insurance_start_date AS DATE) AS sd,
        short_salesman_name(p.salesman_name) AS sn,
        p.premium,
        COALESCE(p.fee_amount, 0) AS fee_amount
      FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
      WHERE p.org_level_3=?
        AND p.{time_field} BETWEEN ? AND ?
        AND p.insurance_start_date IS NOT NULL
    ),
    policy_dedup AS (
      SELECT policy_no, sd, sn,
             SUM(premium) AS premium,
             SUM(fee_amount) AS fee_amount
      FROM filtered
      GROUP BY policy_no, sd, sn
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
        p.policy_no, p.sd, p.sn, p.premium, p.fee_amount,
        DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR) AS policy_term,
        LEAST(GREATEST(DATEDIFF('day', p.sd, DATE '{end.isoformat()}'), 0),
              DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR)) AS earned_days,
        COALESCE(c.claim_cases, 0) AS claim_cases,
        COALESCE(c.reported_claims, 0) AS reported_claims
      FROM policy_dedup p
      LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
    )
    SELECT
      sn AS dim,
      CAST(COUNT(DISTINCT policy_no) AS INTEGER) AS policy_count,
      ROUND(SUM(premium), 2) AS premium,
      CAST(SUM(claim_cases) AS INTEGER) AS claim_count,
      CASE WHEN SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)) > 0
            AND SUM(premium) > 0
           THEN ROUND(SUM(reported_claims) * 100.0
                      / SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE))
                      + SUM(fee_amount) * 100.0 / SUM(premium), 2)
           ELSE NULL END AS variable_cost_ratio_pct,
      CASE WHEN SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)) > 0
           THEN ROUND(SUM(reported_claims) * 100.0
                      / SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)), 2)
           ELSE NULL END AS earned_loss_ratio_pct,
      CASE WHEN SUM(earned_days) > 0
           THEN ROUND(SUM(claim_cases) * 365.0 / SUM(earned_days) * 100, 2)
           ELSE NULL END AS earned_loss_freq_pct,
      CASE WHEN SUM(claim_cases) > 0
           THEN ROUND(SUM(reported_claims) / CAST(SUM(claim_cases) AS DOUBLE), 0)
           ELSE NULL END AS avg_claim
    FROM e
    WHERE sn IS NOT NULL AND sn != ''
    GROUP BY sn
    ORDER BY premium DESC NULLS LAST
    """
    return con.execute(sql, [org, year_start.isoformat(), end.isoformat()]).df()


def _fetch_growth_by_salesman(con, org, time_field, end):
    """同比 YTD 保费增长率：当期 vs 去年同 YTD（按业务员简称）。"""
    register_udfs(con)
    year_start = date(end.year, 1, 1)
    base_end = (end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29)
                else end.replace(year=end.year - 1, day=28))
    base_start = date(base_end.year, 1, 1)

    def _premium_by_salesman(s, e):
        sql = f"""
        SELECT short_salesman_name(salesman_name) AS sn, SUM(premium) AS p
        FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
        WHERE org_level_3=?
          AND {time_field} BETWEEN ? AND ?
          AND insurance_start_date IS NOT NULL
        GROUP BY short_salesman_name(salesman_name)
        """
        return con.execute(sql, [org, s.isoformat(), e.isoformat()]).df()

    cur = _premium_by_salesman(year_start, end).rename(columns={"p": "cur_p"})
    base = _premium_by_salesman(base_start, base_end).rename(columns={"p": "base_p"})
    g = cur.merge(base, on="sn", how="left").fillna({"base_p": 0})
    g["premium_growth_pct"] = g.apply(
        lambda r: ((r["cur_p"] - r["base_p"]) * 100.0 / r["base_p"]) if r["base_p"] > 0 else None,
        axis=1,
    )
    return g[["sn", "premium_growth_pct"]].rename(columns={"sn": "dim"})


def _fetch_plan_by_salesman(con, org, end):
    """达成率：plan_vehicle × 10000 / 时间进度 vs SUM(policy.premium)，按业务员简称。"""
    register_udfs(con)
    year_start = date(end.year, 1, 1)
    is_leap = (end.year % 4 == 0 and end.year % 100 != 0) or (end.year % 400 == 0)
    days_in_year = 366 if is_leap else 365
    progress = ((end - year_start).days + 1) / days_in_year

    plan_df = con.execute(f"""
        SELECT short_salesman_name(salesman_name) AS sn,
               SUM(plan_vehicle) * 10000.0 AS plan_yuan
        FROM read_parquet('{PLAN_PARQUET}')
        WHERE plan_year=? AND organization=? AND level='salesman'
        GROUP BY short_salesman_name(salesman_name)
    """, [end.year, org]).df()

    actual_df = con.execute(f"""
        SELECT short_salesman_name(salesman_name) AS sn,
               SUM(premium) AS actual_yuan
        FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
        WHERE org_level_3=?
          AND policy_date BETWEEN ? AND ?
          AND insurance_start_date IS NOT NULL
        GROUP BY short_salesman_name(salesman_name)
    """, [org, year_start.isoformat(), end.isoformat()]).df()

    m = plan_df.merge(actual_df, on="sn", how="outer").fillna({"plan_yuan": 0, "actual_yuan": 0})
    m["plan_completion_pct"] = m.apply(
        lambda r: (r["actual_yuan"] * 100.0 / (r["plan_yuan"] * progress))
                  if r["plan_yuan"] > 0 and progress > 0 else None,
        axis=1,
    )
    return m[["sn", "plan_completion_pct"]].rename(columns={"sn": "dim"})


def _fetch_renewal_by_salesman(con, org, end):
    """续保率：按 renewal_tracker.salesman_name 简称分组。"""
    register_udfs(con)
    sql = f"""
    SELECT
      short_salesman_name(salesman_name) AS dim,
      100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? THEN vehicle_frame_no END)
            / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS renewal_rate_pct
    FROM read_parquet('{RENEWAL_PARQUET}')
    WHERE org_level_3=?
      AND expected_expiry_date >= DATE '{end.year}-01-01'
      AND expected_expiry_date <= ?
    GROUP BY short_salesman_name(salesman_name)
    """
    return con.execute(sql, [end.isoformat(), org, end.isoformat()]).df()


def fetch_top_salesmen(con, org, time_field, end, top_n=TOP_N_CAP):
    """组装 TOP N 业务员的 10 列 DataFrame（按保费 DESC 取前 N，不含合计行）。"""
    base = _fetch_metrics_by_salesman(con, org, time_field, end)
    if base.empty:
        return base, 0

    # 按保费 DESC 取 TOP N（min(top_n, 实际数)）
    actual_n = min(top_n, len(base))
    base = base.head(actual_n)

    growth = _fetch_growth_by_salesman(con, org, time_field, end)
    plan = _fetch_plan_by_salesman(con, org, end)
    renewal = _fetch_renewal_by_salesman(con, org, end)

    df = base.merge(growth, on="dim", how="left") \
             .merge(plan, on="dim", how="left") \
             .merge(renewal, on="dim", how="left")

    return df[[
        "dim", "policy_count", "premium",
        "plan_completion_pct", "premium_growth_pct", "renewal_rate_pct",
        "variable_cost_ratio_pct", "earned_loss_ratio_pct", "earned_loss_freq_pct",
        "avg_claim", "claim_count",
    ]], actual_n


# 表头：业务员维度 + 9 项指标（与板块 3 完全一致）
HEADERS_TOP_SALESMEN = [
    ("dim",                       short_label("dim_salesman"),             "left", None,     None),
    ("premium",                   short_label("premium"),                  "num",  "wan",    None),
    ("plan_completion_pct",       short_label("plan_completion_pct"),      "num",  "pct",    None),
    ("premium_growth_pct",        short_label("premium_growth_pct"),       "num",  "pct",    None),
    ("renewal_rate_pct",          short_label("renewal_rate_pct"),         "num",  "pct",    None),
    ("variable_cost_ratio_pct",   short_label("variable_cost_ratio_pct"),  "num",  "pct",    None),
    ("earned_loss_ratio_pct",     short_label("earned_loss_ratio_pct"),    "num",  "pct",    None),
    ("earned_loss_freq_pct",      short_label("earned_loss_freq_pct"),     "num",  "pct",    None),
    ("avg_claim",                 short_label("avg_claim"),                "num",  "money0", None),
    ("claim_count",               short_label("claim_count"),              "num",  "int",    None),
]


def build(con, ctx) -> tuple[str, list, dict]:
    """渲染板块 4，返回 (card_html, drill_pages, nav_entry)。"""
    org = ctx.org
    time_field = ctx.time_field
    cutoff_date = ctx.cutoff

    print(">> 第 4 板块：TOP N 业务员...")
    df, n = fetch_top_salesmen(con, org, time_field, cutoff_date)

    problem_narrative = render_problem_narrative(
        df,
        checks=[
            ("plan_completion_pct",     f"{short_label('plan_completion_pct')}严重滞后", {"alert-yellow", "alert-red"}),
            ("variable_cost_ratio_pct", f"{short_label('variable_cost_ratio_pct')}超线",  {"alert-yellow", "alert-red"}),
            ("renewal_rate_pct",        f"{short_label('renewal_rate_pct')}不足",         {"alert-yellow", "alert-red"}),
            ("earned_loss_ratio_pct",   f"{short_label('earned_loss_ratio_pct')}超线",    {"alert-yellow", "alert-red"}),
        ],
    )

    table_html = render_table(df, dim_label=short_label("dim_salesman"),
                              headers=HEADERS_TOP_SALESMEN)
    title = f"TOP {n} 业务员"
    card = render_card(
        title, "",
        problem_narrative + table_html,
        card_id="section-top-salesmen",
    )

    return card, [], {"anchor": "section-top-salesmen", "label": title}
