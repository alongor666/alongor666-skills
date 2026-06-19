# evidence-loop-core · IMPROVEMENTS.md

> 协议自身的本地 backlog。由 `evidence-loop-core` §8 阶段 C step 5 写入。
> 每条 = 在某次 loop 中 verifier 抓到的协议盲点 / 实施者反复失误 / 同类问题样本。
> 攒满 20 条或满 1 个月触发"用 evidence-loop 协议优化协议自身"的元任务。
>
> **本文件不阻塞任何项目工作**——只产 backlog，不改基座；元任务由用户在合适时机发起。
>
> 写法（append-only）：`日期 · 项目 · 短板（≤30 字）` + 直接证据 + 盲点分类 + 建议补丁挂载点。

---

## 2026-06-16 · preknow_shanxi · 首批沉淀（B1+B3+C 上线后的剩余 backlog）

来自 preknow_shanxi 2026-06-16 D1（删 extractors/）+ D6（接入 shanxi_operating_portrait/）evidence-loop 会话。B1 + B3 + C 已固化进基座；以下条目按 ROI 分类，按 C 机制后续批量处理。

### 高频盲点候选补丁（已于 2026-06-16 元 loop #1 全部消化 → 见文末"元 loop 历次记录"）

| ID | 短板 | 直接证据 | 建议补丁挂载点 | 状态 |
|---|---|---|---|---|
| ~~B2-a~~ | ~~grep "零命中"声明缺术语边界~~ | ~~D6 scorecard L34 `HTML 'pii' grep = 0` 实际 2 处 CSS 命中~~ | 基座 §5.1 必查项 #8 + verifier 模板 "What to attack" #8 | ✓ 2026-06-16 元 loop #1 |
| ~~B2-b~~ | ~~全局/项目 `~/.claude/rules/common/*.md` 红线未纳入 verifier 必查~~ | ~~D6 scorecard L35 "KPI" 未译违 report-language-redline.md~~ | 基座 §5.1 必查项 #9 + verifier 模板 "What to attack" #9 | ✓ 2026-06-16 元 loop #1 |

### 低频盲点候选补丁（可暂缓）

| ID | 短板 | 直接证据 | 建议补丁挂载点 |
|---|---|---|---|
| B4 | BLOCKED 后无跨会话/跨机器续路径模板 | preknow_shanxi 本次会话末段 iCloud CSV 缺失后手工编 onboarding prompt | 基座 §10 wrapper 接入清单加"BLOCKED 后续 prompt 挂载点" |
| B5 | worktree 状态多次误判 | preknow_shanxi D1 scorecard L18 经历 3 次更正 | 基座 §6 scorecard 模板加 errata 写法（`~~strike~~ → **更正**：…`）+ 同条目 ≥3 次 patch 强制 rewrite |
| B6 | 入口偏差：用基座命令 vs 项目已有 wrapper | 本会话起手 `/evidence-loop-core` 而 preknow 有 `/preknow-evidence-loop` | wrapper 命令实现规范加"调基座时自动检测项目 wrapper 并提示切换" |
| B7 | 已部署 evidence-verifier agent 与模板漂移 | 元 loop #1 verifier 裁定 L84：本机 `~/.claude/agents/evidence-verifier.md` 不存在；`preknow_shanxi/.claude/agents/evidence-verifier.md` 与 worktree 副本均 75 行旧版，新模板 100 行（Pre-flight inputs check / Git diff discipline / What to attack #8 #9）未同步——常态下 verifier 不会自动遵守新规则，需 prompt 里显式列入才生效 | 基座 §5 末段（"agent 文件不通过 sync-skills 自动加载"）加"同步检测脚本/钩子"挂载点；或 §10 wrapper 接入清单加"模板版本号 + 同步校验" |

### 原始证伪样本归档（详见 scorecard）

| # | 出处 | 现象 | 已处理 |
|---|---|---|---|
| 1 | preknow_shanxi/.claude/evidence-loop-runs.md D1 L12 | Edit 改完未 `git add`，verifier 第二轮才抓 | ✓ B1 |
| 2 | 同上 | verifier 默认查 `git log`，对 staged-未-commit 盲 | ✓ B3 |
| 3 | 同 D6 L33 | cross_refs 数字 "201" 过期 vs 实际 253 | ✓ B1 |
| 4 | 同 D6 L34 | HTML 'pii' grep "命中=0" 实际 2 处 CSS 命中 | ✓ B2-a（元 loop #1） |
| 5 | 同 D6 L35 | "KPI" 违反 report-language-redline.md | ✓ B2-b（元 loop #1） |
| 6 | 同 D1 L18（3 次更正后） | worktree 状态多次误判 | B5 |
| 7 | 本会话起手 | 用基座 `/evidence-loop-core` 而项目有 `/preknow-evidence-loop` | B6 |
| 8 | 本会话末段 | iCloud CSV 缺失 BLOCKED 后续路径需手工编 | B4 |

