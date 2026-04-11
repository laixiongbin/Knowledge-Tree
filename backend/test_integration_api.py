"""
接入真实 HTTP 服务与（可选）真实大模型 /generate 的集成测试。

前置条件：
  1. 启动后端（在 backend 目录）:
       python app.py
     或指定端口时设置环境变量 INTEGRATION_BASE_URL。

  2. 仅跑只读接口时无需配置 DeepSeek；若要测完整生成，见下文。

环境变量：
  INTEGRATION_BASE_URL     默认 http://127.0.0.1:5050
  INTEGRATION_FULL         设为 1 时执行 POST /generate（调用服务端配置的 DeepSeek，较慢、消耗配额）
  INTEGRATION_GENERATE_TIMEOUT  /generate 超时秒数，默认 180
  INTEGRATION_DIRECT_DEEPSEEK 设为 1 时额外测本机到 DeepSeek 的直连（需 DEEPSEEK_API_KEY，不经过 Flask）

建议服务端加速集成测试（.env）:
  LITERATURE_ENRICH_ON_GENERATE=0

运行:
  cd backend
  ..\\venv\\Scripts\\python.exe test_integration_api.py
"""

from __future__ import annotations

import os
import unittest

import requests

_DEFAULT_BASE = "http://127.0.0.1:5050"


def _base_url() -> str:
    return (os.getenv("INTEGRATION_BASE_URL") or _DEFAULT_BASE).strip().rstrip("/")


def _server_reachable(base: str, timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{base}/health", timeout=timeout)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except (requests.RequestException, ValueError, TypeError):
        return False


@unittest.skipUnless(
    os.getenv("SKIP_INTEGRATION_HTTP", "").strip().lower() not in ("1", "true", "yes"),
    "已设置 SKIP_INTEGRATION_HTTP，跳过 HTTP 集成测试",
)
class TestLiveHTTPIntegration(unittest.TestCase):
    """对运行中的 Flask 服务发真实 HTTP 请求。"""

    @classmethod
    def setUpClass(cls):
        cls.base = _base_url()
        if not _server_reachable(cls.base):
            raise unittest.SkipTest(
                f"无法连接 {cls.base}/health ，请先启动后端: cd backend && python app.py"
            )

    def test_health(self):
        r = requests.get(f"{self.base}/health", timeout=10)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")

    def test_api_trees(self):
        r = requests.get(f"{self.base}/api/trees", timeout=30)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("code"), 200)
        self.assertIn("data", body)

    def test_api_stats(self):
        r = requests.get(f"{self.base}/api/stats", timeout=30)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("code"), 200)
        self.assertIn("total_trees", body.get("data", {}))

    def test_api_search(self):
        r = requests.get(f"{self.base}/api/search", params={"q": "test"}, timeout=30)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("code"), 200)

    @unittest.skipUnless(
        (os.getenv("INTEGRATION_FULL") or "").strip() in ("1", "true", "yes"),
        "未设置 INTEGRATION_FULL=1，跳过真实 /generate（避免误耗配额）",
    )
    def test_generate_real_llm(self):
        timeout = int(os.getenv("INTEGRATION_GENERATE_TIMEOUT") or "180")
        r = requests.post(
            f"{self.base}/generate",
            json={"keyword": (os.getenv("INTEGRATION_GENERATE_KEYWORD") or "知识图谱").strip()},
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        self.assertEqual(
            r.status_code,
            200,
            f"body={r.text[:500]}",
        )
        data = r.json()
        self.assertIn("name", data)
        self.assertTrue(str(data["name"]).strip())


@unittest.skipUnless(
    (os.getenv("INTEGRATION_DIRECT_DEEPSEEK") or "").strip() in ("1", "true", "yes"),
    "未设置 INTEGRATION_DIRECT_DEEPSEEK=1，跳过 DeepSeek 直连",
)
class TestDeepSeekDirect(unittest.TestCase):
    """直连 DeepSeek API（验证密钥与网络，不经由本项目 Flask）。"""

    def test_chat_completion_minimal(self):
        from dotenv import load_dotenv

        load_dotenv()
        api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        if not api_key:
            self.skipTest("未配置 DEEPSEEK_API_KEY")

        endpoint = (os.getenv("DEEPSEEK_ENDPOINT") or "https://api.deepseek.com/v1/chat/completions").strip()
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "只回复一个字：好"}],
            "max_tokens": 8,
        }
        r = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        self.assertEqual(r.status_code, 200, r.text[:300])
        body = r.json()
        self.assertIn("choices", body)


def load_dotenv_early():
    try:
        from dotenv import load_dotenv

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(root, ".env"))
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    except ImportError:
        pass


if __name__ == "__main__":
    load_dotenv_early()
    unittest.main(verbosity=2)
