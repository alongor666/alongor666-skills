---
name: company-vortex
description: >
  Use when analyzing a publicly listed company through structural dynamics / vortex model —
  producing a full lifecycle diagnosis report. Trigger: "分析XX公司", "涡旋分析", "结构诊断",
  "company-vortex", stock codes, or any request for a 结构诊断.md report. Also when user pastes
  a stock ticker (A-share/HK/US) and wants a lifecycle structural teardown (listed company
  structural diagnosis).
version: 1.3.0
user_invocable: true
---

# Company Vortex: 上市公司涡旋结构诊断

## Overview

把一家上市公司当作"在压力下由向心力与离心力动态平衡形成的涡漩体"，做全生命周期结构演变诊断，产出 `结构诊断.md` 报告，并可衍生飞书有声长文与双人/单人播客音频。分析口径采用李继刚「商业结构」三才框架（天/人/地）。每次从执行步骤开始，不输出角色描述。

## When to Use

- ✅ 上市公司（A股/港股/美股）的结构演变诊断、全生命周期拆解、涡旋分析、结构诊断报告
- ❌ 非上市公司、纯财务估值/DCF、单纯财报解读——本框架不适用，请勿套用

## Quick Reference

| 项 | 值 |
|----|----|
| **WORKDIR**（工作目录） | 默认 `/Users/alongor666/Desktop/上市公司研究`，下文统一引用 `$WORKDIR` |
| 框架 | `references/vortex-framework.md`（三才/涡旋概念） |
| 搜索协议 | `references/search-protocol.md`（信息源/5+1 轮/三角验证） |
| 报告骨架 | `references/output-template.md`（必选/可选 + 四维★评分） |
| 有声长文 Prompt | `references/lark-longform-prompt.md` |
| 播客文稿 Prompt | `references/podcast-script-prompt.md`（含单人模式） |
| 飞书发布命令 | `references/lark-publish-protocol.md`（含 lark-cli 环境前缀） |

> **工作目录约定**：脚本与产出文件均位于 `$WORKDIR`。**`$WORKDIR` 不会自动存在——每个 bash 片段开头必须先设置（shell 状态不跨片段保留）**：`export WORKDIR="${WORKDIR:-/Users/alongor666/Desktop/上市公司研究}"`，否则 `ls $WORKDIR/...`、`cd $WORKDIR` 会展开成 `/...` 或回到 `$HOME` 而全部失败。脚本（quick_profile.py / vortex_draw_html.py / podcast_tts.py / podcast_qa.py / podcast_standards.yaml / markers.json）为外部依赖，不在 skill 包内；若 `$WORKDIR` 不存在则脚本步骤 fallback 到搜索补全（见执行原则 3）。

## ⚡ 执行原则（最高优先级）

1. **不停顿**：Step 0→11 为连续流程，中间不得暂停询问用户。仅在工具权限被拒或外部服务不可用时跳过该步并继续。
2. **并行优先**：能并行必并行——
   - Step 1（脚本画像，后台）与 Step 2（搜索）并行发起。
   - Step 2 同维度中英文搜索同批并行（一条消息多个 WebSearch）。
   - Step 7/8 中 `auth status` 只查一次，后续复用。
3. **脚本 fallback**：quick_profile.py 失败（超时/SSL/数据残缺）不重试，直接用 Step 2 搜索补全。
4. **飞书 auth 预检**：Step 0 即后台查 `lark-cli auth status`。token 过期 → 先 `auth refresh`；refresh 失败 → 输出登录链接但不阻塞 Step 1-6。Step 6 结束时检查 auth 是否就绪，未就绪则跳过 Step 7-8/11 并告知。

## 输入解析

| 输入示例 | 解析结果 |
|---------|---------|
| `阳光电源` | 公司名；搜索确认股票代码；默认中英双语 |
| `601609` | A股代码；Step 1 获取公司名 |
| `300274 纯英文资料` | A股代码 + 语言约束（仅英文搜索） |
| `SEDG` / `SolarEdge` | 非A股；跳过 AKShare；FinanceToolkit 或搜索补全 |
| `更新诊断` | UPDATE 模式（见 Step U） |

## 模式判断

