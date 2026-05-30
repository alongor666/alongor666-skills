"""时间窗口构造层（v1.20 下沉自 diagnose-period-trend/lib/periods.py）。

所有窗口统一用 (start_excl, end_incl] 半开闭模式：
  - start_excl：起保日期 > 这一天（开区间左端）
  - end_incl：起保日期 <= 这一天（闭区间右端）

两套预设：
  - TREND_KEYS：6 个滚动趋势窗口（搬自 period-trend PERIOD_KEYS）
  - WEEKLY_KEYS：5 个 YTD 累计窗口（搬自 queries.make_weekly_windows 口径）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    label: str        # 列标签（如 "当年起保" / "滚动12个月" / "当周"）
    start_excl: date  # 开区间左端：起保日期 > 这一天
    end_incl: date    # 闭区间右端：起保日期 <= 这一天


# ── 趋势对照预设（搬自 diagnose-period-trend/lib/periods.py:PERIOD_KEYS）────
TREND_KEYS: list[tuple[str, str]] = [
    ("36m", "滚动36个月"),   # start_excl = cutoff − 36 月（最早）
    ("24m", "滚动24个月"),
    ("yoy", "上年同期"),      # start_excl = cutoff.year − 2 年的 12/31
    ("12m", "滚动12个月"),
    ("6m",  "滚动6个月"),
    ("ytd", "当年起保"),      # start_excl = 当年 1/1 的前一天（最新）
]

# ── 周报 YTD 预设（与 queries.make_weekly_windows 口径完全一致）────────────
WEEKLY_KEYS: list[tuple[str, str]] = [
    ("last_quarter",    "上季度"),
    ("last_month",      "上月"),
    ("week_before_last","上上周"),
    ("last_week",       "上周"),
    ("this_week",       "当周"),
]


def _shift_months(cutoff: date, months: int) -> date:
    """从 cutoff 向前推 N 个月。月末越界（如 3/31 推 1 月）退化为 28 日（闰年安全）。"""
    m = cutoff.month - months
    y = cutoff.year
    while m <= 0:
        m += 12
        y -= 1
    try:
        return date(y, m, cutoff.day)
    except ValueError:
        return date(y, m, 28)


def build_periods(cutoff: date | str, *,
                  preset: str = "trend",
                  keys: list[str] | None = None) -> list[Period]:
    """构造时间窗列表。

    Args:
        cutoff:  数据截止日（date 或 'YYYY-MM-DD' 字符串）
        preset:  "trend"（默认，6 窗口趋势对照）或 "weekly"（5 窗口 YTD 周报）
        keys:    时间窗 key 白名单（如 ["ytd", "yoy"]）；None 表示该 preset 全部

    Returns:
        list[Period]，顺序与 preset 的 KEYS 定义一致
    """
    if isinstance(cutoff, str):
        cutoff = date.fromisoformat(cutoff)

    if preset == "weekly":
        return _build_weekly(cutoff, keys)
    if preset == "trend":
        return _build_trend(cutoff, keys)
    raise ValueError(f"未知 preset: {preset!r}，支持 'trend' / 'weekly'")


def _build_trend(cutoff: date, keys: list[str] | None) -> list[Period]:
    last_day_prev_year   = date(cutoff.year - 1, 12, 31)
    last_day_2years_ago  = date(cutoff.year - 2, 12, 31)
    try:
        prev_year_cutoff = date(cutoff.year - 1, cutoff.month, cutoff.day)
    except ValueError:
        prev_year_cutoff = date(cutoff.year - 1, cutoff.month, 28)

    all_periods: dict[str, Period] = {
        "ytd": Period("当年起保",   last_day_prev_year,        cutoff),
        "yoy": Period("上年同期",   last_day_2years_ago,       prev_year_cutoff),
        "6m":  Period("滚动6个月",  _shift_months(cutoff, 6),  cutoff),
        "12m": Period("滚动12个月", _shift_months(cutoff, 12), cutoff),
        "24m": Period("滚动24个月", _shift_months(cutoff, 24), cutoff),
        "36m": Period("滚动36个月", _shift_months(cutoff, 36), cutoff),
    }
    selected = keys or [k for k, _ in TREND_KEYS]
    return [all_periods[k] for k in selected if k in all_periods]


def _build_weekly(cutoff: date, keys: list[str] | None) -> list[Period]:
    """YTD 口径：每个窗口 start = 截止日所属年 1/1，end 各不同。"""
    cur_end  = cutoff
    last_end = cutoff - timedelta(days=7)
    prev_end = cutoff - timedelta(days=14)

    if cutoff.month == 1:
        last_month_end = date(cutoff.year - 1, 12, 31)
    else:
        last_month_end = date(cutoff.year, cutoff.month, 1) - timedelta(days=1)

    quarter = (cutoff.month - 1) // 3 + 1
    if quarter == 1:
        last_q_end = date(cutoff.year - 1, 12, 31)
    else:
        prev_q_end_month = (quarter - 1) * 3
        last_q_end = date(cutoff.year, prev_q_end_month + 1, 1) - timedelta(days=1)

    def ytd_start(end: date) -> date:
        return date(end.year, 1, 1) - timedelta(days=1)  # start_excl = 上年 12/31

    all_periods: dict[str, Period] = {
        "this_week":       Period("当周",   ytd_start(cur_end),        cur_end),
        "last_week":       Period("上周",   ytd_start(last_end),       last_end),
        "week_before_last":Period("上上周", ytd_start(prev_end),       prev_end),
        "last_month":      Period("上月",   ytd_start(last_month_end), last_month_end),
        "last_quarter":    Period("上季度", ytd_start(last_q_end),     last_q_end),
    }
    raw_keys = keys or [k for k, _ in WEEKLY_KEYS]
    periods = [all_periods[k] for k in raw_keys if k in all_periods]
    # 按 end_incl 从早到晚排序（左到右 = 时序前进，与 make_weekly_windows 一致）
    return sorted(periods, key=lambda p: p.end_incl)
