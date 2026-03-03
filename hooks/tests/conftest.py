"""
Pytest 測試配置

提供共用的 fixture 和測試工具
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def tmp_project_root():
    """建立臨時專案根目錄結構"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 建立目錄結構
        (root / ".claude" / "handoff" / "pending").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "work-logs" / "v0.31.0" / "tickets").mkdir(parents=True, exist_ok=True)

        yield root


@pytest.fixture
def env_with_project_root(tmp_project_root):
    """設定環境變數指向臨時專案根目錄"""
    with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_project_root)}):
        yield tmp_project_root


@pytest.fixture
def mock_ppid():
    """模擬父進程 PID"""
    with patch("os.getppid", return_value=12345):
        yield 12345


@pytest.fixture
def sample_handoff_data():
    """範例 handoff 資料"""
    return {
        "ticket_id": "0.31.0-W15-001",
        "title": "測試任務",
        "direction": "continuation",
        "created_at": "2026-02-10T10:00:00",
        "resumed_at": None
    }


@pytest.fixture
def sample_session_state():
    """範例 session 狀態資料"""
    return {
        "locked_ticket_id": "0.31.0-W15-001",
        "locked_at": "2026-02-10T10:30:00"
    }
