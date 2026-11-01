"""In-process investigation workers. One API process, no external queue."""

from __future__ import annotations

import threading

_CAPACITY = 2
_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}
_LIVE: set[str] = set()
_PENDING = 0
_THREADS: dict[str, threading.Thread] = {}
_ORPHANS: set[str] = set()


def lock(key: str) -> threading.Lock:
    with _GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def is_live(run_id: str) -> bool:
    return is_active(run_id)


def is_active(run_id: str) -> bool:
    """True only while this process still has the worker registered or running."""
    with _GUARD:
        if run_id in _LIVE:
            return True
        thread = _THREADS.get(run_id)
        return thread is not None and thread.is_alive()


def reserve() -> bool:
    """Hold one of the two Cortex slots before the RUNNING row is inserted."""
    global _PENDING
    with _GUARD:
        if len(_LIVE) + _PENDING >= _CAPACITY:
            return False
        _PENDING += 1
        return True


def cancel_reservation() -> None:
    global _PENDING
    with _GUARD:
        _PENDING = max(0, _PENDING - 1)


def activate(run_id: str, work) -> threading.Thread:
    global _PENDING

    def target() -> None:
        try:
            work()
        finally:
            with _GUARD:
                _LIVE.discard(run_id)

    with _GUARD:
        _PENDING = max(0, _PENDING - 1)
        _LIVE.add(run_id)
        thread = threading.Thread(target=target, name=f"analysis-{run_id[:8]}", daemon=True)
        _THREADS[run_id] = thread
    thread.start()
    return thread


def claim_orphan(run_id: str) -> bool:
    with _GUARD:
        if run_id in _ORPHANS or run_id in _LIVE:
            return False
        _ORPHANS.add(run_id)
        return True


def wait(run_id: str, timeout: float) -> None:
    thread = _THREADS.get(run_id)
    if thread:
        thread.join(timeout)
