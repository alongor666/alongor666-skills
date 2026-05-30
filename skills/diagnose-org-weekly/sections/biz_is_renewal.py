"""板块：续保（v1.19 — 每维一卡）。"""
from __future__ import annotations
from .dim_section import build_dim_card


def build(con, ctx) -> tuple[str, list, dict]:
    card, nav = build_dim_card("is_renewal", ctx)
    return card, [], nav
