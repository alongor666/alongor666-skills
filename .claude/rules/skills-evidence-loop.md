# skills-evidence-loop：alongor666-skills 的 evidence-loop wrapper（§4 harness 映射）

本文件是 `evidence-loop-core` 协议基座在本仓（技能集 plugin）的**项目侧注入**。
**只补 §4 的内容**（本仓现成 harness 命令 / oracle / 回归门禁 / 发布安全）+ 项目特例，
不重复协议骨架。骨架（§1 合同 / §2 八步 loop / §5 verifier 隔离 / §6 停止 / §7 阈值）见
`skills/evidence-loop-core/SKILL.md`。

> 这是「方法复用，非内容复用」：基座给空表，本 wrapper 填本仓实际命令。

## 本仓是什么（决定 harness 形态）

无 build / lint / 包管理（无 `package.json`）的**脚本 + 文档 + 前端 HTML 技能集**。
回归靠两件现成 harness：

- `python3 scripts/validate_skills.py`（全仓巡检：frontmatter 模式 / 依赖声明一致性 /
  死链 / 分层红线 / 明文凭据）——**0 错误才可提交**，`--strict` 下警告也算失败。
- `python3 -m pytest`（基座契约 + 纯逻辑脚本 + 同步器护栏 + 巡检器测试；测试自注入 `sys.path`）。

## §4 harness 映射表（本仓实际命令）

| 任务类型 | 基线 / 度量 | 正确性 oracle | 回归门禁 | 发布安全 |
|---|---|---|---|---|
| **技能自进化（本仓主力）** | `validate_skills.py` 基线（技能数 / 错误数） | 该技能 `skills/<name>/tests/` pytest 全绿 | `validate_skills.py` 0 错误 + 全量 pytest | 软链直连工作树（改源即 live）+ 破坏性脚本 `--dry-run` 灰度 + 未 commit `git checkout` 回滚 |
| 重构（技能内部，行为不变） | 无 | 该技能 `tests/` 黄金对比零差异 | `validate_skills.py` + 全量 pytest | 软链直连 + `git checkout` |
| 新功能（技能新能力） | — | 新增 `tests/` pytest + §3 证据 | `validate_skills.py` + pytest | `--dry-run`（若破坏性）+ 软链直连 |
| L0 基座 API 改动 | 基座 `tests/` baseline | 基座契约测试（ADR-004 版本契约） | 基座 tests/ + 依赖方 pytest（`diagnose-*` 连锁） | semver bump + `requires_skills` 同步 |
| 报告 / HTML 技能 | — | `node skills/xcl-html2pdf/driver.mjs <html>`（CDP 实测填充率 / 溢出 / 真实页数） | `validate_skills.py` + 报告中文红线自检 | `bundle.mjs` 自包含 + driver 验收 |
| 文档 / SKILL.md / frontmatter | — | `validate_skills.py`（frontmatter 模式 / 死链 / 依赖一致性） | `validate_skills.py` | — |
| 安全加固 | — | 修补不拆除（红线兜底） | `validate_skills.py`（明文凭据扫描） | — |

**现成命令速查**（跑前 `--help` 确认签名）：

```bash
python3 scripts/validate_skills.py            # 回归门禁，0 错误才提交；--strict 警告也失败
python3 -m pytest skills/<name>/tests/ -v     # 单技能 oracle
python3 -m pytest skills/chexian-report-shell/tests/ skills/extract-backlog-governance/tests/ \
  skills/sync-skills/tests/ skills/cleanup-worktrees/tests/ scripts/test_validate_skills.py -q  # 全量
node skills/xcl-html2pdf/driver.mjs <report.html>   # HTML 技能验收
```

> 全量 pytest 依赖 `pytest + pyyaml + pandas + duckdb`——云端 / 新机先 `pip3 install` 这四个，
> 否则基座契约测试因缺包失败（见 `CLAUDE.md`）。

## 项目特例（覆盖基座 §7 默认阈值）

本仓多为文档 / 脚本 / 前端技能，**非性能任务为主**。默认终止条件改为：

- **无正确性回归**（相关技能 `tests/` 全绿）
- **无 validate_skills 回归**（保持 0 错误）
- **相关 pytest 全绿**
- 仅性能类任务才套基座 §7 数字阈值（median / p95 ≥ 20%，CV ≤ 10%）——本仓罕见。

## 停止 / 回滚条件（项目特例追加，基座 §6 之外）

命中即报 **BLOCKED**：

- `validate_skills.py` 报错且无法在最小改动内修复
- 改 L0 基座（`chexian-report-shell/lib`）对外 API 签名但未过基座契约 `tests/`（ADR-004 连锁风险）
- 新增 **L1↔L1 横向 import**（违 ADR-002 星形分层）
- 报告 / HTML / PPT 产物残留英文术语缩写未译（违 `~/.claude/rules/common/report-language-redline.md`）

## scorecard 落位（基座 §8 step 4 / §10 必须显式声明）

> **本仓采用「产物即证据」模式——这是对基座 §10「显式声明一个集中 scorecard 位置」的
> 项目特例，此处即显式声明，故阶段 C step 4 不报 BLOCKED。** 本仓无 `docs/evidence/`
> 之类持久化目录，且基座 §2 step 8 禁止为单次结论新建目录，故不集中写「卡」，而是把
> scorecard 各要素**分布式嵌入下列已被 git 跟踪的产物**：

| scorecard 要素 | 持久化落点 |
|---|---|
| 基线 / 候选 / 决策 | **commit message** body（被验证命令 + 前后对比写进 commit） |
| 正确性 / 回归证据 | 技能 **`tests/`** 新增测试 + PR 描述贴的命令输出 |
| 风险 / 变更说明 | 技能 **`SKILL.md` changelog** |
| 协议短板（非本技能问题） | `skills/evidence-loop-core/IMPROVEMENTS.md`（基座本地 backlog，append-only） |

- scorecard 的**汇总视图**在会话内呈现（便于当轮复核），其证据已落在上表产物中。
- ⚠ **worktree 时序**：在 git worktree 内追加 `IMPROVEMENTS.md` 写的是 worktree 内副本，
  须 commit + merge 回 main 后，主仓软链 `~/.claude/skills/evidence-loop-core/IMPROVEMENTS.md`
  才看得到——**不要假设软链实时可见**。

**禁止写入**（user-only 平台 memory，`CLAUDE.md` 定义为单一事实源，AI 不得擅写）：

- `~/.claude/projects/**/memory/`、`MEMORY.md` —— 由用户 / 平台管理
- 命中即按基座 §8 step 4 **报 BLOCKED**，不默认写受保护路径

## 关联

- 协议骨架：`skills/evidence-loop-core/SKILL.md`
- 三阶段执行器命令：`.claude/commands/skills-evidence-loop.md`
- verifier agent：`.claude/agents/evidence-verifier.md`（复制自 `skills/evidence-loop-core/verifier-agent-template.md`）
- 分层 / 复用约束：`docs/ARCHITECTURE.md` + `docs/adr/ADR-001..005`、`CLAUDE.md`
