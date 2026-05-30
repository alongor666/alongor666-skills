---
name: commit-push-pr-core
description: >
  项目无关的 Git 提交 → 推送 → 建 PR 工作流基座。含跨项目通用护栏（大文件拦截、
  unrelated-histories 处理、rebase 后 lockfile 同步、push 后回主干）+ 可挂载的项目
  红线自审与自进化机制。Use when 用户说 "提交并建 PR"、"commit push pr"、"开个 PR"、
  "走提交流程"，或需要把改动安全地提交、推送、创建 Pull Request 时。设计为被各项目
  的薄 wrapper（如 <project>-commit-push-pr）import 复用，wrapper 只填项目专属红线与脚本路径。
version: 1.0.0
user_invocable: true
requires:
  - git
  - gh CLI（GitHub PR；非 GitHub 平台见 §5 备注）
---

# commit-push-pr-core：可复用的提交建 PR 工作流基座

把「改动 → commit → push → PR」标准化，并内置**跨项目通用的 git 护栏**。
项目专属规则（指标注册表、SQL 安全、领域口径等）**不写在这里**——通过
`.claude/pr-checklist.md`（自审清单）和 `scripts/` 钩子由各项目挂载。

> **复用模型**：本 skill = L1 骨架 + L2 通用护栏 + L3 方法层。
> 各项目建一个薄 wrapper import 本 skill，只补 L3 的**内容**（红线条目、脚本路径）。
> 这是「方法复用，非内容复用」——禁止把任何单一项目的红线条目硬写进本文件。

---

## 0. 探测环境（每次开头执行）

```bash
# 0.1 当前上下文
git branch --show-current
git status --short
git log --oneline -3
BASE="$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')"; BASE="${BASE:-main}"
git diff --stat "origin/$BASE" 2>/dev/null || git diff --stat "$BASE"

# 0.2 自动探测包管理器（用于 lockfile 同步与项目脚本）
# RUN  = 跑 package.json 脚本（如 `$RUN governance`）
# EXEC = 跑脚本文件（如 `$EXEC scripts/x.mjs`）；只有 bun 的 `run` 能直接吃文件路径，
#        npm/pnpm/yarn 的 `run` 会把路径当成脚本名而报错，故非 bun 一律用 node 执行文件
# LOCK = 实际存在的锁文件名（bun.lockb 旧二进制锁不可重写成 bun.lock，否则同步时 git add 到不存在的文件）
if   [ -f bun.lock ];          then PM="bun";  RUN="bun run"; EXEC="bun";  LOCK="bun.lock"
elif [ -f bun.lockb ];         then PM="bun";  RUN="bun run"; EXEC="bun";  LOCK="bun.lockb"
elif [ -f pnpm-lock.yaml ];    then PM="pnpm"; RUN="pnpm";    EXEC="node"; LOCK="pnpm-lock.yaml"
elif [ -f yarn.lock ];         then PM="yarn"; RUN="yarn";    EXEC="node"; LOCK="yarn.lock"
elif [ -f package-lock.json ]; then PM="npm";  RUN="npm run"; EXEC="node"; LOCK="package-lock.json"
else PM=""; RUN=""; EXEC="node"; LOCK=""; fi
echo "包管理器: ${PM:-无}  锁文件: ${LOCK:-无}"
```

```bash
# 0.3 读取项目自进化日志（若存在）——逐条检查「预防」措施是否已满足
cat .claude/workflow/pr-evolution.md 2>/dev/null | tail -40 || true
```

如果本次变更命中已记录的失败模式，**先在步骤 3 之前修复**。

---

## 1. 分析变更

- 查看所有变更文件，理解改动目的与范围
- 识别变更类型：feat / fix / refactor / docs / test / chore / perf / ci
- **依赖链完整性**（通用）：若改了 API/接口/配置的一侧，`grep` 确认另一侧（调用方/路由/类型定义）已同步

---

## 2. 生成 Commit Message

```
<type>(<scope>): <subject>

<body：what 和 why，不是 how；每行 ≤ 72 字符>

<footer：Closes #123 等>
```

