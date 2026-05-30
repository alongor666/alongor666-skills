---
name: chexian-report-shell
description: >-
  车险诊断报告渲染基础设施层（共享库，非业务工具）。提供 render_page / 四级亮灯 /
  SPA 拼装 / 9 维下钻元数据 / 多维多窗 DuckDB 查询 / 飞书企微推送等能力，
  被 diagnose-org-weekly / diagnose-period-trend / diagnose-loss-development
  等 diagnose-* 业务诊断 skill import 复用。本 skill 本身不直接面向用户，
  不通过 /xxx 调用——直接跑业务 skill 即可。
user_invocable: false
version: "1.21.0"
---

# chexian-report-shell: 车险诊断报告渲染基础设施

**所有 `diagnose-*` 业务诊断 skill 的统一渲染层 + 数据辅助层**。你写好 DataFrame，我负责渲染、亮灯、推送、SPA 拼装。

## 与业务诊断 skill 的分工

```
┌────────────────────────────────────────────────────────────────────┐
│  业务诊断层（diagnose-* 家族，user_invocable=true）                │
│  ├ diagnose-org-weekly        三级机构经营诊断周报（10 板块）       │
│  ├ diagnose-period-trend      短中长期对照（7 时间窗 × 7 指标）     │
│  ├ diagnose-loss-development  赔付率发展诊断（cohort + 月份矩阵）   │
│  └ rewrite-conclusion         L2 诊断结论 AI 重写                  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ from lib import ...
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  chexian-report-shell（本 skill，user_invocable=false）            │
│  └ lib/                                                            │
│      ├ render.py        render_page / render_table / render_card  │
│      │                  亮灯 / 双主题 / TOC / SPA / drill-toc     │
│      ├ alerts.py        四级亮灯阈值（优秀/健康/异常/危险）         │
│      ├ format.py        fmt_num / fmt_pct / fmt_wan / 简称转换    │
│      ├ labels.py        SHORT_LABEL / FULL_LABEL 单一事实源       │
│      ├ queries.py       standard_query / build_base_cte / UDF     │
│      ├ report_queries.py 项目专用 fetch_* 函数                    │
│      ├ dimensions.py    9 维下钻元数据 + ValueDef 注册表          │
│      ├ grouping_sets.py multi_dim_periods_query 多维多窗          │
│      ├ drill_body.py    下钻 body 生成器（v1.19 新增）            │
│      ├ page_ids.py      drill_page_id md5（v1.19 新增）           │
│      ├ context.py       SectionContext dataclass                  │
│      ├ contract.py      validate_metrics_df / 阈值同步断言        │
│      └ push.py          飞书 / 企微推送                            │
└────────────────────────────────────────────────────────────────────┘
```

## v1.19 (2026-05-17) 单文件 SPA + 业务工具剥离

**同日两次大改**：
1. 上午：下钻回归 SPA 模式（删 `lib/drill_writer.py`，复用 `render_page(drill_pages=...)`）
2. 下午：业务工具 `examples/org_weekly.py` + `examples/sections/*` 全部独立成 `diagnose-org-weekly` skill；本 skill 改名 `chexian-report-shell`，聚焦渲染基础设施

技术变更：
- **下钻 SPA 模式**：`render_page(drill_pages=[(id,title,body),...])` 原生支持 hidden section + onclick=showPage(id) 同窗口切换
- **新增 `lib/drill_body.py`**：`build_drill_body(dim_key, dim_value, ctx)` + `build_all_drill_pages(ctx)`
- **新增 `lib/page_ids.py:drill_page_id(dim_key, dim_value)`**：md5 哈希成稳定短 DOM id
- **`render.py` 加 drill-toc CSS + IntersectionObserver JS**：下钻页左侧 sticky TOC
- **`render_table:drill_hrefs` 语义变更**：保留签名兼容，等同 `drilldown_target_by_dim`（值视为 page_id），删除 `target=_blank`
- **删除文件**：`lib/drill_writer.py`、`examples/`（搬走）
- **改名**：`diagnose-html-render` → `chexian-report-shell`（旧名引起"渲染层混装业务工具"误导）

## v1.20 (2026-05-28) 组件拆分 + 新模块下沉

