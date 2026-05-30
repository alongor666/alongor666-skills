from html import escape

def render_status_bar(items: list[tuple[str, str]],
                      warn_text: str = "查看亮灯标准与公式",
                      target_id: str = "threshold") -> str:
    """渲染顶部精简状态条。

    Args:
      items: [(标签, 值), ...] 例如 [("样本数", "509"), ("总保费", "73.17 万")]
      warn_text: 右侧警示按钮文字
      target_id: 点击展开的卡片 id（默认 "threshold"）
    """
    items_html = "".join(
        f'<span class="item"><strong>{escape(k)}</strong><span class="v">{escape(v)}</span></span>'
        for k, v in items
    )
    return f"""
<div class="status-bar">
  {items_html}
  <button class="toggle-threshold" onclick="
    const el = document.getElementById('{target_id}');
    if (el) {{
      el.hidden = !el.hidden;
      this.textContent = el.hidden ? '{escape(warn_text)}' : '收起亮灯标准';
      if (!el.hidden) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
    }}
  ">{escape(warn_text)}</button>
</div>"""

