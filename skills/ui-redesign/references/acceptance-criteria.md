# 确定性验收标准（PASS/FAIL，非主观）

> 落地（Phase C）后逐条机器可核。命令用 Phase 0 发现的实际栈替换占位符。全绿才算完成；任一红停下修复。每次为本次重做生成一份 `acceptance.md` 放专项文件夹，勾选留痕。

## 1. 构建 / 类型 / Lint
- [ ] `〈build 命令〉` 退出码 0、零错误。
- [ ] `〈typecheck 命令〉`（若有）零错误。
- [ ] `〈lint 命令〉`（若有）无新增错误。

## 2. 零硬编码（设计系统纪律）
- [ ] 改动文件中**裸色值/裸颜色类命中数 = 0**。示例核法（按 CSS 方案调）：
  ```bash
  # Tailwind 项目：禁裸调色类（应走设计系统封装）
  git diff --name-only | grep -E '\.(tsx?|jsx?|vue|svelte)$' | xargs grep -nE \
    '(text|bg|border|ring|from|to|via)-(red|blue|green|gray|slate|zinc|yellow|amber|orange|rose|emerald|sky|indigo|purple)-[0-9]' && echo "❌ 命中裸颜色类" || echo "✅ 0 命中"
  # 通用：禁源码内裸 hex（应来自 tokens/变量）
  git diff | grep -nE '#[0-9a-fA-F]{3,6}\b' && echo "❌ 命中裸 hex" || echo "✅ 0 命中"
  ```
- [ ] 无虚构/未注册类名（按项目类名体系核）。

## 3. 交互齐全（不丢功能）
- [ ] 逐项核对 Phase 0《交互清单》——每个交互在新组件中仍可用：
  〈下钻/展开折叠 · 左右联动 · 列排序 · 筛选器 · Tab · 分页 · hover/选中态 · 键盘可达〉
- [ ] 全部数据维度仍在（与重做前列/维度数一致）。

## 4. 数据与格式
- [ ] 数据驱动页：至少一个真实请求返回 **HTTP 成功 + 非空**（贴出证据）。
- [ ] 数值/率值/金额/空值格式符合 Phase 0 发现的项目规则。
- [ ] 字段空值防护到位（不因 null 崩）。
- [ ] **单位流转审计**（强制）：每个使用格式化函数的位置，确认值的单位与函数期望一致。
  - 易踩雷：`formatPercent(已是百分比)` vs `formatAchievementRate(0-1 小数)` — 后者会再 ×100
  - 易踩雷：`formatPremiumWan(input=元)` vs `formatWanAdaptive(input=万元)` — 前者会再 ÷10000
  - 简单核法：对照 Phase A 简报里"后端字段契约速查表"，每条数据 tile 写一行注释"value unit = X, formatter expects Y"。
- [ ] **静态数据稿 / deck**（数字硬编码进 JS 数组的报告 / 盯盘，无后端）：所有数字进**唯一数据源数组**（每行一记录 + 一行合计），写**"列求和 = 合计"自洽脚本**，渲染前先全绿再谈视觉（一键抓转写错）。**禁止把灯色 / 状态字符串与数值混在同一位置数组**——明细行带灯色列、合计行不带会"索引漂移"（实战踩过 2 次：bulletRow `r[8]` vs `r[9]`、tableMatured `sum[6]` vs `sum[5]`）；优先**具名字段对象**取代位置数组。多页 16:9 数据 deck 的完整组件与契约见 xcl-html2pdf `references/dashboard-deck.md`。
- [ ] **接口断言**（数据驱动页强制）：用 jq/curl 对每个数据信号断言后端真实返回，不能只看 DOM。
  ```bash
  TOKEN=$(...)  # 项目登录获取
  curl -s '<API_URL>' -H "Authorization: Bearer $TOKEN" | jq '{
    tile1: (...|select(...) | {字段, 单位检查: (.字段 / 已知基准 * 100 | round)}),
    tile2: ...
  }'
  # DOM 看着"320%"和"3.2%"差 100 倍肉眼分不清，jq 数字一目了然。
  ```

## 5. 视觉对齐
- [ ] 落地页与已批准的 Claude Design 导出稿，在**结构 / 信息层级 / 关键区块**上一致（逐块比对，可截图对照存 assets/）。
- [ ] 响应式断点行为符合预期（若简报含响应式）。

## 6. 提交前
- [ ] 走项目偏好提交流程；通过项目治理/校验命令（若有）。
- [ ] 专项文件夹内 `acceptance.md` 已全勾、`retro.md` 已填（见 evolution.md）。

## 7. PR 后的 codex/对抗 review 处置（强制 — Phase D 同步）
> review 后第一轮发现的问题往往是冰山一角，**单次修复后必须按 5 步 SOP 加防回归措施**，否则下次还会犯（实战 4 轮才 0 残留的案例已证明）。

每条 review 意见走：
1. **抽 pattern** — 这条意见背后的"假设错了"是什么？记一句话。
2. **全仓 grep** — 同类 pattern 还有几处？
3. **修** — 修当前 + 同类全修
4. **加静态闸**（关键） — 项目 governance 加 grep 检查 / 加单元测试 / 加类型约束三选一。无静态闸=下次还会犯。
5. **复盘评论** — 在 PR 写明：根因 / 修复路径 / 全仓 grep 结果 / 静态闸位置 / 验收证据。然后**显式 @codex review**（codex 不会自动复审）。

`acceptance.md` 落地完成 ≠ 流程结束。要等 review 也清零，才进 Phase D 复盘。