- type：`feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci`
- subject：动词开头，≤ 60 字符
- 末尾按需附加 attribution trailer（HEREDOC 传递），遵循各项目约定

**示例**

```
feat(auth): 支持 PAT 只读令牌登录

- 新增 Bearer 解析与 readonly 中间件
- DB 仅存 bcrypt(secret)，明文仅生成时返回一次

Closes #42
```

---

## 3. 前置检查（CRITICAL — 通过后才能提交）

### 3.0 大文件拦截（防 push 被远端拒绝）

```bash
find . -not -path './.git/*' -not -path './node_modules/*' -size +50M -exec ls -lh {} \;
```

发现 >50MB 文件：① 确认是否该入 `.gitignore`；② 需提交则配 Git LFS（`git lfs track "*.<ext>"`）；③ **禁止忽略此步直接 push**。

### 3.0b 共同祖先检查（防 unrelated histories）

```bash
# 必须先 fetch 并对 origin/$BASE 判断：仅有 origin/main、无本地 main 的检出（worktree/
# 单分支克隆）下 `git merge-base main HEAD` 会因 main 不是有效对象而误报"无共同祖先"，
# 把正常分支推向下面破坏性的 clean-branch/cherry-pick 路径
git fetch origin "$BASE" 2>/dev/null
git merge-base "origin/$BASE" HEAD || echo "⚠️ 无共同祖先"
```

**无共同祖先**：禁止 rebase（会产生大量 add/add 冲突）。改用 cherry-pick：
```bash
git checkout -b fix/clean-branch "origin/$BASE"
git cherry-pick <本分支独有 commit...>
```

### 3.1 同步远端 + 处理 lockfile

```bash
git fetch origin "$BASE"
```

分支落后 `$BASE`（有共同祖先，常规情况）：
```bash
git stash && git rebase "origin/$BASE" && git stash pop
```

**rebase 后必须同步 lockfile**（否则 CI frozen-lockfile 报错）：
```bash
[ -n "$PM" ] && $PM install \
  && git add "$LOCK" \
  && git commit -m "chore: sync $LOCK after rebase" 2>/dev/null || true
```

push 遇到 LFS `locksverify EOF`：
```bash
git config "lfs.$(git remote get-url origin | sed 's#.*github.com/#https://github.com/#;s#\.git$##').git/info/lfs.locksverify" false
```

### 3.2 项目冲突检测钩子（若存在则运行）

```bash
[ -f scripts/check-write-conflict.mjs ] && $EXEC scripts/check-write-conflict.mjs
```

### 3.3 项目治理校验钩子（若存在则运行）

```bash
[ -f scripts/check-governance.mjs ] && $EXEC scripts/check-governance.mjs
# 通用兜底：有 governance / lint / build 脚本则跑
[ -n "$PM" ] && grep -q '"governance"' package.json 2>/dev/null && $RUN governance || true
```

### 3.4 自审 diff（取代云端自动 review）

```bash
git diff --stat "origin/$BASE"
git diff "origin/$BASE"
```

读完 diff，**逐条**对照红线清单自查。优先读项目清单，缺失则用通用兜底：

```bash
cat .claude/pr-checklist.md 2>/dev/null || echo "（无项目清单，使用通用兜底）"
```

**通用兜底红线**（任何项目都适用）：

| 红线 | 自查问题 |
|------|---------|
| 密钥泄漏 | diff 是否含 API key / token / 密码 / `.env` 实值？ |
| 调试残留 | 是否留下 `console.log` / `print` / 临时断点 / 注释掉的死代码？ |
| 输入校验 | 新增的用户输入/外部数据入口是否做了边界校验？ |
| 破坏性变更 | 是否改了公共 API/接口签名/DB schema 却没同步调用方与迁移？ |
| 测试 | 新逻辑是否有对应测试？是否误删/跳过了既有测试？ |
| 大文件/路径 | 是否引入 >50MB 文件？是否硬编码绝对路径？ |
| 验证证据 | 声称"完成"是否有运行证据（测试通过 / 接口 200 / 构建成功）？ |