**技术变更**：
- **`render.py` 拆分**：1851 行 → `lib/render/` 子包（7 子模块 + `_assets.py`）；`lib/render.py` 保留为历史标记（Python 优先加载 package）；所有旧 import 路径零改动
- **新增 `lib/time_windows.py`**：`Period` dataclass + `build_periods(cutoff, preset)` + `WEEKLY_KEYS` + `TREND_KEYS`；`make_weekly_windows()` 改为薄包装（向后兼容）
- **新增 `lib/anomaly_base.py`**：`Anomaly` dataclass（通用骨架）+ `SEV_WEIGHT` + `rank_anomalies()`
- **新增 `lib/loader.py`**：`load_shell()` 一行 importlib 隔离加载，兼容 period-trend 已有的 `dhr_lib` 别名
- **`lib/__init__.py` 升级**：显式 `__all__`（补 v1.20 新符号）+ `get_threshold(metric_key, index)` 单点阈值入口
- **补契约测试**：`tests/test_sections_contract.py` 18 个用例（TestTimeWindows / TestAnomalyBase / TestRenderFacade / TestLoader / TestThresholdAPI），全 PASS
- **删废弃**：空目录 `examples/` / `styles/` 已删除

**向后兼容保证**：3 个下游 skill + 本仓库 2 个 ad-hoc 脚本（young_driver_diagnosis.py / callout_redesign_demo.py）零改动可用。

## v1.21 (2026-05-28) diagnose-period-trend 能力全面收编

**来源**：`diagnose-period-trend` 业务 skill 7367 行代码中的通用渲染能力上提到壳库。

**技术变更**（6 个 Phase）：
- **P1 主题切换交互层**：复用壳库已有 `ink/midnight` 双主题 CSS，移植 DPT 的切换按钮 + JS + localStorage 交互层；`render_page()` 新增 `show_theme_toggle` 参数；`_assets.py` 新增 `THEME_TOGGLE_CSS`/`THEME_INIT_SCRIPT`/`THEME_TOGGLE_JS`/`theme_toggle_btn()`
- **P2 增强版 sparkline**：`lib/render/weekly.py` 新增 `sparkline()`（area fill + dots + color_mode 可选）；保留 `_sparkline_svg()` 不动（零 breaking）
- **P3 跨维异常排名**：新增 `lib/anomaly_cross.py`（503 行）；`CrossAnomaly` dataclass（17 字段 superset）+ `compute_top_anomalies()` + `build_drilldown_data()`；pandas 依赖进壳库；`anomaly_base.py` 保持不变（零 breaking）
- **P4 V1 驾驶舱布局**：新增 `lib/render/dashboard.py`；`render_topbar()`/`render_rail()`/`render_kpi_strip()`/`render_anomaly_grid()`/`render_section_detail()`
- **P5 V3 叙事周报布局**：新增 `lib/render/deck.py`；`trend_svg()`/`scatter_svg()` SVG 工具 + `render_toolbar()`/`render_cover()`/`render_chapter()`/`render_resp_cards()`/`render_watchlist()`/`render_apx_table()` + `DECK_CSS`（A4 打印）
- **P6 V4 超表**：新增 `lib/render/supertable.py`；列冻结 CSS + 全字段超表 CSS + 客户端渲染 JS（搜索/排序/行展开/交叉下钻）+ `SUPERTABLE_CSS`/`SUPERTABLE_JS`

**新增公开符号**（`lib/__init__.py` 导出）：
- P2: `sparkline`
- P4: `render_topbar`, `render_rail`, `render_kpi_strip`, `render_anomaly_grid`, `render_section_detail`
- P5: `trend_svg`, `scatter_svg`, `render_toolbar`, `render_cover`, `render_chapter`, `render_resp_cards`, `render_watchlist`, `render_apx_table`, `DECK_CSS`
- P6: `SUPERTABLE_CSS`, `SUPERTABLE_JS`, `render_controls`, `render_footer`, `render_table_shell`

**向后兼容保证**：壳库现有 API 签名与行为不变，只增不改不删；DPT 侧改为薄委托（import 壳库）。

## 推荐 import 方式（v1.21）

