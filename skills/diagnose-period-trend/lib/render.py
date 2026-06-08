"""HTML 渲染：表 1（7 时间窗 × 7 指标，可转置）+ 表 2（客户类别 × 时间窗，指标可切换）
+ 表 3（三级机构 × 时间窗，4 级层次：四川 / 同城 / 异地 / 其他，可折叠 + 切换指标动态重排）。

依赖 ~/.claude/skills/chexian-report-shell/lib/ 的 alerts.light / format.fmt_num。
"""
from __future__ import annotations

from html import escape
from typing import Optional

import pandas as pd

# 引入 chexian-report-shell 共享库（亮灯 + 格式化）——通过 cli.py 已注册的 dhr_lib 模块取
# 若本模块被独立调用（如测试场景），按需 lazy-load dhr_lib
# 2026-05-17 重命名：原 diagnose-html-render → chexian-report-shell
import sys as _sys

if "dhr_lib" not in _sys.modules:
    import importlib.util as _ilu
    from pathlib import Path as _P
    _dhr_lib_path = next(
        (p / "chexian-report-shell" / "lib" for p in _P(__file__).resolve().parents
         if p.name == "skills" and (p / "chexian-report-shell").is_dir()),
        _P.home() / ".claude/skills/chexian-report-shell/lib",  # 兜底（ADR-001）
    )
    _spec = _ilu.spec_from_file_location(
        "dhr_lib", str(_dhr_lib_path / "__init__.py"),
        submodule_search_locations=[str(_dhr_lib_path)],
    )
    _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _sys.modules["dhr_lib"] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

import dhr_lib  # type: ignore[import-not-found]  # noqa: E402
light = dhr_lib.light
fmt_num = dhr_lib.fmt_num

# 本 skill 内部模块（绝对 import；cli.py 已把本 skill lib/ 放到 sys.path[0]）
try:
    from .periods import Period
    from .query import METRIC_DEFS, short_category
    from .org_groups import GROUP_LABELS
except ImportError:
    from periods import Period  # type: ignore[no-redef]
    from query import METRIC_DEFS, short_category  # type: ignore[no-redef]
    from org_groups import GROUP_LABELS  # type: ignore[no-redef]


def fmt_or_dash(v, kind: str) -> str:
    if v is None or pd.isna(v):
        return "—"
    if kind == "wan2":
        # 万 + 2 位小数；单位"万"已在表头/按钮 label 内体现，单元格只放数字
        return f"{v / 10000:,.2f}"
    return fmt_num(v, kind)


def light_cls(metric_alert_key: Optional[str], val, n: int) -> str:
    if metric_alert_key is None:
        return ""
    cls, _ = light(metric_alert_key, val, int(n) if pd.notna(n) else 0)
    return cls


def render_table_1(overall: pd.DataFrame, periods: list[Period],
                   instance_id: str = "main") -> str:
    """表 1：正向（7 行指标 × 7 列时间窗）+ 转置（7 行 × 7 列），按钮切换。

    instance_id：多实例命名空间。主页传 "main"；下钻页传 "drill-cat-XXX" 等，
    避免 ID 冲突（同一页面有多个表 1 时 toggleTranspose 找错元素）。
    """
    overall = overall.set_index("period_label").reindex([p.label for p in periods])

    # ── 正向：行=指标, 列=趋势 + 时间窗 ──
    th_normal = "".join(f"<th class='num-th'>{escape(p.label)}</th>" for p in periods)
    rows_normal = []
    for key, name, kind, alert in METRIC_DEFS:
        # 该指标 6 周期值（按时序从早到晚）+ 末值亮灯
        values = [overall.loc[p.label].get(key) if p.label in overall.index else None for p in periods]
        last_row = overall.iloc[-1] if len(overall) else None
        last_n = int(last_row["policy_count"]) if last_row is not None and pd.notna(last_row.get("policy_count")) else 0
        last_val = values[-1] if values else None
        last_alert = light_cls(alert, last_val, last_n)
        trend_html = _sparkline_svg(values, last_alert, _min_range_for_kind(kind))

        tds = []
        for p in periods:
            row = overall.loc[p.label]
            v = row.get(key)
            n = int(row["policy_count"]) if pd.notna(row.get("policy_count")) else 0
            cls = light_cls(alert, v, n)
            dot_cls = cls.replace("alert-", "dot-") if cls else "dot-empty"
            tds.append(
                f'<td class="num {cls} has-dot">'
                f'<span class="num-val">{fmt_or_dash(v, kind)}</span>'
                f'<span class="dot {dot_cls}" aria-hidden="true"></span></td>'
            )
        rows_normal.append(
            f"<tr><td class='dim-cell'><strong>{escape(name)}</strong></td>"
            f"<td class='trend-cell'>{trend_html}</td>"
            f"{''.join(tds)}</tr>"
        )

    table_normal = (
        f"<table class='data-table' id='table-1-normal-{escape(instance_id)}' data-instance='{escape(instance_id)}'>"
        f"<thead><tr><th>指标</th><th class='trend-th'>6 期趋势</th>{th_normal}</tr></thead>"
        f"<tbody>{''.join(rows_normal)}</tbody></table>"
    )

    # ── 转置：行=时间窗, 列=指标 ──
    th_t = "".join(f"<th class='num-th'>{escape(name)}</th>" for _, name, _, _ in METRIC_DEFS)
    rows_t = []
    for p in periods:
        row = overall.loc[p.label]
        tds = []
        for key, _, kind, alert in METRIC_DEFS:
            v = row.get(key)
            n = int(row["policy_count"]) if pd.notna(row.get("policy_count")) else 0
            cls = light_cls(alert, v, n)
            dot_cls = cls.replace("alert-", "dot-") if cls else "dot-empty"
            tds.append(
                f'<td class="num {cls} has-dot">'
                f'<span class="num-val">{fmt_or_dash(v, kind)}</span>'
                f'<span class="dot {dot_cls}" aria-hidden="true"></span></td>'
            )
        rows_t.append(f"<tr><td class='dim-cell'><strong>{escape(p.label)}</strong></td>{''.join(tds)}</tr>")

    table_t = (
        f"<table class='data-table' id='table-1-transposed-{escape(instance_id)}' "
        f"data-instance='{escape(instance_id)}' style='display:none'>"
        f"<thead><tr><th>时间窗</th>{th_t}</tr></thead>"
        f"<tbody>{''.join(rows_t)}</tbody></table>"
    )

    button = (
        f"<div class='table-actions'>"
        f"<button class='btn-toggle' onclick=\"toggleTranspose1('{escape(instance_id)}')\">"
        f"⇄ 行列转置</button></div>"
    )
    return button + table_normal + table_t


