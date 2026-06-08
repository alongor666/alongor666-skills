"""diagnose-loss-development MVP CLI（Phase 1：控制台输出 Card 1 三角形）。

调用：
    python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
        --cutoff 2026-05-15 \
        --project-root '/Users/alongor666/Downloads/底层数据湖DUD/chexian-api'

Phase 1 只验证 SQL 正确性 + Card 1 三角形数据，不渲染 HTML。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

# 脚本式 + 包式双兼容 import
try:
    from .query import (
        DIM_FIELDS, DW_ANCHORS, METRIC_DEFS, PY_START_YEAR,
        build_agg_input_materialized_sql, build_main_grouping_sql,
        build_max_date_sql, build_subdim_batch_sql,
        classify_dim_row, derive_metrics,
    )
    from .render import (
        DIM_CARDS, EXTRA_CSS, METRIC_SWITCHER_JS,
        auto_insight_card1, render_dev_triangle, render_dim_card,
        render_drill_page, drill_slug, select_top_dim_values,
        render_global_controls,
    )
except ImportError:  # pragma: no cover
    from query import (  # type: ignore[no-redef]
        DIM_FIELDS, DW_ANCHORS, METRIC_DEFS, PY_START_YEAR,
        build_agg_input_materialized_sql, build_main_grouping_sql,
        build_max_date_sql, build_subdim_batch_sql,
        classify_dim_row, derive_metrics,
    )
    from render import (  # type: ignore[no-redef]
        DIM_CARDS, EXTRA_CSS, METRIC_SWITCHER_JS,
        auto_insight_card1, render_dev_triangle, render_dim_card,
        render_drill_page, drill_slug, select_top_dim_values,
        render_global_controls,
    )

# 复用 dhr_lib（2026-05-17 重命名：原 diagnose-html-render → chexian-report-shell）
try:
    from ._shell import SHELL_ROOT as _DHR_PATH  # 路径解析集中本技能一处（ADR-001）
except ImportError:
    from _shell import SHELL_ROOT as _DHR_PATH  # type: ignore[no-redef]
if str(_DHR_PATH) not in sys.path:
    sys.path.insert(0, str(_DHR_PATH))
from lib import render_card, render_page  # type: ignore[no-redef]


def auto_cutoff(con: duckdb.DuckDBPyConnection, project_root: Path) -> date:
    """从数据中取 MAX(policy_date) 作为 cutoff 兜底。"""
    sql = build_max_date_sql(project_root)
    val = con.execute(sql).fetchone()[0]
    if val is None:
        raise RuntimeError("Cannot determine cutoff: no policy_date in parquet")
    return val if isinstance(val, date) else val.date()


def run(cutoff: date | None, project_root: Path) -> dict:
    """v2.1 二段式架构：物化 agg_input 为 TEMP TABLE，再跑主 SQL。

    保留 con 以便后续 generate_drill_pages 复用 TEMP TABLE 跑 batch SQL（避免重复扫 parquet）。

    返回：{"con": DuckDBConn, "raw": DataFrame, "derived": DataFrame, "cutoff": date}
    """
    con = duckdb.connect(":memory:")
    if cutoff is None:
        cutoff = auto_cutoff(con, project_root)

    # 阶段 1：物化 agg_input（policy_no × 6 DW × 12 dim + 5 指标原料）为 TEMP TABLE
    agg_sql = build_agg_input_materialized_sql(cutoff, project_root)
    con.execute(f"CREATE TEMP TABLE agg_input AS {agg_sql}")

    # 阶段 2：主 SQL（一维 + 整体 GROUPING SETS）
    raw = con.execute(build_main_grouping_sql()).df()
    derived = derive_metrics(raw)
    derived[["dim_key", "dim_value"]] = derived.apply(
        lambda r: pd.Series(classify_dim_row(r)), axis=1,
    )
    return {"con": con, "raw": raw, "derived": derived, "cutoff": cutoff}


def query_subdim_data(
    con, parent_dim: str, parent_value: str, child_dims: list[str],
) -> dict[str, "pd.DataFrame"]:
    """从 TEMP TABLE agg_input 跑 batch SQL，返回该父维度值在 N 个副维度的 derived 数据。

    返回字典：{child_dim: derived_df}，其中 derived_df 含 (dim_key, dim_value, py, dw_days, 5 指标 + completeness)。
    """
    batch_sql = build_subdim_batch_sql(parent_dim, parent_value, child_dims)
    raw_batch = con.execute(batch_sql).df()
    result: dict[str, pd.DataFrame] = {}
    if raw_batch.empty:
        return result
    for child_dim in child_dims:
        if child_dim == parent_dim:
            continue
        sub = raw_batch[raw_batch["child_dim"] == child_dim].copy()
        if sub.empty:
            continue
        # 派生 5 指标 + completeness（与主 derived 同公式）
        sub = derive_metrics(sub)
        # 适配 render_dim_card 所需的 dim_key/dim_value 列
        sub["dim_key"] = child_dim
        sub["dim_value"] = sub["child_value"].astype(str)
        result[child_dim] = sub
    return result


def print_card1_triangle(df: pd.DataFrame, cutoff: date) -> None:
    """Phase 1 验证：打印 Card 1 整体三角形（PY × DW × 5 指标）。"""
    overall = df[df["dim_key"] == "__overall__"].copy()
    overall = overall.sort_values(["py", "dw_days"], ascending=[False, True])

    print(f"\n{'='*80}")
    print(f"Card 1 · 整体发展三角形 · cutoff = {cutoff}")
    print(f"{'='*80}\n")

    for metric_id, metric_name, _kind, _th in METRIC_DEFS:
        print(f"━━ {metric_name} ({metric_id}) ━━")
        pivot = overall.pivot(index="py", columns="dw_days", values=metric_id)
        pivot = pivot.reindex(columns=DW_ANCHORS)
        pivot.index = [f"{int(py)} PY" for py in pivot.index]
        pivot.columns = [f"{d}d" for d in pivot.columns]
        print(pivot.round(2).to_string(na_rep="—"))
        print()

    # 完成度（用于 △ 标记）
    print("━━ 完成度 (completeness_ratio) ━━")
    pivot = overall.pivot(index="py", columns="dw_days", values="completeness_ratio")
    pivot = pivot.reindex(columns=DW_ANCHORS)
    pivot.index = [f"{int(py)} PY" for py in pivot.index]
    pivot.columns = [f"{d}d" for d in pivot.columns]
    print(pivot.round(3).to_string(na_rep="—"))
    print()

    # 保单覆盖
    print("━━ 保单数 ━━")
    pivot = overall.pivot(index="py", columns="dw_days", values="policy_count")
    pivot = pivot.reindex(columns=DW_ANCHORS)
    pivot.index = [f"{int(py)} PY" for py in pivot.index]
    pivot.columns = [f"{d}d" for d in pivot.columns]
    print(pivot.fillna(0).astype(int).to_string())
    print()


# 当前 PY 默认：优先 2025（用户重点关注年份），fallback 到最近一个 365d 完整观察的 PY
PREFERRED_CURRENT_PY = 2025


def _pick_current_py(derived: pd.DataFrame) -> int:
    """选当前 PY：2025 在数据中存在则优先，否则取最近 365d 完整观察的 PY。"""
    available = {int(p) for p in derived["py"].unique()}
    if PREFERRED_CURRENT_PY in available:
        return PREFERRED_CURRENT_PY
    df_365_complete = derived[
        (derived["dw_days"] == 365)
        & (derived["completeness_ratio"] >= 0.95)
        & (derived["dim_key"] == "__overall__")
    ]
    if not df_365_complete.empty:
        return int(df_365_complete["py"].max())
    return int(derived["py"].max())


def render_html(derived: pd.DataFrame, cutoff: date) -> str:
    """渲染完整 HTML 报告（Card 1 整体三角形 + Card 2-13 十二维度切片）。"""
    overall = derived[derived["dim_key"] == "__overall__"].copy()
    total_policies = int(overall["policy_count"].max() or 0)
    total_premium = float(overall["earned_premium_sum"].max() or 0.0)
    py_count = overall["py"].nunique()

    # Card 1 body = 关键发现 + 三角形
    insight = auto_insight_card1(overall)
    triangle = render_dev_triangle(overall, table_id="card1-triangle")
    card1_body = f"{insight}{triangle}"

    card1_subtitle = (
        "<strong>满期口径</strong>：满期保费 = 保费 × min(观察期, 保单期) / 保单期；"
        "<strong>赔款口径</strong>：已结案取已决金额，未结案取未决金额（项目标准）；"
        "<strong>截尾标记</strong>：✓ 完整观察 / △ 部分完成（&lt; 95%）/ — 未到。"
        "<br><br><strong>顶部全局切换</strong>：指标（满期赔付率 · 满期出险率 · 案均赔款 · 满期保费 · 人伤案占比 · 人伤金额占比）"
        "联动整体三角与全部维度卡；保单年度切换作用于各维度卡（整体三角按年成行、全程可见）。"
        "各维度卡内行按当年满期保费从大到小排序。"
    )
    card1 = render_card(
        title="整体发展三角形",
        subtitle=card1_subtitle,
        body=card1_body,
        card_id="card-overall",
    )

    current_py = _pick_current_py(derived)
    py_options: list[int] = sorted({int(p) for p in derived["py"].unique()})
    dim_cards_html: list[str] = []
    nav_items: list[tuple[str, str]] = [("card-overall", "整体发展三角形")]
    for cfg in DIM_CARDS:
        c = render_dim_card(
            derived, dim_cfg=cfg, current_py=current_py,
            overall_df=overall, py_options=py_options,
        )
        if c:
            dim_cards_html.append(c)
            nav_items.append((f"card-{cfg['key']}", cfg["label"]))

    page_meta_text = (
        f"{total_policies / 10000:,.2f} 万单 · "
        f"{total_premium / 10000:,.0f} 万元 · "
        f"{py_count} 个保单年度 · 当前 {current_py} 年"
    )

    controls = render_global_controls(py_options, current_py)
    cards_html = (
        EXTRA_CSS + controls + card1 + "".join(dim_cards_html) + METRIC_SWITCHER_JS
    )

    html = render_page(
        title=f"多年车险保单赔付发展对比 · {cutoff.isoformat()}",
        cards_html=cards_html,
        meta_text=page_meta_text,
        footer_text=f"数据截止 {cutoff.isoformat()} · 由 skill diagnose-loss-development 生成",
        nav_items=nav_items,
    )
    return html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="diagnose-loss-development — PY × DW 满期赔付发展三角形",
    )
    p.add_argument("--cutoff", type=str, default=None,
                   help="截止日期 YYYY-MM-DD；默认取 MAX(policy_date)")
    p.add_argument("--project-root", type=str, required=True,
                   help="chexian-api 项目根目录绝对路径")
    p.add_argument("--out", type=str, default=None,
                   help="本地预览模式：输出 HTML 文件路径；不指定则控制台打印 Card 1")
    p.add_argument("--deploy", action="store_true",
                   help="部署模式：输出到 {project-root}/server/data/reports/"
                        "diagnose-loss-development/{cutoff}/，与 --out 互斥；"
                        "后续 sync-vps.mjs 自动同步到 VPS")
    p.add_argument("--report-id", type=str, default="diagnose-loss-development",
                   help="--deploy 模式下的报告 ID（须与后端 ALLOWED_REPORT_IDS 一致）")
    return p.parse_args(argv)


def _resolve_display_label(raw: str, dim_cfg: dict) -> str:
    """复用 render.py 中维度值的显示逻辑（value_shortener 优先，否则 value_labels 映射）。"""
    value_shortener = dim_cfg.get("value_shortener")
    value_labels = dim_cfg.get("value_labels", {})
    if value_shortener:
        return value_shortener(raw) or raw
    return value_labels.get(raw, raw)


def generate_drill_pages(
    con,
    derived,
    cutoff: date,
    drill_dir: Path,
    main_page_filename: str,
) -> int:
    """v2.1：为主页可见的所有维度值生成下钻子页（总体 Card + 11 副维度 Card）。

    每个父维度值跑 1 次 batch SQL（FROM TEMP TABLE agg_input），输出 11 副维度数据。
    路径布局：{drill_dir}/{dim_key}/{slug}.html
    """
    current_py = _pick_current_py(derived)
    py_options: list[int] = sorted({int(p) for p in derived["py"].unique()})
    child_dims = list(DIM_FIELDS)  # 所有 12 维度（query_subdim_data 内部会跳过父维度自身）
    written = 0
    for cfg in DIM_CARDS:
        key = cfg["key"]
        dim_card_label = cfg["label"]
        values = select_top_dim_values(derived, cfg, current_py)
        if not values:
            continue
        key_dir = drill_dir / key
        key_dir.mkdir(parents=True, exist_ok=True)
        for raw in values:
            display_label = _resolve_display_label(raw, cfg)
            sub_data = query_subdim_data(con, key, raw, child_dims)
            html_str = render_drill_page(
                derived,
                dim_key=key, dim_value=raw,
                display_label=display_label, dim_card_label=dim_card_label,
                sub_data=sub_data,
                cutoff=cutoff,
                current_py=current_py,
                py_options=py_options,
                dim_cards=DIM_CARDS,
                main_page_filename=main_page_filename,
            )
            if not html_str:
                continue
            (key_dir / f"{drill_slug(raw)}.html").write_text(html_str, encoding="utf-8")
            written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cutoff = None
    if args.cutoff:
        cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").date()
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.exists():
        print(f"[ERR] project_root not found: {project_root}", file=sys.stderr)
        return 2

    if args.deploy and args.out:
        print("[ERR] --deploy 与 --out 互斥", file=sys.stderr)
        return 2

    result = run(cutoff, project_root)
    try:
        if args.deploy:
            actual_cutoff = result["cutoff"].isoformat()
            out_path = (
                project_root / "server/data/reports" / args.report_id
                / actual_cutoff / "preview-mvp.html"
            )
        elif args.out:
            out_path = Path(args.out).expanduser().resolve()
        else:
            print_card1_triangle(result["derived"], result["cutoff"])
            return 0

        out_path.parent.mkdir(parents=True, exist_ok=True)
        html = render_html(result["derived"], result["cutoff"])
        out_path.write_text(html, encoding="utf-8")
        print(f"[OK] 主页: {out_path}")
        drill_dir = out_path.parent / "drill"
        n_drill = generate_drill_pages(
            result["con"], result["derived"], result["cutoff"],
            drill_dir=drill_dir, main_page_filename=out_path.name,
        )
        print(f"[OK] 下钻子页: {n_drill} 个 → {drill_dir}/")
        if args.deploy:
            url_base = (
                f"https://chexian.cretvalu.com/api/reports/"
                f"{args.report_id}/{result['cutoff'].isoformat()}"
            )
            print(f"[OK] 部署 URL: {url_base}/preview-mvp.html")
            print("[NEXT] 同步 VPS: cd <project-root> && node scripts/sync-vps.mjs")
    finally:
        result["con"].close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
