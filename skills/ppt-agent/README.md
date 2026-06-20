# ppt-agent

一个 Claude Code / Codex 的 **orchestrator skill**，把三个互补的 PPT skill 编排成一条工作流：

```
原始材料
  → humanize-ppt（出叙事 brief）
  → 路由判断（杂志风 / 学术风）
  → guizang-ppt-skill 或 academic-pptx-skill（渲染）
  → 演讲体检
```

## 为什么用 orchestrator 而不是合并？

三个原 skill 都在独立维护、各自更新（尤其 `humanize-ppt` 迭代很快）。fork 合并等于背维护债。Orchestrator 让 Agent 当调度员，三个 skill 当工具，跟 Claude Code 官方 skill 体系一致。

## 安装

把下面整段发给 Claude Code / Codex：

```
帮我装 ppt-agent 工作流，请依次执行：

mkdir -p ~/.claude/skills
git clone https://github.com/LearnPrompt/humanize-ppt.git ~/.claude/skills/humanize-ppt
git clone https://github.com/op7418/guizang-ppt-skill.git ~/.claude/skills/guizang-ppt-skill
git clone https://github.com/Gabberflast/academic-pptx-skill.git ~/.claude/skills/academic-pptx-skill

然后把我提供的 ppt-agent/SKILL.md 放到 ~/.claude/skills/ppt-agent/SKILL.md

验证：ls ~/.claude/skills/ 应该看到 4 个目录。
```

## 触发

任何"我要做 PPT/演讲/分享/答辩"类语句都会触发。

试用：

```
用 ppt-agent 帮我做一份 30 分钟的内部技术分享：
主题：我们如何从 Webpack 迁移到 Rspack
听众：同公司前端 + 全栈
素材：构建时间对比图、bundle 体积截图、配置 diff
```

预期流程：
1. humanize-ppt 跑 6 题验收，让你确认 audience / state / tension
2. 没有学术关键词 → 默认走 guizang
3. 输出单文件 HTML
4. 跑演讲体检，flag 哪页"只能看不能讲"

## 路由规则

默认 **guizang**。命中以下任一信号切 **academic**：

- 关键词：学术 / academic / 论文 / 答辩 / thesis / seminar / conference / grant / 评审 / 监管 / 合规 / SOX / 审计 / 董事会
- 受众包含：教授 / 评审委员 / 监管 / 审计 / 董事
- 必须输出 `.pptx`
- 需要引用规范

模糊场景 Agent 会问一次。

## 自定义

要改路由规则、加新渲染器、改演讲体检逻辑——直接改 `SKILL.md`。这就是整个 skill 的全部代码，没有别的状态。

加新渲染器（比如 remotion 视频）的步骤：

1. 在「Required upstream skills」加一项
2. 在「Step 2 — Route」加触发信号
3. 在「Step 3 — Render」加映射表

## 文件结构

```
ppt-agent/
├── SKILL.md      ← 路由 / 契约 / 失败模式（Agent 读这个）
└── README.md     ← 给你看的（本文件）
```

## License

MIT
