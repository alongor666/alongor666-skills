"""车险经营诊断报告的板块共享取数。

只放跨板块复用的 fetch_*；板块独占的取数请放在 sections/<板块>.py 内。
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .queries import (
    standard_query, DATA_ROOT, POLICY_GLOB, CLAIMS_GLOB, METRICS_SELECT,
)
from .queries import register_udfs


PLAN_PARQUET = str(DATA_ROOT / "数据管理/warehouse/dim/plan/latest.parquet")
RENEWAL_PARQUET = str(DATA_ROOT / "数据管理/warehouse/fact/renewal_tracker/latest.parquet")
CROSS_SELL_PARQUET = str(DATA_ROOT / "数据管理/warehouse/fact/cross_sell/latest.parquet")


def _org_pred(level: str, org, col: str = "org_level_3"):
    """构造机构过滤谓词。

    level='org'    → ("{col}=?", [org])  仅当前三级机构
    level='branch' → ("TRUE", [])        分公司层：聚合全部三级机构（去过滤）

    用于把单一事实源的 org 过滤逻辑从各 fetch_* 中抽出，
    使三级机构层（org）/ 分公司层（branch）共用同一套取数。
    """
    if level == "branch":
        return ("TRUE", [])
    return (f"{col}=?", [org])


def fetch_standard_window(con, org, time_field, start, end, level="org"):
    """跑一次合计查询，截止 end 日；起保口径 BETWEEN start AND end。"""
    pred, pp = _org_pred(level, org)
    where = f"{pred} AND {time_field} BETWEEN ? AND ?"
    df = standard_query(
        con, where_clause=where, params=pp + [start.isoformat(), end.isoformat()],
        cutoff=end.isoformat(),
    )
    return df.iloc[0] if not df.empty else None


def fetch_household_share(con, org, time_field, start, end, level="org"):
    """家自车占比 = 客户类别='非营业个人客车' 的保单数 / 全部保单数。"""
    pred, pp = _org_pred(level, org)
    sql = f"""
    SELECT
      100.0 * COUNT(DISTINCT CASE WHEN customer_category='非营业个人客车' THEN policy_no END)
            / NULLIF(COUNT(DISTINCT policy_no), 0) AS share_pct
    FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
    WHERE {pred} AND {time_field} BETWEEN ? AND ?
      AND insurance_start_date IS NOT NULL
    """
    r = con.execute(sql, pp + [start.isoformat(), end.isoformat()]).fetchone()
    return r[0] if r and r[0] is not None else None


def fetch_premium_growth(con, org, time_field, start, end, level="org"):
    """保费增长率（同比）= (本期保费 - 去年同期保费) × 100 / 去年同期保费。"""
    base_start = start.replace(year=start.year - 1) if start.month != 2 or start.day != 29 else start.replace(year=start.year - 1, day=28)
    base_end = end.replace(year=end.year - 1) if end.month != 2 or end.day != 29 else end.replace(year=end.year - 1, day=28)
    pred, pp = _org_pred(level, org)
    sql = f"""
    WITH cur AS (
      SELECT SUM(premium) AS p
      FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
      WHERE {pred} AND {time_field} BETWEEN ? AND ?
    ),
    base AS (
      SELECT SUM(premium) AS p
      FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
      WHERE {pred} AND {time_field} BETWEEN ? AND ?
    )
    SELECT
      CASE WHEN base.p > 0
           THEN (cur.p - base.p) * 100.0 / base.p
           ELSE NULL END AS growth_pct
    FROM cur, base
    """
    r = con.execute(sql, pp + [start.isoformat(), end.isoformat()]
                    + pp + [base_start.isoformat(), base_end.isoformat()]).fetchone()
    return r[0] if r and r[0] is not None else None


def fetch_renewal_rate(con, org, end, level="org"):
    """商业险续保率（项目口径）= 已续件数 ÷ 应续件数 × 100（VIN 去重）。

    数据源：renewal_tracker fact 表（项目 RenewalTrackerFact 的本地 parquet）
    口径（v1.9）：
      - 应续：expected_expiry_date 在 [year-01-01, end] 范围内（YTD 至 end）
      - 已续：上述应续 VIN 中 is_renewed=true 且 renewed_date <= end 的部分
      - 与项目 server/src/sql/renewal-tracker.ts 同口径
      - 摩托/挂车在 RenewalTrackerFact 入库时已过滤（应续口径定义本身排除）
    """
    pred, pp = _org_pred(level, org)
    sql = f"""
    SELECT
      100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ? THEN vehicle_frame_no END)
            / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS rate_pct
    FROM read_parquet('{RENEWAL_PARQUET}')
    WHERE {pred}
      AND expected_expiry_date >= DATE '{end.year}-01-01'
      AND expected_expiry_date <= ?
    """
    r = con.execute(sql, [end.isoformat()] + pp + [end.isoformat()]).fetchone()
    return r[0] if r and r[0] is not None else None


def fetch_cross_sell_completion(con, org, end, level="org"):
    """交叉销售达成率 = 实际驾意保费 × 100 ÷ (年计划驾意保费 × 时间进度)。

    数据源：
      - 实际：cross_sell fact 表 SUM(cross_sell_premium_driver) WHERE policy_date BETWEEN year-01-01 AND end
      - 计划：plan parquet 的 plan_personal（人身险计划，单位万元；驾意险是其主体）
              level='organization' 防 double counting
      - 时间进度：与计划达成率同口径（day_of_year / days_in_year）
      - 项目 server/src/sql/cross-sell-heatmap.ts:430 用 KpiPlanConfig.driver business_line，
        本地用 plan_personal 替代（绝大部分人身险计划即驾意险）
    """
    plan_year = end.year
    is_leap = (end.year % 4 == 0 and end.year % 100 != 0) or (end.year % 400 == 0)
    days_in_year = 366 if is_leap else 365
    day_of_year = (end - date(end.year, 1, 1)).days + 1
    progress = day_of_year / days_in_year

    plan_pred, plan_pp = _org_pred(level, org, col="organization")
    cs_pred, cs_pp = _org_pred(level, org)
    sql = f"""
    WITH plan AS (
      SELECT SUM(plan_personal) * 10000.0 AS yp_yuan  -- branch 层 SUM 全机构；单机构 SUM=自身
      FROM read_parquet('{PLAN_PARQUET}')
      WHERE plan_year=? AND {plan_pred} AND level='organization'
    ),
    actual AS (
      SELECT SUM(cross_sell_premium_driver) AS ap
      FROM read_parquet('{CROSS_SELL_PARQUET}')
      WHERE {cs_pred}
        AND policy_date >= DATE '{end.year}-01-01'
        AND policy_date <= ?
    )
    SELECT plan.yp_yuan, actual.ap FROM plan, actual
    """
    r = con.execute(sql, [plan_year] + plan_pp + cs_pp + [end.isoformat()]).fetchone()
    if not r or not r[0] or r[0] <= 0 or r[1] is None:
        return None
    yp_yuan, ap = r
    if progress <= 0:
        return None
    return ap * 100.0 / (yp_yuan * progress)


def fetch_plan_completion(con, org, time_field, start, end, level="org"):
    """计划达成率 = SUM(实际签单保费) × 100 ÷ (SUM(车险年计划) × 时间进度)。

    口径（v1.8 修正）：
      - 实际：policy 表 SUM(premium)（车险净保费）WHERE 起保日期 BETWEEN start AND end
      - 计划：plan_vehicle（**仅车险**，与 policy.premium 同口径），单位万元
              ⚠️ 不可用 plan_total（含财产+人身），口径不一致会让分母虚高、达成率偏低
              与项目 server/src/sql/premiumPlan.ts:117-118 一致
      - 时间进度：end 在 end.year 中的 day_of_year / (闰年 366 / 平年 365)
      - YTD 口径：start = year-01-01
    """
    plan_year = end.year
    # ⚠️ plan parquet 同一 organization 有两个 level：
    #   - level='organization' 1 条：机构汇总值（权威）
    #   - level='salesman'   N 条：业务员分摊值，SUM 后等于机构汇总
    # 不加 level 过滤 → 两份都 SUM → 数值翻倍
    plan_pred, plan_pp = _org_pred(level, org, col="organization")
    pol_pred, pol_pp = _org_pred(level, org)
    sql = f"""
    WITH plan AS (
      SELECT SUM(plan_vehicle) * 10000.0 AS yp_yuan  -- 万元转元；仅车险，与 policy.premium 同口径；branch 层 SUM 全机构
      FROM read_parquet('{PLAN_PARQUET}')
      WHERE plan_year=? AND {plan_pred} AND level='organization'
    ),
    actual AS (
      SELECT SUM(premium) AS ap
      FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
      WHERE {pol_pred} AND {time_field} BETWEEN ? AND ?
    )
    SELECT plan.yp_yuan, actual.ap FROM plan, actual
    """
    r = con.execute(sql, [plan_year] + plan_pp + pol_pp
                    + [start.isoformat(), end.isoformat()]).fetchone()
    if not r or not r[0] or r[0] <= 0:
        return None
    yp_yuan, ap = r
    if ap is None:
        return None
    is_leap = (end.year % 4 == 0 and end.year % 100 != 0) or (end.year % 400 == 0)
    days_in_year = 366 if is_leap else 365
    day_of_year = (end - date(end.year, 1, 1)).days + 1
    progress = day_of_year / days_in_year
    if progress <= 0:
        return None
    return ap * 100.0 / (yp_yuan * progress)


def fetch_team_salesman_periods(con, org, time_field, periods, year,
                                level="org", top_n=None) -> pd.DataFrame:
    """team / salesman 维度的多窗长表（drill_long_df 兼容格式）。

    level='branch' 时：不加 org 过滤（聚合全部三级机构）、**仅产出 team 维度**
    （业务员维度在分公司层由 org_level_3 替代，走 multi_dim_periods_query），
    并按 top_n（如 20）截取最新窗口签单保费 YTD 前 N 名团队。

    为什么单独写：policy.parquet **无 team 字段**，team 必须 JOIN plan.parquet
    （level='salesman'）的 `salesman_name → team` 映射派生。standard 的
    `build_base_cte`/`multi_dim_periods_query` 走纯 policy 表，无法直接产出 team，
    且其 `?` 参数按外部 where_clause 位置绑定，注入 salesman_team CTE 会打乱参数顺序。
    故此处自包含查询，但 **指标公式复用 `METRICS_SELECT`（单一事实源）**，
    salesman_team JOIN 模式复刻已验证的 `sections/sales_team.py:_fetch_metrics_by_team`。

    Returns:
      长表 DataFrame，列与 `grouping_sets.multi_dim_periods_query` 对齐：
        period, dim_key('team'|'salesman'), dim_value,
        policy_count, premium, reported_claims, earned_loss_freq_pct,
        earned_loss_ratio_pct, per_policy_premium, avg_claim,
        expense_ratio_pct, variable_cost_ratio_pct
    """
    register_udfs(con)
    st_plan_pred, st_plan_pp = _org_pred(level, org, col="organization")
    pol_pred, pol_pp = _org_pred(level, org, col="p.org_level_3")
    frames: list[pd.DataFrame] = []
    for label, start, end in periods:
        cutoff_str = end.isoformat()
        # CTE 结构对齐 queries.build_base_cte，额外派生 team + salesman 两列
        cte = f"""
        WITH salesman_team AS (
          SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
          FROM read_parquet('{PLAN_PARQUET}')
          WHERE plan_year=? AND {st_plan_pred} AND level='salesman'
        ),
        filtered AS (
          SELECT
            p.policy_no,
            CAST(p.insurance_start_date AS DATE) AS insurance_start_date,
            COALESCE(st.team, '未归属') AS team,
            COALESCE(NULLIF(short_salesman_name(p.salesman_name), ''), '未知') AS salesman,
            p.premium,
            COALESCE(p.fee_amount, 0) AS fee_amount
          FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
          LEFT JOIN salesman_team st
            ON short_salesman_name(p.salesman_name) = st.s_short
          WHERE {pol_pred} AND p.{time_field} BETWEEN ? AND ?
            AND p.insurance_start_date IS NOT NULL
        ),
        policy_dedup AS (
          SELECT policy_no, insurance_start_date, team, salesman,
                 SUM(premium) AS premium, SUM(fee_amount) AS fee_amount
          FROM filtered
          GROUP BY policy_no, insurance_start_date, team, salesman
          HAVING SUM(premium) > 0
        ),
        claims_agg AS (
          -- 口径对齐 queries.build_base_cte：accident_time<=cutoff（赔款与满期保费同窗口）
          --   + settled-or-reserve 公式 + 剔除无责/零结/注销/拒赔
          SELECT policy_no,
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
            AND CAST(accident_time AS DATE) <= DATE '{cutoff_str}'
          GROUP BY policy_no
        ),
        policy_exposure AS (
          SELECT
            p.policy_no, p.insurance_start_date, p.team, p.salesman,
            p.premium, p.fee_amount,
            DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR) AS policy_term,
            LEAST(
              GREATEST(DATEDIFF('day', p.insurance_start_date, DATE '{cutoff_str}'), 0),
              DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR)
            ) AS earned_days,
            COALESCE(c.claim_cases, 0) AS claim_cases,
            COALESCE(c.reported_claims, 0) AS reported_claims
          FROM policy_dedup p
          LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
        )
        """
        base_params = [year] + st_plan_pp + pol_pp + [start.isoformat(), end.isoformat()]
        # team 用 short_team_name 去「业务团队」后缀（与 sales_team.py 展示口径一致）；
        # salesman 在 filtered CTE 已 short_salesman_name 化，直接用。
        # branch 层仅产 team（salesman 由 org_level_3 替代）。
        dim_specs = [("team", "short_team_name(team)")]
        if level != "branch":
            dim_specs.append(("salesman", "salesman"))
        for dim_key, group_expr in dim_specs:
            sql = (
                f"{cte} SELECT "
                f"  '{label}' AS period, "
                f"  '{dim_key}' AS dim_key, "
                f"  CAST({group_expr} AS VARCHAR) AS dim_value, "
                f"  {METRICS_SELECT} "
                f"FROM policy_exposure GROUP BY {group_expr}"
            )
            frames.append(con.execute(sql, base_params).df())

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)

    # Top N 截取（分公司层 Top20 团队）：按最新窗口签单保费 YTD 降序取前 N 名，
    # 全窗口仅保留这些团队。放在 completion 循环前以省去非 Top 团队的达成率子查询。
    if top_n and not result.empty:
        latest_label = periods[-1][0]
        team_latest = result[(result["dim_key"] == "team") & (result["period"] == latest_label)]
        top_teams = set(
            team_latest.sort_values("premium", ascending=False)
            .head(top_n)["dim_value"].tolist()
        )
        keep = (result["dim_key"] != "team") | (result["dim_value"].isin(top_teams))
        result = result[keep].reset_index(drop=True)

    # 追加 plan_completion_pct 列（D1 回退：仅 team/salesman 维度有值）
    is_leap_map: dict[int, bool] = {}
    completion_vals: list = []
    for _, row in result.iterrows():
        dim_key = row["dim_key"]
        period_label = row["period"]
        # 找对应 period 的 start/end
        window = next(((s, e) for lbl, s, e in periods if lbl == period_label), None)
        if window is None or dim_key not in ("team", "salesman"):
            completion_vals.append(None)
            continue
        start, end = window
        plan_year = end.year
        days_in_year = 366 if (plan_year % 4 == 0 and plan_year % 100 != 0) or plan_year % 400 == 0 else 365
        day_of_year = (end - date(end.year, 1, 1)).days + 1
        progress = day_of_year / days_in_year
        if progress <= 0:
            completion_vals.append(None)
            continue

        dim_value = str(row["dim_value"])
        if dim_key == "team":
            yp_plan_pred, yp_plan_pp = _org_pred(level, org, col="s2.organization")
            sql = f"""
            SELECT SUM(p.premium) AS ap, (
              SELECT SUM(s2.plan_vehicle) * 10000.0
              FROM read_parquet('{PLAN_PARQUET}') s2
              WHERE s2.plan_year=? AND {yp_plan_pred} AND s2.level='salesman'
                AND short_team_name(s2.team)=?
            ) AS yp
            FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
            LEFT JOIN (
              SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
              FROM read_parquet('{PLAN_PARQUET}')
              WHERE plan_year=? AND {st_plan_pred} AND level='salesman'
            ) st ON short_salesman_name(p.salesman_name) = st.s_short
            WHERE {pol_pred} AND p.{time_field} BETWEEN ? AND ?
              AND short_team_name(st.team)=?
            """
            r = con.execute(sql, [plan_year] + yp_plan_pp + [dim_value,
                                  plan_year] + st_plan_pp + pol_pp
                                  + [start.isoformat(), end.isoformat(), dim_value]).fetchone()
        else:  # salesman
            sql = f"""
            WITH plan AS (
              SELECT plan_vehicle * 10000.0 AS yp
              FROM read_parquet('{PLAN_PARQUET}')
              WHERE plan_year=? AND organization=? AND level='salesman'
                AND short_salesman_name(salesman_name)=?
            ),
            actual AS (
              SELECT SUM(premium) AS ap
              FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
              WHERE org_level_3=? AND {time_field} BETWEEN ? AND ?
                AND short_salesman_name(salesman_name)=?
            )
            SELECT actual.ap, plan.yp FROM actual, plan
            """
            r = con.execute(sql, [plan_year, org, dim_value,
                                  org, start.isoformat(), end.isoformat(), dim_value]).fetchone()

        if r and r[0] is not None and r[1] and r[1] > 0:
            completion_vals.append(r[0] * 100.0 / (r[1] * progress))
        else:
            completion_vals.append(None)

    result = result.copy()
    result["plan_completion_pct"] = completion_vals
    return result


def fetch_dim_growth_rates(
    con,
    org: str,
    time_field: str,
    periods: list,
    year: int,
    dim_keys: list[str],
    level: str = "org",
) -> pd.DataFrame:
    """各维度同比保费增长率序列。

    对每个 (period, dim_key, dim_value) 计算：
      growth_pct = (本期 premium - 去年同期 premium) / 去年同期 premium * 100

    Returns:
      DataFrame [period, dim_key, dim_value, premium_growth_pct]
    """
    from .dimensions import get_dimension  # noqa: PLC0415
    register_udfs(con)

    pred, pp = _org_pred(level, org)
    frames: list[pd.DataFrame] = []
    for label, start, end in periods:
        prev_start = start.replace(year=start.year - 1) if not (start.month == 2 and start.day == 29) \
            else start.replace(year=start.year - 1, day=28)
        prev_end = end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29) \
            else end.replace(year=end.year - 1, day=28)

        # 仅处理 multi_dim_periods_query 覆盖的 7 维（team/salesman 走单独路径）
        for dim_key in dim_keys:
            if dim_key in ("team", "salesman"):
                continue
            try:
                dim = get_dimension(dim_key)
            except KeyError:
                continue
            dim_expr = dim.sql_expr

            sql = f"""
            WITH cur AS (
              SELECT CAST({dim_expr} AS VARCHAR) AS dim_value,
                     SUM(premium) AS cur_prem
              FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
              WHERE {pred} AND {time_field} BETWEEN ? AND ?
                AND insurance_start_date IS NOT NULL
              GROUP BY dim_value
            ),
            base AS (
              SELECT CAST({dim_expr} AS VARCHAR) AS dim_value,
                     SUM(premium) AS base_prem
              FROM read_parquet('{POLICY_GLOB}', union_by_name=true)
              WHERE {pred} AND {time_field} BETWEEN ? AND ?
                AND insurance_start_date IS NOT NULL
              GROUP BY dim_value
            )
            SELECT
              ? AS period, ? AS dim_key, cur.dim_value,
              CASE WHEN base.base_prem > 0
                   THEN ROUND((cur.cur_prem - base.base_prem) * 100.0 / base.base_prem, 2)
                   ELSE NULL END AS premium_growth_pct
            FROM cur LEFT JOIN base USING (dim_value)
            """
            df = con.execute(sql,
                pp + [start.isoformat(), end.isoformat()]
                + pp + [prev_start.isoformat(), prev_end.isoformat()]
                + [label, dim_key],
            ).df()
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["period", "dim_key", "dim_value", "premium_growth_pct"])
    return pd.concat(frames, ignore_index=True)


def fetch_renewal_by_dim(
    con,
    org: str,
    periods: list,
    dim_keys: list[str],
    level: str = "org",
) -> pd.DataFrame:
    """各维度续保率序列（从 renewal_tracker 聚合）。

    口径与 fetch_renewal_rate 一致：
      应续：expected_expiry_date IN [year-01-01, end]（YTD 至 end）
      已续：is_renewed=true AND renewed_date <= end

    支持维度：customer_category, coverage_combination, is_nev, is_new_car,
              is_transfer, is_renewal, team（team_name 字段）, salesman
    SKIP：insurance_type（renewal_tracker 无此字段 → 留 None）

    Returns:
      DataFrame [period, dim_key, dim_value, renewal_rate_pct]
    """
    # 字段映射：dim_key → renewal_tracker 字段 + SQL 表达式
    DIM_TO_RENEWAL_FIELD: dict[str, tuple[str, str]] = {
        "customer_category":    ("customer_category", "customer_category"),
        "coverage_combination": ("coverage_combination", "coverage_combination"),
        "is_nev":               ("is_nev", "CASE WHEN is_nev THEN '新能源' ELSE '燃油' END"),
        "is_new_car":           ("is_new_car", "CASE WHEN is_new_car THEN '新车' ELSE '旧车' END"),
        "is_transfer":          ("is_transfer", "CASE WHEN is_transfer THEN '过户' ELSE '非过户' END"),
        "is_renewal":           ("is_renewal", "CASE WHEN is_renewal THEN '续保' ELSE '非续保' END"),
        "team":                 ("team_name", "team_name"),
        "salesman":             ("salesman_name", "short_salesman_name(salesman_name)"),
        "org_level_3":          ("org_level_3", "org_level_3"),
    }

    pred, pp = _org_pred(level, org)
    frames: list[pd.DataFrame] = []
    for label, _start, end in periods:
        year_start = date(end.year, 1, 1)
        for dim_key in dim_keys:
            if dim_key not in DIM_TO_RENEWAL_FIELD:
                continue  # insurance_type 等无对应字段，跳过

            _, sql_expr = DIM_TO_RENEWAL_FIELD[dim_key]
            sql = f"""
            SELECT
              ? AS period, ? AS dim_key,
              CAST({sql_expr} AS VARCHAR) AS dim_value,
              100.0 * COUNT(DISTINCT CASE WHEN is_renewed=true AND renewed_date <= ?
                                          THEN vehicle_frame_no END)
                    / NULLIF(COUNT(DISTINCT vehicle_frame_no), 0) AS renewal_rate_pct
            FROM read_parquet('{RENEWAL_PARQUET}')
            WHERE {pred}
              AND expected_expiry_date >= DATE '{year_start.isoformat()}'
              AND expected_expiry_date <= ?
              AND {sql_expr} IS NOT NULL
            GROUP BY dim_value
            """
            df = con.execute(sql, [label, dim_key, end.isoformat()]
                             + pp + [end.isoformat()]).df()
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["period", "dim_key", "dim_value", "renewal_rate_pct"])
    return pd.concat(frames, ignore_index=True)


# ── 维度交叉下钻数据取数（A5）────────────────────────────────────────────────

# 7 维及其 SQL 表达式（不含 team/salesman，此二维需 JOIN plan.parquet 单独处理）
_ORG_DIM_EXPRS: dict[str, str] = {
    "customer": ("customer_category", "customer_category"),
    "insurance": ("insurance_type", "insurance_type"),
    "combo": ("coverage_combination", "coverage_combination"),
    "energy": ("is_nev", "CASE WHEN is_nev THEN '新能源' ELSE '燃油' END"),
    "newused": ("is_new_car", "CASE WHEN is_new_car THEN '新车' ELSE '旧车' END"),
    "transfer": ("is_transfer", "CASE WHEN is_transfer THEN '过户' ELSE '非过户' END"),
    "renewal": ("is_renewal", "CASE WHEN is_renewal THEN '续保' ELSE '非续保' END"),
}


def fetch_org_cross_data(
    con,
    org: str,
    time_field: str,
    periods: list,
    year: int,
    level: str = "org",
    extra_dims: dict | None = None,
) -> pd.DataFrame:
    """org-weekly 维度交叉下钻数据（5 YTD 窗口 × N 维互相交叉）。

    对每个有效 (主维, 次维) 对，在所有 5 个窗口内取双维聚合指标。
    salesman / team 维需 JOIN plan.parquet，不在本函数内处理。

    level='branch' 时去掉 org 过滤（聚合全部三级机构）。
    extra_dims：额外纯 policy 列交叉维（如分公司层的 org_level_3），
      形如 {"org3": ("org_level_3", "org_level_3")}；其 sql_expr 必须是裸列名，
      因为会同时进 build_base_cte 的 extra_fields 与交叉表达式。

    Returns:
      DataFrame 列：
        period, prim_sec_id, prim_val, sec2_id, sec2_val,
        policy_count, premium, earned_loss_freq_pct, earned_loss_ratio_pct,
        avg_claim, expense_ratio_pct, variable_cost_ratio_pct
    """
    from .queries import build_base_cte, register_udfs, METRICS_SELECT  # noqa: PLC0415
    register_udfs(con)

    dim_exprs = dict(_ORG_DIM_EXPRS)
    base_extra = ["customer_category", "insurance_type", "coverage_combination",
                  "is_nev", "is_new_car", "is_transfer", "is_renewal"]
    if extra_dims:
        dim_exprs.update(extra_dims)
        for _sid, (_col, _expr) in extra_dims.items():
            if _col not in base_extra:
                base_extra.append(_col)

    org_pred, org_pp = _org_pred(level, org)
    sec_ids = list(dim_exprs.keys())
    frames: list[pd.DataFrame] = []

    for label, _start, end in periods:
        cutoff_str = end.isoformat()
        where_clause = f"{org_pred} AND YEAR({time_field})=? AND {time_field} <= DATE '{cutoff_str}'"
        cte = build_base_cte(
            extra_fields=base_extra,
            cutoff=cutoff_str,
            where_clause=where_clause,
        )
        # 临时物化 policy_exposure（复用 multi_dim_periods_query 模式）
        temp = f"_org_cross_{abs(hash((label, cutoff_str))) % 10**9}"
        con.execute(f"DROP TABLE IF EXISTS {temp}")
        con.execute(
            f"CREATE TEMP TABLE {temp} AS {cte} SELECT * FROM policy_exposure",
            org_pp + [year],
        )
        try:
            for prim_id in sec_ids:
                prim_col, prim_expr = dim_exprs[prim_id]
                for sec2_id in sec_ids:
                    if sec2_id == prim_id:
                        continue
                    _, sec2_expr = dim_exprs[sec2_id]
                    sql = (
                        f"SELECT "
                        f"  '{label}' AS period, "
                        f"  '{prim_id}' AS prim_sec_id, "
                        f"  CAST({prim_expr} AS VARCHAR) AS prim_val, "
                        f"  '{sec2_id}' AS sec2_id, "
                        f"  CAST({sec2_expr} AS VARCHAR) AS sec2_val, "
                        f"  {METRICS_SELECT} "
                        f"FROM {temp} "
                        f"GROUP BY CAST({prim_expr} AS VARCHAR), CAST({sec2_expr} AS VARCHAR)"
                    )
                    frames.append(con.execute(sql).df())
        finally:
            con.execute(f"DROP TABLE IF EXISTS {temp}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def fetch_org_team_cross_data(
    con,
    org: str,
    time_field: str,
    periods: list,
    year: int,
    level: str = "branch",
    top_teams: set | None = None,
    extra_dims: dict | None = None,
) -> pd.DataFrame:
    """team 维作主维的交叉下钻数据（team × 全部业务维 [+ org3]）。

    team 需 JOIN plan.parquet（level='salesman' 的 salesman→team 映射）派生归属，
    无法走 build_base_cte，故自包含 CTE（复刻 fetch_team_salesman_periods 的 JOIN 模式
    + fetch_org_cross_data 的临时表交叉模式），指标公式仍复用 METRICS_SELECT（单一事实源）。

    跨机构同名团队按 short_team_name 合并（与团队段 fetch_team_salesman_periods 口径一致）。
    top_teams：仅算这些团队（通常是 Top20 团队段展示的集合），省去非 Top 团队的计算。

    Returns:
      与 fetch_org_cross_data 同列：period, prim_sec_id('team'), prim_val(团队名),
      sec2_id, sec2_val + 指标列。
    """
    from .queries import register_udfs, METRICS_SELECT  # noqa: PLC0415
    register_udfs(con)

    sec_dims = dict(_ORG_DIM_EXPRS)  # 7 业务维
    if extra_dims:
        sec_dims.update(extra_dims)  # 分公司层加 org3

    st_plan_pred, st_plan_pp = _org_pred(level, org, col="organization")
    pol_pred, pol_pp = _org_pred(level, org, col="p.org_level_3")
    raw_cols = ["customer_category", "insurance_type", "coverage_combination",
                "is_nev", "is_new_car", "is_transfer", "is_renewal", "org_level_3"]
    cols_sel = ", ".join(raw_cols)
    cols_p = ", ".join(f"p.{c}" for c in raw_cols)

    frames: list[pd.DataFrame] = []
    for label, _start, end in periods:
        cutoff_str = end.isoformat()
        cte = f"""
        WITH salesman_team AS (
          SELECT DISTINCT short_salesman_name(salesman_name) AS s_short, team
          FROM read_parquet('{PLAN_PARQUET}')
          WHERE plan_year=? AND {st_plan_pred} AND level='salesman'
        ),
        filtered AS (
          SELECT
            p.policy_no,
            CAST(p.insurance_start_date AS DATE) AS insurance_start_date,
            COALESCE(st.team, '未归属') AS team,
            {cols_p},
            p.premium,
            COALESCE(p.fee_amount, 0) AS fee_amount
          FROM read_parquet('{POLICY_GLOB}', union_by_name=true) p
          LEFT JOIN salesman_team st
            ON short_salesman_name(p.salesman_name) = st.s_short
          WHERE {pol_pred} AND YEAR(p.{time_field})=? AND p.{time_field} <= DATE '{cutoff_str}'
            AND p.insurance_start_date IS NOT NULL
        ),
        policy_dedup AS (
          SELECT policy_no, insurance_start_date, team, {cols_sel},
                 SUM(premium) AS premium, SUM(fee_amount) AS fee_amount
          FROM filtered
          GROUP BY policy_no, insurance_start_date, team, {cols_sel}
          HAVING SUM(premium) > 0
        ),
        claims_agg AS (
          -- 口径对齐 queries.build_base_cte：accident_time<=cutoff（赔款与满期保费同窗口）
          --   + settled-or-reserve 公式 + 剔除无责/零结/注销/拒赔
          SELECT policy_no,
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
            AND CAST(accident_time AS DATE) <= DATE '{cutoff_str}'
          GROUP BY policy_no
        ),
        policy_exposure AS (
          SELECT
            p.policy_no, p.insurance_start_date,
            short_team_name(p.team) AS team, {cols_p},
            p.premium, p.fee_amount,
            DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR) AS policy_term,
            LEAST(
              GREATEST(DATEDIFF('day', p.insurance_start_date, DATE '{cutoff_str}'), 0),
              DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR)
            ) AS earned_days,
            COALESCE(c.claim_cases, 0) AS claim_cases,
            COALESCE(c.reported_claims, 0) AS reported_claims
          FROM policy_dedup p
          LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
        )
        """
        base_params = [year] + st_plan_pp + pol_pp + [year]
        temp = f"_team_cross_{abs(hash((label, cutoff_str))) % 10**9}"
        con.execute(f"DROP TABLE IF EXISTS {temp}")
        con.execute(f"CREATE TEMP TABLE {temp} AS {cte} SELECT * FROM policy_exposure", base_params)
        try:
            for sec2_id, (_col, sec2_expr) in sec_dims.items():
                sql = (
                    f"SELECT "
                    f"  '{label}' AS period, "
                    f"  'team' AS prim_sec_id, "
                    f"  CAST(team AS VARCHAR) AS prim_val, "
                    f"  '{sec2_id}' AS sec2_id, "
                    f"  CAST({sec2_expr} AS VARCHAR) AS sec2_val, "
                    f"  {METRICS_SELECT} "
                    f"FROM {temp} "
                    f"GROUP BY team, CAST({sec2_expr} AS VARCHAR)"
                )
                frames.append(con.execute(sql).df())
        finally:
            con.execute(f"DROP TABLE IF EXISTS {temp}")

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    if top_teams is not None:
        result = result[result["prim_val"].isin(top_teams)].reset_index(drop=True)
    return result
