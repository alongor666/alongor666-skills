---
name: ui-redesign
description: 任意项目前端页面/模块的"视觉重做"编排，配合 Claude Design（claude.ai/design）。AI 自动发现该项目的技术栈与设计系统（不硬编码），把当前页还原成 standalone HTML + 写高命中率设计简报，存进专项文件夹供上传；用户在 Claude Design 操作并导出后，AI 落地回组件并按确定性验收标准检查；每次运行复盘并把通用经验回写本 skill（自进化）。Use when 用户说"重新设计/重做这个页面/redesign/换个设计/用 Claude Design 改 XX 页/视觉翻新"某个前端页面或模块时。
version: 2.1.0
user_invocable: true
---

# ui-redesign：页面/模块视觉重做编排（Claude Design 协作）

把"某个页面想重新设计"跑成稳定闭环：**发现 → 备料 → Claude Design（用户操作）→ 落地 → 复盘进化**。本 skill **项目无关**：技术栈、设计系统、提交流程等项目特色一律**按指令现场发现**，不硬编码（见 §1）。

## 0. 三条不变量（每次自带）

1. **Claude Design = `claude.ai/design` 是 Anthropic 独立网页产品，由用户本人在浏览器操作，AI 无法代为驱动**（需用户登录态；该产品/目标站点常被运行环境 egress 白名单挡，云端 `curl`/CDP 会 403）。AI 只负责"备好料"+"落地产出"，中间交给用户。它吃什么 context 才高效、接受/导出什么 → `references/claude-design-context-spec.md`。
2. **设计系统是发现来的，不是假设来的**：动手前必须先发现并读该项目自己的设计 tokens / 规范（§1）。禁止凭空发明色彩、字体、间距语言。
3. **重做只动展示层**：保留全部数据维度与交互（下钻/联动/排序/筛选/Tab/分页…）；不碰指标公式/阈值/数据口径。

## 1. Phase 0 · 发现（AI，零硬编码）

按指令现场探测项目特色，产出一份《项目设计上下文》供后续所有阶段引用：

- **技术栈**：读 `package.json`/`pyproject.toml`/`go.mod` 等 → 框架(React/Vue/Svelte/Next…)、CSS 方案(Tailwind/CSS-Modules/styled-components/UnoCSS)、组件库、构建/测试命令。
- **设计系统 SSOT**：按优先级找——`DESIGN.md`/`STYLEGUIDE*`/`design-system*` 文档；`tailwind.config.*`；design tokens(`tokens.*`/`theme.*`/`*/styles/*`)；`.claude/rules/*`、`CLAUDE.md`/`AGENTS.md`/`.cursorrules` 里的 UI 约束。提取：语义色板、中性色阶、字体栈、组件预设(card/button/table)、数值/排版规则、暗色模式策略。
- **目标模块代码**：用搜索 agent grep 关键词分组返回——页面、子组件、hooks/types、API/数据层、后端路由/查询(若有)。**逐一记录每个交互**(下钻/联动/排序/筛选/Tab) 形成"交互清单",作 Phase C/验收的对照基线。
- **提交流程**：发现项目偏好的提交/PR 方式(是否有 `*-commit-push-pr` skill / CONTRIBUTING / PR 模板)。

> 探测细则与各栈识别表见 `references/discovery-playbook.md`。发现不到设计系统时——明确告诉用户"未发现设计系统,将用通用克制风格 + 你给的参考",不要静默编造。

## 2. Phase A · 备料（AI → 专项文件夹）

**为每次重做建一个专项文件夹**(便于上传、留档、复盘),默认路径:
```
<project>/design-handoff/<module>-<YYYYMMDD>/
├── README.md          # 索引 + 给用户的上传操作指引（Claude Design 怎么用这些料）
├── current-page.html  # 当前页的 standalone 忠实还原（Claude Design 的起点）
├── design-brief.md    # 粘进 Claude Design 的设计简报
├── acceptance.md      # 本次确定性验收标准（落地后逐条核）
├── assets/            # 截图/参考图/competitor（可选）
└── retro.md           # Phase D 复盘填写（自进化输入，初始为模板）
```
- 日期取 `date +%Y%m%d`。该文件夹是否纳入 git 由项目决定:默认在 README 提示"可 gitignore",但**文件留在磁盘**以便随时重新上传。
- `current-page.html`:用 Tailwind CDN(或还原项目实际 CSS 方案)+ 把发现到的 tokens 写进配置 + 真实业务样例数据,忠实复刻布局/列/状态(hover/选中/展开)。生产站可直连时(如本地终端无 egress 墙)可改用 CDP 截真图存 `assets/`。
- `design-brief.md`:套 `references/design-brief-template.md`,填入 Phase 0 发现的项目上下文。简报必须满足 `references/claude-design-context-spec.md` 的 context 清单(受众/用例、逐维度方向、要避免的默认、必保交互、红线、交付物=standalone HTML)。
- 完成后**告诉用户文件夹路径**并给出"打开 claude.ai/design → 上传 current-page.html → 粘贴 design-brief.md → 导出 HTML 回这个文件夹"的指引。**不用 SendUserFile 发送**——材料留在专项文件夹。

