"""跨维度异常排名基类（v1.20 下沉自 diagnose-period-trend/lib/anomalies.py）。

设计原则：
  - 只下沉通用骨架（字段 + 排序策略）
  - 不抽业务特定字段（sparkline 时间窗顺序、ranked metrics 名单、aux dim）
  - 下游 skill 可继承 Anomaly 扩展业务字段，或直接使用基类
  - 亮灯逻辑从 alerts.light() 取，禁止本模块硬编码颜色阈值
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Anomaly:
    """单条跨维度异常记录（通用骨架）。"""
    tag: str           # 维度组合标签（如 "category::非营业个人客车"）
    dim_label: str     # 维度名（如 "客户类别"）
    dim_value: str     # 维度值（如 "非营业个人客车"）
    metric: str        # 指标 key（对应 alerts.TH）
    value: float
    alert_class: str   # light() 返回的 CSS 类，如 "alert-red"
    alert_label: str   # 优秀 / 健康 / 异常 / 危险
    severity: int      # SEV_WEIGHT 映射后的权重
    premium_share: float  # 该维度占总保费比（0~1）
    delta: float          # 与基准期的差值（业务 skill 决定基准）
    note: str = ""        # 自由文本备注


# 严重度权重：匹配 alerts.light() 返回的 CSS 类
SEV_WEIGHT: dict[str, int] = {
    "alert-red":    4,
    "alert-yellow": 2,
    "alert-blue":   0,
    "alert-green":  0,
    "alert-gray":   0,
}


def rank_anomalies(
    rows: list[Anomaly],
    n: int = 8,
    strategy: str = "severity_x_premium",
) -> list[Anomaly]:
    """对异常列表按指定策略排序并截断到 top-N。

    Args:
        rows:     Anomaly 列表
        n:        保留条数（默认 8）
        strategy: 排序策略，当前支持：
                  "severity_x_premium" — sev_weight × premium_share × (1 + |delta|/10)
                  "severity"           — 仅 sev_weight，相同时按 delta 绝对值降序

    Returns:
        top-N 列表（已按 strategy 降序排序）
    """
    if strategy == "severity_x_premium":
        def _score(a: Anomaly) -> float:
            return a.severity * a.premium_share * (1 + abs(a.delta) / 10)
    elif strategy == "severity":
        def _score(a: Anomaly) -> float:  # type: ignore[misc]
            return a.severity * 1000 + abs(a.delta)
    else:
        raise ValueError(f"未知排序策略: {strategy!r}，支持 severity_x_premium / severity")

    return sorted(rows, key=_score, reverse=True)[:n]
