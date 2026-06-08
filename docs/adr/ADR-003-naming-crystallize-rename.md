# ADR-003：命名规范 + `crystallize-skill` 正名

- **状态**：Accepted（2026-06-08）
- **路线图阶段**：P0（立即）
- **关联**：[ARCHITECTURE.md](../ARCHITECTURE.md) · [ADR-001](./ADR-001-skill-path-resolver.md)

## 背景（Context）

- 业务簇前缀清晰：`chexian-*`（车险）/ `diagnose-*`（诊断报告）/ `company-vortex*`（上市公司）。
- 6 个工程通用工具命名分散、无统一前缀（`commit-push-pr-core` / `cleanup-worktrees` / `sync-skills` / `extract-backlog-governance` / `ui-redesign` / `chexian-crystallize-skill`）。
- **`chexian-crystallize-skill` 前缀误导**：它带 `chexian`（车险）前缀，实为"把任意重复流程固化为可复用 skill"的**通用元工具**，与车险毫无关系。

## 决策（Decision）

1. **命名约定**：
   - 领域技能用领域前缀（`chexian-*` / `diagnose-*` / `company-vortex*`）。
   - **项目无关通用工具不强加统一前缀**——保持 `cleanup-worktrees` 等现状，靠 README 分组归类即可。**不为统一而统一**（避免过度工程化）。
2. **正名**：`chexian-crystallize-skill` → **`crystallize-skill`**，归入工程治理 / 通用工具簇。

## 后果（Consequences）

### 正面
- 消除唯一一处实质性命名误导，技能名与职责一致。
- 明确"领域前缀 vs 通用工具无前缀"的约定，新技能命名有依据。

### 负面 / 代价
- 重命名技能目录需同步：`sync-skills` 软链、`MEMORY.md`/文档中的引用、README 表格。
- 借 ADR-001 解析器，跨技能引用的重命名成本显著下降（路径探测从散落 10 处收敛到二跳点调解析器 + 各技能集中片段，共 ~4 处）；本技能当前无被其它技能 import，影响面小。

## 备选方案（Alternatives Considered）

- **给全部 6 个工程工具加统一前缀（如 `gx-*` / `dev-*`）**：弃。属为统一而统一，破坏已被记忆/文档引用的稳定名，收益低于成本。
- **保留 `chexian-crystallize-skill`**：弃。前缀误导会让人/AI 误判其领域归属。
