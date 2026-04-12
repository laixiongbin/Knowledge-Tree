# Knowledge-Tree 接口文档（后端 API）

本文档基于 `backend/app.py` 当前实现整理。环境与打包说明见 [DEVELOPMENT.md](DEVELOPMENT.md)。

默认服务地址：

- **Base URL**：`http://127.0.0.1:5050`（默认端口；可用环境变量 `PORT` 覆盖。Windows 上 **5000** 常被系统服务占用，若连错进程会出现 **404**。）
- **Content-Type**：除 `GET` 外一般使用 `application/json`

## 通用说明

### DeepSeek 密钥（可选，按请求覆盖）

调用 **DeepSeek** 的接口需要有效 API Key。服务端默认读取环境变量 **`DEEPSEEK_API_KEY`**（及 `.env`）。此外，每个请求可用以下方式**临时指定用户自己的密钥**（优先级高于环境变量）：

1. **HTTP 请求头**：`X-DeepSeek-Api-Key: sk-...`
2. **JSON Body**（仅适用于带 JSON 体的 `POST`）：`deepseek_api_key` 或 `deepseekApiKey`

**当前会使用上述逻辑的接口**：

- `POST /generate`
- `POST /expand`
- `POST /api/tree/<tree_name>/auto_importance`

未提供请求级密钥且环境变量也未配置时，`/generate` 仍会返回**回退树**；`/expand` 与 `auto_importance` 在无密钥时可能返回 **500** 或业务错误。

**安全提示**：请求级密钥会经本服务转发至 DeepSeek，请勿在不可信网络泄露；浏览器前端若填写密钥，通常保存在 **localStorage**（同源页面可见）。

### CORS

后端对跨域请求允许请求头 **`Content-Type`**、**`X-DeepSeek-Api-Key`**（便于 `file://` 或其它端口打开的前端页面调用 API）。

### 1) 返回格式约定

本项目接口返回存在两种风格：

- **风格 A（多数 `/api/*` 接口）**：`{ "code": 200, "data": ..., "message": "...", ... }`
- **风格 B（部分接口，如 `/generate`）**：直接返回业务 JSON（没有 `code` 包裹）

请以前端调用方式与本文档为准。

### 2) 知识树数据结构（核心字段）

知识树是一个递归结构（节点可嵌套 children）：

```json
{
  "name": "注意力机制",
  "type": "concept",
  "description": "可选，概念说明",
  "children": [
    {
      "name": "子概念",
      "type": "concept",
      "description": "可选",
      "children": []
    },
    {
      "name": "论文节点",
      "type": "paper",
      "authors": "可选",
      "year": "可选",
      "quote": "可选",
      "url": "可选",
      "children": []
    }
  ],
  "created_at": "YYYY-MM-DD HH:mm:ss",
  "updated_at": "YYYY-MM-DD HH:mm:ss"
}
```

### 3) 节点路径（node_path / parent_path）

后端使用 **“按 name 逐级匹配”** 的路径查找节点：

- 路径分隔符：`/`
- 示例：`根节点/一级子节点/二级子节点`
- 注意：如果同一层级有重名节点，会导致路径歧义。

---

## 根路径说明

### GET `/` 与 `/index.html`

**用途**：由后端 **直接返回** `frontend/index.html`，浏览器打开 `http://127.0.0.1:5050/`（或与 `PORT` 一致）即可进入知识树界面（与 API 同源）。

**前端文件解析顺序**（与 `backend/app.py` 一致）：

1. 环境变量 **`KNOWLEDGE_TREE_FRONTEND_DIR`**：若指向的目录下存在 `index.html`，则使用该目录。
2. **PyInstaller 单文件（`-F`）**：打包时若使用 `--add-data "frontend;frontend"`，解压目录 **`sys._MEIPASS/frontend`** 下的 `index.html`。
3. **可执行文件同目录**：`exe` 所在目录下的 **`frontend/index.html`**（若存在）。
4. **源码运行**：仓库根目录下的 **`frontend/index.html`**。

若以上均找不到 `index.html`，返回 **`503`** 与 JSON 说明（`error` / `hint` / `try.health`）。

---

## 健康检查

### GET `/health`

**用途**：检查服务是否存活。

**响应**：

```json
{ "status": "ok" }
```

