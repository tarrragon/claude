"""session_state_key 單元測試：鍵取自 hook 輸入的 session_id，取不到時 fail-open。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.session_state_key import session_state_key, session_state_path


def test_key_from_session_id():
    assert session_state_key({"session_id": "abc-123_X"}) == "abc-123_X"


def test_key_independent_of_ppid():
    """E1 對照：ppid 改變不影響鍵；session_id 改變才影響鍵。"""
    with patch("os.getppid", return_value=111):
        a = session_state_key({"session_id": "s1"})
    with patch("os.getppid", return_value=222):
        b = session_state_key({"session_id": "s1"})
        c = session_state_key({"session_id": "s2"})
    assert a == b == "s1"
    assert c == "s2" and c != a


def test_key_sanitizes_path_chars():
    key = session_state_key({"session_id": "../../etc/passwd"})
    assert "/" not in key and ".." not in key
    assert key == "______etc_passwd"


def test_key_length_capped():
    assert len(session_state_key({"session_id": "a" * 500})) == 128


def test_missing_session_id_returns_none_warns_and_writes_stderr(capsys):
    logger = MagicMock()
    for bad in ({}, {"session_id": ""}, {"session_id": "   "}, {"session_id": 123}, None):
        assert session_state_key(bad, logger) is None
    assert logger.warning.call_count == 5
    assert "session_id" in capsys.readouterr().err


def test_no_ppid_fallback_when_missing():
    with patch("os.getppid", return_value=999):
        assert session_state_path("/tmp/x-{session_id}", {}) is None


def test_path_expands_template():
    assert session_state_path("/tmp/x-{session_id}.json", {"session_id": "s9"}) == Path("/tmp/x-s9.json")
    assert os.path.basename(str(session_state_path("/tmp/y-{session_id}", {"session_id": "a/b"}))) == "y-a_b"
