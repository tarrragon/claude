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


# ----------------------------------------------------------------------------
# W11-017：三層 guard 精度修正（status / 章節位置 / ticket frontmatter）
# ----------------------------------------------------------------------------

# 模擬 pending ticket 的內容（含「Phase 4」字串，但只是文本引用）
_PENDING_TICKET_CONTENT = """---
id: 0.18.0-W11-099
title: 範例 ticket
type: IMP
status: pending
---

# Execution Log

## Problem Analysis

修復策略：Phase 4 評估時需注意 X。文中提到 Phase 4 屬於文本引用，
不應被視為「自身的 Phase 4 完成報告」。

## Solution

<!-- To be filled by executing agent -->
"""

# 模擬 in_progress ticket 真正寫 Phase 4 章節，但 Solution 空
_INPROGRESS_TICKET_PHASE4_EMPTY_SOLUTION = """---
id: 0.18.0-W11-100
title: 真實 Phase 4 評估
type: IMP
status: in_progress
---

# Execution Log

## Phase 4 評估

實作已重構完成。

## Solution

<!-- To be filled by executing agent -->
"""

# 獨立 phase 完成報告檔（無 frontmatter id，路徑亦非 tickets/）
_STANDALONE_PHASE_REPORT_CONTENT = """# Phase 4 評估報告

## Problem Analysis

評估範圍 ...
"""


def test_pending_ticket_with_phase4_string_not_identified_as_completion():
    """pending ticket 含「Phase 4」字串（文本引用）不應被識別為 phase 完成報告"""
    file_path = "docs/work-logs/v0.18.0/tickets/0.18.0-W11-099.md"
    is_completion, _ = module.is_phase_completion_report(
        file_path, _PENDING_TICKET_CONTENT, _logger()
    )
    assert is_completion is False, "pending ticket 內文引用 Phase 4 不應被識別為完成報告"


def test_inprogress_ticket_real_phase4_section_still_identified():
    """in_progress ticket 真正寫 ## Phase 4 章節仍應被識別為 phase 完成報告"""
    file_path = "docs/work-logs/v0.18.0/tickets/0.18.0-W11-100.md"
    is_completion, phase_type = module.is_phase_completion_report(
        file_path, _INPROGRESS_TICKET_PHASE4_EMPTY_SOLUTION, _logger()
    )
    assert is_completion is True, "真實的 ## Phase 4 章節應被識別"
    assert phase_type is not None


def test_standalone_phase_report_still_identified():
    """獨立 phase 完成報告檔（非 ticket md）行為維持不變（向後相容）"""
    file_path = "docs/work-logs/v0.18.0/phase4-evaluation.md"
    is_completion, phase_type = module.is_phase_completion_report(
        file_path, _STANDALONE_PHASE_REPORT_CONTENT, _logger()
    )
    assert is_completion is True, "獨立 phase 報告檔應維持觸發"
    assert phase_type is not None


def test_pending_ticket_phase4_string_in_strategy_text_no_warning():
    """ticket strategy 含「Phase 4 評估」純引用文字不應觸發完成識別"""
    file_path = "docs/work-logs/v0.18.0/tickets/0.18.0-W11-099.md"
    content = """---
id: 0.18.0-W11-099
status: pending
---

## Problem Analysis

修復策略對齊 Phase 4 評估流程；案例 2 提到 Phase 4 結論「無需重構」。
"""
    is_completion, _ = module.is_phase_completion_report(
        file_path, content, _logger()
    )
    assert is_completion is False
