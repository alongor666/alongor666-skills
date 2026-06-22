# SVG 系统图配方库（深色仪表盘风）

> **铁律 L3**：每个节点必须带**文字标签** + **方向箭头**。禁止"无标签圆点"当装饰图——那等于没画图。
> 所有图用 CSS 变量取色（`var(--accent)` 电蓝 / `var(--accent2)` 青 / `var(--line)` 描边 / `var(--panel)` 卡底）。
> 文字用内置类 `.lbl`（11px mono 次要）/ `.lblb`（13px sans 加粗主要）；标签长就用 `text-anchor` 靠边放。

## 取色约定
- 主流程 / 当前节点：`var(--accent)`（电蓝）
- 闸 / 关键节点 / 箭头：`var(--accent2)`（青）
- 弱化 / 非本波 / 普通连线：`var(--dim)` / `var(--line)`
- 红线 / 缺陷：`var(--warn)` / `var(--p0)`

---

## 配方 1 · 同心双环（两层模型）

内环 = 基座闭环，外环 = 新增编排层。环上点数表达"几步/几段"，底部一行文字交代计数。

```html
<svg viewBox="0 0 320 300" width="100%" style="max-height:52vh">
  <circle cx="160" cy="150" r="128" fill="none" stroke="var(--accent)" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="3 5"/>
  <circle cx="160" cy="150" r="74" fill="none" stroke="var(--accent2)" stroke-opacity=".6" stroke-width="1.5"/>
  <circle cx="160" cy="150" r="40" fill="var(--panel)" stroke="var(--line)"/>
  <text x="160" y="146" text-anchor="middle" class="lblb">内核名</text>
  <text x="160" y="163" text-anchor="middle" class="lbl">N 步闭环</text>
  <g fill="var(--accent2)"><circle cx="160" cy="76" r="4"/><circle cx="212" cy="98" r="4"/><circle cx="234" cy="150" r="4"/><circle cx="212" cy="202" r="4"/><circle cx="160" cy="224" r="4"/><circle cx="108" cy="202" r="4"/><circle cx="86" cy="150" r="4"/><circle cx="108" cy="98" r="4"/></g>
  <g fill="var(--accent)"><circle cx="160" cy="22" r="4.5"/><circle cx="248" cy="48" r="4.5"/><circle cx="289" cy="118" r="4.5"/><circle cx="282" cy="200" r="4.5"/><circle cx="220" cy="262" r="4.5"/><circle cx="135" cy="276" r="4.5"/><circle cx="58" cy="248" r="4.5"/><circle cx="32" cy="170" r="4.5"/><circle cx="55" cy="78" r="4.5"/></g>
  <text x="160" y="295" text-anchor="middle" class="lbl">外环 N 段 · 内环 N 步</text>
</svg>
```

## 配方 2 · 冲突图 / 独立集（并行调度）

节点 = 任务，边 = 共享资源（连边即冲突）。高亮一组**无连边**的节点 = 本波可并行。

```html
<svg viewBox="0 0 300 240" width="100%" style="max-height:48vh">
  <line x1="70" y1="60" x2="150" y2="40" stroke="var(--line)" stroke-width="1.5"/>
  <line x1="150" y1="40" x2="150" y2="120" stroke="var(--line)" stroke-width="1.5"/>
  <!-- 独立集（accent 高亮 + 标签） -->
  <g><circle cx="70" cy="60" r="20" fill="#13202e" stroke="var(--accent)" stroke-width="2"/><text x="70" y="64" text-anchor="middle" class="lblb">A1</text></g>
  <g><circle cx="240" cy="160" r="20" fill="#13202e" stroke="var(--accent)" stroke-width="2"/><text x="240" y="164" text-anchor="middle" class="lblb">A2</text></g>
  <!-- 冲突节点（dim 弱化 + 标签） -->
  <g opacity=".55"><circle cx="150" cy="40" r="18" fill="var(--panel)" stroke="var(--dim)"/><text x="150" y="44" text-anchor="middle" class="lbl">B</text></g>
  <text x="150" y="222" text-anchor="middle" class="lbl">蓝色 = 本波可并行（无连边的独立集）</text>
</svg>
```

## 配方 3 · 纵向流水 + 三源汇入（双闸 / 多源校验）

纵向 6 段流，闸节点青色加粗描边；右侧 3 个来源用箭头汇入某一节点。**适合短内容页靠它撑满右栏。**

