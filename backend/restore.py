import json
import os
import threading
from typing import Any, Dict, Optional


class JSONStorage:
    """将多棵知识树以「树名 -> JSON 对象」形式存入单个 JSON 文件。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, Any]:
        if not os.path.isfile(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if not raw:
                    return {}
                data = json.loads(raw)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        abs_path = os.path.abspath(self.path)
        parent = os.path.dirname(abs_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        base = os.path.basename(abs_path)
        tmp = os.path.join(parent or ".", f".{base}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, abs_path)

    def read_all(self) -> Dict[str, Any]:
        with self._lock:
            return self._load()

    def read(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._load().get(name)

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._load()

    def create(self, name: str, data: Dict[str, Any]) -> None:
        with self._lock:
            all_data = self._load()
            all_data[name] = data
            self._save(all_data)

    def delete(self, name: str) -> bool:
        with self._lock:
            all_data = self._load()
            if name not in all_data:
                return False
            del all_data[name]
            self._save(all_data)
            return True