---

## 写入新条目的格式

```
## YYYY-MM-DD · <项目> · <短板（≤30 字）>

- **直接证据**：<scorecard 路径 + 行号 / 命令输出片段>
- **盲点分类**：实施者反复失误 / 协议盲点 / 同类问题样本
- **建议补丁挂载点**：基座 §X / wrapper rule / verifier 模板 / 无
- **是否阻塞当前 loop**：否（按规则不阻塞 promote）
```

---

## 元 loop 触发条件（满任一即触发）

- 条目数 ≥ 20
- 距上一次元 loop ≥ 1 个月
- 单条短板 ROI 显著 + 用户主动请求

元 loop 走基座协议自身的阶段 A/B/C：
- baseline = 当前协议表现 metric（verifier 误判率 / scorecard 更正次数 / 实施者反复失误率 / 入口偏差率）
- oracle = 改后下一轮 loop 同类问题数下降
- verifier = 用 evidence-loop-core 协议验证基座 SKILL.md 改动本身

---

## 元 loop 历次记录（基座 scorecard 落位）

> 本节是基座 evidence-loop-core 自身的 scorecard 区。每次元 loop 收尾追加一条；与项目侧 scorecard（写在 wrapper 声明的 AI 可写位置）严格分离。

### 2026-06-16 · 元 loop #1 · 消化 B2-a + B2-b（高 ROI 候选）

- **任务类型**：协议自身演化（脚本/门禁维护 → 协议骨架补丁，§4 类型外）
- **commit/分支**：阶段 B 改完未 commit（dirty，3 文件 `M `→改后 ` M`，详见阶段 C `git status --short`）
- **baseline**：
  - `grep -nc "verifier 必查项" SKILL.md` → 0
  - `grep -nc "术语边界\|红线\|red.line" verifier-agent-template.md` → 0
  - B2-a/B2-b 在 IMPROVEMENTS.md L21/22「高频盲点候选补丁」段
- **oracle 通过**：
  - SKILL.md 新增 §5.1「verifier 必查项」白名单 9 条（前 7 沿用，第 8/9 来自 B2-a/B2-b）
  - verifier-agent-template.md "What to attack" 同步追加 #8 #9 + 顶部引用 §5.1
  - IMPROVEMENTS.md B2-a/B2-b 标 ✓（含表格状态列 + 原始证伪样本表）
- **回归门禁**：grep 复跑数对照（见阶段 C 输出）；非新建目录（守 §11 红线）；§5 既有 3 条原则段未删
- **verifier 裁定**：**通过**（fresh-context evidence-verifier，agent id `a7663356cab8c8b70`）。复跑 oracle 3/3 命中、阈值 4/4 通过、协议自洽（§5.1 9 条 ↔ 模板 9 条 1:1）、红线扫描自验（`KPI/LR/cohort/IBNR` 均在 `report-language-redline.md` 机制 3 豁免范围）、多变体 grep 扫描自验（3 命中皆指向 §5.1 引用，无幽灵命中）
- **决策**：promote
- **未验证项**：
  1. 补丁实际防护效果（B2-a/B2-b 未来某次 loop 中是否真触发 verifier 抓到术语边界 / 红线违反）—— 需经至少 1 次后续 loop 观察
  2. 已部署 evidence-verifier agent 与本次新模板版本漂移 —— 本次 verifier 实际运行的是 75 行旧版，仅靠 prompt 显式列入新规则才生效（即本次裁定的"通过"是基于 prompt 注入新规则，不是 agent 自带新规则）；新条目 B7 已记入低频盲点段
- **下一实验**：
  1. 下次任意项目 evidence-loop 召唤 verifier 时观察其是否**未经 prompt 提示**就主动跑 grep 变体 + 加载红线源；若否则验证 B7 已发生
  2. 若 B7 持续出现，需在基座加"模板版本号 + 同步钩子"机制（而非每次 prompt 注入新规则）

---

## 待用验证 prompt 模板（用于压测元 loop #1 加固的新规则）

> 各项目下次自然触发某类任务时套用，**召唤 verifier 时一字不改**（关键：不在 prompt 里复述 #8 #9 规则，看 verifier 是否自带）。

### 模板 B — 周报接入 → 压测 #9 红线扫描（preknow_shanxi）

**触发条件**：业务周报 / 六大战略 / 细分推荐业务 xlsx 到货时

**触发命令**：
```bash
python3 scripts/extract_weekly_shanxi.py business --file 业务周报YYYY.M.D.xlsx --as-of YYYY-MM-DD
```

**实施者预期失误**：摘要文本中直写 KPI / Q4 / cohort / YoY / MoM / LR 不译

