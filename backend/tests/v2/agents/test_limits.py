import pytest

from app.agents.faults import ApiFault
from app.agents.limits import memory


def test_in_flight_cap_is_four():
    memory.reset()
    try:
        held = [memory.reserve("create", None) for _ in range(4)]
        with pytest.raises(ApiFault) as caught:
            memory.reserve("create", None)
        assert caught.value.code == "AGENT_BUSY"
        assert caught.value.retry_after_ms == 5000
        memory.release(held[0])
        memory.reserve("create", None)
    finally:
        memory.reset()


def test_duplicate_client_request_is_remembered():
    memory.reset()
    try:
        memory.remember("client-1", "fingerprint-a", 202, {"data": {"ok": True}})
        assert memory.recall("client-1", "fingerprint-a") == (202, {"data": {"ok": True}})
        with pytest.raises(ApiFault) as caught:
            memory.recall("client-1", "fingerprint-b")
        assert caught.value.code == "IDEMPOTENCY_KEY_REUSED"
    finally:
        memory.reset()
