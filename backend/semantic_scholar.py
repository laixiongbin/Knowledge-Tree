"""Semantic Scholar Graph API：理工科文献检索与链接补全。

文档：https://api.semanticscholar.org/api-docs/
建议配置 SEMANTIC_SCHOLAR_API_KEY 以提高限额。
"""

from __future__ import annotations

import difflib
import os
import re
from typing import Any, Dict, List, Optional

import requests

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
TITLE_MATCH_MIN = 0.52

_DEFAULT_UA = "Knowledge-Tree/1.0 (Semantic Scholar; set SEMANTIC_SCHOLAR_API_KEY / OPENALEX_MAILTO in .env)"


def _user_agent() -> str:
    m = os.getenv("OPENALEX_MAILTO", "").strip()
    if m and "@" in m:
        return f"Knowledge-Tree/1.0 (mailto:{m})"
    return _DEFAULT_UA


def _normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _pick_best_paper(papers: List[Dict[str, Any]], query_title: str) -> Optional[Dict[str, Any]]:
    if not papers:
        return None
    qn = _normalize_title(query_title)
    if not qn:
        return papers[0]
    best = None
    best_score = 0.0
    for p in papers:
        raw = (p.get("title") or "").strip()
        raw = re.sub(r"\s+", " ", raw)
        score = difflib.SequenceMatcher(None, qn, _normalize_title(raw)).ratio()
        if score > best_score:
            best_score = score
            best = p
    if best_score >= TITLE_MATCH_MIN and best:
        return best
    return None


def _url_from_paper(p: Dict[str, Any]) -> Optional[str]:
    oa = p.get("openAccessPdf")
    if isinstance(oa, dict):
        u = oa.get("url")
        if u and isinstance(u, str) and u.strip().startswith("http"):
            return u.strip()
    ext = p.get("externalIds")
    if isinstance(ext, dict):
        ax = ext.get("ArXiv") or ext.get("arXiv")
        if ax:
            aid = str(ax).strip()
            if aid:
                return f"https://arxiv.org/abs/{aid}"
    u = p.get("url")
    if u and isinstance(u, str) and u.strip().startswith("http"):
        return u.strip()
    return None


def search_best_literature_url(
    title: str,
    authors: Optional[str] = None,
    year: Optional[str] = None,
) -> Optional[str]:
    """
    按标题检索，返回 PDF/着陆页/arxiv 等可点击链接；匹配不足则 None。
    authors/year 当前仅预留，查询仍以标题为主（S2 的 query 为全文检索）。
    """
    del authors, year  # 预留
    title = (title or "").strip()
    if not title:
        return None

    params = {
        "query": title[:512],
        "limit": 8,
        "fields": "title,url,year,openAccessPdf,externalIds",
    }
    headers = {"User-Agent": _user_agent()}
    key = (os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    if key:
        headers["x-api-key"] = key

    try:
        r = requests.get(
            S2_SEARCH,
            params=params,
            headers=headers,
            timeout=40,
        )
        if r.status_code == 429:
            return None
        r.raise_for_status()
    except requests.RequestException:
        return None

    try:
        payload = r.json()
    except ValueError:
        return None

    papers = payload.get("data") or []
    if not isinstance(papers, list):
        return None
    best = _pick_best_paper(papers, title)
    if not best:
        return None
    return _url_from_paper(best)
