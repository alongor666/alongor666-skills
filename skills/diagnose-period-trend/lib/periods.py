"""时间窗口构造（v1.20 起委托 chexian-report-shell/lib/time_windows，保持 API 兼容）。

原始实现已下沉到 chexian-report-shell/lib/time_windows.py；本文件作为薄 shim 保持
调用方（query.py / cli.py / render.py）的 import 不变。

API 不变：
    from .periods import Period, PERIOD_KEYS, build_periods
    periods = build_periods(cutoff, keys=["ytd","yoy","12m"])
"""
from __future__ import annotations

from datetime import date

try:
    from ._dhr_bootstrap import dhr as _dhr
except ImportError:
    from _dhr_bootstrap import dhr as _dhr  # type: ignore[no-redef]

# ── 重新导出（维持调用方 import 不变）─────────────────────────────────────────
Period = _dhr.Period

# PERIOD_KEYS ≡ TREND_KEYS（顺序相同：36m/24m/yoy/12m/6m/ytd）
PERIOD_KEYS: list[tuple[str, str]] = _dhr.TREND_KEYS


def build_periods(cutoff: "date | str", keys: list[str] | None = None) -> list:
    """Thin shim：委托给 chexian-report-shell/lib/time_windows.build_periods(preset='trend')。"""
    return _dhr.build_periods(cutoff, preset="trend", keys=keys)


# 内部工具函数（供 query.py 偶有直接调用时兼容）
def _shift_months(cutoff: date, months: int) -> date:
    m = cutoff.month - months
    y = cutoff.year
    while m <= 0:
        m += 12
        y -= 1
    try:
        return date(y, m, cutoff.day)
    except ValueError:
        return date(y, m, 28)
