# diagnose-period-trend · 车险经营短中长期对照（三视图）

把「年初至今 / 上年同期 / 滚动 6·12·24·36 月」共 6 个时间窗 × 5 核心指标的整体 + 分客户类别 + 三级机构 + 7 辅助维度画像，渲染成三种 HTML 报告：**V1 驾驶舱 / V3 叙事周报 / V4 超表**。

> 完整数据口径（满期赔付率/出险率/自主系数等公式）、参数全集、QC 自检见 [`SKILL.md`](./SKILL.md)。本 README 只讲快速上手、依赖、产物。

## 快速上手

```bash
# 一次产出全部三视图
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --view all

# 单独某一视图（指定数据截止日）
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view v1   # 驾驶舱
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view v3   # 叙事周报
python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --cutoff 2026-05-26 --view v4   # 超表

# 指定数据湖项目根
CHEXIAN_PROJECT_ROOT=/path/to/chexian-api python3 ~/.claude/skills/diagnose-period-trend/lib/cli.py --view all
```

常用参数（全集见 SKILL.md）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--view` | `legacy` | `all` 产三视图 / `v1` 驾驶舱 / `v3` 叙事 / `v4` 超表 / `legacy` 旧版多期交互表 |
| `--cutoff` | 自动 | 数据截止日（默认 DuckDB 取最大起保日期），所有时间窗的锚点 |
| `--project-root` | `$CHEXIAN_PROJECT_ROOT` 或当前目录 | 解析 `policy/current/*.parquet` 路径 |
| `--output-dir` | `<项目根>/public/reports/diagnose-period-trend/` | 输出目录 |
| `--push-im` | 关 | 跑完是否推飞书 / 企微（配合 `--feishu-doc` / `--wecom-chat`） |

## 依赖

| 依赖 | 性质 | 说明 |
|---|---|---|
| **chexian-report-shell** | 运行时必需（见 frontmatter `requires_skills`） | 渲染基础设施：亮灯 / 格式化 / SVG 折线散点图 / 超表组件。`lib/_dhr_bootstrap.py` 按 ADR-001 策略定位基座 `lib/`，经 `importlib` 动态加载为 `dhr_lib` 模块（避免 `sys.path` 污染） |
| **数据湖 parquet** | 运行时必需 | `policy/current/*.parquet`，DuckDB 直查 |

> 「薄壳依赖」：渲染层下沉到基座，本技能只负责本场景业务逻辑；跨项目（私董会 / 作战地图 / chexian-api）共用同一套口径。

## 产物

| 视图 | 文件名 | 适用场景 |
|---|---|---|
| V1 驾驶舱 | `<cutoff>-dashboard.html` | 管理层周会开屏：KPI 卡 + Top 8 异常信号 |
| V3 叙事周报 | `<cutoff>-weekly.html` | A4 打印 / PDF 发送：4 章节叙事 + 附录表 |
| V4 超表 | `<cutoff>-table.html` | 分析师自助：多维交互过滤 + 列指标切换 |
| 旧版 | `<cutoff>.html` | `legacy` 模式：7 窗 × 7 指标交互表 |

默认输出到 `<项目根>/public/reports/diagnose-period-trend/`，作为车险看板首页「开屏第一眼」入口报告。三视图共用主题资源（已下沉基座 `dhr_lib.themes_v2`，支持明 / 暗双主题）。
