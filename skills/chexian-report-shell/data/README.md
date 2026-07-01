# SX（山西）年计划数据

`sx_plan_2026.parquet` — 山西分公司 10 个纯三级机构的 2026 年车险年计划。

被 `chexian-report-shell/lib/report_queries.py` 的 `plan_parquet_for_branch("SX")` 读取。
`diagnose-org-weekly` 的 SX 分公司报告据此算计划达成率。限制与补缺见
`diagnose-org-weekly/SKILL.md`「已知限制与后续补缺」段。

## 数据源

山西分公司经营快报分机构表（2026 年）的「保费任务」列（用户 2026-07-01 提供）。

## schema

| 列 | 类型 | 说明 |
|---|---|---|
| plan_year | BIGINT | 2026 |
| level | VARCHAR | `'organization'`（机构层；无 salesman 拆分） |
| organization | VARCHAR | 三级机构名（与 `policy.org_level_3` 一致，白名单靠它匹配） |
| plan_vehicle | DOUBLE | 车险年计划，单位**万元** |
| plan_personal | DOUBLE | NULL（驾意险计划待补） |

## 机构映射（考核机构名 → policy.org_level_3）

| org_level_3 | 经营快报考核名 | plan_vehicle（万）|
|---|---|---|
| 太原一部 | 太原业务一部 | 2960 |
| 太原二部 | 太原业务二部 | 3750 |
| 大同 | 大同 | 2610 |
| 阳泉 | 阳泉 | 1300 |
| 长治 | 长治 | 1970 |
| 晋城 | 晋城 | 1500 |
| 晋中 | 晋中 | 3000 |
| 运城 | 运城 | 2050 |
| 临汾 | 临汾 | 2100 |
| 吕梁 | 吕梁 | 2000 |
| **合计** | | **23240** |

⚠️ 太原一部/二部与考核表"太原业务一部/二部"保费量级有差异（policy 352/1628 vs 考核
928/1058，截至 5-31），是两套统计口径的切分差异，机构实体已确认对应（用户 2026-07-01
确认），直接按名映射。

## 未统计（待补）

渠道类（车商 / 经代 / 金融同业 / 重客）+「其他」——因与三级机构重复计算、规则复杂，
暂不统计。补缺需先理清重复计算规则。影响：分公司整体计划达成率偏高约 10-15%（渠道
实际保费计入分子、不进分母）。

## 每年更新

每年初用新年计划重建本文件。生成命令（duckdb）：

```python
import duckdb
con = duckdb.connect()
con.execute("CREATE TABLE sx_plan(plan_year BIGINT, level VARCHAR, organization VARCHAR, plan_vehicle DOUBLE, plan_personal DOUBLE)")
con.executemany("INSERT INTO sx_plan VALUES (?,?,?,?,?)", [
    (2027, 'organization', '太原一部', <新值>, None),
    # ... 10 个机构
])
con.execute("COPY sx_plan TO 'sx_plan_2027.parquet' (FORMAT PARQUET)")
```

文件名按年份：`sx_plan_<year>.parquet`。换年份后同步改 `lib/report_queries.py` 的
`SX_PLAN_PARQUET` 常量（指向新文件）。

## 口径校验

SX 起保口径 YTD 保费 ≈ 经营快报累计保费（差应 <0.5%）。例：2026-05-31 起保口径 8961 万
vs 快报 8997 万。差异大说明口径漂移，需核查。
