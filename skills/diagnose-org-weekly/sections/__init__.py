"""SECTIONS 注册：list 顺序即 TOC 与卡片渲染顺序。

新增板块两步：
  1. 在本目录写 sections/<name>.py，暴露 build(con, ctx) -> (card, drills, nav)
  2. 在本文件 import 后追加到 SECTIONS list
"""
from __future__ import annotations

from . import (
    overview, customer_type, sales_team, top_salesmen,
    biz_insurance_type, biz_coverage, biz_is_nev,
    biz_is_new_car, biz_is_transfer, biz_is_renewal,
)

# v1.19：6 业务属性回归"每维一卡"，删除原 business_attrs 大平表
SECTIONS = [
    overview,
    customer_type,
    sales_team,
    top_salesmen,
    biz_insurance_type,
    biz_coverage,
    biz_is_nev,
    biz_is_new_car,
    biz_is_transfer,
    biz_is_renewal,
]

__all__ = ["SECTIONS"]