- **NEW** — 首次分析，执行 Step 0→11
- **UPDATE** — 用户说"更新诊断/补充诊断/新信息/修正一下/最新数据"，执行 Step U

---

## NEW 模式

### Step 0: 加载框架 + 环境预检

**并行执行三件事**（一条消息发出）：
1. 读 `references/vortex-framework.md`，内化三才框架，不输出框架内容。
2. 后台 `lark-cli auth status`（前缀见 `references/lark-publish-protocol.md`），记录 tokenStatus / userOpenId；过期则后台 refresh → 失败则 `auth login --recommend` 输出链接（不阻塞）。
3. 设置并确认工作目录：`export WORKDIR="${WORKDIR:-/Users/alongor666/Desktop/上市公司研究}" && ls "$WORKDIR/scripts/quick_profile.py"`。

完成后立即进入 Step 1+2（并行）。

### Step 1: 数据快速画像（与 Step 2 并行启动，后台运行不等待）

**A股/港股代码 →** 后台运行，失败/超时/残缺则不重试、由 Step 2 补全：
```bash
export WORKDIR="${WORKDIR:-/Users/alongor666/Desktop/上市公司研究}"
cd "$WORKDIR" && .venv/bin/python3 scripts/quick_profile.py {代码}
```
提取：公司全称、行业、近5年营收/净利/毛利率/净利率/ROE。

**美股/其他 →** 检测 `.env` 的 FMP_API_KEY（先 cwd 再 `$WORKDIR`）：
- 有 Key → FinanceToolkit：`Toolkit(["{TICKER}"], api_key=key, start_date="5年前").ratios.collect_profitability_ratios()`
- 无 Key → 跳过，Step 2 补全

**仅公司名 →** 跳过脚本，Step 2 搜索时同步确认股票代码。

### Step 2: 双语信息搜索（与 Step 1 并行启动）

参考 `references/search-protocol.md` 的信息源优先级与轮次规则，执行 5+1 轮搜索。

**并行策略**：每条消息最多 3 个 WebSearch，分 2-3 批；同维度中英文同批。

| 批次 | 轮次 | 关键词模式 |
|------|------|-----------|
| 批次1 | 1-中 / 1-英 / 2-中 | {公司名} 创始人 发展历史 · {Company} founder history · {公司名} {年份} 业绩 营收 净利润 |
| 批次2 | 2-英 / 3-中 / 3-英 | {Company} {year} revenue earnings · {公司名} 竞争格局 市场份额 · {Company} market share competition |
| 批次3 | 4 / 5 / **R** | {公司名} 技术路线 风险 / {Company} technology roadmap risk · {公司名} 海外市场 政策 / {Company} overseas policy tariff · {公司名} 风险 失败 争议 做空 / {Company} risk failure controversy |

语言约束：默认每维度 1 中 + 1 英；"纯英文资料"仅英文；"纯中文"仅中文。
**批次3 必含逆向搜索（R 轮），不可省略。**

### Step 3: 三角验证

> 先列出每个关键判断的候选证据及其来源强度（一手 > 二手 > 媒体），再下结论。

- 每个关键判断须有 ≥2 个独立来源交叉确认
- 中文看国内视角+政策信号，英文看全球格局+国际投资者态度
- 区分事实与观点：年报数据是事实，券商目标价是观点
- 信息不足标注「信息不足」，不编造

### Step 4: 涡旋结构分析

读取 `references/vortex-framework.md` 的三才分析框架。对公司全生命周期划分 **3-5 个关键转折阶段**（按真实转折点，不按年份平均切分）。

> 形态判定前：先列出候选结构形态假设（如"钻头/堡垒/蛛网/等离子体"等隐喻）及各自证据强度，再选定最贴合的一个并下结论。

每阶段必须包含：

a) **三才拆解** — 天（外部压力：时代制约、熵增威胁来源）/ 人（向心力：核心凝聚力、最高密度点）/ 地（离心力：业务边界、扩张疆域）

b) **结构形态命名**（物理/几何隐喻 + 为什么必须是这个形状）

c) **ASCII 涡旋快照** — 上方外部压力（向下箭头）/ 中间涡旋主体（边界+核心）/ 标注力量方向与关键节点 / 用 Unicode 方框字符（═ │ ┌ └ ┐ ┘ ╔ ╗ ╚ ╝）

