"""SQL 构造 + DataFrame 派生。

核心：PY (保单年度 2022~当前) × DW (30/90/180/270/365/730d) × 维度。
满期口径：earned_days = LEAST(DW, term_days, cutoff - start)
率值铁律：永远 SUM(分子) / SUM(分母)，禁加权 / 均值 / 二次汇总。
"""
from __future__ import annotations

from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Optional

import pandas as pd


# 6 个 DW 锚点（满期天数），用户已锁定不再切换
DW_ANCHORS: list[int] = [30, 90, 180, 270, 365, 730]

# PY 起点：2022 年（之前数据少且老案已封口）
PY_START_YEAR = 2022

# 12 个维度字段（v2.1 起统一使用此列表生成 GROUPING SETS 一维 + 二维交叉）
DIM_FIELDS: list[str] = [
    "customer_category", "org_level_3", "team", "salesman_chinese",
    "insurance_grade", "insurance_type", "coverage_combination",
    "is_nev", "is_new_car", "is_transfer", "is_renewal", "is_telemarketing",
]

# 高 cardinality 维度：不参与二维 GROUPING SETS（避免内存爆炸）
# salesman_chinese 通常 1000+ 唯一值，任何与之的二维交叉都会让 derived 行数飙到百万级
# 业务员相关二维分析改由 runtime 小 SQL 按需生成
HIGH_CARDINALITY_DIMS: set[str] = {"salesman_chinese"}


# (指标 ID, 中文名, 格式 kind, alerts.TH key 用于打灯；None=不打灯, sort_dir: lower_better=越小越好)
# 注：earned_premium_sum 是聚合原料列（非二次派生），直接作为可切换指标（规模视角，不打灯）。
METRIC_DEFS: list[tuple[str, str, str, Optional[str]]] = [
    ("mature_loss_ratio",       "满期赔付率",   "pct",    "earned_loss_ratio_pct"),
    ("mature_incident_rate",    "满期出险率",   "pct",    "earned_loss_freq_pct"),
    ("avg_claim_amount",        "案均赔款",     "money0", None),
    ("earned_premium_sum",      "满期保费(万)", "wan",    None),
    ("bi_case_ratio_pct",       "人伤案占比",   "pct",    None),
    ("bi_amount_ratio_pct",     "人伤金额占比", "pct",    None),
]


def policy_glob(project_root: Path) -> str:
    # [!S]* 排除 SX_ 前缀：fact/current 物理混放 SC+SX（Phase A 前缀架构），裸 *.parquet 会混入
    # SX 致四川赔付率发展三角形虚高约 70%（本技能 _build_ctes_sql 无 branch_code 过滤）。与
    # chexian-api diagnose_common.branch_paths SC policy_glob 同款隔离；文件名前缀可靠性由
    # chexian-api governance「SC policy glob前缀隔离」闸校验（读同一份 warehouse/fact 数据）。
    return str(project_root / "数据管理/warehouse/fact/policy/current/[!S]*.parquet")


def claims_glob(project_root: Path) -> str:
    return str(project_root / "数据管理/warehouse/fact/claims_detail/claims_*.parquet")


def dim_salesman_glob(project_root: Path) -> str:
    return str(project_root / "数据管理/warehouse/dim/salesman/*.parquet")


def build_max_date_sql(project_root: Path) -> str:
    """cutoff 兜底：MAX(policy_date)，与 /api/data/version 同源。"""
    return f"""
    SELECT MAX(CAST(policy_date AS DATE)) AS max_date
    FROM read_parquet('{policy_glob(project_root)}')
    WHERE policy_date IS NOT NULL
    """


