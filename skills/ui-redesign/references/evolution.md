# 自进化协议（Phase D）

> 让本 skill 越用越准。每次重做落地后必填 `retro.md`，并把**通用经验回写仓库**。核心归因问题：**这次不顺，是不是因为给 Claude Design 的信息/prompt 不到位？** 是 → 改进简报/context-spec；否 → 改进发现/落地环节。

## 1. retro.md 模板（放专项文件夹，每次一份）

```markdown
# 复盘 — 〈模块〉 〈日期〉

## 结果
- 备料→Claude Design→落地 整体顺畅度：〈1-5〉
- Claude Design 出稿可用度：〈1-5；几轮收敛〉

## Claude Design 哪里没达预期
- 〈现象：如"加了渐变""字体退回 Inter""把小计行删了""率值带了2位小数"〉
  - 归因：□ 简报没写清 / 写漏  □ context-spec 缺这条  □ 模型默认惰性  □ 落地阶段我改坏
  - 下次改进：〈具体补哪句 context / 改哪段措辞 / 加哪条黑名单〉

## 发现阶段问题
- 〈如：没找到 design tokens 真实路径 / 漏了某交互〉→ 改进：〈…〉

## 落地阶段问题
- 〈如：某交互回归 / 某验收项漏核〉→ 改进：〈…〉

## 分流结论
- 通用经验（任何项目适用）→ 回写本 skill：〈列具体文件+改动〉
- 项目专属经验 → 记到本项目笔记：〈…〉
```

## 2. 回写规则（改在仓库·装到本地·本地只读）

判定经验**通用性**：
- **通用**（与具体项目无关，如"Claude Design 默认爱加渐变需提前禁""简报必须显式写死率值小数位""数据密集型页要声明非营销页"）→ 编辑本 skill 仓库 clone 的对应文件：
  - 模型行为/最佳实践 → `references/claude-design-context-spec.md`
  - 简报缺项 → `references/design-brief-template.md`
  - 发现盲区 → `references/discovery-playbook.md`
  - 验收漏洞 → `references/acceptance-criteria.md`
  - 流程本身 → `SKILL.md`
  然后：
  ```bash
  cd 〈repo clone，通常 ~/alongor666-skills〉
  git add skills/ui-redesign && git commit -m "evolve(ui-redesign): 〈一句话经验〉" && git push
  npx skills add alongor666/alongor666-skills -g --skill ui-redesign -y   # 重装软链生效
  ```
- **项目专属**（依赖某项目数据/路径/口径）→ 写进该项目 `design-handoff/` 或项目笔记，**不污染通用 skill**。

## 3. 触发式进化（不拖延）

- 同类问题**重复出现 ≥2 次** → 必须当次回写，不能只记 retro。
- 每次回写后在 commit message 用 `evolve(ui-redesign):` 前缀，便于回看本 skill 的进化轨迹。
- 版本：实质性能力变更时 bump `SKILL.md` frontmatter `version`。

## 4. 边界
- 自进化只改"如何更好地指导设计与落地",不改项目业务口径/指标定义。
- 回写前先读现有 reference,避免重复堆叠;能改一句不另起一段。