**输出格式**（贴对话，便于复核）：

```
🔍 自审清单
- 密钥泄漏 ✅
- 调试残留 ✅
- 破坏性变更 ⚠️ <说明>
- 验证证据 ✅ <证据摘要>
...
结论：可推送 / 需先修 <项>
```

发现问题 → 当场修 → 重跑 3.2/3.3/3.4 → 全 ✅ 才进步骤 4。

> 需要「第二意见」时（架构变动 / 跨模块重构 / 可疑口径）才追加 `/codex review` 或
> `@claude review` 等付费复审，**常规变更不滥用**。

---

## 4. 提交 + 推送

```bash
git add .
git commit -m "<生成的 commit message>"
git push origin "$(git branch --show-current)"
```

> 若当前在 `$BASE` 主干上：先切 feature 分支再提交（`feature/*` / `bugfix/*` / `hotfix/*`），禁止直推主干。

---

## 5. 创建 PR

```bash
gh pr create --title "<与 commit subject 一致，≤60 字符>" --body "$(cat <<'EOF'
## 变更说明
[目的与内容]

## 变更类型
- [ ] 新功能  - [ ] Bug 修复  - [ ] 重构  - [ ] 文档

## 测试
- [ ] 单元测试通过  - [ ] 手动验证完成

## 相关 Issue
Closes #
EOF
)" --base "$BASE"
```

> **非 GitHub 平台**：GitLab 用 `glab mr create`；Bitbucket / Gitea 用各自 CLI 或 Web。
> 其余步骤（护栏 / 自审 / 自进化）平台无关，照用。

---

## 6. 回到主干（防后续任务在旧分支操作）

```bash
CUR="$(git branch --show-current)"
git checkout "$BASE" && git pull --rebase origin "$BASE"
echo "如需改 PR：git checkout $CUR"
```

---

## 7. Post-PR 验证 + 自进化（GitHub）

```bash
gh pr view <PR> --json mergeable --jq '.mergeable'
BR="$CUR"
gh api "repos/{owner}/{repo}/actions/runs?branch=$BR&per_page=5" \
  --jq '.workflow_runs[] | "\(.name) | \(.status) | \(.conclusion)"'
```

> Token 若无 `checks:read` 权限，`gh pr checks` 会 403——改用上面的 `actions/runs` API。

**判定**：
- `MERGEABLE` + 全部 `success/skipped` → 报告 PR URL，结束
- `CONFLICTING` → 回 §3.1 rebase 后重推
- 任一 `failure` → 读日志 → 修 → 追加 commit

**自进化（关键）**：每次踩坑后记录到 `.claude/workflow/pr-evolution.md`：

```markdown
## YYYY-MM-DD <失败现象一句话>
- 根因：
- 修复：
- 预防：<下次 §3 哪一步要先检查>
```

**进化铁律**：同类失败 **2 次** → 必须从 prompt 升级为自动检查（git hook 或 governance 脚本），不再依赖人/AI 记得。

---

## 接入清单（项目侧一次性配置）

把本 skill 落到某项目时，项目只需提供（全部可选，缺则走通用兜底）：

| 挂载点 | 路径 | 作用 |
|--------|------|------|
| 红线自审清单 | `.claude/pr-checklist.md` | §3.4 项目专属红线（指标注册表 / SQL 安全 / 领域口径…） |
| 冲突检测钩子 | `scripts/check-write-conflict.mjs` | §3.2 多 Agent 协作 / 索引跨区写入检测 |
| 治理校验钩子 | `scripts/check-governance.mjs` 或 `package.json` 的 `governance` 脚本 | §3.3 一致性 / 单一事实源校验 |
| 自进化日志 | `.claude/workflow/pr-evolution.md` | §0.3 / §7 失败模式沉淀 |

**薄 wrapper 写法**（项目级 `.claude/commands/<project>-commit-push-pr.md`）：
> 「执行 commit-push-pr-core 流程。本项目红线见 `.claude/pr-checklist.md`，
> 钩子见 `scripts/check-*.mjs`。」——不重复骨架，只声明挂载点。