def _build_ctes_sql(cutoff: date, project_root: Path) -> str:
    """返回从 policy_base 到 agg_input 的 CTE 链（不含 WITH 关键字，便于复用）。"""
    cutoff_str = cutoff.isoformat()
    py_end = cutoff.year
    return f"""
policy_base AS (
  SELECT
    policy_no,
    CAST(insurance_start_date AS DATE) AS start_date,
    CAST(insurance_end_date   AS DATE) AS end_date,
    DATEDIFF('day', CAST(insurance_start_date AS DATE), CAST(insurance_end_date AS DATE)) AS term_days,
    YEAR(insurance_start_date) AS py,
    SUM(premium) AS premium,
    -- 维度（取 ANY_VALUE，policy_no 已去重）
    ANY_VALUE(customer_category)    AS customer_category,
    ANY_VALUE(org_level_3)          AS org_level_3,
    ANY_VALUE(salesman_name)        AS salesman_full_name,
    ANY_VALUE(insurance_grade)      AS insurance_grade,
    ANY_VALUE(insurance_type)       AS insurance_type,
    ANY_VALUE(coverage_combination) AS coverage_combination,
    ANY_VALUE(is_nev)               AS is_nev,
    ANY_VALUE(is_new_car)           AS is_new_car,
    ANY_VALUE(is_transfer)          AS is_transfer,
    ANY_VALUE(is_renewal)           AS is_renewal,
    ANY_VALUE(is_telemarketing)     AS is_telemarketing
  FROM read_parquet('{policy_glob(project_root)}')
  WHERE insurance_start_date IS NOT NULL
    AND insurance_end_date   IS NOT NULL
    AND CAST(insurance_start_date AS DATE) <= DATE '{cutoff_str}'
    AND YEAR(insurance_start_date) BETWEEN {PY_START_YEAR} AND {py_end}
  GROUP BY
    policy_no,
    CAST(insurance_start_date AS DATE),
    CAST(insurance_end_date   AS DATE),
    YEAR(insurance_start_date)
  HAVING SUM(premium) > 0
),
-- JOIN dim_salesman 派生 salesman_chinese（纯姓名）+ team（中文）
-- policy.salesman_name 形如 "210011829安辉"；dim_salesman.full_name 同形，dim_salesman.salesman_name 仅 "安辉"
policy_with_salesman AS (
  SELECT
    p.*,
    COALESCE(ds.salesman_name, REGEXP_REPLACE(p.salesman_full_name, '^[0-9]+', ''))
      AS salesman_chinese,
    COALESCE(NULLIF(ds.team, 'nan'), '（未知团队）') AS team
  FROM policy_base p
  LEFT JOIN read_parquet('{dim_salesman_glob(project_root)}') ds
    ON p.salesman_full_name = ds.full_name
),
dw_anchors(dw_days) AS (
  VALUES (30), (90), (180), (270), (365), (730)
),
policy_dw AS (
  -- 每张保单 × 6 DW 展开；按天比例算满期保费 / 满期件数 / 完成度
  -- 真实 NULL → '__NULL__'，避免与 GROUPING marker NULL 混淆
  SELECT
    p.policy_no,
    p.py,
    d.dw_days,
    p.start_date,
    p.end_date,
    p.term_days,
    p.premium,
    COALESCE(p.customer_category,    '__NULL__') AS customer_category,
    COALESCE(p.org_level_3,          '__NULL__') AS org_level_3,
    COALESCE(p.team,                 '__NULL__') AS team,
    COALESCE(p.salesman_chinese,     '__NULL__') AS salesman_chinese,
    COALESCE(p.insurance_grade,      '__NULL__') AS insurance_grade,
    COALESCE(p.insurance_type,       '__NULL__') AS insurance_type,
    COALESCE(p.coverage_combination, '__NULL__') AS coverage_combination,
    COALESCE(CAST(p.is_nev           AS VARCHAR), '__NULL__') AS is_nev,
    COALESCE(CAST(p.is_new_car       AS VARCHAR), '__NULL__') AS is_new_car,
    COALESCE(CAST(p.is_transfer      AS VARCHAR), '__NULL__') AS is_transfer,
    COALESCE(CAST(p.is_renewal       AS VARCHAR), '__NULL__') AS is_renewal,
    COALESCE(CAST(p.is_telemarketing AS VARCHAR), '__NULL__') AS is_telemarketing,
    -- 实际暴露天数：min(dw_days, term_days, cutoff - start)
    LEAST(
      d.dw_days,
      p.term_days,
      GREATEST(DATEDIFF('day', p.start_date, DATE '{cutoff_str}'), 0)
    ) AS exposed_days,
    -- 是否完整观察（用于 △ 标记）：cutoff - start ≥ dw_days
    DATEDIFF('day', p.start_date, DATE '{cutoff_str}') >= d.dw_days AS is_complete,
    -- 满期保费（按真实暴露天数）：分子分母时间窗口必须与赔案 accident_time 一致
    -- 用 exposed_days 而非 LEAST(dw,term)：partial cell（cutoff-start < dw）时
    --   赔款只能在 [start, cutoff] 内观察，分母也只能按 cutoff-start 缩放
    p.premium * LEAST(
                  d.dw_days,
                  p.term_days,
                  GREATEST(DATEDIFF('day', p.start_date, DATE '{cutoff_str}'), 0)
                )
              / NULLIF(CAST(p.term_days AS DOUBLE), 0) AS earned_premium_at_dw
  FROM policy_with_salesman p
  CROSS JOIN dw_anchors d
),
-- 关联出险案件（accident_time ∈ [start, start+dw_days]，且案件已上报系统）
-- 金额口径（项目标准，参 diagnose-period-trend/lib/query.py:227）：
--   已决（settlement_time ≤ start+dw_days）→ settled_amount
--   未决                                   → reserve_amount
-- 二选一不相加；人伤金额同口径
claims_in_dw AS (
  SELECT
    pdw.policy_no,
    pdw.py,
    pdw.dw_days,
    pdw.customer_category,
    pdw.org_level_3,
    pdw.team,
    pdw.salesman_chinese,
    pdw.insurance_grade,
    pdw.insurance_type,
    pdw.coverage_combination,
    pdw.is_nev,
    pdw.is_new_car,
    pdw.is_transfer,
    pdw.is_renewal,
    pdw.is_telemarketing,
    c.claim_no,
    -- 业务过滤对齐项目 SSOT ClaimsAgg：金额剔除无责(liability_ratio=0)与零结/注销/拒赔；
    -- 件数(claim_cases)不过滤，保持 cohort 与 xlsx 周报对齐（settlement<=dw 的开发口径保留）
    CASE
      WHEN COALESCE(c.liability_ratio, 100) > 0
       AND (c.case_type IS NULL OR c.case_type NOT IN ('零结', '注销', '拒赔'))
      THEN (CASE
              WHEN c.settlement_time IS NOT NULL
               AND DATEDIFF('day', pdw.start_date, CAST(c.settlement_time AS DATE)) <= pdw.dw_days
              THEN COALESCE(c.settled_amount, 0)
              ELSE COALESCE(c.reserve_amount, 0)
            END)
      ELSE 0
    END AS claim_amount,
    CASE
      WHEN COALESCE(c.liability_ratio, 100) > 0
       AND (c.case_type IS NULL OR c.case_type NOT IN ('零结', '注销', '拒赔'))
      THEN (CASE
              WHEN c.settlement_time IS NOT NULL
               AND DATEDIFF('day', pdw.start_date, CAST(c.settlement_time AS DATE)) <= pdw.dw_days
              THEN COALESCE(c.settled_bodily_amount, 0)
              ELSE COALESCE(c.reserve_bodily_amount, 0)
            END)
      ELSE 0
    END AS bi_claim_amount,
    COALESCE(c.is_bodily_injury, FALSE) AS is_bi
  FROM policy_dw pdw
  JOIN read_parquet('{claims_glob(project_root)}') c
    ON c.policy_no = pdw.policy_no
   AND c.report_time   IS NOT NULL
   AND c.accident_time IS NOT NULL
   AND DATEDIFF('day', pdw.start_date, CAST(c.accident_time AS DATE)) BETWEEN 0 AND pdw.dw_days
   AND CAST(c.accident_time AS DATE) <= DATE '{cutoff_str}'
   AND CAST(c.report_time   AS DATE) <= DATE '{cutoff_str}'
),
-- 案件级聚合到 (py, dw, dim, policy)
claim_per_policy AS (
  SELECT
    py, dw_days,
    customer_category, org_level_3, team, salesman_chinese,
    insurance_grade, insurance_type, coverage_combination,
    is_nev, is_new_car, is_transfer, is_renewal, is_telemarketing,
    policy_no,
    COUNT(DISTINCT claim_no)              AS claim_cases,
    SUM(claim_amount)                     AS total_claim,
    SUM(bi_claim_amount)                  AS bi_claim,
    SUM(CAST(is_bi AS INT))               AS bi_count,
    -- 出险件数（按 VIN/policy 去重）：只要有案件就算 1，与 diagnose-period-trend 一致
    1                                     AS incident_flag
  FROM claims_in_dw
  GROUP BY ALL
),
-- 合并保单暴露 + 案件聚合（LEFT JOIN，保单无案件也保留）
agg_input AS (
  SELECT
    pdw.py,
    pdw.dw_days,
    pdw.customer_category,
    pdw.org_level_3,
    pdw.team,
    pdw.salesman_chinese,
    pdw.insurance_grade,
    pdw.insurance_type,
    pdw.coverage_combination,
    pdw.is_nev,
    pdw.is_new_car,
    pdw.is_transfer,
    pdw.is_renewal,
    pdw.is_telemarketing,
    pdw.policy_no,
    pdw.term_days,
    pdw.exposed_days,
    pdw.earned_premium_at_dw,
    pdw.is_complete,
    COALESCE(cpp.claim_cases, 0)   AS claim_cases,
    COALESCE(cpp.total_claim, 0)   AS total_claim,
    COALESCE(cpp.bi_claim, 0)      AS bi_claim,
    COALESCE(cpp.bi_count, 0)      AS bi_count,
    COALESCE(cpp.incident_flag, 0) AS incident_flag
  FROM policy_dw pdw
  LEFT JOIN claim_per_policy cpp USING (
    py, dw_days,
    customer_category, org_level_3, team, salesman_chinese,
    insurance_grade, insurance_type, coverage_combination,
    is_nev, is_new_car, is_transfer, is_renewal, is_telemarketing,
    policy_no
  )
)
"""


