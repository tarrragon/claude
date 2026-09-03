"""跨 agent 協調狀態（handoff pending/archive、dispatch-active.json）root 解析
統一測試（0.2.1-W4-028 / 0.2.1-W4-034 / 0.2.1-W4-031）。

驗證 handoff.py / resume.py / handoff_gc.py / track_dashboard.py /
track_dispatch_check.py / checkpoint_state.py / handoff_utils.py /
track_runqueue.py / version_shift.py / migrate.py / track_query.py /
track_snapshot.py / topic_backfill.py 在 linked worktree cwd 下，讀寫皆落在
主倉庫（非 worktree 本地副本）。

背景：這些模組原用 get_project_root()（worktree 感知，回傳呼叫端自己所在的
worktree 根目錄）解析跨 agent 協調狀態的落點；worktree 隔離的代理人各自把
handoff / dispatch-active 寫入自己的 worktree，PM 在主倉庫看不到，且內容
不隨 worktree 分支合併帶回主倉庫。改用 get_ticket_state_root()（linked
worktree 場景反向回推主倉庫根目錄）統一寫入單一位置。

隔離依賴同目錄 `.claude/skills/ticket/conftest.py` 的 autouse fixture
`_isolate_project_root`：每個 test 前自動清 get_project_root() /
get_ticket_state_root() 快取並注入獨立 tmp 目錄；`linked_worktree` fixture
關閉該逃生艙，使兩函式走真實 git 解析鏈，真實重現 worktree 場景下的根目錄
分歧（手法與 test_topic_assignments.py::linked_worktree 一致）。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.paths import (
    reset_project_root_cache,
    reset_ticket_state_root_cache,
)
from ticket_system.lib.constants import (
    HANDOFF_DIR,
    HANDOFF_PENDING_SUBDIR,
    HANDOFF_ARCHIVE_SUBDIR,
    WORK_LOGS_DIR,
)


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _init_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q")
    _run_git(root, "checkout", "-q", "-b", "main")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-q", "-m", "init")


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    """建立真實 main repo + linked worktree，cwd 切至 worktree。

    關閉 autouse `_isolate_project_root` 注入的
    `TICKET_SYSTEM_TEST_ISOLATION` 逃生艙與 `CLAUDE_PROJECT_DIR`（手法同
    `conftest.py` 的 `real_repo_root` fixture：後設定的 monkeypatch 勝出），
    使 `get_project_root()` / `get_ticket_state_root()` 走真實 git 解析鏈，
    真實重現 worktree 場景下兩者的根目錄分歧。
    """
    main_root = tmp_path / "main"
    wt_root = tmp_path / "wt"
    _init_git_repo(main_root)
    _run_git(main_root, "worktree", "add", "-q", "-b", "feat/test", str(wt_root), "HEAD")

    monkeypatch.delenv("TICKET_SYSTEM_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    monkeypatch.chdir(wt_root)

    yield main_root, wt_root

    reset_project_root_cache()
    reset_ticket_state_root_cache()


class TestHandoffCreateWorktreeRootUnification:
    """handoff.py：建立 handoff 檔案應落在主倉庫。"""

    def test_create_handoff_file_in_linked_worktree_writes_to_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.handoff import _create_handoff_file_internal

        ticket = {
            "id": "0.1.0-W1-777",
            "status": "in_progress",
            "title": "測試任務",
            "what": "測試",
            "chain": {},
        }

        exit_code = _create_handoff_file_internal(ticket, "to-parent")

        main_file = main_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR / "0.1.0-W1-777.json"
        wt_file = wt_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR / "0.1.0-W1-777.json"

        assert exit_code == 0
        assert main_file.exists()
        assert not wt_file.exists()


class TestResumeListWorktreeRootUnification:
    """resume.py + handoff_utils.py：list_pending_handoffs 應讀主倉庫寫入的 handoff。"""

    def test_list_pending_handoffs_in_linked_worktree_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.resume import list_pending_handoffs

        pending_dir = main_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "0.1.0-W1-778.json").write_text(
            json.dumps({
                "ticket_id": "0.1.0-W1-778",
                "direction": "context-refresh",
                "timestamp": "2026-09-02T00:00:00",
                "from_status": "in_progress",
                "title": "測試",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        result = list_pending_handoffs()

        assert len(result.handoffs) == 1
        assert result.handoffs[0]["ticket_id"] == "0.1.0-W1-778"


class TestHandoffGcArchiveWorktreeRootUnification:
    """handoff_gc.py + handoff_utils.py：stale handoff 歸檔應落在主倉庫。"""

    def test_gc_execute_in_linked_worktree_archives_to_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands import handoff_gc

        pending_dir = main_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
        pending_dir.mkdir(parents=True, exist_ok=True)
        stale_file = pending_dir / "0.1.0-W1-779.json"
        stale_file.write_text(
            json.dumps({
                "ticket_id": "0.1.0-W1-779",
                "direction": "context-refresh",
                "timestamp": "2026-09-02T00:00:00",
                "from_status": "completed",  # 規則 3：from_status=completed 即 stale
                "title": "測試",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        rc = handoff_gc.execute_gc(dry_run=False, force=False)

        main_archive = main_root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR / "0.1.0-W1-779.json"
        wt_archive = wt_root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR / "0.1.0-W1-779.json"

        assert rc == 0  # exit code 0：正常完成
        assert not stale_file.exists()
        assert main_archive.exists()
        assert not wt_archive.exists()


class TestDispatchCheckWorktreeRootUnification:
    """track_dispatch_check.py：dispatch-active.json 應讀主倉庫。"""

    def test_dispatch_check_in_linked_worktree_reads_main_repo(
        self, linked_worktree
    ):
        import argparse
        main_root, wt_root = linked_worktree
        from ticket_system.commands.track_dispatch_check import execute_dispatch_check

        claude_dir = main_root / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "dispatch-active.json").write_text(
            json.dumps({
                "dispatches": [
                    {"agent_description": "worker", "ticket_id": "0.1.0-W1-780", "dispatched_at": "t1"},
                ],
            }),
            encoding="utf-8",
        )

        rc = execute_dispatch_check(argparse.Namespace())

        assert rc == 1  # 有活躍派發（讀到主倉庫檔案，非 worktree 側缺檔的 exit 0）


class TestCheckpointStateDataSourcesWorktreeRootUnification:
    """checkpoint_state.py：_read_dispatch_active / _read_handoff_pending
    未顯式傳入 project_root 時（CLI 場景）應解析主倉庫。
    """

    def test_read_dispatch_active_without_explicit_root_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.lib.checkpoint_state import _read_dispatch_active

        claude_dir = main_root / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "dispatch-active.json").write_text(
            json.dumps({
                "dispatches": [
                    {"agent_description": "worker", "ticket_id": "T1", "status": "in_progress"},
                ],
            }),
            encoding="utf-8",
        )

        active_count, _raw = _read_dispatch_active()

        assert active_count == 1

    def test_read_handoff_pending_without_explicit_root_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.lib.checkpoint_state import _read_handoff_pending

        pending_dir = main_root / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "T2.json").write_text(
            json.dumps({"ticket_id": "T2"}), encoding="utf-8"
        )

        ticket_id = _read_handoff_pending()

        assert ticket_id == "T2"


class TestRunqueueWorktreeRootUnification:
    """track_runqueue.py：_get_pending_handoff_info 應讀主倉庫寫入的 handoff。

    0.2.1-W4-034：修復前用 get_project_root()（worktree 感知，回傳 worktree
    本地根目錄），linked worktree cwd 下讀不到主倉庫的 pending handoff，
    導致 runqueue --context=resume 與 readiness 標註恆為空/NO-CB 視角。
    """

    def test_get_pending_handoff_info_in_linked_worktree_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.track_runqueue import _get_pending_handoff_info

        pending_dir = main_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "0.1.0-W1-782.json").write_text(
            json.dumps({
                "ticket_id": "0.1.0-W1-782",
                "direction": "context-refresh",
                "timestamp": "2026-09-03T00:00:00",
                "from_status": "in_progress",
                "title": "測試",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        result = _get_pending_handoff_info()

        assert "0.1.0-W1-782" in result
        assert result["0.1.0-W1-782"]["ticket_id"] == "0.1.0-W1-782"


class TestDashboardAutoGcWorktreeRootUnification:
    """track_dashboard.py：_auto_gc_stale_handoffs 歸檔應落在主倉庫。"""

    def test_auto_gc_in_linked_worktree_archives_to_main_repo(self, linked_worktree):
        main_root, wt_root = linked_worktree
        from ticket_system.commands import track_dashboard

        pending_dir = main_root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
        pending_dir.mkdir(parents=True, exist_ok=True)
        stale_file = pending_dir / "0.1.0-W1-781.json"
        stale_file.write_text(
            json.dumps({
                "ticket_id": "0.1.0-W1-781",
                "direction": "context-refresh",
                "timestamp": "2026-09-02T00:00:00",
                "from_status": "completed",
                "title": "測試",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        track_dashboard._auto_gc_stale_handoffs()

        main_archive = main_root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR / "0.1.0-W1-781.json"
        wt_archive = wt_root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR / "0.1.0-W1-781.json"

        assert not stale_file.exists()
        assert main_archive.exists()
        assert not wt_archive.exists()


def _write_minimal_ticket(path: Path, ticket_id: str, **extra_frontmatter: str) -> None:
    """寫入最小可解析 ticket md（同 test_frontmatter_cache.py 的 _ticket_content 模式）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"id: {ticket_id}",
        "title: 測試",
        "type: IMP",
        "priority: P2",
        "status: pending",
    ]
    for key, value in extra_frontmatter.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("# body")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


