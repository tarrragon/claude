"""
測試 stop-worklog-handoff-sync-check-hook 第 7 格偵測（0.2.1-W3-219）。

第 7 格（來源票 0.2.1-W3-178 8 格矩陣）：worklog 無交接段 + handoff pending 空
+ ticket body 有交接 context。原第 546-547 行對雙軌皆空明文短路 return None，
本票新增 S3 閘門（session ticket 活動）+ S1 主訊號（commit subject 交接語意）
+ S4 反向濾除（chore( 前綴）偵測，命中時輸出提醒並附具體建議命令；未命中
（第 8 格：確實無交接）維持靜默不回歸。
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
import time
from pathlib import Path

import pytest


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "stop-worklog-handoff-sync-check-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "stop_worklog_handoff_sync_check_hook_cell7", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def hook_module():
    return _load_hook_module()


@pytest.fixture()
def logger():
    log = logging.getLogger("test-stop-worklog-handoff-sync-check-cell7")
    log.addHandler(logging.NullHandler())
    return log


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    _git(project_root, "init", "-q")
    _git(project_root, "config", "user.email", "test@example.com")
    _git(project_root, "config", "user.name", "Test User")
    (project_root / "README.md").write_text("init\n", encoding="utf-8")
    _git(project_root, "add", "README.md")
    _git(project_root, "commit", "-q", "-m", "chore: init")


def _commit(project_root: Path, filename: str, subject: str) -> None:
    (project_root / filename).write_text(subject, encoding="utf-8")
    _git(project_root, "add", filename)
    _git(project_root, "commit", "-q", "-m", subject)


def _write_ticket(
    project_root: Path,
    version: str,
    ticket_id: str,
    *,
    started_at: str | None = None,
    completed_at: str | None = None,
    status: str = "in_progress",
) -> Path:
    parts = version.split(".")
    major, minor = parts[0], f"{parts[0]}.{parts[1]}"
    tickets_dir = (
        project_root
        / "docs"
        / "work-logs"
        / f"v{major}"
        / f"v{minor}"
        / f"v{version}"
        / "tickets"
    )
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = tickets_dir / f"{ticket_id}.md"
    lines = ["---", f"id: {ticket_id}", f"status: {status}"]
    if started_at:
        lines.append(f"started_at: '{started_at}'")
    if completed_at:
        lines.append(f"completed_at: '{completed_at}'")
    lines.append("---")
    lines.append("")
    lines.append("# body")
    ticket_path.write_text("\n".join(lines), encoding="utf-8")
    return ticket_path


def _write_todolist_active(project_root: Path, version: str) -> None:
    todolist = project_root / "docs" / "todolist.yaml"
    todolist.parent.mkdir(parents=True, exist_ok=True)
    todolist.write_text(
        f"versions:\n  - version: \"{version}\"\n    status: active\n",
        encoding="utf-8",
    )


def _write_worklog(project_root: Path, version: str, content: str = "# worklog\n") -> Path:
    parts = version.split(".")
    major, minor = parts[0], f"{parts[0]}.{parts[1]}"
    worklog_dir = project_root / "docs" / "work-logs" / f"v{major}" / f"v{minor}" / f"v{version}"
    worklog_dir.mkdir(parents=True, exist_ok=True)
    worklog_path = worklog_dir / f"v{version}-main.md"
    worklog_path.write_text(content, encoding="utf-8")
    return worklog_path


class TestCell7DetectHandoffCommitSignal:
    """S1 主訊號 + S4 反向濾除單元測試。"""

    def test_matches_handoff_keyword_subject(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        session_start_ts = time.time() - 1
        _commit(tmp_path, "a.txt", "docs(0.2.1-W3-174): 寫入交接 context 並更正 Context Bundle")

        hits = hook_module._detect_handoff_commit_signal(tmp_path, session_start_ts, logger)

        assert len(hits) == 1
        assert "交接" in hits[0]

    def test_filters_chore_prefix_noise(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        session_start_ts = time.time() - 1
        _commit(tmp_path, "b.txt", "chore(0.2.1-W3-174): append-log 交接 context")

        hits = hook_module._detect_handoff_commit_signal(tmp_path, session_start_ts, logger)

        assert hits == []

    def test_no_keyword_no_hit(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        session_start_ts = time.time() - 1
        _commit(tmp_path, "c.txt", "feat(0.2.1-W3-174): 新增功能")

        hits = hook_module._detect_handoff_commit_signal(tmp_path, session_start_ts, logger)

        assert hits == []

    def test_session_start_zero_returns_empty(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        assert hook_module._detect_handoff_commit_signal(tmp_path, 0, logger) == []


class TestCell7GetSessionActiveTickets:
    """S3 閘門單元測試。"""

    def test_ticket_started_after_session_start_is_active(self, hook_module, logger, tmp_path):
        _write_ticket(
            tmp_path, "0.2.1", "0.2.1-W3-219",
            started_at="2026-08-03T18:00:00",
        )
        session_start_ts = __import__("datetime").datetime(2026, 8, 3, 17, 0, 0).timestamp()

        active = hook_module._get_session_active_tickets(tmp_path, "0.2.1", session_start_ts, logger)

        assert active == ["0.2.1-W3-219"]

    def test_ticket_before_session_start_is_not_active(self, hook_module, logger, tmp_path):
        _write_ticket(
            tmp_path, "0.2.1", "0.2.1-W3-100",
            completed_at="2026-08-01T10:00:00",
        )
        session_start_ts = __import__("datetime").datetime(2026, 8, 3, 17, 0, 0).timestamp()

        active = hook_module._get_session_active_tickets(tmp_path, "0.2.1", session_start_ts, logger)

        assert active == []

    def test_session_start_zero_returns_empty(self, hook_module, logger, tmp_path):
        _write_ticket(tmp_path, "0.2.1", "0.2.1-W3-219", started_at="2026-08-03T18:00:00")
        assert hook_module._get_session_active_tickets(tmp_path, "0.2.1", 0, logger) == []


class TestCell7Integration:
    """detect_sync_drift 整合測試：第 7 格觸發 + 第 8 格靜默。"""

    def test_cell7_full_flow(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        _write_todolist_active(tmp_path, "0.2.1")
        session_start_ts = time.time()
        worklog_path = _write_worklog(tmp_path, "0.2.1")
        import os
        old_time = session_start_ts - 3600
        os.utime(worklog_path, (old_time, old_time))

        # W17-176 根因 2 豁免：in_progress ticket 會使既有防護整體跳過偵測，
        # 故用 completed 模擬「本 session 完成任務但未走 handoff」的第 7 格典型情境。
        import datetime as _dt
        completed_at_iso = _dt.datetime.fromtimestamp(session_start_ts + 60).isoformat()
        _write_ticket(
            tmp_path, "0.2.1", "0.2.1-W3-219",
            completed_at=completed_at_iso, status="completed",
        )

        _commit(tmp_path, "handoff.txt", "docs(0.2.1-W3-174): 寫入交接 context")

        warning = hook_module.detect_sync_drift(tmp_path, session_start_ts, logger, input_data={})

        assert warning is not None
        assert "ticket handoff --next" in warning
        assert "--from-ticket-id 0.2.1-W3-219" in warning

    def test_cell8_stays_silent_without_commit_signal(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        _write_todolist_active(tmp_path, "0.2.1")
        session_start_ts = time.time()
        worklog_path = _write_worklog(tmp_path, "0.2.1")
        import os
        old_time = session_start_ts - 3600
        os.utime(worklog_path, (old_time, old_time))

        import datetime as _dt
        completed_at_iso = _dt.datetime.fromtimestamp(session_start_ts + 60).isoformat()
        _write_ticket(
            tmp_path, "0.2.1", "0.2.1-W3-219",
            completed_at=completed_at_iso, status="completed",
        )

        # 無交接語意的 commit（非 chore，但也非交接語意）
        _commit(tmp_path, "feat.txt", "feat(0.2.1-W3-219): 新增功能")

        warning = hook_module.detect_sync_drift(tmp_path, session_start_ts, logger, input_data={})

        assert warning is None

    def test_cell8_stays_silent_without_session_ticket_activity(self, hook_module, logger, tmp_path):
        _init_repo(tmp_path)
        _write_todolist_active(tmp_path, "0.2.1")
        session_start_ts = time.time()
        worklog_path = _write_worklog(tmp_path, "0.2.1")
        import os
        old_time = session_start_ts - 3600
        os.utime(worklog_path, (old_time, old_time))

        # 無任何 ticket 活動落在 session 窗內（S3 閘門不通過）
        _commit(tmp_path, "handoff.txt", "docs(0.2.1-W3-174): 寫入交接 context")

        warning = hook_module.detect_sync_drift(tmp_path, session_start_ts, logger, input_data={})

        assert warning is None

    def test_orphan_pending_path_unaffected(self, hook_module, logger, tmp_path):
        """既有防護不回歸：pending 非空時（cell 5/6）維持既有邏輯路徑，不誤觸第 7 格輸出格式。"""
        _init_repo(tmp_path)
        _write_todolist_active(tmp_path, "0.2.1")
        session_start_ts = time.time()
        worklog_path = _write_worklog(tmp_path, "0.2.1")
        import os
        old_time = session_start_ts - 3600
        os.utime(worklog_path, (old_time, old_time))

        pending_dir = tmp_path / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "0.2.1-W3-100.json").write_text(
            '{"ticket_id": "0.2.1-W3-100"}', encoding="utf-8"
        )

        warning = hook_module.detect_sync_drift(tmp_path, session_start_ts, logger, input_data={})

        # worklog mtime 早於 session_start 且 pending 非空 → 沿用既有靜默行為（非本票範圍）
        assert warning is None
