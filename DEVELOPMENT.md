# Knowledge-Tree 开发文档

本文档主要面向项目开发者，描述此项目代码结构、运行方式、配置项、主要接口与打包流程。

## 项目概览

- **后端**：`backend/app.py`（Flask API 服务，负责知识树生成、保存、查询、扩展等）
- **前端**：`frontend/`（静态页面 `index.html`，内联 JavaScript 通过 HTTP 调用后端 API）
- **配置**：`.env`（DeepSeek API Key 与 Endpoint）
- **数据存储**：默认 **`backend/storage.json`**（与 `app.py` 同目录；读写在 `backend/restore.py`）
- **打包**：`AI_Knowledge_Tree.spec`（通过PyInstaller 配置）

## 环境准备

- **操作系统**：Windows 10/11
- **Python**：建议 3.10.x（本项目使用Python3.10.11）

建议使用项目根目录下的虚拟环境（仓库中常见为 **`venv`** 或 **`.venv`**）：

```powershell
& ".\venv\Scripts\Activate.ps1"
# 或: & ".\.venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
```

## 配置（.env）

项目通过 `python-dotenv` 读取 `.env`。源码运行时优先加载**当前工作目录**下的 `.env`；**PyInstaller 单文件**运行时会**额外**尝试加载解压目录 **`sys._MEIPASS/.env`**（与 `spec` 中打入的 `.env` 对应）。

在项目根目录（或 exe 同目录）创建 `.env`（可参考仓库内示例，**勿将含真实 Key 的 `.env` 提交到 Git**）：

```dotenv
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
```

说明：

- **DEEPSEEK_API_KEY**：你的 DeepSeek API Key
- **DEEPSEEK_ENDPOINT**：接口地址（默认值已在代码中提供）

## 本地运行（开发态/源代码）

### 启动后端

在项目根目录或 `backend/` 目录启动均可，推荐在 `backend/` 下启动app.py

```powershell
& ".\venv\Scripts\python.exe" "backend\app.py"
# 或: & ".\.venv\Scripts\python.exe" "backend\app.py"
```

默认监听地址（以实际输出为准）：

- `http://127.0.0.1:5050`（默认；Windows 上 5000 常被系统服务占用导致 404，见 `backend/app.py` 说明）

可用健康检查：

- `GET /health`

### 启动/打开前端

前端是静态文件（`frontend/index.html`），开发时可直接用浏览器打开该文件，或用任意静态服务器托管它。

- **方式 A**：直接双击打开 `frontend/index.html`
  - 前端通过 `API_BASE` 调用 API：从后端打开页面时为当前站点 `origin`，直接打开本地 `index.html` 时回退为 `http://127.0.0.1:5050`
  - 后端已启用 CORS，通常可以正常请求

> 备注：`http://127.0.0.1:5050/` 由后端直接返回 `frontend/index.html`。打包时 `frontend/` 作为 PyInstaller `datas` 纳入后，运行时会从 **`sys._MEIPASS/frontend`** 或 exe 旁的 `frontend/` 解析路径（见 `backend/app.py` 中 `_default_frontend_dir()`）。环境变量 **`KNOWLEDGE_TREE_FRONTEND_DIR`** 可覆盖前端目录。

### 前端中的 DeepSeek Key（可选）

`index.html` 提供 **DeepSeek API Key** 输入框；浏览器将密钥保存在 **localStorage**（键名 `knowledgeTreeDeepseekApiKey`），并在调用 **`POST /generate`**、**`POST /expand`** 时自动附加请求头 **`X-DeepSeek-Api-Key`**。未填写时由服务端 `.env` 中的 **`DEEPSEEK_API_KEY`** 生效。

## 后端接口速览（backend/app.py）

以下为主要路由（以代码为准）：

- **生成知识树**
  - `POST /generate`
  - Body：`{ "keyword": "..." }`
  - 返回：知识树 JSON（失败时可能回退为本地生成的“树”）

