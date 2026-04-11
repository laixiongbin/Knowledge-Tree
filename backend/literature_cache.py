from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from hashlib import sha1
from typing import Any, Dict, Optional, Tuple


_LOCK = threading.Lock()


def _cache_path() -> str:
    p = (os.getenv("LITERATURE_CACHE_FILE") or "").strip()
    if p:
        return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "literature_cache.json")


def _enabled() -> bool:
    v = (os.getenv("LITERATURE_CACHE", "1") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _ttl_seconds() -> int:
    raw = (os.getenv("LITERATURE_CACHE_TTL_SECONDS", "604800") or "").strip()  # 7 days
    try:
        n = int(raw)
    except ValueError:
        n = 604800
    return max(60, n)


def _make_key(title: str, authors: Optional[str], year: Optional[str]) -> str:
    t = (title or "").strip().lower()
    a = (authors or "").strip().lower()
    y = (year or "").strip().lower()
    blob = f"{t}\n{a}\n{y}".encode("utf-8", errors="ignore")
    return sha1(blob).hexdigest()


def _read_all() -> Dict[str, Any]:
    path = _cache_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _write_all(data: Dict[str, Any]) -> None:
    path = _cache_path()
    tmp = f"{path}.tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@dataclass(frozen=True)
class CacheHit:
    url: Optional[str]
    is_negative: bool


def get_cached(title: str, authors: Optional[str], year: Optional[str]) -> Optional[CacheHit]:
    if not _enabled():
        return None
    key = _make_key(title, authors, year)
    ttl = _ttl_seconds()
    now = int(time.time())
    with _LOCK:
        all_data = _read_all()
        ent = all_data.get(key)
        if not isinstance(ent, dict):
            return None
        ts = ent.get("ts")
        if not isinstance(ts, int) or now - ts > ttl:
            return None
        if ent.get("neg") is True:
            return CacheHit(url=None, is_negative=True)
        url = ent.get("url")
        if isinstance(url, str) and url.strip():
            return CacheHit(url=url.strip(), is_negative=False)
        return None


def put_cached(title: str, authors: Optional[str], year: Optional[str], url: Optional[str]) -> None:
    if not _enabled():
        return
    key = _make_key(title, authors, year)
    now = int(time.time())
    payload: Dict[str, Any] = {"ts": now}
    if url and isinstance(url, str) and url.strip():
        payload["url"] = url.strip()
        payload["neg"] = False
    else:
        payload["url"] = ""
        payload["neg"] = True
    with _LOCK:
        all_data = _read_all()
        all_data[key] = payload
        _write_all(all_data)

