---
name: diagnose-org-weekly
description: >-
  车险三级机构经营诊断周报 — 一键单文件 SPA HTML 报告。10 板块（经营指标概况
  + 分客户类型 + 分销售团队 + Top 业务员 + 险类 / 险别组合 / 能源 / 新旧车 /
  过户 / 续保）+ 22 个同窗口下钻子页（showPage 切换 + 内置 drill-toc）。
  当用户说"机构周报"、"X 经营诊断周报"、"跑一份 X 周报"、"三级机构周度盯盘"、
  "天府/高新/宜宾经营诊断"、"组织绩效周报"时触发。
user_invocable: true
version: "1.20.0"
---

# diagnose-org-weekly: 三级机构经营诊断周报

车险产险三级机构（天府 / 高新 / 宜宾 等 12 个）的周度经营诊断 HTML 报告。

## 一键命令

```bash
python3 ~/.claude/skills/diagnose-org-weekly/cli.py --org "<机构名>" --year 2026
```

可选参数：
- `--level org|branch` — **层级**（默认 `org` 三级机构层）。`branch` = 分公司层：聚合全部三级机构、
  团队维度→Top20 团队（按签单保费 YTD）、业务员维度→三级机构维度，三级机构 × 全部业务维双向下钻。
  branch 时 `--org` 为展示名（默认「分公司」，不进 SQL 过滤）。
- `--view legacy|v1|v3|v4|all` — 渲染模式（默认 `all`）。`all` 产出 V1 驾驶舱 + V3 叙事 + V4 超表三文件，
  **并额外产出带 Tab 切换的合集壳页** `<org>_<year>_合集.html`（3 个常驻 iframe 懒加载，切换不重载不重新鉴权）。
- `--cutoff 2026-MM-DD` — 显式指定数据截止日（默认 DuckDB 自动取 `MAX(insurance_start_date)`）
- `--output <目录>` — 输出目录（默认 `/tmp`）
- `--time-field policy_date` — 切换签单口径（默认 `insurance_start_date` 起保口径）

分公司层一键命令：
```bash
python3 ~/.claude/skills/diagnose-org-weekly/cli.py --level branch --org 四川分公司 --year 2026
```

适用机构（12 个）：天府 · 高新 · 新都 · 青羊 · 武侯 · 乐山 · 宜宾 · 德阳 · 泸州 · 自贡 · 资阳 · 达州

## 报告结构（10 板块 + 22 SPA 下钻）

**主页 TOC（顺序固定）**：
1. **经营指标概况** — 9 项核心 KPI × 5 时间窗（当周/上周/上上周/上月/上季度，均 YTD 累计） + sparkline
2. **分客户类型** — 11 类客户，每行可下钻
3. **分销售团队** — team 派生自 plan.parquet salesman→team 映射（Phase 6 增下钻）
4. **TOP 业务员** — 综合排序（Phase 6 增下钻）
5. **险类**（交强险 / 商业保险）
6. **险别组合**（单交 / 交三 / 主全）
7. **能源**（新能源 / 燃油）
8. **新旧车**（新车 / 旧车）
9. **过户**（过户 / 非过户）
10. **续保**（续保 / 非续保）

**下钻子页（22 个 hidden section）**：
- DOM id 形如 `drill-<2字符前缀>-<6位md5前缀>`
- 内容：9 KPI × 5 时间窗 + 客户类别拆解 + 5 个兄弟业务属性横切
- 跳转：主页表格行 onclick=showPage(id) **同窗口切换**，子页顶部"← 返回主报告"

## 依赖

本 skill 是「渲染层 + 诊断业务」薄分离架构的"业务侧"：
- **渲染层**：`~/.claude/skills/chexian-report-shell/lib/*`（render_page / 亮灯 / SPA 拼装 /
  下钻元数据 / 多维多窗查询 / 飞书企微推送）
- **数据源**：`chexian-api/数据管理/warehouse/{policy,claim,plan,renewal_tracker}/current/*.parquet`
- **DuckDB 直查**：无需起服务，cli.py 自带 connection

## 触发场景

当用户问下列任一时，**禁止**重新搜索 skill 位置或重写命令——直接用本 skill 命令模板：

| 用户原话 | 操作 |
|---------|------|
| "跑一份天府周报" / "更新天府报告" | `cli.py --org 天府 --year 2026` |
| "宜宾经营诊断" / "宜宾经营怎么样" | `cli.py --org 宜宾 --year 2026` |
| "组织绩效周报" / "机构周度盯盘" | 提示用户指定具体机构名 |
| "X 机构（任一）出险率/费用率为啥高" | 先跑本 skill 看全图，再用 `chexian-ir-diagnosis` 钻特定指标（前身 auto-ir-diagnosis） |

## 改造历史

- **v1.19 (2026-05-17)**：单文件 SPA + 每维一卡（10 板块）+ 22 下钻；同日从 `diagnose-html-render/examples/org_weekly.py` 独立成本 skill
- **v1.18 (2026-05-17)**：多文件目录方案（已废弃，详见 v1.19 changelog）
- **v1.17 之前**：作为 `diagnose-html-render/examples/` 下的演示脚本演进

## 改造历史（续）

- **v1.20 (2026-05-29)**：① `--level branch` 分公司层（聚合全部三级机构 + 团队 Top20 + 三级机构维度
  双向下钻），渲染层 section/下钻 level-aware；② `--view all` 额外产出合集壳页（顶部 Tab + 懒加载 iframe）；
  ③ 新增 `org_level_3` 下钻维度（chexian-report-shell/lib：`_org_pred` 参数化 org 过滤 + dimensions 注册）；
  ④ `fetch_org_team_cross_data`：Top20 团队 × 全部业务维 + 三级机构交叉下钻（JOIN plan 派生团队，
  跨机构按 short_team_name 同名合并，仅算 Top20）。
  验证：分公司合计 247,089 张与 DuckDB 直查一致、Top20 团队=20、三级机构=14、cohort 求和自洽、
  团队 DD 键 160=20×8、三级机构层无回归（114 DD 键不变）。

## 不在本 skill 范围

- ❌ 指标公式 / 阈值 — 在 chexian-api 的 `数据管理/diagnose_common.py`，本 skill 只调用不改
- ❌ ETL / parquet 写入 — 本 skill 仅消费 parquet
- ❌ 飞书 / 企微推送 — 调用 chexian-report-shell 的 `push.py`，未来由 `chexian-im-push` 接管
