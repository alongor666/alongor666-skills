# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

个人自建的 Claude Code 技能集（plugin），平铺命名空间，覆盖三大领域 + 一个可视化横切层：

- **车险经营**：`chexian-*`（渠道/出险率/市场/定价/复盘）、`diagnose-*`（机构周报/周期趋势/赔付发展三角）、`rewrite-conclusion`
- **上市公司诊断**：`company-vortex`（涡旋结构诊断）、`company-vortex-card`（诊断→视觉卡片）
- **工程治理 / 横切**：`commit-push-pr-core`、`sync-skills`、`cleanup-worktrees`、`extract-backlog-governance`、`crystallize-skill`、`ui-redesign`、`xcl-html2pdf`（HTML→PDF/PPT 基座）、`chexian-report-shell`（报告渲染基座）

每个技能 = `skills/<name>/` 一个目录，必有 `SKILL.md`（带 frontmatter），按需附 `*.py` / `*.sh` / `*.mjs` / `lib/` / `references/` / `assets/` / `tests/`。**没有 build / lint / 包管理**（无 `package.json`）——这是脚本 + 文档 + 前端 HTML 的集合；其中 `*.mjs`（driver / bundle）依赖本机 Node + Chrome/CDP，其余为纯 Python / bash。

## 常用命令

```bash
# 全仓技能巡检（frontmatter 模式 / 依赖声明一致性 / 死链 / 分层红线 / 明文凭据，规则见脚本头注释）
python3 scripts/validate_skills.py            # 0 错误才可提交；--strict 警告也算失败

# 测试（基座 + 纯逻辑脚本 + 同步器护栏 + 巡检器；无 pytest.ini/conftest，测试自注入 sys.path）
python3 -m pytest skills/chexian-report-shell/tests/ skills/extract-backlog-governance/tests/ skills/sync-skills/tests/ scripts/test_validate_skills.py -q
python3 -m pytest skills/chexian-report-shell/tests/test_skill_path.py -v   # 单文件
python3 -m pytest skills/chexian-report-shell/tests/test_skill_path.py -k sibling_walkup -v  # 单用例（-k 子串匹配）

# 技能软链同步（见下「同步模型」）——改源即生效的关键
skills/sync-skills/sync-skills.sh link    --repo "$(pwd)" --dest ~/.claude/skills --subdir skills
skills/sync-skills/sync-skills.sh doctor  --repo "$(pwd)" --dest ~/.claude/skills --subdir skills  # 体检软链是否直连
skills/sync-skills/sync-skills.sh install-hooks  # 装 post-checkout/post-merge 钩子，切分支/pull 后自动补软链

# HTML 报告类技能：验收 driver.mjs（xcl-html2pdf 与 company-vortex-card 均有）；打包 bundle.mjs（仅 xcl-html2pdf）
node skills/xcl-html2pdf/driver.mjs <report.html>   # CDP 实测每页填充率/溢出/真实页数
node skills/xcl-html2pdf/bundle.mjs <report.html>   # 外链 css/js 内联成自包含单文件
```

## 同步模型：软链直连工作树（必读，否则"改了源不生效"）

`sync-skills link` 把 `skills/<name>/` **软链**到 `~/.claude/skills/<name>`——Claude Code 实际加载的就是本仓工作树文件。**改源即 live**，无需 `cp`、无需重装。`.githooks/{post-checkout,post-merge}` 会在切分支 / pull / merge 后幂等补齐软链。

⚠️ 陷阱：`npx skills add … --all`（README 给外部用户的安装方式）会把软链**覆盖为拷贝**，此后改源不再生效。本机用 `doctor` 检测、`link` 修回。详见 memory `skills-install-via-npx`。

## 分层架构与跨技能复用（读多文件才能看清的大局）

权威文档：`docs/ARCHITECTURE.md` + `docs/adr/ADR-001..005`。要点：

**星形分层依赖**，所有箭头指向 L0，**禁止 L1↔L1 横向 import**（ADR-002）：