## 3. Phase B · Claude Design（用户操作，AI 等待）

用户:① 打开 `https://claude.ai/design`(需 Pro/Max/Team/Enterprise) ② 上传 `current-page.html` 作起点(可选:链接代码仓库让它读真实组件、确认已继承组织设计系统,提高落地保真度) ③ 粘贴 `design-brief.md` ④ **内联批注**(组件级精改)+ **Chat**(结构级改/要 2-3 备选)+ 旋钮打磨 ⑤ 二选一交回:
- **A. 导出 standalone HTML** 存回专项文件夹(命名 `claude-design-export.html`)→ 走 Phase C 落地。**默认**。
- **B. Handoff to Claude Code** 直接把设计交接给 Claude Code → 仍按 Phase C 的设计系统纪律与验收落地,只是省了导出/回传。

## 4. Phase C · 落地（AI，用户回传导出稿后）

1. 读导出稿,对照改真实组件(页面 + 子组件 + 必要 hook/样式)。
2. **严格用 Phase 0 发现的设计系统常量**(项目怎么封装就怎么用,禁硬编码颜色/虚构类名)。
3. **保留 Phase 0 交互清单的每一项**——不为视觉牺牲任何数据维度或交互。
4. 跑 `acceptance.md` 全部确定性验收(见 §6),不过不算完成。
5. 用项目偏好的提交流程提 PR。

## 5. Phase D · 复盘进化（AI，自迭代核心）

> **前置**：Phase C 落地 + acceptance.md 全过 ≠ 流程结束。先经 Phase D-pre（对抗 review 闭环），再进复盘。

### 5.0 Phase D-pre · 对抗 review 闭环（codex / 第二意见 / 自查）

PR 提交后，对每一条 review 意见走 5 步 SOP（详见 `references/acceptance-criteria.md` §7）：
1. 抽 pattern → 2. 全仓 grep 同类 → 3. 修 → 4. **加静态闸**（governance grep / 单测 / 类型，三选一）→ 5. 复盘评论 + 显式 `@codex review`

**关键**：单次修复 ≠ 修了一类。无静态闸 → 下次还会犯。实战 4-5 轮 codex review 才 0 残留是常态，预留时间。

### 5.1 retro.md

review 清零后，填 `retro.md`(模板见 `references/evolution.md`)。至少记:
- 哪些简报段落 Claude Design **没理解/理解偏**;它的产出**哪里偏离了设计系统/交互/数据规范**。
- 哪些 review 意见暴露了**简报缺失**（如未列字段契约 → P2-1 整体达成永远 fallback）。
- 归因:**问题来自给 Claude Design 的信息/prompt** → 写清"下次该补什么 context、改哪句措辞";来自落地或发现阶段 → 记对应改进。
- **分流回写**:
  - 通用经验(任何项目都适用,如"简报必须显式写死率值小数位""Claude Design 默认爱加渐变,需提前禁") → **打开本 skill 仓库 clone 编辑对应 reference,push,重装**(改在仓库·装到本地·本地只读,见 §7),完成自进化。
  - 项目专属经验 → 写进该项目的 `design-handoff/` 或项目笔记。
- 触发式进化:发现同类问题**重复 ≥2 次** → 必须当次回写 skill,不拖延。

## 6. 确定性验收标准（落地的 PASS/FAIL，非主观）

逐条机器可核(命令按 Phase 0 发现的栈替换),全绿才算完成。完整清单+命令见 `references/acceptance-criteria.md`,核心:
- **构建零错**:项目 build/类型检查命令退出码 0。
- **零硬编码**:改动文件中无裸色值/裸颜色类(grep 命中数=0,颜色只经设计系统常量)。
- **交互齐全**:Phase 0 交互清单逐项在新组件中仍可用(逐条勾)。
- **格式合规**:数值/率值/金额格式符合项目规则(发现到的)。
- **数据通**:数据驱动页至少一个真实请求返回成功且非空。
- **视觉对齐**:落地页与已批准导出稿在结构/层级上一致(关键区块逐块比对)。

## 7. 维护铁律（本 skill 是共享 skill）

安装态是只读软链,**禁止本地原地改**。任何对本 skill 的修改(含 Phase D 自进化回写)走:
```
# 在仓库 clone（locate: 通常 ~/alongor666-skills）编辑 skills/ui-redesign/**
git add skills/ui-redesign && git commit -m "..." && git push
npx skills add alongor666/alongor666-skills -g --skill ui-redesign -y   # 重装软链
```
查重不新建、登记 SKILL_INDEX——遵循 `crystallize-skill` 流水线。

## 8. References
- `references/discovery-playbook.md` — Phase 0 各技术栈/设计系统探测细则
- `references/claude-design-context-spec.md` — Claude Design 吃什么 context 才高效 + 接受/导出能力 + 最佳实践
- `references/design-brief-template.md` — 设计简报填空模板
- `references/acceptance-criteria.md` — 确定性验收清单与命令
- `references/evolution.md` — retro.md 模板 + 自进化回写协议
