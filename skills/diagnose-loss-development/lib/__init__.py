"""diagnose-loss-development: 保单年度 × 发展期 满期赔付率/出险率/案均/人伤指标三角形 skill。

主入口：lib/cli.py（直接调用 `python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py`）

设计基础：复用 diagnose-period-trend 的 SQL 风格（CROSS JOIN periods → CROSS JOIN dw_anchors）
+ chexian-report-shell/lib 的渲染共享层（原 diagnose-html-render，2026-05-17 重命名）。
"""

__all__: list[str] = []
