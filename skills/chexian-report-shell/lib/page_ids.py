"""下钻 page_id 生成（v1.19 新增）。

设计目标：
  - 把 (dim_key, dim_value) 哈希成短稳定 DOM ID，回避中文 / 路径分隔符 / URL escape 问题
  - 主页表格 onclick 与 drill_pages 的 section id 必须用同一函数生成，保证 SPA 跳转命中
  - 借鉴 diagnose-period-trend/lib/cli.py:_make_drill_page_id 的范式

格式：drill-<prefix>-<6-char-md5-prefix>
"""
from __future__ import annotations

import hashlib

# 维度键 → page_id 前缀（短缩写，避免 id 过长）
_DIM_PREFIX = {
    "team":                 "tm",
    "salesman":             "sm",
    "customer_category":    "cc",
    "insurance_type":       "it",
    "coverage_combination": "cv",
    "is_nev":               "nv",
    "is_new_car":           "nc",
    "is_transfer":          "tf",
    "is_renewal":           "rn",
}


def drill_page_id(dim_key: str, dim_value) -> str:
    """生成稳定的下钻 page_id。

    Args:
      dim_key: 维度键（必须在 _DIM_PREFIX 中注册）
      dim_value: 维度值（任意类型，str() 后参与哈希）

    Returns:
      形如 "drill-cc-a1b2c3" 的字符串，36 字符内
    """
    if dim_key not in _DIM_PREFIX:
        raise KeyError(f"未注册的下钻维度前缀: {dim_key!r}")
    raw = f"{dim_key}::{dim_value}".encode("utf-8")
    digest = hashlib.md5(raw).hexdigest()[:6]
    return f"drill-{_DIM_PREFIX[dim_key]}-{digest}"
