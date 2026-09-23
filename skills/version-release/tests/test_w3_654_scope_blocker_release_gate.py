"""
0.1.0-W3-654: version-release check 發版判準改寫測試

覆蓋：
- E1：無 scope_blocker 的 pending 改前阻擋、改後不阻擋，且出現在前移清單（對照）
- E2：帶 scope_blocker 的 pending 與 in_progress 確實阻擋（紅輸入）
- finish：前移清單逐張 migrate；目標版本未登記時整批阻擋；任一張失敗即中止
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ticket_md(
    ticket_id: str,
    status: str,
    ticket_type: str = "IMP",
    what: str = "修復 某功能",
    scope_blocker: str | None = None,
) -> str:
    lines = [
        "---",
        f"id: {ticket_id}",
        f"type: {ticket_type}",
        f"status: {status}",
        f"what: {what}",
    ]
    if scope_blocker is not None:
        lines.append(f"scope_blocker: '{scope_blocker}'")
    else:
        lines.append("scope_blocker: null")
    lines.append("---")
    lines.append("")
    lines.append("# body")
    return "\n".join(lines)


def _setup_version_tickets(tmp_path: Path, version: str, tickets: dict) -> Path:
    major, minor, patch = version.split(".")
    tickets_dir = (
        tmp_path / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}" / f"v{version}" / "tickets"
    )
    for ticket_id, content in tickets.items():
        _write(tickets_dir / f"{ticket_id}.md", content)
    return tickets_dir


class TestCollectTicketScopeGroupsE1AndE2:
    """collect_ticket_scope_groups：E1（無 blocker 對照）與 E2（紅輸入）。"""

    def test_e2_pending_with_blocker_and_in_progress_are_blocked(self, tmp_path):
        """紅輸入：帶 scope_blocker 的 pending 與 in_progress 都進 blocked/in_progress 組"""
        tickets_dir = _setup_version_tickets(
            tmp_path,
            "0.1.0",
            {
                "0.1.0-W3-001": _ticket_md("0.1.0-W3-001", "pending", scope_blocker="用戶明確放行"),
                "0.1.0-W3-002": _ticket_md("0.1.0-W3-002", "in_progress"),
            },
        )

        groups = vr.collect_ticket_scope_groups(tickets_dir, "0.1.0")

        assert len(groups["blocked"]) == 1
        assert groups["blocked"][0]["id"] == "0.1.0-W3-001"
        assert groups["blocked"][0]["scope_blocker"] == "用戶明確放行"
        assert len(groups["in_progress"]) == 1
        assert groups["in_progress"][0]["id"] == "0.1.0-W3-002"
        assert groups["overflow"] == []

    def test_e1_pending_without_blocker_goes_to_overflow_with_target_version(self, tmp_path):
        """對照：無 blocker 的 pending 不進 blocked，出現在 overflow 且含目標版本"""
        tickets_dir = _setup_version_tickets(
            tmp_path,
            "0.1.0",
            {
                "0.1.0-W3-003": _ticket_md("0.1.0-W3-003", "pending"),
            },
        )

        groups = vr.collect_ticket_scope_groups(tickets_dir, "0.1.0")

        assert groups["blocked"] == []
        assert groups["in_progress"] == []
        assert len(groups["overflow"]) == 1
        overflow_ticket = groups["overflow"][0]
        assert overflow_ticket["id"] == "0.1.0-W3-003"
        assert overflow_ticket["target_version"] == "0.1.1"

    def test_e1_new_feature_action_overflows_to_next_minor(self, tmp_path):
        """IMP + 新功能動詞（實作）→ minor+1；其餘 → patch+1（分類差異對照）"""
        tickets_dir = _setup_version_tickets(
            tmp_path,
            "0.1.0",
            {
                "0.1.0-W3-004": _ticket_md(
                    "0.1.0-W3-004", "pending", ticket_type="IMP", what="實作 新功能 X"
                ),
            },
        )

        groups = vr.collect_ticket_scope_groups(tickets_dir, "0.1.0")

        assert groups["overflow"][0]["target_version"] == "0.2.0"

    def test_completed_ticket_is_ignored(self, tmp_path):
        """completed 狀態既不阻擋也不進前移清單"""
        tickets_dir = _setup_version_tickets(
            tmp_path,
            "0.1.0",
            {
                "0.1.0-W3-005": _ticket_md("0.1.0-W3-005", "completed"),
            },
        )

        groups = vr.collect_ticket_scope_groups(tickets_dir, "0.1.0")

        assert groups["blocked"] == []
        assert groups["overflow"] == []
        assert groups["in_progress"] == []


class TestCheckWorklogCompletedBeforeAfter:
    """check_worklog_completed 對照：改前後行為差異驗證同一 fixture。"""

    def _setup(self, tmp_path, ticket_id, status, scope_blocker=None):
        tickets_dir = _setup_version_tickets(
            tmp_path,
            "1.2.0",
            {ticket_id: _ticket_md(ticket_id, status, scope_blocker=scope_blocker)},
        )
        version_subdir = tickets_dir.parent
        _write(version_subdir / "v1.2.0-main.md", "# worklog\n")
        return tickets_dir

    def test_pending_without_blocker_does_not_block(self, tmp_path):
        """E1（改後）：無 blocker 的 pending 不再產生 error"""
        self._setup(tmp_path, "1.2.0-W1-001", "pending")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("1.2.0")

        assert ok is True, f"unexpected errors: {errors}"

    def test_pending_with_blocker_blocks(self, tmp_path):
        """E2：帶 scope_blocker 的 pending 仍阻擋"""
        self._setup(tmp_path, "1.2.0-W1-002", "pending", scope_blocker="理由")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("1.2.0")

        assert ok is False
        assert any("scope_blocker" in e for e in errors)

    def test_in_progress_blocks(self, tmp_path):
        """E2：in_progress 一律阻擋"""
        self._setup(tmp_path, "1.2.0-W1-003", "in_progress")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("1.2.0")

        assert ok is False
        assert any("in_progress" in e for e in errors)


class TestMigrateOverflowTickets:
    """finish 的前移邏輯：目標版本未登記阻擋 / 失敗中止 / 逐張成功。"""

    def _setup_overflow(self, tmp_path, version="0.1.0"):
        return _setup_version_tickets(
            tmp_path,
            version,
            {f"{version}-W3-010": _ticket_md(f"{version}-W3-010", "pending")},
        )

    def _write_todolist(self, tmp_path, versions):
        content_lines = ["versions:"]
        for v in versions:
            content_lines.append(f"  - version: {v}")
        _write(tmp_path / "docs" / "todolist.yaml", "\n".join(content_lines) + "\n")

    def test_no_overflow_returns_true_without_migrate_call(self, tmp_path):
        """無 pending 票時直接成功，不呼叫 migrate"""
        _setup_version_tickets(tmp_path, "0.1.0", {})
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "_run_ticket_migrate") as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0")

        assert ok is True
        mock_migrate.assert_not_called()

    def test_missing_target_version_registration_blocks_without_migrating(self, tmp_path):
        """目標版本未在 todolist.yaml 登記時整批阻擋，不呼叫 migrate，不自動登記"""
        self._setup_overflow(tmp_path)
        self._write_todolist(tmp_path, ["0.1.0"])  # 0.1.1 未登記
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "_run_ticket_migrate") as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0")

        assert ok is False
        mock_migrate.assert_not_called()

        # 不自動登記：todolist.yaml 內容未被改寫新增 0.1.1
        todolist_text = (tmp_path / "docs" / "todolist.yaml").read_text(encoding="utf-8")
        assert "0.1.1" not in todolist_text

    def test_registered_target_calls_migrate_with_expected_args(self, tmp_path):
        """目標版本已登記時對每張票呼叫 migrate，帶正確 source/target/version"""
        self._setup_overflow(tmp_path)
        self._write_todolist(tmp_path, ["0.1.0", "0.1.1"])
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        success = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "_run_ticket_migrate", return_value=success) as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0")

        assert ok is True
        mock_migrate.assert_called_once_with(
            "0.1.0-W3-010", "0.1.1-W3-010", "0.1.1", False
        )

    def test_migrate_failure_aborts_without_processing_remaining(self, tmp_path):
        """任一張 migrate 失敗即中止，不繼續處理剩餘票"""
        version = "0.1.0"
        tickets_dir = _setup_version_tickets(
            tmp_path,
            version,
            {
                f"{version}-W3-010": _ticket_md(f"{version}-W3-010", "pending"),
                f"{version}-W3-011": _ticket_md(f"{version}-W3-011", "pending"),
            },
        )
        self._write_todolist(tmp_path, ["0.1.0", "0.1.1"])
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        failure = MagicMock(returncode=1, stdout="", stderr="collision")
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "_run_ticket_migrate", return_value=failure) as mock_migrate:
            ok = vr.migrate_overflow_tickets(version)

        assert ok is False
        # 第一張失敗即中止，不應呼叫第二次
        assert mock_migrate.call_count == 1
