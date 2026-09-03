"""跨 agent 協調狀態（handoff pending/archive、dispatch-active.json）root 解析
統一測試（0.2.1-W4-028）。

驗證 handoff.py / resume.py / handoff_gc.py / track_dashboard.py /
track_dispatch_check.py / checkpoint_state.py / handoff_utils.py 在
linked worktree cwd 下，讀寫皆落在主倉庫（非 worktree 本地副本）。

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

        pending_dir = main_root / ".claude" / "handoffs" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "T2.json").write_text(
            json.dumps({"ticket_id": "T2"}), encoding="utf-8"
        )

        ticket_id = _read_handoff_pending()

        assert ticket_id == "T2"


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
