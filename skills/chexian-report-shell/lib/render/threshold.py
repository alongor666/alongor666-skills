from html import escape
from typing import Optional

from ..alerts import filter_threshold_rows

def render_threshold_table(metric_keys: Optional[list] = None) -> str:
    """渲染"四级亮灯标准对照表"。

    Args:
      metric_keys: 想展示的 metric_key 列表；None 表示全部。
                   v1.6 起每行有 metric_key（见 alerts.THRESHOLD_TABLE_ROWS）。
    """
    rows = []
    selected = filter_threshold_rows(metric_keys)
    for r in selected:
        rows.append(f"""
<tr>
  <td class="th-name">{escape(r['name'])}</td>
  <td class="th-unit">{escape(r['unit'])}</td>
  <td class="th-cell"><span class="th-val">{escape(r['优'])}</span><span class="dot dot-green"></span></td>
  <td class="th-cell"><span class="th-val">{escape(r['良'])}</span><span class="dot dot-blue"></span></td>
  <td class="th-cell"><span class="th-val">{escape(r['警'])}</span><span class="dot dot-yellow"></span></td>
  <td class="th-cell"><span class="th-val">{escape(r['险'])}</span><span class="dot dot-red"></span></td>
  <td class="th-formula">{escape(r.get('formula', ''))}</td>
  <td class="th-scope">{escape(r.get('scope', ''))}</td>
</tr>""")
    return f"""
<table class="threshold-table">
  <thead>
    <tr>
      <th>指标</th>
      <th>单位</th>
      <th class="th-cell"><span class="th-val">优秀</span><span class="dot dot-green"></span></th>
      <th class="th-cell"><span class="th-val">健康</span><span class="dot dot-blue"></span></th>
      <th class="th-cell"><span class="th-val">异常</span><span class="dot dot-yellow"></span></th>
      <th class="th-cell"><span class="th-val">危险</span><span class="dot dot-red"></span></th>
      <th>公式</th>
      <th>口径</th>
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
<p class="threshold-note">本卡片仅展示本报告涉及的指标。<br>
小样本规则：单分组保单数小于 30 张时，所有率值均灰显（标注为「样本不足」），不参与亮灯打分，仅供参考。<br>
阈值版本：分公司经营口径 v1.6（2026-05-13），与项目源 diagnose_common.py 已脱钩独立维护。</p>"""


def render_threshold_card(metric_keys: Optional[list] = None,
                          extra_formulas: Optional[list] = None,
                          preface_html: str = "") -> str:
    """渲染"亮灯标准 + 公式 + 口径"卡片（默认隐藏，由状态条按钮触发）。

    Args:
      metric_keys: 白名单（对应 alerts.THRESHOLD_TABLE_ROWS 的 metric_key）；None 表示全部
      extra_formulas: 额外公式说明 [(name, formula_text)]
      preface_html: 卡片顶部的"取数口径"说明 HTML（v1.7 新增；放在阈值表前）
    """
    formulas_html = ""
    if extra_formulas:
        items = "".join(
            f'<div class="formula-item">'
            f'<span class="formula-name">{escape(name)}</span>'
            f'<span class="formula-text">{escape(text)}</span>'
            f'</div>'
            for name, text in extra_formulas
        )
        formulas_html = (
            f'<h2 style="margin-top:22px;">补充指标说明</h2>'
            f'<p class="subtitle">本报告引用但暂不打灯的指标。</p>'
            f'<div class="formula-list">{items}</div>'
        )
    preface_block = (f'<div class="threshold-preface">{preface_html}</div>'
                     if preface_html else "")
    return f"""
<div class="card threshold-card" id="threshold" hidden>
  <div class="kicker">数据口径</div>
  <h2>亮灯标准、公式与口径</h2>
  <p class="subtitle">管理决策的红线刻度尺。本报告涉及的指标已列出，单位、公式、口径皆在表内。</p>
  {preface_block}
  {render_threshold_table(metric_keys)}
  {formulas_html}
</div>"""
