---
name: diagnose-loss-development
description: >-
  车险经营 · 多年保单赔付发展三角形（保单年度 2022~ × 观察期 30/90/180/270 天 + 满 1/2 年 × 6 指标 × 12 维度）。
  生成交互式单页 HTML 报告，顶部 sticky 全局控制栏（保单年度 × 指标，一处切换联动所有卡），6 指标含满期赔付率/出险率/案均/满期保费/人伤案占比/人伤金额占比，
  12 维度含客户类别/三级机构/团队/业务员/风险等级/险类/险别组合/是否新能源/是否新车/是否过户/是否续保/是否电销；维度卡内行按当年满期保费规模降序。
  含完成度截尾标记（✓/△/—）与四级亮灯。
  当用户说 "保单赔付发展"、"发展三角形"、"满 1 年/2 年赔付率"、"多年保单赔付对比"、
  "人伤案件 vs 人伤金额"、"赔付率成熟曲线" 时使用。
user_invocable: true
version: "2.4.0"
requires_skills:
  - chexian-report-shell   # 渲染基础设施（亮灯/格式化/SPA 拼装），经 _shell.py 注入 SHELL_ROOT 后 from lib import（运行时必需）
---

# diagnose-loss-development: 多年保单赔付发展三角形

把 5 个保单年度（2022~2026）× 6 个观察期锚点（30/90/180/270 天 + 满 1 年 / 满 2 年）的"赔付率成熟曲线"渲染成交互式单页 HTML。诊断核心：**频率（出险率）vs 严重性（案均、人伤金额占比）vs 综合（赔付率）三视角同表对比**。

## 设计意图

- **金标三角形**：精算最经典口径，看保单年度在不同观察期的赔付收敛轨迹
- **全局控制栏**：保单年度 × 指标（v2.3 起 sticky 顶部一组，替代每卡局部双切换器）——一处切换即时联动整体三角 + 全部维度卡，跨维度同口径可比；指标作用于所有表，年度作用于各维度卡（整体三角按年成行、不受年度切换影响）。数据全量嵌入 cell data 属性，切换纯前端、零取数
- **截尾标记**：`✓ 完整观察 / △ 部分（< 95% 保单完成）/ — 未到`，避免老年度/新年度不可比
- **人伤双指标**：案占比（频率）+ 金额占比（严重性）配对呈现"频率轻、金额重 5 倍"的人伤特性
- **规模视角**：满期保费（v2.4 起）作可切换指标，与赔付率/出险率对照——先看"盘子多大"再判"赔得好不好"，避免被小样本极端率值误导
- **保费规模排序**：维度卡内各行按当年满期保费从大到小排序（v2.4 起，替代原保单数排序），让"赔付高且保费大"的重点盘自然上浮到表首；首行"整体"基准行豁免、恒钉首位；整体三角按保单年度成行、不参与排序
- **整体基准行**：Card 2-13 每张表首行"整体"作同年度同观察期对照

## 数据口径

- **PY 范围**：2022 ~ 当前年（前两年数据少、老案已封口）
- **DW 锚点**：30 / 90 / 180 / 270 / 365（满期 1 年）/ 730（满期 2 年）天
- **PY 切片**：`YEAR(insurance_start_date)`，按起保年划归
- **DW 真实暴露**：`exposed_days = LEAST(dw_days, term_days, cutoff - start)` — 三道闸：观察期 / 保单期 / 截止日
- **满期保费**：`premium × exposed_days / term_days`（按真实暴露天数，**必须用 exposed_days 而非 LEAST(dw,term)**——partial cell 下分子受 cutoff 约束，分母也须同比缩放）
- **完成度**：`SUM(is_complete) / COUNT(policy)`，`is_complete = (cutoff - start >= dw_days)`
- **赔款（项目标准口径）**：
  - 已结案（`settlement_time ≤ start + dw_days`）→ `settled_amount`
  - 未结案 → `reserve_amount`（项目标准，非 `pending_amount`）
  - 二选一不相加；人伤金额（`settled_bodily_amount` / `reserve_bodily_amount`）同口径
- **案件归集**：`accident_time ∈ [start, start + dw_days]` 且 `report_time ≤ cutoff`
- **保单去重**：按 `(policy_no, start, end, py)` SUM(premium)，`HAVING SUM(premium) > 0`

## 6 个核心指标