| 场景 | 推荐 |
|---|---|
| **新建 `diagnose-*` skill**（推荐） | `from chexian_report_shell.loader import load_shell; shell = load_shell()` |
| 已存在 skill 维护 | 旧 `sys.path.insert` + `from lib import ...` 继续工作，**不强制迁移** |
| 本仓库 ad-hoc 脚本 | 同上，不强制迁移 |

## 时间窗 API（time_windows.py）

```python
from lib import build_periods, Period, TREND_KEYS, WEEKLY_KEYS
from datetime import date

# 趋势对照（6 窗口）
periods = build_periods(date(2026, 5, 24), preset="trend")
# 周报 YTD（5 窗口）
periods = build_periods(date(2026, 5, 24), preset="weekly")
# 裁剪
periods = build_periods(date(2026, 5, 24), preset="trend", keys=["ytd", "yoy", "12m"])

for p in periods:
    print(p.label, p.start_excl, p.end_incl)
```

`make_weekly_windows(cutoff)` 保留为兼容薄包装，返回 `[(label, start_incl, end), ...]` 与 v1.19 格式完全一致。

## 异常排名 API（anomaly_base.py）

```python
from lib import Anomaly, SEV_WEIGHT, rank_anomalies

rows = [Anomaly(...), ...]  # 从 alerts.light() 取 alert_class + alert_label
top8 = rank_anomalies(rows, n=8, strategy="severity_x_premium")
```

`strategy` 支持 `"severity_x_premium"`（默认）和 `"severity"`。业务 skill 可继承 `Anomaly` 扩展字段。

## get_threshold API

```python
from lib import get_threshold, TH

# TH[metric_key] = (优秀线, 健康线, 危险线) 三元组
notice_val = get_threshold("earned_loss_ratio_pct", 0)  # 优秀线 = 60
warn_val   = get_threshold("earned_loss_ratio_pct", 1)  # 健康线 = 70
danger_val = get_threshold("earned_loss_ratio_pct", 2)  # 危险线 = 75
```

替代各 skill 内散落的 `TH["metric"][0]` 访问，避免 TH 结构调整时漏改。

## 设计意图

- **共享渲染层**：所有 `diagnose-*` 业务 skill 共用一套四级亮灯 / 小样本警示 / 卡片样式 / IM 推送，避免每个 skill 各搞一套
- **阈值唯一事实源**：四级灯阈值取自项目 `diagnose_common.py` 的 `TH_*` 常量，与业务规则字典 v3.0 §938 完全一致
- **薄壳叠加**：本 skill → `chexian-im-push` skill → `chexian-api` 的 `push_html.py`，每层只做自己那部分
- **管理决策优先**：核心数据显性化（顶部状态条 + 亮灯对照），技术细节隐性化（折叠在对照卡内的指标公式段）

## v1.16-v1.17 视觉系统（飞书云文档式三栏 + 板块化）

### 页面布局（v1.16）

桌面端 ≥ 1025px：
- **左** `<aside class="app-toc">` 240px 常驻目录，板块名 + active 高亮（IntersectionObserver 监听 `.card[id^="section-"]`）
- **中** `<main class="app-main">` 主报告/下钻 880px、说明页 1140px（CSS `:has()` 切换）
- **右上** `.app-actions` fixed 浮按钮组，顺序：**主题 → 说明 → 反馈**
  - 主题切换（Lucide 月亮/太阳，墨水↔午夜，localStorage 记忆）
  - 说明（toggle 主页 / 说明页）
  - 意见反馈（Lucide `message-circle-question`，`<a href="<!-- FEEDBACK_URL -->">`，下游推送替换占位符）

移动端 ≤ 1024px：
- TOC 折叠为浮层，主页用汉堡按钮 `☰ 目录` 打开；子页不渲染汉堡
- 浮按钮组横排到右上 `top:8 right:8`

### 子页规则（v1.17）

- **说明页 / 下钻页**：通过 `body:has(#page-main[hidden])` 选择器隐藏 TOC + 汉堡，main 在 grid 中 `justify-self: center` 居中
- **主报告板块卡片**：可下钻行 整行 `onclick` + 维度文字渲染为蓝色加粗（`.dim-link`），hover 加底色 + 下划线；行内任意位置可点

### 表格视觉

