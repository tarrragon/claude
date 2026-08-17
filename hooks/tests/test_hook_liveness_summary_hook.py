#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook-liveness-summary-hook.py 測試

驗證彙整入口正確區分「已載入 / 本 session 從未觸發 / 未涵蓋（無探針）」
三類清單，且不誤把當前（剛啟動、尚無實質資料的）session 自己的檔案
當作比對基準。
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).resolve().parent.parent
_HOOK_PATH = _HOOK_DIR / "hook-liveness-summary-hook.py"

_spec = importlib.util.spec_from_file_location("hook_liveness_summary", _HOOK_PATH)
summary_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summary_hook)

_test_logger = logging.getLogger("test-hook-liveness-summary")


def _write_settings(root: Path, hook_files):
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    hooks_entries = [
        {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/{}.py".format(name)}
        for name in hook_files
    ]
    settings = {"hooks": {"SessionStart": [{"hooks": hooks_entries}]}}
    (settings_dir / "settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def _write_hook_file(root: Path, name: str, covered: bool):
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    body = "run_hook_safely(main, '{}')\n".format(name) if covered else "pass\n"
    (hooks_dir / "{}.py".format(name)).write_text(body, encoding="utf-8")


def _write_liveness_file(root: Path, session_id: str, hook_names):
    liveness_dir = root / ".claude" / "hook-logs" / "_liveness"
    liveness_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"hook": name, "session_id": session_id, "pid": 1, "ts": "t"})
        for name in hook_names
    ]
    (liveness_dir / "{}.jsonl".format(session_id)).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


class TestRegisteredHookNames:
    def test_extracts_hooks_dir_py_files_only(self):
        settings = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"},
                            {
                                "command": "$CLAUDE_PROJECT_DIR/.claude/skills/x/hooks/bar.py"
                            },
                            {"command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/baz.py"},
                        ]
                    }
                ]
            }
        }
        names = summary_hook._registered_hook_names(settings)
        assert "foo" in names
        assert "baz" in names
        assert "bar" not in names


class TestCoveredByRunHookSafely:
    def test_distinguishes_covered_and_uncovered(self, tmp_path):
        _write_hook_file(tmp_path, "covered-hook", covered=True)
        _write_hook_file(tmp_path, "uncovered-hook", covered=False)

        covered = summary_hook._covered_by_run_hook_safely(
            tmp_path, {"covered-hook", "uncovered-hook", "missing-hook"}
        )

        assert covered == {"covered-hook"}


class TestMostRecentCompletedLivenessFile:
    def test_excludes_current_session_file(self, tmp_path):
        _write_liveness_file(tmp_path, "prev-session", ["hook-a"])
        _write_liveness_file(tmp_path, "current-session", ["hook-liveness-summary"])

        result = summary_hook._most_recent_completed_liveness_file(
            tmp_path, exclude_session_id="current-session"
        )

        assert result.stem == "prev-session"

    def test_returns_none_when_no_liveness_dir(self, tmp_path):
        result = summary_hook._most_recent_completed_liveness_file(
            tmp_path, exclude_session_id="anything"
        )
        assert result is None


class TestInvokedHookNames:
    def test_parses_jsonl_lines(self, tmp_path):
        _write_liveness_file(tmp_path, "s1", ["hook-a", "hook-b"])
        liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "s1.jsonl"

        invoked = summary_hook._invoked_hook_names(liveness_file)

        assert invoked == {"hook-a", "hook-b"}

    def test_skips_malformed_lines(self, tmp_path):
        liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"
        liveness_dir.mkdir(parents=True)
        f = liveness_dir / "s2.jsonl"
        f.write_text('not-json\n{"hook": "ok-hook"}\n', encoding="utf-8")

        invoked = summary_hook._invoked_hook_names(f)

        assert invoked == {"ok-hook"}


class TestMainEndToEnd:
    def test_main_reports_three_categories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            summary_hook, "get_project_root", lambda: tmp_path
        )
        monkeypatch.setenv(summary_hook.ENV_SESSION_ID, "current-session")
        monkeypatch.setattr(
            "sys.stdin", __import__("io").StringIO("")
        )

        _write_settings(tmp_path, ["loaded-hook", "silent-hook", "stub-hook"])
        _write_hook_file(tmp_path, "loaded-hook", covered=True)
        _write_hook_file(tmp_path, "silent-hook", covered=True)
        _write_hook_file(tmp_path, "stub-hook", covered=False)
        _write_liveness_file(tmp_path, "prev-session", ["loaded-hook"])

        exit_code = summary_hook.main()

        assert exit_code == 0

    def test_main_handles_missing_settings_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            summary_hook, "get_project_root", lambda: tmp_path
        )
        monkeypatch.setattr(
            "sys.stdin", __import__("io").StringIO("")
        )

        exit_code = summary_hook.main()

        assert exit_code == 0
