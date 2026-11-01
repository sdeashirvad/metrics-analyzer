"""Process-local cooldown. One worker, no external store."""

from __future__ import annotations

import threading
import time


class Gate:
    def __init__(self, cooldown_seconds: float = 30) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._open_until = 0.0
        self._probing = False

    def allow(self) -> str:
        """primary, probe, or fallback. Only one probe runs at a time."""
        now = time.monotonic()
        with self._lock:
            if now < self._open_until or self._probing:
                return "fallback"
            if self._open_until > 0:
                self._probing = True
                return "probe"
            return "primary"

    def succeed(self) -> None:
        with self._lock:
            self._open_until = 0.0
            self._probing = False

    def fail(self) -> None:
        with self._lock:
            self._open_until = time.monotonic() + self.cooldown_seconds
            self._probing = False

    def cancel_probe(self) -> None:
        with self._lock:
            self._probing = False

    def serving_fallback(self) -> bool:
        now = time.monotonic()
        with self._lock:
            return now < self._open_until or self._probing

    def reset(self) -> None:
        with self._lock:
            self._open_until = 0.0
            self._probing = False


snowflake_gate = Gate(30)
cortex_gate = Gate(30)
