"""SQL 构造 + 派生指标计算。

与原 ad-hoc 完全一致的口径，但路径改为参数注入（不再硬编码项目根）。
"""
from __future__ import annotations

import importlib.util as _spec
import sys as _sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    from .periods import Period
except ImportError:  # pragma: no cover — 脚本式调用 fallback
    from periods import Period  # type: ignore[no-redef]


# 11 类（来自 src/shared/config/customer-categories.ts）。实际数据可能多 1 类「拖拉机」，
# cli.py 主流程会自动补齐到 category_order 末尾。
CUSTOMER_CATEGORIES_REGISTERED = [
    "非营业个人客车", "摩托车", "非营业货车", "非营业企业客车",
    "营业货车", "营业出租租赁", "特种车", "营业公路客运",
    "挂车", "非营业机关客车", "营业城市公交",
]


# 客户类别简称：单一事实源在 chexian-report-shell/lib/labels.py。
# 这里通过 dhr_lib 顶层包 re-export，保留本模块 `SHORT_CATEGORY_LABEL` 与 `short_category`
# 名称兼容，render.py / cli.py 既有调用方无需改动。
if "dhr_lib" not in _sys.modules:
    _dhr_path = Path.home() / ".claude/skills/chexian-report-shell/lib"
    _spec_obj = _spec.spec_from_file_location(
        "dhr_lib", str(_dhr_path / "__init__.py"),
        submodule_search_locations=[str(_dhr_path)],
    )
    _mod = _spec.module_from_spec(_spec_obj)  # type: ignore[arg-type]
    _sys.modules["dhr_lib"] = _mod  # 先注册，再 exec：让包内 `from .alerts import` 可解析
    _spec_obj.loader.exec_module(_mod)  # type: ignore[union-attr]
import dhr_lib  # type: ignore[import-not-found]  # noqa: E402

SHORT_CATEGORY_LABEL: dict[str, str] = dhr_lib.SHORT_CATEGORY_LABEL
short_category = dhr_lib.short_category_label


# 6 个辅助下钻维度（复用项目 src/shared/config/drilldown-dimensions.ts + QuickFilterBar.tsx 的字段定义）。
# 每个维度均为二值：5 个 boolean + 1 个 varchar (insurance_type)。
# 数据层：SQL 取 ANY_VALUE(field) AS field，按 (period, parent_dim, aux_field) 做 GROUPING SETS。
# 渲染层：dim_order = [true_val, false_val]，display 映射 → true_label / false_label。
# 真值/假值用字符串（与 DuckDB CAST(bool AS VARCHAR) 输出 'true'/'false' 对齐）
AUX_DIMENSIONS: list[dict] = [
    {"key": "insurance_type",   "label": "险类",     "field": "insurance_type",
     "true_val": "交强险",       "false_val": "商业保险",
     "true_label": "交强险",     "false_label": "商业保险"},
    # 多值维度：4 个原始值，按数据频次降序展示；用 "values" 列出（含简称映射）
    {"key": "coverage_combination", "label": "险别组合", "field": "coverage_combination",
     "values": [
         {"val": "单交", "label": "单交"},
         {"val": "交三", "label": "交三"},
         {"val": "主全", "label": "主全"},
         {"val": "其他", "label": "其他"},
     ]},
    {"key": "is_nev",           "label": "能源类型", "field": "is_nev",
     "true_val": "true",         "false_val": "false",
     "true_label": "新能源",     "false_label": "燃油"},
    {"key": "is_new_car",       "label": "新旧车",   "field": "is_new_car",
     "true_val": "true",         "false_val": "false",
     "true_label": "新车",       "false_label": "旧车"},
    {"key": "is_transfer",      "label": "是否过户", "field": "is_transfer",
     "true_val": "true",         "false_val": "false",
     "true_label": "过户",       "false_label": "非过户"},
    {"key": "is_renewal",       "label": "是否续保", "field": "is_renewal",
     "true_val": "true",         "false_val": "false",
     "true_label": "续保",       "false_label": "非续保"},
    {"key": "is_telemarketing", "label": "是否电销", "field": "is_telemarketing",
     "true_val": "true",         "false_val": "false",
     "true_label": "电销",       "false_label": "非电销"},
]


