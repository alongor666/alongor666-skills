"""V3 叙事周报适配器（org-weekly 版）。

从 SectionContext + drill_long_df 提取数据，调用壳库 deck.py 组件渲染。
A4 打印风格，5 章节叙事 + 附录数据表。
"""
from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path
from typing import Optional

# 复用 render_v1_org 的常量和工具
from render_v1_org import (
    _safe, _e, _fmt, _fmt_delta,
    PERIOD_ORDER_ORG, YTD_IDX, PREV_IDX,
    SECTION_DEFS_ORG, ORG_KPI_DEFS, DIM_KEY_TO_SEC,
)


def _extract_trend_points(ctx) -> list[dict]:
    """5 点趋势（变率/赔付率/出险率三线）。"""
    points = []
    for i, r in enumerate(ctx.standard_rows):
        if r is None: continue
        points.append({
            "label": PERIOD_ORDER_ORG[i],
            "vcr": _safe(r.get("variable_cost_ratio_pct")),
            "lr": _safe(r.get("earned_loss_ratio_pct")),
            "freq": _safe(r.get("earned_loss_freq_pct")),
        })
    return points


def _extract_scatter_points(ctx, drill_long_df) -> list[dict]:
    """客户类别维度散点（赔付率 × 出险率，气泡=保费占比）。"""
    if drill_long_df is None or drill_long_df.empty: return []

    ytd_label = ctx.windows[YTD_IDX][0]
    ytd_df = drill_long_df[(drill_long_df["dim_key"] == "customer_category") &
                          (drill_long_df["period"] == ytd_label)]
    if ytd_df.empty: return []

    overall_prem = _safe(ctx.total_premiums[YTD_IDX]) or 1.0
    from lib import light  # noqa: PLC0415

    points = []
    for _, row in ytd_df.iterrows():
        lr = _safe(row.get("earned_loss_ratio_pct"))
        freq = _safe(row.get("earned_loss_freq_pct"))
        prem = _safe(row.get("premium")) or 0
        prem_share = round(prem / overall_prem * 100, 1) if overall_prem > 0 else 0
        n_pol = int(_safe(row.get("policy_count")) or 0)

        vcr = _safe(row.get("variable_cost_ratio_pct"))
        sev_cls, _ = light("variable_cost_ratio_pct", vcr, n_pol) if vcr else ("alert-gray", "")
        sev_short = sev_cls.replace("alert-", "")

        points.append({
            "name": str(row["dim_value"]),
            "lr": lr, "freq": freq,
            "prem_share": prem_share,
            "sev": sev_short,
        })
    return points


def _extract_kpi_cells(ctx) -> list[dict]:
    """5 格 KPI（deck.py 的 KpiCell 格式）。"""
    from lib import light  # noqa: PLC0415

    cells = []
    n_ytd = ctx.sample_n[YTD_IDX] if ctx.standard_rows else 0
    for col, label, alert_key in ORG_KPI_DEFS:
        r_ytd = ctx.standard_rows[YTD_IDX] if YTD_IDX < len(ctx.standard_rows) else None
        r_prev = ctx.standard_rows[PREV_IDX] if PREV_IDX < len(ctx.standard_rows) else None

        val_ytd = _safe(r_ytd.get(col)) if r_ytd is not None else None
        val_prev = _safe(r_prev.get(col)) if r_prev is not None else None

        delta = val_ytd - val_prev if val_ytd is not None and val_prev is not None else None

        sev = ""
        if val_ytd is not None and alert_key:
            sev, _ = light(alert_key, val_ytd, n_ytd)

        cells.append({
            "label": label, "value": val_ytd,
            "delta_yoy": delta, "kind": "pct", "alert": sev,
        })
    return cells


def _extract_watchlist(ctx, drill_long_df) -> list[dict]:
    """变率超警戒的客户类别清单。"""
    if drill_long_df is None or drill_long_df.empty: return []
    from lib import light  # noqa: PLC0415

    ytd_label = ctx.windows[YTD_IDX][0]
    ytd_df = drill_long_df[(drill_long_df["dim_key"] == "customer_category") &
                          (drill_long_df["period"] == ytd_label)]
    if ytd_df.empty: return []

    items = []
    for _, row in ytd_df.iterrows():
        vcr = _safe(row.get("variable_cost_ratio_pct"))
        if vcr is None: continue
        n_pol = int(_safe(row.get("policy_count")) or 0)
        sev, _ = light("variable_cost_ratio_pct", vcr, n_pol)
        if sev not in ("alert-red", "alert-yellow"): continue

        prem = _safe(row.get("premium"))
        items.append({
            "name": str(row["dim_value"]),
            "vcr": vcr,
            "lr": _safe(row.get("earned_loss_ratio_pct")),
            "freq": _safe(row.get("earned_loss_freq_pct")),
            "prem": prem,
            "sev": sev,
        })

    items.sort(key=lambda x: -(x["vcr"] or 0))
    return items


