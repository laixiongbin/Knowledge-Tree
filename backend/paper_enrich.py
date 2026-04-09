"""
多数据源补全论文链接：arXiv → Semantic Scholar → OpenAlex。
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import arxiv_client
import openalex_client
import semantic_scholar


def _step_delay() -> float:
    """同一篇论文内，切换数据源前的短间隔（秒）。"""
    try:
        v = float(os.getenv("LITERATURE_STEP_DELAY", "1.0"))
    except ValueError:
        v = 1.0
    return max(0.0, v)


def _max_papers() -> int:
    raw = os.getenv("LITERATURE_MAX_ENRICH") or os.getenv("ARXIV_MAX_ENRICH", "40")
    try:
        n = int(raw)
    except ValueError:
        n = 40
    return max(1, min(n, 200))


def needs_literature_lookup(url: Any) -> bool:
    if url is None or not isinstance(url, str) or not url.strip():
        return True
    u = url.lower()
    if "arxiv.org/abs/" in u:
        return False
    if "example.com" in u or "placeholder" in u or "test.com" in u:
        return True
    return False


def resolve_paper_url(
    title: str,
    authors: Optional[str] = None,
    year: Optional[str] = None,
) -> Optional[str]:
    """
    按优先级解析可点击链接；任一源成功即返回。
    year 可为字符串或数字，会转成 str 传入下游（预留）。
    """
    y = str(year).strip() if year is not None and str(year).strip() else None

    u = arxiv_client.search_arxiv_abs_url(title, authors)
    if u:
        return u

    d = _step_delay()
    if d:
        time.sleep(d)
    u = semantic_scholar.search_best_literature_url(title, authors, y)
    if u:
        return u

    if d:
        time.sleep(d)
    u = openalex_client.search_best_literature_url(title, authors, y)
    return u


def enrich_tree_with_literature(tree: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度优先遍历 paper 节点，补全 url（原地修改）。
    论文与论文之间的间隔复用 ARXIV_QUERY_DELAY。
    """
    delay = arxiv_client._delay_seconds()
    limit = _max_papers()
    done = 0
    last_request_at = 0.0

    def tick_before_paper():
        nonlocal last_request_at
        if delay <= 0:
            return
        now = time.monotonic()
        wait = delay - (now - last_request_at)
        if wait > 0:
            time.sleep(wait)
        last_request_at = time.monotonic()

    def walk(node: Dict[str, Any]) -> None:
        nonlocal done
        if done >= limit:
            return
        if node.get("type") == "paper":
            if needs_literature_lookup(node.get("url")):
                if done >= limit:
                    return
                tick_before_paper()
                yr = node.get("year")
                u = resolve_paper_url(
                    str(node.get("name") or ""),
                    str(node.get("authors") or "") if node.get("authors") else None,
                    yr,
                )
                done += 1
                if u:
                    node["url"] = u
            return
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child)

    walk(tree)
    return tree
