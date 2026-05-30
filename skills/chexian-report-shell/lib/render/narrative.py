from html import escape
from typing import Optional

import pandas as pd

from ..alerts import light, LOWER_WORSE
from ..format import fmt_num

def render_metric_narrative(metrics: list, time_labels: list,
                            *, current_label_idx: int = -1,
                            baseline_label_idx: int = 0,
                            extra_facts: Optional[list] = None) -> str:
    """根据 metrics 自动生成"当周指标状态及趋势概述"段（通用规则，可复用）。

    输出三段：
      1. 总体亮灯分布（绿/蓝/黄/红/灰 计数）
      2. 趋势改善 / 恶化的指标排名（基于 values[current] vs values[baseline]）
      3. 调用方传入的额外事实（如时间进度对照）

    Args:
      metrics: 与 render_weekly_table 同结构
      time_labels: 列标题列表
      current_label_idx: 「当前/最新」对应 values 中的索引（v1.8 默认 -1 = 最后一列）
      baseline_label_idx: 「基准/起点」对应 values 中的索引（v1.8 默认 0 = 第一列）
      extra_facts: list[str]，每项是一段额外事实文本（HTML 片段，已 escape）
    """
    if not metrics:
        return ""
    n = len(time_labels)
    cur_label = time_labels[current_label_idx] if -n <= current_label_idx < n else ""
    base_label = time_labels[baseline_label_idx] if -n <= baseline_label_idx < n else ""

    # 1) 亮灯计数
    counts = {"alert-green": 0, "alert-blue": 0, "alert-yellow": 0, "alert-red": 0,
              "alert-gray": 0, "no-light": 0}
    for m in metrics:
        if m.get("is_reference"):
            continue  # 参照行（如「时间进度」）不计入亮灯统计
        if m.get("placeholder"):
            counts["no-light"] += 1; continue
        values = m.get("values") or []
        cur = values[current_label_idx] if values and abs(current_label_idx) <= len(values) else None
        if cur is None:
            counts["no-light"] += 1; continue
        if not m.get("metric_key"):
            counts["no-light"] += 1; continue
        cls, _ = light(m["metric_key"], cur, m.get("sample_n", 999))
        counts[cls or "no-light"] += 1

    light_summary_parts = []
    for cls, label_text in [("alert-green", "优秀"), ("alert-blue", "健康"),
                            ("alert-yellow", "异常"), ("alert-red", "危险")]:
        if counts[cls] > 0:
            light_summary_parts.append(
                f'<span class="narr-pill narr-{cls.replace("alert-", "")}">'
                f'{label_text} {counts[cls]}</span>'
            )
    if counts["no-light"] > 0:
        light_summary_parts.append(
            f'<span class="narr-pill narr-gray">未打灯 {counts["no-light"]}</span>'
        )
    light_summary_html = " ".join(light_summary_parts)

    # 2) 趋势改善 / 恶化
    moves = []
    for m in metrics:
        if m.get("placeholder") or m.get("is_reference"):
            continue
        values = m.get("values") or []
        if len(values) < 2: continue
        cur = values[current_label_idx]
        base = values[baseline_label_idx]
        if cur is None or base is None: continue
        delta = cur - base
        # 判断方向（越低越差时，下降是恶化；越高越差时，下降是改善）
        is_lower_worse = m.get("metric_key") in LOWER_WORSE
        if is_lower_worse:
            improved = delta > 0
        else:
            improved = delta < 0
        moves.append({
            "name": m["name"],
            "abs_delta": abs(delta),
            "delta": delta,
            "improved": improved,
            "kind": m.get("kind", "pct"),
        })
    moves_sorted = sorted(moves, key=lambda x: x["abs_delta"], reverse=True)
    improved = [x for x in moves_sorted if x["improved"]][:3]
    worsened = [x for x in moves_sorted if not x["improved"]][:2]

    def mv_str(mv):
        sign = "+" if mv["delta"] > 0 else ""
        return f'{escape(mv["name"])}（{sign}{fmt_num(mv["delta"], mv["kind"])}）'

    trend_lines = []
    if improved:
        trend_lines.append(
            f'<p class="narr-line narr-improve">'
            f'<strong>改善：</strong>{"；".join(mv_str(x) for x in improved)}'
            f'</p>'
        )
    if worsened:
        trend_lines.append(
            f'<p class="narr-line narr-worsen">'
            f'<strong>恶化：</strong>{"；".join(mv_str(x) for x in worsened)}'
            f'</p>'
        )

    # 3) 额外事实
    extra_html = "".join(f'<p class="narr-line narr-fact">{x}</p>' for x in (extra_facts or []))

    return f"""
<div class="narrative">
  <div class="narr-summary">
    <span class="narr-label">{escape(cur_label)}（最新列）亮灯分布：</span>
    {light_summary_html}
    <span class="narr-baseline">vs {escape(base_label)}</span>
  </div>
  {''.join(trend_lines)}
  {extra_html}
</div>"""