分析深度：解释"为什么这个结构在当时能赢"和"为什么后来失效了"，不做历史流水账。

### Step 5: 生成诊断报告

按 `references/output-template.md` 骨架生成完整报告。

**语言风格**：冷静、犀利、透彻；物理学+哲学词汇（熵增、矢量、阻尼、相变、奇点、向心力、离心力）。

**必含元素**（template 中【必选】）：每阶段三才+形态+涡旋快照（MD 保留 ASCII；飞书替换为 HTML→PNG）· 终局判断表（核心密度/边界扩张力/抗熵增能力/相变概率，四维★评分）· 一句话定义（物理学隐喻，可独立成立）· Sources（中英分组，MD 超链接）。

**行业自适应元素**（template 中【可选】）：财务表格、利润结构图、产能矩阵、客户集中度图等，按行业选用。

生成后用文末「质量检查」清单做一次自检回路，再进入 Step 6。

### Step 6: 保存文件（完成后立即进入 Step 7，不暂停）

文件名 `{公司名}_{股票代码}_结构诊断.md`（非A股用 `{交易所代码}`），保存至 `$WORKDIR/`。保存后告知路径，**立即继续 Step 7**，不要输出确认性问句。

### Step 7: 创建飞书云文档（依赖 Step 0 的 auth 预检）

**前置**：auth 未就绪 → 跳过 Step 7-8，提示"飞书授权未完成，报告已保存至本地，完成授权后说'发布飞书'即可补发。"

- **7a 有声长文**：按 `references/lark-longform-prompt.md` 把诊断报告转为可被飞书 TTS 流畅朗读的有声长文，保存为 `{公司名}_{股票代码}_有声长文.md`（与诊断报告同目录）。
- **7b 写入飞书**：按 `references/lark-publish-protocol.md`（分段创建文档 + 生成涡旋 PNG 图集 + media-insert + 授权所有者 + 输出 URL）。

### Step 8: 发送飞书消息通知

按 `references/lark-publish-protocol.md` Step 8（`/lark-im` 发文档链接给所有者）。

### Step 9: 生成播客文稿（Step 6 后即可启动，与 Step 7/8 并行）

按 `references/podcast-script-prompt.md` 生成约 1200-1500 字播客文稿（默认双人云阳/晓晓，单人模式见同文件），保存为 `{公司名}_{股票代码}_播客文稿.md`（与诊断报告同目录）。

### Step 9.5: 文稿质检（Step 9 后自动执行）

对文稿运行自动化质检（认知负荷/结构/格式/情绪弧线/对话真实感五维）：
```bash
export WORKDIR="${WORKDIR:-/Users/alongor666/Desktop/上市公司研究}"
.venv/bin/python3 $WORKDIR/scripts/podcast_qa.py \
  --script {公司名}_{股票代码}_播客文稿.md \
  --config $WORKDIR/scripts/podcast_standards.yaml \
  --markers $WORKDIR/scripts/markers.json
```
处理规则：**PASS** → 进 Step 10；**WARN** → 输出警告项继续 Step 10（不阻塞）；**FAIL** → 按报告 FAIL 项与 suggestion 修正后重跑，直到 PASS/WARN，最多重试 2 次。
标准配置 `podcast_standards.yaml`（三层：宪法/场景/派生参数）；词表 `markers.json`（追问/语气词/修正/知识不对称）。

### Step 10: 生成播客音频（Step 9.5 通过后执行）

Edge TTS 转音频，**默认 2 倍速**（`--rate "+100%"`）。脚本自动解析文稿标记：`[pause:Xs]` → 段后静音；`(放慢)` → +60%（≈1.6×）；`(加重)` → +120%（≈2.2×）；`(轻声)` → +80% 且音量 -30%（≈1.8×）；`[BGM:*]`/`[音效:*]` → 忽略。以上 rate 魔数为 2 倍速基线下的换算。

**可用声音**（经验证；若失效见脚本 Old patterns / 重新探测）：

