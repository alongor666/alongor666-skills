"""板块：险类（v1.19 — 每维一卡）。"""
from __future__ import annotations
from .dim_section import build_dim_card


def build(con, ctx) -> tuple[str, list, dict]:
    card, nav = build_dim_card("insurance_type", ctx)
    return card, [], nav
