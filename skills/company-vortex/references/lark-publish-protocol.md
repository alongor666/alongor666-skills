# 飞书发布协议

> Step 7b / 8 / 11 调用。把有声长文 + 涡旋图集发布到飞书云文档、发文档链接、发播客音频。
> 前置：Step 0 的 auth 预检结果须为就绪；未就绪则跳过对应步骤并提示用户补发。

## lark-cli 环境前缀（所有 lark-cli 命令必须以此开头）

```bash
export PATH="$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ | tail -1)/bin:$PATH" &&
```

`tail -1` = 取 nvm 下最新安装的 node 版本目录。本文件所有命令默认已带此前缀。

---

## Step 7b: 有声长文 → 飞书云文档（含涡旋图集）

使用 `/lark-doc` 技能。

### 1. 准备 Lark-flavored Markdown
- 移除 H1 标题（由 `--title` 参数设置）
- 「一句话定义」转为 `<callout emoji="🔭" background-color="light-blue">`
- 风险断层线段落转为 `<callout emoji="⚠️" background-color="light-red/light-yellow">`
- 涡旋快照转为 PNG 图片，追加在文末图集章节

### 1b. 生成涡旋快照图片（HTML+CSS → Chrome 截图）
为每个阶段生成 JSON 数据文件，调用通用脚本 `$WORKDIR/scripts/vortex_draw_html.py` 生成 HTML 并截图为 PNG。

JSON 数据格式（写入 `/tmp/vortex_phase{N}.json`）：
```json
{
  "title": "第N阶段：形态名（年份范围）",
  "pressures": ["外部压力1", "外部压力2"],
  "entities": ["关键实体1", "关键实体2"],
  "demand": "核心需求/主题",
  "core_title": "{公司名} · 核心涡旋",
  "core_items": ["核心能力1", "核心能力2", "核心能力3"],
  "expansions": ["扩张方向1", "扩张方向2"],
  "risks": [
    {"text": "风险描述", "level": "critical"},
    {"text": "风险描述", "level": "warning"}
  ],
  "footer": "一句话总结"
}
```
除 `title` 外字段均可选——早期阶段可省略 `entities`/`demand`/`risks`。视觉规范（深色渐变、三层结构天=橙/人=蓝/地=灰蓝、1200×900px 圆角卡片、虚线断层线）脚本内置，无需手动控制。

```bash
.venv/bin/python3 $WORKDIR/scripts/vortex_draw_html.py \
  --data /tmp/vortex_phase{N}.json \
  --output assets/images/vortex_phase{N}.png
```
Fallback：Chrome 不可用 → Playwright → 都不可用则输出 HTML 路径提示手动截图。
在飞书 Markdown 中用斜体占位引用 `*涡旋快照见文末图集 · 第N阶段*`。

### 2. 分段创建文档（长文档分批，提高成功率）
```bash
# 第一段：概览 + 财务数据
lark-cli docs +create --title "{公司名}（{代码}）· 结构演变全景分析" --markdown "$(cat /tmp/lark_chunk1.md)"
# 记录返回的 doc_id

# 后续段：逐段追加
lark-cli docs +update --doc "{doc_id}" --mode append --markdown "$(cat /tmp/lark_chunkN.md)"

# 添加图集章节标题
lark-cli docs +update --doc "{doc_id}" --mode insert_before \
  --selection-with-ellipsis "## 资料来源" --markdown "## 涡旋结构图集"

# 逐个插入涡旋图片（末尾追加，位于资料来源之后）
lark-cli docs +media-insert --doc "{doc_id}" --file ./assets/images/vortex_phaseN.png \
  --align center --caption "{阶段标题}"
```

### 3. 授权文档所有者（bot 身份创建时必须）
```bash
lark-cli auth status  # 从 userOpenId 字段获取 open_id

lark-cli drive permission.members create \
  --params '{"token":"{doc_id}","type":"docx","need_notification":"true"}' \
  --data '{"member_type":"openid","member_id":"{open_id}","perm":"full_access","type":"user"}' \
  --as bot
```

### 4. 输出文档 URL 告知用户。

---

## Step 8: 发送文档链接（/lark-im）

```bash
lark-cli im +messages-send \
  --user-id {open_id} \
  --markdown "**{公司名}（{代码}）结构诊断报告已生成**\n\n文档链接：[点击查看]({doc_url})\n\n报告包含：{阶段数}阶段涡旋演变分析、风险矩阵、终局四维评分。" \
  --as bot
```
- 接收者 open_id 复用 Step 7 的 `userOpenId`
- 需 bot 具有 `im:message:send_as_bot` scope；无权限则提示用户在开发者后台开通

---

## Step 11: 发送播客音频

```bash
lark-cli im +messages-send \
  --user-id {open_id} \
  --file $WORKDIR/{公司名}_{股票代码}_播客.mp3 \
  --as bot
```
- 用 `--file`（而非 `--audio`）发送 mp3，兼容性更好（经验性 know-how）
- lark-cli 自动上传文件再发送，无需手动调上传接口
- 需 bot 具有 `im:message:send_as_bot` + `im:resource:upload` scope
- 飞书单文件上限 30MB，5 分钟播客 mp3 通常 < 5MB

---

## UPDATE 模式同步（U6/U7）

```bash
# 搜索现有文档
lark-cli docs +search --query "{公司名} 结构演变全景分析"

# 追加修正内容到文档末尾
lark-cli docs +update --doc "{doc_id}" --mode append --markdown "{修正内容}"

# 发送更新通知
lark-cli im +messages-send \
  --user-id {open_id} \
  --markdown "**{公司名}（{代码}）结构诊断已更新**\n\n更新内容：{修正项摘要}\n评分变化：{变化条数}项\n\n文档链接：[点击查看]({doc_url})" \
  --as bot
```
若未找到飞书文档，执行 Step 7-8 创建新文档并通知。