| 声音 ID | 性别 · 别名 | 风格 | 用途 |
|---------|------|------|------|
| `zh-CN-YunyangNeural` | 男 · 云阳 | 新闻播报，权威 | 主持人 / 单人独白 |
| `zh-CN-XiaoxiaoNeural` | 女 · 晓晓 | 温暖自然 | 分析师 |
| `zh-CN-YunxiNeural` | 男 · 云希 | 阳光活泼 | 备选主持人 |
| `zh-CN-XiaoyiNeural` | 女 · 晓伊 | 甜美活泼 | 备选分析师 |

```bash
export WORKDIR="${WORKDIR:-/Users/alongor666/Desktop/上市公司研究}"
# 双人（默认云阳+晓晓，2倍速）
.venv/bin/python3 $WORKDIR/scripts/podcast_tts.py \
  --script {公司名}_{股票代码}_播客文稿.md \
  --output {公司名}_{股票代码}_播客.mp3 --rate "+100%"

# 单人（仅云阳，2倍速）：追加 --voice-a zh-CN-YunyangNeural
```
**时长控制**：目标 5 分钟 ≈ 1200-1500 字（约 250 字/分钟）；偏差超 ±1 分钟则调文稿长度重生成。音频保存 `{公司名}_{股票代码}_播客.mp3`。完成后告知路径与时长，**立即继续 Step 11**。

### Step 11: 发送播客音频到飞书（Step 10 后执行，依赖 auth 预检）

**前置**：auth 未就绪 → 跳过，提示"飞书授权未完成，播客音频已保存至本地，完成授权后说'发送播客'即可补发。"
执行命令见 `references/lark-publish-protocol.md` Step 11（`--file` 方式，复用 `userOpenId`）。

---

## UPDATE 模式

检测到 UPDATE 时执行以下，不执行 Step 0-6。

- **U1 定位**：当前目录搜 `*_结构诊断.md`；多个则询问确认，读取全文。
- **U2 搜证**：针对更新方向（或默认最新年度数据）搜 2-3 轮 + 三角验证。
- **U3 增量修正**：每项含「新证据链」「旧诊断 vs 新诊断」「评分变化（{维度} {旧★}→{新★} {↑/↓/→}，原因一句话）」。
- **U4 更新终局表**：每个变化维度标 ↑/↓/→ 与原因。
- **U5 写回**：修正合并入现有诊断文件，生成完整文档（读者无需看两份）；告知更新章节与评分变化条数。
- **U6 同步飞书 / U7 更新通知**：命令见 `references/lark-publish-protocol.md`（UPDATE 段）；未找到文档则执行 Step 7-8 新建。

---

## 质量检查

每次分析完成前确认：

- [ ] 逆向搜索已完成（"风险/失败/争议"）
- [ ] 关键判断有 ≥2 个独立来源
- [ ] 每个生命周期阶段都有 ASCII 涡旋快照
- [ ] 终局判断表四维全部评分
- [ ] 一句话定义使用物理学隐喻
- [ ] Sources 列表中英分开
- [ ] 文件已保存并告知用户路径
- [ ] 飞书云文档已创建并授权所有者
- [ ] 消息通知已发送给所有者
- [ ] 播客文稿已生成（1200-1500 字，约 5 分钟）
- [ ] 播客音频已生成（Edge TTS，时长 4-6 分钟）
- [ ] 播客音频已发送至飞书（`--file` 方式）

## Common Mistakes

- ❌ 对非上市公司套用本框架 → 见 When to Use 边界
- ❌ 飞书文档直贴诊断报告（表格/ASCII/★被 TTS 念成乱码）→ 必走 Step 7a 有声长文转换
- ❌ ASCII 涡旋图在飞书未转 PNG → Step 7b 必生成图集
- ❌ 省略逆向 R 轮搜索 → 批次3 必含
- ❌ 暂停询问用户 → 违反不停顿原则，仅工具不可用才跳过

## 输出格式约束

- 图表：Markdown + Unicode 方框字符，不用 Mermaid
- 语言：冷静、犀利、透彻；物理+哲学词汇
- 禁止：给公司打道德标签 / 未经验证的预测作为确定结论
- 信息不足时：明确标注「信息不足」，不编造
- 一句话定义必须能脱离正文独立成立