- **状态色块按列对齐**：色块用 `position: absolute right:12px` 贴单元格右边缘，**同列色块自动整齐**
- **阈值表 nowrap**：表头与数字单元格 `white-space: nowrap`（指标/单位/优秀/健康/异常/危险全单行），公式/口径列保留多行
- **状态全词**：优秀 / 健康 / 异常 / 危险（去 emoji，纯 CSS 圆点）
- **打印样式**：`@media print` 隐藏 TOC / 浮按钮 / 汉堡 / 浮层遮罩

### 承接：chexian-api 项目级报告输出 5 条铁律

本 skill 是 chexian-api 项目 `DESIGN.md §4 数据报告交互规则（RED LINE）` 的范本实现。前端看板 / 后端 API / 其他 skill 接入新报告时，5 条铁律同样适用：

| 铁律 | 本 skill 实现位置 |
|------|------------------|
| 1. 合计行锚点（`row-total` 固定第一行不排序） | `lib/render/table.py:render_table`（自动检测 `dim == "合计"`） |
| 2. 一键排序（DESC 默认 / 文本走 localeCompare / 空值沉底） | `lib/render/_assets.py:PAGE_HEAD` 注入 `sortTable()` JS |
| 3. 问题诊断 chips "最差→最好" | `lib/render/narrative.py:render_problem_narrative` 读 `alerts.LOWER_WORSE` |
| 4. 字段简称双层映射 + 启动断言 | `lib/labels.py:SHORT_LABEL` / `FULL_LABEL` 末尾 assert |
| 5. 简称/维度归一化 UDF 同源 | `lib/format.py:short_*` + `lib/queries.py:register_udfs` |

→ 修改本 skill 的 5 条实现前，请先查阅项目 DESIGN.md 中的语义约定，避免"skill 内部一致但与项目其他报告不一致"的漂移。

## 如何被业务诊断 skill 集成

任何新建的 `diagnose-*` skill 只需 3 步即可复用本 shell：

### Step 1：sys.path 注入

```python
import sys
from pathlib import Path

SHELL_ROOT = Path.home() / ".claude" / "skills" / "chexian-report-shell"
sys.path.insert(0, str(SHELL_ROOT))

from lib import (
    render_page, render_table, render_card, render_weekly_table,
    standard_query, fetch_standard_window, make_weekly_windows,
    SectionContext,
    # SPA 下钻：
    build_all_drill_pages, multi_dim_periods_query, drill_page_id,
)
```

### Step 2：板块化结构（多 card 场景）

```
diagnose-<场景>/
├── SKILL.md             user_invocable=true，业务触发词
├── cli.py               主入口（< 200 行）：参数解析 + ctx 构造 + SECTIONS 循环
└── sections/
    ├── __init__.py      SECTIONS 注册（list 顺序 = TOC / 渲染顺序）
    └── <板块>.py        每板块暴露 build(con, ctx) -> (card, drills, nav)
```

### Step 3：参考实现

最完整的范本是 `diagnose-org-weekly`（10 板块 + 22 SPA 下钻）。另一个相对简单的范本是 `diagnose-period-trend`（双主表 + customer_category × aux 下钻）。

## 关键 API（lib/）

### 渲染层（render.py）

| 函数 | 作用 |
|---|---|
| `light(metric, val, n)` | 四级亮灯判定，返回 `(css 类名, 文字标签)`。标签为「优秀/健康/异常/危险」，小样本（n<30）返回「样本不足」 |
| `fmt_wan(v)` / `fmt_pct(v)` / `fmt_int(v)` | 数字格式化（万元 / 百分比 / 千分位） |
| `render_table(df, dim_label, headers, drilldown_target_by_dim)` | 单张表 HTML；`drilldown_target_by_dim={dim: page_id}` 触发行整体可点 + 维度蓝色链接（v1.17） |
| `render_card(title, sub, body, kicker, card_id)` | 卡片包裹；`card_id="section-xxx"` 注册 TOC 锚点（v1.16） |
| `render_callout(text, cite, level)` | 引用框，level ∈ info/warn/danger |
| `render_rule()` | 卡片内分隔线 |
| `render_weekly_table(metrics, time_labels)` | 周报 5 时序横向表（v1.7+），sparkline + 当周亮灯一致色 |
| `render_metric_narrative(...)` / `render_problem_narrative(...)` | 卡片顶部"问题导向叙述"块（改善/恶化、超线汇总） |
| `render_status_bar(items, warn_text, target_id)` | 顶部精简状态条 |
| `render_threshold_card()` | 「亮灯标准对照」+ 公式 + 口径表（v1.16 加 nowrap 表头/阈值格） |
| `render_page(title, cards_html, info_html, drill_pages, kicker, nav_items, footer_text)` | 整页 HTML，三栏布局 + 多 section（page-main / page-info / page-drill-*）|