```
L2 编排   chexian-ops-review · company-vortex-card
L1 业务   chexian-* · diagnose-* · company-vortex · rewrite-conclusion
L0 基座   chexian-report-shell(lib) · xcl-html2pdf · commit-push-pr-core   ← 复用枢纽
横切      sync-skills · cleanup-worktrees · extract-backlog-governance · ui-redesign · crystallize-skill
```

- **复用靠运行时 `sys.path` 注入**，不靠包管理。跨技能定位兄弟技能用 `chexian-report-shell/lib/skill_path.py` 的 `skill_path(name)` / `skill_lib(name)`，**严禁再写硬编码 `~/.claude/skills/...`**（ADR-001 修的就是这个崩溃点）。解析优先级：`$CLAUDE_SKILLS_DIR` 环境变量 > 兄弟目录回溯 > 旧硬编码兜底——所以安装位置无关。
- **SSOT 下沉**：亮灯阈值、客户类别标签、时间窗构造、主题等集中在 `chexian-report-shell/lib/`，业务技能用 thin shim 委托，不要复制粘贴这些常量。
- **基座 `user_invocable: false`** 主动隐藏，不面向用户 `/` 调用；直接跑 L1/L2 业务技能即可。

## SKILL.md frontmatter 约定

```yaml
name: <技能名>           # 与目录名一致
description: >-          # Use when… + 中英双触发词，AI 据此选技能，写充分
user_invocable: true     # 基座设 false
version: "1.20.0"        # 语义化版本
requires_skills:         # 仅声明「运行时 import 边」——见下口径
  - chexian-report-shell
```

`requires_skills` **口径（ADR-005）**：只覆盖 `sys.path` 运行时 import 依赖（`skill_path`/`skill_lib`/`SHELL_ROOT`/`dhr_lib` 那类）。**编排式调用**（斜杠命令工作流，如 ops-review 调 market/channel/pricing）和**产物消费**（如 vortex-card 读 vortex 的 `.md`）**不入** `requires_skills`，记在 SKILL.md 正文。删掉某依赖最后一处 import 时，同步删声明。当前已声明的 import 边：`diagnose-{org-weekly,period-trend,loss-development}` → `chexian-report-shell`（必需）；`chexian-report-shell` → `chexian-im-push`（可选·外部技能·仅推送降级）。一致性由 `scripts/validate_skills.py` **自动巡检**（声明↔代码双向核对 + L1 横向边检测），提交前必须 0 错误。

## 改动技能时的关键约束

- **改 L0 基座对外 API 前**：先过基座 `tests/`（ADR-004 的版本契约）。`chexian-report-shell/lib/` 被多个 `diagnose-*` 共用，改签名会连锁。
- **新增跨技能依赖**：用 `skill_path()` 解析 + 在 SKILL.md 补 `requires_skills`，两件事一起做。
- **org-weekly 渲染器入口不变量**：`render_v{1,3,4}_org.py` 的 `from lib.themes_v2 import …` 无兜底，依赖 `cli.py` 在导入前注入 `SHELL_ROOT`。若新增非 `cli.py` 的进程入口，必须同样注入 `SHELL_ROOT` 或补回退（详见 ARCHITECTURE.md §7）。
- **报告产物与对话回复严格中文化**：本仓充满 `diagnose-*` / `chexian-*` 报告技能，产出的 HTML/PDF/PPT/图表正文禁用英文术语缩写（LR/DW/cohort/IBNR/emergence/fallback…），须译为中文全称 + 首次释义。SKILL.md 内部可用英文编排，**产物不可**。红线见 `~/.claude/rules/common/report-language-redline.md`。
- **命名**：领域技能用领域前缀（`chexian-` / `diagnose-` / `company-`）；项目无关通用工具不强加前缀。

## 重资产技能的内部文档

`chexian-report-shell`、`diagnose-org-weekly`、`diagnose-period-trend`、`diagnose-loss-development`、`xcl-html2pdf` 等带自己的 `README.md`，讲清 lib 模块职责 / 渲染管线 / CSS 皮肤体系。动这些技能前先读其 README，别只看 SKILL.md。
