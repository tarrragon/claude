#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook liveness 訊號測試

涵蓋：
- mark_hook_entry 寫入格式與 session_id 綁定
- run_hook_safely 於 main_func 之前無條件呼叫 mark_hook_entry（含 main_func
  拋例外時仍已寫入的情形，用以觀察「已進入但崩於 main() 中」）
- 迴歸釘子：delay=True 與 FILE_HANDLER_LEVEL=DEBUG 是「有檔即等於有呼叫」
  保證的實作前提，任何破壞此二者的改動必須紅燈
"""

import json
import logging

import pytest

from lib import hook_logging


@pytest.fixture
def liveness_dir(tmp_path, monkeypatch):
    """隔離 liveness 索引到 tmp_path，並回傳其路徑"""
    monkeypatch.setattr(hook_logging, "get_project_root", lambda: tmp_path)
    return tmp_path / ".claude" / "hook-logs" / hook_logging.LIVENESS_SUBDIR


class TestMarkHookEntry:
    def test_writes_one_jsonl_line_per_call(self, liveness_dir, monkeypatch):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "sess-abc")

        hook_logging.mark_hook_entry("example-hook")

        log_file = liveness_dir / "sess-abc.jsonl"
        assert log_file.exists(), "liveness 索引檔應已建立"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["hook"] == "example-hook"
        assert entry["session_id"] == "sess-abc"
        assert "pid" in entry and "ts" in entry

    def test_uses_session_id_env_var_for_filename_and_binding(
        self, liveness_dir, monkeypatch
    ):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "session-xyz")

        hook_logging.mark_hook_entry("another-hook")

        assert (liveness_dir / "session-xyz.jsonl").exists()

    def test_falls_back_to_unknown_session_when_env_missing(
        self, liveness_dir, monkeypatch
    ):
        monkeypatch.delenv(hook_logging.ENV_SESSION_ID, raising=False)

        hook_logging.mark_hook_entry("no-session-hook")

        log_file = liveness_dir / "{}.jsonl".format(hook_logging.UNKNOWN_SESSION_ID)
        assert log_file.exists()
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["session_id"] == hook_logging.UNKNOWN_SESSION_ID

    def test_two_hooks_same_session_append_to_same_file(
        self, liveness_dir, monkeypatch
    ):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "shared-session")

        hook_logging.mark_hook_entry("hook-a")
        hook_logging.mark_hook_entry("hook-b")

        log_file = liveness_dir / "shared-session.jsonl"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        hooks = {json.loads(line)["hook"] for line in lines}
        assert hooks == {"hook-a", "hook-b"}


class TestRunHookSafelyWritesLivenessBeforeMain:
    def test_liveness_entry_written_even_when_main_raises(
        self, liveness_dir, monkeypatch
    ):
        """main_func 崩潰不應阻止 liveness 訊號已寫入——這正是本票要區分的
        「已載入但崩於 main() 中」與「未被呼叫」兩種情形的關鍵斷言。"""
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "crash-session")

        def crashing_main() -> int:
            raise RuntimeError("boom")

        exit_code = hook_logging.run_hook_safely(crashing_main, "crashing-hook")

        assert exit_code == hook_logging.EXIT_ERROR
        log_file = liveness_dir / "crash-session.jsonl"
        assert log_file.exists(), "main_func 崩潰前，liveness 訊號應已落檔"
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["hook"] == "crashing-hook"

    def test_liveness_entry_written_on_success(self, liveness_dir, monkeypatch):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "ok-session")

        exit_code = hook_logging.run_hook_safely(lambda: 0, "ok-hook")

        assert exit_code == 0
        log_file = liveness_dir / "ok-session.jsonl"
        assert log_file.exists()


class TestLivenessRegressionGuards:
    """迴歸釘子：破壞這兩個常數會使『有檔即等於有呼叫』的既有保證靜默消失。"""

    def test_file_handler_level_is_debug(self):
        assert hook_logging.FILE_HANDLER_LEVEL == logging.DEBUG, (
            "FILE_HANDLER_LEVEL 若被提高（如改為 INFO），run_hook_safely 內"
            "既有的 DEBUG 級『Hook execution time』一行不再落檔，"
            "『有檔即等於有呼叫』的既有保證即靜默消失"
        )

    def test_file_handler_uses_delay_true_lazy_creation(
        self, tmp_path, monkeypatch
    ):
        """delay=True 使『有檔』等價於『有寫入』；若改為 delay=False，
        setup_hook_logging 呼叫當下即建檔，即使從未寫入任何一行，
        亦會被誤判為『已載入且執行中』。"""
        monkeypatch.setattr(hook_logging, "get_project_root", lambda: tmp_path)
        monkeypatch.delenv(hook_logging.ENV_HOOK_DEBUG, raising=False)

        logger = hook_logging.setup_hook_logging("lazy-hook")

        log_dir = tmp_path / ".claude" / "hook-logs" / "lazy-hook"
        existing_before_write = list(log_dir.glob("*.log"))
        assert existing_before_write == [], (
            "setup_hook_logging 呼叫後、尚未寫入任何日誌前，不應已建立日誌檔"
            "（delay=True 的直接可觀察後果）"
        )

        logger.debug("trigger lazy file creation")

        existing_after_write = list(log_dir.glob("*.log"))
        assert len(existing_after_write) == 1, "首次寫入後應已建立唯一日誌檔"
