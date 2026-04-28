from datetime import UTC

from app.infrastructure.clock import SystemClock
from app.infrastructure.id_generator import UlidIdGenerator


def test_system_clock_returns_aware_utc_now():
    c = SystemClock()
    n = c.now()
    assert n.tzinfo is not None
    assert n.tzinfo.utcoffset(n) == UTC.utcoffset(n)


def test_ulid_id_generator_emits_prefixed_ids():
    ids = UlidIdGenerator()
    s = ids.session_id()
    sh = ids.shot_id()
    e = ids.export_id()
    assert s.startswith("ses_") and len(s) == 4 + 26
    assert sh.startswith("shot_") and len(sh) == 5 + 26
    assert e.startswith("exp_") and len(e) == 4 + 26


def test_ulid_id_generator_emits_unique_ids():
    ids = UlidIdGenerator()
    seen = {ids.session_id() for _ in range(100)}
    assert len(seen) == 100
