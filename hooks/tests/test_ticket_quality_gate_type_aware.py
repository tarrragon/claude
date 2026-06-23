"""
Ticket Quality Gate Hook - type-aware 觸發測試

對應 Ticket 0.18.0-W10-123：
- 重構 should_trigger_check 加入 ticket type 過濾
- ANA / DOC type 跳過 c2/c3 檢查（避免 Flutter 風格 test/*.dart + Layer 標示
  對分析 / 文件類 ticket 的 false positive）
- IMP type 保留現有觸發行為

W10-118 ANA Case B 驗證：W10-113 ANA ticket 被套用 Flutter Bloc 風格章節要求
被誤判為 incomplete。
"""

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
        "ticket_quality_gate_hook", hook_path
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
    import logging
    return logging.getLogger("test-ticket-quality-gate-type-aware")


def _make_ticket_content(ticket_type: str) -> str:
    """產出含 frontmatter type 標示與 ticket structure marker 的內容。"""
    return f"""---
id: 0.18.0-W10-999
title: test
type: {ticket_type}
status: in_progress
---

## 實作步驟
- step

## 驗收條件
Layer 1 something

## 參考文件
"""


def _make_input(ticket_type: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "docs/work-logs/v0.18.0/tickets/0.18.0-W10-999.md",
            "content": _make_ticket_content(ticket_type),
        },
    }


# ----------------------------------------------------------------------------
# W10-123 案例 1：type=ANA 應跳過 c2/c3 檢查
# ----------------------------------------------------------------------------

def test_ana_type_skips_quality_gate(
    hook_module, reset_config_cache, logger
):
    """ANA ticket 屬分析類，不適用 Flutter 風格 test path 與 Layer 標示要求。"""
    input_data = _make_input("ANA")
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# W10-123 案例 2：type=DOC 應跳過 c2/c3 檢查
# ----------------------------------------------------------------------------

def test_doc_type_skips_quality_gate(
    hook_module, reset_config_cache, logger
):
    """DOC ticket 屬文件類，不適用實作品質檢查。"""
    input_data = _make_input("DOC")
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# W10-123 案例 3：type=IMP 應觸發 c2/c3 檢查（向後相容）
# ----------------------------------------------------------------------------

def test_imp_type_triggers_quality_gate(
    hook_module, reset_config_cache, logger
):
    """IMP ticket 屬實作類，保留現有 c2/c3 行為（向後相容）。"""
    input_data = _make_input("IMP")
    assert hook_module.should_trigger_check(input_data, logger) is True


# ----------------------------------------------------------------------------
# W10-123 案例 4：缺 type frontmatter 應 fallback 為觸發（向後相容）
# ----------------------------------------------------------------------------

def test_missing_type_falls_back_to_trigger(
    hook_module, reset_config_cache, logger
):
    """無 type frontmatter 的 ticket → fallback 為觸發（不破壞既有觸發路徑）。"""
    content = """# Test

## 實作步驟
- step

## 驗收條件
Layer 1 something

## 參考文件
"""
    input_data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "docs/work-logs/v0.18.0/tickets/0.18.0-W10-999.md",
            "content": content,
        },
    }
    assert hook_module.should_trigger_check(input_data, logger) is True
