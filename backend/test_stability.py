"""
稳定性 / 冒烟测试：不调用外网大模型与文献 API（通过 mock 与环境变量）。
在 backend 目录下执行: python test_stability.py
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 在导入 app 前关闭生成时的文献补全，避免外网与长耗时
os.environ.setdefault("LITERATURE_ENRICH_ON_GENERATE", "0")

# 保证以 backend 为工作目录时可找到同目录模块
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import app as app_module  # noqa: E402


TEST_TREE_NAME = "__stability_test_tree__"


class TestAPIStability(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_health_many_times(self):
        for _ in range(30):
            r = self.client.get("/health")
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertEqual(r.get_json().get("status"), "ok")

    def test_api_trees(self):
        r = self.client.get("/api/trees")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body.get("code"), 200)
        self.assertIn("data", body)

    def test_api_stats(self):
        r = self.client.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body.get("code"), 200)
        self.assertIn("total_trees", body.get("data", {}))

    def test_api_search_empty_q_delegates(self):
        r = self.client.get("/api/search?q=")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json().get("code"), 200)

    @patch.object(app_module, "call_deepseek")
    def test_generate_mocked_llm(self, mock_llm):
        mock_llm.return_value = (
            {
                "name": "测试主题",
                "type": "concept",
                "description": "冒烟",
                "children": [
                    {"name": "子节点", "type": "concept", "children": []},
                ],
            },
            None,
        )
        r = self.client.post("/generate", json={"keyword": "测试关键词"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertEqual(data.get("name"), "测试主题")
        self.assertTrue(len(data.get("children", [])) >= 1)

    def test_generate_missing_keyword(self):
        r = self.client.post("/generate", json={"keyword": "  "})
        self.assertEqual(r.status_code, 400)

    def test_save_roundtrip_and_delete(self):
        # 清理旧数据
        self.client.delete(f"/api/tree/{TEST_TREE_NAME}")

        payload = {
            "name": TEST_TREE_NAME,
            "type": "root",
            "description": "stability test",
            "children": [{"name": "仅子节点", "type": "concept", "children": []}],
        }
        r = self.client.post("/save", json=payload)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json().get("code"), 200)

        r2 = self.client.get(f"/api/tree/{TEST_TREE_NAME}")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json().get("code"), 200)
        self.assertEqual(r2.get_json().get("data", {}).get("name"), TEST_TREE_NAME)

        r3 = self.client.delete(f"/api/tree/{TEST_TREE_NAME}")
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.get_json().get("code"), 200)

    @patch("app.requests.post")
    def test_expand_mocked_http(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"name":"扩展子项","type":"concept","description":"d","children":[]}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        r = self.client.post(
            "/expand",
            json={"parent_name": "父", "tree_name": "t", "keyword": "父"},
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body.get("code"), 200)
        self.assertIsInstance(body.get("children"), list)


class TestLiteratureModule(unittest.TestCase):
    def test_enrich_empty_tree(self):
        import paper_enrich

        tree = {"name": "r", "type": "concept", "children": []}
        paper_enrich.enrich_tree_with_literature(tree)
        self.assertEqual(tree["children"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
