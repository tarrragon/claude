"""ticket track sessions 命令測試（multi-PM 協調層 Phase 1）。

驗證重點：
1. 正常表格輸出（FRESH session，session_id/name/age/status/tickets/files）
2. registry 缺檔 -> 空表 + exit 0（降級路徑）
3. registry JSON 解析失敗 -> 空表 + exit 0（降級路徑）
4. stale 判定：heartbeat 逾 30 分鐘 -> STALE；heartbeat 缺失/無法解析
   一律 fail-open 為 STALE
5. 同專案篩選：project 欄位不符當前 git toplevel 的 session 被過濾
6. --format json 輸出結構化資料

全數測試以 patch `_run_git` 模擬 git 拓樸 + tmp_path 假 registry 檔，
不觸碰真實 `.git/`。
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ticket_system.commands import track_sessions


NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ROOT = "/Users/tester/project/flutter_balance"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _write_registry(tmp_path: Path, sessions: dict) -> Path:
    registry_dir = tmp_path / ".git"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "pm-registry.json"
    registry_path.write_text(
        json.dumps({"schema_version": 1, "sessions": sessions}, ensure_ascii=False),
        encoding="utf-8",
    )
    return registry_path


def _fake_run_git(tmp_path: Path, *, toplevel: str = PROJECT_ROOT):
    """建立模擬 `_run_git` 的 side_effect，依 args 回傳對應假值。"""
    git_common_dir = str(tmp_path / ".git")

    def _run(*args: str):
        if args == ("rev-parse", "--git-common-dir"):
            return git_common_dir
        if args == ("rev-parse", "--show-toplevel"):
            return toplevel
        raise AssertionError(f"unexpected git args: {args}")

    return _run


def _run_sessions(capsys, *, fmt: str = "table") -> str:
    args = Namespace(format=fmt, _now=NOW)
    rc = track_sessions.execute_sessions(args)
    assert rc == 0
    return capsys.readouterr().out


class TestNormalTable:
    def test_fresh_session_shown_with_counts(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-a": {
                "name": "flutter-balance-b6",
                "project": PROJECT_ROOT,
                "registered_at": _iso(NOW - timedelta(minutes=10)),
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),
                "tickets": ["0.2.1-W3-999"],
                "files": ["a.py", "b.py"],
                "parent_session_id": None,
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)

        assert "session-a" in out
        assert "flutter-balance-b6" in out
        assert "FRESH" in out
        assert "STALE" not in out
        # age = 5 分鐘、tickets=1、files=2
        assert "5" in out


class TestDegradePaths:
    def test_missing_registry_file_empty_table_exit0(self, tmp_path, capsys):
        # tmp_path/.git 不存在 pm-registry.json（未呼叫 _write_registry）
        (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "無同專案 session" in out

    def test_json_parse_failure_degrades_to_empty(self, tmp_path, capsys):
        registry_dir = tmp_path / ".git"
        registry_dir.mkdir(parents=True, exist_ok=True)
        (registry_dir / "pm-registry.json").write_text("{not valid json", encoding="utf-8")
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "無同專案 session" in out

    def test_git_unavailable_degrades_to_empty(self, capsys):
        with patch.object(track_sessions, "_run_git", return_value=None):
            out = _run_sessions(capsys)
        assert "無同專案 session" in out


class TestStaleJudgement:
    def test_heartbeat_over_threshold_is_stale(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-b": {
                "name": "stale-session",
                "project": PROJECT_ROOT,
                "registered_at": _iso(NOW - timedelta(hours=2)),
                "heartbeat_ts": _iso(NOW - timedelta(minutes=45)),
                "tickets": [],
                "files": [],
                "parent_session_id": None,
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "STALE" in out
        assert "FRESH" not in out

    def test_missing_heartbeat_fail_open_stale(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-c": {
                "name": "no-heartbeat",
                "project": PROJECT_ROOT,
                "registered_at": _iso(NOW),
                "tickets": [],
                "files": [],
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "STALE" in out

    def test_malformed_heartbeat_fail_open_stale(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-d": {
                "name": "bad-heartbeat",
                "project": PROJECT_ROOT,
                "heartbeat_ts": "not-a-timestamp",
                "tickets": [],
                "files": [],
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "STALE" in out


class TestProjectFiltering:
    def test_other_project_session_filtered_out(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-here": {
                "name": "same-project",
                "project": PROJECT_ROOT,
                "heartbeat_ts": _iso(NOW - timedelta(minutes=1)),
                "tickets": [],
                "files": [],
            },
            "session-elsewhere": {
                "name": "other-project",
                "project": "/Users/tester/project/other_repo",
                "heartbeat_ts": _iso(NOW - timedelta(minutes=1)),
                "tickets": [],
                "files": [],
            },
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)
        assert "same-project" in out
        assert "other-project" not in out


class TestJsonFormat:
    def test_json_output_structure(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-a": {
                "name": "flutter-balance-b6",
                "project": PROJECT_ROOT,
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),
                "tickets": ["0.2.1-W3-999"],
                "files": ["a.py"],
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys, fmt="json")

        payload = json.loads(out)
        assert "sessions" in payload
        assert len(payload["sessions"]) == 1
        row = payload["sessions"][0]
        assert row["session_id"] == "session-a"
        assert row["status"] == "FRESH"
        assert row["tickets_count"] == 1
        assert row["files_count"] == 1
        assert row["heartbeat_age_minutes"] == 5
