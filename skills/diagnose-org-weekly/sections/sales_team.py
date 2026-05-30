"""板块 3：分销售团队（指标诊断表格）。

字段（用户决策 2026-05-15）：
  销售团队 / 保费 / 达成率 / 增长率 / 续保率
  / 变动成本率 / 满期赔付率 / 满期出险率 / 案均赔款 / 赔案件数

数据源与口径：
  - policy.parquet：保费、变动成本率、满期赔付率、满期出险率、案均赔款、赔案件数
    （policy 表无 team 字段，从 plan 维表 `salesman_name → team` 派生归属，
     无归属业务员归入 "未归属"）
  - plan.parquet：达成率（plan_vehicle×10000/年/team / 时间进度 vs 实际 SUM(policy.premium)/team）
  - renewal_tracker.parquet：续保率（直接 GROUP BY team_name，与 plan.team 命名基本对齐）
  - 增长率：同比 YTD policy.premium / team

设计：本板块仅展示分团队概览，不产生 drill 子页。
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


def _fetch_metrics_by_team(con, org, time_field, end):
    """policy 表派生的 8 项核心指标（按 team 分组）+ 合计行。

    返回 DataFrame 列：
      dim, policy_count, premium, claim_count,
      variable_cost_ratio_pct, earned_loss_ratio_pct, earned_loss_freq_pct,
      avg_claim
    """
    register_udfs(con)
    year_start = date(end.year, 1, 1)
    sql = f"""
    WITH salesman_team AS (
      SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
      FROM read_parquet('{PLAN_PARQUET}')
      WHERE plan_year=? AND organization=? AND level='salesman'
    ),
    filtered AS (
      SELECT
        p.policy_no,
        CAST(p.insurance_start_date AS DATE) AS sd,
        COALESCE(st.team, '未归属') AS team,
        p.premium,
        COALESCE(p.fee_amount, 0) AS fee_amount
      FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
      LEFT JOIN salesman_team st ON short_salesman_name(p.salesman_name) = st.s_short
      WHERE p.org_level_3=?
        AND p.{time_field} BETWEEN ? AND ?
        AND p.insurance_start_date IS NOT NULL
    ),
    policy_dedup AS (
      SELECT
        policy_no, sd, team,
        SUM(premium) AS premium,
        SUM(fee_amount) AS fee_amount
      FROM filtered
      GROUP BY policy_no, sd, team
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
        p.policy_no, p.sd, p.team, p.premium, p.fee_amount,
        DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR) AS policy_term,
        LEAST(GREATEST(DATEDIFF('day', p.sd, DATE '{end.isoformat()}'), 0),
              DATEDIFF('day', p.sd, p.sd + INTERVAL 1 YEAR)) AS earned_days,
        COALESCE(c.claim_cases, 0) AS claim_cases,
        COALESCE(c.reported_claims, 0) AS reported_claims
      FROM policy_dedup p
      LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
    )
    SELECT
      short_team_name(team) AS dim,
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
    GROUP BY team
    ORDER BY premium DESC NULLS LAST
    """
    df = con.execute(sql, [end.year, org, org, year_start.isoformat(), end.isoformat()]).df()

    # 合计行（不分组聚合）—— 与 standard_query 不分组语义一致
    sql_total = sql.replace("short_team_name(team) AS dim,", "'合计' AS dim,")
    sql_total = sql_total.replace("GROUP BY team\n    ORDER BY premium DESC NULLS LAST", "")
    df_total = con.execute(sql_total,
                           [end.year, org, org, year_start.isoformat(), end.isoformat()]).df()
    return pd.concat([df_total, df], ignore_index=True)


def _fetch_growth_by_team(con, org, time_field, end):
    """同比 YTD 保费增长率：当期 vs 去年同 YTD。"""
    year_start = date(end.year, 1, 1)
    base_end = (end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29)
                else end.replace(year=end.year - 1, day=28))
    base_start = date(base_end.year, 1, 1)

    register_udfs(con)
    def _premium_by_team(plan_year, s, e):
        sql = f"""
        WITH salesman_team AS (
          SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
          FROM read_parquet('{PLAN_PARQUET}')
          WHERE plan_year=? AND organization=? AND level='salesman'
        )
        SELECT short_team_name(COALESCE(st.team, '未归属')) AS team,
               SUM(p.premium) AS premium
        FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
        LEFT JOIN salesman_team st ON short_salesman_name(p.salesman_name) = st.s_short
        WHERE p.org_level_3=?
          AND p.{time_field} BETWEEN ? AND ?
          AND p.insurance_start_date IS NOT NULL
        GROUP BY short_team_name(COALESCE(st.team, '未归属'))
        """
        return con.execute(sql, [plan_year, org, org, s.isoformat(), e.isoformat()]).df()

    cur = _premium_by_team(end.year, year_start, end).rename(columns={"premium": "cur_p"})
    base = _premium_by_team(end.year, base_start, base_end).rename(columns={"premium": "base_p"})
    g = cur.merge(base, on="team", how="left").fillna({"base_p": 0})
    g["premium_growth_pct"] = g.apply(
        lambda r: ((r["cur_p"] - r["base_p"]) * 100.0 / r["base_p"]) if r["base_p"] > 0 else None,
        axis=1,
    )
    return g[["team", "premium_growth_pct"]].rename(columns={"team": "dim"})


def _fetch_plan_by_team(con, org, time_field, end):
    """达成率（按 team 聚合 plan_vehicle 与 actual policy.premium）。

    plan_completion_pct = actual × 100 / (plan_vehicle_yuan × 时间进度)
    """
    register_udfs(con)
    year_start = date(end.year, 1, 1)
    is_leap = (end.year % 4 == 0 and end.year % 100 != 0) or (end.year % 400 == 0)
    days_in_year = 366 if is_leap else 365
    progress = ((end - year_start).days + 1) / days_in_year

    sql_plan = f"""
    SELECT short_team_name(team) AS team,
           SUM(plan_vehicle) * 10000.0 AS plan_yuan
    FROM read_parquet('{PLAN_PARQUET}')
    WHERE plan_year=? AND organization=? AND level='salesman'
    GROUP BY short_team_name(team)
    """
    plan_df = con.execute(sql_plan, [end.year, org]).df()

    sql_actual = f"""
    WITH salesman_team AS (
      SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
      FROM read_parquet('{PLAN_PARQUET}')
      WHERE plan_year=? AND organization=? AND level='salesman'
    )
    SELECT short_team_name(COALESCE(st.team, '未归属')) AS team,
           SUM(p.premium) AS actual_yuan
    FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
    LEFT JOIN salesman_team st ON short_salesman_name(p.salesman_name) = st.s_short
    WHERE p.org_level_3=?
      AND p.{time_field} BETWEEN ? AND ?
      AND p.insurance_start_date IS NOT NULL
    GROUP BY short_team_name(COALESCE(st.team, '未归属'))
    """
    actual_df = con.execute(sql_actual,
                            [end.year, org, org, year_start.isoformat(), end.isoformat()]).df()

    m = plan_df.merge(actual_df, on="team", how="outer").fillna(
        {"plan_yuan": 0, "actual_yuan": 0})
    m["plan_completion_pct"] = m.apply(
        lambda r: (r["actual_yuan"] * 100.0 / (r["plan_yuan"] * progress))
                  if r["plan_yuan"] > 0 and progress > 0 else None,
        axis=1,
    )
    return m[["team", "plan_completion_pct"]].rename(columns={"team": "dim"})


def _fetch_renewal_by_team(con, org, end):
    """续保率（renewal_tracker.team_name 直接分组，包装为简称）。"""
    register_udfs(con)
    sql = f"""
    SELECT
      short_team_name(team_name) AS dim,
      100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? THEN vehicle_frame_no END)
            / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS renewal_rate_pct
    FROM read_parquet('{RENEWAL_PARQUET}')
    WHERE org_level_3=?
      AND expected_expiry_date >= DATE '{end.year}-01-01'
      AND expected_expiry_date <= ?
    GROUP BY short_team_name(team_name)
    """
    return con.execute(sql, [end.isoformat(), org, end.isoformat()]).df()


def fetch_sales_team_breakdown(con, org, time_field, end):
    """组装分团队 10 列 DataFrame（含合计行，过滤无业务的团队）。"""
    base = _fetch_metrics_by_team(con, org, time_field, end)
    growth = _fetch_growth_by_team(con, org, time_field, end)
    plan = _fetch_plan_by_team(con, org, time_field, end)
    renewal = _fetch_renewal_by_team(con, org, end)

    # 合计 dim 不参与 merge；先拆出合计行
    total_row = base[base["dim"] == "合计"].copy()
    rows = base[base["dim"] != "合计"].copy()

    df = rows.merge(growth, on="dim", how="left") \
             .merge(plan, on="dim", how="left") \
             .merge(renewal, on="dim", how="left")

    # 过滤兜底类团队：保费 < 5 万元且无有效计划的（如"未归属"/"未分配"/"天府团队"）
    # 这些行业务量极小，极端率值（增长率 -98% 等）会污染问题诊断
    df = df[(df["premium"].fillna(0) >= 50000) | (df["plan_completion_pct"].notna())]
    df = df.sort_values("premium", ascending=False, na_position="last").reset_index(drop=True)

    # 合计行的同比 / 达成率 / 续保率（不分组重算，与逐 team 同口径）
    year_start = date(end.year, 1, 1)
    base_end = (end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29)
                else end.replace(year=end.year - 1, day=28))
    base_start = date(base_end.year, 1, 1)

    def _premium_total(s, e):
        r = con.execute(
            f"SELECT SUM(premium) FROM read_parquet('{POLICY_GLOB}', union_by_name=true) "
            f"WHERE org_level_3=? AND {time_field} BETWEEN ? AND ? "
            f"AND insurance_start_date IS NOT NULL",
            [org, s.isoformat(), e.isoformat()],
        ).fetchone()
        return r[0] or 0

    cur_p_total = _premium_total(year_start, end)
    base_p_total = _premium_total(base_start, base_end)
    total_growth = ((cur_p_total - base_p_total) * 100.0 / base_p_total) if base_p_total > 0 else None

    plan_yuan_total = (con.execute(
        f"SELECT SUM(plan_vehicle) * 10000.0 FROM read_parquet('{PLAN_PARQUET}') "
        f"WHERE plan_year=? AND organization=? AND level='salesman'",
        [end.year, org],
    ).fetchone()[0] or 0)
    is_leap = (end.year % 4 == 0 and end.year % 100 != 0) or (end.year % 400 == 0)
    days_in_year = 366 if is_leap else 365
    progress = ((end - year_start).days + 1) / days_in_year
    total_plan = (cur_p_total * 100.0 / (plan_yuan_total * progress)
                  if plan_yuan_total > 0 and progress > 0 else None)

    total_renewal = con.execute(
        f"SELECT 100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? "
        f"THEN vehicle_frame_no END) / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) "
        f"FROM read_parquet('{RENEWAL_PARQUET}') "
        f"WHERE org_level_3=? AND expected_expiry_date >= DATE '{end.year}-01-01' "
        f"AND expected_expiry_date <= ?",
        [end.isoformat(), org, end.isoformat()],
    ).fetchone()[0]

    total_row = total_row.assign(
        premium_growth_pct=total_growth,
        plan_completion_pct=total_plan,
        renewal_rate_pct=total_renewal,
    )

    return pd.concat([total_row, df], ignore_index=True)[[
        "dim", "policy_count", "premium",
        "plan_completion_pct", "premium_growth_pct", "renewal_rate_pct",
        "variable_cost_ratio_pct", "earned_loss_ratio_pct", "earned_loss_freq_pct",
        "avg_claim", "claim_count",
    ]]


# 表头从 SHORT_LABEL 派生（v1.18 唯一事实源；防止换行 + 与其他板块对齐）
HEADERS_SALES_TEAM = [
    ("dim",                       short_label("dim_sales_team"),           "left", None,     None),
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
    """渲染板块 3，返回 (card_html, drill_pages, nav_entry)。"""
    org = ctx.org
    time_field = ctx.time_field
    cutoff_date = ctx.cutoff

    print(">> 第 3 板块：分销售团队...")
    df = fetch_sales_team_breakdown(con, org, time_field, cutoff_date)

    problem_narrative = render_problem_narrative(
        df,
        checks=[
            ("plan_completion_pct",     f"{short_label('plan_completion_pct')}严重滞后",      {"alert-yellow", "alert-red"}),
            ("variable_cost_ratio_pct", f"{short_label('variable_cost_ratio_pct')}超线",       {"alert-yellow", "alert-red"}),
            ("renewal_rate_pct",        f"{short_label('renewal_rate_pct')}不足",              {"alert-yellow", "alert-red"}),
            ("earned_loss_ratio_pct",   f"{short_label('earned_loss_ratio_pct')}超线",         {"alert-yellow", "alert-red"}),
        ],
    )

    table_html = render_table(df, dim_label=short_label("dim_sales_team"), headers=HEADERS_SALES_TEAM)
    card = render_card(
        "分销售团队",
        "",
        problem_narrative + table_html,
        card_id="section-sales-team",
    )

    return card, [], {"anchor": "section-sales-team", "label": f"分{short_label('dim_sales_team')}"}
