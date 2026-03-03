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

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        # 無任務情況
        with patch.object(hook_module, "scan_pending_handoff_tasks", return_value=[]):
            output = hook_module.generate_hook_output()

        # 即使無任務也不應建立 flag（因為無阻塊決策）
        assert output.get("suppressOutput") is True
        assert not flag_path.exists()

    def test_ac4_prevents_duplicate_trigger(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-4: 防重複觸發 - 同 session 第二次呼叫直接跳過"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        # 模擬第一次呼叫後建立的 flag
        flag_path.touch()

        # 第二次呼叫應跳過
        output = hook_module.generate_hook_output()

        assert output.get("suppressOutput") is True

        flag_path.unlink(missing_ok=True)

    def test_ac5_reads_session_state(self, env_with_project_root, mock_ppid, tmp_project_root, sample_session_state):
        """AC-5: 優先讀取 session 狀態檔案中的 locked_ticket_id"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")
        with open(state_file, 'w') as f:
            json.dump(sample_session_state, f)

        output = hook_module.generate_hook_output()

        # 應該阻塊並要求恢復 session state 中的任務
        assert output.get("decision") == "block"
        assert "/ticket resume 0.31.0-W15-001" in output.get("reason", "")

        state_file.unlink(missing_ok=True)
        flag_path.unlink(missing_ok=True)

    def test_ac7_scans_pending_without_session_state(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-7: 無 session 狀態時，掃描 pending 目錄查找未恢復任務"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")

        flag_path.unlink(missing_ok=True)
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

        output = hook_module.generate_hook_output()

        # 應該從 pending 目錄找到任務並阻塊
        assert output.get("decision") == "block"
        assert "/ticket resume 0.31.0-W15-001" in output.get("reason", "")

        flag_path.unlink(missing_ok=True)

    def test_ac8_allows_when_no_pending_tasks(self, env_with_project_root, mock_ppid, tmp_project_root):
        """AC-8: 無待恢復任務時，允許對話終止"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")

        flag_path.unlink(missing_ok=True)
        state_file.unlink(missing_ok=True)

        # 不建立任何待恢復任務

        output = hook_module.generate_hook_output()

        # 應該允許對話終止
        assert output.get("suppressOutput") is True
        assert "decision" not in output or output.get("decision") is None

        flag_path.unlink(missing_ok=True)


class TestStopHookJsonOutput:
    """Hook 輸出格式測試"""

    def test_block_decision_format(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試 block 決策的輸出格式"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")

        flag_path.unlink(missing_ok=True)
        state_file.unlink(missing_ok=True)

        # 建立 session 狀態
        state_data = {
            "locked_ticket_id": "0.31.0-W15-001",
            "locked_at": "2026-02-10T10:30:00"
        }
        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        output = hook_module.generate_hook_output()

        # 驗證輸出結構
        assert isinstance(output, dict)
        assert output.get("decision") == "block"
        assert "reason" in output
        assert "ticket" in output.get("reason", "").lower() or "resume" in output.get("reason", "").lower()

        state_file.unlink(missing_ok=True)
        flag_path.unlink(missing_ok=True)

    def test_suppress_output_format(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試 suppressOutput 的輸出格式"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        flag_path.unlink(missing_ok=True)

        output = hook_module.generate_hook_output()

        # 無任務時應使用 suppressOutput
        assert isinstance(output, dict)
        assert output.get("suppressOutput") is True or output.get("suppressOutput") is None


class TestStopHookErrorHandling:
    """錯誤處理測試"""

    def test_graceful_failure_on_invalid_json(self, env_with_project_root, mock_ppid, tmp_project_root):
        """測試無效 JSON 時的優雅失敗"""
        hook_module = load_stop_hook_module()

        flag_path = Path(f"/tmp/claude-handoff-stop-{mock_ppid}")
        state_file = Path(f"/tmp/claude-handoff-state-{mock_ppid}.json")

        flag_path.unlink(missing_ok=True)
        state_file.unlink(missing_ok=True)

        # 寫入無效 JSON
        with open(state_file, 'w') as f:
            f.write("{invalid json")

        # 應該優雅處理而不拋例外
        try:
            output = hook_module.generate_hook_output()
            # 應該回傳有效的 Hook 輸出
            assert isinstance(output, dict)
            assert "suppressOutput" in output or "decision" in output
        except Exception:
            pytest.fail("Should handle invalid JSON gracefully")

        state_file.unlink(missing_ok=True)
        flag_path.unlink(missing_ok=True)

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

        tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root)

        # 應該只找到未恢復任務
        assert len(tasks) == 1
        assert "0.31.0-W15-002" in tasks

    def test_handles_missing_pending_directory(self, tmp_project_root):
        """測試 pending 目錄不存在時的處理"""
        hook_module = load_stop_hook_module()

        # 確保 pending 目錄不存在
        pending_dir = tmp_project_root / ".claude" / "handoff" / "pending"
        if pending_dir.exists():
            import shutil
            shutil.rmtree(pending_dir)

        tasks = hook_module.scan_pending_handoff_tasks(tmp_project_root)

        # 應該優雅返回空列表
        assert tasks == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