| ID | 中文 | 公式 | 单位 | 亮灯阈值 |
|---|---|---|---|---|
| `mature_loss_ratio`    | 满期赔付率   | (已决+未决) ÷ 满期保费 | % | `earned_loss_ratio_pct`：≤60 优 / 70 健 / 75 异 / >75 险 |
| `mature_incident_rate` | 满期出险率   | **SUM(赔案件数 × 保单期 / 暴露天数) ÷ 保单数**（年化口径，与 metric-registry `earned_loss_frequency` v2.1.0 一致；未满期 cell 按 `term_days/exposed_days` 放大到等价 1 年） | % | `earned_loss_freq_pct`：≤8 优 / 10 健 / 12 异 / >12 险 |
| `avg_claim_amount`     | 案均赔款     | 总赔款 ÷ 赔案件数      | 元 | 不打灯 |
| `earned_premium_sum`   | 满期保费     | `SUM(premium × exposed_days / term_days)`（聚合原料列，规模视角；v2.4 起作可切换指标，cell 折万元保 1 位小数） | 万元 | 不打灯 |
| `bi_case_ratio_pct`    | 人伤案占比   | 人伤案件 ÷ 总案件      | % | 不打灯（新登记于 metric-registry v1.0.0） |
| `bi_amount_ratio_pct`  | 人伤金额占比 | 人伤赔款 ÷ 总赔款      | % | 不打灯（新登记于 metric-registry v1.0.0） |

## 12 个维度（Card 2-13）

| Card | 维度 key | 标签 | 备注 |
|------|---------|------|------|
| 2 | `customer_category` | 客户类别 | — |
| 3 | `org_level_3` | 三级机构 | — |
| 4 | `team` | 团队 | top 10，JOIN dim_salesman 取中文 |
| 5 | `salesman_chinese` | 业务员 | top 15，JOIN dim_salesman 取纯姓名 |
| 6 | `insurance_grade` | 风险等级 | — |
| 7 | `insurance_type` | 险类 | 交强险 / 商业保险 |
| 8 | `coverage_combination` | 险别组合 | — |
| 9 | `is_nev` | 是否新能源 | 新能源 / 燃油 |
| 10 | `is_new_car` | 是否新车 | 新车 / 旧车 |
| 11 | `is_transfer` | 是否过户车 | 过户 / 非过户 |
| 12 | `is_renewal` | 是否续保 | 续保 / 新保 |
| 13 | `is_telemarketing` | 是否电销 | 电销 / 非电销 |

Card 2-13 默认显示 **2025 年**切片（用户重点关注），通过**页面顶部 sticky 全局控制栏**（v2.3 起）即时切到 2022/2023/2024/2026 任一年，所有维度卡同步联动；指标切换同样由全局栏统一驱动整体三角与全部维度卡。未观察完整的 cell 标 △ 并附浅灰斜纹底。**行序（v2.4 起）按当前年满期保费规模从大到小排，首行"整体"基准恒钉首位**；排序锚点取该年最成熟可得观察期（365→270→…）的原始满期保费，不受 △/— 显示标记影响，切年度时行序固定不跳（避免 top_n 抖动）。

