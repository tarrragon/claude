"""ticket 套件的 liveness 隔離：session id 前綴與洩漏哨兵（E2 正向對照）。"""

import os
from types import SimpleNamespace

import liveness_session_isolation as iso


def test_session_uses_pytest_prefix():
    assert os.environ[iso.ENV_SESSION_ID].startswith(iso.SESSION_ID_PREFIX)


def test_sentinel_fails_on_leak_and_passes_when_removed(tmp_path):
    liveness = tmp_path / iso.LIVENESS_RELATIVE
    liveness.mkdir(parents=True)
    leak = liveness / "pytest-1-abcd.jsonl"
    leak.write_text("{}\n", encoding="utf-8")
    (liveness / "real-session.jsonl").write_text("{}\n", encoding="utf-8")

    session = SimpleNamespace(exitstatus=0)
    assert iso.apply_leak_sentinel(session, tmp_path) == [leak]
    assert session.exitstatus == 1

    leak.unlink()
    session = SimpleNamespace(exitstatus=0)
    assert iso.apply_leak_sentinel(session, tmp_path) == []
    assert session.exitstatus == 0