```html
<svg viewBox="0 0 300 360" width="100%" style="max-height:58vh">
  <defs>
    <marker id="da" markerWidth="9" markerHeight="9" refX="5" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 z" fill="var(--dim)"/></marker>
    <marker id="da2" markerWidth="9" markerHeight="9" refX="5" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 z" fill="var(--accent2)"/></marker>
  </defs>
  <g stroke="var(--dim)" stroke-width="1.5" marker-end="url(#da)">
    <line x1="100" y1="46" x2="100" y2="64"/><line x1="100" y1="106" x2="100" y2="124"/>
    <line x1="100" y1="166" x2="100" y2="184"/><line x1="100" y1="226" x2="100" y2="244"/>
    <line x1="100" y1="290" x2="100" y2="308"/>
  </g>
  <g><rect x="36" y="14" width="128" height="32" fill="var(--panel)" stroke="var(--line)"/><text x="100" y="34" text-anchor="middle" class="lbl">① 起点</text></g>
  <g><rect x="36" y="72" width="128" height="34" fill="#13201e" stroke="var(--accent2)" stroke-width="2"/><text x="100" y="93" text-anchor="middle" class="lblb" style="fill:var(--accent2)">闸-1</text></g>
  <g><rect x="36" y="132" width="128" height="32" fill="var(--panel)" stroke="var(--line)"/><text x="100" y="152" text-anchor="middle" class="lbl">中间步</text></g>
  <g><rect x="36" y="192" width="128" height="32" fill="var(--panel)" stroke="var(--line)"/><text x="100" y="212" text-anchor="middle" class="lbl">确定性步</text></g>
  <g><rect x="36" y="250" width="128" height="34" fill="#13201e" stroke="var(--accent2)" stroke-width="2"/><text x="100" y="271" text-anchor="middle" class="lblb" style="fill:var(--accent2)">闸-2</text></g>
  <g><rect x="36" y="316" width="128" height="32" fill="#13202e" stroke="var(--accent)" stroke-width="2"/><text x="100" y="336" text-anchor="middle" class="lblb" style="fill:var(--accent)">终点</text></g>
  <g stroke="var(--accent2)" stroke-width="1.4" marker-end="url(#da2)" fill="none">
    <path d="M250 250 L168 263"/><path d="M254 273 L168 270"/><path d="M250 296 L168 277"/>
  </g>
  <g text-anchor="start" class="lbl"><text x="200" y="248">源1</text><text x="200" y="271">源2</text><text x="200" y="294">源3</text></g>
  <text x="218" y="226" text-anchor="middle" class="lbl" style="fill:var(--accent2)">多源汇入</text>
</svg>
```

## 配方 4 · 自进化回环（带向循环）

5 节点圆周排布，**圆弧箭头标方向**，每节点带序号标签，中心放回环名。半径 r=92、圆心 (160,140)。

```html
<svg viewBox="0 0 320 300" width="100%" style="max-height:48vh">
  <defs><marker id="ev" markerWidth="9" markerHeight="9" refX="5" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 z" fill="var(--accent2)"/></marker></defs>
  <g fill="none" stroke="var(--accent2)" stroke-width="1.6" stroke-opacity=".85" marker-end="url(#ev)">
    <path d="M173 50 A92 92 0 0 1 244 100"/>
    <path d="M252 124 A92 92 0 0 1 224 205"/>
    <path d="M202 221 A92 92 0 0 1 118 221"/>
    <path d="M96 205 A92 92 0 0 1 68 124"/>
    <path d="M76 100 A92 92 0 0 1 147 50"/>
  </g>
  <g fill="var(--accent)"><circle cx="160" cy="48" r="6"/><circle cx="248" cy="112" r="6"/><circle cx="214" cy="214" r="6"/><circle cx="106" cy="214" r="6"/><circle cx="72" cy="112" r="6"/></g>
  <text x="160" y="34" text-anchor="middle" class="lblb">① 阶段一</text>
  <text x="262" y="112" text-anchor="start" class="lbl">② 阶段二</text>
  <text x="222" y="234" text-anchor="start" class="lbl">③ 阶段三</text>
  <text x="98" y="234" text-anchor="end" class="lbl">④ 阶段四</text>
  <text x="58" y="112" text-anchor="end" class="lbl">⑤ 阶段五</text>
  <text x="160" y="138" text-anchor="middle" class="lblb" style="fill:var(--accent2)">回环名</text>
  <text x="160" y="156" text-anchor="middle" class="lbl">一句注脚</text>
</svg>
```

## 配方 5 · 九宫流水（HTML，非 SVG）

9 段流程用 `.pipe` + `.pstep`（含 `.gate` 高亮）即可，无需 SVG。见模板示例第 4 页。
适合"步骤多、每步一句"的总流程页；闸/关键步加 `gate` class 青色高亮。

---

## 通用注意
- viewBox 高度别超过 `max-height:~58vh`，给标题/页脚留白。
- 中文标签短，长则拆两行或挪到节点外侧用 `text-anchor` 靠边。
- 箭头必须用 `<marker>` + `marker-end`，别用裸线段冒充有向。
- 一页一图，图与文左右分栏（`.row flex:1`），不堆砌多图。
