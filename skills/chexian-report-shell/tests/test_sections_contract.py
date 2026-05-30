"""v1.20 契约测试 — 覆盖 time_windows / anomaly_base / render 兼容路径 / loader / get_threshold。

运行：
    pytest ~/.claude/skills/chexian-report-shell/tests/ -v
"""
import sys
from datetime import date
from pathlib import Path

import pytest

SHELL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SHELL_ROOT))


# ──────────────────────────────────────────────────────────────────────────────
class TestTimeWindows:
    def test_build_periods_trend_preset_returns_6_periods(self):
        from lib.time_windows import build_periods
        periods = build_periods(date(2026, 5, 24), preset="trend")
        assert len(periods) == 6
        labels = [p.label for p in periods]
        assert "当年起保" in labels
        assert "上年同期" in labels
        assert "滚动36个月" in labels

    def test_build_periods_weekly_preset_returns_5_periods(self):
        from lib.time_windows import build_periods
        periods = build_periods(date(2026, 5, 24), preset="weekly")
        assert len(periods) == 5
        labels = [p.label for p in periods]
        assert "当周" in labels
        assert "上季度" in labels

    def test_period_keys_subsetting(self):
        from lib.time_windows import build_periods
        periods = build_periods(date(2026, 5, 24), preset="trend", keys=["ytd", "yoy"])
        assert len(periods) == 2
        labels = [p.label for p in periods]
        assert "当年起保" in labels
        assert "上年同期" in labels

    def test_shift_months_leap_year_safe(self):
        from lib.time_windows import _shift_months
        result = _shift_months(date(2026, 3, 31), 1)
        assert result == date(2026, 2, 28)

    def test_build_periods_weekly_sorted_by_end(self):
        from lib.time_windows import build_periods
        periods = build_periods(date(2026, 5, 24), preset="weekly")
        ends = [p.end_incl for p in periods]
        assert ends == sorted(ends)

    def test_build_periods_string_cutoff(self):
        from lib.time_windows import build_periods
        periods = build_periods("2026-05-24", preset="trend")
        assert len(periods) == 6

    def test_make_weekly_windows_compat_start_is_jan1(self):
        """make_weekly_windows 返回的 start 必须是各年 Jan 1（包含边界，向后兼容）。"""
        from lib.queries import make_weekly_windows
        windows = make_weekly_windows(date(2026, 5, 24))
        assert len(windows) == 5
        for label, start, end in windows:
            assert start.month == 1 and start.day == 1, \
                f"{label}: start={start} 应为 Jan 1"


# ──────────────────────────────────────────────────────────────────────────────
class TestAnomalyBase:
    def test_rank_anomalies_severity_order(self):
        from lib.anomaly_base import Anomaly, rank_anomalies
        rows = [
            Anomaly("t1", "维度", "A", "earned_loss_ratio_pct", 80.0,
                    "alert-yellow", "异常", severity=2, premium_share=0.5, delta=5.0),
            Anomaly("t2", "维度", "B", "earned_loss_ratio_pct", 95.0,
                    "alert-red", "危险", severity=4, premium_share=0.3, delta=10.0),
            Anomaly("t3", "维度", "C", "earned_loss_ratio_pct", 55.0,
                    "alert-green", "优秀", severity=0, premium_share=0.2, delta=-5.0),
        ]
        ranked = rank_anomalies(rows, n=3, strategy="severity_x_premium")
        assert ranked[0].alert_class == "alert-red"
        assert ranked[-1].alert_class == "alert-green"

    def test_rank_anomalies_topn_truncation(self):
        from lib.anomaly_base import Anomaly, rank_anomalies
        rows = [
            Anomaly(f"t{i}", "维度", f"V{i}", "metric", float(i),
                    "alert-yellow", "异常", severity=2, premium_share=0.1, delta=float(i))
            for i in range(10)
        ]
        ranked = rank_anomalies(rows, n=5)
        assert len(ranked) == 5

    def test_rank_anomalies_unknown_strategy_raises(self):
        from lib.anomaly_base import rank_anomalies
        with pytest.raises(ValueError, match="未知排序策略"):
            rank_anomalies([], strategy="unknown")


# ──────────────────────────────────────────────────────────────────────────────
class TestRenderFacade:
    def test_legacy_import_from_lib_still_works(self):
        from lib import render_page, render_table, render_card, render_callout
        from lib import render_weekly_table, render_threshold_card, render_status_bar
        assert callable(render_page)
        assert callable(render_table)

    def test_new_render_subpackage_deep_imports(self):
        from lib.render.page import render_page
        from lib.render.table import render_table, HEADERS_8METRIC
        from lib.render.card import render_card, render_callout, render_rule
        from lib.render.narrative import render_problem_narrative, render_metric_narrative
        from lib.render.threshold import render_threshold_table, render_threshold_card
        from lib.render.weekly import render_weekly_table
        from lib.render.status import render_status_bar
        assert callable(render_page)
        assert len(HEADERS_8METRIC) == 10

    def test_render_package_root_imports(self):
        from lib.render import render_page, render_card, render_table
        assert callable(render_page)

    def test_render_page_produces_html(self):
        from lib import render_page
        html = render_page("测试标题", "<p>内容</p>")
        assert "<!DOCTYPE html>" in html
        assert "测试标题" in html


# ──────────────────────────────────────────────────────────────────────────────
class TestLoader:
    def test_load_shell_returns_full_api(self):
        from lib.loader import load_shell
        shell = load_shell(alias="_test_full_api")
        assert hasattr(shell, "light")
        assert hasattr(shell, "TH")
        assert hasattr(shell, "render_page")
        assert callable(shell.light)

    def test_load_shell_idempotent(self):
        from lib.loader import load_shell
        m1 = load_shell(alias="_test_idem")
        m2 = load_shell(alias="_test_idem")
        assert m1 is m2


# ──────────────────────────────────────────────────────────────────────────────
class TestThresholdAPI:
    def test_get_threshold_matches_TH_dict(self):
        """TH[key] 是三元组 (优秀线, 健康线, 危险线)，用索引 0/1/2 对齐。"""
        from lib import get_threshold, TH
        for metric_key, thresholds in TH.items():
            for i, expected in enumerate(thresholds):
                assert get_threshold(metric_key, i) == expected, \
                    f"get_threshold({metric_key!r}, {i}) 与 TH 不一致"

    def test_get_threshold_bad_key_raises(self):
        from lib import get_threshold
        with pytest.raises(KeyError):
            get_threshold("nonexistent_metric", 0)
