"""In-memory caps, duplicate suppression, and short-lived thread caches."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
import uuid
from dataclasses import dataclass

from app.agents.faults import ApiFault
from app.agents.registry import MAX_IN_FLIGHT
from app.common.agent_availability import bind

_HOUR = 3600.0
_DAY = 86400.0
_TEN_MINUTES = 600.0
_RUNS_PER_HANDLE = 10
_NEW_CONVERSATIONS = 20
_RUNS_PER_HOUR = 60
_RUNS_PER_DAY = 300
_GATE_FAILURES = 3
_GATE_COOLDOWN = 30.0
_PARSE_TTL = 1800.0
_PARSE_LIMIT = 50
_THREAD_TTL = 2.0
_THREAD_LIMIT = 100
_IDEMPOTENCY_TTL = 3600.0


@dataclass
class _Reservation:
    kind: str
    handle_key: str | None
    created: float


@dataclass
class _InFlight:
    run_token: str
    thread_id: int
    user_message_id: str
    created: float


@dataclass
class _Idem:
    fingerprint: str
    status: int
    body: dict
    created: float


@dataclass
class _Parsed:
    content: dict
    created: float


class Limits:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client_locks: dict[str, threading.Lock] = {}
        self._reservations: dict[str, _Reservation] = {}
        self._inflight: dict[str, _InFlight] = {}
        self._runs: list[float] = []
        self._creates: list[float] = []
        self._by_handle: dict[str, list[float]] = {}
        self._idem: dict[str, _Idem] = {}
        self._threads: dict[int, tuple[float, object]] = {}
        self._parsed: dict[tuple[int, str], _Parsed] = {}
        self._runs_by_message: dict[tuple[int, str], str] = {}
        self._active: dict[int, str] = {}
        self._logged: dict[str, str] = {}
        self._failures = 0
        self._gate_until = 0.0

    def reset(self) -> None:
        with self._lock:
            self.__init__()

    def client_lock(self, client_id: str) -> threading.Lock:
        with self._lock:
            lock = self._client_locks.get(client_id)
            if lock is None:
                lock = threading.Lock()
                self._client_locks[client_id] = lock
            return lock

    def availability(self) -> str:
        with self._lock:
            if self._gate_open(time.monotonic()):
                return "unavailable"
            if len(self._inflight) + len(self._reservations) >= MAX_IN_FLIGHT:
                return "busy"
            return "available"

    def note_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= _GATE_FAILURES:
                self._gate_until = time.monotonic() + _GATE_COOLDOWN

    def note_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._gate_until = 0.0

    def reserve(self, kind: str, handle: str | None) -> str:
        now = time.monotonic()
        with self._lock:
            self._check(kind, handle, now)
            reservation_id = f"pending-{uuid.uuid4().hex}"
            handle_key = _handle_key(handle) if handle else None
            self._reservations[reservation_id] = _Reservation(kind, handle_key, now)
            return reservation_id

    def release(self, reservation_id: str) -> None:
        with self._lock:
            self._reservations.pop(reservation_id, None)

    def fulfill(
        self,
        reservation_id: str,
        *,
        snowflake_run_id: str,
        run_token: str,
        thread_id: int,
        user_message_id: str,
        handle: str | None,
    ) -> None:
        now = time.monotonic()
        with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            self._inflight[snowflake_run_id] = _InFlight(run_token, thread_id, str(user_message_id), now)
            self._runs.append(now)
            self._runs_by_message[(thread_id, str(user_message_id))] = run_token
            self._active[thread_id] = run_token
            if reservation and reservation.kind == "create":
                self._creates.append(now)
            handle_key = _handle_key(handle) if handle else None
            if handle_key is None and reservation is not None:
                handle_key = reservation.handle_key
            if handle_key:
                self._by_handle.setdefault(handle_key, []).append(now)
            self._failures = 0
            self._gate_until = 0.0

    def note_terminal(self, snowflake_run_id: str) -> None:
        with self._lock:
            self._inflight.pop(snowflake_run_id, None)

    def active_token(self, thread_id: int) -> str | None:
        with self._lock:
            return self._active.get(thread_id)

    def remembered_run(self, thread_id: int, user_message_id: str) -> str | None:
        with self._lock:
            return self._runs_by_message.get((thread_id, str(user_message_id)))

    def cached_thread(self, thread_id: int):
        now = time.monotonic()
        with self._lock:
            hit = self._threads.get(thread_id)
            if not hit or now - hit[0] > _THREAD_TTL:
                return None
            return hit[1]

    def store_thread(self, thread_id: int, view: object) -> None:
        now = time.monotonic()
        with self._lock:
            self._threads[thread_id] = (now, view)
            if len(self._threads) > _THREAD_LIMIT:
                oldest = min(self._threads, key=lambda key: self._threads[key][0])
                self._threads.pop(oldest, None)

    def drop_thread(self, thread_id: int) -> None:
        with self._lock:
            self._threads.pop(thread_id, None)

    def cached_parse(self, thread_id: int, message_id: str) -> dict | None:
        now = time.monotonic()
        with self._lock:
            hit = self._parsed.get((thread_id, message_id))
            if not hit or now - hit.created > _PARSE_TTL:
                self._parsed.pop((thread_id, message_id), None)
                return None
            return hit.content

    def store_parse(self, thread_id: int, message_id: str, content: dict) -> None:
        now = time.monotonic()
        with self._lock:
            self._parsed[(thread_id, message_id)] = _Parsed(content, now)
            if len(self._parsed) > _PARSE_LIMIT:
                oldest = min(self._parsed, key=lambda key: self._parsed[key].created)
                self._parsed.pop(oldest, None)

    def recall(self, client_id: str, fingerprint: str) -> tuple[int, dict] | None:
        now = time.monotonic()
        with self._lock:
            self._purge_idem(now)
            entry = self._idem.get(client_id)
            if entry is None:
                return None
            if not hmac.compare_digest(entry.fingerprint, fingerprint):
                raise ApiFault(
                    409,
                    "IDEMPOTENCY_KEY_REUSED",
                    "This request id was already used for a different request.",
                )
            return entry.status, entry.body

    def remember(self, client_id: str, fingerprint: str, status: int, body: dict) -> None:
        now = time.monotonic()
        with self._lock:
            self._purge_idem(now)
            self._idem[client_id] = _Idem(fingerprint, status, body, now)

    def status_changed(self, run_key: str, status: str) -> bool:
        with self._lock:
            previous = self._logged.get(run_key)
            if previous == status:
                return False
            self._logged[run_key] = status
            if len(self._logged) > 500:
                self._logged.pop(next(iter(self._logged)))
            return True

    def _check(self, kind: str, handle: str | None, now: float) -> None:
        if self._gate_open(now):
            remaining = max(int((self._gate_until - now) * 1000), 1000)
            raise ApiFault(
                503,
                "AGENT_UNAVAILABLE",
                "The agent is temporarily unavailable.",
                retryable=True,
                retry_after_ms=remaining,
            )
        if len(self._inflight) + len(self._reservations) >= MAX_IN_FLIGHT:
            raise ApiFault(
                429,
                "AGENT_BUSY",
                "Too many agent runs are in progress.",
                retryable=True,
                retry_after_ms=5000,
            )
        hour = _retry_after(self._runs, now, _HOUR, _RUNS_PER_HOUR)
        day = _retry_after(self._runs, now, _DAY, _RUNS_PER_DAY)
        if hour is not None or day is not None:
            raise ApiFault(
                429,
                "AGENT_BUDGET_EXHAUSTED",
                "The agent run budget is exhausted.",
                retryable=True,
                retry_after_ms=hour or day,
            )
        if kind == "create":
            retry = _retry_after(self._creates, now, _TEN_MINUTES, _NEW_CONVERSATIONS)
            if retry is not None:
                raise ApiFault(
                    429,
                    "RATE_LIMITED",
                    "Too many new conversations. Try again shortly.",
                    retryable=True,
                    retry_after_ms=retry,
                )
            return
        retry = _retry_after(
            self._by_handle.setdefault(_handle_key(handle or ""), []),
            now,
            _TEN_MINUTES,
            _RUNS_PER_HANDLE,
        )
        if retry is not None:
            raise ApiFault(
                429,
                "RATE_LIMITED",
                "Too many runs for this conversation. Try again shortly.",
                retryable=True,
                retry_after_ms=retry,
            )

    def _gate_open(self, now: float) -> bool:
        return now < self._gate_until

    def _purge_idem(self, now: float) -> None:
        expired = [key for key, entry in self._idem.items() if now - entry.created > _IDEMPOTENCY_TTL]
        for key in expired:
            self._idem.pop(key, None)


def _handle_key(handle: str) -> str:
    return hashlib.sha256(handle.encode("utf-8")).hexdigest()[:16]


def _retry_after(events: list[float], now: float, window: float, limit: int) -> int | None:
    events[:] = [stamp for stamp in events if now - stamp < window]
    if len(events) < limit:
        return None
    oldest = min(events)
    return max(int((oldest + window - now) * 1000), 1000)


memory = Limits()
bind(memory.availability)