### 标准查询层（queries.py，v1.3 新增）

| 函数 / 常量 | 作用 |
|---|---|
| `standard_query(con, where_clause, params, cutoff, extra_fields, dim_expr, order)` | 跑一条标准化诊断查询，返回符合 11 列契约的 DataFrame。**新场景只用调它，不再复制 80 行 SQL** |
| `auto_cutoff(con, where_clause, params)` | 自动从 max(policy_date) 取截止日期 |
| `make_weekly_windows(cutoff)` | 5 时序窗口生成（上季度 / 上月 / 上上周 / 上周 / 当周，均 YTD 截至日）|
| `build_base_cte(extra_fields, cutoff, where_clause)` | 仅返回 CTE 字符串（高级用法，自定义 SELECT 时用） |
| `DIM_EXPR` | 常用维度表达式速查（新旧车 / 能源类型 / 是否过户 / 起保月 / 车牌前两位）|
| `PRICE_BUCKETS` | 新车购置价分桶 SQL（私家车专用 7 档）|

### 板块共享取数（report_queries.py，v1.17 新增）

跨板块复用的 fetch 函数。原则：**两个及以上板块复用 → `lib/report_queries`；板块独占 → 内联到 `sections/xxx.py`**。

| 函数 | 作用 |
|---|---|
| `fetch_standard_window(con, org, time_field, start, end)` | 单窗口 standard_query 合计行 |
| `fetch_household_share(con, org, time_field, start, end)` | 家自车占比（customer_category = '非营业个人客车'）|
| `fetch_premium_growth(con, org, time_field, start, end)` | 同比保费增长率（处理 2/29 闰年边界）|
| `fetch_plan_completion(con, org, time_field, start, end)` | 计划达成率（plan_vehicle × 时间进度修正，level='organization' 防 double counting）|
| `fetch_renewal_rate(con, org, end)` | 商业险续保率（renewal_tracker fact 表，VIN 去重）|
| `fetch_cross_sell_completion(con, org, end)` | 交叉销售达成率（cross_sell fact 表 × plan_personal × 时间进度）|
| `PLAN_PARQUET` / `RENEWAL_PARQUET` / `CROSS_SELL_PARQUET` | 项目 fact 表本地 parquet 路径 |

### 跨板块上下文（context.py，v1.17 新增）

```python
@dataclass(frozen=True)
class SectionContext:
    org: str
    year: int
    cutoff: date
    time_field: str
    windows: list           # [(label, start, end), ...]
    time_labels: list       # ["上季度 03-31", ...]
    standard_rows: list     # 5 窗口 standard_query 合计（板块复用，避免重复扫表）
    sample_n: list
    total_premiums: list
```

主入口构造一次，板块只读消费；板块禁止回写。如需新字段，回主入口补上后传入。

### 契约校验层（contract.py，v1.3 新增）

| 函数 | 作用 |
|---|---|
| `validate_metrics_df(df, strict=True)` | 校验 DataFrame 是否符合 11 列契约 + 业务合理性。strict=True 时违反抛 ContractError，否则返回错误列表 |
| `assert_threshold_in_sync(skill_th, project_th_path)` | 对比本 skill `TH` 字典与项目 `diagnose_common.py` 的 `TH_*` 常量。返回 None 表示同步，否则给出差异说明 |
| `ContractError` | 契约违反异常类 |

### 推送层（push.py）

| 函数 | 作用 |
|---|---|
| `push_to_im(html_path, title, channels)` | 推送到飞书 ／ 企微 ／ 同步 VPS |

## DataFrame 列约定

每张表必须含以下列（缺则填 `NULL`）：

