---
name: diagnose-period-trend
description: >-
  车险经营 · 短中长期对照（YTD / 上年同期 / 滚动 6/12/24/36 月 × 5 核心指标 × 11 客户类别 × 14 三级机构）。
  支持三视图输出：V1 驾驶舱（KPI + Top 异常卡）、V3 叙事周报（A4 打印）、V4 超表（分析师交互表）。
  当用户说 "短中长期对照"、"期间趋势诊断"、"YTD vs 上年同期"、"滚动 12/24/36 月对照"、
  "客户类别 × 时间窗"、"全局画像首页报告"、"经营开屏报告"、"周期趋势报告"、"趋势叙事周报"、
  "超表"、"分析师超表"、"驾驶舱"、"三视图" 时使用。
user_invocable: true
version: "2.0.0"
requires_skills:
  - chexian-report-shell   # 渲染基础设施（亮灯/格式化/SVG 图表/超表），经 _dhr_bootstrap 动态加载为 dhr_lib（运行时必需）
---

# diagnose-period-trend: 车险经营 · 短中长期对照（三视图版）

把"年初至今 / 上年同期 / 滚动 6/12/24/36 月"6 个时间窗 × 5 核心指标的整体 + 分客户类别 + 三级机构 + 7 辅助维度画像，渲染为三种 HTML 报告格式：**V1 驾驶舱 / V3 叙事周报 / V4 超表**。

## 三视图

| 视图 | `--view` | 文件名 | 场景 |
|------|---------|--------|------|
| V1 驾驶舱 | `v1` | `<cutoff>-dashboard.html` | 管理层周会开屏，Top 8 异常信号 + KPI 卡 |
| V3 叙事周报 | `v3` | `<cutoff>-weekly.html` | A4 打印 / PDF 发送，4 章节叙事 + 附录表 |
| V4 超表 | `v4` | `<cutoff>-table.html` | 分析师自助，多维交互过滤 + 列指标切换 |
| 全部生成 | `all` | 以上三个 | 一次生成三个文件 |
| 旧版多期对照 | `legacy` | `<cutoff>.html` | 保留旧版 7 窗 × 7 指标交互表 |

## 设计意图

- **常态资产**：从一次性 ad-hoc 脚本升级为可参数化复用的 skill；跨项目（私董会 / 作战地图 / chexian-api）共用同一套口径
- **门户视角**：默认输出到 `<project_root>/public/reports/diagnose-period-trend/`，作为车险看板首页"开屏第一眼"的入口报告
- **薄壳依赖**：渲染层依赖 `~/.claude/skills/chexian-report-shell`（亮灯、格式化），只负责本场景业务逻辑

## 数据口径（与 ad-hoc 完全一致）

- **时间锚**：起保日期 `insurance_start_date`
- **当年起保**：`[当年 1 月 1 日, cutoff]`
- **上年同期**：与"当年起保"日历对称，整体平移一年
- **滚动 N 月**：`(cutoff − N 月, cutoff]`，左开右闭
- **保单去重**：按 `(保单号, 起保日期)` 聚合，`HAVING SUM(premium) > 0`
- **赔款**：已结案取 `settled_amount`，未结案取 `reserve_amount`
- **满期保费**：`保费 × 满期天数 / 保险期限天数`（闰年感知 365/366）
- **变动成本率** = 满期赔付率 + 费用率（两个分母不同：满期保费 vs 签单保费）
- **满期出险率**：年化口径 `Σ(赔案 × 保险期限 / 满期天数) / 去重保单数`
- **自主系数**：仅商业险，调和加权 `Σ(商业险保费) / Σ(基准保费)`，结果应在 `[0.5, 1.5]`

