# ADR-004：复用枢纽的测试与版本契约

- **状态**：Accepted（2026-06-08）
- **路线图阶段**：P1（短期）
- **关联**：[ARCHITECTURE.md](../ARCHITECTURE.md) · [ADR-001](./ADR-001-skill-path-resolver.md) · [ADR-002](./ADR-002-layering-no-lateral-deps.md)

## 背景（Context）

3 个 L0 基座是复用枢纽，其变更会同时牵动整簇：

- `chexian-report-shell` → 3 个 `diagnose-*`
- `xcl-html2pdf` → `company-vortex-card` + 全部报告产物
- `commit-push-pr-core` → 各项目薄 wrapper

当前 19 个技能中**仅 `chexian-report-shell` 有 `tests/` 目录**。枢纽缺乏回归网时，一次内部重构就可能静默打挂多个下游。

## 决策（Decision）

1. **枢纽硬约束**：L0 三基座的**对外 API** 变更前必须过回归测试。
   - `chexian-report-shell/lib`：`render_page` / `light`（亮灯）/ `labels`（客户标签 SSOT）/ `time_windows` / `queries`，以及 ADR-001 新增的 `skill_path`。
   - `xcl-html2pdf`：`driver.mjs` 填充率/溢出/页数验收（已具备）。
   - `commit-push-pr-core`：跨项目护栏（大文件拦截、unrelated-histories、push 后回主干）。
2. **版本契约**：枢纽对外 API 的破坏性变更须升 minor 以上版本，并在变更说明中列出受影响的下游技能清单。
3. **业务脚本测试按风险补**：优先纯逻辑脚本（如 `extract-backlog-governance/governance_stats.py`）；**不强求 80% 覆盖**——务实于单人维护，避免为指标而测。

## 后果（Consequences）

### 正面
- 枢纽稳定性有回归网，重构有信心。
- 版本号 + 影响清单让下游升级可预期。

### 负面 / 代价
- 基座迭代略增测试成本（`report-shell` 已部分具备，增量可控）。

## 备选方案（Alternatives Considered）

- **全仓强制 80% 覆盖**：弃。违反"低运维"约束，对编排型/提示型技能（无可测纯逻辑）意义不大。
- **完全不设测试约束**：弃。枢纽单点已确认，无网重构风险过高。