---

## 生成知识树

### POST `/generate`

**用途**：根据关键词调用 DeepSeek 生成一棵知识树；如果 DeepSeek 调用失败，会返回后端生成的“回退树”。

**请求 Body**：

```json
{ "keyword": "注意力机制" }
```

可选：在 Body 中增加 **`deepseek_api_key`**（或 **`deepseekApiKey`**），或使用请求头 **`X-DeepSeek-Api-Key`**，见上文「DeepSeek 密钥」。

**成功响应（200）**：直接返回知识树 JSON（不包 `code`）。

**失败响应**：

- `400`：缺少关键词

```json
{ "error": "请提供关键词" }
```

**示例（PowerShell）**：

```powershell
$body = @{ keyword = "注意力机制" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5050/generate" -ContentType "application/json" -Body $body

# 使用请求头传入 DeepSeek Key（示例）
# Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5050/generate" -Headers @{ "X-DeepSeek-Api-Key" = "sk-..." } -ContentType "application/json" -Body $body
```

### 生成为什么慢、如何加速

耗时主要来自两部分：

1. **DeepSeek 生成整棵树**（一次大模型调用，`max_tokens` 较大），网络与模型推理时间难以从后端完全消除。
2. **论文链接补全**（默认开启）：对多棵 `paper` 节点依次访问 arXiv / Semantic Scholar / OpenAlex，且 arXiv 有请求间隔要求，篇数多时会明显拉长总时间。

可选手段（在 `.env` 或运行环境中配置）：

| 变量 | 说明 |
|------|------|
| `LITERATURE_ENRICH_ON_GENERATE` | 设为 `0` / `false` / `off` 时，**生成接口不再补全论文 URL**，首包最快；链接可后续再补或依赖模型已填的 `url`。 |
| `LITERATURE_MAX_ENRICH` | 单次最多补全的论文数量上限（默认 `40`），调小可缩短最坏情况耗时。 |
| `LITERATURE_ENRICH_WORKERS` | 并行补全线程数（默认 `4`）。多篇论文在 arXiv 侧仍全局限频串行，但在 Semantic Scholar / OpenAlex 等阶段可重叠，整体往往快于完全串行。 |
| `ARXIV_QUERY_DELAY` | 两次 arXiv HTTP 请求之间的最小间隔（秒，默认约 `3.1`）。**不建议调得过低**，否则易被限流；已命中 `literature_cache` 的标题不会打 arXiv。 |
| `LITERATURE_STEP_DELAY` | 同一篇论文在 arXiv 失败后切换到下一数据源前的间隔（秒，默认 `1`），可适当设为 `0` 略省时间（注意各源速率限制）。 |

### 自动化：接入真实 HTTP / 大模型的集成测试

脚本：`backend/test_integration_api.py`（依赖 `requests`，使用本机已启动的 Flask）。

1. 终端 A：`cd backend` 后执行 `python app.py`（或使用 venv 下的 `python`）。
2. 终端 B：

```powershell
cd backend
..\venv\Scripts\python.exe test_integration_api.py
```

默认会请求 **`/health`、`/api/trees`、`/api/stats`、`/api/search`**，**不会**自动调用 **`/generate`**（避免误耗 DeepSeek 配额）。

要对 **`/generate` 做一次真实生成**，在运行前设置：

```powershell
$env:INTEGRATION_FULL = "1"
# 可选：自定义关键词与超时（秒）
# $env:INTEGRATION_GENERATE_KEYWORD = "注意力机制"
# $env:INTEGRATION_GENERATE_TIMEOUT = "180"
..\venv\Scripts\python.exe test_integration_api.py
```

建议在服务端 `.env` 中设置 **`LITERATURE_ENRICH_ON_GENERATE=0`**，以缩短集成测试耗时。非默认地址时使用 **`INTEGRATION_BASE_URL`**（如 `http://127.0.0.1:8000`）。

仅验证**本机到 DeepSeek 的直连**（不经过 Flask），需已配置 **`DEEPSEEK_API_KEY`**（脚本会尝试加载项目根目录 `.env`）：

```powershell
$env:INTEGRATION_DIRECT_DEEPSEEK = "1"
..\venv\Scripts\python.exe test_integration_api.py
```

