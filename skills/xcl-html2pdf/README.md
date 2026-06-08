# xcl-html2pdf · HTML → 印刷级 PDF / 演示级 PPT 基座

把任意 HTML 报告做成**屏幕横向一屏一页、导出一页一张**的印刷 / 演示级文档。分离式架构：版面机制 + 视觉皮肤 + 你的内容，套标准 class 即得统一的「中国国家地理风 / 经营仪表盘风」视觉。

> 完整的版式 / 皮肤选择规则、组件语汇、实战坑（Gotchas）、Troubleshooting 见 [`SKILL.md`](./SKILL.md)。本 README 只讲快速上手、依赖、产物。

## 先决条件（依赖）

本技能**不依赖任何其它技能**（无 `requires_skills`），只依赖运行环境：

| 依赖 | 要求 | 说明 |
|---|---|---|
| **Node.js** | ≥ 21 | 内置全局 `WebSocket` / `fetch`（driver 零 npm 依赖）。实测 v22.16.0 |
| **系统 Chrome / Chromium** | 已安装 | 走 CDP 协议，无需下载 chromium。macOS 默认路径已内置；其它平台 `export CHROME=/path/to/chrome` |

## 快速上手

**0. 先定版式**（用户没明说默认 **PPT**）：PPT（16:9，大字号，适合屏幕 / 投影）或 PDF（A4，密排，适合打印 / 归档）。

```bash
# 1. 复制对应套件到工作目录（*-deck.css / report-skin.css / deck*.js 等勿改）
#    PPT·国家地理风（默认）：skeleton-16x9.html + deck-16x9.css + report-skin.css + skin-16x9.css + deck-16x9.js
#    PPT·经营仪表盘风：skeleton-dashboard-16x9.html + deck-16x9.css + report-skin-dashboard.css + deck-16x9.js
#    PDF：skeleton.html + page-deck.css + report-skin.css + deck.js

# 2. 把骨架每个 <section class="page"> 换成你的内容，套标准 class（sec-head / table.data / verdict ...）

# 3. 反复跑 driver 验收到全 PASS（同一 driver，画幅无关）
node driver.mjs your.html 10 --open          # 全 PASS 后自动用默认浏览器打开预览

# 4. 分发前打包成自包含单文件（治跨平台「文字错位 + 翻不动」）
node bundle.mjs your.html                     # → your.standalone.html（内联 css/js，发这一个即可）
node bundle.mjs your.html out.html --webfont  # 额外内联思源黑/宋，跨平台像素级一致
```

## 验收 driver

```bash
# 用法：node driver.mjs <html> [期望页数] [--min 80] [--max 100] [--pdf out.pdf] [--open]
node driver.mjs assets/skeleton-16x9.html 4   # 自启 http server + 系统 Chrome（CDP），实测每页填充率/溢出/真实页数
```

退出码：`0` 全达标 / `1` 有页不达标或页数不符 / `2` 运行错误 —— 可直接接 CI。

**铁律**：每页填充率 80–100%、零溢出、内容不跨页。可用高（填充率分母）：PDF ≈ 1005px（A4），PPT ≈ 604px（16:9）——PPT 每页内容量约为 PDF 的六成。

## 产物

| 形态 | 文件 | 说明 |
|---|---|---|
| 开发态（多文件） | `your.html` + 外链 css/js | 便于改皮肤 / 机制；**勿单独分发**（外链相对路径，换电脑会 404 → 文字错位 + 翻不动） |
| 分发态（单文件） | `your.standalone.html` | `bundle.mjs` 内联全部 css/js；Edge / Chrome / Safari · PC 与手机一致显示并翻页（方向键 + 触摸滑动 + 浮动 ‹ › 箭头 + 序号条） |
| 导出 PDF | `out.pdf` | `driver.mjs --pdf out.pdf` 或浏览器 `Cmd/Ctrl+P`（**取消页眉页脚**）→ 一页一张 |

> 涡旋诊断专属组件（stage / triad / shape / vortex）不在本基座，见 company-vortex-card。