def _extract_apx_rows(ctx, drill_long_df) -> list[dict]:
    """附录表行：整体 + 客户类别 × 5 期变率。"""
    rows = []

    # 整体行
    overall_vals = []
    for r in ctx.standard_rows:
        overall_vals.append(_safe(r.get("variable_cost_ratio_pct")) if r is not None else None)
    rows.append({"name": "整体", "values": overall_vals, "is_overall": True})

    # 客户类别行
    if drill_long_df is not None and not drill_long_df.empty:
        ytd_periods = [w[0] for w in ctx.windows]
        cat_df = drill_long_df[drill_long_df["dim_key"] == "customer_category"]
        for dim_value in sorted(cat_df["dim_value"].unique()):
            vals = []
            for p in ytd_periods:
                sub = cat_df[(cat_df["dim_value"] == dim_value) & (cat_df["period"] == p)]
                vals.append(_safe(sub.iloc[0].get("variable_cost_ratio_pct")) if not sub.empty else None)
            rows.append({"name": str(dim_value), "values": vals, "is_overall": False})

    return rows


def _generate_tldr(ctx) -> str:
    """生成 TL;DR 摘要。"""
    r_ytd = ctx.standard_rows[YTD_IDX] if YTD_IDX < len(ctx.standard_rows) else None
    r_prev = ctx.standard_rows[PREV_IDX] if PREV_IDX < len(ctx.standard_rows) else None

    if r_ytd is None:
        return "数据暂缺。"

    vcr_ytd = _safe(r_ytd.get("variable_cost_ratio_pct"))
    vcr_prev = _safe(r_prev.get("variable_cost_ratio_pct")) if r_prev is not None else None

    parts = [f"变动成本率 {vcr_ytd:.1f}%"]
    if vcr_prev is not None:
        delta = vcr_ytd - vcr_prev
        direction = "上升" if delta > 0 else "下降"
        parts.append(f"较上周{direction} {abs(delta):.1f}pp")

    lr_ytd = _safe(r_ytd.get("earned_loss_ratio_pct"))
    if lr_ytd is not None:
        parts.append(f"赔付率 {lr_ytd:.1f}%")

    freq_ytd = _safe(r_ytd.get("earned_loss_freq_pct"))
    if freq_ytd is not None:
        parts.append(f"出险率 {freq_ytd:.1f}%")

    n_pol = ctx.sample_n[YTD_IDX] if YTD_IDX < len(ctx.sample_n) else 0
    parts.append(f"累计 {n_pol:,} 张保单")

    return "；".join(parts) + "。"


