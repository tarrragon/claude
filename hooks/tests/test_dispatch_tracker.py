"""
Active Dispatch Tracker 單元測試

測試 .claude/lib/dispatch_tracker.py 的所有公開 API。
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 設定 import 路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.dispatch_tracker import (
    get_state_file_path,
    record_dispatch,
    clear_dispatch,
    get_active_dispatches,
    is_file_under_dispatch,
    cleanup_expired,
    detect_orphan_branches,
    mark_turn_ended_by_id,
    mark_oldest_active_null_agent_id_entry_turn_ended,
)


@pytest.fixture
def project_root():
    """建立臨時 project_root 目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".claude").mkdir()
        yield root


class TestRecordDispatch:
    def test_record_dispatch(self, project_root: Path):
        """記錄後 get_active_dispatches 回傳正確"""
        record_dispatch(
            project_root,
            agent_description="Fix dart_parser",
            ticket_id="W7-001",
            files=["lib/parsers/dart_parser.py"],
            branch_name="agent-abc12345",
        )
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "Fix dart_parser"
        assert dispatches[0]["ticket_id"] == "W7-001"
        assert dispatches[0]["files"] == ["lib/parsers/dart_parser.py"]
        assert dispatches[0]["branch_name"] == "agent-abc12345"
        assert "dispatched_at" in dispatches[0]

    def test_record_dispatch_default_branch_name(self, project_root: Path):
        """未提供 branch_name 時預設為空字串"""
        record_dispatch(project_root, "Task without branch")
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["branch_name"] == ""

    def test_record_multiple_dispatches(self, project_root: Path):
        """多次記錄累加"""
        record_dispatch(project_root, "Task A")
        record_dispatch(project_root, "Task B")
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 2

    def test_record_dispatch_stores_name(self, project_root: Path):
        """named agent 的 name（如 subagent_type）寫入 entry（0.2.1-W3-1205）。"""
        record_dispatch(
            project_root,
            agent_description="Fix dart_parser",
            name="thyme-python-developer",
        )
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["name"] == "thyme-python-developer"

    def test_record_dispatch_default_name_is_empty(self, project_root: Path):
        """未提供 name 時預設為空字串（如 code-review 型無 named agent 的派發）。"""
        record_dispatch(project_root, "Task without name")
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["name"] == ""

    def test_record_dispatch_new_entry_turn_ended_at_is_none(self, project_root: Path):
        """新記錄的 turn_ended_at 初始為 None（尚未回合結束，0.2.1-W3-1205）。"""
        record_dispatch(project_root, "Task A")
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["turn_ended_at"] is None


class TestClearDispatch:
    def test_clear_dispatch(self, project_root: Path):
        """清理後記錄消失"""
        record_dispatch(project_root, "Task A")
        record_dispatch(project_root, "Task B")

        result = clear_dispatch(project_root, "Task A")

        assert result is True
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "Task B"

    def test_clear_dispatch_not_found(self, project_root: Path):
        """清理不存在的記錄回傳 False"""
        record_dispatch(project_root, "Task A")
        result = clear_dispatch(project_root, "Task X")
        assert result is False
        assert len(get_active_dispatches(project_root)) == 1


class TestMarkTurnEndedById:
    """SubagentStop 主路徑：標記回合結束而非刪除 entry（0.2.1-W3-1205）。

    背景：SubagentStop 的觸發前提「代理人真正停止才觸發」實測不成立
    （代理人回合結束後轉入 idle 仍存活、仍可接受訊息並繼續工作）。刪除
    entry 會使唯一追蹤存活狀態的資料源在代理人尚未終止時即清空。
    """

    def test_marks_without_removing_entry(self, project_root: Path):
        """標記後 entry 仍存在（非刪除），且 turn_ended_at 被寫入。"""
        record_dispatch(
            project_root,
            agent_description="Fix dart_parser",
            ticket_id="W7-001",
            agent_id="agent-abc",
            name="thyme-python-developer",
        )

        result = mark_turn_ended_by_id(project_root, "agent-abc")

        assert result is True
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1, "entry 應保留，不應被刪除"
        assert dispatches[0]["turn_ended_at"] is not None
        # 其餘欄位（name / ticket_id）不受標記動作影響，仍可查得
        assert dispatches[0]["name"] == "thyme-python-developer"
        assert dispatches[0]["ticket_id"] == "W7-001"

    def test_not_found_returns_false(self, project_root: Path):
        """agent_id 無匹配時回傳 False，不影響既有記錄。"""
        record_dispatch(project_root, "Task A", agent_id="agent-a")

        result = mark_turn_ended_by_id(project_root, "agent-nonexistent")

        assert result is False
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["turn_ended_at"] is None

    def test_duplicate_agent_id_marks_all_and_warns(
        self, project_root: Path, capsys
    ):
        """重複 agent_id（異常情境）全數標記，並於 stderr 提示重複匹配。"""
        record_dispatch(project_root, "Task A", agent_id="agent-dup")
        record_dispatch(project_root, "Task B", agent_id="agent-dup")

        result = mark_turn_ended_by_id(project_root, "agent-dup")

        assert result is True
        dispatches = get_active_dispatches(project_root)
        assert all(d["turn_ended_at"] is not None for d in dispatches)
        assert "重複匹配" in capsys.readouterr().err


