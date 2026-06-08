# diagnose-org-weekly · 三级机构经营诊断周报

车险产险**三级机构**（天府 / 高新 / 宜宾 等 12 个）的周度经营诊断报告，一键产出单文件交互式 HTML（SPA，含 10 个经营板块 + 22 个同窗下钻子页）。

> 完整口径、参数、改造历史见 [`SKILL.md`](./SKILL.md)。本 README 只讲「怎么快速跑起来」「依赖什么」「产出什么」。

## 快速上手

```bash
# 三级机构层（默认）
python3 ~/.claude/skills/diagnose-org-weekly/cli.py --org 天府 --year 2026

# 分公司层（聚合全部三级机构 + 团队 Top20 + 三级机构维度双向下钻）
python3 ~/.claude/skills/diagnose-org-weekly/cli.py --level branch --org 四川分公司 --year 2026
```

常用参数（全集见 SKILL.md）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--org` | 必填 | 机构名（12 个：天府/高新/新都/青羊/武侯/乐山/宜宾/德阳/泸州/自贡/资阳/达州） |
| `--level` | `org` | `org` 三级机构层 / `branch` 分公司层 |
| `--view` | `all` | `all` 产 V1 驾驶舱 + V3 叙事 + V4 超表 + 合集壳页；也可 `v1`/`v3`/`v4`/`legacy` |
| `--cutoff` | 自动 | 数据截止日（默认 DuckDB 取最大起保日期） |
| `--output` | `/tmp` | 输出目录 |

## 依赖

| 依赖 | 性质 | 说明 |
|---|---|---|
| **chexian-report-shell** | 运行时必需（见 frontmatter `requires_skills`） | 渲染层：`render_page` / 四级亮灯 / SPA 拼装 / 多维多窗 DuckDB 查询 / 飞书企微推送薄壳。`cli.py` 启动时按 ADR-001 策略定位其 `lib/` 并注入 `sys.path` |
| **数据湖 parquet** | 运行时必需 | `chexian-api/数据管理/warehouse/{policy,claim,plan,renewal_tracker}/current/*.parquet`，DuckDB 直查、无需起服务 |
| 指标公式 / 阈值 | 仅读取 | 在 `chexian-api/数据管理/diagnose_common.py`，本技能只调用不改 |

> 本技能是「渲染层 + 诊断业务」薄分离架构的**业务侧**；渲染与亮灯能力全部下沉到基座 chexian-report-shell，本技能只写本场景的业务逻辑。

## 产物

`--view all` 在输出目录产出 4 个文件（以 `--org 天府 --year 2026` 为例）：

```
天府_2026_cockpit.html     ← V1 驾驶舱：9 项 KPI × 5 时间窗 + Top 异常卡
天府_2026_narrative.html   ← V3 叙事周报：A4 打印风，4 章节 + 附录表
天府_2026_table.html       ← V4 超表：分析师交互表（列冻结 + 搜索 + 排序 + 展开行）
天府_2026_合集.html         ← 合集壳页：顶部 Tab 切换，3 个常驻 iframe 懒加载（切换不重载）
```

每个报告为**自包含单文件**：10 板块主页 + 22 个 hidden 下钻子页（主页表格行 `onclick=showPage(id)` 同窗切换，子页顶部「← 返回主报告」）。