def render_table_2(by_cat: pd.DataFrame, periods: list[Period],
                   category_order: list[str],
                   drillable_dims: Optional[dict] = None,
                   instance_id: str = "main",
                   metric_defs=None,
                   dim_col: str = "customer_category",
                   dim_header: str = "客户类别",
                   label_func=None,
                   overall: Optional[pd.DataFrame] = None) -> str:
    """表 2 / 辅助二值表：行=指定维度, 列=时间窗。

    dim_col: 维度字段名（默认 customer_category；aux 维度传 is_nev/is_new_car 等）
    dim_header: 表头首列文案（默认"客户类别"）
    label_func: 维度原始值 → 显示标签 映射函数；默认 short_category（适配客户类别）
    drillable_dims: {dim_value: page_id} 可下钻配置；aux 表通常 None
    overall: 可选；若传入则在 tbody 顶部插入"整体"基准行（class=row-total + 不可下钻）
    """
    drillable_dims = drillable_dims or {}
    metric_defs = metric_defs or METRIC_DEFS
    label_func = label_func or short_category
    by_cat = by_cat.set_index([dim_col, "period_label"])

    # v1.25 P5：表顶"整体"基准行——把 overall 注入 by_cat（虚拟 dim 值 __OVERALL__）
    if overall is not None and not overall.empty:
        overall_idx = overall.set_index("period_label")
        overall_rows = []
        for p in periods:
            if p.label in overall_idx.index:
                r = overall_idx.loc[p.label].to_dict()
                r[dim_col] = "__OVERALL__"
                r["period_label"] = p.label
                overall_rows.append(r)
        if overall_rows:
            overall_df = pd.DataFrame(overall_rows).set_index([dim_col, "period_label"])
            by_cat = pd.concat([overall_df, by_cat])
            category_order = ["__OVERALL__"] + list(category_order)

    # ── 顶部指标切换按钮组（按 instance 隔离） ──
    btn_html = "<div class='table-actions metric-switcher'><span class='switcher-label'>切换指标：</span>"
    for i, (key, name, _, _) in enumerate(metric_defs):
        active = " active" if i == 0 else ""
        btn_html += (
            f"<button class='btn-metric{active}' data-metric='{key}' "
            f"data-instance='{escape(instance_id)}' data-table='2' "
            f"onclick=\"switchMetric2('{key}', '{escape(instance_id)}')\">"
            f"{escape(name)}</button>"
        )
    btn_html += "</div>"

    # ── 表头：维度首列 + 趋势列 + 6 周期列（周期列可点击排序） ──
    th = "".join(
        f"<th class='num-th sortable' data-period-idx='{i}' "
        f"onclick=\"sortByColumn('table-2-{escape(instance_id)}', {i})\">"
        f"{escape(p.label)}<span class='sort-arrow'>⇅</span></th>"
        for i, p in enumerate(periods)
    )
    head_html = (
        f"<thead><tr><th>{escape(dim_header)}</th><th class='trend-th'>6 期趋势</th>{th}</tr></thead>"
    )

    # ── tbody ──
    rows_html = []
    for cat in category_order:
        # 先收集该 cat 在 6 周期下的全 7 指标值 + 末值亮灯（供 trend cell + 重绘用）
        metric_vals: dict[str, list] = {}
        metric_alerts_last: dict[str, str] = {}
        last_n_for_alert = 0
        try:
            last_row = by_cat.loc[(cat, periods[-1].label)]
            last_n_for_alert = int(last_row["policy_count"]) if pd.notna(last_row.get("policy_count")) else 0
        except KeyError:
            last_row = None
        for key, _, _, alert in metric_defs:
            vals: list = []
            for p in periods:
                try:
                    vals.append(by_cat.loc[(cat, p.label)].get(key))
                except KeyError:
                    vals.append(None)
            metric_vals[key] = vals
            metric_alerts_last[key] = light_cls(alert, vals[-1] if vals else None, last_n_for_alert) if alert else ""
        default_key = metric_defs[0][0]
        trend_cell_html = _build_trend_cell_html(
            metric_vals[default_key], metric_alerts_last[default_key],
            metric_vals, metric_alerts_last,
            metric_defs=metric_defs, default_key=default_key,
        )

        cells = []
        for p in periods:
            try:
                row = by_cat.loc[(cat, p.label)]
            except KeyError:
                # 该 (类别, 时间窗) 组合无数据；色点用 dot-empty 占位保对齐
                placeholder_data = " ".join(f'data-{k}="—" data-light-{k}=""' for k, *_ in metric_defs)
                cells.append(
                    f"<td class='num data-cell has-dot' {placeholder_data}>"
                    f"<span class='num-val'>—</span>"
                    f"<span class='dot dot-empty' aria-hidden='true'></span></td>"
                )
                continue
            n = int(row["policy_count"]) if pd.notna(row["policy_count"]) else 0

            data_attrs = []
            light_attrs = []
            display_text = "—"
            display_cls = ""
            for i, (key, _, kind, alert) in enumerate(metric_defs):
                v = row.get(key)
                text = fmt_or_dash(v, kind)
                data_attrs.append(f'data-{key}="{escape(text)}"')
                cls = light_cls(alert, v, n)
                light_attrs.append(f'data-light-{key}="{cls}"')
                if i == 0:  # 默认显示第一个：变动成本率
                    display_text = text
                    display_cls = cls
            display_dot_cls = display_cls.replace("alert-", "dot-") if display_cls else "dot-empty"
            cells.append(
                f'<td class="num data-cell {display_cls} has-dot" '
                f'{" ".join(data_attrs)} {" ".join(light_attrs)}>'
                f'<span class="num-val">{display_text}</span>'
                f'<span class="dot {display_dot_cls}" aria-hidden="true"></span></td>'
            )
        drill_page = drillable_dims.get(cat)
        is_total = (cat == "__OVERALL__")
        if is_total:
            tr_open = '<tr class="row-total">'
            dim_cls = "dim-cell"
            display_label = "整体"
        elif drill_page:
            tr_open = (
                f'<tr class="expandable" '
                f'onclick="showPage(\'{escape(drill_page)}\')">'
            )
            dim_cls = "dim-cell dim-link"
            display_label = label_func(cat)
        else:
            tr_open = "<tr>"
            dim_cls = "dim-cell"
            display_label = label_func(cat)
        rows_html.append(
            f"{tr_open}<td class='{dim_cls}'><strong>{escape(display_label)}</strong></td>"
            f"{trend_cell_html}"
            f"{''.join(cells)}</tr>"
        )

    table = (
        f"<table class='data-table' id='table-2-{escape(instance_id)}' "
        f"data-instance='{escape(instance_id)}'>{head_html}"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )
    return btn_html + table


# ── 表 3 辅助函数（_cell_inline 与 _empty_cell_html 与表 2 的内联代码功能等价；
#     这里独立成函数仅服务于表 3，不影响表 2 输出） ──

def _empty_cell_html(metric_defs=None) -> str:
    metric_defs = metric_defs or METRIC_DEFS
    placeholder_data = " ".join(
        f'data-{k}="—" data-light-{k}=""' for k, *_ in metric_defs
    )
    return (
        f"<td class='num data-cell has-dot' {placeholder_data}>"
        f"<span class='num-val'>—</span>"
        f"<span class='dot dot-empty' aria-hidden='true'></span></td>"
    )


def _cell_inline(row, n: int, metric_defs=None) -> str:
    """单元格：内嵌全 N 指标值 + 亮灯 class，默认显示第 0 个。"""
    metric_defs = metric_defs or METRIC_DEFS
    data_attrs: list[str] = []
    light_attrs: list[str] = []
    display_text = "—"
    display_cls = ""
    for i, (key, _, kind, alert) in enumerate(metric_defs):
        v = row.get(key)
        text = fmt_or_dash(v, kind)
        data_attrs.append(f'data-{key}="{escape(text)}"')
        cls = light_cls(alert, v, n)
        light_attrs.append(f'data-light-{key}="{cls}"')
        if i == 0:
            display_text = text
            display_cls = cls
    display_dot_cls = display_cls.replace("alert-", "dot-") if display_cls else "dot-empty"
    return (
        f'<td class="num data-cell {display_cls} has-dot" '
        f'{" ".join(data_attrs)} {" ".join(light_attrs)}>'
        f'<span class="num-val">{display_text}</span>'
        f'<span class="dot {display_dot_cls}" aria-hidden="true"></span></td>'
    )