def render_v3(ctx, drill_long_df, args):
    """生成 V3 叙事周报 HTML。"""
    from lib.render.deck import (
        trend_svg, scatter_svg,
        render_toolbar, render_cover, render_chapter,
        render_kpi_strip, render_resp_cards, render_watchlist,
        render_apx_table, DECK_CSS,
        TrendPoint, ScatterPoint, KpiCell, RespCard, WatchItem, ApTableRow,
    )  # noqa: PLC0415
    from lib import light  # noqa: PLC0415

    org = ctx.org
    cutoff = ctx.cutoff
    cs = cutoff.isoformat()
    out_dir = Path(args.output)

    # 主题资源
    try:
        from themes_v2 import (FONT_LINKS, BASE_CSS, DARK_CSS, THEME_TOGGLE_CSS,
                               THEME_INIT_SCRIPT, THEME_TOGGLE_JS, theme_toggle_btn)
    except ImportError:
        import importlib, sys
        _pt_lib = next(
            (p / "diagnose-period-trend" / "lib" for p in Path(__file__).resolve().parents
             if p.name == "skills" and (p / "diagnose-period-trend").is_dir()),
            Path.home() / ".claude/skills/diagnose-period-trend/lib",  # 兜底（ADR-001）
        )
        sys.path.insert(0, str(_pt_lib))
        _tv2 = importlib.import_module("themes_v2")
        FONT_LINKS, BASE_CSS = _tv2.FONT_LINKS, _tv2.BASE_CSS
        DARK_CSS, THEME_TOGGLE_CSS = _tv2.DARK_CSS, _tv2.THEME_TOGGLE_CSS
        THEME_INIT_SCRIPT, THEME_TOGGLE_JS = _tv2.THEME_INIT_SCRIPT, _tv2.THEME_TOGGLE_JS
        theme_toggle_btn = _tv2.theme_toggle_btn

    # 1. Toolbar（叙事为当前页，链到驾驶舱/超表）
    cockpit_href = f"{org}_{ctx.year}_cockpit.html"
    table_href = f"{org}_{ctx.year}_table.html"
    toolbar = render_toolbar(
        cutoff=cutoff, title=f"{org} 经营诊断周报",
        brand_mark=org[0], theme_toggle_btn=theme_toggle_btn(),
        view_links=[(cockpit_href, "驾驶舱"), (table_href, "超表")],
    )

    # 2. Cover + TL;DR
    tldr = _generate_tldr(ctx)
    kpi_cells = [KpiCell(**c) for c in _extract_kpi_cells(ctx)]
    kpi_strip = render_kpi_strip(kpi_cells)
    cover = render_cover(
        tldr=tldr, kpi_strip=kpi_strip, cutoff=cutoff,
        title=f"{org} {ctx.year} 经营诊断周报",
        subtitle=f"截至 {cs} · YTD 累计口径",
    )

    # 3. Trend SVG
    tp_data = _extract_trend_points(ctx)
    trend_points = [TrendPoint(**p) for p in tp_data]
    trend_chart = trend_svg(trend_points)

    # 4. Scatter SVG
    sp_data = _extract_scatter_points(ctx, drill_long_df)
    scatter_points = [ScatterPoint(**p) for p in sp_data]
    scatter_chart = scatter_svg(scatter_points)

    # 5. Watchlist
    wl_data = _extract_watchlist(ctx, drill_long_df)
    watchlist = render_watchlist([WatchItem(**i) for i in wl_data], header_label="客户类别")

    # 6. Appendix table
    apx_rows = _extract_apx_rows(ctx, drill_long_df)
    apx_headers = PERIOD_ORDER_ORG
    apx_table = render_apx_table([ApTableRow(**r) for r in apx_rows], apx_headers)

    # 7. Chapters
    chapters = [
        render_chapter("01", "关键指标走势",
                       f'<div style="margin-bottom:16px">{trend_chart}</div>', sub="5 期 YTD 三线对照"),
        render_chapter("02", "客户结构分析",
                       f'<div style="margin-bottom:16px">{scatter_chart}</div>'
                       f'<div style="margin-top:20px">{watchlist}</div>',
                       sub="赔付率 × 出险率散点 + 警戒清单"),
        render_chapter("03", "分维度明细",
                       '<p style="color:var(--ink-mute);font-size:13px;">详见驾驶舱视图的 10 段折叠卡</p>',
                       sub="9 个维度 · 完整明细"),
        render_chapter("04", "附录数据",
                       apx_table, sub="客户类别 × 5 期变动成本率"),
    ]

    # 8. Full page
    full_css = BASE_CSS + DARK_CSS + THEME_TOGGLE_CSS + DECK_CSS
    page = f"""<!doctype html>
<html lang="zh-CN" data-theme="ink">
<head>
<meta charset="utf-8"/>
<title>{_e(org)} {ctx.year} 叙事周报 · {cs}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
{FONT_LINKS}
<style>{full_css}</style>
{THEME_INIT_SCRIPT}
</head>
<body>
{toolbar}
<div class="page-wrap">
  <div class="page">
    {cover}
    {"".join(chapters)}
    <div class="signoff">
      <span>生成 {date.today().isoformat()}</span>
      <span>数据截止 {cs}</span>
    </div>
  </div>
</div>
<script>{THEME_TOGGLE_JS}</script>
</body>
</html>"""

    out_path = out_dir / f"{org}_{ctx.year}_narrative.html"
    out_path.write_text(page, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"      [v3] 已写入：{out_path}（{size_kb:.1f} KB）")