## 参数表

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--cutoff` | `YYYY-MM-DD` | DuckDB 动态查 `MAX(insurance_start_date)` | 数据截止日（所有时间窗的锚点） |
| `--project-root` | 路径 | `$CHEXIAN_PROJECT_ROOT` 或 `cwd` | 用于解析 `policy/current/*.parquet` 路径 |
| `--output-dir` | 路径 | `<project_root>/public/reports/diagnose-period-trend/` | 输出目录 |
| `--output` | 路径 | 无 | 完整输出路径（仅 legacy 模式生效） |
| **`--view`** | `legacy\|all\|v1\|v3\|v4` | `legacy` | **三视图切换**（见上表） |
| `--metrics` | 逗号串 | 全部 7 个 | 可裁剪指标（legacy 模式专用） |
| `--exclude-categories` | 逗号串 | 空 | 排除客户类别（如 `摩托车,挂车`；legacy 模式专用） |
| `--periods` | 逗号串 | `ytd,yoy,6m,12m,24m,36m` | 裁剪时间窗（legacy 模式专用） |
| `--push-im` | flag | False | 跑完是否推 IM（飞书 / 企微） |
| `--feishu-doc` / `--wecom-chat` | str | 空 | 推送目标（仅 `--push-im` 时生效） |

## 调用方式

```bash
# 一次生成三个新视图（推荐日常使用）
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py \
  --cutoff 2026-05-26 \
  --project-root /path/to/chexian-api \
  --view all

# 单独生成 V4 超表（分析师）
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view v4

# 单独生成 V3 叙事周报（A4 打印）
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view v3

# 旧版多期对照（保留兼容）
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view legacy

# cutoff 自动取数据最大日期
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --view all

# 指定项目根（跨项目复用）
CHEXIAN_PROJECT_ROOT=/path/to/chexian-api python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --view all
```

## 工作流（3 步）

### Step 1 · 解析参数 & 构造时间窗
`lib/periods.py:build_periods(cutoff)` 输出 6 个 `Period(label, start_excl, end_incl)`：滚动 36/24 月 + 上年同期 + 滚动 12/6 月 + 当年起保。

### Step 2 · 执行单条 GROUPING SETS SQL
`lib/query.py:build_sql(cutoff, periods)` 生成 `policy_dedup → claims_agg → policy_exposure → GROUPING SETS` 的 DuckDB SQL，返回 `3500+ 行 × 26 列`（含整体 / 客户类别 / 三级机构 / 二维交叉 / 7 个辅助维度）。`derive_metrics()` 用 `SUM(分子) / SUM(分母)` 计算 5 个派生指标。

### Step 3 · 三视图渲染
| 渲染器 | 文件 | 核心技术 |
|--------|------|---------|
| `lib/render_v1.py` | `*-dashboard.html` | Python SSR + 四级亮灯异常卡 + KPI Strip |
| `lib/render_v3.py` | `*-weekly.html` | Python SSR + SVG 折线/散点图 + `@page` A4 打印 |
| `lib/render_v4.py` | `*-table.html` | Python SSR + JS 渲染超表（列冻结 + 搜索 + 排序 + 展开行） |
| `lib/render.py` | `*.html` (legacy) | 旧版交互表（含 SPA 下钻页） |

共享层：`lib/anomalies.py`（Top 异常计算）· 主题 CSS token 已下沉基座 `chexian-report-shell/lib/themes_v2.py`，经 `dhr_lib.themes_v2` 取用（ADR-002，原 `lib/themes_v2.py` 已迁出）

## QC 自检（CLI 输出，三视图模式）

三视图模式（`--view all/v1/v3/v4`）打印：
- 时间窗 × 6 个的实际覆盖范围
- DuckDB 查询返回行数
- 每个视图的文件路径 + KB 大小

旧版模式（`--view legacy`）额外打印：
- 整体行逐期指标表
- 滚动窗保单件数单调性（6/12/24/36 月）
- 自主系数范围 `[0.5, 1.5]`
- 客户类别数 vs 注册表 11 类

## 不在 skill 范围

- ❌ skill **不动**指标公式（与 `server/src/config/metric-registry/categories/cost.ts` 对账后 hardcode）
- ❌ skill **不动** ETL（HTML 仅消费 Parquet，不修改）
- ❌ skill **不自动推送 VPS**——VPS 托管和自动化由后续 PR 解决