不启动服务、不访问外网的冒烟测试见 **`backend/test_stability.py`**。

---

## 扩展节点（生成子节点）

### POST `/expand`

**用途**：给定父节点信息，生成其“直接子节点”（最多 5 个），用于前端点击节点后的扩展操作。

**请求 Body**：

```json
{
  "parent_name": "Transformer",
  "parent_path": "AI 知识体系/深度学习/Transformer",
  "tree_name": "AI 知识体系",
  "keyword": "Transformer"
}
```

字段说明：

- **parent_name**（必填）：父节点名称（为空会返回 400）
- **parent_path**（可选）：父节点路径（主要用于上下文/前端定位）
- **tree_name**（可选）：当前知识树名称
- **keyword**（可选）：用于生成的主题；缺省会用 `parent_name`

可选：请求头 **`X-DeepSeek-Api-Key`**，或 Body 中的 **`deepseek_api_key`** / **`deepseekApiKey`**（见「DeepSeek 密钥」）。

**成功响应（200）**：

```json
{
  "code": 200,
  "children": [
    { "name": "子概念1", "type": "concept", "description": "说明", "children": [] },
    { "name": "相关论文", "type": "paper", "authors": "...", "year": "2024", "quote": "...", "url": "", "children": [] }
  ]
}
```

**失败响应**：

- `400`：缺少父节点名称

```json
{ "error": "缺少父节点名称" }
```

- `500`：DeepSeek 调用或解析异常

```json
{ "code": 500, "message": "..." }
```

---

## 知识树列表/详情

### GET `/api/trees`

**用途**：获取所有知识树列表（带节点数量与预览）。

**成功响应（200）**：

```json
{
  "code": 200,
  "data": [
    {
      "name": "树的存储名",
      "title": "树显示名（通常等于根节点 name）",
      "type": "root/concept/...",
      "created_at": "YYYY-MM-DD HH:mm:ss",
      "updated_at": "YYYY-MM-DD HH:mm:ss",
      "node_count": 12,
      "preview": "预览文本"
    }
  ],
  "total": 1
}
```

**失败响应**：`500`

```json
{ "code": 500, "message": "获取列表失败: ..." }
```

### GET `/api/tree/<tree_name>`

**用途**：获取单棵知识树完整数据。

**成功响应（200）**：

```json
{ "code": 200, "data": { /* 知识树 JSON */ } }
```

**失败响应**：

- `404`：找不到
- `500`：读取失败

---

## 同级节点排序（手动 / AI）

### POST `/api/tree/<tree_name>/reorder`

**用途**：按给定顺序重排某一父节点下的**直接子节点**，并写入 `importance`（1 起递增）。

**请求 Body**：

```json
{
  "parent_path": "根/子路径",
  "ordered_names": ["子节点A", "子节点B"]
}
```

- **parent_path**（可选）：为空字符串时表示重排**根节点**的 `children`。
- **ordered_names**（必填）：子节点 `name` 列表，顺序即新的学习优先级。

**成功响应（200）**：`{ "code": 200, "message": "...", "children": [ ... ] }`

**失败响应**：`400`（参数错误）、`404`（树或父节点不存在）、`500`。

### POST `/api/tree/<tree_name>/auto_importance`

**用途**：将指定父节点下（或根下）的子节点列表交给 **DeepSeek** 排序，并复用内部逻辑写回树（需有效 API Key，支持请求级密钥，见上文）。

**请求 Body**：

```json
{ "parent_path": "根/子路径" }
```

**成功响应（200）**：内部调用 **`POST /api/tree/<tree_name>/reorder`** 写回树，响应体与该接口成功时一致（含 `code`、`message`、`children` 等）。

**失败响应**：`404` / `500`；未配置任何有效 DeepSeek 密钥时一般为 **`500`**，`message` 含「未配置 DeepSeek API 密钥」类说明。

---

## 保存/更新/删除知识树

### POST `/save`

**用途**：保存一棵知识树（前端“保存当前树”按钮）。

**请求 Body**：知识树 JSON（至少包含 `name`）。

**成功响应（200）**：

```json
{
  "code": 200,
  "message": "知识树 \"xxx\" 保存成功！",
  "data": { /* 保存后的知识树 */ }
}
```

**失败响应**：

- `400`：缺少 `name`
- `500`：保存失败

