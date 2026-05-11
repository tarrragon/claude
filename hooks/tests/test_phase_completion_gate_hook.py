"""
Phase Completion Gate Hook - 路徑黑名單測試

驗證 W10-072.1 路徑排除規則：
- tickets/ 子目錄不觸發 phase 報告檢查
- worklog 主檔（v{major}.{minor}.{patch}.md）不觸發
- 真實 phase 報告路徑仍然觸發
"""

import logging
from pathlib import Path
import importlib.util


# 動態載入 hook 模組（檔名含 dash，無法直接 import）
hooks_dir = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "phase_completion_gate_hook",
    str(hooks_dir / "phase-completion-gate-hook.py"),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _logger():
    logger = logging.getLogger("test_phase_completion_gate_hook")
    logger.setLevel(logging.DEBUG)
    return logger


# ----------------------------------------------------------------------------
# W10-072.1：tickets/ 子目錄排除
# ----------------------------------------------------------------------------

def test_ticket_md_in_tickets_subdir_not_triggered():
    """ticket md（tickets/ 子目錄）不應觸發 phase 報告檢查"""
    file_path = "docs/work-logs/v0.18.0/tickets/0.18.0-W10-072.1.md"
    result = module.is_worklog_write_operation(
        "Edit", {"file_path": file_path}, _logger()
    )
    assert result is False, "tickets/ 子目錄應被排除"


def test_nested_ticket_md_not_triggered():
    """巢狀版本路徑下的 ticket md 也應被排除"""
    file_path = "docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W10-072.md"
    result = module.is_worklog_write_operation(
        "Write", {"file_path": file_path}, _logger()
    )
    assert result is False, "巢狀 tickets/ 子目錄也應被排除"


# ----------------------------------------------------------------------------
# W10-072.1：worklog 主檔排除
# ----------------------------------------------------------------------------

def test_worklog_main_file_not_triggered():
    """worklog patch 級主檔（v0.18.0.md）不應觸發"""
    file_path = "docs/work-logs/v0.18.0/v0.18.0.md"
    result = module.is_worklog_write_operation(
        "Edit", {"file_path": file_path}, _logger()
    )
    assert result is False, "worklog 主檔應被排除"


def test_worklog_main_file_absolute_path_not_triggered():
    """絕對路徑下的 worklog 主檔也應被排除"""
    file_path = "/Users/dev/project/docs/work-logs/v1.2.3/v1.2.3.md"
    result = module.is_worklog_write_operation(
        "Write", {"file_path": file_path}, _logger()
    )
    assert result is False


# ----------------------------------------------------------------------------
# W10-072.1：真實 phase 報告仍然觸發
# ----------------------------------------------------------------------------

def test_phase_report_file_still_triggered():
    """真正的 phase 完成報告檔案應仍觸發檢查"""
    file_path = "docs/work-logs/v0.18.0/phase4-evaluation.md"
    result = module.is_worklog_write_operation(
        "Edit", {"file_path": file_path}, _logger()
    )
    assert result is True, "phase 報告檔案應觸發檢查"


def test_other_worklog_file_still_triggered():
    """worklog 目錄下非主檔且非 tickets 子目錄的檔案仍觸發"""
    file_path = "docs/work-logs/v0.18.0/some-phase-report.md"
    result = module.is_worklog_write_operation(
        "Write", {"file_path": file_path}, _logger()
    )
    assert result is True


# ----------------------------------------------------------------------------
# 邊界 / 既有行為保留
# ----------------------------------------------------------------------------

def test_non_worklog_path_not_triggered():
    """非 worklog 路徑不觸發"""
    file_path = "src/foo/bar.py"
    result = module.is_worklog_write_operation(
        "Edit", {"file_path": file_path}, _logger()
    )
    assert result is False


def test_non_write_tool_not_triggered():
    """非 Write/Edit 工具不觸發"""
    file_path = "docs/work-logs/v0.18.0/phase4.md"
    result = module.is_worklog_write_operation(
        "Read", {"file_path": file_path}, _logger()
    )
    assert result is False


def test_minor_version_worklog_not_excluded_as_main_file():
    """非 patch 級命名（如 v0.18.md）不命中 main file 排除規則"""
    # v0.18.md 不符合 v\d+\.\d+\.\d+\.md，故不被當主檔排除
    file_path = "docs/work-logs/v0.18/v0.18.md"
    result = module.is_worklog_write_operation(
        "Edit", {"file_path": file_path}, _logger()
    )
    assert result is True
