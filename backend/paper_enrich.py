"""
多数据源补全论文链接：arXiv → Semantic Scholar → OpenAlex。
"""

from __future__ import annotations

import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import arxiv_client
import openalex_client
import semantic_scholar
import literature_cache


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


def _enrich_workers() -> int:
    raw = (os.getenv("LITERATURE_ENRICH_WORKERS", "4") or "").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 4
    return max(1, min(n, 16))


def _collect_papers_needing_url(tree: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any]) -> None:
        if len(out) >= limit:
            return
        if node.get("type") == "paper" and needs_literature_lookup(node.get("url")):
            out.append(node)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child)

    walk(tree)
    return out


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

    cached = literature_cache.get_cached(title, authors, y)
    if cached is not None:
        return cached.url

    u = arxiv_client.search_arxiv_abs_url(title, authors)
    if u:
        literature_cache.put_cached(title, authors, y, u)
        return u

    d = _step_delay()
    if d:
        time.sleep(d)
    u = semantic_scholar.search_best_literature_url(title, authors, y)
    if u:
        literature_cache.put_cached(title, authors, y, u)
        return u

    if d:
        time.sleep(d)
    u = openalex_client.search_best_literature_url(title, authors, y)
    literature_cache.put_cached(title, authors, y, u)
    return u


def enrich_tree_with_literature(tree: Dict[str, Any]) -> Dict[str, Any]:
    """
    为 paper 节点补全 url（原地修改）。
    多篇论文并行解析（LITERATURE_ENRICH_WORKERS）；arXiv 请求在 arxiv_client 内全局限频。
    """
    limit = _max_papers()
    papers = _collect_papers_needing_url(tree, limit)
    if not papers:
        return tree

    workers = min(_enrich_workers(), len(papers))

    def job(n: Dict[str, Any]) -> tuple:
        yr = n.get("year")
        u = resolve_paper_url(
            str(n.get("name") or ""),
            str(n.get("authors") or "") if n.get("authors") else None,
            yr,
        )
        return n, u

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(job, n) for n in papers]
        for fut in as_completed(futures):
            try:
                node, url = fut.result()
                if url:
                    node["url"] = url
            except Exception:
                print(f"论文链接补全任务异常: {traceback.format_exc()}")

    return tree
