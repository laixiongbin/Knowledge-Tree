"""通过 arXiv API 为论文节点补全 abs 链接。

说明：https://info.arxiv.org/help/api/user-manual.html
请控制请求频率；默认在两次请求之间 sleep，可用环境变量调整。
"""

from __future__ import annotations

import difflib
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

import requests

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"

# arXiv 建议 User-Agent 标明应用与联系方式
_DEFAULT_UA = "Knowledge-Tree/1.0 (arxiv API; contact: set ARXIV_USER_AGENT in .env)"


def _user_agent() -> str:
    return (os.getenv("ARXIV_USER_AGENT") or _DEFAULT_UA).strip() or _DEFAULT_UA


def _delay_seconds() -> float:
    try:
        v = float(os.getenv("ARXIV_QUERY_DELAY", "3.1"))
    except ValueError:
        v = 3.1
    return max(0.0, v)


def _max_papers() -> int:
    try:
        n = int(os.getenv("ARXIV_MAX_ENRICH", "40"))
    except ValueError:
        n = 40
    return max(1, min(n, 200))


def _normalize_title(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip().lower())
    return s


def _clean_query_title(title: str) -> str:
    """去掉易干扰检索的符号，控制长度。"""
    t = re.sub(r'[^\w\s\u4e00-\u9fff\-]', " ", title)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:280] if t else ""


def normalize_arxiv_abs_url(entry_id: str) -> str:
    """atom:id 形如 http://arxiv.org/abs/1706.03762v7 -> https://arxiv.org/abs/1706.03762"""
    entry_id = (entry_id or "").strip()
    m = re.search(r"arxiv\.org/abs/([^?\s#]+)", entry_id, re.I)
    if not m:
        return entry_id
    aid = m.group(1)
    aid = re.sub(r"v\d+$", "", aid)
    return f"https://arxiv.org/abs/{aid}"


def _pick_best_entry(entries: list, query_title: str) -> Optional[ET.Element]:
    if not entries:
        return None
    qn = _normalize_title(query_title)
    if not qn:
        return entries[0]
    best_el = None
    best_score = 0.0
    for ent in entries:
        t_el = ent.find(f"{ATOM}title")
        raw = (t_el.text or "").strip() if t_el is not None else ""
        # arXiv 标题里常有换行
        raw = re.sub(r"\s+", " ", raw)
        score = difflib.SequenceMatcher(None, qn, _normalize_title(raw)).ratio()
        if score > best_score:
            best_score = score
            best_el = ent
    # 分数过低说明检索跑偏，不采用（避免链到错误论文）
    if best_score >= 0.52:
        return best_el
    return None


def search_arxiv_abs_url(title: str, authors: Optional[str] = None) -> Optional[str]:
    """
    用标题（及可选作者）检索 arXiv，返回 https://arxiv.org/abs/... 或 None。
    """
    qtitle = _clean_query_title(title or "")
    if not qtitle:
        return None

    # 短语检索比散列 all:词 更不易跑偏；标题内双引号去掉避免截断查询
    phrase = qtitle.replace('"', " ").strip()
    phrase = re.sub(r"\s+", " ", phrase)
    if not phrase:
        return None

    parts = [f'all:"{phrase}"']
    if authors:
        au = _clean_query_title(authors)
        tokens = [x for x in au.replace(",", " ").split() if len(x) > 2 and re.match(r"^[A-Za-z\-]+$", x)]
        if tokens:
            parts.append(f"au:{tokens[0]}")

    title_only_query = f'all:"{phrase}"'

    def run_query(search_query: str) -> Optional[str]:
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": 5,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            r = requests.get(
                ARXIV_API,
                params=params,
                headers={"User-Agent": _user_agent()},
                timeout=45,
            )
            r.raise_for_status()
        except requests.RequestException:
            return None
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            return None
        entries = list(root.findall(f"{ATOM}entry"))
        if not entries:
            return None
        pick = _pick_best_entry(entries, title)
        if pick is None:
            return None
        id_el = pick.find(f"{ATOM}id")
        if id_el is None or not (id_el.text or "").strip():
            return None
        return normalize_arxiv_abs_url(id_el.text.strip())

    combined = " AND ".join(parts) if len(parts) > 1 else parts[0]
    if len(parts) > 1:
        hit = run_query(combined)
        if hit:
            return hit
        # 作者与 arXiv 署名不一致时 AND 常无结果；回退仅标题（两次请求间稍等，避免连击 API）
        d = _delay_seconds()
        if d > 0:
            time.sleep(min(d, 4.0))
        return run_query(title_only_query)
    return run_query(title_only_query)


def enrich_tree_with_arxiv(tree: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧调用：已改为 arXiv → Semantic Scholar → OpenAlex 链，见 paper_enrich。"""
    from paper_enrich import enrich_tree_with_literature

    return enrich_tree_with_literature(tree)
