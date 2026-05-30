"""跨维度 Top 异常排名（完整版，自 diagnose-period-trend/lib/anomalies.py 移植）。

设计原则：
  - 亮灯统一从 alerts.light() 取，禁止本模块硬编码颜色阈值
    （阈值如 89/93/70/75/10/12 在 alerts.TH 中，任何复刻 = bug）
  - 维度池：客户类别 11 × 三级机构 14 × 7 aux 单维（insurance_type/is_nev/...）
  - 指标池：仅 3 个打灯率值参与"严重度"——variable_cost_ratio / earned_claim_ratio /
    earned_loss_frequency。avg_claim 仅货车打灯不纳入跨维排名；自主系数为信息列。
  - 排序：默认 severity_x_premium = sev_weight × premium_share × (1 + |delta|/10)
    sev_weight: red=4 / yellow=2 / blue=0.5 / green=0 / gray=0
  - spark6：按 PERIOD_ORDER 顺序（36m/24m/yoy/12m/6m/ytd）返回 6 期值，供 sparkline

调用契约：
  compute_top_anomalies(df, n=8, strategy="severity_x_premium") -> list[Anomaly]
  df 必须含 derive_metrics 之后的全部列；时间窗默认 6 个（含上年同期）。

  build_drilldown_data(df) -> dict（交叉下钻预计算，供 V1 驾驶舱和 V4 超表嵌入）
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal, Optional

import pandas as pd

from .alerts import light
from .labels import short_category_label


# ===== 时间窗顺序 =====
PERIOD_ORDER = ["滚动36个月", "滚动24个月", "上年同期", "滚动12个月", "滚动6个月", "当年起保"]
YTD_LABEL = "当年起保"
YOY_LABEL = "上年同期"

# ===== 参与跨维度异常排名的 3 个率值指标（metric_col, alert_key, short_label） =====
RANKED_METRICS: list[tuple[str, str, str]] = [
    ("variable_cost_ratio",   "variable_cost_ratio_pct", "变率"),
    ("earned_claim_ratio",    "earned_loss_ratio_pct",   "赔付率"),
    ("earned_loss_frequency", "earned_loss_freq_pct",    "出险率"),
]

# ===== 7 个 aux 单维（field, dim_label, value→display 映射） =====
AUX_DIM_LABELS: dict[str, str] = {
    "insurance_type":       "险类",
    "coverage_combination": "险别",
    "is_nev":               "能源",
    "is_new_car":           "新旧车",
    "is_transfer":          "过户",
    "is_renewal":           "续保",
    "is_telemarketing":     "电销",
}
AUX_VALUE_LABELS: dict[str, dict[str, str]] = {
    "insurance_type":       {"交强险": "交强险", "商业保险": "商业险"},
    "coverage_combination": {"单交": "单交", "交三": "交三", "主全": "主全", "其他": "其他"},
    "is_nev":               {"true": "新能源", "false": "燃油"},
    "is_new_car":           {"true": "新车",   "false": "旧车"},
    "is_transfer":          {"true": "过户",   "false": "非过户"},
    "is_renewal":           {"true": "续保",   "false": "非续保"},
    "is_telemarketing":     {"true": "电销",   "false": "非电销"},
}

# 严重度权重
SEV_WEIGHT = {
    "alert-red":    4.0,
    "alert-yellow": 2.0,
    "alert-blue":   0.5,
    "alert-green":  0.0,
    "alert-gray":   0.0,
    "":             0.0,
}


@dataclass(frozen=True)
class Anomaly:
    """单条跨维度异常记录（完整版，含 spark6/note 等业务字段）。"""
    tag: str                 # URL 锚点 / focus key，如 "cat:摩托车:variable_cost_ratio"
    dim_label: str           # "客户类别·摩托车" / "三级机构·达州" / "电销·电销"
    dim_kind: str            # "cat" | "org" | "aux"
    dim_field: str           # "customer_category" | "org_level_3" | "is_telemarketing"
    dim_value: str           # 原始值（数据层）
    dim_display: str         # 展示用简称
    metric: str              # "variable_cost_ratio" / "earned_claim_ratio" / "earned_loss_frequency"
    metric_label: str        # "变率" / "赔付率" / "出险率"
    alert_key: str           # alerts.TH 的 key
    value: float             # YTD 当年值
    delta_vs_yoy: float      # 当年 - 上年同期（同维同值口径）
    delta_vs_12m: float      # 当年 - 滚动12个月
    sev: str                 # alerts.light 返回的 CSS 类
    sev_label: str           # 危险 / 异常 / 健康 / 优秀
    premium_share: float     # 该 cohort YTD 保费 / 整体 YTD 保费（%）
    spark6: list[float]      # 6 期值，按 PERIOD_ORDER 顺序，缺值为 NaN
    note: str                # 一句因果归纳（用于 V1 卡片副标 + V3 行动清单）

    def to_dict(self) -> dict:
        d = asdict(self)
        # NaN 在 json 里不合法，转 None
        d["spark6"] = [None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
                       for v in self.spark6]
        for k in ("value", "delta_vs_yoy", "delta_vs_12m", "premium_share"):
            v = d[k]
            if isinstance(v, float) and math.isnan(v):
                d[k] = None
        return d


# -------------------------------------------------------------------- utils

def _safe_float(v) -> Optional[float]:
    if v is None: return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _all_aux_mask(df: pd.DataFrame, exclude_field: Optional[str] = None) -> pd.Series:
    """7 个 aux 字段全部 = __ALL__（且排除 exclude_field 自身）"""
    fields = list(AUX_DIM_LABELS.keys())
    mask = pd.Series(True, index=df.index)
    for f in fields:
        if f == exclude_field: continue
        mask &= (df[f] == "__ALL__")
    return mask


def _slice_overall(df: pd.DataFrame) -> pd.DataFrame:
    """整体行（cat=__ALL__, org=__ALL__, 7 aux 全 __ALL__）— 6 期"""
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[is_all_cat & is_all_org & _all_aux_mask(df)].copy()


def _slice_by_cat(df: pd.DataFrame) -> pd.DataFrame:
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[(~is_all_cat) & is_all_org & _all_aux_mask(df)].copy()


def _slice_by_org(df: pd.DataFrame) -> pd.DataFrame:
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    return df[is_all_cat & (~is_all_org) & _all_aux_mask(df)].copy()


def _slice_by_aux(df: pd.DataFrame, field: str) -> pd.DataFrame:
    """单 aux 维（其他 6 aux + cat + org 全 __ALL__）"""
    is_all_cat = df["customer_category"] == "__ALL__"
    is_all_org = df["org_level_3"] == "__ALL__"
    is_active  = df[field] != "__ALL__"
    is_real    = df[field] != "__NULL__"
    return df[is_all_cat & is_all_org & is_active & is_real & _all_aux_mask(df, exclude_field=field)].copy()


# -------------------------------------------------------------------- builders

def _build_cohort_rows(
    df: pd.DataFrame,
    overall_premium_ytd: float,
) -> pd.DataFrame:
    """
    把所有 cohort（按 (dim_kind, dim_field, dim_value) 唯一）展开为长表，
    每行 6 个时间窗，再 pivot 成宽表方便取 YTD/YOY/12m。

    返回 DataFrame 列：
      dim_kind / dim_field / dim_value / dim_display
      + 6 个时间窗 × 3 指标 + policy_count + premium_sum
    """
    rows = []

    # ---- 1. 客户类别 ----
    by_cat = _slice_by_cat(df)
    for _, r in by_cat.iterrows():
        rows.append(dict(
            dim_kind="cat", dim_field="customer_category",
            dim_value=r["customer_category"],
            dim_display=short_category_label(r["customer_category"]),
            period_label=r["period_label"],
            variable_cost_ratio=r["variable_cost_ratio"],
            earned_claim_ratio=r["earned_claim_ratio"],
            earned_loss_frequency=r["earned_loss_frequency"],
            policy_count=r["policy_count"],
            premium_sum=r["premium_sum"],
        ))

    # ---- 2. 三级机构 ----
    by_org = _slice_by_org(df)
    for _, r in by_org.iterrows():
        rows.append(dict(
            dim_kind="org", dim_field="org_level_3",
            dim_value=r["org_level_3"],
            dim_display=r["org_level_3"],
            period_label=r["period_label"],
            variable_cost_ratio=r["variable_cost_ratio"],
            earned_claim_ratio=r["earned_claim_ratio"],
            earned_loss_frequency=r["earned_loss_frequency"],
            policy_count=r["policy_count"],
            premium_sum=r["premium_sum"],
        ))

    # ---- 3. 7 个 aux 维 ----
    for field, label_map in AUX_VALUE_LABELS.items():
        sub = _slice_by_aux(df, field)
        for _, r in sub.iterrows():
            raw = str(r[field])
            display = label_map.get(raw, raw)
            rows.append(dict(
                dim_kind="aux", dim_field=field,
                dim_value=raw,
                dim_display=f"{AUX_DIM_LABELS[field]}·{display}",
                period_label=r["period_label"],
                variable_cost_ratio=r["variable_cost_ratio"],
                earned_claim_ratio=r["earned_claim_ratio"],
                earned_loss_frequency=r["earned_loss_frequency"],
                policy_count=r["policy_count"],
                premium_sum=r["premium_sum"],
            ))

    long_df = pd.DataFrame(rows)
    if long_df.empty:
        return long_df
    return long_df


def _value_in_period(group: pd.DataFrame, period: str, col: str) -> Optional[float]:
    sub = group[group["period_label"] == period]
    if sub.empty: return None
    return _safe_float(sub.iloc[0][col])


# ── 跨维度下钻 ────────────────────────────────────────────────────────────────

_ALL_DIM_FIELDS = [
    "customer_category", "org_level_3", "insurance_type",
    "is_nev", "is_new_car", "is_transfer", "is_renewal",
    "is_telemarketing", "coverage_combination",
]

# 段 ID → DataFrame 列名
_SEC_FIELD: dict[str, str] = {
    "customer":  "customer_category",
    "branch":    "org_level_3",
    "insurance": "insurance_type",
    "combo":     "coverage_combination",
    "energy":    "is_nev",
    "newused":   "is_new_car",
    "transfer":  "is_transfer",
    "renewal":   "is_renewal",
    "telesales": "is_telemarketing",
}

# 所有段的有序列表（含 JS 显示标签，整体段排除在外）
DRILL_SEC_LIST: list[tuple[str, str]] = [
    ("customer", "客户类别"), ("branch", "三级机构"), ("insurance", "险类"),
    ("combo", "险别组合"), ("energy", "能源"), ("newused", "新旧车"),
    ("transfer", "过户"), ("renewal", "续保"), ("telesales", "电销"),
]

_DRILL_METRIC_COLS = (
    "variable_cost_ratio", "earned_claim_ratio",
    "earned_loss_frequency", "avg_claim_amount", "weighted_pricing_factor",
)
_DRILL_METRIC_ROUNDS = (1, 1, 1, 0, 3)  # 各指标保留小数位
_SEV_INT = {"alert-green": 1, "alert-blue": 2, "alert-yellow": 3, "alert-red": 4}


def _slice_cross_dim(df: pd.DataFrame, prim_f: str, prim_v: str, sec_f: str) -> pd.DataFrame:
    """提取 prim_f=prim_v 且 sec_f 各值、其余维度=__ALL__ 的行。"""
    mask = ((df[prim_f] == prim_v) &
            (df[sec_f] != "__ALL__") &
            (df[sec_f] != "__NULL__"))
    for f in _ALL_DIM_FIELDS:
        if f != prim_f and f != sec_f:
            mask &= (df[f] == "__ALL__")
    return df[mask]


def _rnd(v: Optional[float], dec: int) -> Optional[float]:
    """安全舍入，None/NaN 返回 None。"""
    f = _safe_float(v)
    return round(f, dec) if f is not None else None


def build_drilldown_data(df: pd.DataFrame) -> dict:
    """预计算所有维度 × 维度交叉下钻数据，供 V1 驾驶舱和 V4 超表嵌入 JS DD 对象。

    Returns:
        dict  键 "sec_id|||raw_primary_val|||sec2_id"
              值 [[disp_name, sev_int, [vcr×6], [lr×6], [freq×6], [avg×6], [coef×6]], ...]
              sorted by vcr YTD desc（最差在前）。
              sev_int: 0=gray/none, 1=green, 2=blue, 3=yellow, 4=red
    """
    result: dict = {}

    for sec_id, _ in DRILL_SEC_LIST:
        prim_f = _SEC_FIELD[sec_id]

        # 取主维度所有实际值
        if prim_f == "customer_category":
            prim_df = _slice_by_cat(df)
            prim_vals = [
                (v, short_category_label(v))
                for v in prim_df["customer_category"].unique()
                if v != "__ALL__"
            ]
        elif prim_f == "org_level_3":
            prim_df = _slice_by_org(df)
            prim_vals = [(v, v) for v in prim_df["org_level_3"].unique() if v != "__ALL__"]
        else:
            prim_df = _slice_by_aux(df, prim_f)
            lmap = AUX_VALUE_LABELS.get(prim_f, {})
            prim_vals = [
                (v, lmap.get(str(v), str(v)))
                for v in prim_df[prim_f].unique()
                if v not in ("__ALL__", "__NULL__")
            ]

        for sec2_id, _ in DRILL_SEC_LIST:
            if sec2_id == sec_id:
                continue
            sec2_f = _SEC_FIELD[sec2_id]
            sec2_lmap = AUX_VALUE_LABELS.get(sec2_f, {})

            for raw_v, _ in prim_vals:
                cross = _slice_cross_dim(df, prim_f, raw_v, sec2_f)
                if cross.empty:
                    continue

                sub_rows = []
                for sec2_val, grp in cross.groupby(sec2_f):
                    if str(sec2_val) in ("__ALL__", "__NULL__"):
                        continue
                    # 次级维度显示名
                    if sec2_f == "customer_category":
                        disp = short_category_label(str(sec2_val))
                    elif sec2_f == "org_level_3":
                        disp = str(sec2_val)
                    else:
                        disp = sec2_lmap.get(str(sec2_val), str(sec2_val))

                    n_ytd = int(_safe_float(_value_in_period(
                        grp[grp["period_label"] == YTD_LABEL],
                        YTD_LABEL, "policy_count")) or 0) if not grp[grp["period_label"] == YTD_LABEL].empty else 0
                    if n_ytd == 0:
                        continue

                    vcr_ytd = _value_in_period(grp[grp["period_label"] == YTD_LABEL], YTD_LABEL, "variable_cost_ratio")
                    sev_cls, _ = (light("variable_cost_ratio_pct", vcr_ytd, n_ytd)
                                  if vcr_ytd is not None else ("", ""))
                    sev_int = _SEV_INT.get(sev_cls, 0)

                    series_list = []
                    for col, dec in zip(_DRILL_METRIC_COLS, _DRILL_METRIC_ROUNDS):
                        series_list.append([
                            _rnd(_value_in_period(grp, p, col), dec)
                            for p in PERIOD_ORDER
                        ])

                    sub_rows.append([disp, sev_int, *series_list])

                sub_rows.sort(key=lambda r: (r[2][-1] or 0), reverse=True)
                if sub_rows:
                    result[f"{sec_id}|||{raw_v}|||{sec2_id}"] = sub_rows

    return result


def _format_note(
    metric: str, value: float, delta_yoy: Optional[float],
    sev: str, dim_display: str,
) -> str:
    """一句因果归纳：随 metric / sev / delta 适配口径"""
    m = {
        "variable_cost_ratio":   "变率",
        "earned_claim_ratio":    "赔付率",
        "earned_loss_frequency": "出险率",
    }[metric]
    val_fmt = f"{value:.1f}%" if value is not None else "—"
    sev_emoji = {"alert-red": "🔴", "alert-yellow": "🟡",
                 "alert-blue": "🔵", "alert-green": "🟢", "alert-gray": "⚪"}.get(sev, "")
    if delta_yoy is None:
        delta_part = "无可比上年同期"
    elif abs(delta_yoy) < 0.1:
        delta_part = "同比基本持平"
    else:
        direction = "升" if delta_yoy > 0 else "降"
        # 出险率/变率/赔付率：升=恶化，降=好转
        sign_word = "恶化" if delta_yoy > 0 else "好转"
        delta_part = f"同比{direction} {abs(delta_yoy):.1f} pt（{sign_word}）"
    return f"{sev_emoji} {dim_display} {m} {val_fmt}，{delta_part}"


# -------------------------------------------------------------------- main API

def compute_top_anomalies(
    df: pd.DataFrame,
    n: int = 8,
    strategy: Literal["severity_x_premium", "delta_only", "value_only"] = "severity_x_premium",
    min_policy_count_ytd: int = 30,
) -> list[Anomaly]:
    """跨维度 Top n 异常排名。

    Args:
      df: derive_metrics 之后的完整 DataFrame（含全部 GROUPING SETS 行）
      n: 返回前 n 项
      strategy: severity_x_premium（默认）/ delta_only / value_only
      min_policy_count_ytd: YTD 保单数下限（< 30 退化为 alert-gray，不参与排名）

    Returns:
      list[Anomaly]，按 strategy 综合得分降序
    """
    overall = _slice_overall(df)
    overall_ytd_row = overall[overall["period_label"] == YTD_LABEL]
    if overall_ytd_row.empty:
        return []
    overall_ytd_premium = _safe_float(overall_ytd_row.iloc[0]["premium_sum"]) or 0.0
    if overall_ytd_premium <= 0:
        return []

    long_df = _build_cohort_rows(df, overall_ytd_premium)
    if long_df.empty:
        return []

    # 按 (dim_kind, dim_field, dim_value) groupby
    candidates: list[tuple[float, Anomaly]] = []
    for (kind, field, val), grp in long_df.groupby(
        ["dim_kind", "dim_field", "dim_value"], dropna=False
    ):
        dim_display = grp["dim_display"].iloc[0]
        ytd_row = grp[grp["period_label"] == YTD_LABEL]
        if ytd_row.empty: continue
        n_policy = int(_safe_float(ytd_row.iloc[0]["policy_count"]) or 0)
        premium_ytd = _safe_float(ytd_row.iloc[0]["premium_sum"]) or 0.0
        premium_share = (premium_ytd / overall_ytd_premium * 100) if overall_ytd_premium > 0 else 0.0

        for metric_col, alert_key, metric_label in RANKED_METRICS:
            v_ytd = _value_in_period(grp, YTD_LABEL, metric_col)
            if v_ytd is None: continue
            v_yoy = _value_in_period(grp, YOY_LABEL, metric_col)
            v_12m = _value_in_period(grp, "滚动12个月", metric_col)
            d_yoy = (v_ytd - v_yoy) if v_yoy is not None else float("nan")
            d_12m = (v_ytd - v_12m) if v_12m is not None else float("nan")

            sev_cls, sev_lbl = light(alert_key, v_ytd, n_policy)
            if not sev_cls:
                continue

            # spark6 按 PERIOD_ORDER 顺序
            spark = [
                _value_in_period(grp, p, metric_col) if _value_in_period(grp, p, metric_col) is not None
                else float("nan")
                for p in PERIOD_ORDER
            ]

            # 综合得分（3 个指标都是"越高越差"——同比 > 0 = 恶化 = 应关注；< 0 = 好转 = 降权）
            worsening_delta = max(d_yoy, 0.0) if not math.isnan(d_yoy) else 0.0
            if strategy == "severity_x_premium":
                base = SEV_WEIGHT.get(sev_cls, 0.0) * (1.0 + premium_share / 10.0)
                penalty = 1.0 + worsening_delta / 10.0
                # "在好转的红"降权到 0.25（保留少量曝光但不抢 Top 位）
                direction_factor = 1.0 if (math.isnan(d_yoy) or d_yoy >= -0.5) else 0.25
                score = base * penalty * direction_factor
            elif strategy == "delta_only":
                # 只看恶化幅度——好转项目得分 0
                score = worsening_delta
            else:  # value_only
                # 越高越差指标用 value 自身；过滤好转项目
                score = v_ytd if (math.isnan(d_yoy) or d_yoy >= 0) else 0.0

            note = _format_note(metric_col, v_ytd, None if math.isnan(d_yoy) else d_yoy,
                                sev_cls, dim_display)

            anomaly = Anomaly(
                tag=f"{kind}:{val}:{metric_col}",
                dim_label={"cat": "客户类别·", "org": "三级机构·", "aux": ""}[kind] + dim_display,
                dim_kind=kind, dim_field=field, dim_value=val,
                dim_display=dim_display,
                metric=metric_col, metric_label=metric_label, alert_key=alert_key,
                value=v_ytd,
                delta_vs_yoy=float("nan") if math.isnan(d_yoy) else d_yoy,
                delta_vs_12m=float("nan") if math.isnan(d_12m) else d_12m,
                sev=sev_cls, sev_label=sev_lbl,
                premium_share=premium_share,
                spark6=spark,
                note=note,
            )
            candidates.append((score, anomaly))

    # 同一 cohort 可能对 3 个指标都登榜——保留最高得分的一项防止重复
    by_cohort: dict[str, tuple[float, Anomaly]] = {}
    for score, a in candidates:
        key = f"{a.dim_kind}:{a.dim_value}"
        if key not in by_cohort or score > by_cohort[key][0]:
            by_cohort[key] = (score, a)

    ranked = sorted(by_cohort.values(), key=lambda x: x[0], reverse=True)
    return [a for _, a in ranked[:n]]


# ── org-weekly 交叉下钻（B1）────────────────────────────────────────────────────

# org-weekly 5 窗标签顺序（从早到晚）
ORG_PERIOD_ORDER = ["上季度", "上月", "上上周", "上周", "当周"]
ORG_YTD_LABEL = "当周"

# DD row 指标列（org-weekly 4 个，无 coef）
_ORG_DRILL_METRIC_COLS = ("variable_cost_ratio_pct", "earned_loss_ratio_pct",
                           "earned_loss_freq_pct", "avg_claim")
_ORG_DRILL_METRIC_ROUNDS = (1, 1, 1, 0)


def build_org_drilldown_data(
    cross_df: "pd.DataFrame",
    period_order: Optional[list[str]] = None,
    ytd_label: Optional[str] = None,
) -> dict:
    """预计算 org-weekly 维度交叉下钻数据，供 V1/V4 嵌入 JS DD 对象。

    Args:
        cross_df: fetch_org_cross_data() 返回的长表
                  列：period, prim_sec_id, prim_val, sec2_id, sec2_val,
                      variable_cost_ratio_pct, earned_loss_ratio_pct,
                      earned_loss_freq_pct, avg_claim, policy_count, premium
        period_order: 5 窗标签顺序，默认 ORG_PERIOD_ORDER
        ytd_label: 当期标签，默认 "当周"

    Returns:
        dict  键 "prim_sec_id|||prim_val|||sec2_id"
              值 [[disp_name, sev_int, [vcr×5], [lr×5], [freq×5], [avg×5]], ...]
              按 vcr YTD 降序排列（最差在前）
    """
    if cross_df is None or cross_df.empty:
        return {}

    po = period_order or ORG_PERIOD_ORDER
    yl = ytd_label or ORG_YTD_LABEL
    result: dict = {}

    # 按 (prim_sec_id, prim_val, sec2_id) 分组
    group_keys = ["prim_sec_id", "prim_val", "sec2_id"]
    for (prim_sec_id, prim_val, sec2_id), grp in cross_df.groupby(group_keys, sort=False):
        sub_rows = []
        for sec2_val, val_grp in grp.groupby("sec2_val", sort=False):
            if str(sec2_val) in ("", "None", "__ALL__"):
                continue

            # YTD 件数
            ytd_rows = val_grp[val_grp["period"] == yl]
            if ytd_rows.empty:
                continue
            n_ytd = int(_safe_float(ytd_rows.iloc[0].get("policy_count")) or 0)
            if n_ytd == 0:
                continue

            # 亮灯（按变率）
            vcr_ytd = _safe_float(ytd_rows.iloc[0].get("variable_cost_ratio_pct"))
            sev_cls, _ = light("variable_cost_ratio_pct", vcr_ytd, n_ytd) if vcr_ytd is not None else ("", "")
            sev_int = _SEV_INT.get(sev_cls, 0)

            # 5 期各指标 series
            series_list = []
            for col, dec in zip(_ORG_DRILL_METRIC_COLS, _ORG_DRILL_METRIC_ROUNDS):
                series = []
                for p in po:
                    period_rows = val_grp[val_grp["period"] == p]
                    v = _safe_float(period_rows.iloc[0].get(col)) if not period_rows.empty else None
                    series.append(_rnd(v, dec))
                series_list.append(series)

            sub_rows.append([str(sec2_val), sev_int, *series_list])

        # 按 YTD 变率降序（最差在前）
        sub_rows.sort(key=lambda r: (r[2][-1] or 0) if len(r) > 2 and r[2] else 0, reverse=True)
        if sub_rows:
            result[f"{prim_sec_id}|||{prim_val}|||{sec2_id}"] = sub_rows

    return result