def build_agg_input_materialized_sql(cutoff: date, project_root: Path) -> str:
    """物化 agg_input 用 SQL：CTE 链 + `SELECT * FROM agg_input`。

    cli.py 用 `CREATE TEMP TABLE agg_input AS ...` 包裹此 SQL，让后续主 SQL 和
    runtime batch SQL 都直接查 TEMP TABLE，避免重新扫 parquet。
    """
    return f"""
WITH {_build_ctes_sql(cutoff, project_root)}
SELECT
  py, dw_days,
  customer_category, org_level_3, team, salesman_chinese,
  insurance_grade, insurance_type, coverage_combination,
  is_nev, is_new_car, is_transfer, is_renewal, is_telemarketing,
  policy_no, term_days, exposed_days, earned_premium_at_dw, is_complete,
  claim_cases, total_claim, bi_claim, bi_count, incident_flag
FROM agg_input
"""


def build_main_grouping_sql() -> str:
    """主 SQL：FROM TEMP TABLE agg_input + GROUPING SETS（1 整体 + 12 一维 = 13 组）。

    此 SQL 不再含 CTE 链（agg_input 已物化为 TEMP TABLE）。
    """
    return f"""
SELECT
  ai.py,
  ai.dw_days,
  COALESCE(ai.customer_category,    '__ALL__') AS customer_category,
  COALESCE(ai.org_level_3,          '__ALL__') AS org_level_3,
  COALESCE(ai.team,                 '__ALL__') AS team,
  COALESCE(ai.salesman_chinese,     '__ALL__') AS salesman_chinese,
  COALESCE(ai.insurance_grade,      '__ALL__') AS insurance_grade,
  COALESCE(ai.insurance_type,       '__ALL__') AS insurance_type,
  COALESCE(ai.coverage_combination, '__ALL__') AS coverage_combination,
  COALESCE(ai.is_nev,               '__ALL__') AS is_nev,
  COALESCE(ai.is_new_car,           '__ALL__') AS is_new_car,
  COALESCE(ai.is_transfer,          '__ALL__') AS is_transfer,
  COALESCE(ai.is_renewal,           '__ALL__') AS is_renewal,
  COALESCE(ai.is_telemarketing,     '__ALL__') AS is_telemarketing,
  COUNT(DISTINCT ai.policy_no)                              AS policy_count,
  SUM(CAST(ai.is_complete AS INT))                          AS complete_policy_count,
  SUM(ai.earned_premium_at_dw)                              AS earned_premium_sum,
  SUM(ai.incident_flag)                                     AS incident_count,
  SUM(ai.claim_cases)                                       AS claim_cases_sum,
  SUM(CAST(ai.claim_cases AS DOUBLE) * CAST(ai.term_days AS DOUBLE)
      / NULLIF(CAST(ai.exposed_days AS DOUBLE), 0))         AS annualized_claim_cases_sum,
  SUM(ai.total_claim)                                       AS total_claim_sum,
  SUM(ai.bi_claim)                                          AS bi_claim_sum,
  SUM(ai.bi_count)                                          AS bi_count_sum
FROM agg_input ai
GROUP BY GROUPING SETS (
{_grouping_sets_sql()}
)
ORDER BY ai.py DESC, ai.dw_days
"""


