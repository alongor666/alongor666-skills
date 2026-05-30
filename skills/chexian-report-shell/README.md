# chexian-report-shell

车险诊断报告渲染基础设施层（共享库），**非用户直接调用 skill**。

> 2026-05-17 重命名：原 `diagnose-html-render` → `chexian-report-shell`，业务工具 `examples/org_weekly.py` + `examples/sections/*` 独立为 `diagnose-org-weekly` skill。

## 当前职责（v1.19）

只做"共享渲染基础设施"，不再混装业务工具：

```
lib/
├── render.py        render_page / render_table / render_card / render_weekly_table
│                    四级亮灯 / 双主题 / SPA 拼装 / drill-toc CSS+JS
├── alerts.py        TH 四级阈值（镜像 chexian-api/数据管理/diagnose_common.py）
├── format.py        fmt_num / fmt_pct / fmt_wan / 简称转换
├── labels.py        SHORT_LABEL / FULL_LABEL 单一事实源
├── queries.py       standard_query / build_base_cte / DuckDB UDF
├── report_queries.py 项目专用 fetch_* 函数
├── dimensions.py    9 维下钻元数据 + ValueDef 注册表
├── grouping_sets.py multi_dim_periods_query 多维多窗
├── drill_body.py    下钻 body 生成器（v1.19 新增）
├── page_ids.py      drill_page_id md5（v1.19 新增）
├── context.py       SectionContext dataclass
├── contract.py      validate_metrics_df / 阈值同步断言
└── push.py          飞书 / 企微推送
```

## 上下游

```
[ 业务诊断 skill ]                          [ 渲染层 ]
diagnose-org-weekly         ─┐
diagnose-period-trend       ─┼─→ chexian-report-shell ─→ chexian-im-push ─→ chexian-api/push_html.py
diagnose-loss-development   ─┘     (本 skill)             (IM 推送薄壳)    (智能表格 + reports/ 托管)
```

每层都是薄壳，互不耦合。

## 如何被业务诊断 skill 集成

详见 `SKILL.md` 的「如何被业务诊断 skill 集成」段。最小骨架：

```python
import sys
from pathlib import Path
SHELL_ROOT = Path.home() / ".claude" / "skills" / "chexian-report-shell"
sys.path.insert(0, str(SHELL_ROOT))
from lib import render_page, render_table, standard_query  # ... etc
```

参考实现：
- 全功能范本：`~/.claude/skills/diagnose-org-weekly/cli.py` + `sections/*`
- 薄壳范本：`~/.claude/skills/diagnose-period-trend/lib/cli.py`

## 不要做的事

- ❌ 不要在 lib/ 里写业务诊断逻辑（如"机构周报"特定的板块组合）
- ❌ 不要在本 skill 加 user_invocable=true 触发词（直接用业务诊断 skill 即可）
- ❌ 不要硬编码任何特定机构 / 时间窗 / 维度组合