| 列名 | 含义 | 是否打灯 |
|---|---|---|
| `dim` | 维度值（中文） | — |
| `policy_count` | 保单数 | 决定小样本判定 |
| `premium` | 保费（元） | 否（显示万元） |
| `reported_claims` | 已报告赔款（元） | 否 |
| `earned_loss_freq_pct` | 满期出险率年化 | TH_IR (8/10/12) |
| `earned_loss_ratio_pct` | 满期赔付率 | TH_LR (60/70/75) |
| `per_policy_premium` | 件均保费 | 否 |
| `avg_claim` | 案均赔款 | 否 |
| `expense_ratio_pct` | 费用率 | 否（项目无独立阈值） |
| `variable_cost_ratio_pct` | 变动成本率 | TH_VC (85/91/94) |

## 阈值同步协议（红线）

`lib/alerts.py:TH` 是项目 `diagnose_common.py:93-98` 的瞬时镜像。

- **每季度**：维护者手动 diff 这两处，发现项目改了立即同步本 skill
- **改阈值前**：必须先在项目源改（diagnose_common.py），再同步本 skill，禁止反向

最近同步：2026-05-10。

## 与其他 skill 的关系

**上游消费者（独立 skill，调本 skill 能力）**：
- **`chexian-ir-diagnosis`**：出险率诊断编排器，多脚本协调输出（2026-05-18 由 `auto-ir-diagnosis` 改名）
- **`rewrite-conclusion`**：L2 诊断结论 AI 重写（读本 skill 产出的诊断卡片，改写为管理层语言）

**下游通道**：
- **`chexian-im-push`**：本 skill 的推送实现层（2026-05-18 由 `xcl-ppt2im` 改名）。`push.py` 调它的 `send-lark-html.sh` / `send-wecom-html.sh`

**横向参考**：
- **`magazine-web-ppt`**：不同分工——杂志风 PPT 是创意叙事载体（横向翻页 + WebGL），本 skill 是业务诊断结构化报告载体（纵向滚动 + 数据密集）。本 skill v1.2 借鉴了 magazine 的 CSS 变量主题系统与字体协同思路；v1.16 三栏布局借鉴飞书云文档式阅读体验

## 验收

- [ ] 阈值与 `diagnose_common.py` 一致（grep 对比）
- [ ] 上游业务诊断 skill 跑通：`diagnose-org-weekly/cli.py --org <机构>` 输出单文件 HTML
- [ ] 主页：左 TOC 常驻 + 当前板块 active 高亮 + 行可点下钻（维度蓝色）
- [ ] 说明页：无 TOC + main 1140 居中 + 阈值表头/数字单行 + 公式/口径多行
- [ ] 下钻页：无 TOC + main 880 居中 + 返回按钮紧邻标题左
- [ ] 右上 fixed 浮按钮组顺序：主题 / 说明 / 反馈，在所有页面所有视口可见
- [ ] 说明按钮 toggle：在主页点切到说明，在说明点切回主页
- [ ] 数字单元格色块按列对齐（同列所有色块在同一垂直线上）
- [ ] 飞书 / 企微推送成功（反馈按钮 `<!-- FEEDBACK_URL -->` 占位符被替换）
- [ ] HTML 在 chexian.cretvalu.com 上可访问（rsync 同步成功）
- [ ] 报告全中文，无英文字段名残留，无装饰 emoji
- [ ] page_id 跨进程稳定（不受 PYTHONHASHSEED 影响）
- [ ] 板块化场景：`pytest tests/test_sections_contract.py -v` 全 PASS

## 防僵化机制（v1.3 新增）

按"先抽公共能力，再做契约校验"两步：

1. **标准查询层**（`lib/queries.py`）— 把每个新场景必写的 ~80 行 SQL（base_cte + 8 指标 SELECT + ClaimsAgg 单键 JOIN）抽成 `standard_query()`。新编排脚本只声明「过滤条件 + 维度表达式」即可，**消除复制粘贴老 example 的诱惑**
2. **契约校验层**（`lib/contract.py`）— 调 `render_table` 前校验 DataFrame 列名/类型/业务合理性。SQL 漏乘 100、字段名漂移、负数保单数等问题立即报错
3. **阈值同步检查** — `assert_threshold_in_sync(TH, '项目 diagnose_common.py 路径')` 自动 diff 本 skill 与项目源，CI 或手动跑均可

**示例对比**（agent_ytd.py v1 → v2）：v1 的 ~250 行变 v2 的 ~140 行，删去的 ~110 行全是重复 SQL 模板，全部沉淀到 queries.py。