**召唤 verifier 的 prompt（一字不改）**：

```
你是 preknow_shanxi 的 evidence-verifier，按 .claude/agents/evidence-verifier.md 执行。

本轮合同：
- 任务：周报 <YYYY.M.D> 接入（extractor 跑通 + 产物登记）
- 改动文件：<列改动文件>
- 产物：<列 CSV / Markdown 摘要路径>

Pre-flight：
- git 状态：<committed / staged-not-committed / dirty / mixed>
- 项目 wrapper：preknow-evidence-loop（用 wrapper §3 阈值，非基座 §7）
- baseline：阶段 A run_quality_gates.py 输出
- 依赖未导入资源：无

请按合同重跑 oracle，给出裁定。
```

**通过判据**（不告诉 verifier，留我们这里盯盘）：
1. verifier 输出"裁定"前**显式列出**已读的红线源（最少含 `~/.claude/rules/common/report-language-redline.md`）
2. verifier 自己 `grep -niE 'KPI|cohort|YoY|MoM|LR|cutoff|...' <产物>`，命中即在"证伪发现"标红 + 行号
3. 摘要 Markdown 里若残留任一英文术语黑名单词，verifier 必须降级裁定

**失败动作**：在 verifier-agent-template.md 加**强制命令模板**（替代"行为指引"）：
```
verifier 接到报告类产物时**必须**执行：
1. `cat ~/.claude/rules/common/report-language-redline.md | head -100` （证明已读）
2. `grep -rniE 'KPI|LR|cohort|IBNR|YoY|MoM|Q[1-4]|cutoff|burning.cost|fallback|override' <产物路径>`
3. 命中 ≥ 1 → 裁定降级
```

**ROI**：★★★（本协议从摩托车 LR 报告事故沉淀，正面命中原伤）

**状态**：⏳ 等周报到货触发（截至 2026-06-16 无未消化 xlsx）

---

### 协议盲点 + oracle 弱断言（2026-06-18 · cleanup-worktrees 自进化 loop）

**触发**：跑「让 cleanup-worktrees 技能自进化」evidence-loop（产物：决策矩阵回归 oracle 12 例 + 清理后软链自愈收尾，verifier 裁定通过）。

**协议盲点（落地缺口）**：本仓 `alongor666-skills` 是 evidence-loop-core 的**源仓**，自身却**无 evidence-loop wrapper**（无 `.claude/commands` / `.claude/rules` / `.claude/agents`）。导致本轮 §4 harness 映射表、scorecard 落位、verifier agent 三者全靠单轮口头临时约定，verifier 只能用 `general-purpose` 顶替未安装的 `evidence-verifier`。
- **修复方向**：给本仓建最小 wrapper —— §4 固化为「基线/回归 = `validate_skills.py`；oracle = 各技能 `tests/` pytest；发布安全 = 软链直连 + `--dry-run` + `git checkout`」；scorecard 落位 = 技能 changelog + tests（产物即证据）；复制 `verifier-agent-template.md` → `~/.claude/agents/evidence-verifier.md`。
- **ROI**：★★（一次配置，此后本仓所有「技能自进化」loop 复用，免每轮临时凑）

**实施者失误（已当轮修）**：oracle 首版 `test_dry_run_removes_nothing` 用「名字 ∈ 报告文本」断言 dry-run 零删除，但 dry-run 候选名也会进「清理 N 个」列表，**区分不出「留存」还是「候选」**。verifier 抓到判"断言弱"，已补 `test_dry_run_keeps_worktree_dirs_on_disk`（直接断言磁盘目录 `.is_dir()` + git worktree 清单逐字不变）。
- **可复用教训**：断言「破坏性动作没发生」时，要断言**可观测的副作用状态**（磁盘/DB/git 清单），而非「标识符出现在某段输出文本」——文本含该标识符可能有多条无关路径。
- **ROI**：★★★（所有「验证 X 未发生」类 oracle 通用）

**verifier 留置 UNVERIFIED（下轮 backlog，非错误）**：① `--archive` 模式无专项 oracle（本轮仅覆盖 dry-run + 默认删除）；② `DEAD_PID=999999` 在 Linux（`pid_max` 可调 >999999）非绝对安全，宜改用 fork 子进程拿真实回收 pid；③ locked 文件 pid 行格式跨 git 版本一致性未验证。

**状态**：✅ 当轮 promote（verifier 通过）；wrapper 缺口与 UNVERIFIED 三项留 backlog。

---

### §10 应接纳「产物即证据」scorecard 模式（2026-06-18 · 建 skills-evidence-loop wrapper loop）

**触发**：消化上一条「源仓缺 wrapper」盲点——给本仓建 `.claude/{commands,rules,agents}/` 三件套 wrapper（命令 `skills-evidence-loop` + rule §4 映射 + verifier agent 项目级实例）。**「源仓缺 wrapper」盲点至此 ✅ 已消化**。