## 参数表

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--cutoff` | `YYYY-MM-DD` | DuckDB 动态查 `MAX(policy_date)` | 数据截止日（DW 计算锚点） |
| `--project-root` | 路径 | 必填 | 用于解析 `policy/current/*.parquet` + `claims_detail/claims_*.parquet` |
| `--out` | 路径 | 不指定时仅控制台输出 Card 1 三角形 | 本地预览模式：HTML 输出路径 |
| `--deploy` | flag | False | 部署模式：输出到 `{project-root}/server/data/reports/{report-id}/{cutoff}/`，与 `--out` 互斥 |
| `--report-id` | 字符串 | `diagnose-loss-development` | `--deploy` 模式下的报告 ID（须与后端 `ALLOWED_REPORT_IDS` 一致） |

## 部署到 chexian.cretvalu.com

**生产 URL 模式**：

```
https://chexian.cretvalu.com/api/reports/diagnose-loss-development/{cutoff}/preview-mvp.html
                                          └─── 后端白名单 ────┘ └─ 快照 ─┘ └─ 子页相对路径 ─┘
```

**部署流程**（4 步）：

```bash
# 1. 在 chexian-api 项目根目录生成报告（约 2 分钟）
cd /Users/alongor666/Downloads/底层数据湖DUD/chexian-api
python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
  --cutoff $(date +%F) --project-root "$(pwd)" --deploy

# 2. 同步到 VPS（rsync --no-delete 累积历史快照）
node scripts/sync-vps.mjs

# 3. 验证（带 admin cookie，否则 401）
curl -b "token=<admin_jwt>" \
  https://chexian.cretvalu.com/api/reports/diagnose-loss-development/$(date +%F)/preview-mvp.html

# 4. 推送企微通知（v2.2.1 自动化）—— 用专用 meta 让本报告独立成一张 smartsheet
python3 数据管理/integrations/wecom_bot/push_html.py \
  --external-url "https://chexian.cretvalu.com/api/reports/diagnose-loss-development/$(date +%F)/preview-mvp.html" \
  --title "多年保单赔付发展报告 $(date +%F)" \
  --note "v2.1 主页 · 含 75 子页下钻" \
  --meta 数据管理/integrations/wecom_bot/state/_loss_dev_meta.json \
  --name "chexian-api · 多年保单赔付发展报告"
# --external-url 跳过本地 stage，--meta 独立缓存避免污染共享表，--name 首跑建表用
```

**后端架构**：

- 路由：`GET /api/reports/:reportId/:snapshot/*`（[server/src/routes/reports.ts](../../../Downloads/底层数据湖DUD/chexian-api/server/src/routes/reports.ts)）
- 白名单：`ALLOWED_REPORT_IDS = {'diagnose-loss-development'}`
- 校验：报告 ID 白名单 + snapshot `YYYY-MM-DD` 格式 + 子路径拒绝 `..`/`\`/绝对路径 + `validatePathWithinDirectory` 防符号链接逃逸
- 鉴权：沿用 `authMiddleware`（管理员账号；凭据由 chexian-api 项目侧密钥管理维护，**禁止写入本仓任何文件**）
- CSP：沿用现有 `REPORT_HTML_CSP`（允许内联 JS + jsdelivr）

**历史快照**：rsync 用 `--no-delete` 累积，每个 cutoff 一个独立快照目录。需定期清理时手动 `rm -rf server/data/reports/diagnose-loss-development/2025-*`（保留近 N 天）。

## 调用方式

```bash
# 控制台验证（Phase 1 mode：仅 Card 1）
python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
  --cutoff 2026-05-14 \
  --project-root '/Users/alongor666/Downloads/底层数据湖DUD/chexian-api'

# 生成完整 HTML（10 卡片）
python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
  --cutoff 2026-05-14 \
  --project-root '/Users/alongor666/Downloads/底层数据湖DUD/chexian-api' \
  --out '/Users/alongor666/Downloads/底层数据湖DUD/chexian-api/public/reports/diagnose-loss-development/2026-05-14.html'
```

## 文件结构

```
~/.claude/skills/diagnose-loss-development/
├── SKILL.md                ← 本文件
├── README.md               ← 渲染管线 / lib 模块职责（重资产内部文档）
└── lib/
    ├── __init__.py
    ├── _shell.py            ← chexian-report-shell 根定位（ADR-001，本技能集中一处）
    ├── cli.py               ← 编排：argparse + run() + render_html() + main()
    ├── query.py             ← SQL 构造（CTE + GROUPING SETS）+ derive_metrics()
    └── render.py            ← render_dev_triangle() + render_dim_card() + 指标切换 JS
```

## 依赖

- **DuckDB**：`pip install duckdb pandas`
- **dhr_lib**：`~/.claude/skills/chexian-report-shell`（render_card / render_page / render_callout / light / fmt_*；2026-05-17 由 diagnose-html-render 重命名）
- **数据**：`数据管理/warehouse/fact/policy/current/*.parquet` + `数据管理/warehouse/fact/claims_detail/claims_*.parquet`
- **metric-registry**：`server/src/config/metric-registry/categories/cost.ts` v1.0.0 起新增 `bi_case_ratio_pct` + `bi_amount_ratio_pct`

## 已知 v2.1 边界

- **未实现视图轴切换**：Card 2-13 默认"观察期发展"（行=维度值，列=观察期）；"年度对比"（行=维度值，列=年度）尚未做（PY 切换器已部分覆盖此需求）
- **未实现多级下钻**：子页副维度 Card 行不可再点击下钻（v2.1 只一层），v3 计划支持团队 → 业务员 → 客户的逐级深入
- **未实现跨维度对比**：该维度值 vs 同级中位数/最优值，v2.2 计划补
- **dim_salesman JOIN miss 兜底**：业务员若在 dim 表查不到，用 `REGEXP_REPLACE(salesman_name, '^[0-9]+', '')` 提取尾部中文；团队查不到归入 "（未知团队）" 行（数据质量观察：2025 年 365 天观察期下"（未知团队）"占 ~30%）

## 验证

| 校验项 | 期望 | 实测 (cutoff=2026-05-14) |
|---|---|---|
| 2022 年满 2 年完成度 | 1.000 | 1.000 ✓ |
| 2025 年满 2 年完成度 | 0.000 | 0.000 ✓ |
| 2024 年满 1 年满期赔付率 | ≈ 项目 mature_loss_ratio | 67.75% ✓ |
| 全样本 人伤金额占比 | 53.95%（直查 claims_detail） | 各年度满 1 年区间 52~57% ✓ |
| 双切换器（年度 × 指标） | 点击即时无刷新切换 cell + 保单数 | ✓（puppeteer 验证） |
| 团队 Card 行数 | 10 + 整体 = 11 | 11 ✓ |
| 业务员 Card 行数 | 15 + 整体 = 16 | 16 ✓ |
| 业务员名 | 全部纯中文（无工号前缀） | ✓（李珊 / 乔军 / 王文静 等） |
| 团队名 | 全部纯中文 | ✓（蒲江业务团队 等） |
| HTML 体积 | < 2 MB（gzipped < 400 KB） | 1.5 MB / gzipped 88 KB ✓ |

## 变更日志

- **v2.4.0** (2026-06-03) 第 6 指标「满期保费」+ 维度卡按保费规模排序：
  - **新增指标 `earned_premium_sum`（满期保费）**：它本就是聚合原料列（`SUM(premium × exposed/term)`），无需二次派生，直接登记进 `METRIC_DEFS`（排在案均赔款之后）即成第 6 个可切换指标，全局控制栏自动多出一个按钮、cell/趋势 data 属性与 JS 联动全量动态读取 `METRIC_DEFS` 自动带上。`render.py:_fmt_cell` 加 `wan` 格式 kind（折万元、保 1 位小数），避免大额绝对值撑宽 cell。规模视角与赔付率/出险率同表对照——先看盘子多大再判赔得好不好。
  - **维度卡行序：保单数排序 → 满期保费规模降序**：`render_dim_card` 与 `select_top_dim_values` 的排序键由 `policy_count` 改为 `earned_premium_sum`（同一最成熟可得锚点 DW），用原始保费值排序、不受 △/— 显示标记影响；首行「整体」基准行另行钉首位、不参与排序；整体三角（行=保单年度）天然豁免。让"保费大且赔付高"的重点盘自然上浮表首。
  - **范围**：仅 6 处小改（query.py METRIC_DEFS、render.py `_fmt_cell`/两处排序键/维度卡副标题、cli.py Card1 副标题指标清单），无 SQL 结构变更、无新增取数；旧报告原样重跑即生效。

- **v2.3.0** (2026-06-03) 切换器范式重构：每卡局部「双切换器」上提为**页面级 sticky 全局控制栏**（BI 仪表盘范式）：
  - **病灶**：12+ 维度卡 × 2 套切换器 = 24+ 套重复控件，吃垂直预算 + 视觉噪音；且每卡独立 active state，跨维度横扫时口径打架（A 卡切到「2026 出险率」、B 卡仍停在「2025 赔付率」）。
  - **方案**：`render_global_controls(py_options, current_py, active_metric)` 生成顶部 sticky 栏（年度 + 指标各一组按钮）；`render_dev_triangle` / `render_dim_card` 删除各自切换器，table 加 `data-triangle-kind`（`overall` 行=年度 / `dim` 行=维度值）作 JS 分流标记。
  - **JS 全局联动**：`METRIC_SWITCHER_JS` 由 per-table（`data-target`）重写为 `applyAll(py, mid)` 遍历所有 `table.dev-triangle`——指标驱动全部表（overall 读 `data-{mid}-*`、dim 读 `data-py{py}-{mid}-*`），年度仅驱动维度卡。数据早已全量嵌入 cell data 属性，全局联动纯前端、零取数。
  - **下钻子页同构收编**：`render_drill_page` 同样插全局栏（drill-overall 为 overall 型、副维度卡为 dim 型）。
  - **清理**：删除死 CSS（`.switchers-row` / `.py-switcher` / `.metric-switcher` / `.switcher-label`），`.btn-py` / `.btn-metric` 由全局栏复用。
  - **sticky 堆叠修复（避坑）**：shell 的 `.page-toolbar` 已是 `sticky top:0; z-index:50`（毛玻璃标题栏）。全局栏若也 `top:0` 会同位竞争被标题栏遮住、长报告滚下去就切不了。修法：全局栏 `top:44px`（≈标题栏高）+ `z-index:49`，贴标题栏正下方形成两级粘性堆叠，滚到任何位置都常驻可点。

- **v2.2.1** (2026-05-17) 企微推送自动化（多文件报告）：
  - **push_html.py 新增 `--external-url`**：传 https URL（必须 .html / .htm）跳过本地 stage_html，直接把链接写入企微智能表格「链接」列。配合 cli.py `--deploy` + sync-vps.mjs，整条链路无需手动粘贴 URL。
  - **互斥校验**：`--external-url` 与 positional `html_file` 互斥，传两个 → stderr + exit 2。
  - **URL 校验**：仅接受 http(s) scheme 且路径以 .html / .htm 结尾，空字符串和非法 scheme 立即拒绝（exit 2），避免被 falsy 短路绕过校验。
  - **标题派生**：默认 `title = URL 末段 stem`（preview-mvp.html → "preview-mvp"），可用 `--title` 显式覆盖中文名。
  - **专用 smartsheet**：daily-sync 用 `--meta state/_loss_dev_meta.json` + `--name "chexian-api · 多年保单赔付发展报告"` 让本报告独立成一张 smartsheet（首跑自动新建，之后追加），与共享报告推送表（`_html_push_meta.json`）解耦避免互相污染。

- **v2.2.0-deploy** (2026-05-17) 生产部署能力：
  - **cli.py 加 `--deploy` 模式**：自动输出到 `{project-root}/server/data/reports/diagnose-loss-development/{cutoff}/`，与现有 `node scripts/sync-vps.mjs` rsync 链路无缝集成。
  - **chexian-api 后端新路由 `GET /api/reports/:reportId/:snapshot/*`**（[PR #392](https://github.com/alongor666/chexian-api/pull/392)）：报告 ID 白名单 + snapshot YYYY-MM-DD 校验 + 子路径 traversal 防护 + 沿用 authMiddleware + CSP。
  - **生产 URL**：`https://chexian.cretvalu.com/api/reports/diagnose-loss-development/{cutoff}/preview-mvp.html`（管理员登录后访问，凭据见项目侧密钥管理）
  - **/daily-sync skill 加 Step 3.5**：ETL 完成后可选生成 + 部署报告，纳入每日数据流闭环。
  - **企微推送**：v2.2.1 已扩展 push_html.py `--external-url`，多文件报告主页自动推送到企微智能表格。

