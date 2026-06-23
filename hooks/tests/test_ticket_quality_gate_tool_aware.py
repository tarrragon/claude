"""
Ticket Quality Gate Hook - tool-aware 輸入驗證測試

對應 Ticket 1.0.0-W1-074：
- 修正 validate_input 無條件套用 Write schema（file_path + content）的缺陷：
  Edit（old_string/new_string）、MultiEdit（edits）、Read 等輸入被誤判為
  「缺少必要欄位: content」並產生 ERROR 噪音
- validate_input 改依 tool_name 分流套用各工具專屬 schema
- Edit/MultiEdit 場景的全文內容改由 resolve_ticket_content 讀磁碟取得
  （PostToolUse 時檔案已寫入）
- 錯誤日誌必須含 tool_name（原 ERROR 無法歸因工具）

重現基準：W1-071/W1-075/W1-076 三 session 觀測之
「輸入驗證通過(DEBUG) → ERROR tool_input 缺少必要欄位: content」序列，
實際觸發源為 test_effort_awareness.py 的 tool_name=Read 合成輸入。
"""

import logging
import sys
import importlib.util
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
# W10-092: 部分 ticket-skill hook 已遷至 .claude/skills/ticket/hooks/
ticket_skill_hooks_path = _hooks_dir.parent / "skills" / "ticket" / "hooks"
_lib_dir = _hooks_dir.parent
for p in (str(_hooks_dir), str(_lib_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_hook_module():
    hook_path = ticket_skill_hooks_path / "ticket-quality-gate-hook.py"
    spec = importlib.util.spec_from_file_location(
        "ticket_quality_gate_hook_tool_aware", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_hook_module()


@pytest.fixture
def reset_config_cache(hook_module):
    import config_loader
    config_loader.clear_config_cache()
    hook_module._quality_config = None
    yield
    config_loader.clear_config_cache()
    hook_module._quality_config = None


@pytest.fixture
def logger():
    return logging.getLogger("test-ticket-quality-gate-tool-aware")


def _imp_ticket_content() -> str:
    """產出含 frontmatter type=IMP 與 ticket structure marker 的內容。"""
    return """---
id: 1.0.0-W1-999
title: test
type: IMP
status: in_progress
---

## 實作步驟
- step

## 驗收條件
Layer 1 something

## 參考文件
"""


# ----------------------------------------------------------------------------
# 案例 1：Edit 輸入不再以 Write schema 驗證（acceptance 1）
# ----------------------------------------------------------------------------

def test_edit_input_not_validated_with_write_schema(hook_module, logger):
    """Edit tool_input 無 content 欄位屬正常形狀，不應被 Write schema 拒絕。"""
    input_data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "docs/work-logs/v1.0.0/tickets/x.md",
            "old_string": "a",
            "new_string": "b",
        },
    }
    assert hook_module.validate_input(input_data, logger) is True


def test_multiedit_input_validated_with_own_schema(hook_module, logger):
    """MultiEdit tool_input 形狀為 file_path + edits，同樣不適用 Write schema。"""
    input_data = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "docs/work-logs/v1.0.0/tickets/x.md",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    }
    assert hook_module.validate_input(input_data, logger) is True


def test_edit_input_missing_own_fields_fails_with_tool_name_in_log(
    hook_module, logger, caplog
):
    """Edit 缺自身必要欄位仍應驗證失敗，且錯誤日誌可歸因 tool_name。"""
    input_data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "docs/work-logs/v1.0.0/tickets/x.md",
            "old_string": "a",
            # 缺 new_string
        },
    }
    with caplog.at_level(logging.ERROR):
        assert hook_module.validate_input(input_data, logger) is False
    assert any("Edit" in record.getMessage() for record in caplog.records)


# ----------------------------------------------------------------------------
# 案例 2：Write 工具驗證行為不變（acceptance 2）
# ----------------------------------------------------------------------------

def test_write_input_valid_passes(hook_module, logger):
    """合法 Write 輸入（file_path + content）驗證通過（向後相容）。"""
    input_data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "docs/work-logs/v1.0.0/tickets/x.md",
            "content": "# x",
        },
    }
    assert hook_module.validate_input(input_data, logger) is True


def test_write_input_missing_content_still_fails(hook_module, logger):
    """Write 缺 content 仍應驗證失敗（Write schema 行為不變）。"""
    input_data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "docs/work-logs/v1.0.0/tickets/x.md",
        },
    }
    assert hook_module.validate_input(input_data, logger) is False


# ----------------------------------------------------------------------------
# 案例 3：非處理範圍工具（Read）靜默分流，不產生 ERROR 噪音
# 重現基準：test_effort_awareness.py 合成輸入
# {"tool_name": "Read", "tool_input": {"file_path": "x.py"}}
# ----------------------------------------------------------------------------

def test_read_input_passes_validation_without_error(
    hook_module, logger, caplog
):
    """Read 輸入不套用任何 schema，驗證放行且無 ERROR 記錄。"""
    input_data = {
        "tool_name": "Read",
        "tool_input": {"file_path": "x.py"},
    }
    with caplog.at_level(logging.DEBUG):
        assert hook_module.validate_input(input_data, logger) is True
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_read_input_skipped_by_trigger_check(
    hook_module, reset_config_cache, logger
):
    """Read 不在 allowed_tools，由觸發條件檢查靜默跳過。"""
    input_data = {
        "tool_name": "Read",
        "tool_input": {"file_path": "x.py"},
    }
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# 案例 4：Edit 場景的內容取得（PostToolUse 讀磁碟）
# ----------------------------------------------------------------------------

def test_edit_trigger_reads_content_from_disk(
    hook_module, reset_config_cache, logger, tmp_path
):
    """Edit 輸入無全文，PostToolUse 時檔案已落盤，應讀磁碟判斷觸發條件。"""
    ticket_dir = tmp_path / "tickets"
    ticket_dir.mkdir()
    ticket_file = ticket_dir / "1.0.0-W1-999.md"
    ticket_file.write_text(_imp_ticket_content(), encoding="utf-8")

    input_data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(ticket_file),
            "old_string": "a",
            "new_string": "b",
        },
    }
    assert hook_module.should_trigger_check(input_data, logger) is True


def test_edit_missing_file_skips_gracefully(
    hook_module, reset_config_cache, logger, tmp_path
):
    """Edit 指向不存在的檔案時應靜默跳過檢測，不拋例外。"""
    input_data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / "tickets" / "not-exist.md"),
            "old_string": "a",
            "new_string": "b",
        },
    }
    assert hook_module.should_trigger_check(input_data, logger) is False


def test_resolve_ticket_content_write_uses_payload(hook_module, logger):
    """Write 場景直接取 tool_input.content，不讀磁碟。"""
    content = hook_module.resolve_ticket_content(
        "Write", {"file_path": "/no/such/file.md", "content": "# inline"}, logger
    )
    assert content == "# inline"
