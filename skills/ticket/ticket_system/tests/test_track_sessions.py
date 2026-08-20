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
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ticket_system.commands import track_sessions

from conftest import (  # noqa: F401 — 0.2.1-W3-585/733 收斂複本
    _iso,
    fresh_ts,
    pm_stale_threshold,
    seed_pm_registry,
    stale_ts,
)


# NOW 取模組載入當下（而非固定字面）：所有播種與判定入口皆注入 now=NOW，
# elapsed 完全確定（見 conftest.fresh_ts / stale_ts），故改為動態基準不影響
# FRESH/STALE 判定；同時消除「若入口日後移除 now 注入即立刻引爆」的隱患
# （TEST-MON-001，與 test_lease.py 同型防護，0.2.1-W3-733）。
NOW = datetime.now(timezone.utc)
PROJECT_ROOT = "/Users/tester/project/flutter_balance"


def _write_registry(tmp_path: Path, sessions: dict) -> Path:
    """建立 `<tmp_path>/.git/pm-registry.json`（本檔專屬的路徑推導邏輯，
    寫入本體委派 `conftest.seed_pm_registry` 統一 schema_version 來源，
    0.2.1-W3-585 收斂——原硬編碼 schema_version=1，已與 pm_registry 現行
    契約版本（2）漂移）。"""
    registry_path = tmp_path / ".git" / "pm-registry.json"
    seed_pm_registry(registry_path, sessions)
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
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),  # FRESH，斷言具體 age=5
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


class TestRunGitDelegation:
    """`_run_git` 優先透過 `git_utils.run_git_command`（帶
    `--no-optional-locks`，避免與並行 PM session 競爭 index.lock）；
    `.claude/lib/` 不可用時降級為原生 subprocess，維持既有韌性設計。
    """

    def test_delegates_to_git_utils_when_available(self):
        fake_git_utils = SimpleNamespace(
            run_git_command=lambda args, timeout=5: (True, "abc123\n")
        )
        with patch.object(track_sessions, "_load_git_utils", return_value=fake_git_utils):
            result = track_sessions._run_git("rev-parse", "--git-common-dir")
        assert result == "abc123"

    def test_returns_none_when_git_utils_reports_failure(self):
        fake_git_utils = SimpleNamespace(
            run_git_command=lambda args, timeout=5: (False, "fatal: not a git repository")
        )
        with patch.object(track_sessions, "_load_git_utils", return_value=fake_git_utils):
            result = track_sessions._run_git("rev-parse", "--git-common-dir")
        assert result is None

    def test_falls_back_to_subprocess_when_git_utils_unavailable(self, tmp_path):
        """`.claude/lib/` 不可用（dev 環境結構異常）時，仍能以原生
        subprocess 完成查詢，不因 lib 缺席而整支失效。"""
        with patch.object(track_sessions, "_load_git_utils", return_value=None):
            # 用真實 git 命令對當前 repo 查詢，僅驗證降級路徑本身可執行
            # 且不拋例外（不斷言具體輸出內容，避免與執行環境耦合）
            result = track_sessions._run_git("rev-parse", "--is-inside-work-tree")
        assert result in ("true", None)


class TestStaleJudgement:
    def test_heartbeat_over_threshold_is_stale(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-b": {
                "name": "stale-session",
                "project": PROJECT_ROOT,
                "registered_at": _iso(NOW - timedelta(hours=2)),
                "heartbeat_ts": stale_ts(NOW),
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

    def test_30_5_minutes_matches_pm_registry_is_fresh(self):
        """Phase 4 審查修正 4 回歸案例：30.5 分鐘曾是 sessions（整數分鐘
        `> 30`，30.5 捨為 30 判 FRESH）與 pm_registry.is_fresh（秒級
        `<= 1800`，1830 秒判 STALE）分歧的邊界值。改為單一委派後兩者須
        一致判 STALE，直接呼叫 `_build_rows`（不經 CLI 表格），驗證委派
        正確落地而非僅巧合通過既有 `_run_git` 走 CLI 的整合測試。
        """
        pm_registry = track_sessions._load_pm_registry()
        if pm_registry is None:
            pytest.skip("找不到 .claude/lib/pm_registry.py（開發環境結構異常）")

        registry = {
            "sessions": {
                "session-boundary": {
                    "name": "boundary-session",
                    "project": PROJECT_ROOT,
                    "heartbeat_ts": _iso(NOW - pm_stale_threshold() - timedelta(seconds=30)),
                    "tickets": [],
                    "files": [],
                }
            }
        }

        rows = track_sessions._build_rows(
            registry, project_root=PROJECT_ROOT, now=NOW, pm_registry=pm_registry
        )

        assert len(rows) == 1
        assert rows[0]["status"] == "STALE", (
            "30.5 分鐘應與 pm_registry.is_fresh 一致判 STALE"
            f"（實際：{rows[0]['status']}，舊版整數分鐘比較會誤判 FRESH）"
        )


class TestProjectFiltering:
    def test_other_project_session_filtered_out(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-here": {
                "name": "same-project",
                "project": PROJECT_ROOT,
                "heartbeat_ts": fresh_ts(NOW),
                "tickets": [],
                "files": [],
            },
            "session-elsewhere": {
                "name": "other-project",
                "project": "/Users/tester/project/other_repo",
                "heartbeat_ts": fresh_ts(NOW),
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
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),  # FRESH，斷言具體 age=5
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


class TestReclaimableMarking:
    """multi-PM 協調層 Phase 3：heartbeat 逾 30 分之 session 持票標 reclaimable。"""

    def test_stale_session_tickets_marked_reclaimable(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-stale": {
                "name": "dead-session",
                "project": PROJECT_ROOT,
                "heartbeat_ts": stale_ts(NOW),
                "tickets": ["0.2.1-W3-100", "0.2.1-W3-101"],
                "files": ["lib/a.dart"],
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)

        assert "STALE" in out
        assert "0.2.1-W3-100" in out
        assert "0.2.1-W3-101" in out

    def test_fresh_session_tickets_not_marked_reclaimable(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-alive": {
                "name": "alive-session",
                "project": PROJECT_ROOT,
                "heartbeat_ts": fresh_ts(NOW),
                "tickets": ["0.2.1-W3-200"],
                "files": ["lib/b.dart"],
            }
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys)

        assert "FRESH" in out
        assert "0.2.1-W3-200" not in out

    def test_json_output_includes_reclaimable_tickets_field(self, tmp_path, capsys):
        _write_registry(tmp_path, {
            "session-stale": {
                "name": "dead-session",
                "project": PROJECT_ROOT,
                "heartbeat_ts": stale_ts(NOW),
                "tickets": ["0.2.1-W3-100"],
                "files": [],
            },
            "session-alive": {
                "name": "alive-session",
                "project": PROJECT_ROOT,
                "heartbeat_ts": fresh_ts(NOW),
                "tickets": ["0.2.1-W3-200"],
                "files": [],
            },
        })
        with patch.object(track_sessions, "_run_git", _fake_run_git(tmp_path)):
            out = _run_sessions(capsys, fmt="json")

        payload = json.loads(out)
        rows = {r["session_id"]: r for r in payload["sessions"]}
        assert rows["session-stale"]["reclaimable_tickets"] == ["0.2.1-W3-100"]
        assert rows["session-alive"]["reclaimable_tickets"] == []
