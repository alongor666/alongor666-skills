"""SectionContext：跨板块共享的只读上下文。

主入口构造一次后只读传递给每个 sections/*.py 的 build()。
板块禁止回写任何字段；如发现 ctx 缺字段，回主入口添加后传入。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class SectionContext:
    """跨板块共享的只读上下文。

    Attributes:
      org:            三级机构名
      year:           报告年份
      cutoff:         数据截止日（date 对象，需要字符串调用 .isoformat()）
      time_field:     起保口径字段名，"insurance_start_date" / "policy_date"
      windows:        [(label, start, end), ...] 时序从早到晚的 5 个时间窗口
      time_labels:    ["上季度 03-31", ...] 表头标签
      standard_rows:  [pd.Series | None, ...] 5 个窗口的 standard_query 合计行
      sample_n:       [int, ...] 5 个窗口的 policy_count
      total_premiums: [float | None, ...] 5 个窗口的 premium 合计（占比计算分母）
      out_root:       v1.18 新增 — 报告输出根目录（main.html 与 drill/ 同级）
      drill_long_df:  v1.18 新增 — multi_dim_periods_query 长表（5 窗 × 7 维数据，可选）
    """
    org: str
    year: int
    cutoff: date
    time_field: str
    windows: list
    time_labels: list
    standard_rows: list
    sample_n: list
    total_premiums: list
    out_root: Optional[Path] = None
    drill_long_df: Optional[pd.DataFrame] = None
    org_dd: Optional[dict] = None  # v1.22 交叉下钻数据（V1/V4 注入 DD 对象）
