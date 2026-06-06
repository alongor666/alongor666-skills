"""合集壳页 — 把 V1/V3/V4 三视图包进一个带顶部 Tab 的 self-contained 单文件。

设计目标:**单文件分发**——同事收到一个 HTML,双击即用,无任何路径依赖。

实现:
  - 3 个 <iframe> 用 `srcdoc` 内嵌 HTML(html.escape 给 attribute value)
  - 顶部 3 个 Tab(驾驶舱 / 叙事周报 / 超表)切走 display
  - 默认激活驾驶舱(cockpit)
  - 所有 iframe 在初始 HTML 中即包含完整内容,无外部文件依赖

代价:单文件 ~650KB(原 3.2KB);收益:同事保存到任何路径都能切换 3 视图。

产物:<output>/<org>_<year>_合集.html
依赖:同目录已存在 <org>_<year>_{cockpit,narrative,table}.html(由 render_v1/v3/v4 产出);
      读取后内嵌进合集,所以合集生成后,3 个独立文件不再是必要依赖。

生产环境推送(chexian.cretvalu.com)用同源相对路径走 src 模式也可,但本 skill
默认 self-contained,适合 IM/邮件分享。
"""
from __future__ import annotations

import html
from pathlib import Path


# Tab 定义:(slug, 中文标签, 文件名后缀)。顺序即 Tab 顺序,第一项默认激活。
_TABS = [
    ("cockpit", "驾驶舱", "cockpit"),
    ("narrative", "叙事周报", "narrative"),
    ("table", "超表", "table"),
]


def _e(s: str) -> str:
    return html.escape(str(s), quote=True)


def render_combined(ctx, args) -> Path | None:
    """生成 self-contained 合集页。要求三视图文件已写入同一 out_dir。

    Returns:
      合集 HTML 路径;若三视图文件缺失则返回 None(不阻断主流程)。
    """
    org = ctx.org
    year = ctx.year
    out_dir = Path(args.output)

    files = {slug: f"{org}_{year}_{suffix}.html" for slug, _label, suffix in _TABS}
    missing = [fn for fn in files.values() if not (out_dir / fn).exists()]
    if missing:
        print(f"      [combined] 跳过:缺少视图文件 {missing}")
        return None

    cs = ctx.cutoff.isoformat()

    # 读取 3 视图原始 HTML,注入"内嵌模式"CSS 隐藏视图自带顶栏(避免与合集 tabbar 重复),
    # 然后 escape 给 srcdoc attribute value
    # v1(dashboard.py)用 .topbar,v3(deck.py)用 .toolbar,v4(supertable.py)用 .topbar
    # 内嵌时这两个 class 全部隐藏;独立打开 v1/v3/v4 时不受影响(本注入只作用于 iframe srcdoc)
    hide_inner_topbar = (
        "<style data-embed-hide>"
        ".topbar,.toolbar{display:none !important;}"
        "</style>"
    )
    srcdocs: dict[str, str] = {}
    for slug, _label, _suffix in _TABS:
        view_path = out_dir / files[slug]
        raw = view_path.read_text(encoding="utf-8")
        # 在 </head> 前注入隐藏 CSS;若视图未带 </head>(降级)则跳过注入
        if "</head>" in raw:
            raw = raw.replace("</head>", hide_inner_topbar + "</head>", 1)
        srcdocs[slug] = html.escape(raw, quote=True)

    # Tab 按钮
    tab_btns = "\n".join(
        f'      <button class="tab{" active" if i == 0 else ""}" '
        f'data-target="frame-{slug}" type="button">{_e(label)}</button>'
        for i, (slug, label, _suffix) in enumerate(_TABS)
    )

    # 3 iframe 全部 srcdoc 内联,self-contained 无外部依赖
    frames = "\n".join(
        f'    <iframe id="frame-{slug}" class="view{" active" if i == 0 else ""}" '
        f'srcdoc="{srcdocs[slug]}" title="{_e(label)}"></iframe>'
        for i, (slug, label, _suffix) in enumerate(_TABS)
    )

    page = f"""<!doctype html>
<html lang="zh-CN" data-theme="ink">
<head>
<meta charset="utf-8"/>
<title>{_e(org)} {year} 经营诊断周报 · 合集 · {cs}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {{
    --bar-bg: #0f1115; --bar-fg: #e7e9ee; --bar-mut: #9aa0ad;
    --accent: #d98324; --accent-soft: rgba(217,131,36,.16);
    --line: #232733;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; background: #0f1115; }}
  body {{ display: flex; flex-direction: column; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }}
  .tabbar {{
    flex: 0 0 auto; display: flex; align-items: center; gap: 4px;
    padding: 8px 14px; background: var(--bar-bg); color: var(--bar-fg);
    border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10;
  }}
  .tabbar .brand {{ font-weight: 700; font-size: 14px; margin-right: 14px; letter-spacing: .3px; }}
  .tabbar .brand .cut {{ color: var(--bar-mut); font-weight: 400; font-size: 12px; margin-left: 8px; }}
  .tab {{
    appearance: none; border: 1px solid transparent; cursor: pointer;
    background: transparent; color: var(--bar-mut);
    font-size: 13px; padding: 6px 16px; border-radius: 8px; transition: all .15s;
  }}
  .tab:hover {{ color: var(--bar-fg); background: rgba(255,255,255,.05); }}
  .tab.active {{ color: var(--accent); background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }}
  .stage {{ flex: 1 1 auto; position: relative; min-height: 0; }}
  .view {{
    position: absolute; inset: 0; width: 100%; height: 100%;
    border: 0; display: none; background: #fff;
  }}
  .view.active {{ display: block; }}
</style>
</head>
<body>
  <div class="tabbar">
    <span class="brand">{_e(org)} {year} 经营诊断周报<span class="cut">数据截止 {cs} · 单文件分发</span></span>
{tab_btns}
  </div>
  <div class="stage">
{frames}
  </div>
<script>
(function () {{
  var tabs = document.querySelectorAll('.tab');
  function activate(targetId) {{
    var frame = document.getElementById(targetId);
    if (!frame) return;
    document.querySelectorAll('.view').forEach(function (f) {{ f.classList.remove('active'); }});
    frame.classList.add('active');
    tabs.forEach(function (t) {{
      t.classList.toggle('active', t.dataset.target === targetId);
    }});
  }}
  tabs.forEach(function (t) {{
    t.addEventListener('click', function () {{ activate(t.dataset.target); }});
  }});
}})();
</script>
</body>
</html>"""

    out_path = out_dir / f"{org}_{year}_合集.html"
    out_path.write_text(page, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"      [combined] 已写入:{out_path}({size_kb:.1f} KB · 3 视图 srcdoc 内嵌 · self-contained)")
    return out_path