## 数字精度与中文名简化（v1.4 起）

**精度约定**：
- 绝对值（保费 / 已报告赔款 / 件均 / 案均 / 保单数）一律取整，无小数
- 率值（赔付率 / 出险率 / 费用率 / 变动成本率）保留 1 位小数

**中文名简称**（v1.5 升级为「品牌-地区」结构）：
- 经代：去 10 位编码 + 抽末尾地区 + 删公司类型冗余 + 应用品牌简称映射 + 拼接「品牌-地区」
  - `0110105059中国邮政集团有限公司四川省分公司` → `邮政-四川`
  - `0110104907四川省永成保险代理有限公司简阳分公司` → `永成-简阳`
  - `0110104388中国农业银行股份有限公司成都分行` → `农行-成都`
  - `0110104681平安创展保险销售服务有限公司四川分公司` → `平安创展-四川`
  - `0110102561宋红浪` → `宋红浪`（个人代理人不带横线）
- 业务员：去 8-12 位编码前缀
  - `210011913曾玲` → `曾玲`

**品牌简称映射**（`format.py:_BRAND_MAP`）：
- 邮政集团 → 邮政；邮政储蓄 → 邮储
- 农业银行 → 农行；工商银行 → 工行；建设银行 → 建行；中国银行 → 中行；交通银行 → 交行
- 招商银行 → 招行；中信银行 → 中信；浦发银行 → 浦发等
- 中国人寿 → 国寿；中国太保 → 太保；中国人保 → 人保财/人保寿等
- 没在映射表的品牌（如「永成」「平安创展」）保留原名

**SQL 与 Python 100% 同源**：
- Python 函数 `short_agent_name()` / `short_salesman_name()` 是单一事实源
- DuckDB 通过 `register_udfs(con)` 把它们注册成 UDF，SQL 里直接用：`short_agent_name(agent_name)`
- `standard_query()` 内部已自动调用 `register_udfs()`，编排脚本零额外动作

## 变更日志

