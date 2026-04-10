# Knowledge-Tree（发布版）

这是已打包好的 Windows 版本。运行后会在本机启动一个 Web 服务，并在浏览器中打开前端页面。

## 运行方式

1. 双击运行 `AI_Knowledge_Tree.exe`
2. 打开浏览器访问：`http://127.0.0.1:5000/`

## 配置 DeepSeek（必须）

出于安全考虑，发布包 **不内置** `.env`。请你在 **exe 同目录** 放置一个 `.env` 文件（与 `AI_Knowledge_Tree.exe` 放在一起）。

`.env` 示例：

```
DEEPSEEK_API_KEY=你的key
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
```

## 常见问题

- **页面打不开 / 访问 5000 端口失败**
  - 确认程序仍在运行（不要关闭弹出的黑色窗口）
  - 可能端口被占用：关闭占用 5000 端口的程序后重试
  - 首次运行若弹出防火墙提示，允许本地访问即可

- **无法生成知识树 / 调用 DeepSeek 失败**
  - 检查 `.env` 是否在 exe 同目录、变量名是否写对
  - 检查 `DEEPSEEK_API_KEY` 是否有效/有额度

## 安全提示

- 不要把包含真实 `DEEPSEEK_API_KEY` 的 `.env` 直接发给别人。
