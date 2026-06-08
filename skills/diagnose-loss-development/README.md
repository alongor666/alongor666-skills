# diagnose-loss-development · 多年保单赔付发展三角形

把 5 个**保单年度**（2022~2026）× 6 个**观察期锚点**（30 / 90 / 180 / 270 天 + 满 1 年 / 满 2 年）的「赔付率成熟曲线」，渲染成交互式单页 HTML。诊断核心：**频率（出险率）× 严重性（案均、人伤金额占比）× 综合（赔付率）三视角同表对比**。

> 术语：保单年度 = 按起保日期划归的年份；观察期（观察天数）= 保单成立后经过的天数，用来看赔付随时间收敛的轨迹。
> 完整数据口径（真实暴露天数三道闸、赔款口径、完成度截尾等）、6 指标公式、12 维度、部署流程见 [`SKILL.md`](./SKILL.md)。

## 快速上手

```bash
# 生成完整 HTML（13 张卡：整体三角 + 12 维度卡）
python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
  --cutoff 2026-05-14 \
  --project-root '/path/to/chexian-api' \
  --out '/path/to/chexian-api/public/reports/diagnose-loss-development/2026-05-14.html'

# 仅控制台验证（不写文件，只跑整体三角 Card 1）
python3 ~/.claude/skills/diagnose-loss-development/lib/cli.py \
  --cutoff 2026-05-14 --project-root '/path/to/chexian-api'
```

常用参数（全集见 SKILL.md）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--cutoff` | 必填 | 数据截止日（观察时点）；约束所有观察期的真实暴露天数 |
| `--project-root` | — | 数据湖项目根，解析 `policy/current/*.parquet` |
| `--out` | 无 | 完整输出路径（不给则仅控制台验证） |
| `--deploy` | 关 | 产出后落到 `public/reports/...`，配合 VPS 同步 + 企微推送链路 |

## 依赖

| 依赖 | 性质 | 说明 |
|---|---|---|
| **chexian-report-shell** | 运行时必需（见 frontmatter `requires_skills`） | 渲染基础设施：四级亮灯 / 格式化 / SPA 拼装。`lib/_shell.py` 按 ADR-001 策略定位基座并注入 `sys.path`，随后 `from lib import ...` |
| **数据湖 parquet** | 运行时必需 | `policy/current/*.parquet`，DuckDB 直查 |

## 产物

单文件交互式 HTML，结构：

```
Card 1        整体赔付发展三角（保单年度成行 × 观察期成列）
Card 2-13     12 个维度卡（客户类别 / 三级机构 / 团队 / 业务员 / 风险等级 /
              险类 / 险别组合 / 是否新能源 / 是否新车 / 是否过户 / 是否续保 / 是否电销）
```

交互特性：
- **顶部 sticky 全局控制栏**（保单年度 × 指标），一处切换即时联动整体三角 + 全部维度卡；数据全量嵌入单元格属性，切换纯前端、零取数。
- **完成度截尾标记**：`✓ 完整观察 / △ 部分（不足 95% 保单完成）/ — 未到`，避免新老年度不可比。
- **保费规模排序**：维度卡内各行按当年满期保费降序，「赔得多且保费大」的重点盘自然上浮；「整体」基准行恒钉首位。

生产 URL（部署后，需 admin 登录）：`https://chexian.cretvalu.com/api/reports/diagnose-loss-development/{cutoff}/preview-mvp.html`