def render_problem_narrative(df: pd.DataFrame,
                             checks: list,
                             *, exclude_dim_values=("合计",)) -> str:
    """问题导向叙述（v1.11）：列出每个维度命中的"有问题"维度值。

    Args:
      df: DataFrame，需含 dim / policy_count / 各 metric 列
      checks: list of (metric_key, label, levels)，levels 是触发集合
              如 {"alert-yellow", "alert-red"} 表示异常+危险
      exclude_dim_values: 不参与判定的 dim 值（如「合计」行）

    排序原则（v1.18 新增）：每行 chips 按指标值「从最差到最好」排序——
      越高越差（变动成本率、满期赔付率…）→ 降序；
      越低越差（续保率、达成率、增长率…）→ 升序；
      None 排末尾。让读者第一眼看到最危险的，无需扫描全行。

    Returns:
      问题清单 HTML（嵌进卡片 body 顶部）。无问题时返回简短提示。
    """
    if df is None or df.empty:
        return ""
    sections = []
    for metric_key, label, levels in checks:
        if metric_key not in df.columns:
            continue
        kind = "pct"  # 默认；调用方若有特殊 kind 需求可后续扩展
        hit_items = []
        for _, row in df.iterrows():
            dim_value = str(row.get("dim", ""))
            if dim_value in exclude_dim_values:
                continue
            v = row.get(metric_key)
            n = int(row.get("policy_count") or 0)
            cls, _ = light(metric_key, v, n)
            if cls in levels:
                hit_items.append((dim_value, v, cls))
        # v1.18：按指标值「最差→最好」排序
        higher_worse = metric_key not in LOWER_WORSE
        def _sort_key(item, hw=higher_worse):
            val = item[1]
            if val is None:
                return (1, 0)  # None 排末尾
            return (0, -val if hw else val)
        hit_items.sort(key=_sort_key)
        if not hit_items:
            sections.append(
                f'<p class="prob-line prob-ok">'
                f'<strong>{escape(label)}：</strong>本期无异常</p>'
            )
        else:
            chips = []
            for dim_value, v, cls in hit_items:
                color_suffix = cls.replace("alert-", "")
                # v1.12：名字纯文本（无色无边框），仅数字着色
                chips.append(
                    f'<span class="prob-item">'
                    f'<span class="prob-name">{escape(dim_value)}</span> '
                    f'<span class="prob-num prob-num-{color_suffix}">{fmt_num(v, kind)}</span>'
                    f'</span>'
                )
            sections.append(
                f'<p class="prob-line">'
                f'<strong>{escape(label)}：</strong>{"  ".join(chips)}</p>'
            )
    if not sections:
        return ""
    return f'<div class="problem-narrative">{"".join(sections)}</div>'


def render_red_flag(red_rows: list) -> str:
    """渲染异常红榜表（可在任何编排脚本里复用）。

    Args:
      red_rows: 每项是一个 dict，键：
        dim         维度值（中文，如「永成-简阳」）
        dim_type    类型标签（如「经代」「业务员」「客户类别」）
        metric      指标名（如「满期赔付率」）
        value       实际值（百分比，未带 %）
        threshold   危险阈值（百分比，未带 %）
        n           保单数
        premium_wan 保费（万元，整数）
    """
    if not red_rows:
        return '<p class="empty-data">本期无达到「危险」级的分组。</p>'
    rows_html = []
    for r in red_rows:
        rows_html.append(f"""
<tr>
  <td>{escape(str(r['dim']))}</td>
  <td><span class="pill">{escape(r['dim_type'])}</span></td>
  <td>{escape(r['metric'])}</td>
  <td class="num alert-red"><span class="num-val">{r['value']:.1f}%</span></td>
  <td class="num"><span class="num-val">&gt;{r['threshold']}%</span></td>
  <td class="num"><span class="num-val">{r['n']:,}</span></td>
  <td class="num"><span class="num-val">{r['premium_wan']:,}</span></td>
</tr>""")
    return f"""
<table class="data-table">
  <thead><tr>
    <th>维度</th>
    <th>类型</th>
    <th>异常指标</th>
    <th class="num-th">实际值</th>
    <th class="num-th">危险阈值</th>
    <th class="num-th">保单数</th>
    <th class="num-th">保费(万)</th>
  </tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>"""
