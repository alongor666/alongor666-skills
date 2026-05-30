"""标准化诊断查询层 — 八项指标 SQL 模板（满期口径，复刻 cost-ratios.ts）。

设计目标：
  - 把「base_cte + 八指标 SELECT」这 ~80 行 SQL 抽出来共享
  - 任何新编排脚本（按经代/机构/业务员/车型/...）只需声明
    「过滤条件 + 维度表达式 + 额外字段」，即可拿到标准 DataFrame
  - 渲染层零特化：返回的 DataFrame 列名固定，render_table 直接吃

口径来源：
  /Users/alongor666/Downloads/底层数据湖DUD/chexian-api/server/src/sql/cost/cost-ratios.ts
  数据管理/knowledge/rules/车险数据业务规则字典.md v3.0 §938
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

# ============== 数据源路径（本机）==============
PARQUET_ROOT = Path("/Users/alongor666/Downloads/底层数据湖DUD/chexian-api/数据管理/warehouse/fact")
POLICY_GLOB = str(PARQUET_ROOT / "policy/current/*.parquet")
CLAIMS_GLOB = str(PARQUET_ROOT / "claims_detail/*.parquet")


# ============== SQL 模板 ==============
def build_base_cte(extra_fields: list[str], cutoff: str,
                   where_clause: str = "1=1",
                   policy_glob: str = POLICY_GLOB,
                   claims_glob: str = CLAIMS_GLOB) -> str:
    """构造 policy_dedup + claims_agg + policy_exposure 三段 CTE。

    Args:
      extra_fields: 维度字段（如 ["org_level_3"] / ["customer_category"]）
      cutoff: 截止日期（'YYYY-MM-DD'）
      where_clause: WHERE 子句（不含 WHERE 关键字，如 "agent_name=? AND YEAR(policy_date)=2026"）
      policy_glob/claims_glob: parquet 路径模板
    """
    extras_select = ", ".join(extra_fields) if extra_fields else ""
    extras_group = ", ".join(extra_fields) if extra_fields else ""
    extras_p = ", ".join(f"p.{f}" for f in extra_fields) if extra_fields else ""

    return f"""
WITH filtered AS (
  SELECT * FROM read_parquet('{policy_glob}', union_by_name=true)
  WHERE {where_clause}
    AND insurance_start_date IS NOT NULL
),
policy_dedup AS (
  SELECT
    policy_no,
    CAST(insurance_start_date AS DATE) AS insurance_start_date,
    {extras_select + ',' if extras_select else ''}
    SUM(premium) AS premium,
    SUM(COALESCE(fee_amount, 0)) AS fee_amount
  FROM filtered
  GROUP BY policy_no, CAST(insurance_start_date AS DATE){',' + extras_group if extras_group else ''}
  HAVING SUM(premium) > 0
),
claims_agg AS (
  -- 口径对齐项目权威 ClaimsAgg（server/src/services/duckdb-domain-loaders.ts:390）：
  --   ① accident_time <= cutoff：赔款/件数仅计「窗口截止日前已出险」的案件，
  --      与满期保费分母同口径（否则早期 YTD 窗口把未来赔款÷过去满期保费 → 比率虚高数倍）
  --   ② reported_claims：settlement_time 有则 settled_amount 否则 reserve_amount，
  --      并剔除无责案件(liability_ratio=0)与 零结/注销/拒赔（残留 reserve 不应计入）
  --   ③ claim_cases：COUNT(DISTINCT claim_no) 不做业务过滤，保持件数 cohort 与 xlsx 周报对齐
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
  FROM read_parquet('{claims_glob}', union_by_name=true)
  WHERE policy_no IS NOT NULL
    AND CAST(accident_time AS DATE) <= DATE '{cutoff}'
  GROUP BY policy_no
),
policy_exposure AS (
  SELECT
    p.policy_no,
    p.insurance_start_date,
    {extras_p + ',' if extras_p else ''}
    p.premium,
    p.fee_amount,
    DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR) AS policy_term,
    LEAST(
      GREATEST(DATEDIFF('day', p.insurance_start_date, DATE '{cutoff}'), 0),
      DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR)
    ) AS earned_days,
    COALESCE(c.claim_cases, 0) AS claim_cases,
    COALESCE(c.reported_claims, 0) AS reported_claims
  FROM policy_dedup p
  LEFT JOIN claims_agg c ON p.policy_no = c.policy_no
)
"""


# 八项指标 SELECT — 列名与 alerts.py / render.py 的 HEADERS_8METRIC 严格对齐
METRICS_SELECT = """
  CAST(COUNT(DISTINCT policy_no) AS INTEGER) AS policy_count,
  ROUND(SUM(premium), 2) AS premium,
  ROUND(SUM(reported_claims), 2) AS reported_claims,
  CASE WHEN SUM(earned_days) > 0
       THEN ROUND(SUM(claim_cases) * 365.0 / SUM(earned_days) * 100, 2)
       ELSE NULL END AS earned_loss_freq_pct,
  CASE WHEN SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)) > 0
       THEN ROUND(SUM(reported_claims) * 100.0
                  / SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)), 2)
       ELSE NULL END AS earned_loss_ratio_pct,
  CASE WHEN COUNT(DISTINCT policy_no) > 0
       THEN ROUND(SUM(premium) / COUNT(DISTINCT policy_no), 0)
       ELSE NULL END AS per_policy_premium,
  CASE WHEN SUM(claim_cases) > 0
       THEN ROUND(SUM(reported_claims) / CAST(SUM(claim_cases) AS DOUBLE), 0)
       ELSE NULL END AS avg_claim,
  CASE WHEN SUM(premium) > 0
       THEN ROUND(SUM(fee_amount) * 100.0 / SUM(premium), 2)
       ELSE NULL END AS expense_ratio_pct,
  CASE WHEN SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE)) > 0
        AND SUM(premium) > 0
       THEN ROUND(SUM(reported_claims) * 100.0
                  / SUM(premium * CAST(earned_days AS DOUBLE) / CAST(policy_term AS DOUBLE))
                  + SUM(fee_amount) * 100.0 / SUM(premium), 2)
       ELSE NULL END AS variable_cost_ratio_pct
