"""diagnose-period-trend: 车险经营 · 短中长期对照 skill。

主入口：lib/cli.py（直接调用 `python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py`）
模块化调用：``from cli import run`` 后调用 ``run(**kwargs)``

注意：本 skill 设计为脚本式调用，不暴露 ``run`` 给 ``import diagnose_period_trend``
风格的调用方——避免引入"既是包又是脚本"的双重身份带来的 import 体操。
"""

__all__: list[str] = []