def _sortvals_attrs(row, metric_defs=None) -> str:
    """生成 data-sortval-{metric}="<raw_float>" 串。NaN 留空字符串。"""
    metric_defs = metric_defs or METRIC_DEFS
    parts: list[str] = []
    for key, *_ in metric_defs:
        v = None if row is None else row.get(key)
        if v is None or pd.isna(v):
            parts.append(f'data-sortval-{key}=""')
        else:
            parts.append(f'data-sortval-{key}="{float(v):.6g}"')
    return " ".join(parts)


def _trend_cell_from_df(indexed_df: pd.DataFrame, periods: list[Period], metric_defs=None) -> str:
    """从一个 (period_label index) DataFrame 抽取指标 × 6 周期数据，返回 trend cell HTML。"""
    metric_defs = metric_defs or METRIC_DEFS
    metric_vals: dict[str, list] = {}
    metric_alerts_last: dict[str, str] = {}
    last_label = periods[-1].label
    last_n = 0
    try:
        last_row = indexed_df.loc[last_label]
        last_n = int(last_row["policy_count"]) if pd.notna(last_row.get("policy_count")) else 0
    except KeyError:
        pass
    for key, _, _, alert in metric_defs:
        vals: list = []
        for p in periods:
            try:
                vals.append(indexed_df.loc[p.label].get(key))
            except KeyError:
                vals.append(None)
        metric_vals[key] = vals
        metric_alerts_last[key] = light_cls(alert, vals[-1] if vals else None, last_n) if alert else ""
    default_key = metric_defs[0][0]
    return _build_trend_cell_html(
        metric_vals[default_key], metric_alerts_last[default_key],
        metric_vals, metric_alerts_last,
        metric_defs=metric_defs, default_key=default_key,
    )


def _render_agg_row(agg_df: pd.DataFrame, periods: list[Period],
                    label: str, group_key: Optional[str],
                    instance_id: str = "main", metric_defs=None) -> str:
    """聚合行渲染。group_key=None → 四川（不可折叠 agg-root）；其他 → 可折叠。"""
    metric_defs = metric_defs or METRIC_DEFS
    if agg_df is None or agg_df.empty:
        return ""
    agg = agg_df.set_index("period_label")
    cells: list[str] = []
    for p in periods:
        try:
            row = agg.loc[p.label]
        except KeyError:
            cells.append(_empty_cell_html(metric_defs))
            continue
        n = int(row["policy_count"]) if pd.notna(row["policy_count"]) else 0
        cells.append(_cell_inline(row, n, metric_defs))

    trend_cell = _trend_cell_from_df(agg, periods, metric_defs)

    if group_key is None:
        return (
            f'<tr class="agg-row agg-root" data-instance="{escape(instance_id)}">'
            f'<td class="dim-cell"><strong>{escape(label)}</strong></td>'
            f'{trend_cell}{"".join(cells)}</tr>'
        )
    return (
        f'<tr class="agg-row" data-group="{escape(group_key)}" '
        f'data-instance="{escape(instance_id)}" '
        f'onclick="toggleOrgGroup(\'{escape(group_key)}\', \'{escape(instance_id)}\')">'
        f'<td class="dim-cell"><span class="caret">▶</span>'
        f'<strong>{escape(label)}</strong></td>'
        f'{trend_cell}{"".join(cells)}</tr>'
    )


def _render_child_rows(df_long: pd.DataFrame, periods: list[Period],
                       group_key: str,
                       drillable_dims: Optional[dict] = None,
                       instance_id: str = "main",
                       metric_defs=None) -> list[str]:
    """子机构行。按 YTD（第一个 period）变动成本率降序排（render 时一次性）；
    切换指标后由 JS 按 data-sortval-{metric} 重排。

    drillable_dims: {org_level_3: page_id} 触发该子行可下钻（expandable + dim-link）。
    注：聚合行不下钻（已被 toggleOrgGroup 占用 onclick）。
    """
    drillable_dims = drillable_dims or {}
    metric_defs = metric_defs or METRIC_DEFS
    if df_long is None or df_long.empty:
        return []

    df_indexed = df_long.set_index(["org_level_3", "period_label"])
    orgs = df_long["org_level_3"].unique().tolist()
    first_period = periods[0].label

    def _sort_key(org: str) -> float:
        try:
            v = df_indexed.loc[(org, first_period), "variable_cost_ratio"]
        except KeyError:
            return float("inf")
        if v is None or pd.isna(v):
            return float("inf")
        return -float(v)  # 降序

    orgs_sorted = sorted(orgs, key=_sort_key)

    out: list[str] = []
    for org in orgs_sorted:
        try:
            ytd_row = df_indexed.loc[(org, first_period)]
        except KeyError:
            ytd_row = None
        sortval_attrs = _sortvals_attrs(ytd_row, metric_defs)

        # 该 org 的"period_label index"子表（仅当前 org 在所有 period 的行）
        try:
            org_indexed = df_indexed.loc[org]
        except KeyError:
            org_indexed = pd.DataFrame()
        trend_cell = _trend_cell_from_df(org_indexed, periods, metric_defs) if not org_indexed.empty else "<td class='trend-cell'><span class='spark-empty'>—</span></td>"

        cells: list[str] = []
        for p in periods:
            try:
                row = df_indexed.loc[(org, p.label)]
            except KeyError:
                cells.append(_empty_cell_html(metric_defs))
                continue
            n = int(row["policy_count"]) if pd.notna(row["policy_count"]) else 0
            cells.append(_cell_inline(row, n, metric_defs))

        drill_page = drillable_dims.get(org)
        if drill_page:
            # 子行可下钻：onclick 触发 showPage（与 toggleOrgGroup 互不冲突——子行没有 caret）
            # dim 文字用 <strong> 包裹与表 2 客户类别保持格式一致（蓝色 + 粗体）
            extra_class = " expandable"
            extra_onclick = f' onclick="showPage(\'{escape(drill_page)}\')"'
            dim_cls = "dim-cell child-indent dim-link"
            dim_text = f"<strong>{escape(org)}</strong>"
        else:
            extra_class = ""
            extra_onclick = ""
            dim_cls = "dim-cell child-indent"
            dim_text = escape(org)
        out.append(
            f'<tr class="child-row child-{group_key}{extra_class}" '
            f'data-group="{escape(group_key)}" '
            f'data-instance="{escape(instance_id)}" '
            f'data-row-key="{escape(org)}" {sortval_attrs}{extra_onclick} hidden>'
            f'<td class="{dim_cls}">{dim_text}</td>'
            f'{trend_cell}{"".join(cells)}</tr>'
        )
    return out


