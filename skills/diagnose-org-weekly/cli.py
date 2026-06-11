"""三级机构经营诊断周报 — 薄主入口（v1.19 单文件 SPA）。

设计原则（用户决策 2026-05-17 二次校准 + 同日命名重组）：
  1. 时间窗口 5 列：当周 / 上周 / 上上周 / 上月 / 上季度（均 YTD 累计，截至日不同）
  2. 各板块独立维护在 sections/，主入口仅做参数解析 + ctx 构造 + 板块编排
  3. 维度顺序：概况 → 客户类别 → 销售团队 → Top 业务员 → 险类 → 险别组合
                → 能源 → 新旧车 → 过户 → 续保（10 个 card）
  4. 下钻走 SPA：同窗口 showPage() 切换，每个 (dim, value) 一个隐藏 section

依赖：~/.claude/skills/chexian-report-shell/lib/* （渲染基础设施层）

用法：
    python3 ~/.claude/skills/diagnose-org-weekly/cli.py \\
        --org "天府" --year 2026 [--cutoff 2026-05-12]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import duckdb

# 注入 chexian-report-shell 到 sys.path 以便 `from lib import ...`
# 引导期无法 import 基座的 skill_path（鸡生蛋），故内联同一套三级优先级（ADR-001）：
#   $CLAUDE_SKILLS_DIR 显式覆盖 > 兄弟目录回溯 > 已知安装根兜底（病态 HOME 自动跳过）
def _resolve_shell_root() -> Path | None:
    import os
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    if env:
        cand = Path(env).expanduser() / "chexian-report-shell"
        if (cand / "lib").is_dir():
            return cand
    for p in Path(__file__).resolve().parents:
        if p.name == "skills" and (p / "chexian-report-shell" / "lib").is_dir():
            return p / "chexian-report-shell"
    try:
        home = Path.home()
    except (RuntimeError, KeyError):
        return None
    for root in (home / ".claude" / "skills",
                 home / ".claude" / "plugins" / "alongor666-skills" / "skills",
                 home / ".agents" / "skills"):
        if (root / "chexian-report-shell" / "lib").is_dir():
            return root / "chexian-report-shell"
    return None


SHELL_ROOT = _resolve_shell_root()
if SHELL_ROOT is None:
    print("未找到渲染层依赖 chexian-report-shell：已尝试 $CLAUDE_SKILLS_DIR、"
          "兄弟回溯与已知安装根；可设 CLAUDE_SKILLS_DIR 指定技能安装根", file=sys.stderr)
    raise SystemExit(2)
sys.path.insert(0, str(SHELL_ROOT))

# 注入自身根目录以便 `from sections import SECTIONS`
SELF_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SELF_ROOT))

import pandas as pd  # noqa: E402

from lib import (  # noqa: E402
    auto_cutoff, make_weekly_windows,
    render_threshold_card, render_page,
    fetch_standard_window,
    fetch_plan_completion, fetch_renewal_rate, fetch_premium_growth,
    fetch_household_share, fetch_cross_sell_completion,
    fetch_team_salesman_periods,
    fetch_dim_growth_rates, fetch_renewal_by_dim,
    fetch_org_cross_data, fetch_org_team_cross_data, build_org_drilldown_data,
    SectionContext,
    multi_dim_periods_query, build_all_drill_pages,
)
from sections import SECTIONS  # noqa: E402


# v1.19：参与 GROUPING SETS 的 7 维（客户类别 + 6 业务属性）。
# team/salesman 因 policy 表无 team 字段、需 JOIN plan.parquet 派生，走独立
# fetch_team_salesman_periods 后 concat（见下），不在 multi_dim_periods_query 内。
DRILL_DIMS = [
    "customer_category",
    "insurance_type", "coverage_combination",
    "is_nev", "is_new_car", "is_transfer", "is_renewal",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="经营诊断周报（板块化主入口）— 支持三级机构 / 分公司两级")
    ap.add_argument("--org", default=None,
                    help="三级机构名（level=org 必填）；level=branch 时为分公司展示名，默认「分公司」，不进 SQL 过滤")
    ap.add_argument("--level", default="org", choices=["org", "branch"],
                    help="org=三级机构层（默认，按 org_level_3 过滤）；"
                         "branch=分公司层（聚合全部三级机构，团队→Top20、业务员→三级机构维度）")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--time-field", default="insurance_start_date",
                    choices=["insurance_start_date", "policy_date"])
    ap.add_argument("--cutoff", default=None)
    ap.add_argument("--output", default="/tmp")
    ap.add_argument("--view", default="all",
                    choices=["legacy", "v1", "v3", "v4", "all"],
                    help="渲染模式：all=DPT三视图全部(默认，产出 cockpit+narrative+table)；"
                         "v1=驾驶舱；v3=叙事周报；v4=超表；legacy=旧版SPA卡片")
    args = ap.parse_args()

    is_branch = args.level == "branch"
    if not args.org:
        if is_branch:
            args.org = "分公司"  # 分公司层展示名（不进 SQL 过滤）
        else:
            print("level=org 必须指定 --org <三级机构名>", file=sys.stderr); return 2

    con = duckdb.connect()

    if not args.cutoff:
        cutoff_where = (f"YEAR({args.time_field})={args.year}" if is_branch
                        else f"org_level_3=? AND YEAR({args.time_field})={args.year}")
        cutoff_params = [] if is_branch else [args.org]
        args.cutoff = auto_cutoff(con, cutoff_where, cutoff_params)
        if not args.cutoff:
            print("未找到数据", file=sys.stderr); return 1

    cutoff_date = date.fromisoformat(args.cutoff)
    口径名 = "起保口径" if args.time_field == "insurance_start_date" else "签单口径"
    层名 = "分公司（全部三级机构）" if is_branch else "三级机构"
    print(f">> {层名}：{args.org}  {args.year} 年  {口径名}  截止 {args.cutoff}")

    windows = make_weekly_windows(cutoff_date)
    time_labels = [f"{label} {end.strftime('%m-%d')}" for label, _, end in windows]
    print(f">> 时间窗口（时序从早到晚）：{[(l, s.isoformat(), e.isoformat()) for l, s, e in windows]}")

    # 共享数据：standard_query 合计行 × 5 窗口（板块复用，避免重复扫表）
    print(">> 取数中...")
    standard_rows = []
    for label, start, end in windows:
        row = fetch_standard_window(con, args.org, args.time_field, start, end, level=args.level)
        standard_rows.append(row)
        n = int(row["policy_count"]) if row is not None else 0
        print(f"   {label}（{start}~{end}）：{n:,} 张保单")

    # KPI 补齐：standard_query 不含计划达成率/续保率/保费增长率，
    # 复用 sections/overview.py 同口径的独立 fetch_*，按窗口注入（构造新 dict，不可变）。
    print(">> 补齐 KPI（达成率/续保率/增长率）...")
    standard_rows = [
        ({
            **dict(row),
            "plan_completion_pct":       fetch_plan_completion(con, args.org, args.time_field, s, e, level=args.level),
            "renewal_rate_pct":          fetch_renewal_rate(con, args.org, e, level=args.level),
            "premium_growth_pct":        fetch_premium_growth(con, args.org, args.time_field, s, e, level=args.level),
            "household_share_pct":       fetch_household_share(con, args.org, args.time_field, s, e, level=args.level),
            "cross_sell_completion_pct": fetch_cross_sell_completion(con, args.org, e, level=args.level),
        } if row is not None else None)
        for row, (_, s, e) in zip(standard_rows, windows)
    ]

    sample_n = [int(r["policy_count"]) if r is not None else 0 for r in standard_rows]
    total_premiums = [(r["premium"] if r is not None else None) for r in standard_rows]

    # 下钻维度：分公司层用 org_level_3 替代 salesman（salesman 走 team 那条独立路径不产）。
    # org_level_3 是纯 policy 列，天然走 multi_dim_periods_query。
    drill_dims = list(DRILL_DIMS) + (["org_level_3"] if is_branch else [])

    # v1.19：取多维下钻数据（5 窗 × N 维），供业务属性 sections + 下钻页生成器共享
    print(f">> 取多维下钻数据（5 窗 × {len(drill_dims)} 维）...")
    if is_branch:
        where_clause = f"YEAR({args.time_field}) = ?"
        params = [args.year]
    else:
        where_clause = f"org_level_3 = ? AND YEAR({args.time_field}) = ?"
        params = [args.org, args.year]
    drill_long_df = multi_dim_periods_query(
        con,
        where_clause=where_clause,
        params=params,
        periods=windows,
        dim_keys=drill_dims,
        time_field=args.time_field,
    )
    # team 维度走独立派生查询（JOIN plan.parquet level='salesman' 派生归属）。
    # 分公司层：仅 team（Top20 按签单保费 YTD）；三级机构层：team + salesman。
    print(">> 取 team" + ("" if is_branch else "/salesman") + " 下钻数据（JOIN plan.parquet 派生归属）...")
    ts_df = fetch_team_salesman_periods(con, args.org, args.time_field, windows, args.year,
                                        level=args.level, top_n=(20 if is_branch else None))
    if ts_df is not None and not ts_df.empty:
        drill_long_df = pd.concat([drill_long_df, ts_df], ignore_index=True)
    print(f"   长表 shape: {drill_long_df.shape}")

    # A2. 合并维度增长率序列（team 单独路径暂 None）
    print(">> 计算维度增长率序列...")
    all_drill_dim_keys = drill_dims + (["team"] if is_branch else ["team", "salesman"])
    growth_df = fetch_dim_growth_rates(con, args.org, args.time_field, windows, args.year, drill_dims, level=args.level)
    if not growth_df.empty:
        drill_long_df = drill_long_df.merge(
            growth_df[["period", "dim_key", "dim_value", "premium_growth_pct"]],
            on=["period", "dim_key", "dim_value"], how="left",
        )
    else:
        drill_long_df = drill_long_df.copy()
        drill_long_df["premium_growth_pct"] = None

    # A3. 合并维度续保率序列
    print(">> 计算维度续保率序列...")
    renewal_dim_df = fetch_renewal_by_dim(con, args.org, windows, all_drill_dim_keys, level=args.level)
    if not renewal_dim_df.empty:
        # renewal_by_dim 的 dim_value 对 team 维度是原始 team_name，需与 drill_long_df 对齐
        drill_long_df = drill_long_df.merge(
            renewal_dim_df[["period", "dim_key", "dim_value", "renewal_rate_pct"]],
            on=["period", "dim_key", "dim_value"], how="left",
        )
    else:
        if "renewal_rate_pct" not in drill_long_df.columns:
            drill_long_df = drill_long_df.copy()
            drill_long_df["renewal_rate_pct"] = None

    # plan_completion_pct 已由 fetch_team_salesman_periods 计算，7 维留 None
    if "plan_completion_pct" not in drill_long_df.columns:
        drill_long_df = drill_long_df.copy()
        drill_long_df["plan_completion_pct"] = None
    # 7 维（非 team/salesman）确保列存在且为 None
    mask_non_ts = ~drill_long_df["dim_key"].isin(["team", "salesman"])
    drill_long_df.loc[mask_non_ts, "plan_completion_pct"] = None

    # household_share_pct 维度行暂不展示(需 customer_category × dim_key 二维交叉,
    # 目前仅整体行有数据,维度行先填 None 让 V4 超表 "—" 显示;后续可扩 fetch_household_share_by_dim)
    if "household_share_pct" not in drill_long_df.columns:
        drill_long_df = drill_long_df.copy()
        drill_long_df["household_share_pct"] = None

    # 派生占比列：各 dim_value 当窗口保费 / 整体当窗口保费 * 100
    overall_prem_map = {w[0]: (r["premium"] if r is not None else None) for w, r in zip(windows, standard_rows)}
    def _prem_share(row):
        p = row.get("premium")
        overall = overall_prem_map.get(row["period"])
        if p is None or overall is None or overall == 0:
            return None
        return round(float(p) / float(overall) * 100, 2)
    drill_long_df["premium_share_pct"] = drill_long_df.apply(_prem_share, axis=1)

    print(f"   长表最终 shape: {drill_long_df.shape}（含增长率/续保率/达成率/占比列）")

    # A5. 交叉下钻数据（7 维互相交叉，用于 V1/V4 drill panel）
    print(">> 计算维度交叉下钻数据（N 维 × 5 窗）...")
    # 分公司层把 org_level_3 加进交叉维，使「三级机构」可下钻到其他所有业务维度。
    cross_extra_dims = {"org3": ("org_level_3", "org_level_3")} if is_branch else None
    cross_df = fetch_org_cross_data(con, args.org, args.time_field, windows, args.year,
                                    level=args.level, extra_dims=cross_extra_dims)
    # 分公司层：补 team（Top20）作主维的交叉数据 → Top20 团队可下钻全部业务维 + 三级机构。
    if is_branch:
        ytd_label = windows[-1][0]
        top_teams = set(
            drill_long_df[(drill_long_df["dim_key"] == "team") &
                          (drill_long_df["period"] == ytd_label)]["dim_value"].astype(str).tolist()
        )
        print(f">> 计算 Top20 团队交叉下钻数据（team × 业务维{'+三级机构' if cross_extra_dims else ''}）...")
        team_cross = fetch_org_team_cross_data(
            con, args.org, args.time_field, windows, args.year,
            level=args.level, top_teams=top_teams, extra_dims=cross_extra_dims,
        )
        if team_cross is not None and not team_cross.empty:
            cross_df = pd.concat([cross_df, team_cross], ignore_index=True)
            print(f"   team 交叉行数：{len(team_cross)}（Top{len(top_teams)} 团队）")
    org_dd = build_org_drilldown_data(cross_df)
    print(f"   交叉下钻 DD 键数：{len(org_dd)}")

    ctx = SectionContext(
        org=args.org,
        year=args.year,
        cutoff=cutoff_date,
        time_field=args.time_field,
        windows=windows,
        time_labels=time_labels,
        standard_rows=standard_rows,
        sample_n=sample_n,
        total_premiums=total_premiums,
        out_root=None,  # v1.19 回归单文件
        drill_long_df=drill_long_df,
        org_dd=org_dd,  # v1.22 交叉下钻数据
    )

    # ── 三视图分发 ──────────────────────────────────────────────────
    if args.view in ("v1", "all"):
        from render_v1_org import render_v1  # noqa: PLC0415
        render_v1(ctx, drill_long_df, args)
    if args.view in ("v3", "all"):
        from render_v3_org import render_v3  # noqa: PLC0415
        render_v3(ctx, drill_long_df, args)
    if args.view in ("v4", "all"):
        from render_v4_org import render_v4  # noqa: PLC0415
        render_v4(ctx, drill_long_df, args)

    # all 模式额外产出带 Tab 的合集壳页（根治三文件无切换器的 ad-hoc 痛点）
    if args.view == "all":
        from render_combined import render_combined  # noqa: PLC0415
        render_combined(ctx, args)

    # ── 旧版 SPA 模式 ──────────────────────────────────────────────
    if args.view == "legacy":
        _render_legacy(con, ctx, drill_long_df, args, windows, standard_rows,
                       sample_n, total_premiums, time_labels, 口径名)
    return 0


def _render_legacy(con, ctx, drill_long_df, args, windows, standard_rows,
                   sample_n, total_premiums, time_labels, 口径名):
    """旧版 SPA 卡片报告（向后兼容）。"""
    short_org = args.org[:30]
    # 板块编排（10 个 card）：顺序由 sections/__init__.py 的 SECTIONS list 决定
    cards = ""
    nav_items: list = []
    for mod in SECTIONS:
        card, _drills, nav = mod.build(con, ctx)
        cards += card
        nav_items.append((nav["anchor"], nav["label"]))

    # v1.19：批量生成下钻页（每个 (dim, value) 一个隐藏 section）
    print(">> 生成下钻 SPA 子页...")
    drill_pages = build_all_drill_pages(ctx)
    print(f"   下钻子页数：{len(drill_pages)}")

    # 「说明」页：口径 / 阈值 / 公式（跨板块共享，留在主入口）
    metric_whitelist = [
        "variable_cost_ratio_pct",
        "expense_ratio_pct",
        "earned_loss_ratio_pct",
        "earned_loss_freq_pct",
        "plan_completion_pct",
        "premium_growth_pct",
        "household_share_pct",
        "renewal_rate_pct",
        "cross_sell_completion_pct",
    ]
    n_total = sample_n[-1] if sample_n else 0
    pwan = (standard_rows[-1]["premium"] / 10000) if standard_rows[-1] is not None else 0
    info_preface = (
        f"<strong>报告概况</strong>："
        f"三级机构 <strong>{args.org}</strong> · "
        f"{args.year} 年 · {口径名} · 数据截止 <strong>{args.cutoff}</strong> · "
        f"当周样本 <strong>{n_total:,}</strong> 张 · "
        f"当周保费 <strong>{round(pwan):,}</strong> 万元 · "
        f"阈值版本：分公司口径 v1.11"
        "<br><br>"
        "<strong>统一时间口径</strong>：5 列均为「年累计（YTD）」，仅截至日不同——"
        "当周截至 cutoff、上周截至 cutoff-7、上上周截至 cutoff-14、"
        "上月截至上月最后一天、上季度截至上季度最后一天，起始日均为对应年 1 月 1 日。"
        "<br><strong>选用此口径的原因</strong>：满期类率值（赔付率 / 出险率 / 变动成本率）"
        "在 7 天窗口里因满期天数趋近于 0 会严重失真；YTD 累计才稳定可比。"
        "<br><strong>趋势曲线含义</strong>：YTD 累计随时间推进的轨迹；"
        "线条颜色与「当周」（最新列）亮灯一致，圆点末端加深为强调。"
        "<br><strong>「续保率」术语</strong>：本项目所说「续保率」一律是 VIN 去重后的"
        "商业险续保率（应续 = 上年商业险起保 + 交商同保 − 摩托/挂车）。"
        "<br><strong>「计划达成率」术语</strong>：按时间进度修正的保费达成率"
        "= 实际 ÷ (年计划 × 时间进度) × 100。100% = 按节奏均匀达成；"
        "&gt;100% = 节奏快；&lt;100% = 节奏滞后。与项目 premiumPlan.ts 同口径。"
    )
    info_html = render_threshold_card(
        metric_keys=metric_whitelist, preface_html=info_preface,
    )
    info_html = info_html.replace('id="threshold" hidden', 'id="threshold"')

    title_text = f"{short_org} {args.year} 经营诊断周报"

    html = render_page(
        title=title_text,
        kicker=f"三级机构周度盯盘 · {args.year} 年{口径名}",
        cards_html=cards,
        info_html=info_html,
        drill_pages=drill_pages,
        nav_items=nav_items,
        footer_text=f"生成时间 {date.today().isoformat()} ｜ 数据截止 {args.cutoff} "
                    f"｜ 由 diagnose-org-weekly + chexian-report-shell 生成（v1.19）",
    )

    # v1.19：单文件输出 — <output>/<org>_<year>_经营诊断周报.html
    out_path = Path(args.output) / f"{short_org}_{args.year}_经营诊断周报.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"\n报告输出：{out_path}")
    print(f"  文件大小：{out_path.stat().st_size:,} 字节")
    print(f"  下钻子页：{len(drill_pages)} 个（同窗口 showPage 切换）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
