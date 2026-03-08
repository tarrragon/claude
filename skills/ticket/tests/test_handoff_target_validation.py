"""
Handoff 目標 ticket 存在性驗證（W5-002）和重複 handoff 警告（W5-003）測試

W5-002: 驗證 _validate_target_ticket_exists() 正確偵測不存在的目標 ticket
W5-003: 驗證 _validate_no_duplicate_handoff() 正確偵測重複的 pending handoff
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands.exceptions import (
    HandoffTargetNotFoundError,
    HandoffDuplicateError,
)
from ticket_system.commands.handoff import (
    _validate_target_ticket_exists,
    _validate_no_duplicate_handoff,
)


# ==============================================================================
# W5-002: 目標 ticket 存在性驗證
# ==============================================================================


class TestValidateTargetTicketExists:
    """測試 _validate_target_ticket_exists 函式"""

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_to_sibling_existing_target_no_exception(self, mock_load):
        """to-sibling 指向存在的 ticket 不應拋出例外"""
        mock_load.return_value = {"id": "0.1.0-W5-002", "status": "pending"}
        _validate_target_ticket_exists("to-sibling:0.1.0-W5-002", "0.1.0")  # 不應拋出

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_to_sibling_missing_target_raises_error(self, mock_load):
        """to-sibling 指向不存在的 ticket 應拋出 HandoffTargetNotFoundError"""
        mock_load.return_value = None
        with pytest.raises(HandoffTargetNotFoundError) as exc_info:
            _validate_target_ticket_exists("to-sibling:0.1.0-W5-999", "0.1.0")
        assert exc_info.value.target_id == "0.1.0-W5-999"

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_to_child_existing_target_no_exception(self, mock_load):
        """to-child 指向存在的 ticket 不應拋出例外"""
        mock_load.return_value = {"id": "0.1.0-W5-003", "status": "pending"}
        _validate_target_ticket_exists("to-child:0.1.0-W5-003", "0.1.0")  # 不應拋出

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_to_child_missing_target_raises_error(self, mock_load):
        """to-child 指向不存在的 ticket 應拋出 HandoffTargetNotFoundError"""
        mock_load.return_value = None
        with pytest.raises(HandoffTargetNotFoundError) as exc_info:
            _validate_target_ticket_exists("to-child:0.1.0-W5-999", "0.1.0")
        assert exc_info.value.target_id == "0.1.0-W5-999"

    def test_to_parent_skips_validation(self):
        """to-parent 無 target_id，不應執行驗證（不應拋出）"""
        _validate_target_ticket_exists("to-parent", "0.1.0")  # 不應拋出

    def test_context_refresh_skips_validation(self):
        """context-refresh 不應執行驗證（不應拋出）"""
        _validate_target_ticket_exists("context-refresh", "0.1.0")  # 不應拋出

    def test_auto_skips_validation(self):
        """auto 不應執行驗證（不應拋出）"""
        _validate_target_ticket_exists("auto", "0.1.0")  # 不應拋出

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_error_contains_target_id_in_message(self, mock_load):
        """HandoffTargetNotFoundError 訊息包含目標 ID"""
        mock_load.return_value = None
        with pytest.raises(HandoffTargetNotFoundError) as exc_info:
            _validate_target_ticket_exists("to-sibling:0.1.0-W5-999", "0.1.0")
        assert "0.1.0-W5-999" in str(exc_info.value)

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_error_has_actionable_guidance(self, mock_load):
        """HandoffTargetNotFoundError 包含可操作指引"""
        mock_load.return_value = None
        with pytest.raises(HandoffTargetNotFoundError) as exc_info:
            _validate_target_ticket_exists("to-sibling:0.1.0-W5-999", "0.1.0")
        assert exc_info.value.guidance != ""
        assert "0.1.0-W5-999" in exc_info.value.guidance

    @patch("ticket_system.commands.handoff.load_ticket")
    def test_load_ticket_called_with_correct_args(self, mock_load):
        """load_ticket 應使用正確的 version 和 target_id"""
        mock_load.return_value = {"id": "0.1.0-W5-002"}
        _validate_target_ticket_exists("to-sibling:0.1.0-W5-002", "0.1.0")
        mock_load.assert_called_once_with("0.1.0", "0.1.0-W5-002")


# ==============================================================================
# W5-003: 重複 handoff 警告
# ==============================================================================


@pytest.fixture
def temp_handoff_env():
    """建立臨時 handoff 環境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        handoff_pending = project_root / ".claude" / "handoff" / "pending"
        handoff_pending.mkdir(parents=True, exist_ok=True)
        (project_root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, handoff_pending
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _write_pending_handoff(pending_dir: Path, ticket_id: str, timestamp: str = "2026-01-30T12:00:00") -> None:
    """在 pending 目錄建立測試用 handoff JSON"""
    data = {
        "ticket_id": ticket_id,
        "direction": "context-refresh",
        "timestamp": timestamp,
    }
    path = pending_dir / f"{ticket_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class TestValidateNoDuplicateHandoff:
    """測試 _validate_no_duplicate_handoff 函式"""

    def test_no_pending_dir_no_exception(self, temp_handoff_env):
        """pending 目錄不存在時，不應拋出例外"""
        project_root, pending_dir = temp_handoff_env
        pending_dir.rmdir()  # 移除目錄
        _validate_no_duplicate_handoff("0.1.0-W5-001")  # 不應拋出

    def test_no_existing_handoff_no_exception(self, temp_handoff_env):
        """不存在重複的 pending handoff 時，不應拋出例外"""
        project_root, pending_dir = temp_handoff_env
        _validate_no_duplicate_handoff("0.1.0-W5-001")  # 不應拋出

    def test_existing_handoff_raises_error(self, temp_handoff_env):
        """已存在相同 ticket_id 的 pending handoff 時，應拋出 HandoffDuplicateError"""
        project_root, pending_dir = temp_handoff_env
        _write_pending_handoff(pending_dir, "0.1.0-W5-001", "2026-01-30T12:00:00")
        with pytest.raises(HandoffDuplicateError) as exc_info:
            _validate_no_duplicate_handoff("0.1.0-W5-001")
        assert exc_info.value.ticket_id == "0.1.0-W5-001"

    def test_existing_handoff_timestamp_in_error(self, temp_handoff_env):
        """HandoffDuplicateError 包含既有 handoff 的時間戳"""
        project_root, pending_dir = temp_handoff_env
        _write_pending_handoff(pending_dir, "0.1.0-W5-001", "2026-01-30T12:34:56")
        with pytest.raises(HandoffDuplicateError) as exc_info:
            _validate_no_duplicate_handoff("0.1.0-W5-001")
        assert exc_info.value.existing_timestamp == "2026-01-30T12:34:56"

    def test_different_ticket_id_no_exception(self, temp_handoff_env):
        """不同 ticket_id 的 pending handoff 不應觸發驗證失敗"""
        project_root, pending_dir = temp_handoff_env
        _write_pending_handoff(pending_dir, "0.1.0-W5-002")
        _validate_no_duplicate_handoff("0.1.0-W5-001")  # 不同 ID，不應拋出

    def test_malformed_handoff_uses_fallback_timestamp(self, temp_handoff_env):
        """損壞的 handoff JSON 應使用備援時間戳"""
        project_root, pending_dir = temp_handoff_env
        # 寫入損壞的 JSON
        path = pending_dir / "0.1.0-W5-001.json"
        path.write_text("not valid json", encoding="utf-8")
        with pytest.raises(HandoffDuplicateError) as exc_info:
            _validate_no_duplicate_handoff("0.1.0-W5-001")
        # 應使用備援時間戳（不崩潰）
        assert exc_info.value.existing_timestamp != ""

    def test_error_has_guidance(self, temp_handoff_env):
        """HandoffDuplicateError 包含可操作指引"""
        project_root, pending_dir = temp_handoff_env
        _write_pending_handoff(pending_dir, "0.1.0-W5-001")
        with pytest.raises(HandoffDuplicateError) as exc_info:
            _validate_no_duplicate_handoff("0.1.0-W5-001")
        assert exc_info.value.guidance != ""
        assert "0.1.0-W5-001" in exc_info.value.guidance
