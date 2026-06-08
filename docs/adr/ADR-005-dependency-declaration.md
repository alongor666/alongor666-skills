# ADR-005：依赖声明与文档模板约定

- **状态**：Accepted（2026-06-08）
- **路线图阶段**：P2（持续）
- **关联**：[ARCHITECTURE.md](../ARCHITECTURE.md) · [ADR-001](./ADR-001-skill-path-resolver.md)

## 背景（Context）

- 跨技能依赖只存在于散落的 `sys.path` 字符串里，**无显式声明**——依赖图不可读，新人/AI 无法快速判断"动这个会影响谁"。
- 重资产技能（`diagnose-*`、`xcl-html2pdf`）缺独立 README，仅靠 SKILL.md 自述。

## 决策（Decision）

1. **依赖声明（给人读，不引入加载器）**：有跨技能依赖的技能，在 SKILL.md frontmatter 显式声明：
   ```yaml
   requires_skills:
     - chexian-report-shell   # 渲染基础设施
   ```
   解析仍由 ADR-001 的 `skill_path()` 在运行时完成；`requires_skills` 只是**可读的依赖契约**，不新增机制。
2. **重资产补 README**：`diagnose-org-weekly` / `diagnose-period-trend` / `diagnose-loss-development` / `xcl-html2pdf` 各补一份独立 README（快速上手 + 依赖 + 产物示例），降低复用门槛。
3. **轻资产不强制**：单文件编排型技能（如 `rewrite-conclusion`、`chexian-pricing-decision`）SKILL.md 已足够，不强加 README。

## 后果（Consequences）

### 正面
- 依赖图可读、可审计（配合未来的依赖巡检）。
- 重资产技能复用门槛降低。

### 负面 / 代价
- 轻微文档维护成本（增量、非一次性）。
- `requires_skills` 与实际 `sys.path` 调用需保持一致——可由 ADR-004 的测试或一次性巡检校验。

## 备选方案（Alternatives Considered）

- **引入声明式依赖加载器**（读 `requires_skills` 自动注入 path）：弃。属过度工程化；声明给人读、解析靠 ADR-001 解析器，两者解耦更简单。
- **全仓强制 README**：弃。编排型轻技能 README 会与 SKILL.md 重复。
