# Knowledge-Tree 开发文档

本文档面向本项目的开发者，描述代码结构、运行方式、配置项、主要接口与打包流程。

## 项目概览

- **后端**：`backend/app.py`（Flask API 服务，负责知识树生成、保存、查询、扩展等）
- **前端**：`frontend/`（静态页面 `index.html`，内联 JavaScript 通过 HTTP 调用后端 API）
- **配置**：`.env`（DeepSeek API Key 与 Endpoint）
- **数据存储**：`storage.json`（知识树持久化，具体读写在 `backend/restore.py`）
- **打包**：`AI_Knowledge_Tree.spec`（PyInstaller 配置）

## 环境准备

- **操作系统**：Windows 10/11（当前仓库已按 Windows 流程使用）
- **Python**：建议 3.10.x（仓库 README 提到 3.10.11）

建议使用项目根目录下的虚拟环境（例如 `.venv`）：

```powershell
& ".\.venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
```

## 配置（.env）

项目通过 `python-dotenv` 读取 `.env`。

在项目根目录创建 `.env`（参考 `.env.example`）：

```dotenv
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
```

说明：

- **DEEPSEEK_API_KEY**：你的 DeepSeek API Key
- **DEEPSEEK_ENDPOINT**：接口地址（默认值已在代码中提供）

## 本地运行（开发态）

### 启动后端

在项目根目录或 `backend/` 目录启动均可，推荐在 `backend/` 下启动：

```powershell
& ".\.venv\Scripts\python.exe" "backend\app.py"
```

默认监听地址（以实际输出为准）：

- `http://127.0.0.1:5000`

可用健康检查：

- `GET /health`

### 启动/打开前端

前端是静态文件（`frontend/index.html`），开发时可直接用浏览器打开该文件，或用任意静态服务器托管它。

- **方式 A（最简单）**：直接双击打开 `frontend/index.html`
  - 前端会调用 `http://127.0.0.1:5000` 的 API（在页面脚本里固定为 `API_BASE`）
  - 后端已启用 CORS，通常可以正常请求

> 备注：如果你希望通过 `http://127.0.0.1:5000/` 直接访问前端页面，需要在后端配置静态目录/根路由（例如将 `frontend/` 作为静态目录，并在 `/` 返回 `index.html`）。当前仓库的 `frontend/` 已作为打包资源被纳入 PyInstaller 的 `datas`。

## 后端接口速览（backend/app.py）

以下为主要路由（以代码为准）：

- **生成知识树**
  - `POST /generate`
  - Body：`{ "keyword": "..." }`
  - 返回：知识树 JSON（失败时可能回退为本地生成的“回退树”）

- **扩展节点**
  - `POST /expand`
  - 用途：基于已有节点生成子节点（由前端的“+”按钮触发）

- **健康检查**
  - `GET /health`

- **知识树 CRUD / 查询**
  - `GET /api/trees`：列表
  - `GET /api/tree/<tree_name>`：详情
  - `PUT /api/tree/<tree_name>`：更新整棵树
  - `DELETE /api/tree/<tree_name>`：删除整棵树
  - `POST /api/tree/<tree_name>/node`：新增节点
  - `PUT /api/tree/<tree_name>/node/<path:node_path>`：更新节点
  - `DELETE /api/tree/<tree_name>/node/<path:node_path>`：删除节点
  - `POST /api/tree/<tree_name>/batch_nodes`：批量节点操作
  - `GET /api/search`：搜索
  - `GET /api/stats`：统计

- **保存**
  - `POST /save`
  - 用途：保存当前树（前端“保存当前树”按钮）

## 数据存储

- 默认存储文件：项目根目录 `storage.json`
- 存取逻辑：`backend/restore.py`（例如 JSONStorage）

## 与 DeepSeek 的交互

后端使用 `requests.post(...)` 调用 `DEEPSEEK_ENDPOINT`，并在请求头中带上：

- `Authorization: Bearer <DEEPSEEK_API_KEY>`

返回内容期望为模型的 JSON 输出（代码会做 JSON 解析与基本校验）。

## 打包（Windows 发布）

项目使用 **PyInstaller** + `AI_Knowledge_Tree.spec` 打包：

```powershell
& ".\.venv\Scripts\python.exe" -m PyInstaller ".\AI_Knowledge_Tree.spec"
```

发布产物通常在：

- `dist/AI_Knowledge_Tree.exe`

### 分发安全：外部 .env

当前 `AI_Knowledge_Tree.spec` 已配置为 **不内嵌 `.env`**（避免把 API Key 打进 exe）。

发布给别人时：

- 提供 `.env.example`（不含真实 key）
- 让使用者在 **exe 同目录** 自行创建 `.env`

## 常见问题（Troubleshooting）

### 1) 点击“生成”无反应/报 500

优先检查：

- `.env` 是否存在、变量名是否正确
- `DEEPSEEK_API_KEY` 是否有效、是否有额度
- 后端终端输出是否有报错

### 2) Windows 控制台编码导致崩溃

如果后端在 `print(...)` 输出 emoji/特殊字符，Windows 的默认 `gbk` 控制台可能触发 `UnicodeEncodeError`，从而导致接口 500。  
建议：后端日志输出使用纯 ASCII/中文，避免 emoji（或调整控制台编码到 UTF-8）。

### 3) 端口占用

如果 5000 端口被占用，启动会失败或无法访问。关闭占用进程或改端口后重试。

---

如需我再补充：

- **“后端直接托管前端（/ 直达 index.html）”的标准实现方式**（开发态/打包态都可用）
- **更完整的接口文档**（请求/响应示例、字段说明、错误码）

---

## 接口文档（完整）

以下内容已从 `API.md` 合并至本文档，后续建议以本章节为唯一维护来源。

### Knowledge-Tree 接口文档（后端 API）

本文档基于 `backend/app.py` 当前实现整理，默认服务地址：

- **Base URL**：`http://127.0.0.1:5000`
- **Content-Type**：除 `GET` 外一般使用 `application/json`

## 通用说明

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

**成功响应（200）**：直接返回知识树 JSON（不包 `code`）。

**失败响应**：

- `400`：缺少关键词

```json
{ "error": "请提供关键词" }
```

**示例（PowerShell）**：

```powershell
$body = @{ keyword = "注意力机制" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/generate" -ContentType "application/json" -Body $body
```

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
