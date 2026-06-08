---
name: crystallize-skill
description: >-
  把重复性流程 / 动作沉淀（固化）为一个可复用 skill 的元流程编排。
  当用户说"沉淀成 skill"、"把这个流程做成 skill"、"固化成技能"、"封装成 skill"、
  "crystallize skill"，或当某操作已重复多次、明显值得固化为常态资产时使用。
  自动完成：判归属（Git 共享仓库 vs 项目级）→ 查重叠 → 写在唯一事实源 →
  发布安装 → 登记。面向 AI-Agent native 用户：用户只下一句指令，纪律由本 skill 自动执行。
user_invocable: true
version: "1.0.0"
---

# crystallize-skill：把重复流程沉淀为可复用 skill

用户是 AI-Agent native（不写代码、不亲自维护文件），但会发现重复流程并下指令"沉淀成 skill"。本 skill 是 AI 必须自动执行的**五步流水线**，把维护纪律绑定到动作上，而不是靠 AI 每次自觉。

## 0. 心智模型（铁律）

> **改在仓库 · 装到本地 · 本地只读**

每个 skill 二选一身份：
- **原创态** = 住 GitHub 仓库 `alongor666/alongor666-skills`（✅git，唯一权威源），在仓库 clone 里编辑，git 追溯。
- **消费态** = 住本地软链（`~/.claude/skills/<x>` → `~/.agents/skills/<x>`），**永不在本地编辑**，`skills update` 拉新。

拓扑：① GitHub 仓库 → ② `~/.agents/skills/`（CLI 安装根）→ ③ `~/.claude/skills/`（软链入口；软链=消费态，实体目录=本地原创未发布）。项目专属、不跨项目复用的 skill 放 ④ `<project>/.claude/skills/*.md`（随项目 git）。

## 1. 流水线（AI 自动执行，用户全程不碰文件）

### Step 1 · 判归属（默认值能判就判，仅真歧义问用户一句）
- 跨项目 / 跨会话复用 → **仓库①**（原创态，本 skill 主路径）。
- 只服务单一项目、依赖该项目数据 / 路径 → **项目④** 的 `.claude/skills/<name>.md`。
- 用户已明示"Git 共享 / 仓库 / 跨项目" → 直接走①，不再问。

### Step 2 · 查重叠（防混乱核心，禁止新建重复）
- 先扫描现有 skill 的 `description`（Claude Code 已把全部 skill 描述注入 system-reminder，直接读，不必逐个 grep）。
- 命中相近 skill → 并入它 / 走路由器模式（一域一 router + N 窄子命令），**不新建重复**。
- 与基座类（如 `writing-skills` 写作规范、`commit-push-pr-core` 提交基座）有关 → 复用 / import，不复制其骨架。

### Step 3 · 写在唯一事实源
- 仓库 skill：在仓库 clone 写 `skills/<name>/SKILL.md`。质量规范（frontmatter / 结构 / 触发语）**调用 `writing-skills` skill** 把关，不自行随意发挥。
- 项目 skill：写 `<project>/.claude/skills/<name>.md`。
- frontmatter 必含 `name`（与目录同名）、`description`（含 CSO 第三人称触发语："Use when / 当用户说 …"）；推荐 `version`、`user_invocable`。

### Step 4 · 发布 + 安装（仓库 skill 路径）
```bash
# 在仓库 clone 内
git add skills/<name> && git commit -m "feat(skill): 新增 <name>" && git push
# 装成本地软链（若本地有同名实体目录，先 rm -rf 再装）
npx skills add alongor666/alongor666-skills -g --skill <name> -y
```
- ⚠️ **逗号批量 `--skill a,b,c` 静默失败**——多个 skill 必须 `for` 循环逐个单装。
- 验证落成软链：`[ -L ~/.claude/skills/<name> ] && echo OK`。

### Step 5 · 登记
- 更新本项目 `.claude/rules/skills-map.md` 的"本项目用法"行（若与本项目相关）。
- 写 / 更新 memory（维护模型见 `project_skills_maintenance_model`）。

## 2. 防混乱清单（每条 = 一个制造新乱的动作 + 护栏）

| 禁止动作 | 后果 | 护栏 |
|---|---|---|
| 在本地 ③/② 直接改 skill | `skills update` 覆盖丢失 | 软链=只读 |
| 在 ③ 新建实体目录 skill（绕过仓库） | 重现"四不像"无溯源 | 原创一律进①或④ |
| 不查重就新建 | 重复 / 口径漂移 | Step 2 先扫描 + 路由器 |
| 改完忘 push | 别的机器 / 会话拿旧版 | push 是 Step 4 固定步 |
| 改 skill 不更 skills-map / 文档 | SSOT 漂移 | Step 5 编辑即同步 |
| 逗号批量 `--skill a,b,c` | 静默失败 | 循环单装 |

## 3. 查询命令（不靠记忆）

```bash
npx skills add alongor666/alongor666-skills -g -l   # 仓库已发布哪些
npx skills list -g                                  # 本地装了哪些 + 来源
# 本地独有待发布 = ③ 的实体目录名 ∉ 上面发布清单
```

## 4. 不做什么（范围纪律）
- ❌ 不替代 `writing-skills`：SKILL.md 的写作质量交给它，本 skill 只管编排"判归属→发布→安装→登记"。
- ❌ 不给 `~/.claude/skills` / `~/.agents/skills` 做 git init（运行时目录是软链 + 派生副本，git 化只制造噪音；追溯靠仓库①的 git）。
- ❌ 不过度抽象：项目专属、强依赖单项目数据的流程，留在项目④，不为"共享"强行上提到仓库。
