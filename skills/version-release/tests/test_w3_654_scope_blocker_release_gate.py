"""
0.1.0-W3-654: version-release check 發版判準改寫測試

覆蓋：
- E1：無 scope_blocker 的 pending 改前阻擋、改後不阻擋，且出現在前移清單（對照）
- E2：帶 scope_blocker 的 pending 與 in_progress 確實阻擋（紅輸入）
- finish：前移清單逐張 migrate；目標版本未登記時整批阻擋；任一張失敗即中止

另覆蓋（0.2.0-W1-017，收尾 commit 差集範圍與殘留守衛）：
- E1：finish 收尾提交以差集（非寫死清單）涵蓋 rename 與 todolist 啟用，
  提交後 git status --porcelain 為空（排除執行前已存在者）
- E2：殘留守衛對非白名單路徑的未追蹤殘留 exit 非 0 並列清單，不自動 add
"""  # rule8-exempt: relocation:延用既有檔頭 docstring 慣例，僅新增段落

import subprocess
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

        with patch.object(vr, "get_project_root", return_value=tmp_path):
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

        with patch.object(vr, "get_project_root", return_value=tmp_path):
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


def _init_git_repo(root: Path) -> None:
    """建立可提交的最小 git repo（tmp_path，不觸碰共用 index）。"""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    _write(root / "docs" / "todolist.yaml", "versions:\n  - version: 0.1.0\n")
    _write(root / "CHANGELOG.md", "# Changelog\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


class TestFinishCommitScopeAndResidualGuard:
    """0.2.0-W1-017：收尾 commit 差集範圍 + exit 前殘留守衛。"""

    def test_e1_diff_based_commit_covers_rename_and_todolist_activation(self, tmp_path):
        """E1 對照：差集涵蓋 Step 0 前移 rename 與 todolist 啟用，收尾後工作區乾淨。"""
        _init_git_repo(tmp_path)
        baseline = vr.snapshot_git_status_paths(tmp_path)
        assert baseline == set()  # 剛 commit 完，執行前基準應為乾淨狀態

        # 模擬 Step 0 前移：rename 一張 ticket 檔（非 todolist/CHANGELOG）
        old_path = tmp_path / "docs" / "work-logs" / "v0" / "v0.1" / "v0.1.0" / "tickets" / "0.1.0-W3-010.md"
        new_path = tmp_path / "docs" / "work-logs" / "v0" / "v0.1" / "v0.1.1" / "tickets" / "0.1.1-W3-010.md"
        _write(old_path, "# ticket\n")
        subprocess.run(["git", "add", str(old_path)], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "pre-existing ticket"], cwd=tmp_path, check=True)
        # 重新取基準：上面這個 commit 屬「執行前已存在」，須在 baseline 之後才模擬 rename
        baseline = vr.snapshot_git_status_paths(tmp_path)

        new_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", str(old_path), str(new_path)], cwd=tmp_path, check=True)
        # 模擬 todolist 啟用（Step 4）
        _write(tmp_path / "docs" / "todolist.yaml", "versions:\n  - version: 0.1.0\n  - version: 0.1.1\n")

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            ok = vr.commit_changes("0.1.0", dry_run=False, baseline=baseline)

        assert ok is True

        residual = vr.check_residual_after_finish(tmp_path, baseline)
        assert residual == [], f"E1 對照失敗：收尾後仍有殘留 {residual}"

        log = subprocess.run(
            ["git", "log", "--stat", "-1"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout
        assert "0.1.1-W3-010.md" in log
        assert "todolist.yaml" in log

    def test_e1_stale_hardcoded_list_would_leave_rename_uncommitted(self, tmp_path):
        """對照組（反證）：若沿用舊版寫死清單（僅 add todolist/CHANGELOG），
        rename 產生的新檔會被排除在 stage_targets 外——證明差集範圍非退化為寫死清單。
        """
        _init_git_repo(tmp_path)
        old_path = tmp_path / "docs" / "work-logs" / "v0" / "v0.1" / "v0.1.0" / "tickets" / "0.1.0-W3-010.md"
        _write(old_path, "# ticket\n")
        subprocess.run(["git", "add", str(old_path)], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "pre-existing ticket"], cwd=tmp_path, check=True)
        baseline = vr.snapshot_git_status_paths(tmp_path)

        new_path = tmp_path / "docs" / "work-logs" / "v0" / "v0.1" / "v0.1.1" / "tickets" / "0.1.1-W3-010.md"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", str(old_path), str(new_path)], cwd=tmp_path, check=True)

        stage_targets_new_style = [
            p
            for p in vr._diff_new_paths(tmp_path, baseline)
            if p == "CHANGELOG.md" or p.startswith("docs/")
        ]
        hardcoded_style = {"docs/todolist.yaml", "CHANGELOG.md"}

        assert any(
            "0.1.1-W3-010.md" in p for p in stage_targets_new_style
        ), "差集範圍應涵蓋 rename 產生的新檔"
        assert not any(
            "0.1.1-W3-010.md" in p for p in hardcoded_style
        ), "寫死清單不會涵蓋 rename（回歸測試錨點）"

    def test_e2_residual_guard_detects_untracked_non_whitelisted_file(self, tmp_path):
        """E2 紅輸入：非白名單路徑的未追蹤殘留必須被守衛偵測到，且不自動 add。"""
        _init_git_repo(tmp_path)
        baseline = vr.snapshot_git_status_paths(tmp_path)
        assert baseline == set()

        stray_file = tmp_path / "lib" / "accidental_output.dart"
        _write(stray_file, "// 非本次 finish 產生範圍內的殘留\n")

        residual = vr.check_residual_after_finish(tmp_path, baseline)

        # 未追蹤的新目錄，git status --porcelain 回報目錄路徑（非逐檔展開）
        assert any(p.startswith("lib/") for p in residual)

        status_after = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout
        assert "??" in status_after  # 仍是未追蹤狀態，守衛未自動 add

    def test_e2_residual_guard_clean_tree_returns_empty(self, tmp_path):
        """對照：baseline 之後無新變更時，殘留守衛回傳空清單（不誤報）。"""
        _init_git_repo(tmp_path)
        baseline = vr.snapshot_git_status_paths(tmp_path)

        residual = vr.check_residual_after_finish(tmp_path, baseline)

        assert residual == []


class TestCheckVersionFrozenGate:
    """0.2.0-W1-029：check／finish 的凍結前置關卡。"""

    def _write_todolist(self, tmp_path, versions_yaml: str) -> None:
        _write(tmp_path / "docs" / "todolist.yaml", versions_yaml)

    def test_e2_unfrozen_version_fails_with_explicit_message(self, tmp_path):
        """E2 紅輸入：未凍結版本 exit 非 0 且訊息含「未凍結」處置。"""
        self._write_todolist(
            tmp_path,
            "versions:\n  - version: \"0.2.0\"\n    status: active\n",
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            ok, errors = vr.check_version_frozen("0.2.0")

        assert ok is False
        assert any("未凍結" in e for e in errors)

    def test_e1_frozen_version_passes(self, tmp_path):
        """E1 對照：加 scope: frozen 後通過前置關卡，進入既有判定。"""
        self._write_todolist(
            tmp_path,
            "versions:\n  - version: \"0.1.1\"\n    status: active\n    scope: \"frozen\"\n",
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            ok, errors = vr.check_version_frozen("0.1.1")

        assert ok is True
        assert errors == []

    def test_missing_version_registration_fails(self, tmp_path):
        """目標版本未登記於 todolist.yaml 時同樣視為未通過凍結前置關卡。"""
        self._write_todolist(tmp_path, "versions:\n  - version: \"0.1.0\"\n")

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            ok, errors = vr.check_version_frozen("0.2.0")

        assert ok is False
        assert any("未登記" in e for e in errors)

    def test_finish_aborts_before_migrate_when_unfrozen(self, tmp_path):
        """finish 對未凍結版本於 Step 0（migrate）之前中止，無 migrate 副作用。"""
        self._write_todolist(
            tmp_path,
            "versions:\n  - version: \"0.2.0\"\n    status: active\n",
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch("sys.argv", ["version_release.py", "finish", "--version", "0.2.0"]), \
                patch.object(vr, "migrate_overflow_tickets") as mock_migrate:
            exit_code = vr.main()

        assert exit_code == 1
        mock_migrate.assert_not_called()
