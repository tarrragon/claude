"""
Ticket Quality Gate Hook - 路徑黑名單與 keyword 縮緊測試

對應 Ticket 0.18.0-W10-100：
- 修復 ticket-quality-gate-hook 路徑黑名單與 keyword 強化
- 父 ANA: 0.18.0-W10-072.4 重現實驗確認 substring `-ticket-` 過寬會誤命中
  `.claude/error-patterns/` 下含「ticket」字眼的 PC 檔（如 current-ticket-id）

測試覆蓋：
1. 黑名單路徑（.claude/error-patterns/...current-ticket-id...md）→ 不觸發
2. 黑名單路徑（.claude/methodologies/...ticket...md）→ 不觸發
3. 真實 ticket md（docs/work-logs/.../tickets/X.md）→ 觸發
4. 縮緊後的 keyword：純 `-ticket-` substring 不再觸發
5. `/tickets/` 父目錄錨點路徑 → 觸發
"""

import sys
import importlib.util
from pathlib import Path

import pytest

# 將 .claude/hooks 與 .claude/lib 加入 sys.path
_hooks_dir = Path(__file__).parent.parent
# W10-092: 部分 ticket-skill hook 已遷至 .claude/skills/ticket/hooks/
ticket_skill_hooks_path = _hooks_dir.parent / "skills" / "ticket" / "hooks"
_lib_dir = _hooks_dir.parent
for p in (str(_hooks_dir), str(_lib_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_hook_module():
    """動態載入 ticket-quality-gate-hook.py（檔名含連字號，無法直接 import）"""
    hook_path = ticket_skill_hooks_path / "ticket-quality-gate-hook.py"
    spec = importlib.util.spec_from_file_location("ticket_quality_gate_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_hook_module()


@pytest.fixture
def reset_config_cache(hook_module):
    """確保配置從檔案載入（清除快取）"""
    import config_loader
    config_loader.clear_config_cache()
    hook_module._quality_config = None
    yield
    config_loader.clear_config_cache()
    hook_module._quality_config = None


@pytest.fixture
def logger():
    import logging
    return logging.getLogger("test-ticket-quality-gate")


# 含 Layer 標記的內容（會通過結構檢查）
TICKET_LIKE_CONTENT = """# Test

## 實作步驟
- step

## 驗收條件
Layer 1 something

## 參考文件
"""


def _make_input(file_path: str, content: str = TICKET_LIKE_CONTENT) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": file_path,
            "content": content,
        },
    }


# ----------------------------------------------------------------------------
# 案例 1：黑名單命中 — error-patterns 下含 -ticket- substring 的 PC 檔
# ----------------------------------------------------------------------------

def test_blacklist_error_patterns_with_ticket_substring(
    hook_module, reset_config_cache, logger
):
    """`.claude/error-patterns/process-compliance/PC-098-...current-ticket-id.md`
    雖含 `-ticket-` substring 與 Layer 標記，但命中黑名單應不觸發。"""
    input_data = _make_input(
        ".claude/error-patterns/process-compliance/"
        "PC-098-pm-rule-content-contains-current-ticket-id.md"
    )
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# 案例 2：黑名單命中 — methodologies 下含 ticket 字眼的 md
# ----------------------------------------------------------------------------

def test_blacklist_methodologies_directory(
    hook_module, reset_config_cache, logger
):
    input_data = _make_input(
        ".claude/methodologies/atomic-ticket-methodology.md"
    )
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# 案例 3：真實 ticket md 仍應觸發
# ----------------------------------------------------------------------------

def test_real_ticket_path_triggers(
    hook_module, reset_config_cache, logger
):
    """docs/work-logs/v0.18.0/tickets/0.18.0-W10-100.md 屬真實 ticket，應觸發。"""
    input_data = _make_input(
        "docs/work-logs/v0.18.0/tickets/0.18.0-W10-100.md"
    )
    assert hook_module.should_trigger_check(input_data, logger) is True


# ----------------------------------------------------------------------------
# 案例 4：縮緊後 keyword — 純 `-ticket-` substring 不再觸發
# ----------------------------------------------------------------------------

def test_loose_ticket_substring_no_longer_triggers(
    hook_module, reset_config_cache, logger
):
    """專案根目錄下任意 `something-ticket-foo.md` 不在 docs/work-logs/、
    docs/tickets/、/tickets/ 之下，縮緊後不應觸發（避免 PC-098 類誤判）。"""
    input_data = _make_input("notes/random-ticket-draft.md")
    assert hook_module.should_trigger_check(input_data, logger) is False


# ----------------------------------------------------------------------------
# 案例 5：`/tickets/` 父目錄錨點路徑觸發
# ----------------------------------------------------------------------------

def test_tickets_parent_dir_anchor_triggers(
    hook_module, reset_config_cache, logger
):
    """任意專案下 `path/tickets/<id>.md` 屬合法 ticket 位置，應觸發。"""
    input_data = _make_input("some/project/tickets/X-001.md")
    assert hook_module.should_trigger_check(input_data, logger) is True
