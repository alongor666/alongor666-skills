# ADR-002：三层 + 横切，禁止业务层横向 import

- **状态**：Accepted（2026-06-08）
- **路线图阶段**：P1（短期）
- **关联**：[ARCHITECTURE.md](../ARCHITECTURE.md) · [ADR-001](./ADR-001-skill-path-resolver.md)

## 背景（Context）

`diagnose-org-weekly` 的 `render_v1_org.py` / `render_v3_org.py` / `render_v4_org.py` 中：

```python
sys.path.insert(0, str(Path.home() / ".claude/skills/diagnose-period-trend/lib"))
```

即 **业务技能 `diagnose-org-weekly` 直接依赖另一个业务技能 `diagnose-period-trend` 的内部 lib**。这违反分层：业务层之间产生横向耦合边，卸载/重构 `period-trend` 会连带打挂 `org-weekly`，且 `period-trend/lib` 的内部实现变成了事实上的对外 API。

## 决策（Decision）

确立依赖规则：

- **L0 基础设施基座**：`chexian-report-shell` · `xcl-html2pdf` · `commit-push-pr-core`
- **L1 业务层**：`chexian-*` · `diagnose-*` · `company-vortex` · `rewrite-conclusion`
- **L2 编排层**：`chexian-ops-review` · `company-vortex-card`
- **横切通用工具**：不分层

规则：**L1 业务层只能向下依赖 L0 基座；禁止 L1 ↔ L1 横向 import。** L2 可依赖 L1/L0。

落地：把 `org-weekly` 实际复用的 `period-trend/lib` 代码（共享渲染/时间窗逻辑）**下沉到 `chexian-report-shell/lib`**——它本就是共享渲染基础设施。两个业务技能再各自从基座取（经 ADR-001 解析器）。

## 后果（Consequences）

### 正面
- 依赖图变成干净的星形（所有边指向 L0），无横向边。
- 卸载/重构任一业务技能不连带打挂他者。
- 共享逻辑归位到基座，强化既有 SSOT 实践。

### 负面 / 代价
- 一次性下沉迁移工作量；需回归 `org-weekly` 与 `period-trend` 两份报告产物。
- 下沉时须保持 `period-trend` 现有 API 兼容（可用 thin shim 过渡，与现有 `periods.py` shim 模式一致）。

## 备选方案（Alternatives Considered）

- **保持现状横向依赖**：弃。脆弱性已确认，且让业务技能内部 lib 沦为隐式公共 API。
- **把 period-trend 整体降为基座**：弃。它是面向用户的业务技能，不应整体降层；只下沉真正共享的部分。