def build_subdim_batch_sql(parent_dim: str, parent_value: str, child_dims: list[str]) -> str:
    """运行时 batch SQL：FROM TEMP TABLE agg_input WHERE parent_dim=value，
    输出该父维度值在 N 个副维度的二维聚合（UNION ALL）。

    每个 child_dim 子查询输出：(child_dim_marker, child_value, py, dw, 5 指标聚合)
    输出列首加 child_dim 标识列，cli.py 根据它分发到对应副维度 Card。
    """
    if parent_dim not in DIM_FIELDS:
        raise ValueError(f"unknown parent_dim: {parent_dim}")
    safe_value = parent_value.replace("'", "''")
    parts: list[str] = []
    for child_dim in child_dims:
        if child_dim == parent_dim or child_dim not in DIM_FIELDS:
            continue
        parts.append(f"""SELECT
  '{child_dim}'        AS child_dim,
  {child_dim}          AS child_value,
  py, dw_days,
  COUNT(DISTINCT policy_no)                              AS policy_count,
  SUM(CAST(is_complete AS INT))                          AS complete_policy_count,
  SUM(earned_premium_at_dw)                              AS earned_premium_sum,
  SUM(incident_flag)                                     AS incident_count,
  SUM(claim_cases)                                       AS claim_cases_sum,
  SUM(CAST(claim_cases AS DOUBLE) * CAST(term_days AS DOUBLE)
      / NULLIF(CAST(exposed_days AS DOUBLE), 0))         AS annualized_claim_cases_sum,
  SUM(total_claim)                                       AS total_claim_sum,
  SUM(bi_claim)                                          AS bi_claim_sum,
  SUM(bi_count)                                          AS bi_count_sum
FROM agg_input
WHERE {parent_dim} = '{safe_value}'
GROUP BY child_dim, child_value, py, dw_days""")
    return "\nUNION ALL\n".join(parts) + "\nORDER BY child_dim, child_value, py DESC, dw_days"