class TestVersionShiftWorktreeRootUnification:
    """version_shift.py：0.2.1-W4-031，來源版本目錄驗證應讀主倉庫。"""

    def test_dry_run_in_linked_worktree_reads_main_repo_version_dir(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        import argparse
        from ticket_system.commands.version_shift import execute

        from_dir = main_root / WORK_LOGS_DIR / "v0.1.0" / "tickets"
        from_dir.mkdir(parents=True, exist_ok=True)

        args = argparse.Namespace(
            from_version="0.1.0",
            to_version="0.2.0",
            dry_run=True,
            no_backup=True,
            skip_todolist=True,
        )

        rc = execute(args)

        # 修復前：get_project_root() 回傳 wt_root，wt_root 下無 v0.1.0/，
        # _validate_versions 判定來源版本不存在，rc == 1。
        assert rc == 0


class TestMigrateWorktreeRootUnification:
    """migrate.py：0.2.1-W4-031，交叉引用掃描與備份應讀寫主倉庫。"""

    def test_update_cross_references_in_linked_worktree_updates_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.migrate import _update_cross_references

        referencing = main_root / WORK_LOGS_DIR / "v0.1.0" / "tickets" / "0.1.0-W1-200.md"
        _write_minimal_ticket(
            referencing, "0.1.0-W1-200", **{"blockedBy": "\n  - 0.1.0-W1-100"}
        )
        wt_referencing = wt_root / WORK_LOGS_DIR / "v0.1.0" / "tickets" / "0.1.0-W1-200.md"

        updated_count = _update_cross_references("0.1.0-W1-100", "0.1.0-W1-999")

        # 修復前：get_project_root() 回傳 wt_root（無此檔），掃描不到任何
        # ticket，updated_count == 0。
        assert updated_count == 1
        assert "0.1.0-W1-999" in referencing.read_text(encoding="utf-8")
        assert not wt_referencing.exists()

    def test_backup_ticket_in_linked_worktree_writes_to_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.migrate import _backup_ticket
        from ticket_system.lib.paths import get_ticket_path

        ticket_path = get_ticket_path("0.1.0", "0.1.0-W1-300")
        _write_minimal_ticket(ticket_path, "0.1.0-W1-300")

        backup_path = _backup_ticket("0.1.0", "0.1.0-W1-300")

        main_backup_root = main_root / ".claude" / "migration-backups"
        wt_backup_root = wt_root / ".claude" / "migration-backups"

        # 修復前：backup_dir 建在 get_project_root()（wt_root）之下。
        assert backup_path is not None
        assert backup_path.exists()
        assert list(main_backup_root.rglob("0.1.0-W1-300.md"))
        assert not wt_backup_root.exists()


class TestTrackQueryCrossVersionWarningWorktreeRootUnification:
    """track_query.py：0.2.1-W4-031，跨版本待辦掃描應讀主倉庫。"""

    def test_cross_version_warning_in_linked_worktree_reads_main_repo(
        self, linked_worktree, capsys
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.track_query import _print_cross_version_warning

        # 掃描邏輯只認 work-logs 下扁平的 v{version}/ 目錄名（非階層式
        # v{major}/v{major.minor}/v{version}/），故直接手動建構扁平路徑，
        # 不透過 get_ticket_path（其在兩者皆不存在時預設回傳階層式路徑）。
        ticket_path = main_root / WORK_LOGS_DIR / "v0.1.0" / "tickets" / "0.1.0-W1-400.md"
        _write_minimal_ticket(ticket_path, "0.1.0-W1-400")

        _print_cross_version_warning("0.2.0")

        captured = capsys.readouterr()
        # 修復前：get_project_root() 回傳的 wt_root 下無 docs/work-logs/，
        # work_logs.exists() 為 False，函式提早 return，無任何輸出。
        assert "0.1.0" in captured.out
        assert "pending" in captured.out


class TestTrackSnapshotScanAllVersionsWorktreeRootUnification:
    """track_snapshot.py：0.2.1-W4-031，版本目錄掃描應讀主倉庫。"""

    def test_scan_all_versions_in_linked_worktree_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        import importlib
        from ticket_system.commands import track_snapshot as ts_module

        # conftest.py 的 autouse fixture `_mock_track_snapshot_filesystem_scan`
        # （W11-015 效能優化）monkeypatch 掉 `_scan_all_versions` 為固定假清單，
        # 本測試需驗證真實掃描邏輯，故 reload 模組還原真實實作（in-place 更新
        # 同一模組物件，不影響其他測試對該模組的既有參照）。
        importlib.reload(ts_module)

        version_dir = main_root / WORK_LOGS_DIR / "v0.1.0"
        version_dir.mkdir(parents=True, exist_ok=True)

        versions = ts_module._scan_all_versions()

        # 修復前：get_project_root() 回傳 wt_root，wt_root 下無版本目錄，
        # versions == []。
        assert "0.1.0" in versions


class TestTopicBackfillIterTicketFilesWorktreeRootUnification:
    """topic_backfill.py：0.2.1-W4-031，ticket 檔案掃描應讀主倉庫。"""

    def test_iter_ticket_files_in_linked_worktree_reads_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree
        from ticket_system.commands.topic_backfill import _iter_ticket_files
        from ticket_system.lib.paths import get_ticket_path

        ticket_path = get_ticket_path("0.1.0", "0.1.0-W1-500")
        _write_minimal_ticket(ticket_path, "0.1.0-W1-500")

        files = _iter_ticket_files()

        # 修復前：get_project_root() 回傳 wt_root，掃描不到任何檔案，
        # files == []。
        assert ticket_path in files
