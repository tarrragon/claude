"""hook_logging 寫入路徑的 test_run 帳本與洩漏哨兵（3.4.0-W1-326）。

帳本只在寫入路徑（setup_hook_logging 建 handler、save_check_log 寫檔）記帳；
唯讀解析（_default_log_root、get_hook_log_dir）不記帳，避免誤紅。
"""

import os
from pathlib import Path

import pytest

from lib import hook_logging as hl
from lib import liveness_session_isolation as iso

LEDGER_KEY = "shared:_liveness/" + hl.WRITE_LEDGER_NAME


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """real（測試根）與 shared（共用根）分離；未隔離、有 test_run 的環境。"""
    real, shared = tmp_path / "wt", tmp_path / "main"
    for r in (real, shared):
        (r / ".claude" / "hook-logs").mkdir(parents=True)
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv(iso.ENV_TEST_RUN, "restore-me")  # teardown 還原 take_snapshot 的改寫
    monkeypatch.setattr(hl, "_default_log_root", lambda: shared)
    return real, shared


def _snapshot(real, shared):
    return iso.take_snapshot(real, shared)


def _diff(real, shared, before):
    after = iso.take_snapshot(real, shared, before[iso.TEST_RUN_KEY])
    return iso.diff_snapshots(before, after, "caller-real-id")


class TestPositiveControl:
    def test_save_check_log_unisolated_is_leak(self, roots):
        real, shared = roots
        before = _snapshot(real, shared)
        hl.save_check_log("probe-hook", "x\n")
        assert _diff(real, shared, before) == [LEDGER_KEY]

    def test_setup_hook_logging_unisolated_is_leak(self, roots):
        real, shared = roots
        before = _snapshot(real, shared)
        hl.setup_hook_logging("probe-hook")
        assert _diff(real, shared, before) == [LEDGER_KEY]


class TestNegativeControl:
    def test_other_session_write_is_not_leak(self, roots, monkeypatch):
        real, shared = roots
        before = _snapshot(real, shared)
        monkeypatch.setenv(iso.ENV_TEST_RUN, "other-session-run")
        hl.save_check_log("probe-hook", "x\n")
        assert (shared / ".claude" / "hook-logs" / "_liveness" / hl.WRITE_LEDGER_NAME).exists()
        assert _diff(real, shared, before) == []

    def test_write_without_test_run_env_is_not_leak(self, roots, monkeypatch):
        real, shared = roots
        before = _snapshot(real, shared)
        monkeypatch.delenv(iso.ENV_TEST_RUN)
        hl.save_check_log("probe-hook", "x\n")
        assert _diff(real, shared, before) == []

    def test_isolated_write_is_not_leak(self, roots, monkeypatch):
        real, shared = roots
        before = _snapshot(real, shared)
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
        hl.save_check_log("probe-hook", "x\n")
        hl.setup_hook_logging("probe-hook")
        assert not (shared / ".claude" / "hook-logs" / "_liveness").exists()
        assert _diff(real, shared, before) == []

    def test_read_only_resolution_is_not_leak(self, roots):
        real, shared = roots
        before = _snapshot(real, shared)
        hl._default_log_root()
        hl.get_hook_log_dir("probe-hook")
        assert _diff(real, shared, before) == []


class TestLedgerFailureIsNonFatal:
    def test_failure_writes_stderr_and_main_flow_continues(self, roots, capsys):
        real, shared = roots
        # _liveness 位置放一個普通檔，使帳本 mkdir 失敗（OSError）
        (shared / ".claude" / "hook-logs" / "_liveness").write_text("block")
        logger = hl.setup_hook_logging("probe-hook")
        hl.save_check_log("probe-hook", "payload\n")
        assert logger is not None
        log_file = next((shared / ".claude" / "hook-logs" / "probe-hook").glob("checks-*.log"))
        assert log_file.read_text(encoding="utf-8") == "payload\n"
        assert "[hook-logging] 寫入帳本失敗" in capsys.readouterr().err
