---
name: diagnose-loss-development
description: >-
  车险经营 · 多年保单赔付发展三角形（保单年度 2022~ × 观察期 30/90/180/270 天 + 满 1/2 年 × 5 指标 × 12 维度）。
  生成交互式单页 HTML 报告，双切换器（保单年度 × 指标），5 指标含满期赔付率/出险率/案均/人伤案占比/人伤金额占比，
  12 维度含客户类别/三级机构/团队/业务员/风险等级/险类/险别组合/是否新能源/是否新车/是否过户/是否续保/是否电销。
  含完成度截尾标记（✓/△/—）与四级亮灯。
  当用户说 "保单赔付发展"、"发展三角形"、"满 1 年/2 年赔付率"、"多年保单赔付对比"、
  "人伤案件 vs 人伤金额"、"赔付率成熟曲线" 时使用。
user_invocable: true
version: "2.2.1"
---

# diagnose-loss-development: 多年保单赔付发展三角形

把 5 个保单年度（2022~2026）× 6 个观察期锚点（30/90/180/270 天 + 满 1 年 / 满 2 年）的"赔付率成熟曲线"渲染成交互式单页 HTML。诊断核心：**频率（出险率）vs 严重性（案均、人伤金额占比）vs 综合（赔付率）三视角同表对比**。

## 设计意图

- **金标三角形**：精算最经典口径，看保单年度在不同观察期的赔付收敛轨迹
- **双切换器**：保单年度 × 指标（v1.1）——Card 2-13 每张卡同时支持切年度和切指标，无刷新即时联动 cell + 保单数
- **截尾标记**：`✓ 完整观察 / △ 部分（< 95% 保单完成）/ — 未到`，避免老年度/新年度不可比
- **人伤双指标**：案占比（频率）+ 金额占比（严重性）配对呈现"频率轻、金额重 5 倍"的人伤特性
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

## 5 个核心指标

| ID | 中文 | 公式 | 单位 | 亮灯阈值 |
|---|---|---|---|---|
| `mature_loss_ratio`    | 满期赔付率   | (已决+未决) ÷ 满期保费 | % | `earned_loss_ratio_pct`：≤60 优 / 70 健 / 75 异 / >75 险 |
| `mature_incident_rate` | 满期出险率   | **SUM(赔案件数 × 保单期 / 暴露天数) ÷ 保单数**（年化口径，与 metric-registry `earned_loss_frequency` v2.1.0 一致；未满期 cell 按 `term_days/exposed_days` 放大到等价 1 年） | % | `earned_loss_freq_pct`：≤8 优 / 10 健 / 12 异 / >12 险 |
| `avg_claim_amount`     | 案均赔款     | 总赔款 ÷ 赔案件数      | 元 | 不打灯 |
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

Card 2-13 默认显示 **2025 年**切片（用户重点关注），可通过表头上方的"保单年度"切换器即时切到 2022/2023/2024/2026 任一年，cell 内容和保单数列同步联动。未观察完整的 cell 标 △ 并附浅灰斜纹底。

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
- 鉴权：沿用 `authMiddleware`（admin/CxAdmin@2026!）
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
├── lib/
│   ├── __init__.py
│   ├── cli.py              ← 编排：argparse + run() + render_html() + main()
│   ├── query.py            ← SQL 构造（CTE + GROUPING SETS）+ derive_metrics()
│   └── render.py           ← render_dev_triangle() + render_dim_card() + 5 指标 JS
└── examples/
    └── preview-mvp.html    ← cutoff=2026-05-14 的固化样例
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

- **v2.2.1** (2026-05-17) 企微推送自动化（多文件报告）：
  - **push_html.py 新增 `--external-url`**：传 https URL（必须 .html / .htm）跳过本地 stage_html，直接把链接写入企微智能表格「链接」列。配合 cli.py `--deploy` + sync-vps.mjs，整条链路无需手动粘贴 URL。
  - **互斥校验**：`--external-url` 与 positional `html_file` 互斥，传两个 → stderr + exit 2。
  - **URL 校验**：仅接受 http(s) scheme 且路径以 .html / .htm 结尾，空字符串和非法 scheme 立即拒绝（exit 2），避免被 falsy 短路绕过校验。
  - **标题派生**：默认 `title = URL 末段 stem`（preview-mvp.html → "preview-mvp"），可用 `--title` 显式覆盖中文名。
  - **专用 smartsheet**：daily-sync 用 `--meta state/_loss_dev_meta.json` + `--name "chexian-api · 多年保单赔付发展报告"` 让本报告独立成一张 smartsheet（首跑自动新建，之后追加），与共享报告推送表（`_html_push_meta.json`）解耦避免互相污染。

- **v2.2.0-deploy** (2026-05-17) 生产部署能力：
  - **cli.py 加 `--deploy` 模式**：自动输出到 `{project-root}/server/data/reports/diagnose-loss-development/{cutoff}/`，与现有 `node scripts/sync-vps.mjs` rsync 链路无缝集成。
  - **chexian-api 后端新路由 `GET /api/reports/:reportId/:snapshot/*`**（[PR #392](https://github.com/alongor666/chexian-api/pull/392)）：报告 ID 白名单 + snapshot YYYY-MM-DD 校验 + 子路径 traversal 防护 + 沿用 authMiddleware + CSP。
  - **生产 URL**：`https://chexian.cretvalu.com/api/reports/diagnose-loss-development/{cutoff}/preview-mvp.html`（admin/CxAdmin@2026! 登录后访问）
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
