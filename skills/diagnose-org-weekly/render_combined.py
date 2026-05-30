"""合集壳页 — 把 V1/V3/V4 三视图包进一个带顶部 Tab 的单文件壳页。

根治"--view all 产出三个独立 HTML、无切换器"的 ad-hoc 痛点：
  - 顶部 3 个 Tab（驾驶舱 / 叙事周报 / 超表）
  - 3 个常驻 <iframe>，懒加载（首次激活才 set src）
  - 切换走 display 切换，**不重载、不重新鉴权**（已加载的 iframe 保活）
  - 默认激活驾驶舱（cockpit）

产物：<output>/<org>_<year>_合集.html
依赖：同目录已存在 <org>_<year>_{cockpit,narrative,table}.html（由 render_v1/v3/v4 产出）

生产环境内嵌前提：server/src/routes/reports.ts 的 CSP 含 `frame-src 'self'`
（PR #429 已放开），iframe src 用同源相对路径。
"""
from __future__ import annotations

import html
from pathlib import Path


# Tab 定义：(slug, 中文标签, 文件名后缀)。顺序即 Tab 顺序，第一项默认激活。
_TABS = [
    ("cockpit", "驾驶舱", "cockpit"),
    ("narrative", "叙事周报", "narrative"),
    ("table", "超表", "table"),
]


def _e(s: str) -> str:
    return html.escape(str(s), quote=True)


def render_combined(ctx, args) -> Path | None:
    """生成合集壳页。要求三视图文件已写入同一 out_dir。

    Returns:
      合集 HTML 路径；若三视图文件缺失则返回 None（不阻断主流程）。
    """
    org = ctx.org
    year = ctx.year
    out_dir = Path(args.output)

    # 校验三视图文件存在（缺失说明未跑全 all，跳过合集）
    files = {slug: f"{org}_{year}_{suffix}.html" for slug, _label, suffix in _TABS}
    missing = [fn for fn in files.values() if not (out_dir / fn).exists()]
    if missing:
        print(f"      [combined] 跳过：缺少视图文件 {missing}")
        return None

    cs = ctx.cutoff.isoformat()

    # Tab 按钮
    tab_btns = "\n".join(
        f'      <button class="tab{" active" if i == 0 else ""}" '
        f'data-target="frame-{slug}" type="button">{_e(label)}</button>'
        for i, (slug, label, _suffix) in enumerate(_TABS)
    )

    # 常驻 iframe：第一项立即 src，其余 data-src 懒加载
    frames = "\n".join(
        (
            f'    <iframe id="frame-{slug}" class="view{" active" if i == 0 else ""}" '
            f'src="{_e(files[slug])}" title="{_e(label)}" loading="eager"></iframe>'
            if i == 0 else
            f'    <iframe id="frame-{slug}" class="view" '
            f'data-src="{_e(files[slug])}" title="{_e(label)}" loading="lazy"></iframe>'
        )
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
    <span class="brand">{_e(org)} {year} 经营诊断周报<span class="cut">数据截止 {cs}</span></span>
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
    // 懒加载：首次激活才把 data-src 写入 src（已加载的保活，不重载、不重新鉴权）
    if (!frame.src && frame.dataset.src) frame.src = frame.dataset.src;
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
    print(f"      [combined] 已写入：{out_path}（{size_kb:.1f} KB · 3 视图 Tab 切换）")
    return out_path
