# 信息搜索协议

## 信息源优先级

| 层级 | 来源 | 用途 |
|------|------|------|
| **一手源（必查）** | 年报/半年报/季报、业绩说明会纪要、招股说明书、行业监管机构 | 财务数据、管理层口径、竞争格局 |
| **高价值二手源** | 券商首次覆盖报告(Initiation)、国际机构报告(IEA/CME/J.P. Morgan/McKinsey/Gartner)、行业数据库(Wood Mackenzie/Frost & Sullivan/IDC/TrendForce) | 行业全景、全球视角、出货量/市占率 |
| **辅助验证源** | 财经媒体(证券时报/财新/Reuters/Bloomberg)、行业垂直媒体(SMM/OFweek/MINING.COM/C114)、公司官网 | 事件触发、细分领域深度 |

## 搜索轮次（5+1）

默认中英文双语搜索。每个维度至少搜一轮中文+一轮英文，确保信息交叉验证。
用户指定语言时从其指令（如"纯英文资料"则只搜英文）。

| 轮次 | 覆盖维度 | 搜索关键词模式 |
|------|---------|---------------|
| 1 | 创始人/历史 | {公司名} 创始人 发展历史 / {Company} founder history |
| 2 | 最新业绩 | {公司名} {年份} 业绩 营收 净利润 / {Company} {year} revenue earnings |
| 3 | 竞争格局 | {公司名} 竞争格局 市场份额 / {Company} market share competition landscape |
| 4 | 技术路线/风险 | {公司名} 技术路线 风险 / {Company} technology roadmap risk |
| 5 | 海外/政策 | {公司名} 海外市场 政策 / {Company} overseas market policy tariff |
| **R** | **逆向搜索（必做）** | {公司名} 风险 失败 争议 做空 / {Company} risk failure controversy short |

## 三角验证规则

- 任何关键判断至少需要 **2个独立来源** 交叉确认
- 中文看国内视角+政策信号，英文看全球格局+国际投资者态度
- 区分事实与观点：年报数据是事实，券商目标价是观点，不可混同
- 信息不足时：明确标注「信息不足」，不编造

## 非A股补充数据源

| 市场 | 数据源 |
|------|--------|
| 美股 | SEC EDGAR (10-K/10-Q/20-F)、Yahoo Finance、FinanceToolkit (FMP API) |
| 港股 | HKEX 披露易、Wind/Choice |
| 其他 | 公司IR页面、当地交易所公告 |

对于中概股（ADR/港股），同时检查 SEC 和 HKEX/巨潮的披露。