def render_table_3(
    sichuan_agg: pd.DataFrame,
    sc_agg: pd.DataFrame, rm_agg: pd.DataFrame, other_agg: pd.DataFrame,
    sc_rows: pd.DataFrame, rm_rows: pd.DataFrame, other_rows: pd.DataFrame,
    periods: list[Period],
    drillable_dims: Optional[dict] = None,
    instance_id: str = "main",
    metric_defs=None,
) -> str:
    """表 3：三级机构 × 时间窗。4 层聚合 + 可折叠子机构 + 切换指标动态重排。

    DOM 顺序契约：同组聚合行紧邻同组子行连续放置，组间不交错（JS 重排依赖此结构）。
    drillable_dims: {org_level_3: page_id} 仅作用于子机构行；聚合行不下钻。
    instance_id: 多实例命名空间。
    """
    drillable_dims = drillable_dims or {}
    metric_defs = metric_defs or METRIC_DEFS
    # 顶部指标切换按钮组（独立 class btn-metric-3 + data-instance 隔离）
    btn_html = "<div class='table-actions metric-switcher'><span class='switcher-label'>切换指标：</span>"
    for i, (key, name, _, _) in enumerate(metric_defs):
        active = " active" if i == 0 else ""
        btn_html += (
            f"<button class='btn-metric-3{active}' data-metric='{key}' "
            f"data-instance='{escape(instance_id)}' data-table='3' "
            f"onclick=\"switchMetric3('{key}', '{escape(instance_id)}')\">"
            f"{escape(name)}</button>"
        )
    btn_html += "</div>"

    # 表头：机构首列 + 趋势列 + 6 周期列（周期列可点击排序）
    th = "".join(
        f"<th class='num-th sortable' data-period-idx='{i}' "
        f"onclick=\"sortByColumn('table-3-{escape(instance_id)}', {i})\">"
        f"{escape(p.label)}<span class='sort-arrow'>⇅</span></th>"
        for i, p in enumerate(periods)
    )
    head_html = (
        f"<thead><tr><th>机构</th><th class='trend-th'>6 期趋势</th>{th}</tr></thead>"
    )

    rows: list[str] = []
    # 第 1 行：四川（不可折叠 agg-root）
    rows.append(_render_agg_row(sichuan_agg, periods, "四川", None, instance_id, metric_defs))
    # 第 2 段：同城（汇总）+ 子机构
    rows.append(_render_agg_row(sc_agg, periods, GROUP_LABELS["same-city"], "same-city", instance_id, metric_defs))
    rows.extend(_render_child_rows(sc_rows, periods, "same-city", drillable_dims, instance_id, metric_defs))
    # 第 3 段：异地（汇总）+ 子机构
    rows.append(_render_agg_row(rm_agg, periods, GROUP_LABELS["remote"], "remote", instance_id, metric_defs))
    rows.extend(_render_child_rows(rm_rows, periods, "remote", drillable_dims, instance_id, metric_defs))
    # 第 4 段：其他（汇总）+ 子机构
    rows.append(_render_agg_row(other_agg, periods, GROUP_LABELS["other"], "other", instance_id, metric_defs))
    rows.extend(_render_child_rows(other_rows, periods, "other", drillable_dims, instance_id, metric_defs))

    # 去除空字符串行（其他组数据为空时聚合行可能返回 ""）
    rows = [r for r in rows if r]

    table = (
        f"<table class='data-table' id='table-3-{escape(instance_id)}' "
        f"data-instance='{escape(instance_id)}'>{head_html}"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return btn_html + table


# 注入的 JS（在 cards_html 末尾追加一段 <script>）
# 所有函数 instance-aware：同一页面可存在多个表 1/2/3 实例，互不干扰。
INTERACT_JS = """
<script>
(function() {
  const ALERT_CLASSES = ['alert-green','alert-blue','alert-yellow','alert-red','alert-gray'];
  const DOT_CLASSES   = ['dot-green','dot-blue','dot-yellow','dot-red','dot-gray','dot-empty'];

  // 表 1 转置：每个 instance 一对 normal/transposed 表 + 一个独立状态
  const _trans1State = {};
  window.toggleTranspose1 = function(instance) {
    instance = instance || 'main';
    const normal  = document.getElementById('table-1-normal-' + instance);
    const trans   = document.getElementById('table-1-transposed-' + instance);
    if (!normal || !trans) return;
    const isTrans = !!_trans1State[instance];
    normal.style.display = isTrans ? '' : 'none';
    trans.style.display  = isTrans ? 'none' : '';
    _trans1State[instance] = !isTrans;
  };

  // 通用：单元格切换指标
  function applyMetricToCells(tableId, metric) {
    document.querySelectorAll('#' + tableId + ' td.data-cell').forEach(td => {
      const valText = td.dataset[metric] || td.getAttribute('data-' + metric) || '—';
      const valSpan = td.querySelector('.num-val');
      if (valSpan) valSpan.textContent = valText;

      ALERT_CLASSES.forEach(c => td.classList.remove(c));
      const raw = td.getAttribute('data-light-' + metric);
      if (raw) td.classList.add(raw);

      const dot = td.querySelector('.dot');
      if (dot) {
        DOT_CLASSES.forEach(c => dot.classList.remove(c));
        dot.classList.add(raw ? raw.replace('alert-','dot-') : 'dot-empty');
      }
    });
  }

  // 通用：按钮 active 状态切换（按 data-instance + data-table 双重隔离）
  function applyButtonActive(tableNum, instance, metric) {
    const sel = '.btn-metric' + (tableNum === 3 ? '-3' : '') +
                '[data-instance="' + instance + '"]' +
                '[data-table="' + tableNum + '"]';
    document.querySelectorAll(sel).forEach(b => {
      b.classList.toggle('active', b.dataset.metric === metric);
    });
  }

  // 表 2 指标切换（含 mini 趋势重绘）
  window.switchMetric2 = function(metric, instance) {
    instance = instance || 'main';
    applyMetricToCells('table-2-' + instance, metric);
    applyButtonActive(2, instance, metric);
    redrawSparklinesForTable('table-2-' + instance, metric);
    toggleInsightsBlock(instance, 2, metric);
  };

  // 表 3 折叠 / 展开（按 instance 隔离）
  window.toggleOrgGroup = function(groupKey, instance) {
    instance = instance || 'main';
    const aggRow = document.querySelector(
      '#table-3-' + instance + ' tr.agg-row[data-group="' + groupKey + '"]'
    );
    if (!aggRow) return;
    const children = document.querySelectorAll(
      '#table-3-' + instance + ' tr.child-row[data-group="' + groupKey + '"]'
    );
    if (children.length === 0) return;
    const willShow = children[0].hidden;
    children.forEach(c => { c.hidden = !willShow; });
    const caret = aggRow.querySelector('.caret');
    if (caret) caret.textContent = willShow ? '▼' : '▶';
  };

  // ── mini 趋势图：JS 端 sparkline 生成（与 Python _sparkline_svg 同规格） ──
  // minRange：最小可视范围；数据真实波动 < minRange 时强制 y 轴扩展到 minRange，防止视觉放大错觉
  function drawSparkline(values, sparkClass, minRange) {
    const W = 96, H = 28, M = 3;
    minRange = minRange || 0;
    const cleaned = [];
    values.forEach((v, i) => { if (v !== null && !isNaN(v)) cleaned.push([i, v]); });
    if (cleaned.length < 2) return '<span class="spark-empty">—</span>';

    const ys = cleaned.map(p => p[1]);
    let yMin = Infinity, yMax = -Infinity;
    ys.forEach(v => { if (v < yMin) yMin = v; if (v > yMax) yMax = v; });
    // 强制最小可视范围（与 Python _sparkline_svg 一致）
    if (minRange > 0 && (yMax - yMin) < minRange) {
      const mid = (yMax + yMin) / 2;
      yMin = mid - minRange / 2;
      yMax = mid + minRange / 2;
    }
    const yRange = yMax > yMin ? (yMax - yMin) : 1.0;
    const nSteps = Math.max(1, values.length - 1);

    function coord(i, v) {
      const x = M + (i / nSteps) * (W - 2*M);
      const y = H - M - ((v - yMin) / yRange) * (H - 2*M);
      return [x, y];
    }

    const points = cleaned.map(([i, v]) => {
      const c = coord(i, v); return c[0].toFixed(1) + ',' + c[1].toFixed(1);
    }).join(' ');

    const lastIdx = cleaned[cleaned.length - 1][0];
    const circles = cleaned.map(([i, v]) => {
      const c = coord(i, v);
      const r = i === lastIdx ? 2.4 : 1.4;
      return '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + r + '"/>';
    }).join('');

    return '<svg class="sparkline" viewBox="0 0 ' + W + ' ' + H +
           '" width="' + W + '" height="' + H + '" preserveAspectRatio="none">' +
           '<g class="spark-group ' + sparkClass + '">' +
           '<polyline points="' + points + '" fill="none"/>' + circles + '</g></svg>';
  }

  function redrawSparklinesForTable(tableId, metric) {
    const table = document.getElementById(tableId);
    if (!table) return;
    table.querySelectorAll('td.trend-cell').forEach(cell => {
      const trendData = cell.getAttribute('data-trend-' + metric) || '';
      const values = trendData.split('/').map(s => s === '' ? NaN : parseFloat(s));
      const lightAttr = cell.getAttribute('data-light-' + metric) || 'alert-gray';
      const sparkClass = (lightAttr || 'alert-gray').replace('alert-', 'spark-');
      const mrAttr = cell.getAttribute('data-minrange-' + metric);
      const minRange = mrAttr ? parseFloat(mrAttr) : 0;
      cell.innerHTML = drawSparkline(values, sparkClass, minRange);
    });
  }

  // ── 列头排序：parse cell 的 data-{metric} 文本为数值 ──
  function parseSortVal(text) {
    if (!text || text === '—') return NaN;
    return parseFloat(String(text).replace(/,/g, '').replace(/%/g, '').trim());
  }

  function getActiveMetric(instance, tableNum) {
    const btnClass = tableNum === 3 ? 'btn-metric-3' : 'btn-metric';
    const sel = '.' + btnClass + '[data-instance="' + instance + '"].active';
    const btn = document.querySelector(sel);
    return btn ? btn.dataset.metric : 'variable_cost_ratio';
  }

  function compareByCol(colIdx, metric, dir) {
    return (a, b) => {
      // colIdx 是周期索引（0-based）；+2 因首列是维度名 + 第 2 列是趋势 cell
      const cellA = a.children[colIdx + 2];
      const cellB = b.children[colIdx + 2];
      const va = parseSortVal(cellA && cellA.getAttribute('data-' + metric));
      const vb = parseSortVal(cellB && cellB.getAttribute('data-' + metric));
      if (isNaN(va) && isNaN(vb)) return 0;
      if (isNaN(va)) return 1;
      if (isNaN(vb)) return -1;
      return dir === 'asc' ? va - vb : vb - va;
    };
  }

  function resetArrows(table) {
    table.querySelectorAll('th.num-th.sortable').forEach(t => {
      delete t.dataset.sortDir;
      const arr = t.querySelector('.sort-arrow');
      if (arr) arr.textContent = '⇅';
    });
  }

  window.sortByColumn = function(tableId, periodIdx) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const instance = table.dataset.instance || 'main';
    const tableNum = tableId.indexOf('table-3-') === 0 ? 3 : 2;
    const metric = getActiveMetric(instance, tableNum);

    // 第 (periodIdx+1) 个 th（首列是维度名）
    const ths = table.querySelectorAll('th.num-th.sortable');
    const th  = ths[periodIdx];
    const prev = th ? th.dataset.sortDir : '';
    const dir  = prev === 'desc' ? 'asc' : 'desc';

    if (tableNum === 2) {
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(compareByCol(periodIdx, metric, dir));
      rows.forEach(r => tbody.appendChild(r));
    } else {
      // 表 3：每个分组内独立排序，聚合行位置不变
      ['same-city','remote','other'].forEach(groupKey => {
        const aggRow = table.querySelector(
          'tr.agg-row[data-group="' + groupKey + '"]'
        );
        if (!aggRow) return;
        const rows = Array.from(table.querySelectorAll(
          'tr.child-row[data-group="' + groupKey + '"]'
        ));
        if (rows.length < 2) return;
        rows.sort(compareByCol(periodIdx, metric, dir));
        let anchor = aggRow;
        rows.forEach(r => {
          if (anchor.nextSibling !== r) {
            aggRow.parentNode.insertBefore(r, anchor.nextSibling);
          }
          anchor = r;
        });
      });
    }

    resetArrows(table);
    th.dataset.sortDir = dir;
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = dir === 'desc' ? '▼' : '▲';
  };

  // 表 3 指标切换：改单元格 + 按当前指标降序重排子行（仅本 instance 内）
  window.switchMetric3 = function(metric, instance) {
    instance = instance || 'main';
    const tableId = 'table-3-' + instance;
    applyMetricToCells(tableId, metric);
    applyButtonActive(3, instance, metric);
    redrawSparklinesForTable(tableId, metric);

    // 子行按 data-sortval-{metric} 降序重排（每组内独立，组间不动）
    ['same-city','remote','other'].forEach(groupKey => {
      const aggRow = document.querySelector(
        '#' + tableId + ' tr.agg-row[data-group="' + groupKey + '"]'
      );
      if (!aggRow) return;
      const rows = Array.from(document.querySelectorAll(
        '#' + tableId + ' tr.child-row[data-group="' + groupKey + '"]'
      ));
      if (rows.length < 2) return;

      rows.sort((a, b) => {
        const aRaw = a.getAttribute('data-sortval-' + metric);
        const bRaw = b.getAttribute('data-sortval-' + metric);
        const va = aRaw === '' || aRaw === null ? NaN : parseFloat(aRaw);
        const vb = bRaw === '' || bRaw === null ? NaN : parseFloat(bRaw);
        if (isNaN(va) && isNaN(vb)) return 0;
        if (isNaN(va)) return 1;   // NaN 排末尾
        if (isNaN(vb)) return -1;
        return vb - va;            // 降序
      });

      // 紧贴聚合行下方按排序结果重新插入；anchor 逐行递进
      let anchor = aggRow;
      rows.forEach(r => {
        if (anchor.nextSibling !== r) {
          aggRow.parentNode.insertBefore(r, anchor.nextSibling);
        }
        anchor = r;
      });
    });

    toggleInsightsBlock(instance, 3, metric);
  };

  // 切换该 (instance, table) 下 insights-wrapper 内的 insights-block 显示
  // 只有 data-metric=metric 的 block 显示，其它 hidden
  function toggleInsightsBlock(instance, tableNum, metric) {
    const wrapper = document.querySelector(
      '.insights-wrapper[data-instance="' + instance + '"][data-table="' + tableNum + '"]'
    );
    if (!wrapper) return;
    wrapper.querySelectorAll('.insights-block').forEach(b => {
      b.hidden = (b.dataset.metric !== metric);
    });
  }

  // 下钻页内置 TOC 高亮：IntersectionObserver 跟踪可见的 .card[id]，对应 TOC 链接置 active
  function initDrillToc(tocEl) {
    const links = Array.from(tocEl.querySelectorAll('.drill-toc-link'));
    const targets = links.map(a => document.getElementById(a.dataset.target)).filter(Boolean);
    if (targets.length === 0) return;

    const obs = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          const id = e.target.id;
          links.forEach(a => a.classList.toggle('active', a.dataset.target === id));
        }
      });
    }, { rootMargin: '-30% 0px -60% 0px', threshold: 0 });

    targets.forEach(t => obs.observe(t));
  }
  // 主报告页加载后扫一次所有 drill-toc（含 hidden 子页内的，IntersectionObserver 对 hidden 也安全）
  // + 把 dhr_lib 主 TOC 标题"本报告板块"改为"目录"（与下钻页统一）
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.drill-toc').forEach(initDrillToc);
    const tocTitle = document.querySelector('.app-toc-title');
    if (tocTitle && tocTitle.textContent.trim() === '本报告板块') {
      tocTitle.textContent = '目录';
    }
  });
})();
</script>
<style>
/* ── 加宽页面 + 左右对称（覆盖 dhr_lib body 1440px / .app-main 880px）── */
body { max-width: min(96vw, 2000px) !important; }

/* 主页（#page-main 可见时）：TOC 180 + gap 16 + 右 padding 196，左右视觉对称 */
body:has(#page-main:not([hidden])) {
  grid-template-columns: 180px 1fr !important;
}
body:has(#page-main:not([hidden])) .app-main {
  max-width: none !important;
  padding: 24px 196px 40px 16px !important;
}

/* 下钻 / 说明子页（#page-main 隐藏时）：dhr_lib 已自动隐藏 TOC + 单列 grid。
   左 padding = 0，让内置 drill-toc 顶左占据「主页 TOC 那一列」的位置，
   右 padding = 196 与主页对称，cards 实际宽度 = 主页 cards 宽度（差 0）。 */
body:has(#page-main[hidden]) .app-main {
  max-width: none !important;
  padding: 24px 196px 40px 0 !important;
}

.app-main .page {
  max-width: 1800px !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

/* 单元格内容禁止换行（数字 / 维度名 / 表头） */
.data-table th, .data-table td { white-space: nowrap; }
.data-table .dim-cell { white-space: nowrap; }

/* 视觉层级原则（用户决策）：图 > 数字 > 文字 > 装饰。
   所有 callout 左侧竖线统一低调浅灰，不分级用红/黄/蓝预警色，
   让数据表格的 sparkline 和数字成为视觉焦点；亮灯信号仅保留在表格单元格内（彩点 + 描边）。*/
.callout,
.callout-info,
.callout-warn,
.callout-danger {
  border-left-color: #d0d0d0 !important;
  background: rgba(0, 0, 0, 0.02) !important;
}

/* 暗黑模式 callout 内文字对比度修复：dhr_lib 默认 callout 不设 color，
   warn/danger 半透明红/黄背景叠暗黑底色后文字易显灰；强制 callout 内全部用 --ink 提亮 */
.callout,
.callout li,
.callout p,
.callout strong,
.callout b,
.insights-list li,
.insights-list b,
.insights-list strong {
  color: var(--ink) !important;
}
/* subtitle 在暗黑下也偏暗，提到 muted-strong 提升对比度 */
.card > .subtitle {
  color: var(--muted-strong) !important;
}

/* ── 下钻页内置 sticky TOC（不复用 dhr_lib .app-toc 避免被切换页隐藏）──
   drill-toc 宽 180 + gap 16 与主页 .app-toc(180) + main padding-left(16) 对齐，
   保证 drill-main 实际宽度 ≡ 主页 cards 宽度。 */
.drill-layout {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.drill-toc {
  flex: 0 0 180px;
  position: sticky;
  top: 24px;
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  padding: 14px 16px;
  background: var(--card-bg, #fff);
  border-radius: 10px;
  box-shadow: var(--card-shadow, 0 1px 3px rgba(0,0,0,.04));
  font-size: 13.5px;
}
.drill-toc-title {
  font-size: 12.5px;
  color: var(--muted, #888);
  margin-bottom: 10px;
  letter-spacing: 0.5px;
}
.drill-toc ol {
  list-style: none;
  padding: 0;
  margin: 0;
}
.drill-toc li {
  margin: 0;
}
.drill-toc a {
  display: block;
  padding: 7px 10px;
  color: var(--muted-strong);            /* 复用 dhr .app-toc a 同款配色，暗黑下 #cbd5e1 中浅灰 */
  text-decoration: none;
  border-radius: 6px;
  border-left: 2px solid transparent;
  transition: background .15s ease, color .15s ease;
}
.drill-toc a:hover {
  background: var(--th-bg);
  color: var(--ink);                     /* 悬停提到主文字色 */
}
.drill-toc a.active {
  background: rgba(96, 165, 250, 0.10);  /* 暗黑下淡蓝光晕；明亮下也淡蓝 */
  color: var(--alert-blue);              /* dhr 两个主题都定义：明亮 #2563eb / 暗黑 #60a5fa */
  border-left-color: var(--alert-blue);
  font-weight: 600;
}
.drill-main {
  flex: 1;
  min-width: 0;
}

.dot-empty { visibility: hidden; }
/* v1.25：metric-switcher 改造为 segmented control 风格——一个胶囊容器，激活态仅是底色差异 */
.table-actions { margin: 8px 0 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.metric-switcher {
  background: rgba(var(--ink-rgb), .06);
  border-radius: 8px;
  padding: 3px;
  gap: 0;  /* segmented 内按钮无 gap */
}
.btn-toggle, .btn-metric, .btn-metric-3 {
  padding: 5px 12px;
  border: 0;
  background: transparent;
  color: var(--muted-strong);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 500;
  font-family: var(--sans-zh);
  line-height: 1.4;
  transition: background .15s ease, color .15s ease;
}
.btn-toggle:hover, .btn-metric:hover, .btn-metric-3:hover {
  background: rgba(var(--ink-rgb), .06);
  color: var(--ink);
}
.btn-metric.active, .btn-metric-3.active {
  background: var(--card-bg);
  color: var(--ink);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .08);
}
.metric-switcher .btn-metric.active:hover,
.metric-switcher .btn-metric-3.active:hover { background: var(--card-bg); }
.switcher-label {
  font-size: 12.5px;
  color: var(--muted);
  margin-right: 4px;
  padding-left: 6px;
}
/* btn-toggle（行列转置等独立按钮）保留外边框，与 metric-switcher 区分 */
.table-actions > .btn-toggle {
  border: 1px solid var(--rule);
  background: var(--card-bg);
  padding: 6px 12px;
  font-size: 13px;
}

/* 列头排序（表 2/3） */
.num-th.sortable { cursor: pointer; user-select: none; transition: background .12s; }
.num-th.sortable:hover { background: var(--th-bg, rgba(26,77,140,0.08)); }
.sort-arrow { font-size: 10px; opacity: 0; margin-left: 4px; display: inline-block; min-width: 12px; transition: opacity .15s ease; }  /* v1.25：默认隐藏 */
.num-th.sortable:hover .sort-arrow { opacity: 0.5; }
.num-th[data-sort-dir] .sort-arrow { opacity: 1; color: var(--accent-bg, #1a4d8c); font-weight: 700; }

/* mini 趋势图 sparkline（借鉴 dhr_lib） */
.trend-th { width: 110px; text-align: center; }
.trend-cell { text-align: center; padding: 4px 6px; vertical-align: middle; }
.sparkline { display: inline-block; vertical-align: middle; }
.spark-group polyline { stroke-width: 1.5; fill: none; }
.spark-group circle { stroke: var(--card-bg, #fff); stroke-width: 0.5; }
.spark-group.spark-green  polyline { stroke: var(--alert-green-color, #10b981); }
.spark-group.spark-blue   polyline { stroke: var(--alert-blue-color,  #3b82f6); }
.spark-group.spark-yellow polyline { stroke: var(--alert-yellow-color,#d97706); }
.spark-group.spark-red    polyline { stroke: var(--alert-red-color,   #dc2626); }
.spark-group.spark-gray   polyline { stroke: var(--alert-gray-color,  #9ca3af); }
.spark-group.spark-green  circle { fill: var(--alert-green-color, #10b981); }
.spark-group.spark-blue   circle { fill: var(--alert-blue-color,  #3b82f6); }
.spark-group.spark-yellow circle { fill: var(--alert-yellow-color,#d97706); }
.spark-group.spark-red    circle { fill: var(--alert-red-color,   #dc2626); }
.spark-group.spark-gray   circle { fill: var(--alert-gray-color,  #9ca3af); }
.spark-empty { color: var(--text-muted, #999); font-size: 12px; }

/* 当年起保（最右列）视觉重点突出：表头深色 + cell 浅色背景 */
.data-table thead th:last-child {
  background: var(--accent-bg, #1a4d8c);
  color: #fff;
}
.data-table thead th:last-child .sort-arrow { color: #fff; opacity: 0.7; }
.data-table thead th:last-child[data-sort-dir] .sort-arrow { opacity: 1; }
.data-table tbody td:last-child {
  background: rgba(26,77,140,0.05);
  font-weight: 600;
}

/* 表 3 子机构可下钻：覆盖 child-indent 的浅色弱化，保持与表 2 客户类别一致 */
[id^="table-3-"] .child-row.expandable .child-indent {
  color: var(--link, #2563eb) !important;
  font-weight: 500 !important;  /* 与表 2 dim-link 实测 computed 500 一致 */
}
[id^="table-3-"] .child-row.expandable .child-indent strong {
  font-weight: 600;  /* strong 元素维持 600，dhr 主题统一 */
}
[id^="table-3-"] .child-row.expandable:hover .child-indent strong {
  text-decoration: underline;
}

/* 解读引用框（callout）的色彩与背景：dhr_lib 默认 + 本 skill 上方 .callout/.callout-* 统一覆盖
   已生效（浅灰边框 + 极弱中性背景 + ink 文字色）；本处只保留布局微调。 */
.callout-title { margin-bottom: 0.4em; font-size: 13.5px; }
.insights-list { margin: 0.4em 0 0 1.2em; padding: 0; }
.insights-list li { margin: 0.3em 0; line-height: 1.6; }
.insights-list b { font-variant-numeric: tabular-nums; }

/* 表 3 层次化样式（用 [id^="table-3-"] 覆盖所有 instance） */
[id^="table-3-"] .agg-row { cursor: pointer; font-weight: 600; }
[id^="table-3-"] .agg-row.agg-root { cursor: default; }
[id^="table-3-"] .agg-row:hover:not(.agg-root) { background: var(--row-hover-bg, rgba(26,77,140,0.04)); }
[id^="table-3-"] .caret {
  display: inline-block; width: 1.2em; user-select: none;
  color: var(--text-muted, #888); margin-right: 4px;
}
[id^="table-3-"] .child-indent {
  padding-left: 28px; color: var(--text-muted, #555); font-weight: 400;
}
</style>
"""


# ── mini 趋势图 SVG helper（借鉴 dhr_lib._sparkline_svg） ──

_SPARK_W, _SPARK_H, _SPARK_MARGIN = 96, 28, 3


def _min_range_for_kind(kind: str) -> float:
    """每个指标 kind 的"最小可视范围"——数据实际波动小于此值时，y 轴固定扩展到此值，
    防止"明明相近的数值被 auto-scale 放大成视觉剧烈波动"的错觉。

    pct  → 5pp（5%）— 比如 vcr 86–87 % 真实差 1pp 时，曲线只占 1/5 高度，扁平显示
    coef → 0.05    — 自主系数 0.91–0.92 真实差 0.01 时，曲线只占 1/5 高度
    其他 → 0      — money0 / wan2 / int 不限制（绝对量本身有规模差异）
    """
    if kind == "pct":   return 5.0
    if kind == "coef":  return 0.05
    return 0.0


def _sparkline_svg(values: list, alert_class: str = "alert-gray",
                   min_range: float = 0.0) -> str:
    """生成 mini 趋势图 SVG。

    values: 按时序从早到晚的数值（None / NaN 视为缺失）
    alert_class: 末值的亮灯 class（alert-green/blue/yellow/red/gray）→ 决定线条颜色
    min_range: 最小 y 轴范围；数据实际范围 < min_range 时强制扩展到 min_range（中点对称）
    """
    cleaned: list[tuple[int, float]] = []
    for i, v in enumerate(values):
        if v is None or pd.isna(v):
            continue
        cleaned.append((i, float(v)))
    if len(cleaned) < 2:
        return "<span class='spark-empty'>—</span>"

    ys = [v for _, v in cleaned]
    y_min, y_max = min(ys), max(ys)
    actual_range = y_max - y_min
    # 强制最小可视范围（防止小波动被 auto-scale 放大成视觉错觉）
    if min_range > 0 and actual_range < min_range:
        mid = (y_max + y_min) / 2.0
        y_min = mid - min_range / 2.0
        y_max = mid + min_range / 2.0
    y_range = (y_max - y_min) if y_max > y_min else 1.0
    n_steps = max(1, len(values) - 1)

    def coord(idx: int, val: float) -> tuple[float, float]:
        x = _SPARK_MARGIN + (idx / n_steps) * (_SPARK_W - 2 * _SPARK_MARGIN)
        y = _SPARK_H - _SPARK_MARGIN - ((val - y_min) / y_range) * (_SPARK_H - 2 * _SPARK_MARGIN)
        return x, y

    points = " ".join(f"{coord(i, v)[0]:.1f},{coord(i, v)[1]:.1f}" for i, v in cleaned)
    spark_cls = alert_class.replace("alert-", "spark-") if alert_class else "spark-gray"

    last_idx = cleaned[-1][0]
    circles = []
    for i, v in cleaned:
        x, y = coord(i, v)
        r = 2.4 if i == last_idx else 1.4
        circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>')

    return (
        f'<svg class="sparkline" viewBox="0 0 {_SPARK_W} {_SPARK_H}" '
        f'width="{_SPARK_W}" height="{_SPARK_H}" preserveAspectRatio="none">'
        f'<g class="spark-group {spark_cls}">'
        f'<polyline points="{points}" fill="none"/>'
        f'{"".join(circles)}</g></svg>'
    )


def _build_trend_cell_html(values_for_default: list, alert_for_default: str,
                            all_metric_values: dict, all_metric_alerts: dict,
                            metric_defs=None,
                            default_key: Optional[str] = None) -> str:
    """趋势 cell：默认显示「变动成本率」的 sparkline + 把全 7 指标的值和亮灯都存 data-*，
    切换指标时由 JS redrawSparkline 重绘。

    all_metric_values: {metric_key: [v1..v6]}（按时序）
    all_metric_alerts: {metric_key: alert_class_at_last}（末值亮灯）
    metric_defs: 用于推 kind → min_range（防视觉错觉）；不传则用全局 METRIC_DEFS
    default_key: 默认显示哪个指标的 SVG（决定首次 min_range）；不传用 metric_defs[0][0]
    """
    defs = metric_defs or METRIC_DEFS
    kind_by_key = {k: kind for k, _, kind, _ in defs}
    default_key = default_key or defs[0][0]
    default_min_range = _min_range_for_kind(kind_by_key.get(default_key, ""))

    svg = _sparkline_svg(values_for_default, alert_for_default, default_min_range)
    # 紧凑序列化（用 / 分隔，NaN/None → 空），避免每个 cell 重复 6 个 data-{metric}-X 属性
    data_attrs = []
    for mkey, vals in all_metric_values.items():
        s = "/".join("" if v is None or pd.isna(v) else f"{float(v):.6g}" for v in vals)
        data_attrs.append(f'data-trend-{mkey}="{s}"')
    for mkey, alert in all_metric_alerts.items():
        data_attrs.append(f'data-light-{mkey}="{alert or ""}"')
    # 把每个指标的 min_range 也存到 data 属性，供 JS redraw 使用
    for mkey in all_metric_values.keys():
        mr = _min_range_for_kind(kind_by_key.get(mkey, ""))
        data_attrs.append(f'data-minrange-{mkey}="{mr:g}"')
    return f'<td class="trend-cell" {" ".join(data_attrs)}>{svg}</td>'


def render_callout(text: str, level: str = "info") -> str:
    """引用框组件（左边框 + 浅色背景，借鉴 dhr_lib.render_callout）。

    level: info（默认，蓝）/ warn（黄）/ danger（红）
    text 内可含 HTML（不会再 escape）。
    """
    return f'<div class="callout callout-{escape(level)}">{text}</div>'


def render_drill_overview(
    dim_label: str,
    dim_val: str,
    slice_overall: pd.DataFrame,
    second_table_html: str,
    second_table_title: str,
    second_table_subtitle: str,
    periods: list[Period],
    instance_id: str,
    ytd_vcr: Optional[float],
    m12_vcr: Optional[float],
    first_insights_html: str = "",
    second_insights_html: str = "",
    extra_cards_html: str = "",
    drill_nav_items: Optional[list] = None,
    card_1_id: str = "",
    card_2_id: str = "",
) -> str:
    """下钻子页 body：两块卡片并陈（+ 可选 extra aux 卡片追加在后）。

    Card 1：复用 render_table_1（小表 1 单项明细，7 指标 × 7 周期 + 转置按钮）。
    Card 2：调用方传入已渲染好的 HTML 串（应是 render_table_2 或 render_table_3 的输出）。
    insights_html：可选诊断卡 HTML，插入到对应表前面（与主页装配顺序一致）。
    extra_cards_html：可选附加卡片串（如 6 个 aux 维度卡），追加在 card_2 之后。
    """
    def _fmt(v: Optional[float]) -> str:
        return "—" if v is None or pd.isna(v) else f"{v:.1f}%"

    subtitle_parts = [
        f"{dim_label}：<strong>{escape(dim_val)}</strong>",
        f"YTD 变率 {_fmt(ytd_vcr)}",
        f"滚动 12 个月 {_fmt(m12_vcr)}",
    ]
    head_subtitle = " · ".join(subtitle_parts)

    table_1_html = render_table_1(slice_overall, periods, instance_id=instance_id)

    card_1 = dhr_lib.render_card(
        title=f"{dim_val} · 保单品质",
        subtitle=head_subtitle,
        body=f"{first_insights_html}{table_1_html}",
        card_id=card_1_id,
    )
    card_2 = dhr_lib.render_card(
        title=second_table_title,
        subtitle=second_table_subtitle,
        body=f"{second_insights_html}{second_table_html}",
        card_id=card_2_id,
    )
    all_cards = card_1 + card_2 + (extra_cards_html or "")

    # 下钻页内置 sticky TOC（与主页 dhr_lib TOC 视觉一致；不复用 .app-toc 避免被 dhr 切换页时隐藏）
    if drill_nav_items:
        items_html = "".join(
            f'<li><a href="#{escape(sid)}" class="drill-toc-link" data-target="{escape(sid)}">{escape(label)}</a></li>'
            for sid, label in drill_nav_items
        )
        toc_html = (
            f'<nav class="drill-toc" aria-label="目录">'
            f'<div class="drill-toc-title">目录</div>'
            f'<ol>{items_html}</ol>'
            f'</nav>'
        )
        return (
            f'<div class="drill-layout">'
            f'{toc_html}'
            f'<div class="drill-main">{all_cards}</div>'
            f'</div>'
        )
    return all_cards


def build_info_card_html(cutoff_iso: str, cutoff_year: int, cutoff_month: int, cutoff_day: int) -> str:
    """数据口径说明卡（与 ad-hoc 一致）。"""
    return f"""
    <div class="card">
      <h2>数据口径</h2>
      <ul>
        <li><strong>时间锚</strong>：起保日期 <code>insurance_start_date</code>。</li>
        <li><strong>当年起保</strong>：[当年 1 月 1 日, {cutoff_iso}]。</li>
        <li><strong>上年同期</strong>：与"当年起保"日历对称，整体平移一年 →
            [{cutoff_year - 1}-01-01, {cutoff_year - 1}-{cutoff_month:02d}-{cutoff_day:02d}]。</li>
        <li><strong>滚动 N 个月</strong>：(cutoff − N 月, cutoff]，左开右闭，避免左端日重复入两窗。</li>
        <li><strong>保单去重</strong>：按 (保单号, 起保日期) 聚合，<code>HAVING SUM(premium) &gt; 0</code>，排除全退保。</li>
        <li><strong>赔款</strong>：已结案取 <code>settled_amount</code>，未结案取 <code>reserve_amount</code>。</li>
        <li><strong>满期保费</strong>：<code>保费 × 满期天数 / 保险期限天数</code>（闰年感知 365/366）。</li>
        <li><strong>变动成本率</strong> = 满期赔付率（分母满期保费） + 费用率（分母签单保费）。</li>
        <li><strong>满期出险率</strong>：年化口径 <code>Σ(赔案 × 保险期限 / 满期天数) / 去重保单数</code>。</li>
        <li><strong>自主系数</strong>：仅商业险样本，调和加权 <code>Σ(商业险保费) / Σ(商业险基准保费)</code>，
            基准保费 = 商业险保费 / 自主系数。结果应落在 [0.5, 1.5]。</li>
        <li><strong>件数单位</strong>：保单件数和赔案件数以"万"为单位，保留 2 位小数（表头已标注）。</li>
        <li><strong>范围</strong>：不分险种、不排除任何客户类别。</li>
      </ul>
    </div>
    """
