# ADR-001：统一技能路径解析器，消除硬编码安装路径

- **状态**：Accepted（2026-06-08）
- **路线图阶段**：P0（立即）
- **关联**：[ARCHITECTURE.md](../ARCHITECTURE.md) · [ADR-002](./ADR-002-layering-no-lateral-deps.md) · [ADR-005](./ADR-005-dependency-declaration.md)

## 背景（Context）

跨技能复用通过运行时 `sys.path` 注入实现，路径**硬编码**为安装位置：

```python
# diagnose-org-weekly/cli.py
SHELL_ROOT = Path.home() / ".claude" / "skills" / "chexian-report-shell"
sys.path.insert(0, str(SHELL_ROOT))
from lib import render_page, ...
```

同样的硬编码散落在 `diagnose-period-trend/lib/_dhr_bootstrap.py`、`render.py`、`query.py` 以及 `diagnose-org-weekly` 的 `render_v1/v3/v4_org.py`（后者还指向 `diagnose-period-trend/lib`）。

**问题**：
1. README 提供两种安装方式——`npx skills add -g`（落到 `~/.claude/skills` 或 `~/.agents`）与 `git clone … ~/.claude/plugins/alongor666-skills`。硬编码只认 `~/.claude/skills`，**走 git clone 方式安装时全部 `diagnose-*` 崩溃**（找不到基座）。
2. 对 `~/.agents/skills`、软链直连等位置均不鲁棒。
3. 重命名/移动基座（如 2026-05-17 `diagnose-html-render → chexian-report-shell`）需全局改 path 字符串。

## 决策（Decision）

在基座 `chexian-report-shell` 提供一个零依赖的路径解析器 `skill_path(name)` / `skill_lib(name)`，**按优先级探测**候选根，返回第一个存在者：

1. `$CLAUDE_SKILLS_DIR`（环境变量，显式覆盖，最高优先——运维旋钮）
2. 相对调用文件回溯到 `skills/` 取兄弟（`resolve()` 穿透软链，覆盖软链直连 / 同根安装）
3. 已知安装根兜底：`~/.claude/skills` → `~/.claude/plugins/alongor666-skills/skills` → `~/.agents/skills`

**实现说明（鸡生蛋约束）**：能直接 import 解析器的调用点（如 `diagnose-org-weekly/render_v*_org.py` 这类「二跳点」，运行时基座已在 `sys.path`）一律改调 `skill_lib(...)`；而「自举点」（本身负责定位基座，import 解析器前无从加载）只能内联同款回溯逻辑，按技能各收敛到一处（如 `diagnose-loss-development/lib/_shell.py`、`diagnose-period-trend/lib/_dhr_bootstrap.py`）。路径探测因此从散落 10 处收敛到 ~4 个集中点 + 解析器。

**兼容性**：兄弟回溯优先于旧硬编码（短路，非平级兜底）；在 sync-skills「软链=消费态」模型下解析目标与旧行为一致，故快乐路径无感知变化。但当工作树兄弟与已安装版本内容不同时解析目标会变——因此不宣称严格「零行为变化」。内联兜底改为惰性求值（仅回溯未命中才碰 `Path.home()`），HOME 不可解析时安全降级为 `FileNotFoundError`。

## 后果（Consequences）

### 正面
- 三种安装方式（npx / git clone / 软链直连）都能找到依赖。
- 重命名/移动只改解析器一处（配合 ADR-005 的声明）。
- 解析逻辑集中在基座，杜绝散落复制。

### 负面 / 代价
- 引入一个被所有 `diagnose-*` 依赖的新公共函数（但它本就该集中在基座）。
- 解析器自身成为关键路径，需纳入基座测试（见 ADR-004）。

## 备选方案（Alternatives Considered）

- **Python 包 + `pip install -e`**：弃。违反"零新增运行时依赖 / 低运维"首要约束，且与 Claude Code 技能的平铺安装模型不契合。
- **各技能各自复制路径探测逻辑**：弃。又是散落耦合，重命名成本照旧。
- **维持现状**：弃。git clone 安装崩溃是已确认的可复现缺陷。