- **v1.20.0（2026-05-28）**：render.py 1851 行 → `lib/render/` 子包（7 子模块 + `_assets.py` 存放 PAGE_HEAD）；`lib/render.py` 保留为历史标记（Python package 优先级高于同名 .py）；新增 `lib/time_windows.py`（`Period` + `build_periods` + `WEEKLY_KEYS` + `TREND_KEYS`，`make_weekly_windows` 改薄包装）；新增 `lib/anomaly_base.py`（`Anomaly` + `SEV_WEIGHT` + `rank_anomalies`）；新增 `lib/loader.py`（`load_shell()` importlib 隔离一行入口）；`lib/__init__.py` 补显式 `__all__` + `get_threshold(metric_key, index)` + `render_status_bar` 导出；删除空目录 `examples/` / `styles/`；`tests/test_sections_contract.py` 全量重写为 18 个 v1.20 契约测试（TestTimeWindows/TestAnomalyBase/TestRenderFacade/TestLoader/TestThresholdAPI），全 PASS；3 个下游 skill + 2 个 ad-hoc 脚本向后兼容，零改动
- **v1.17.0（2026-05-14）**：板块化重构 `org_weekly.py` — 主入口 679 → 156 行；新建 `examples/sections/` 含 `overview.py` / `customer_type.py` + `__init__.py` 注册；新建 `lib/report_queries.py` 收纳 6 个跨板块 fetch；新建 `lib/context.py` 定义 frozen `SectionContext` dataclass；page_id 改用 `hashlib.md5(name)[:8]` 跨进程稳定；反馈卡 → 右上 fixed 浮按钮 `<a class="btn-feedback">` + Lucide message-circle-question SVG；浮按钮组排序 主题→说明→反馈；说明按钮改 `toggleInfo()` 在主页/说明间切换；说明页 main 扩到 1140px（CSS `:has(#page-info:not([hidden]))`）+ 公式/口径列 min-width 240/280；子页（说明/下钻）隐藏 TOC + 汉堡 + main 居中（CSS `:has(#page-main[hidden])`）；可下钻行去 `›` caret，整行 onclick + 维度文字蓝色加粗（`.dim-link`），hover 加下划线；说明页阈值表头/数字格 `white-space: nowrap`；新增 `tests/test_sections_contract.py` 9 个契约单测全 PASS
- **v1.16.0（2026-05-14）**：飞书云文档式三栏布局：`<aside class="app-toc">` 240px 常驻 + `<main class="app-main">` 880px + `.app-actions` 右上 fixed 浮按钮组；IntersectionObserver 监听 `.card[id^="section-"]` 同步 TOC active；移动端 TOC 折叠为浮层（`.app-toc.open` + overlay）+ 汉堡按钮；CSS grid + grid-template-areas；`render_card(card_id=...)` 注入板块锚点；`render_page(nav_items=[...])` 接受板块列表自动渲染 TOC；`@media print` 隐藏所有导航元素
- **v1.15.0（2026-05-13）**：每页 sticky toolbar 含目录 dropdown + 标题 + 返回 + 说明 + 主题切换；目录 dropdown 全屏 z-index；点击外部关闭；主题图标用 Lucide SUN/MOON SVG（语义"显示目标主题"）
- **v1.11.0（2026-05-12）**：多页面架构 `<section class="page">` + `showPage(pageId)` 切换 + drilldown 改为跳转独立页（不再 inline 展开）+ page-info 独立页存放口径/阈值/公式说明
- **v1.9.0（2026-05-12）**：续保率（renewal_tracker fact 表，VIN 去重）+ 交叉销售达成率（cross_sell fact 表 × plan_personal × 时间进度）接入实数；摩托/挂车在应续口径排除
- **v1.8.0（2026-05-12）**：时间窗口按时序从早到晚排序（趋势 sparkline 直观连线）；列头改 `标签 MM-DD` 直显窗口截至日；计划达成率口径修正：plan_vehicle 替代 plan_total + level='organization' 防 double counting + 时间进度修正
- **v1.7.0（2026-05-12）**：周报 5 时序窗口（上季度 / 上月 / 上上周 / 上周 / 当周，均 YTD 累计仅截至日不同）+ `render_weekly_table` 横向时序表 + sparkline + 当周亮灯一致色 + `make_weekly_windows(cutoff)` 时间窗口生成器
- **v1.6.0（2026-05-11）**：经代地区取**最细一级**（街/路 > 区/县 > 市 > 省），无最细则上收（例：`泰源保险代理有限公司成都武侯区佳灵路第二营业部` → `泰源-佳灵路`；`某某保险代理有限公司成都武侯区营业部` → `某某-武侯区`）；用 lookahead `(?=(...))` finditer 收集所有候选，优先取「前有行政分隔符（区/县/市/省/盟/州/旗）的最末段」+ 删除报告中所有副标题/kicker/callout 解释段/footer 多余文字（仅保留标题 + 表格，让数据自证）
- **v1.5.0（2026-05-11）**：经代简称升级为「品牌-地区」结构（含通用品牌简称映射如农行/工行/邮政等 30+ 条）+ 用 DuckDB Python UDF 让 SQL 直接复用 Python 函数（确保两侧逻辑 100% 同源）+ 修复地区正则贪婪回退 bug + `standard_query()` 自动注册 UDF
- **v1.4.0（2026-05-11）**：经代用简称且去编码 + 业务员用中文去编码 + 绝对值取整无小数 + 率值保留 1 位小数
- **v1.3.0（2026-05-11）**：抽标准查询层 `queries.py`（消重复 SQL 80%）+ 加契约校验 `contract.py`（含阈值同步检查 + DataFrame schema 校验）+ 新增 `examples/org_ytd.py`（三级机构年初至今诊断，证明扩展易）+ 重构 agent_ytd.py 用新查询层
- **v1.2.0（2026-05-11）**：去英文 + 去 emoji + 顶部状态条 + 可折叠对照卡 + 状态全词「优秀/健康/异常/危险」+ 色块按列对齐 + 公式段整合到对照卡 + 主表自动洞察 callout
- **v1.1.0（2026-05-11）**：借鉴 magazine 字体协同 + CSS 变量双主题 + kicker 小标 + callout/rule API
- **v1.0.0（2026-05-11）**：从 `/tmp/pingan_chuangzhan_2026ytd.py` 一次性脚本沉淀，抽出 lib/ 共享渲染层 + examples/agent_ytd.py 示例
