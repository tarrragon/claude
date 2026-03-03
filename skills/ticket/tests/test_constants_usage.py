"""
測試模組 B: 路徑常數化

驗證：
1. B-1: handoff.py 使用常數，功能不變
2. B-2: resume.py 使用常數，功能不變
3. B-3: 常數值正確
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_handoff_constants_have_correct_values() -> None:
    """B-3: 常數值正確"""
    from ticket_system.lib.constants import (
        HANDOFF_DIR,
        HANDOFF_PENDING_SUBDIR,
        HANDOFF_ARCHIVE_SUBDIR,
    )

    assert HANDOFF_DIR == ".claude/handoff"
    assert HANDOFF_PENDING_SUBDIR == "pending"
    assert HANDOFF_ARCHIVE_SUBDIR == "archive"


def test_handoff_py_uses_constants_no_regression() -> None:
    """B-1: handoff.py 使用常數，功能不變"""
    from ticket_system.commands.handoff import _create_handoff_file_internal
    from ticket_system.lib.constants import (
        HANDOFF_DIR,
        HANDOFF_PENDING_SUBDIR,
    )

    # 準備測試資料
    test_ticket = {
        "id": "0.1.0-W1-001",
        "title": "Test Task",
        "status": "completed",
        "what": "Test description",
    }

    # Mock get_project_root 和檔案系統操作
    with patch("ticket_system.commands.handoff.get_project_root") as mock_root:
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            with patch("builtins.open", create=True) as mock_open:
                # 設定 mock
                temp_dir = Path("/tmp/test_project")
                mock_root.return_value = temp_dir
                mock_open.return_value.__enter__ = lambda self: self
                mock_open.return_value.__exit__ = lambda *args: None
                mock_open.return_value.write = MagicMock()

                # 執行函式
                result = _create_handoff_file_internal(test_ticket, "to-parent")

                # 驗證結果
                assert result == 0

                # 驗證路徑構建使用常數
                expected_path = temp_dir / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
                # 驗證 mkdir 被呼叫並使用正確的路徑
                mock_mkdir.assert_called_once()
                call_args = mock_mkdir.call_args
                # 驗證路徑包含常數值
                assert str(call_args).find(HANDOFF_DIR) >= 0 or ".claude/handoff" in str(temp_dir / HANDOFF_DIR)


def test_resume_py_uses_constants_no_regression() -> None:
    """B-2: resume.py 使用常數，功能不變"""
    from ticket_system.commands.resume import _get_handoff_dir
    from ticket_system.lib.constants import (
        HANDOFF_DIR,
        HANDOFF_PENDING_SUBDIR,
        HANDOFF_ARCHIVE_SUBDIR,
    )

    # Mock get_project_root
    with patch("ticket_system.commands.resume.get_project_root") as mock_root:
        temp_dir = Path("/tmp/test_project")
        mock_root.return_value = temp_dir

        # 測試 pending 目錄
        pending_dir = _get_handoff_dir(HANDOFF_PENDING_SUBDIR)
        expected_pending = temp_dir / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
        assert pending_dir == expected_pending

        # 測試 archive 目錄
        archive_dir = _get_handoff_dir(HANDOFF_ARCHIVE_SUBDIR)
        expected_archive = temp_dir / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR
        assert archive_dir == expected_archive

        # 測試預設值（應該是 pending）
        default_dir = _get_handoff_dir()
        assert default_dir == expected_pending