### PUT `/api/tree/<tree_name>`

**用途**：更新整棵树（对现有树做 merge/update，并刷新 `updated_at`）。

**请求 Body**：任意要更新的字段（会 `update()` 到已有数据）。

**成功响应（200）**：

```json
{
  "code": 200,
  "message": "知识树 \"xxx\" 更新成功",
  "data": { /* 更新后的树 */ }
}
```

**失败响应**：

- `404`：树不存在
- `500`：更新失败

### DELETE `/api/tree/<tree_name>`

**用途**：删除整棵树。

**成功响应（200）**：

```json
{ "code": 200, "message": "知识树 \"xxx\" 删除成功" }
```

**失败响应**：

- `404`：树不存在
- `500`：删除失败

---

## 节点操作（增/改/删）

### POST `/api/tree/<tree_name>/node`

**用途**：向指定树添加一个节点；可通过 `parent_path` 指定父节点，否则添加到根节点 children。

**请求 Body**（最小）：

```json
{ "name": "新节点名称" }
```

可选字段：

- `type`：缺省为 `concept`
- `description/authors/year/quote/url/children/...`
- `parent_path`：父节点路径

**成功响应（200）**：

```json
{
  "code": 200,
  "message": "节点 \"xxx\" 添加成功",
  "data": { /* 新节点 */ }
}
```

**失败响应**：

- `404`：树不存在 / 父节点路径不存在
- `400`：缺少 name
- `500`：添加失败

### PUT `/api/tree/<tree_name>/node/<path:node_path>`

**用途**：更新某个节点（按路径查找，找到后对节点执行 `node.update(update_data)`）。

**请求 Body**：要更新的字段，例如：

```json
{ "description": "新的说明", "type": "concept" }
```

**成功响应（200）**：

```json
{ "code": 200, "message": "节点 \"xxx\" 更新成功", "data": { /* 更新后的节点 */ } }
```

**失败响应**：

- `404`：树或节点不存在
- `500`：更新失败

### DELETE `/api/tree/<tree_name>/node/<path:node_path>`

**用途**：删除某个节点（通过拆分路径，定位父节点后按 `name` 删除）。

**成功响应（200）**：

```json
{ "code": 200, "message": "节点 \"xxx\" 删除成功" }
```

**失败响应**：

- `404`：树不存在 / 节点不存在
- `500`：删除失败

---

## 批量节点操作

### POST `/api/tree/<tree_name>/batch_nodes`

**用途**：批量添加多个节点（列表形式），每个节点可携带 `parent_path`。

**请求 Body**：数组

```json
[
  { "name": "节点1", "type": "concept" },
  { "name": "节点2", "parent_path": "根/父节点", "type": "concept" }
]
```

**成功响应（200）**：

```json
{ "code": 200, "message": "成功添加 2 个节点", "count": 2 }
```

**失败响应**：

- `404`：树不存在
- `400`：Body 不是数组
- `500`：批量添加失败

---

## 搜索与统计

### GET `/api/search?q=<keyword>`

**用途**：按关键字搜索知识树（匹配 `tree_name` 或根节点 `name` 的包含关系，忽略大小写）。

参数：

- `q`：搜索关键字；为空则等价于调用 `/api/trees`

**成功响应（200）**：

```json
{ "code": 200, "data": [ /* 同 /api/trees 列表项 */ ], "total": 1 }
```

**失败响应**：`500`

### GET `/api/stats`

**用途**：统计所有树的数量、总节点数、论文节点数、概念节点数。

**成功响应（200）**：

```json
{
  "code": 200,
  "data": {
    "total_trees": 3,
    "total_nodes": 120,
    "total_papers": 10,
    "total_concepts": 110
  }
}
```

**失败响应**：`500`

---

## 备注与改进建议（可选）

- **返回风格不统一**：建议将 `/generate` 与 `/health` 也统一为 `{code,data,message}` 结构，便于前端一致处理。
- **路径歧义**：节点查找依赖 `name`，若同层重名会导致定位错误；建议引入稳定的 `id`。
- **/expand 的 response_format**：当前提示词要求返回数组，但 payload 中使用了 `{"type":"json_object"}`，建议调整为匹配实际期望，或在后端更稳健地兼容两种格式。

