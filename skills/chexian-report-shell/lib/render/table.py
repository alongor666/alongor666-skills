from html import escape
from typing import Optional

import pandas as pd

from ..alerts import light, LIGHT_METRICS
from ..format import fmt_num
from ..labels import short_label as _sl

HEADERS_8METRIC: list[tuple[str, str, str, Optional[str], Optional[str]]] = [
    ("dim",                       "维度",                              "left", None,     None),
    ("policy_count",              _sl("policy_count"),                 "num",  "int",    "去重后的保单条数（按 保单号 + 起保日期 双键去重）"),
    ("premium",                   _sl("premium") + "(万)",             "num",  "wan",    "净保费合计（原单加批改净额，HAVING SUM(premium) > 0）"),
    ("reported_claims",           _sl("reported_claims") + "(万)",     "num",  "wan",    "已决赔款 + 未决赔款"),
    ("earned_loss_freq_pct",      _sl("earned_loss_freq_pct"),         "num",  "pct",    "赔案件数合计 × 365 ÷ 满期天数合计 × 100"),
    ("earned_loss_ratio_pct",     _sl("earned_loss_ratio_pct"),        "num",  "pct",    "已报告赔款合计 × 100 ÷ 满期保费合计；满期保费 = 保费 × 满期天数 ÷ 保险期限天数"),
    ("per_policy_premium",        _sl("per_policy_premium"),           "num",  "money0", "保费合计 ÷ 保单数"),
    ("avg_claim",                 _sl("avg_claim"),                    "num",  "money0", "已报告赔款合计 ÷ 赔案件数"),
    ("expense_ratio_pct",         _sl("expense_ratio_pct"),            "num",  "pct",    "费用金额合计 × 100 ÷ 保费合计"),
    ("variable_cost_ratio_pct",   _sl("variable_cost_ratio_pct"),      "num",  "pct",    "满期赔付率 + 费用率（注意两个分母不同：满期保费 vs 签单保费）"),
]


def _info_icon(tip: str) -> str:
    """v1.2 已弃用——表头不再加图标。公式信息整合到对照表卡片底部。
    保留函数仅为向后兼容，固定返回空串。"""
    return ""


def _dot(level_class: str) -> str:
    """渲染纯 CSS 色块（不依赖 emoji）。"""
    if not level_class:
        return ""
    return f'<span class="dot {level_class.replace("alert-", "dot-")}" aria-hidden="true"></span>'


def render_table(df: pd.DataFrame,
                 dim_label: str = "维度",
                 headers: Optional[list] = None,
                 drilldown_target_by_dim: Optional[dict] = None,
                 drill_hrefs: Optional[dict] = None) -> str:
    """渲染数据表（v1.19：回归 SPA showPage 模式，drill_hrefs 兼容签名但等价于 drilldown_target_by_dim）。

    Args:
      drilldown_target_by_dim: dict[dim_value -> page_id]。同窗口 SPA showPage 跳转。
      drill_hrefs: 历史签名兼容（v1.18 多文件方案废弃后保留）；语义等同 drilldown_target_by_dim，
        值视为 page_id 而非 URL。两者合并使用，后者优先级更高。
    """
    if df.empty:
        return '<p class="empty-data">无数据</p>'

    headers = headers or HEADERS_8METRIC
    drill = dict(drill_hrefs or {})
    drill.update(drilldown_target_by_dim or {})
    col_count = len(headers)

    # v1.18：每个 <th> 加 sortable + data-col-type/onclick，开启一键排序
    # 合计行（dim="合计"）固定第一行不参与排序 —— 全局视觉锚点（见 SKILL.md）
    th_cells = []
    for key, label, align, _, tip in headers:
        display = dim_label if key == "dim" else label
        col_type = "text" if align != "num" else "num"
        cls_list = ["sortable"]
        if align == "num":
            cls_list.append("num-th")
        cls = f' class="{" ".join(cls_list)}"'
        info = _info_icon(tip) if tip else ""
        th_cells.append(
            f'<th{cls} data-col-type="{col_type}" '
            f'onclick="sortTable(this)">{escape(display)}{info}'
            f'<span class="sort-ind" aria-hidden="true"></span></th>'
        )

    rows_html = []
    for _, row in df.iterrows():
        n = int(row["policy_count"]) if "policy_count" in row and pd.notna(row.get("policy_count")) else 0
        dim_value = str(row.get("dim", ""))
        has_drill = dim_value in drill
        is_total = (dim_value == "合计")

        cells = []
        for key, _, align, kind, _ in headers:
            v = row.get(key)
            if key == "dim":
                text = escape(str(v) if v is not None else "—")
                cls = "dim-cell dim-link" if has_drill else "dim-cell"
                cells.append(f'<td class="{cls}">{text}</td>')
            elif key in LIGHT_METRICS:
                cls, label = light(key, v, n)
                dot_cls = cls.replace("alert-", "dot-") if cls else ""
                dot = (f'<span class="dot {dot_cls}" aria-hidden="true"></span>'
                       if cls else '')
                cells.append(
                    f'<td class="num {cls} has-dot">'
                    f'<span class="num-val">{fmt_num(v, kind)}</span>'
                    f'{dot}'
                    f'</td>'
                )
            else:
                cells.append(f'<td class="num">{fmt_num(v, kind)}</td>')

        # 行属性：合计行 row-total（排序时锚定）；下钻行 expandable + onclick
        tr_classes = []
        tr_onclick = ""
        if is_total:
            tr_classes.append("row-total")
        if has_drill:
            tr_classes.append("expandable")
            tr_onclick = f' onclick="showPage(\'{drill[dim_value]}\')"'
        tr_cls = f' class="{" ".join(tr_classes)}"' if tr_classes else ""
        rows_html.append(f"<tr{tr_cls}{tr_onclick}>" + "".join(cells) + "</tr>")

    return f"""
<table class="data-table">
  <thead><tr>{''.join(th_cells)}</tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>"""

