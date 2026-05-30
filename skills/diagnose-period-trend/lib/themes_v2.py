"""V1/V3/V4 三视图共享的 CSS token + 字体 + 基础样式（v2.1：支持 light/dark 双主题）。

设计来源：/tmp/design_pkg/untitled/project/V1 诊断驾驶舱.html
项目本地化：替换 navy/red/orange/green 为分公司经营口径色卡。

CSS 变量按用途分组：
  --paper / --surface       底色与纸面
  --ink                     文字（4 个深浅）
  --line                    分隔线（3 个深浅）
  --navy                    YTD 列高亮 / 关键 link / 蓝灯（健康）
  --red / --orange / --green 四级亮灯映射（red=危险 / orange=异常 / green=优秀；blue 复用 navy）

亮灯类映射（与 alerts.py:light() 返回值对齐）：
  alert-red    → --red    (#b8392b 危险)
  alert-yellow → --orange (#c97826 异常)
  alert-blue   → --navy   (#1c4878 健康)
  alert-green  → --green  (#3a7a4b 优秀)
  alert-gray   → --ink-mute (#8c8478 样本不足)

字体策略：
  - 标题 / 数字：Noto Serif SC（中文衬线，呼应"杂志/电子墨水"质感）
  - 正文：Noto Sans SC（中文无衬线）
  - 退路：PingFang SC（macOS 系统字体，离线可用）

主题切换：
  - THEME_INIT_SCRIPT：放 <head> 末尾，避免 FOUC（闪白）
  - DARK_CSS：[data-theme="dark"] 覆盖变量
  - theme_toggle_btn()：插入 TopBar 的一键切换按钮（CSS 驱动文字，零额外 JS）
  - 所有三个视图在 <html> 上打 data-theme 属性，localStorage key = 'diag-theme'（与壳库对齐）
"""

# Google Fonts 预连接 + CSS link
FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '<link href="https://fonts.googleapis.com/css2'
    '?family=Noto+Serif+SC:wght@400;500;600;700'
    '&family=Noto+Sans+SC:wght@300;400;500;600;700'
    '&display=swap" rel="stylesheet" />'
)

# CSS token + 全局基线（独立于具体视图）
BASE_CSS = """
:root{
  --paper:        #f4efe6;
  --paper-soft:   #ede7da;
  --surface:      #ffffff;
  --surface-soft: #faf6ee;
  --ink:          #1d1813;
  --ink-soft:     #5a5048;
  --ink-mute:     #8c8478;
  --ink-light:    #b2aa9d;
  --line:         #e6dfcf;
  --line-soft:    #efe8d8;
  --line-strong:  #d8d0bd;

  --navy:         #1c4878;
  --navy-deep:    #133258;
  --navy-soft:    rgba(28,72,120,0.08);
  --navy-line:    rgba(28,72,120,0.18);

  --red:          #b8392b;
  --red-soft:     rgba(184,57,43,0.08);
  --red-line:     rgba(184,57,43,0.25);
  --orange:       #c97826;
  --orange-soft:  rgba(201,120,38,0.10);
  --orange-line:  rgba(201,120,38,0.28);
  --green:        #3a7a4b;
  --green-soft:   rgba(58,122,75,0.10);
  --green-line:   rgba(58,122,75,0.28);

  --radius:       6px;
  --radius-sm:    4px;
  --radius-lg:    10px;

  --shadow-sm:    0 1px 2px rgba(29,24,19,0.04), 0 0 0 1px var(--line);
  --shadow-md:    0 2px 8px rgba(29,24,19,0.06), 0 0 0 1px var(--line);
  --shadow-pop:   0 12px 36px rgba(29,24,19,0.18), 0 0 0 1px var(--line-strong);
}
*{ box-sizing: border-box; }
html, body{ margin:0; padding:0; }
body{
  background: var(--paper);
  color: var(--ink);
  font-family: 'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,sans-serif;
  font-size: 14px;
  line-height: 1.5;
  font-feature-settings: 'tnum' 0;
  -webkit-font-smoothing: antialiased;
}
.serif{ font-family:'Noto Serif SC','PingFang SC',serif; }
.num { font-variant-numeric: tabular-nums; }

/* ── alert 映射：alerts.light() 返回类 → 设计颜色 token ─────────── */
.alert-red    { --bg: var(--red-soft);    --fg: var(--red);    --line-clr: var(--red-line); }
.alert-yellow { --bg: var(--orange-soft); --fg: var(--orange); --line-clr: var(--orange-line); }
.alert-blue   { --bg: var(--navy-soft);   --fg: var(--navy);   --line-clr: var(--navy-line); }
.alert-green  { --bg: var(--green-soft);  --fg: var(--green);  --line-clr: var(--green-line); }
.alert-gray   { --bg: var(--paper-soft);  --fg: var(--ink-mute); --line-clr: var(--line); }

.sev-dot{ display:inline-block; width:6px; height:6px; border-radius:50%; background: var(--fg); }
"""