def aux_short_label(field: str, raw_val) -> str:
    """把 aux 字段的字符串值映射为显示短标签；未命中退回原值。

    支持二值（true_val/false_val）与多值（values 列表）两种 dim_def 形态。
    """
    s = str(raw_val)
    for d in AUX_DIMENSIONS:
        if d["field"] != field:
            continue
        if "values" in d:
            for v in d["values"]:
                if s == v["val"]: return v["label"]
            return s
        if s == d.get("true_val"):  return d.get("true_label", s)
        if s == d.get("false_val"): return d.get("false_label", s)
    return s


def aux_is_multi(dim_def: dict) -> bool:
    """判断 dim_def 是否为多值（含 "values" 列表）。"""
    return "values" in dim_def


def aux_valid_values(dim_def: dict) -> set:
    """返回该 aux 维度的合法值集合（字符串）。"""
    if aux_is_multi(dim_def):
        return {str(v["val"]) for v in dim_def["values"]}
    return {str(dim_def["true_val"]), str(dim_def["false_val"])}


def aux_default_order(dim_def: dict) -> list:
    """返回该 aux 维度的默认显示顺序（字符串列表）。"""
    if aux_is_multi(dim_def):
        return [str(v["val"]) for v in dim_def["values"]]
    return [str(dim_def["true_val"]), str(dim_def["false_val"])]


# (列 key, 中文名（借鉴 dhr_lib 简称规则）, fmt kind, alerts.TH key 用于打灯；None=不打灯)
# 表 1（整体经营）使用——保单数 / 案件数 是绝对量（万）
METRIC_DEFS: list[tuple[str, str, str, Optional[str]]] = [
    ("variable_cost_ratio",     "变率",             "pct",    "variable_cost_ratio_pct"),
    ("policy_count",            "保单数（万）",     "wan2",   None),
    ("earned_claim_ratio",      "赔付率",           "pct",    "earned_loss_ratio_pct"),
    ("earned_loss_frequency",   "出险率",           "pct",    "earned_loss_freq_pct"),
    ("avg_claim_amount",        "案均",             "money0", None),
    ("claim_cases",             "案件数（万）",     "wan2",   None),
    ("weighted_pricing_factor", "自主系数",         "coef",   None),
]

# 表 2 / 表 3（子维度）使用——保费贡献 / 赔款占比 是相对整体的占比（％），可比性优于绝对量
# 数据派生在 cli.py 的 _compute_share_metrics() 完成（按 period_label 分母 = overall）
METRIC_DEFS_T23: list[tuple[str, str, str, Optional[str]]] = [
    ("variable_cost_ratio",     "变率",             "pct",    "variable_cost_ratio_pct"),
    ("premium_share",           "保费贡献",         "pct",    None),
    ("earned_claim_ratio",      "赔付率",           "pct",    "earned_loss_ratio_pct"),
    ("earned_loss_frequency",   "出险率",           "pct",    "earned_loss_freq_pct"),
    ("avg_claim_amount",        "案均",             "money0", None),
    ("claim_share",             "赔款占比",         "pct",    None),
    ("weighted_pricing_factor", "自主系数",         "coef",   None),
]


def policy_glob(project_root: Path) -> str:
    return str(project_root / "数据管理/warehouse/fact/policy/current/*.parquet")


def claims_glob(project_root: Path) -> str:
    return str(project_root / "数据管理/warehouse/fact/claims_detail/claims_*.parquet")


def build_max_date_sql(project_root: Path) -> str:
    """查询数据中最大 policy_date（ETL 处理日），用于 cutoff 默认值兜底。

    与 server/src/routes/data.ts:830 `SELECT MAX(policy_date) FROM PolicyFact` 同源，
    保证 HomePage `/api/data/version` 取到的 etlDate 与 skill 输出文件名一致。
    """
    return f"""
    SELECT MAX(CAST(policy_date AS DATE)) AS max_date
    FROM read_parquet('{policy_glob(project_root)}')
    WHERE policy_date IS NOT NULL
    """


