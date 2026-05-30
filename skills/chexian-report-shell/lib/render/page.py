from html import escape
from typing import Optional

from ._assets import PAGE_HEAD

def render_page(title: str,
                cards_html: str,
                info_html: str = "",
                drill_pages: Optional[list] = None,
                kicker: str = "",
                meta_text: str = "",
                footer_text: str = "",
                nav_items: Optional[list] = None,
                # 兼容旧调用：保留 pills/meta_items/status_items 参数但本版本已废弃
                pills=None, meta_items=None, status_items=None,
                lang_pack: Optional[dict] = None) -> str:
    """渲染整页 HTML（v1.16：飞书文档式三栏布局）。

    Args:
      title:        浏览器 title + 主页 h1
      cards_html:   page-main 的卡片内容（业务主体）
      info_html:    page-info 的内容（口径/阈值/数据截止/公式说明等）
      drill_pages:  list of (page_id, page_title, body_html)，下钻独立页面
      kicker:       主标题上方小字
      footer_text:  页脚
      nav_items:    [(anchor, label), ...] 板块锚点列表，用于左侧 TOC

    布局：
      <aside class="app-toc">    左侧常驻目录（≥1024px）/ 浮层（<1024px）
      <main class="app-main">    中间内容（max-width 880px）
        ├ page-main              主报告
        ├ page-info              说明子页
        └ page-drill-*           下钻子页
      <div class="app-actions">  右上 fixed [说明][主题]
      <div class="toc-overlay">  小屏 TOC 浮层背景
    """
    head = PAGE_HEAD.replace("{title}", escape(title))

    kicker_html = f'<div class="kicker">{escape(kicker)}</div>' if kicker else ""

    # 左侧 TOC（全局唯一）
    toc_html = ""
    if nav_items:
        nav_links = "".join(
            f'<li><a href="#{escape(a)}" '
            f'onclick="return navJump(\'#{escape(a)}\')">{escape(l)}</a></li>'
            for a, l in nav_items
        )
        toc_html = (
            f'<aside class="app-toc" id="app-toc">'
            f'<div class="app-toc-title">本报告板块</div>'
            f'<ul>{nav_links}</ul>'
            f'</aside>'
        )

    # 右上 fixed 浮按钮组（全局唯一）— 顺序：主题 → 说明 → 反馈
    # 反馈用 <a> 直链 <!-- FEEDBACK_URL -->，下游推送脚本替换占位符
    actions_html = (
        '<div class="app-actions">'
        '<button class="btn-theme" onclick="toggleTheme()" '
        'title="切换午夜主题" aria-label="切换午夜主题"></button>'
        '<button class="btn-info" onclick="toggleInfo()">说明</button>'
        '<a class="btn-feedback" href="<!-- FEEDBACK_URL -->" '
        'target="_blank" rel="noopener" title="意见反馈" aria-label="意见反馈">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
        '<line x1="12" x2="12.01" y1="17" y2="17"/>'
        '</svg></a>'
        '</div>'
    )
    overlay_html = '<div class="toc-overlay"></div>'

    # 小屏汉堡（每个 page-toolbar 注入一份，依赖 CSS 控制可见性）
    burger_html = (
        '<button class="toc-burger" onclick="toggleToc()" '
        'aria-label="打开目录">☰ 目录</button>'
        if nav_items else ""
    )
    back_btn = ('<button class="toolbar-back" onclick="showPage(\'page-main\')" '
                'aria-label="返回主报告">← 返回主报告</button>')

    # 主页 toolbar：[汉堡(小屏)] [标题h1（含 inline meta）]
    meta_inline = f'<span class="page-meta">{escape(meta_text)}</span>' if meta_text else ""
    main_toolbar = (
        f'<div class="page-toolbar">{burger_html}'
        f'<div class="toolbar-title">{kicker_html}<h1>{escape(title)}{meta_inline}</h1></div>'
        f'</div>'
    )

    main_section = (
        f'<section id="page-main" class="page">'
        f'{main_toolbar}{cards_html}'
        f'</section>'
    )

    def _sub_toolbar(sub_kicker: str, sub_title: str) -> str:
        """子页 toolbar：[汉堡(小屏)] [返回紧邻] [标题h2]。"""
        return (
            f'<div class="page-toolbar">{burger_html}{back_btn}'
            f'<div class="toolbar-title">'
            f'<div class="kicker">{escape(sub_kicker)}</div>'
            f'<h2>{escape(sub_title)}</h2>'
            f'</div></div>'
        )

    info_section = ""
    if info_html:
        info_section = (
            f'<section id="page-info" class="page" hidden>'
            f'{_sub_toolbar("说明", "口径、公式与亮灯标准")}'
            f'{info_html}'
            f'</section>'
        )

    drill_sections = ""
    for pid, ptitle, pbody in (drill_pages or []):
        drill_sections += (
            f'<section id="{escape(pid)}" class="page" hidden>'
            f'{_sub_toolbar("下钻详情", ptitle)}'
            f'{pbody}'
            f'</section>'
        )

    main_block = (
        f'<main class="app-main">'
        f'{main_section}{info_section}{drill_sections}'
        f'</main>'
    )

    footer_html = (
        f'<footer>{escape(footer_text)}</footer></body></html>'
        if footer_text else '</body></html>'
    )

    return head + toc_html + main_block + actions_html + overlay_html + footer_html
