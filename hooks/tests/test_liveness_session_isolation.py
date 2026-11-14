"""liveness 隔離：洩漏哨兵 E2 正向對照與 session id 前綴。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib import liveness_session_isolation as iso

_HOOKS_ROOT = Path(__file__).resolve().parents[1]
_LEAK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "from pathlib import Path;"
    "from lib.hook_logging import mark_hook_entry;"
    "mark_hook_entry('leak-probe', project_root=Path(sys.argv[2]))"
)


@pytest.fixture(autouse=True)
def _restore_test_run_env(monkeypatch):
    """take_snapshot 會改寫 HOOK_LIVENESS_TEST_RUN；還原以免干擾 conftest 的整體哨兵。"""
    monkeypatch.setenv(iso.ENV_TEST_RUN, os.environ.get(iso.ENV_TEST_RUN, "unset"))
    yield


def _bypass_write(real_root: Path, session_id: str) -> None:
    """繞過重導：subprocess 直接以 project_root 指向「真實根」寫 liveness。"""
    env = {**os.environ, iso.ENV_SESSION_ID: session_id}
    subprocess.run(
        [sys.executable, "-c", _LEAK_SCRIPT, str(_HOOKS_ROOT.parent), str(real_root)],
        env=env, check=True, capture_output=True,
    )


class TestSessionId:
    def test_current_test_session_uses_pytest_prefix(self):
        assert os.environ[iso.ENV_SESSION_ID].startswith(iso.SESSION_ID_PREFIX)


class TestLeakSentinel:
    def test_e2_bypass_write_is_judged_failure_then_clean_passes(self, tmp_path):
        fake_real = tmp_path / "real"
        session = SimpleNamespace(exitstatus=0)

        _bypass_write(fake_real, iso.SESSION_ID_PREFIX + "bypass")
        leaked = iso.apply_leak_sentinel(session, fake_real)
        assert [p.name for p in leaked] == ["pytest-bypass.jsonl"]
        assert session.exitstatus == 1

        for p in leaked:
            p.unlink()
        session2 = SimpleNamespace(exitstatus=0)
        assert iso.apply_leak_sentinel(session2, fake_real) == []
        assert session2.exitstatus == 0

    def test_real_session_file_is_not_a_leak(self, tmp_path):
        _bypass_write(tmp_path, "real-session-abc")
        assert iso.find_leaked_liveness_files(tmp_path) == []

    def test_missing_liveness_dir_is_clean(self, tmp_path):
        assert iso.find_leaked_liveness_files(tmp_path) == []


class TestSnapshotSentinel:
    """前後快照比對：不限 pytest- 前綴，真實 session_id 形式的洩漏亦判紅。"""

    def test_real_session_id_leak_is_judged_failure(self, tmp_path):
        real = tmp_path / "real"
        before = iso.take_snapshot(real)
        _bypass_write(real, "0f1e2d3c-real-session-id")
        session = SimpleNamespace(exitstatus=0)
        leaks = iso.apply_snapshot_sentinel(session, real, before, "0f1e2d3c-real-session-id")
        assert leaks == ["_liveness/0f1e2d3c-real-session-id.jsonl"]
        assert session.exitstatus == 1

    def test_pytest_prefix_leak_still_judged_failure(self, tmp_path):
        real = tmp_path / "real"
        before = iso.take_snapshot(real)
        _bypass_write(real, iso.SESSION_ID_PREFIX + "x")
        assert iso.diff_snapshots(before, iso.take_snapshot(real), None) == [
            "_liveness/pytest-x.jsonl"
        ]

    def test_unrelated_parallel_session_is_not_a_leak(self, tmp_path):
        real = tmp_path / "real"
        before = iso.take_snapshot(real)
        _bypass_write(real, "other-parallel-session")
        session = SimpleNamespace(exitstatus=0)
        assert iso.apply_snapshot_sentinel(session, real, before, "my-real-id") == []
        assert session.exitstatus == 0

    def test_new_hook_logs_subdir_is_a_leak(self, tmp_path):
        real = tmp_path / "real"
        before = iso.take_snapshot(real)
        (real / ".claude" / "hook-logs" / "some-hook").mkdir(parents=True)
        assert iso.diff_snapshots(before, iso.take_snapshot(real), None) == [
            "hook-logs/some-hook"
        ]


REAL_ID = "caller-real-id"


def _append_raw(root: Path, session_id: str, text: str) -> None:
    liveness = root / ".claude" / "hook-logs" / "_liveness"
    liveness.mkdir(parents=True, exist_ok=True)
    with open(liveness / (session_id + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(text)


def _line(**fields) -> str:
    return json.dumps({"hook": "h", **fields}) + "\n"


class TestTestRunMarker:
    """呼叫者 id 檔增長：以 test_run 標記區分測試寫入與呼叫者正常寫入。"""

    def _snap(self, root, monkeypatch):
        monkeypatch.delenv(iso.ENV_TEST_RUN, raising=False)
        monkeypatch.setenv(iso.ENV_TEST_RUN, "restore-me")  # teardown 還原
        return iso.take_snapshot(root)

    def _diff(self, before, root):
        after = iso.take_snapshot(root, root, before[iso.TEST_RUN_KEY])
        return iso.diff_snapshots(before, after, REAL_ID)

    def test_caller_normal_write_without_test_run_is_not_leak(self, tmp_path, monkeypatch):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, _line(session_id=REAL_ID))
        assert self._diff(before, tmp_path) == []

    def test_other_test_run_is_not_leak(self, tmp_path, monkeypatch):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, _line(test_run="another-run"))
        assert self._diff(before, tmp_path) == []

    def test_matching_test_run_is_leak(self, tmp_path, monkeypatch):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, _line(test_run=before[iso.TEST_RUN_KEY]))
        assert self._diff(before, tmp_path) == ["_liveness/" + REAL_ID + ".jsonl"]

    def test_partial_trailing_line_is_ignored(self, tmp_path, monkeypatch):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, _line(a=1) + '{"hook": "h", "test_ru')
        assert self._diff(before, tmp_path) == []

    def test_leading_partial_line_is_ignored(self, tmp_path, monkeypatch):
        _append_raw(tmp_path, REAL_ID, '{"hook": "h", "ts": "20')
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, '26"}\n')
        assert self._diff(before, tmp_path) == []

    def test_leading_partial_line_then_marked_full_line_is_leak(self, tmp_path, monkeypatch):
        _append_raw(tmp_path, REAL_ID, '{"hook": "h", "ts": "20')
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, '26"}\n' + _line(test_run=before[iso.TEST_RUN_KEY]))
        assert self._diff(before, tmp_path) == ["_liveness/" + REAL_ID + ".jsonl"]

    def test_corrupt_complete_line_is_leak(self, tmp_path, monkeypatch, capsys):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, "not-json{{\n")
        assert self._diff(before, tmp_path) == ["_liveness/" + REAL_ID + ".jsonl"]
        assert "fail-closed" in capsys.readouterr().err

    def test_unreadable_file_is_leak(self, tmp_path, monkeypatch, capsys):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, REAL_ID, _line(a=1))
        after = iso.take_snapshot(tmp_path, tmp_path, before[iso.TEST_RUN_KEY])
        after[iso.REAL_ROOT_KEY] = str(tmp_path / "missing-root")
        assert iso.diff_snapshots(before, after, REAL_ID) == ["_liveness/" + REAL_ID + ".jsonl"]
        assert "fail-closed" in capsys.readouterr().err

    def test_pytest_prefix_and_hook_logs_still_leak(self, tmp_path, monkeypatch):
        before = self._snap(tmp_path, monkeypatch)
        _append_raw(tmp_path, "pytest-z", _line(a=1))
        (tmp_path / ".claude" / "hook-logs" / "new-hook").mkdir()
        assert self._diff(before, tmp_path) == ["_liveness/pytest-z.jsonl", "hook-logs/new-hook"]

    def test_shared_root_file_content_is_read(self, tmp_path, monkeypatch):
        real, shared = tmp_path / "wt", tmp_path / "main"
        real.mkdir()
        shared.mkdir()
        monkeypatch.setenv(iso.ENV_TEST_RUN, "restore-me")
        before = iso.take_snapshot(real, shared)
        _append_raw(shared, REAL_ID, _line(a=1))
        after = iso.take_snapshot(real, shared, before[iso.TEST_RUN_KEY])
        assert iso.diff_snapshots(before, after, REAL_ID) == []
        _append_raw(shared, REAL_ID, _line(test_run=before[iso.TEST_RUN_KEY]))
        after = iso.take_snapshot(real, shared, before[iso.TEST_RUN_KEY])
        assert iso.diff_snapshots(before, after, REAL_ID) == [
            "shared:_liveness/" + REAL_ID + ".jsonl"
        ]


class TestSharedRootFirstLevel:
    """共用根第一層新增項目不判定；測試根照舊；有 marker 的 _liveness 紀錄仍判紅。"""

    def _roots(self, tmp_path, monkeypatch):
        real, shared = tmp_path / "wt", tmp_path / "main"
        for r in (real, shared):
            (r / ".claude" / "hook-logs").mkdir(parents=True)
        monkeypatch.setenv(iso.ENV_TEST_RUN, "restore-me")
        return real, shared, iso.take_snapshot(real, shared)

    def _diff(self, real, shared, before):
        after = iso.take_snapshot(real, shared, before[iso.TEST_RUN_KEY])
        return iso.diff_snapshots(before, after, REAL_ID)

    def test_shared_first_level_without_marker_is_not_leak(self, tmp_path, monkeypatch):
        real, shared, before = self._roots(tmp_path, monkeypatch)
        (shared / ".claude" / "hook-logs" / "pre-fix-evaluation-1.json").write_text("{}")
        assert self._diff(real, shared, before) == []

    def test_test_root_first_level_is_leak(self, tmp_path, monkeypatch):
        real, shared, before = self._roots(tmp_path, monkeypatch)
        (real / ".claude" / "hook-logs" / "new-item.json").write_text("{}")
        assert self._diff(real, shared, before) == ["hook-logs/new-item.json"]

    def test_shared_first_level_plus_marked_liveness_reports_liveness_only(self, tmp_path, monkeypatch):
        real, shared, before = self._roots(tmp_path, monkeypatch)
        (shared / ".claude" / "hook-logs" / "pre-fix-evaluation-1.json").write_text("{}")
        _append_raw(shared, REAL_ID, _line(test_run=before[iso.TEST_RUN_KEY]))
        assert self._diff(real, shared, before) == ["shared:_liveness/" + REAL_ID + ".jsonl"]


class TestMarkHookEntryTestRun:
    def _entry(self, tmp_path, env):
        full = {k: v for k, v in os.environ.items() if k != iso.ENV_TEST_RUN}
        full.update(env)
        full[iso.ENV_SESSION_ID] = "marker-sid"
        subprocess.run(
            [sys.executable, "-c", _LEAK_SCRIPT, str(_HOOKS_ROOT.parent), str(tmp_path)],
            env=full, check=True, capture_output=True,
        )
        f = tmp_path / ".claude" / "hook-logs" / "_liveness" / "marker-sid.jsonl"
        return json.loads(f.read_text().splitlines()[-1])

    def test_env_set_writes_test_run(self, tmp_path):
        assert self._entry(tmp_path, {iso.ENV_TEST_RUN: "run-1"})["test_run"] == "run-1"

    def test_env_unset_keeps_fields(self, tmp_path):
        entry = self._entry(tmp_path, {})
        assert "test_run" not in entry
        assert set(entry) == {"hook", "session_id", "pid", "ts"}


def test_lib_and_ticket_copies_are_identical():
    lib_copy = Path(iso.__file__).resolve()
    ticket_copy = lib_copy.parents[1] / "skills" / "ticket" / "liveness_session_isolation.py"
    assert lib_copy.read_bytes() == ticket_copy.read_bytes()
