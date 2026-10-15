"""dispatch_tracker _state_cache 以檔案路徑為鍵的契約測試（0.5.0-W1-264.6.1）。"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib import dispatch_tracker as dt

BASE_NS = 1_700_000_000_000_000_000


def _make_root(tmp_path: Path, tag: str, mtime_ns: int) -> Path:
    root = tmp_path / tag
    state_file = root / dt.STATE_FILE_RELATIVE
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"dispatches": [{"agent_description": tag}]}))
    os.utime(state_file, ns=(mtime_ns, mtime_ns))
    return root


def _tag(root: Path) -> str:
    return dt._read_state(root)["dispatches"][0]["agent_description"]


@pytest.fixture(autouse=True)
def _fresh_cache():
    dt.reset_cache()
    yield
    dt.reset_cache()


def test_two_roots_same_mtime_read_own_content(tmp_path):
    a = _make_root(tmp_path, "ROOT_A", BASE_NS)
    b = _make_root(tmp_path, "ROOT_B", BASE_NS)
    assert _tag(a) == "ROOT_A"
    assert _tag(b) == "ROOT_B"


def test_two_roots_mtime_differs_by_one_ns_read_own_content(tmp_path):
    a = _make_root(tmp_path, "ROOT_A", BASE_NS)
    b = _make_root(tmp_path, "ROOT_B", BASE_NS + 1)
    assert _tag(a) == "ROOT_A"
    assert _tag(b) == "ROOT_B"


def test_same_file_one_ns_change_is_reread(tmp_path):
    a = _make_root(tmp_path, "OLD", BASE_NS)
    assert _tag(a) == "OLD"
    state_file = a / dt.STATE_FILE_RELATIVE
    state_file.write_text(json.dumps({"dispatches": [{"agent_description": "NEW"}]}))
    os.utime(state_file, ns=(BASE_NS + 1, BASE_NS + 1))
    assert _tag(a) == "NEW"


def test_mutating_returned_object_does_not_affect_next_read(tmp_path):
    a = _make_root(tmp_path, "ROOT_A", BASE_NS)
    first = dt._read_state(a)
    first["dispatches"][0]["agent_description"] = "POLLUTED"
    first["dispatches"].append({"agent_description": "EXTRA"})
    second = dt._read_state(a)
    assert second is not first
    assert second["dispatches"] == [{"agent_description": "ROOT_A"}]


def test_write_invalidates_only_written_path(tmp_path):
    a = _make_root(tmp_path, "ROOT_A", BASE_NS)
    b = _make_root(tmp_path, "ROOT_B", BASE_NS)
    _tag(a)
    _tag(b)
    dt._write_state(a, {"dispatches": [{"agent_description": "A2"}]})
    assert dt.get_state_file_path(a) not in dt._state_cache
    assert dt.get_state_file_path(b) in dt._state_cache
    assert _tag(a) == "A2"


def test_reset_cache_clears_all_entries(tmp_path):
    a = _make_root(tmp_path, "ROOT_A", BASE_NS)
    b = _make_root(tmp_path, "ROOT_B", BASE_NS)
    _tag(a)
    _tag(b)
    dt.reset_cache()
    assert len(dt._state_cache) == 0