"""


# ============== 高阶查询接口 ==============
def standard_query(con: duckdb.DuckDBPyConnection,
                   *,
                   where_clause: str,
                   params: list,
                   cutoff: str,
                   extra_fields: Optional[list[str]] = None,
                   dim_expr: Optional[str] = None,
                   order: str = "premium DESC NULLS LAST",
                   policy_glob: str = POLICY_GLOB,
                   claims_glob: str = CLAIMS_GLOB) -> pd.DataFrame:
    """跑一条标准化诊断查询，返回符合 11 列契约的 DataFrame。

    Args:
      con: DuckDB 连接
      where_clause: 过滤条件（含参数化占位符 ?）
      params: 占位符对应的参数列表
      cutoff: 截止日期
      extra_fields: 拉到 CTE 的额外字段（用于分组）
      dim_expr: 维度表达式；None 表示不分组（出合计行）
      order: 排序子句
      policy_glob/claims_glob: 自定义数据源路径

    Returns:
      含 11 列的 DataFrame：dim + 8 指标 + claim 计数辅助
    """
    # 自动注册简称 UDF（重复调用安全）
    register_udfs(con)

    extra_fields = extra_fields or []
    cte = build_base_cte(extra_fields, cutoff, where_clause, policy_glob, claims_glob)

    if dim_expr is None:
        sql = f"{cte} SELECT '合计' AS dim, {METRICS_SELECT} FROM policy_exposure"
    else:
        sql = (f"{cte} SELECT {dim_expr} AS dim, {METRICS_SELECT} "
               f"FROM policy_exposure GROUP BY {dim_expr} ORDER BY {order}")

    return con.execute(sql, params).df()


def auto_cutoff(con: duckdb.DuckDBPyConnection,
                where_clause: str,
                params: list,
                policy_glob: str = POLICY_GLOB) -> Optional[str]:
    """自动从数据 max(policy_date) 取截止日期。"""
    r = con.execute(
        f"SELECT MAX(policy_date)::DATE FROM read_parquet('{policy_glob}', union_by_name=true) "
        f"WHERE {where_clause}",
        params,
    ).fetchone()
    return str(r[0]) if r and r[0] else None


# ============== 常用维度表达式（速查）==============
# 经代/业务员简称走 Python UDF，确保 SQL 与 Python 函数 100% 一致。
# 调用方必须在 standard_query 之前对 con 调用 register_udfs(con) —— 已在 standard_query 内自动处理。
DIM_EXPR = {
    "新旧车":       "CASE WHEN is_new_car THEN '新车' ELSE '旧车' END",
    "能源类型":     "CASE WHEN is_nev THEN '新能源' ELSE '燃油' END",
    "是否过户":     "CASE WHEN is_transfer THEN '过户' ELSE '非过户' END",
    "起保月":       "MONTH(insurance_start_date)::VARCHAR || '月'",
    "车牌前两位":   "COALESCE(SUBSTR(plate_no, 1, 2), '未知')",
    "经代简称":     "COALESCE(NULLIF(short_agent_name(agent_name), ''), '未知')",
    "业务员简称":   "COALESCE(NULLIF(short_salesman_name(salesman_name), ''), '未知')",
    "销售团队简称": "COALESCE(NULLIF(short_team_name(team), ''), '未知')",
}


def register_udfs(con: duckdb.DuckDBPyConnection) -> None:
    """注册简称 UDF 到 DuckDB 连接。重复调用安全（第二次会被忽略）。"""
    from .format import short_agent_name, short_salesman_name, short_team_name
    for fn_name, fn in [
        ("short_agent_name", short_agent_name),
        ("short_salesman_name", short_salesman_name),
        ("short_team_name", short_team_name),
    ]:
        try:
            con.create_function(fn_name, fn, [str], str)
        except (duckdb.CatalogException, duckdb.NotImplementedException, Exception) as e:
            # 已存在 / 重复注册 → 忽略
            if "already" not in str(e).lower() and "exists" not in str(e).lower():
                # 其他异常仍然要冒出来
                if "Function with name" not in str(e):
                    raise

def make_weekly_windows(cutoff) -> list[tuple]:
    """v1.19 兼容入口；新代码请用 build_periods(cutoff, preset='weekly')。

    返回 [(label, start_date, end_date), ...] 按 end_date 从早到晚排序。
    start_date 为包含边界（即各年 1/1），与旧行为一致（Period.start_excl + 1 天）。
    """
    from datetime import timedelta
    from .time_windows import build_periods
    return [(p.label, p.start_excl + timedelta(days=1), p.end_incl)
            for p in build_periods(cutoff, preset="weekly")]


# 新车购置价分桶（私家车专用）
PRICE_BUCKETS = """CASE
  WHEN new_vehicle_price IS NULL THEN '未知'
  WHEN new_vehicle_price < 50000 THEN '小于 5 万'
  WHEN new_vehicle_price < 100000 THEN '5 至 10 万'
  WHEN new_vehicle_price < 150000 THEN '10 至 15 万'
  WHEN new_vehicle_price < 200000 THEN '15 至 20 万'
  WHEN new_vehicle_price < 300000 THEN '20 至 30 万'
  WHEN new_vehicle_price < 500000 THEN '30 至 50 万'
  ELSE '50 万及以上'
END"""