def build_sql(cutoff: date, periods: list[Period], project_root: Path) -> str:
    """单条 SQL，输出 (period, customer_category | __ALL__, org_level_3 | __ALL__, 全部聚合中间量)。

    GROUPING SETS:
      - 整体（表 1）   ：(period_label)                                  → cust=__ALL__, org=__ALL__
      - 客户类别（表 2）：(period_label, customer_category)              → cust=类别,    org=__ALL__
      - 三级机构（表 3）：(period_label, org_level_3)                    → cust=__ALL__, org=机构
      - 二维交叉（下钻）：(period_label, customer_category, org_level_3) → cust=类别,    org=机构
    上层按 (cust, org) 组合拆分四种行，避免交叉污染。
    """
    earliest = min(p.start_excl for p in periods)
    period_rows = ",\n    ".join(
        f"('{p.label}', DATE '{p.start_excl.isoformat()}', DATE '{p.end_incl.isoformat()}')"
        for p in periods
    )
    cutoff_str = cutoff.isoformat()

    # ⚠️ 关键修正（2026-05-15）：claims 与 earned_days 都按 period_end_incl 计算，
    #    不再统一用 cutoff。否则上年同期保单（cutoff − 1 年）会"假装"满期，
    #    导致赔案累计 / 满期保费 / 派生率值全部"窗口长不可比"。
    #    本次重写让所有 6 个时间窗下，对应起保区间内的保单只暴露到该 period 的右端。
    return f"""
WITH policy_dedup AS (
  SELECT
    policy_no,
    CAST(insurance_start_date AS DATE) AS insurance_start_date,
    SUM(premium)                       AS premium,
    SUM(COALESCE(fee_amount, 0))       AS fee_amount,
    ANY_VALUE(insurance_type)          AS insurance_type,
    ANY_VALUE(customer_category)       AS customer_category,
    ANY_VALUE(org_level_3)             AS org_level_3,
    ANY_VALUE(is_nev)                  AS is_nev,
    ANY_VALUE(is_new_car)              AS is_new_car,
    ANY_VALUE(is_transfer)             AS is_transfer,
    ANY_VALUE(is_renewal)              AS is_renewal,
    ANY_VALUE(is_telemarketing)        AS is_telemarketing,
    ANY_VALUE(coverage_combination)    AS coverage_combination,
    COALESCE(
      ANY_VALUE(CASE WHEN premium > 0 THEN commercial_pricing_factor END),
      ANY_VALUE(commercial_pricing_factor)
    )                                  AS commercial_pricing_factor
  FROM read_parquet('{policy_glob(project_root)}')
  WHERE insurance_start_date IS NOT NULL
    AND CAST(insurance_start_date AS DATE) >  DATE '{earliest.isoformat()}'
    AND CAST(insurance_start_date AS DATE) <= DATE '{cutoff_str}'
  GROUP BY policy_no, CAST(insurance_start_date AS DATE)
  HAVING SUM(premium) > 0
),
periods(period_label, period_start_excl, period_end_incl) AS (
  VALUES
    {period_rows}
),
claims_by_period AS (
  -- 关键：每个 (period, policy) 一行；出险 accident_time / 报案 report_time / 结案 settlement_time
  --   都按 period_end_incl 决策。上年同期 period_end_incl = cutoff − 1 年（不是 cutoff），避免假装满期。
  -- 出险锚点 accident_time<=period_end：赔款分子与满期保费分母同窗口（与 loss-development 双锚点一致）。
  -- 业务过滤对齐项目 SSOT ClaimsAgg：金额剔除无责(liability_ratio=0)与零结/注销/拒赔；
  --   件数(claim_cases)不过滤，保持 cohort 与 xlsx 周报对齐。
  SELECT
    pr.period_label,
    c.policy_no,
    COUNT(DISTINCT c.claim_no) AS claim_cases,
    SUM(
      CASE
        WHEN COALESCE(c.liability_ratio, 100) > 0
         AND (c.case_type IS NULL OR c.case_type NOT IN ('零结', '注销', '拒赔'))
        THEN (CASE
                WHEN c.settlement_time IS NOT NULL
                 AND CAST(c.settlement_time AS DATE) <= pr.period_end_incl
                THEN COALESCE(c.settled_amount, 0)
                ELSE COALESCE(c.reserve_amount, 0)
              END)
        ELSE 0
      END
    ) AS reported_claims
  FROM read_parquet('{claims_glob(project_root)}') c
  CROSS JOIN periods pr
  WHERE c.report_time IS NOT NULL
    AND CAST(c.report_time AS DATE) <= pr.period_end_incl
    AND c.accident_time IS NOT NULL
    AND CAST(c.accident_time AS DATE) <= pr.period_end_incl
  GROUP BY pr.period_label, c.policy_no
),
policy_exposure_per_period AS (
  -- 每个 (period, policy) 一行：earned_days 按 period_end_incl 算，赔案从 claims_by_period 取
  SELECT
    pr.period_label,
    p.policy_no,
    p.insurance_start_date,
    p.insurance_type,
    p.customer_category,
    p.org_level_3,
    p.is_nev,
    p.is_new_car,
    p.is_transfer,
    p.is_renewal,
    p.is_telemarketing,
    p.coverage_combination,
    p.premium,
    p.fee_amount,
    p.commercial_pricing_factor,
    COALESCE(c.reported_claims, 0) AS reported_claims,
    COALESCE(c.claim_cases, 0)     AS claim_cases,
    DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR) AS policy_term,
    LEAST(
      GREATEST(DATEDIFF('day', p.insurance_start_date, pr.period_end_incl), 0),
      DATEDIFF('day', p.insurance_start_date, p.insurance_start_date + INTERVAL 1 YEAR)
    ) AS earned_days
  FROM periods pr
  JOIN policy_dedup p
    ON p.insurance_start_date >  pr.period_start_excl
   AND p.insurance_start_date <= pr.period_end_incl
  LEFT JOIN claims_by_period c
    ON c.period_label = pr.period_label
   AND c.policy_no    = p.policy_no
)
SELECT
  pe.period_label,
  COALESCE(pe.customer_category, '__ALL__')               AS customer_category,
  COALESCE(pe.org_level_3,        '__ALL__')              AS org_level_3,
  -- 真实 NULL 与 grouping marker NULL 区分：CASE 把 NULL 实值转 '__NULL__'，再 COALESCE 标 grouping
  CASE WHEN GROUPING(pe.insurance_type)   = 1 THEN '__ALL__'
       WHEN pe.insurance_type IS NULL THEN '__NULL__' ELSE pe.insurance_type END AS insurance_type,
  CASE WHEN GROUPING(pe.is_nev)           = 1 THEN '__ALL__'
       WHEN pe.is_nev IS NULL THEN '__NULL__' ELSE CAST(pe.is_nev AS VARCHAR) END AS is_nev,
  CASE WHEN GROUPING(pe.is_new_car)       = 1 THEN '__ALL__'
       WHEN pe.is_new_car IS NULL THEN '__NULL__' ELSE CAST(pe.is_new_car AS VARCHAR) END AS is_new_car,
  CASE WHEN GROUPING(pe.is_transfer)      = 1 THEN '__ALL__'
       WHEN pe.is_transfer IS NULL THEN '__NULL__' ELSE CAST(pe.is_transfer AS VARCHAR) END AS is_transfer,
  CASE WHEN GROUPING(pe.is_renewal)       = 1 THEN '__ALL__'
       WHEN pe.is_renewal IS NULL THEN '__NULL__' ELSE CAST(pe.is_renewal AS VARCHAR) END AS is_renewal,
  CASE WHEN GROUPING(pe.is_telemarketing) = 1 THEN '__ALL__'
       WHEN pe.is_telemarketing IS NULL THEN '__NULL__' ELSE CAST(pe.is_telemarketing AS VARCHAR) END AS is_telemarketing,
  CASE WHEN GROUPING(pe.coverage_combination) = 1 THEN '__ALL__'
       WHEN pe.coverage_combination IS NULL THEN '__NULL__' ELSE pe.coverage_combination END AS coverage_combination,
  COUNT(DISTINCT pe.policy_no)              AS policy_count,
  SUM(pe.reported_claims)                   AS reported_claims_sum,
  SUM(pe.premium * CAST(pe.earned_days AS DOUBLE)
      / NULLIF(CAST(pe.policy_term AS DOUBLE), 0))   AS earned_premium_sum,
  SUM(COALESCE(pe.fee_amount, 0))           AS fee_sum,
  SUM(pe.premium)                           AS premium_sum,
  SUM(CASE WHEN pe.insurance_type = '商业保险'
           THEN pe.premium END)             AS commercial_premium_sum,
  SUM(CASE WHEN pe.insurance_type = '商业保险'
            AND pe.commercial_pricing_factor > 0
           THEN pe.premium / pe.commercial_pricing_factor END)
                                            AS baseline_premium_sum,
  SUM(pe.claim_cases)                       AS claim_cases_sum,
  SUM(CAST(pe.claim_cases AS DOUBLE) * CAST(pe.policy_term AS DOUBLE)
      / NULLIF(CAST(pe.earned_days AS DOUBLE), 0))   AS annualized_claim_cases_sum
FROM policy_exposure_per_period pe
GROUP BY GROUPING SETS (
  -- 原有 4 个：整体 / 客户类别 / 三级机构 / 类别×机构
  (pe.period_label),
  (pe.period_label, pe.customer_category),
  (pe.period_label, pe.org_level_3),
  (pe.period_label, pe.customer_category, pe.org_level_3),
  -- 新增 12 个：客户类别 × 6 辅助维度
  (pe.period_label, pe.customer_category, pe.insurance_type),
  (pe.period_label, pe.customer_category, pe.is_nev),
  (pe.period_label, pe.customer_category, pe.is_new_car),
  (pe.period_label, pe.customer_category, pe.is_transfer),
  (pe.period_label, pe.customer_category, pe.is_renewal),
  (pe.period_label, pe.customer_category, pe.is_telemarketing),
  (pe.period_label, pe.customer_category, pe.coverage_combination),
  -- 三级机构 × 7 辅助维度
  (pe.period_label, pe.org_level_3, pe.insurance_type),
  (pe.period_label, pe.org_level_3, pe.is_nev),
  (pe.period_label, pe.org_level_3, pe.is_new_car),
  (pe.period_label, pe.org_level_3, pe.is_transfer),
  (pe.period_label, pe.org_level_3, pe.is_renewal),
  (pe.period_label, pe.org_level_3, pe.is_telemarketing),
  (pe.period_label, pe.org_level_3, pe.coverage_combination),
  -- 7 个 aux 单维（主页 7 aux 卡用）
  (pe.period_label, pe.insurance_type),
  (pe.period_label, pe.is_nev),
  (pe.period_label, pe.is_new_car),
  (pe.period_label, pe.is_transfer),
  (pe.period_label, pe.is_renewal),
  (pe.period_label, pe.is_telemarketing),
  (pe.period_label, pe.coverage_combination),
  -- 21 个 aux × aux 互相交叉（aux 下钻页的其他 aux 卡用）C(7,2) = 21
  (pe.period_label, pe.insurance_type,       pe.is_nev),
  (pe.period_label, pe.insurance_type,       pe.is_new_car),
  (pe.period_label, pe.insurance_type,       pe.is_transfer),
  (pe.period_label, pe.insurance_type,       pe.is_renewal),
  (pe.period_label, pe.insurance_type,       pe.is_telemarketing),
  (pe.period_label, pe.insurance_type,       pe.coverage_combination),
  (pe.period_label, pe.is_nev,               pe.is_new_car),
  (pe.period_label, pe.is_nev,               pe.is_transfer),
  (pe.period_label, pe.is_nev,               pe.is_renewal),
  (pe.period_label, pe.is_nev,               pe.is_telemarketing),
  (pe.period_label, pe.is_nev,               pe.coverage_combination),
  (pe.period_label, pe.is_new_car,           pe.is_transfer),
  (pe.period_label, pe.is_new_car,           pe.is_renewal),
  (pe.period_label, pe.is_new_car,           pe.is_telemarketing),
  (pe.period_label, pe.is_new_car,           pe.coverage_combination),
  (pe.period_label, pe.is_transfer,          pe.is_renewal),
  (pe.period_label, pe.is_transfer,          pe.is_telemarketing),
  (pe.period_label, pe.is_transfer,          pe.coverage_combination),
  (pe.period_label, pe.is_renewal,           pe.is_telemarketing),
  (pe.period_label, pe.is_renewal,           pe.coverage_combination),
  (pe.period_label, pe.is_telemarketing,     pe.coverage_combination)
)
ORDER BY pe.period_label, customer_category, org_level_3;
"""


def derive_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """SUM(分子)/SUM(分母)，分母 0 时返回 NaN（渲染显示 —）。

    率值聚合铁律：永远 SUM(分子) / SUM(分母)，禁加权 / 均值 / 二次汇总。
    """
    def safe_div(num, den):
        return num.where(den.fillna(0) > 0) / den.where(den.fillna(0) > 0)

    out = df.copy()
    out["earned_claim_ratio"]      = safe_div(out.reported_claims_sum, out.earned_premium_sum) * 100
    out["expense_ratio"]           = safe_div(out.fee_sum,             out.premium_sum)        * 100
    out["variable_cost_ratio"]     = out["earned_claim_ratio"] + out["expense_ratio"]
    out["earned_loss_frequency"]   = safe_div(out.annualized_claim_cases_sum, out.policy_count) * 100
    out["avg_claim_amount"]        = safe_div(out.reported_claims_sum, out.claim_cases_sum)
    out["weighted_pricing_factor"] = safe_div(out.commercial_premium_sum, out.baseline_premium_sum)
    out["claim_cases"]             = out.claim_cases_sum
    return out