def build_sql(cutoff: date, project_root: Path) -> str:
    """v2.1：保留兼容入口。等价于「物化 agg_input + 跑主 SQL」的单 SQL 版本。

    主流程推荐改用 build_agg_input_materialized_sql + build_main_grouping_sql 二段式，
    以便 cli.py 同时复用 TEMP TABLE 跑下钻子页的 batch SQL。
    """
    return f"""
WITH {_build_ctes_sql(cutoff, project_root)}
SELECT
  ai.py,
  ai.dw_days,
  COALESCE(ai.customer_category,    '__ALL__') AS customer_category,
  COALESCE(ai.org_level_3,          '__ALL__') AS org_level_3,
  COALESCE(ai.team,                 '__ALL__') AS team,
  COALESCE(ai.salesman_chinese,     '__ALL__') AS salesman_chinese,
  COALESCE(ai.insurance_grade,      '__ALL__') AS insurance_grade,
  COALESCE(ai.insurance_type,       '__ALL__') AS insurance_type,
  COALESCE(ai.coverage_combination, '__ALL__') AS coverage_combination,
  COALESCE(ai.is_nev,               '__ALL__') AS is_nev,
  COALESCE(ai.is_new_car,           '__ALL__') AS is_new_car,
  COALESCE(ai.is_transfer,          '__ALL__') AS is_transfer,
  COALESCE(ai.is_renewal,           '__ALL__') AS is_renewal,
  COALESCE(ai.is_telemarketing,     '__ALL__') AS is_telemarketing,
  COUNT(DISTINCT ai.policy_no)                              AS policy_count,
  SUM(CAST(ai.is_complete AS INT))                          AS complete_policy_count,
  SUM(ai.earned_premium_at_dw)                              AS earned_premium_sum,
  SUM(ai.incident_flag)                                     AS incident_count,
  SUM(ai.claim_cases)                                       AS claim_cases_sum,
  -- 年化赔案件数（与 metric-registry earned_loss_frequency v2.1.0 一致口径）：
  -- 保单已观察 exposed_days，但保单完整期 term_days，年化系数 = term_days / exposed_days；
  -- 完整满期 (exposed=term) 时 ratio=1，未满期 ratio>1（放大）
  SUM(CAST(ai.claim_cases AS DOUBLE) * CAST(ai.term_days AS DOUBLE)
      / NULLIF(CAST(ai.exposed_days AS DOUBLE), 0))         AS annualized_claim_cases_sum,
  SUM(ai.total_claim)                                       AS total_claim_sum,
  SUM(ai.bi_claim)                                          AS bi_claim_sum,
  SUM(ai.bi_count)                                          AS bi_count_sum
FROM agg_input ai
GROUP BY GROUPING SETS (
{_grouping_sets_sql()}
)
ORDER BY ai.py DESC, ai.dw_days;
"""