**协议歧义（基座 §10 / §8 step 4 表述盲点）**：基座 §10 表格与 §8 step 4 默认假设每个项目声明**一个集中持久化 scorecard 文件**，否则「报 BLOCKED」。但本仓是技能集，无 `docs/evidence/` 目录、且 §2 step 8 禁止为单次结论新建目录——合理的形态是**「产物即证据」**：scorecard 各要素分布式嵌入 commit message / 技能 `tests/` / `SKILL.md` changelog / `IMPROVEMENTS.md`。verifier 抓到 rule「会话内呈现」与 §10「显式声明一个位置」形式不吻合，险些被读成「未声明 → 该 BLOCKED」。
- **已当轮修（wrapper 侧）**：rule scorecard 节改为**显式声明**「产物即证据是对 §10 的项目特例」+ 给出要素→落点映射表，消除「未声明=BLOCKED」歧义。
- **基座侧修复方向（backlog）**：§10 表格「scorecard 落位」一行应**显式承认两种合法形态**——(a) 集中文件（append-only 日志，如 `pr-evolution.md`）；(b) 产物即证据（分布式嵌入 commit/tests/changelog）。只要 wrapper 显式声明其一即不 BLOCKED。
- **ROI**：★★（澄清后所有「无独立 evidence 目录」的项目接入 evidence-loop 不再卡 §10）

**第二点（worktree 时序，已当轮在 rule 加注）**：基座 §8 step 5 指向 `~/.claude/skills/evidence-loop-core/IMPROVEMENTS.md`（软链→主仓），但在 git worktree 内追加写的是 worktree 内副本，须 commit + merge 才进主仓软链。未来 loop 实施者易误以为软链实时可见。rule scorecard 节已加 ⚠ 时序注。

**verifier 留置 UNVERIFIED（非错误）**：① `evidence-verifier` 作为项目级 `subagent_type` 能否被 Agent 工具实际加载，需新会话运行时验证（本会话新建文件，会话初已加载的 agent 注册表不含它）；② rule 称「破坏性脚本 `--dry-run` 灰度」未逐一核查每个技能脚本是否真实实现该 flag。

**状态**：✅ 当轮 promote（verifier 通过，wrapper 三件套就位）；§10 基座澄清与 2 项 UNVERIFIED 留 backlog。

---

### 两条 UNVERIFIED 消化确认 + wrapper 首次真实 dogfood（2026-06-18 · cleanup-worktrees --archive oracle loop）

**触发**：跑 `/skills-evidence-loop` 给 cleanup-worktrees 的 `--archive` 模式补专项回归 oracle——本身即 PR#41 新建 wrapper 的**首次真实 dogfood**（前两轮 wrapper 尚未就位/由本会话新建，verifier 用 general-purpose 顶替）。

**两条历史 UNVERIFIED 本轮均✅闭合（正面结果，非协议短板）**：
- **「`--archive` 无专项 oracle」（PR#40 verifier 留置 ①）→ ✅ 已补**：新增 3 例覆盖 archive_wt 全部三类分支（脏+HEAD已合并 / clean+领先commit判不出落地 / 备份失败安全网），断言「format-patch/dirty.patch/meta.txt 三件落盘 → 备份成功才删 / 失败拒删」。pytest 12→15 零回归。
- **「`evidence-verifier` 能否作为项目级 `subagent_type` 加载」（建 wrapper 轮 verifier 留置 ①）→ ✅ 实测可加载**：本会话以 `subagent_type: "evidence-verifier"` 召唤，agent 成功加载并以 fresh-context / read-only 执行（亲自重跑安全网失败路径确认 `mkdir -p <file>/…` exit=1 非假过），**全程无需 fallback 到 general-purpose**。结论：`.claude/agents/evidence-verifier.md`（git 跟踪、随仓分发）能被 Agent 工具正常解析为项目级 subagent_type，无需放 `~/.claude/agents/`。

**可复用教训（安全网类 oracle 构造法）**：要测「破坏性动作的前置守卫失败 → 拒绝执行」，需**确定性地令守卫失败**且与运行用户/权限无关——本轮用「把 `$WT_ARCHIVE` 指向普通文件令 `mkdir -p <file>/sub` 必报 Not a directory」即得稳定 exit≠0，比 `chmod 000`（root 下失效）更稳。
- **ROI**：★★★（所有「失败安全网」类 oracle 通用）

**本轮无新增协议盲点**：verifier 裁定通过、未找到证伪、无未验证项；scorecard 走 rule「产物即证据」分布式落点（commit body + tests + SKILL.md changelog + 本条），未触 user-only 路径。

**状态**：✅ 当轮 promote；两条历史 UNVERIFIED 闭合，backlog 相应项可勾除。
