"""Process-local TTL cache. Keys include the dataset promoted time."""

from __future__ import annotations

import hashlib
import json
import threading
import time


class TtlCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, int, object]] = {}

    def get(self, key: str):
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored, ttl, value = item
            age = now - stored
            if age > ttl:
                self._items.pop(key, None)
                return None
            return value, int(age), ttl

    def set(self, key: str, value, ttl: int) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), int(ttl), value)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


response_cache = TtlCache()
PROBE_TTL = 600
PROBE_KEY = "v2-dataset-probe"


def catalog_key(promoted_at) -> str:
    return f"v2-catalog|{promoted_at}"


def response_key(endpoint: str, params: dict, promoted_at) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"v2|{endpoint}|{promoted_at}|{digest}"
