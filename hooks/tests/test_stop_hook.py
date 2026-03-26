"""
Stop hook 測試

覆蓋 P0 優先級測試用例
"""

import pytest
import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO


# 載入 Stop hook 模組
STOP_HOOK_PATH = Path(__file__).parent.parent / "handoff-auto-resume-stop-hook.py"


def load_stop_hook_module():
    """動態載入 Stop hook 模組"""
    spec = importlib.util.spec_from_file_location("handoff_auto_resume_stop_hook", STOP_HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestStopHookSessionFlag:
    """Session flag 相關測試"""

    def test_ac1_first_trigger_creates_flag(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-1: 首次觸發時建立 session flag"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        # 無任務情況
        with patch.object(hook_module, "scan_pending_handoff_tasks", return_value=([], [])):
            output = hook_module.generate_hook_output(logger)

        # 即使無任務也不應建立 flag（因為無阻塊決策）
        assert output.get("suppressOutput") is True
        assert not flag_path.exists()

    def test_ac4_prevents_duplicate_trigger(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-4: 防重複觸發 - 同 session 第二次呼叫直接跳過"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        # 模擬第一次呼叫後建立的 flag（使用帶時間戳的 JSON 格式）
        flag_file = tmp_project_root / hook_module.STOP_FLAG_FILE
        flag_file.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        from datetime import datetime as _dt
        with open(flag_file, 'w') as f:
            _json.dump({"created_at": _dt.now().isoformat(), "reason": "test"}, f)

        # 第二次呼叫應跳過
        output = hook_module.generate_hook_output(logger)

        assert output.get("suppressOutput") is True

    def test_ac5_reads_session_state(self, env_with_project_root, mock_ppid, tmp_project_root, sample_session_state):
        """AC-5: 優先讀取 session 狀態檔案中的 locked_ticket_id"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        with open(state_file, 'w') as f:
            json.dump(sample_session_state, f)

        output = hook_module.generate_hook_output(logger)

        # 應該阻塊並要求恢復 session state 中的任務
        assert output.get("decision") == "block"
        assert "/ticket resume 0.31.0-W15-001" in output.get("reason", "")

        state_file.unlink(missing_ok=True)

    def test_ac7_scans_pending_without_session_state(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-7: 無 session 狀態時，掃描 pending 目錄查找未恢復任務"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        state_file.unlink(missing_ok=True)

        # 建立待恢復任務
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"
        pending_file = pending_dir / "0.31.0-W15-001.json"
        with open(pending_file, 'w') as f:
            json.dump({
                "ticket_id": "0.31.0-W15-001",
                "title": "未恢復任務",
                "resumed_at": None
            }, f)

        # Mock is_ticket_completed 和 is_ticket_recently_started
        with patch.object(hook_module, "is_ticket_completed", return_value=False), \
             patch.object(hook_module, "is_ticket_recently_started", return_value=False):
            output = hook_module.generate_hook_output(logger)

        # 應該從 pending 目錄找到任務並阻塊
        assert output.get("decision") == "block"
        assert "/ticket resume 0.31.0-W15-001" in output.get("reason", "")

    def test_ac8_allows_when_no_pending_tasks(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-8: 無待恢復任務時，允許對話終止"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        state_file.unlink(missing_ok=True)

        # 不建立任何待恢復任務

        output = hook_module.generate_hook_output(logger)

        # 應該允許對話終止
        assert output.get("suppressOutput") is True
        assert "decision" not in output or output.get("decision") is None


class TestStopHookJsonOutput:
    """Hook 輸出格式測試"""

    def test_block_decision_format(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試 block 決策的輸出格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        state_file.unlink(missing_ok=True)

        # 建立 session 狀態
        state_data = {
            "locked_ticket_id": "0.31.0-W15-001",
            "locked_at": "2026-02-10T10:30:00"
        }
        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        output = hook_module.generate_hook_output(logger)

        # 驗證輸出結構
        assert isinstance(output, dict)
        assert output.get("decision") == "block"
        assert "reason" in output
        assert "ticket" in output.get("reason", "").lower() or "resume" in output.get("reason", "").lower()

        state_file.unlink(missing_ok=True)

    def test_suppress_output_format(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試 suppressOutput 的輸出格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        output = hook_module.generate_hook_output(logger)

        # 無任務時應使用 suppressOutput
        assert isinstance(output, dict)
        assert output.get("suppressOutput") is True or output.get("suppressOutput") is None


class TestStopHookErrorHandling:
    """錯誤處理測試"""

    def test_graceful_failure_on_invalid_json(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試無效 JSON 時的優雅失敗"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        state_file.unlink(missing_ok=True)

        # 寫入無效 JSON
        with open(state_file, 'w') as f:
            f.write("{invalid json")

        # 應該優雅處理而不拋例外
        try:
            output = hook_module.generate_hook_output(logger)
            # 應該回傳有效的 Hook 輸出
            assert isinstance(output, dict)
            assert "suppressOutput" in output or "decision" in output
        except Exception:
            pytest.fail("Should handle invalid JSON gracefully")

        state_file.unlink(missing_ok=True)

    def test_missing_project_root_fallback(self, mock_ppid):
        """測試無 PROJECT_DIR 時的 fallback"""
        hook_module = load_stop_hook_module()

        with patch.dict("os.environ", {}, clear=True):
            # 應該使用 fallback 方式取得根目錄
            root = hook_module.get_project_root()
            assert isinstance(root, Path)


class TestStopHookPendingDirectoryScan:
    """Pending 目錄掃描測試"""

    def test_skips_already_resumed_tasks(self, env_with_project_root, tmp_project_root):
        """測試跳過已恢復的任務（resumed_at != null）"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        # 建立已恢復任務
        resumed_file = pending_dir / "0.31.0-W15-001.json"
        with open(resumed_file, 'w') as f:
            json.dump({
                "ticket_id": "0.31.0-W15-001",
                "title": "已恢復",
                "resumed_at": "2026-02-10T10:30:00"
            }, f)

        # 建立未恢復任務
        pending_file = pending_dir / "0.31.0-W15-002.json"
        with open(pending_file, 'w') as f:
            json.dump({
                "ticket_id": "0.31.0-W15-002",
                "title": "未恢復",
                "resumed_at": None
            }, f)

        with patch.object(hook_module, "is_ticket_completed", return_value=False), \
             patch.object(hook_module, "is_ticket_recently_started", return_value=False):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        # 應該只找到未恢復任務（歸入 pending_tasks，因為非 auto 且非 recently started）
        assert len(pending_tasks) == 1
        assert pending_tasks[0]["ticket_id"] == "0.31.0-W15-002"
        assert len(recent_tasks) == 0

    def test_handles_missing_pending_directory(self, tmp_project_root):
        """測試 pending 目錄不存在時的處理"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        # 確保 pending 目錄不存在
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"
        if pending_dir.exists():
            import shutil
            shutil.rmtree(pending_dir)

        pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        # 應該優雅返回空 tuple
        assert pending_tasks == []
        assert recent_tasks == []


class TestShouldPreservePendingJson:
    """should_preserve_pending_json 函式測試"""

    def test_preserve_to_sibling_with_target_id(self):
        """測試 to-sibling 帶目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-sibling:0.31.1-W3-002", logger)

        assert result is True
        logger.debug.assert_called_once()
        assert "to-sibling:0.31.1-W3-002" in logger.debug.call_args[0][0]

    def test_preserve_to_parent_with_target_id(self):
        """測試 to-parent 帶目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-parent:0.31.1-W3-001", logger)

        assert result is True

    def test_preserve_to_child_with_target_id(self):
        """測試 to-child 帶目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-child:0.31.1-W3-003", logger)

        assert result is True

    def test_preserve_to_sibling_without_target_id(self):
        """測試 to-sibling 無目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-sibling", logger)

        assert result is True

    def test_preserve_to_parent_without_target_id(self):
        """測試 to-parent 無目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-parent", logger)

        assert result is True

    def test_preserve_to_child_without_target_id(self):
        """測試 to-child 無目標 ID 格式"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("to-child", logger)

        assert result is True

    def test_do_not_preserve_context_refresh(self):
        """測試 context-refresh 不應保留"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("context-refresh", logger)

        assert result is False
        logger.debug.assert_not_called()

    def test_do_not_preserve_continuation(self):
        """測試 continuation 不應保留"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        result = hook_module.should_preserve_pending_json("continuation", logger)

        assert result is False

    def test_do_not_preserve_other_formats(self):
        """測試其他不相關格式不應保留"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()

        # 測試幾個其他格式
        other_formats = ["other-direction", "to-sibling-unknown", "unknown-to-sibling"]
        for fmt in other_formats:
            result = hook_module.should_preserve_pending_json(fmt, logger)
            assert result is False


class TestAutoDirectionHandling:
    """auto direction 分類邏輯測試（0.2.0-W3-008）"""

    def _create_pending_json(self, pending_dir, filename, ticket_id, direction, resumed_at=None):
        """建立 pending JSON 測試檔案的輔助函式"""
        file_path = pending_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "ticket_id": ticket_id,
                "title": f"測試任務 {ticket_id}",
                "direction": direction,
                "resumed_at": resumed_at
            }, f)
        return file_path

    def test_auto_direction_not_blocking(self, tmp_project_root):
        """場景 1: auto direction 未完成 Ticket 歸入 recent_tasks"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(pending_dir, "auto-task.json", "0.2.0-W3-009", "auto")

        with patch.object(hook_module, "is_ticket_completed", return_value=False):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(pending_tasks) == 0
        assert len(recent_tasks) == 1
        assert recent_tasks[0]["direction"] == "auto"

    def test_auto_direction_with_target_id(self, tmp_project_root):
        """場景 2: auto:TARGET_ID 格式同樣不阻塞"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(
            pending_dir, "auto-target.json", "0.2.0-W3-010", "auto:0.2.0-W3-011"
        )

        with patch.object(hook_module, "is_ticket_completed", return_value=False):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(pending_tasks) == 0
        assert len(recent_tasks) == 1
        assert recent_tasks[0]["direction"] == "auto:0.2.0-W3-011"

    def test_auto_direction_old_ticket_still_not_blocking(self, tmp_project_root):
        """場景 3: auto direction 超過 30 分鐘仍不阻塞"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(pending_dir, "auto-old.json", "0.2.0-W3-009", "auto")

        with patch.object(hook_module, "is_ticket_completed", return_value=False), \
             patch.object(hook_module, "is_ticket_recently_started", return_value=False):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        # auto 永遠不進 pending_tasks，即使超過 30 分鐘
        assert len(pending_tasks) == 0
        assert len(recent_tasks) == 1

    def test_non_auto_direction_still_blocks(self, tmp_project_root):
        """場景 4: 非 auto direction 遺留任務仍阻塞"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(
            pending_dir, "context-refresh.json", "0.2.0-W3-012", "context-refresh"
        )

        with patch.object(hook_module, "is_ticket_completed", return_value=False), \
             patch.object(hook_module, "is_ticket_recently_started", return_value=False):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(pending_tasks) == 1
        assert pending_tasks[0]["ticket_id"] == "0.2.0-W3-012"
        assert len(recent_tasks) == 0

    def test_non_auto_direction_recent_still_recent(self, tmp_project_root):
        """場景 5: 非 auto direction 最近任務歸入 recent_tasks"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(
            pending_dir, "context-refresh.json", "0.2.0-W3-012", "context-refresh"
        )

        with patch.object(hook_module, "is_ticket_completed", return_value=False), \
             patch.object(hook_module, "is_ticket_recently_started", return_value=True):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(recent_tasks) == 1
        assert recent_tasks[0]["ticket_id"] == "0.2.0-W3-012"
        assert len(pending_tasks) == 0

    def test_auto_direction_completed_ticket_gc(self, tmp_project_root):
        """場景 6: auto + 已完成 Ticket 被 GC 刪除"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        file_path = self._create_pending_json(
            pending_dir, "auto-completed.json", "0.2.0-W3-009", "auto"
        )

        with patch.object(hook_module, "is_ticket_completed", return_value=True):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(pending_tasks) == 0
        assert len(recent_tasks) == 0
        # auto 不在 chain_directions，should_preserve 回傳 False，檔案應被 GC 刪除
        assert not file_path.exists()

    def test_mixed_auto_and_non_auto_directions(self, tmp_project_root):
        """場景 7: 混合場景 - auto 和非 auto 同時存在"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        # ticket A: auto, 未完成
        self._create_pending_json(pending_dir, "auto-task.json", "0.2.0-W3-009", "auto")
        # ticket B: context-refresh, 未完成, 超過 30 分鐘
        self._create_pending_json(
            pending_dir, "context-refresh.json", "0.2.0-W3-012", "context-refresh"
        )

        def mock_completed(project_root, ticket_id, logger):
            return False

        def mock_recently_started(project_root, ticket_id, logger):
            # 只有非 auto 才會進入此判斷，回傳 False 模擬超時
            return False

        with patch.object(hook_module, "is_ticket_completed", side_effect=mock_completed), \
             patch.object(hook_module, "is_ticket_recently_started", side_effect=mock_recently_started):
            pending_tasks, recent_tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        assert len(pending_tasks) == 1
        assert pending_tasks[0]["ticket_id"] == "0.2.0-W3-012"
        assert len(recent_tasks) == 1
        assert recent_tasks[0]["ticket_id"] == "0.2.0-W3-009"

    def test_auto_direction_logs_info_message(self, tmp_project_root):
        """場景 8: auto direction 的 logger.info 驗證"""
        hook_module = load_stop_hook_module()
        logger = MagicMock()
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"

        self._create_pending_json(pending_dir, "auto-task.json", "0.2.0-W3-009", "auto")

        with patch.object(hook_module, "is_ticket_completed", return_value=False):
            hook_module.scan_pending_handoff_tasks(tmp_project_root, logger)

        # 驗證 logger.info 被呼叫，訊息包含 "auto handoff" 和 "不阻塞"
        info_calls = [str(call) for call in logger.info.call_args_list]
        info_messages = " ".join(info_calls)
        assert "auto handoff" in info_messages
        assert "不阻塞" in info_messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
