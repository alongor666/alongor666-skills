from html import escape

def render_card(title: str, subtitle: str, body: str,
                kicker: str = "", style: str = "",
                card_id: str = "") -> str:
    """卡片包裹。kicker 为中文小标（不接受英文）。card_id 用于目录锚点跳转。

    v1.22：subtitle 非空时渲染为 <h2> 旁 ⓘ 图标的 hover 浮窗（CSS-only）。
    subtitle 支持 HTML 内联标签（<strong>/<b>/<code>），调用方自行 escape 数据值。
    """
    style_attr = f' style="{style}"' if style else ""
    id_attr = f' id="{escape(card_id)}"' if card_id else ""
    kicker_html = f'<div class="kicker">{escape(kicker)}</div>' if kicker else ""
    note_html = (
        '<span class="hover-note" aria-label="说明">'
        '<span class="hover-note-icon">ⓘ</span>'
        f'<span class="hover-note-body">{subtitle}</span>'
        '</span>'
    ) if subtitle else ""
    return f"""
<div class="card"{id_attr}{style_attr}>
  {kicker_html}
  <h2>{escape(title)}{note_html}</h2>
  {body}
</div>"""


def render_callout(text: str, cite: str = "", level: str = "info") -> str:
    """引用框（左边框 + 浅色背景）。level: info | warn | danger"""
    cite_html = f'<span class="cite">{escape(cite)}</span>' if cite else ""
    return f"""
<div class="callout callout-{level}">
  <div class="callout-text">{text}</div>
  {cite_html}
</div>"""


def render_rule() -> str:
    return '<hr class="rule">'

