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

## 5. 视觉对齐
- [ ] 落地页与已批准的 Claude Design 导出稿，在**结构 / 信息层级 / 关键区块**上一致（逐块比对，可截图对照存 assets/）。
- [ ] 响应式断点行为符合预期（若简报含响应式）。

## 6. 提交前
- [ ] 走项目偏好提交流程；通过项目治理/校验命令（若有）。
- [ ] 专项文件夹内 `acceptance.md` 已全勾、`retro.md` 已填（见 evolution.md）。