- **扩展节点**
  - `POST /expand`
  - 用途：基于已有节点生成子节点（由前端的蓝色“+”按钮触发）

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
  - `POST /api/tree/<tree_name>/reorder`：同级节点手动排序（`importance`）
  - `POST /api/tree/<tree_name>/auto_importance`：调用 DeepSeek 对子节点排序（需有效 Key）
  - `GET /api/search`：搜索
  - `GET /api/stats`：统计

- **保存**
  - `POST /save`
  - 用途：保存当前树（前端“保存当前树”按钮）

## 数据存储

- 默认存储文件：与 **`backend/app.py` 同目录** 的 **`storage.json`**（见 `app.py` 中 `_STORAGE_FILE`）
- 存取逻辑：`backend/restore.py`（例如 JSONStorage）

## 与 DeepSeek 的交互

后端使用 `requests.post(...)` 调用 **`DEEPSEEK_ENDPOINT`**（默认 DeepSeek 兼容的 Chat Completions URL），并在请求头中带上：

- `Authorization: Bearer <有效密钥>`

其中 **`<有效密钥>`** 的解析顺序为：请求头 **`X-DeepSeek-Api-Key`** 或 JSON 中的 **`deepseek_api_key` / `deepseekApiKey`**（见 `API.md`）→ 环境变量 **`DEEPSEEK_API_KEY`**。

返回内容期望为模型的 JSON 输出（代码做 JSON 解析和校验）。

## 打包（Windows 发布）

项目使用 **PyInstaller** + `AI_Knowledge_Tree.spec` 打包：

```powershell
& ".\venv\Scripts\python.exe" -m PyInstaller ".\AI_Knowledge_Tree.spec"
```

直接运行文件在：

- `dist/AI_Knowledge_Tree.exe`

### 分发与 `.env`

当前 `AI_Knowledge_Tree.spec` 的 **`datas`** 中包含 **`frontend`** 与 **`.env`**（便于本地一键构建自测）。**对外分发时请从 `spec` 中移除真实 `.env` 条目**，或仅打包不含密钥的模板文件；接收方可以：

- 在 **exe 同目录** 放置自己的 `.env`，或
- 仅使用网页上的 **DeepSeek API Key** 输入框（密钥仅存浏览器）。

运行 exe 时建议**工作目录为 `dist/`**（与放置 `storage.json`、`.env` 的习惯一致）；根路径 `http://127.0.0.1:5050/` 应能直接打开打包进去的前端页面。

## 常见问题（Troubleshooting）

### 1) 点击“生成”无反应/报错 500 

优先检查：

- 页面 **DeepSeek API Key** 是否已填，或 `.env` 中 **`DEEPSEEK_API_KEY`** 是否有效、是否有额度
- 后端终端输出是否有报错
- 可使用项目根目录 **`test.py`** 或 **`backend/test_integration_api.py`** 排查网络与密钥（见 `API.md` 集成测试小节）

### 2) Windows 控制台编码导致崩溃

如果后端在 `print(...)` 输出 emoji/特殊字符，Windows 的默认 `gbk` 控制台可能触发 `UnicodeEncodeError`，从而导致接口 500。  
建议：后端日志输出使用纯 ASCII/中文，避免 emoji（或调整控制台编码到 UTF-8）。

### 3) 端口占用

默认 **5050**（`PORT`）。若端口被占用，启动会失败；请改 `PORT` 或释放端口。勿误用已被系统占用的 **5000**（易出现 404）。

### 4) 根路径返回 JSON「未找到 frontend/index.html」

多见于**旧版 exe**或 **`spec` 未打入 `frontend`**。当前 `app.py` 会在 **PyInstaller** 解压目录 **`sys._MEIPASS/frontend`**、**exe 同目录 `frontend/`** 与源码仓库 `frontend/` 之间解析；请用最新代码重新打包，或设置环境变量 **`KNOWLEDGE_TREE_FRONTEND_DIR`** 指向含 `index.html` 的目录。

## 接口与参数约定

完整的路由、请求/响应示例、集成测试与环境变量说明见 [API.md](API.md)（避免与本文档重复维护）。