- **v2.1.0** (2026-05-17) 下钻页全维度归因分析：每个下钻子页从"1 张总体三角形"扩展到"1 总体 + 11 副维度 Card"，覆盖该维度值沿其他 11 个维度的完整内部分布。点宜宾二部进子页，立即看到团队内**客户类别 / 业务员 / 险类 / 险别组合 / 是否新能源 / 是否过户 / ...** 全维度拆分，3 秒锁定赔付率黑洞（如：摩托车 147% / 非营业个人客车 118%）。
  - **SQL 架构升级（教训记录）**：原计划单 SQL 加 55 个二维 GROUPING SETS，DuckDB hash aggregate 累计内存爆炸 OOM（即便排除高 cardinality 的 salesman_chinese）。架构改为**二段式**：
    1. 主 SQL 物化 `agg_input` 到 DuckDB TEMP TABLE（policy_no × 6 DW × 12 dim 原料行）
    2. 主页跑一维 GROUPING SETS（13 组，与 v1.1 一致）
    3. 每个下钻子页跑一次 `build_subdim_batch_sql(parent_dim, parent_value, child_dims)`，UNION ALL 输出 11 个子查询，全部基于已物化的 TEMP TABLE（无重复 parquet 扫描）
  - **生成规模**（cutoff=2026-05-14）：主页 1.9 MB + 75 子页 / 98 MB（每子页 ~1.2 MB / 12 Card）；总生成时间 ~2 分钟
  - **业务员维度兜底**：业务员副维度卡现在能正确显示（用 TEMP TABLE 内 batch query 而非主 SQL 二维交叉，避免 cardinality 爆炸）
  - **新公共 API**：`build_agg_input_materialized_sql` / `build_main_grouping_sql` / `build_subdim_batch_sql` / `query_subdim_data`
  - **多级下钻 / 跨维度对比**：推到 v3+