def _grouping_sets_sql() -> str:
    """主 SQL GROUPING SETS：1 整体 + 12 一维 = 13 组。

    v2.1 教训：二维交叉（55 组）会让 DuckDB hash aggregate 内存爆炸，
    即便排除高 cardinality 的 salesman 也不够。二维分析改由 build_subdim_batch_sql 按需运行。

    不要使用 SQL 行注释 `--`：它会吞掉后面的逗号，导致 parser error。
    """
    sets = ["  (ai.py, ai.dw_days)"]
    for dim in DIM_FIELDS:
        sets.append(f"  (ai.py, ai.dw_days, ai.{dim})")
    return ",\n".join(sets)


def derive_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """SUM(分子)/SUM(分母)，分母 0 时返回 NaN（渲染显示 —）。

    率值聚合铁律：永远 SUM(分子) / SUM(分母)。
    """
    def safe_div(num, den):
        return num.where(den.fillna(0) > 0) / den.where(den.fillna(0) > 0)

    out = df.copy()
    out["mature_loss_ratio"]    = safe_div(out.total_claim_sum,  out.earned_premium_sum) * 100
    # 满期出险率（年化口径）：年化赔案件数 / 保单数 × 100
    # 与项目 metric-registry earned_loss_frequency v2.1.0 一致；未满期 cell 被年化系数放大
    out["mature_incident_rate"] = safe_div(out.annualized_claim_cases_sum, out.policy_count) * 100
    out["avg_claim_amount"]     = safe_div(out.total_claim_sum,  out.claim_cases_sum)
    out["bi_case_ratio_pct"]    = safe_div(out.bi_count_sum,     out.claim_cases_sum)    * 100
    out["bi_amount_ratio_pct"]  = safe_div(out.bi_claim_sum,     out.total_claim_sum)    * 100
    # 完成度（用于 △ / — 标记）
    out["completeness_ratio"]   = safe_div(out.complete_policy_count, out.policy_count)
    return out


def classify_dim_row(row: pd.Series) -> tuple[str, str]:
    """从一行聚合输出判断它属于哪个维度切片（Card N）。

    返回 (dim_key, dim_value)。
    dim_key='__overall__' 表示 Card 1 整体。
    """
    DIM_FIELDS = [
        ("customer_category",    "customer_category"),
        ("org_level_3",          "org_level_3"),
        ("team",                 "team"),
        ("salesman_chinese",     "salesman_chinese"),
        ("insurance_grade",      "insurance_grade"),
        ("insurance_type",       "insurance_type"),
        ("coverage_combination", "coverage_combination"),
        ("is_nev",               "is_nev"),
        ("is_new_car",           "is_new_car"),
        ("is_transfer",          "is_transfer"),
        ("is_renewal",           "is_renewal"),
        ("is_telemarketing",     "is_telemarketing"),
    ]
    active = [
        (key, row[col]) for key, col in DIM_FIELDS
        if row[col] != "__ALL__"
    ]
    if len(active) == 0:
        return ("__overall__", "__ALL__")
    if len(active) == 1:
        return active[0]
    # v2.1：二维交叉行（不属于主页 Card），用专用 marker，由 classify_dim_pair_row 进一步解析
    return ("__pair__", "__ALL__")


def classify_dim_pair_row(row: pd.Series) -> Optional[tuple[str, str, str, str]]:
    """v2.1 下钻页副维度卡数据归类。

    输入一行 derived 数据，若是二维交叉（恰好 2 个 dim 列非 __ALL__）则返回
    (parent_key, parent_val, child_key, child_val)；否则返回 None。
    """
    active = [
        (key, row[key]) for key in DIM_FIELDS if row[key] != "__ALL__"
    ]
    if len(active) != 2:
        return None
    (k1, v1), (k2, v2) = active
    return (k1, str(v1), k2, str(v2))