class TestMarkOldestActiveNullAgentIdEntryTurnEnded:
    """FIFO fallback：SubagentStop input 無 description，agent_id 精準匹配
    失敗時，標記 agent_id 為 null 且尚未標記過回合結束的最早一筆。
    """

    def test_fifo_marks_oldest_unmarked_candidate(self, project_root: Path):
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        new_time = datetime.now(timezone.utc).isoformat()
        state = {
            "dispatches": [
                {
                    "agent_description": "older",
                    "agent_id": None,
                    "turn_ended_at": None,
                    "dispatched_at": old_time,
                },
                {
                    "agent_description": "newer",
                    "agent_id": None,
                    "turn_ended_at": None,
                    "dispatched_at": new_time,
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        result = mark_oldest_active_null_agent_id_entry_turn_ended(project_root)

        assert result is True
        dispatches = get_active_dispatches(project_root)
        by_desc = {d["agent_description"]: d for d in dispatches}
        assert by_desc["older"]["turn_ended_at"] is not None
        assert by_desc["newer"]["turn_ended_at"] is None
        assert len(dispatches) == 2, "entry 應保留，不應被刪除"

    def test_excludes_already_marked_entries(self, project_root: Path):
        """已標記過回合結束的 null-agent_id entry 不再是候選（避免保留期拉長
        後 FIFO 對其重複判定，使呼叫端『候選 > 1 停用 FIFO』邏輯永久失效）。
        """
        already_marked_time = "2026-01-01T00:00:00+00:00"
        state = {
            "dispatches": [
                {
                    "agent_description": "already-marked",
                    "agent_id": None,
                    "turn_ended_at": already_marked_time,
                    "dispatched_at": "2026-01-01T00:00:00+00:00",
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        result = mark_oldest_active_null_agent_id_entry_turn_ended(project_root)

        assert result is False
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["turn_ended_at"] == already_marked_time, (
            "已標記過的 entry 不應被本函式改動"
        )

    def test_no_candidates_returns_false(self, project_root: Path):
        record_dispatch(project_root, "Task with agent_id", agent_id="agent-x")
        result = mark_oldest_active_null_agent_id_entry_turn_ended(project_root)
        assert result is False


class TestIsFileUnderDispatch:
    def test_file_under_dispatch(self, project_root: Path):
        """檔案在派發中回傳 dispatch 記錄"""
        record_dispatch(
            project_root, "Fix parser", files=["src/parser.py", "src/utils.py"]
        )
        result = is_file_under_dispatch(project_root, "src/parser.py")
        assert result is not None
        assert result["agent_description"] == "Fix parser"

    def test_file_not_under_dispatch(self, project_root: Path):
        """不在派發中回傳 None"""
        record_dispatch(project_root, "Fix parser", files=["src/parser.py"])
        result = is_file_under_dispatch(project_root, "src/other.py")
        assert result is None


class TestCleanupExpired:
    def test_cleanup_expired(self, project_root: Path):
        """超時記錄被清理"""
        # 手動寫入一筆過期記錄
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        state = {
            "dispatches": [
                {
                    "agent_description": "Old task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": old_time,
                },
                {
                    "agent_description": "New task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": datetime.now(timezone.utc).isoformat(),
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        removed = cleanup_expired(project_root, max_age_hours=4)

        assert removed == 1
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "New task"

    def test_cleanup_no_expired(self, project_root: Path):
        """無超時記錄時回傳 0"""
        record_dispatch(project_root, "Fresh task")
        removed = cleanup_expired(project_root)
        assert removed == 0

    def test_cleanup_default_ttl_is_1h(self, project_root: Path):
        """default max_age_hours=1：90 分鐘前的記錄會被清理（W11-024）"""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        state = {
            "dispatches": [
                {
                    "agent_description": "90min ago task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": old_time,
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        # 不傳參數，使用 default
        removed = cleanup_expired(project_root)
        assert removed == 1
        assert len(get_active_dispatches(project_root)) == 0

    def test_cleanup_1h_keeps_recent(self, project_root: Path):
        """default 1h TTL 下，30 分鐘前的記錄保留（W11-024）"""
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        state = {
            "dispatches": [
                {
                    "agent_description": "30min ago task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": recent_time,
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        removed = cleanup_expired(project_root)
        assert removed == 0
        assert len(get_active_dispatches(project_root)) == 1


class TestDetectOrphanBranches:
    def test_detect_orphan_branches(self, project_root: Path):
        """mock git worktree list，偵測 orphan"""
        porcelain_output = (
            "worktree /main\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("lib.dispatch_tracker.subprocess.run", return_value=mock_result):
            # 無 dispatch 記錄，agent- 分支應為 orphan
            orphans = detect_orphan_branches(project_root)

        assert "agent-fix-parser" in orphans

    def test_no_orphan_when_dispatch_exists(self, project_root: Path):
        """有對應 dispatch 記錄（含 branch_name）時不算 orphan"""
        record_dispatch(
            project_root, "fix-parser", branch_name="agent-fix-parser"
        )

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("lib.dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        assert len(orphans) == 0

    def test_orphan_when_dispatch_has_no_branch_name(self, project_root: Path):
        """dispatch 記錄無 branch_name 時，worktree 分支視為 orphan"""
        record_dispatch(project_root, "fix-parser")

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("lib.dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        # 無 branch_name 的 dispatch 不會匹配任何 worktree
        assert "agent-fix-parser" in orphans

    def test_exact_match_prevents_substring_false_negative(self, project_root: Path):
        """精確比對防止子字串誤判（如 agent-fix 不匹配 agent-fix-parser）"""
        record_dispatch(
            project_root, "fix", branch_name="agent-fix"
        )

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("lib.dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        # agent-fix != agent-fix-parser，精確比對不會誤判
        assert "agent-fix-parser" in orphans


class TestEdgeCases:
    def test_state_file_not_exist(self, project_root: Path):
        """狀態檔不存在時各函式正常運作"""
        assert get_active_dispatches(project_root) == []
        assert is_file_under_dispatch(project_root, "any.py") is None
        assert clear_dispatch(project_root, "any") is False
        assert cleanup_expired(project_root) == 0

    def test_concurrent_access(self, project_root: Path):
        """多次寫入不會損壞 JSON"""
        for i in range(10):
            record_dispatch(project_root, f"Task {i}")

        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 10

        # 驗證 JSON 可正確解析
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data["dispatches"]) == 10

    def test_parallel_writes_no_data_loss(self, project_root: Path):
        """多執行緒並行寫入不遺失資料（fcntl.flock 防護驗證）"""
        import threading

        errors = []
        num_threads = 5

        def write_dispatch(thread_id):
            try:
                record_dispatch(project_root, f"Thread-{thread_id}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_dispatch, args=(i,))
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"並行寫入發生錯誤: {errors}"
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == num_threads, (
            f"預期 {num_threads} 筆記錄，實際 {len(dispatches)} 筆（資料遺失）"
        )


class TestAtomicWrite:
    """_write_state 的 tempfile + os.replace 原子替換（0.2.1-W3-556）。"""

    def test_fsync_failure_writes_stderr_and_still_persists(
        self, project_root: Path, capsys
    ):
        """fsync 失敗不阻斷寫入（os.replace 仍執行，資料正確落地），但需
        可觀測（規則 4）：stderr 記一筆警示。"""
        with patch(
            "lib.dispatch_tracker.os.fsync", side_effect=OSError("fsync unsupported")
        ):
            record_dispatch(project_root, "Task despite fsync failure")

        state_file = get_state_file_path(project_root)
        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data["dispatches"]) == 1

        err = capsys.readouterr().err
        assert "fsync 失敗" in err
        assert "不影響本次寫入" in err

    def test_no_temp_file_left_behind_after_success(self, project_root: Path):
        record_dispatch(project_root, "Task A")
        state_file = get_state_file_path(project_root)
        siblings = [
            p for p in state_file.parent.iterdir() if p.name != "dispatch-active.lock"
        ]
        assert siblings == [state_file]

    def test_replace_failure_cleans_up_temp_file_and_raises(self, project_root: Path):
        state_file = get_state_file_path(project_root)

        with patch("lib.dispatch_tracker.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                record_dispatch(project_root, "Task fails to persist")

        leftovers = list(state_file.parent.glob("*.tmp.*"))
        assert leftovers == []
        assert not state_file.exists()

    def test_write_failure_preserves_previous_content(self, project_root: Path):
        """寫入失敗時，既有狀態檔內容維持原封不動（原子替換未發生）。"""
        record_dispatch(project_root, "Task keep")
        state_file = get_state_file_path(project_root)
        before = state_file.read_text(encoding="utf-8")

        with patch("lib.dispatch_tracker.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                record_dispatch(project_root, "Task should not land")

        after = state_file.read_text(encoding="utf-8")
        assert before == after

    def test_concurrent_read_during_write_never_sees_torn_content(
        self, project_root: Path
    ):
        """讀端在寫入密集進行時反覆讀取，永遠看到完整可解析的 JSON（不會 torn read）。

        直接讀原始檔案（非透過 get_active_dispatches，其記憶體快取層會
        遮蔽本測試要驗證的 torn-write 問題）。
        """
        import threading

        state_file = get_state_file_path(project_root)
        record_dispatch(project_root, "seed")

        stop_flag = threading.Event()
        errors = []

        def reader():
            while not stop_flag.is_set():
                if state_file.exists():
                    try:
                        json.loads(state_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as e:
                        errors.append(e)

        reader_thread = threading.Thread(target=reader)
        reader_thread.start()
        try:
            for i in range(150):
                record_dispatch(project_root, f"writer-{i}")
        finally:
            stop_flag.set()
            reader_thread.join(timeout=5)

        assert errors == []
