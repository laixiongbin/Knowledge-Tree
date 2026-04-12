# Knowledge-Tree（AI 知识树）

基于 **DeepSeek** 的文献与主题知识树：用自然语言生成与扩展树形结构，在浏览器中管理节点、搜索与持久化。后端为 **Flask**，前端为单页 **HTML/JS**；论文节点可通过 **arXiv → Semantic Scholar → OpenAlex** 多源补全链接与元数据（见 `backend/paper_enrich.py`）。

---

## 功能概览

- 调用大模型生成知识树、按需展开子节点
- 多棵知识树的增删改查与本地存储（`storage.json` 等）
- 文献检索与缓存、论文信息补全
- 健康检查 `GET /health`，默认服务端口 **5050**（避免 Windows 上 5000 被占用）

---

## 方式一：从源码运行（开发）

适用于克隆本仓库后直接调试。

**环境**：Python 3.10+（与当前依赖测试版本一致即可）

**步骤**（PowerShell 示例）：

```powershell
cd Knowledge-Tree
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在**仓库根目录**放置 `.env`（与 `load_dotenv()` 行为一致），例如：

```env
DEEPSEEK_API_KEY=你的key
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
```

启动服务：

```powershell
python backend/app.py
```

浏览器访问：`http://127.0.0.1:5050/`（若需改端口，设置环境变量 `PORT` 或 `FLASK_RUN_PORT`）。

**可选环境变量**

| 变量 | 说明 |
|------|------|
| `PORT` / `FLASK_RUN_PORT` | HTTP 端口，默认 `5050` |
| `KNOWLEDGE_TREE_FRONTEND_DIR` | 自定义前端目录（需含 `index.html`） |
| `LITERATURE_STEP_DELAY` | 文献多源查询间隔（秒），默认 `1.0` |
| `LITERATURE_MAX_ENRICH` / `ARXIV_MAX_ENRICH` | 单次补全论文数量上限，默认 `40`，最大 `200` |
| `LITERATURE_ENRICH_WORKERS` | 补全并发数，默认 `4`，最大 `16` |

**密钥**：除 `.env` 外，请求也可携带请求头 `X-DeepSeek-Api-Key`（或 JSON 中的 `deepseek_api_key` / `deepseekApiKey`），服务端在未配置环境变量时会使用该密钥。

---

## 方式二：Windows 发布版（可执行文件）

这是已打包好的 Windows 版本。运行后在本机启动 Web 服务，并在浏览器中打开前端页面。

### 运行

1. 双击运行 `AI_Knowledge_Tree.exe`
2. 浏览器访问：`http://127.0.0.1:5050/`（默认端口；可用环境变量 `PORT` 修改）

### 配置 DeepSeek（必须）

出于安全考虑，发布包**不内置** `.env`。请在 **exe 同目录** 放置 `.env`（与 `AI_Knowledge_Tree.exe` 放在一起）。

`.env` 示例：

```env
DEEPSEEK_API_KEY=你的key
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
```

### 打包（维护者）

在已安装依赖的环境中，使用仓库内规格文件构建：

```powershell
pyinstaller AI_Knowledge_Tree.spec
```

产物通常在 `dist/` 目录。

---

## 常见问题

- **页面打不开 / 404**
  - 确认程序仍在运行（不要关闭控制台窗口）
  - 默认端口为 **5050**；Windows 上 **5000** 常被系统服务占用，连错进程会 404。请用 `PORT` 指定端口并访问对应地址
  - 若防火墙提示，允许本地访问即可

- **无法生成知识树 / 调用 DeepSeek 失败**
  - 检查 `.env` 是否在 exe 同目录（发布版）或仓库根目录（源码），变量名是否正确
  - 检查 `DEEPSEEK_API_KEY` 是否有效、是否有额度

- **前端路径异常**
  - 可设置 `KNOWLEDGE_TREE_FRONTEND_DIR` 指向包含 `index.html` 的目录

---

## 安全提示

- 不要把包含真实 `DEEPSEEK_API_KEY` 的 `.env` 提交到版本库或随意发给他人
- 在公共环境优先使用个人密钥头字段，并注意浏览器与网络环境安全
