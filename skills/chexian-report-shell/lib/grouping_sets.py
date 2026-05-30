"""多维多窗查询编排（v1.18 新增）— 一次取 5 时间窗 × 9 下钻维度的 8 指标矩阵。

设计权衡（Phase 1 范围控制）：
  Phase 1 实现：5 个 period × 9 个 dim = 45 条独立 SQL，concat 出长表。
  Phase 4 升级：合并为单条 SQL + GROUPING SETS（参 diagnose-period-trend/lib/query.py）。

  Phase 1 选简化版的原因：
    - 复用现有 build_base_cte / METRICS_SELECT，零结构改动
    - SQL 行为独立可调试，每条 < 30 行
    - 性能损失可接受：45 × ~0.5s ≈ 22s（85K 保单场景）

口径：
  - 各 period 的 earned_days 按 period_end 算（与 period-trend 2026-05-15 修正一致），
    避免上年同期保单"假装"满期。
  - 8 指标 SQL 完全复用 lib/queries.py:METRICS_SELECT。
"""
from __future__ import annotations

from typing import Optional

import duckdb
import pandas as pd

from .dimensions import (
    ALL_DIMENSIONS, BUSINESS_DIMENSIONS, ORG_DIMENSIONS,
    DrillDimension, get_dimension,
)
from .queries import (
    build_base_cte, register_udfs,
    METRICS_SELECT, POLICY_GLOB, CLAIMS_GLOB,
)


# 维度键 → 进 CTE 的 extra_fields（base_cte 的 policy_dedup 必须含此字段才能 GROUP BY）
DIMENSION_EXTRA_FIELDS: dict[str, list[str]] = {
    "team":                  ["team"],
    "salesman":              ["salesman_name"],
    "org_level_3":           ["org_level_3"],
    "customer_category":     ["customer_category"],
    "insurance_type":        ["insurance_type"],
    "coverage_combination":  ["coverage_combination"],
    "is_nev":                ["is_nev"],
    "is_new_car":            ["is_new_car"],
    "is_transfer":           ["is_transfer"],
    "is_renewal":            ["is_renewal"],
}


def collect_extra_fields(dim_keys: list[str]) -> list[str]:
    """合并多个维度需要的 extra_fields，去重保序。"""
    seen: dict[str, None] = {}
    for k in dim_keys:
        for f in DIMENSION_EXTRA_FIELDS.get(k, []):
            seen.setdefault(f, None)
    return list(seen)


def multi_dim_periods_query(
    con: duckdb.DuckDBPyConnection,
    *,
    where_clause: str,
    params: list,
    periods: list[tuple],       # [(label, start_excl, end_incl), ...]
    dim_keys: Optional[list[str]] = None,
    time_field: Optional[str] = None,
    policy_glob: str = POLICY_GLOB,
    claims_glob: str = CLAIMS_GLOB,
) -> pd.DataFrame:
    """跑多维多窗诊断查询。

    Args:
      con: DuckDB 连接
      where_clause: 基础过滤（如 "org_level_3 = ? AND YEAR(insurance_start_date) = 2026"）
      params: where_clause 的参数列表（duckdb 占位符 ?）
      periods: 5 元时间窗列表（lib.queries.make_weekly_windows() 的输出）
      dim_keys: 下钻维度键列表；None 表示全部 9 维
      time_field: 时间字段名（如 "insurance_start_date"）；提供时按 period end 截断，
                  确保 policy_count / premium 等不依赖 earned_days 的指标也随窗口变化
      policy_glob/claims_glob: parquet 路径

    Returns:
      长表 DataFrame，列：
        period       — 时间窗 label（如 "当周"）
        dim_key      — 维度键（如 "team" / "is_nev"）
        dim_value    — 维度值（已 CAST 为 VARCHAR）
        policy_count / premium / reported_claims / earned_loss_freq_pct /
        earned_loss_ratio_pct / per_policy_premium / avg_claim /
        expense_ratio_pct / variable_cost_ratio_pct
    """
    register_udfs(con)
    if dim_keys is None:
        dim_keys = [d.key for d in ALL_DIMENSIONS]
    dims = [get_dimension(k) for k in dim_keys]

    extra_fields = collect_extra_fields(dim_keys)

    frames: list[pd.DataFrame] = []
    for label, _start, end in periods:
        cutoff_str = str(end)
        # 按 period end 截断：policy_count/premium 等不依赖 earned_days 的指标
        # 需要通过 WHERE 过滤才能随窗口变化；否则 5 个周期会取到相同保单集。
        period_where = (
            f"{where_clause} AND {time_field} <= DATE '{cutoff_str}'"
            if time_field else where_clause
        )
        cte = build_base_cte(
            extra_fields=extra_fields,
            cutoff=cutoff_str,
            where_clause=period_where,
            policy_glob=policy_glob,
            claims_glob=claims_glob,
        )
        # 为减少 base_cte 重复扫描，每个 period 先物化 policy_exposure 到 TEMP TABLE
        temp_tbl = f"_pe_{abs(hash((label, cutoff_str))) % 10**9}"
        con.execute(f"DROP TABLE IF EXISTS {temp_tbl}")
        con.execute(
            f"CREATE TEMP TABLE {temp_tbl} AS {cte} SELECT * FROM policy_exposure",
            params,
        )

        try:
            for dim in dims:
                sql = (
                    f"SELECT "
                    f"  '{label}'      AS period, "
                    f"  '{dim.key}'    AS dim_key, "
                    f"  CAST({dim.sql_expr} AS VARCHAR) AS dim_value, "
                    f"  {METRICS_SELECT} "
                    f"FROM {temp_tbl} "
                    f"GROUP BY CAST({dim.sql_expr} AS VARCHAR)"
                )
                frames.append(con.execute(sql).df())
        finally:
            con.execute(f"DROP TABLE IF EXISTS {temp_tbl}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def pivot_for_drill(df: pd.DataFrame, dim_key: str,
                    dim_value: str, metric: str = "variable_cost_ratio_pct") -> pd.DataFrame:
    """从长表抽出单个 (dim_key, dim_value) 切片：period × metric → 数值。

    便于 drill_writer 喂给现有的 render_weekly_table。
    """
    sub = df[(df["dim_key"] == dim_key) & (df["dim_value"] == dim_value)]
    return sub[["period", metric]].copy()