- **v2.0.0** (2026-05-17) 下钻子页 MVP：主表非整体行的维度值 dim_cell 变成可点击的下钻链接，跳转到独立 HTML 子页。子页只展该维度值的 5 PY × 6 DW × 5 指标完整三角形（含 sparkline 趋势 + 指标切换 + 返回主页链接），让用户专注看单一维度值的"5 年成熟轨迹"，不被同级竞争分散注意力。**0 新增 SQL**——子页数据复用主表 `derived` 过滤。
  - **文件布局**：`examples/drill/{dim_key}/{md5(dim_value)[:8]}.html`
  - **生成规模**（cutoff=2026-05-14）：75 个子页 / 5.1 MB（12 维度 × 各自 top_n 维度值）
  - **副维度切片 / 跨维度对比 / 多级下钻**：推到 v2.1+
  - **新公共 API**：`drill_slug(value)` / `select_top_dim_values(derived, cfg, current_py)` / `render_drill_page(...)`

- **v1.1.0** (2026-05-16) UX 升级 + 两项口径修复 + 趋势 sparkline：13 卡（Card 1 整体三角形 + Card 2-13 十二维度）。
  - **🎯 趋势列**：每张表最右加 96×28 mini sparkline，借鉴 diagnose-period-trend 表 1 精髓。6 期数据点 polyline + circles，末值圆点放大（r=2.4 vs 1.4），全曲线颜色 = 满 1 年（365 天）亮灯色（绿/蓝/黄/红/灰），跨行可视化对比"赔付率成熟轨迹"。切保单年度/切指标时 JS 端 `drawSparkline()` 即时重绘。
  - **维度**：新增团队（top 10，借鉴 dhr_lib `short_team_name` 显示简称：蒲江业务团队→蒲江）/ 险类 / 是否新车 / 是否电销，删除终端来源；业务员 top 20 → 15。
  - **双切换器**：Card 2-13 每张表加保单年度切换器，默认 2025 年；与指标切换器并列、视觉对比强烈（已选纸白底 + 1px 边框 + 加粗）。
  - **数据增强**：LEFT JOIN dim_salesman 派生纯中文 `salesman_chinese` + 中文 `team`。
  - **UI 中文化**：表头 `30d/90d/...` → `30 天/.../满 1 年/满 2 年`；行标签去 "PY" 后缀；删全部 "Card N" kicker；meta/footer 全中文。
  - **🔴 满期出险率年化修复**：分子从 `incident_flag`（出险保单数）改为 `claim_cases × term_days / exposed_days`（年化赔案件数），与 metric-registry `earned_loss_frequency` v2.1.0 一致。修复前 30 天 DW 显示 1.24%（实际是 30 天累计密度），修复后 15.6%（年化到 1 年）。曲线呈现精算上正确的"早期高估→收敛稳态"形态，跨 DW 可比。
  - **🔴 满期赔付率 partial cell 修复**：分母 `earned_premium` 从 `premium × LEAST(dw_days, term_days) / term_days` 改为 `premium × exposed_days / term_days`（即 `LEAST(dw, term, cutoff−start) / term`）。修复前 2025 PY 365d 显示 55.6%（compl=41%，分母按完整 365 天算虚高），修复后 67.7%（与 2024 PY 同口径稳态吻合）。
  - **🔴 根因**：v1.0 默认"保单完整观察 DW 天"，把"名义 DW"与"真实暴露 `exposed_days`"等价。任何分子受 cutoff 约束 + 分母用名义 DW 的公式都会在 partial cell 错位。
  - **修复**：table 自身 id 与容器 div id 冲突（同名导致 getElementById 永远返回 div），改 table id 为 `card-{key}-table`。

- **v1.0.0** (2026-05-16) MVP 上线：10 卡片（Card 1 整体三角形 + Card 2-10 九维度），5 指标切换，截尾标记 (`✓/△/—`)，整体基准行。同 PR 注册 metric-registry 新指标 `bi_case_ratio_pct` + `bi_amount_ratio_pct`。
