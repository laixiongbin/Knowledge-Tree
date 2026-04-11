"""OpenAlex Works API：跨学科文献元数据与 OA 链接。

文档：https://docs.openalex.org
建议在请求中携带 mailto=（环境变量 OPENALEX_MAILTO）以进入 polite pool。
"""

from __future__ import annotations

import difflib
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

OPENALEX_WORKS = "https://api.openalex.org/works"
TITLE_MATCH_MIN = 0.52

_DEFAULT_UA = "Knowledge-Tree/1.0 (OpenAlex; set OPENALEX_MAILTO in .env)"


def _user_agent() -> str:
    m = os.getenv("OPENALEX_MAILTO", "").strip()
    if m and "@" in m:
        return f"Knowledge-Tree/1.0 (mailto:{m})"
    return _DEFAULT_UA


def _normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _url_from_work(w: Dict[str, Any]) -> Optional[str]:
    oa = w.get("best_oa_location") or {}
    if isinstance(oa, dict):
        for key in ("pdf_url", "url", "landing_page_url"):
            u = oa.get(key)
            if u and isinstance(u, str) and u.strip().startswith("http"):
                return u.strip()
    pl = w.get("primary_location") or {}
    if isinstance(pl, dict):
        u = pl.get("landing_page_url")
        if u and isinstance(u, str) and u.strip().startswith("http"):
            return u.strip()
    doi = w.get("doi")
    if doi and isinstance(doi, str):
        d = doi.strip()
        if d.startswith("http"):
            return d
        return f"https://doi.org/{d.lstrip('/')}"
    return None


def _pick_best_work(results: List[Dict[str, Any]], query_title: str) -> Optional[Dict[str, Any]]:
    if not results:
        return None
    qn = _normalize_title(query_title)
    if not qn:
        return results[0]
    best = None
    best_score = 0.0
    for w in results:
        raw = (w.get("display_name") or w.get("title") or "").strip()
        raw = re.sub(r"\s+", " ", raw)
        score = difflib.SequenceMatcher(None, qn, _normalize_title(raw)).ratio()
        if score > best_score:
            best_score = score
            best = w
    if best_score >= TITLE_MATCH_MIN and best:
        return best
    return None


def _openalex_query_variants(title: str) -> List[str]:
    """多种检索串合并去重，提高命中率（如「BERT: 副标题」再搜副标题段）。"""
    title = (title or "").strip()
    if not title:
        return []
    out: List[str] = [title[:280]]
    if ":" in title:
        tail = title.split(":", 1)[1].strip()
        if len(tail) > 24 and tail[:120] not in title[:130]:
            out.append(tail[:280])
    # 去重保序
    seen = set()
    uniq: List[str] = []
    for q in out:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq


def _openalex_fetch_results(search_value: str, mailto: str) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"search": search_value, "per_page": 18}
    if mailto:
        params["mailto"] = mailto
    try:
        r = requests.get(
            OPENALEX_WORKS,
            params=params,
            headers={"User-Agent": _user_agent()},
            timeout=40,
        )
        r.raise_for_status()
    except requests.RequestException:
        return []
    try:
        payload = r.json()
    except ValueError:
        return []
    results = payload.get("results") or []
    return results if isinstance(results, list) else []


def search_best_literature_url(
    title: str,
    authors: Optional[str] = None,
    year: Optional[str] = None,
) -> Optional[str]:
    del authors, year
    title = (title or "").strip()
    if not title:
        return None

    mailto = (os.getenv("OPENALEX_MAILTO") or "").strip()
    merged: List[Dict[str, Any]] = []
    seen_ids = set()
    for i, q in enumerate(_openalex_query_variants(title)):
        if i:
            time.sleep(0.35)
        for w in _openalex_fetch_results(q, mailto):
            wid = w.get("id")
            if wid and wid not in seen_ids:
                seen_ids.add(wid)
                merged.append(w)
        if len(merged) >= 40:
            break

    best = _pick_best_work(merged, title)
    if not best:
        return None
    return _url_from_work(best)