# ── 暗主题 CSS 变量覆盖（data-theme="dark" 时生效）──────────────────────────
DARK_CSS = """
[data-theme="dark"]{
  --paper:        #18181f;
  --paper-soft:   #20202a;
  --surface:      #242432;
  --surface-soft: #2a2a3a;
  --ink:          #ece8df;
  --ink-soft:     #b4ac9c;
  --ink-mute:     #706860;
  --ink-light:    #46423c;
  --line:         #36323a;
  --line-soft:    #2e2c34;
  --line-strong:  #46424c;

  --navy:         #6094d8;
  --navy-deep:    #4878c0;
  --navy-soft:    rgba(96,148,216,0.14);
  --navy-line:    rgba(96,148,216,0.24);

  --red:          #e06050;
  --red-soft:     rgba(224,96,80,0.14);
  --red-line:     rgba(224,96,80,0.30);
  --orange:       #e09848;
  --orange-soft:  rgba(224,152,72,0.14);
  --orange-line:  rgba(224,152,72,0.32);
  --green:        #58b06a;
  --green-soft:   rgba(88,176,106,0.14);
  --green-line:   rgba(88,176,106,0.30);

  --shadow-sm:    0 1px 2px rgba(0,0,0,0.20), 0 0 0 1px var(--line);
  --shadow-md:    0 2px 8px rgba(0,0,0,0.30), 0 0 0 1px var(--line);
  --shadow-pop:   0 12px 36px rgba(0,0,0,0.50), 0 0 0 1px var(--line-strong);
}
"""

# ── 防 FOUC：<head> 末尾注入，页面渲染前读取存储主题────────────────────────
THEME_INIT_SCRIPT = """<script>
(function(){
  var t=localStorage.getItem('diag-theme')||'ink';
  document.documentElement.setAttribute('data-theme',t);
})();
</script>"""

# ── 切换按钮 CSS（SVG 图标随 data-theme 切换可见性）───────────────────────────
THEME_TOGGLE_CSS = """
#theme-btn{
  width:32px; height:32px; padding:0;
  display:inline-flex; align-items:center; justify-content:center;
  border:1px solid var(--line); background:var(--surface);
  color:var(--ink-soft); border-radius:6px; cursor:pointer;
  transition:background .15s, color .15s;
}
#theme-btn:hover{ background:var(--surface-soft); color:var(--ink); }
#theme-btn .icon-moon{ display:block; }
#theme-btn .icon-sun { display:none; }
[data-theme="dark"] #theme-btn .icon-moon{ display:none; }
[data-theme="dark"] #theme-btn .icon-sun { display:block; }
"""

THEME_TOGGLE_JS = """function _toggleTheme(){
  var el=document.documentElement;
  var next=el.getAttribute('data-theme')==='dark'?'ink':'dark';
  el.setAttribute('data-theme',next);
  try{localStorage.setItem('diag-theme',next);}catch(e){}
}"""

# 月亮图标 = 当前亮色模式，点击进入暗色；太阳图标 = 当前暗色模式，点击返回亮色
_MOON_SVG = (
    '<svg class="icon-moon" xmlns="http://www.w3.org/2000/svg" width="15" height="15" '
    'viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
    '</svg>'
)
_SUN_SVG = (
    '<svg class="icon-sun" xmlns="http://www.w3.org/2000/svg" width="15" height="15" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="5"/>'
    '<line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>'
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
    '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
    '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>'
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
    '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
    '</svg>'
)


def theme_toggle_btn() -> str:
    """返回插入 TopBar 的主题切换按钮 HTML（月亮/太阳图标，CSS 控制可见性）。"""
    return (
        f'<button id="theme-btn" onclick="_toggleTheme()" title="切换亮/暗主题">'
        f'{_MOON_SVG}{_SUN_SVG}'
        f'</button>'
    )


def style_block() -> str:
    """返回 <link> + <style> 块（含 light + dark 主题）。"""
    return f'{FONT_LINKS}\n<style>{BASE_CSS}{DARK_CSS}{THEME_TOGGLE_CSS}</style>'
