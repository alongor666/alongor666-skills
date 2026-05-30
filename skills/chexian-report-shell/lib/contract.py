"""DataFrame 契约校验 — 防止编排脚本与渲染层之间字段漂移。

任何调用 render_table(df) 之前，可以先调用 validate_metrics_df(df)
立即定位字段缺失/类型错误，比让渲染层悄悄渲染坏数据强 10 倍。
"""
from __future__ import annotations

import pandas as pd

# 必需列（dim + 9 项指标）
REQUIRED_COLUMNS: list[tuple[str, str]] = [
    ("dim",                       "object"),     # 维度值（中文字符串）
    ("policy_count",              "integer"),    # 保单数
    ("premium",                   "numeric"),    # 保费（元）
    ("reported_claims",           "numeric"),    # 已报告赔款（元）
    ("earned_loss_freq_pct",      "numeric"),    # 满期出险率（%）
    ("earned_loss_ratio_pct",     "numeric"),    # 满期赔付率（%）
    ("per_policy_premium",        "numeric"),    # 件均保费（元）
    ("avg_claim",                 "numeric"),    # 案均赔款（元）
    ("expense_ratio_pct",         "numeric"),    # 费用率（%）
    ("variable_cost_ratio_pct",   "numeric"),    # 变动成本率（%）
]


class ContractError(Exception):
    """DataFrame 契约违反。打印时直接给可读修复建议。"""


def _is_numeric(dtype) -> bool:
    return pd.api.types.is_numeric_dtype(dtype)


def _is_integer(dtype) -> bool:
    return pd.api.types.is_integer_dtype(dtype)


def validate_metrics_df(df: pd.DataFrame, *, strict: bool = True) -> list[str]:
    """校验 DataFrame 是否符合八项指标契约。

    Args:
      df: 待校验 DataFrame
      strict: True 时违反即抛 ContractError；False 时仅返回错误列表

    Returns:
      错误信息列表（空列表表示通过）
    """
    errors: list[str] = []

    if df.empty:
        # 空表合法（编排层可能想呈现"无数据"），不报错
        return errors

    actual_cols = set(df.columns)
    for col_name, expected_type in REQUIRED_COLUMNS:
        if col_name not in actual_cols:
            errors.append(
                f"缺少必需列「{col_name}」（期望类型 {expected_type}）。"
                f"现有列：{sorted(actual_cols)}"
            )
            continue

        actual_dtype = df[col_name].dtype
        if expected_type == "integer" and not _is_integer(actual_dtype):
            errors.append(
                f"列「{col_name}」类型应为整数，实际为 {actual_dtype}。"
                f"建议：CAST(... AS INTEGER) 或 .astype('Int64')"
            )
        elif expected_type == "numeric" and not _is_numeric(actual_dtype):
            errors.append(
                f"列「{col_name}」类型应为数值，实际为 {actual_dtype}。"
                f"建议：在 SELECT 里 ROUND() 或 CAST(... AS DOUBLE)"
            )
        elif expected_type == "object" and pd.api.types.is_numeric_dtype(actual_dtype):
            errors.append(
                f"列「{col_name}」应为字符串维度值，实际为数值类型 {actual_dtype}。"
                f"建议：CAST(... AS VARCHAR) 或在 SELECT 拼字符串"
            )

    # 业务合理性校验
    if "policy_count" in actual_cols:
        if (df["policy_count"] < 0).any():
            errors.append("policy_count 出现负数（保单数不可为负）")
    if "premium" in actual_cols:
        if (df["premium"] < 0).any():
            errors.append("premium 出现负数（净保费已 HAVING > 0 应不会发生）")
    for pct_col in ("earned_loss_freq_pct", "earned_loss_ratio_pct",
                    "expense_ratio_pct", "variable_cost_ratio_pct"):
        if pct_col in actual_cols:
            non_null = df[pct_col].dropna()
            if not non_null.empty:
                max_v = non_null.max()
                if max_v > 10000:
                    errors.append(
                        f"{pct_col} 最大值 {max_v:.0f}% 远超合理范围（>10000%），"
                        f"高度怀疑 SQL 漏乘 100，请检查 SELECT 表达式"
                    )
                elif max_v > 1000:
                    # 仅提示，非错误：小满期保费 + 大赔案是真实业务情况
                    errors.append(
                        f"[业务极端值] {pct_col} 最大值 {max_v:.0f}%，"
                        f"该分组可能存在小满期保费碰大额赔案的极端样本，"
                        f"建议人工核查具体保单（非 SQL 错误）"
                    )

    if errors and strict:
        msg = "DataFrame 契约校验失败：\n  " + "\n  ".join(errors)
        raise ContractError(msg)

    return errors


def assert_threshold_in_sync(skill_th: dict, project_th_path: str) -> Optional[str]:
    """v1.6 起改为「参考性差异提示」（不再阻断）。

    本 skill 已脱离项目源独立维护（分公司经营口径），项目源仅作参考。
    本函数返回差异说明字符串（用于人工判断是否合并项目最新调整），
    返回 None 表示完全一致。调用方不应再用 assert_, 改用 warn_threshold_drift。
    """
    return warn_threshold_drift(skill_th, project_th_path)


def warn_threshold_drift(skill_th: dict, project_th_path: str) -> Optional[str]:
    """对比本 skill 的 TH 字典与项目 diagnose_common.py 的差异（仅参考）。

    Args:
      skill_th: 本 skill 的 TH 字典
      project_th_path: 项目 diagnose_common.py 完整路径

    Returns:
      None 表示完全一致；否则返回多行差异说明（仅供人工判断是否合并项目调整，不阻断流程）
    """
    from pathlib import Path
    import re

    p = Path(project_th_path)
    if not p.is_file():
        return f"[提示] 无法找到项目阈值源：{project_th_path}（本技能已独立维护，仅影响差异比对）"

    text = p.read_text(encoding="utf-8")

    project_values = {}
    patterns = {
        "earned_loss_freq_pct":    r"TH_IR\s*=\s*\(([\d.,\s]+)\)",
        "earned_loss_ratio_pct":   r"TH_LR\s*=\s*\(([\d.,\s]+)\)",
        "variable_cost_ratio_pct": r"TH_VC\s*=\s*\(([\d.,\s]+)\)",
        "combined_cost_ratio_pct": r"TH_CC\s*=\s*\(([\d.,\s]+)\)",
        "edge_contribution_pct":   r"TH_MR\s*=\s*\(([\d.,\s]+)\)",
        "avg_claim_cargo":         r"TH_AC_CARGO\s*=\s*\(([\d.,\s]+)\)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            nums = tuple(float(x.strip()) for x in m.group(1).split(",") if x.strip())
            project_values[key] = nums

    diffs = []
    for key, skill_v in skill_th.items():
        proj_v = project_values.get(key)
        if proj_v is None:
            diffs.append(f"  - {key}：项目源缺失（本技能独立维护，正常）")
        elif tuple(map(float, skill_v)) != tuple(map(float, proj_v)):
            diffs.append(f"  - {key}：本技能={skill_v} vs 项目源={proj_v}")

    if diffs:
        return ("[阈值差异提示]（不阻断，仅供人工核对是否需合并项目调整）\n"
                + "\n".join(diffs))
    return None


# 给 type checker 看的可选导入
try:
    from typing import Optional  # noqa: E402
except ImportError:
    pass
