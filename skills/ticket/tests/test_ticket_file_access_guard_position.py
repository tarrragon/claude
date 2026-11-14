"""
ticket-file-access-guard-hook 依 old_string 位置判定 frontmatter 編輯（3.3.0-W1-098.6.2）。

原判定只看 old_string 去空白後的第一行欄位名，且只認 20 個欄位；
3.3.0-W1-098.6 實測 7 種開頭可直接改 frontmatter。改為讀目標檔、定位 old_string，
與 frontmatter 區段重疊即阻擋。

E2 正向對照：098.6 實測的 7 種放行開頭全數斷言為 deny。
對照：body 章節內的編輯（含字面像 frontmatter 欄位的行）斷言為 allow。
保守側：讀檔失敗／無 frontmatter／找不到 old_string 時退回字面判定。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "ticket-file-access-guard-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "ticket_file_access_guard_position", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TICKET_RELPATH = "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-549.md"

TICKET_CONTENT = """---
id: 0.2.1-W3-549
title: 範例
type: IMP
status: in_progress
version: 0.2.1
wave: 3
priority: P2
relatedTo: []
who:
  current: rosemary-project-manager
  history: {}
where:
  layer: hooks
  files:
  - CLAUDE.md::read
acceptance:
- '[ ] Solution 含修法與 spawn 規劃'
tdd_phase: phase1
---

# Execution Log

## Solution

status: 這一行在 body 內，只是字面像欄位
wave: 1 也是 body 內文

---

## Test Results

尚未執行
"""

# 3.3.0-W1-098.6 實測放行的 7 種 old_string 開頭（rc=0），修正後應全數 deny
SEVEN_BYPASS_OLD_STRINGS = [
    "relatedTo: []",
    "tdd_phase: phase1",
    "acceptance:\n- '[ ] Solution 含修法與 spawn 規劃'",
    "---\nid: 0.2.1-W3-549",
    "wave: 3\npriority: P2",
    "  current: rosemary-project-manager",
    "- '[ ] Solution 含修法與 spawn 規劃'",
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    module = _load_hook_module()
    path = tmp_path / TICKET_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TICKET_CONTENT, encoding="utf-8")
    monkeypatch.setattr(module, "get_project_root", lambda: tmp_path)
    logger = module.setup_hook_logging("test")
    return module, tmp_path, logger


class TestSevenBypassFormsDenied:
    """E2 正向對照：098.6 的 7 種放行開頭改為 deny。"""

    @pytest.mark.parametrize("old_string", SEVEN_BYPASS_OLD_STRINGS)
    def test_relative_path_denied(self, env, old_string):
        module, _root, logger = env
        is_allowed, reason = module.check_edit_permission(TICKET_RELPATH, old_string, logger)
        assert is_allowed is False
        assert "禁止直接編輯 ticket frontmatter 欄位" in reason

    @pytest.mark.parametrize("old_string", SEVEN_BYPASS_OLD_STRINGS)
    def test_absolute_path_denied(self, env, old_string):
        module, root, logger = env
        abs_path = str(root / TICKET_RELPATH)
        is_allowed, _ = module.check_edit_permission(abs_path, old_string, logger)
        assert is_allowed is False

    def test_where_suffix_line_denied_and_reason_points_to_set_where(self, env):
        module, _root, logger = env
        is_allowed, reason = module.check_edit_permission(
            TICKET_RELPATH, "  - CLAUDE.md::read", logger
        )
        assert is_allowed is False
        assert "set-where" in reason


class TestBodyEditsAllowed:
    """對照：body 章節內的編輯放行，含字面像 frontmatter 欄位的行。"""

    @pytest.mark.parametrize(
        "old_string",
        [
            "## Solution\n\nstatus: 這一行在 body 內",
            "status: 這一行在 body 內，只是字面像欄位",
            "wave: 1 也是 body 內文",
            "尚未執行",
        ],
    )
    def test_body_edit_allowed(self, env, old_string):
        module, _root, logger = env
        is_allowed, _ = module.check_edit_permission(TICKET_RELPATH, old_string, logger)
        assert is_allowed is True

    def test_old_string_in_both_regions_denied(self, env):
        """同一字串同時出現在 frontmatter 與 body：任一出現位置觸及 frontmatter 即 deny。"""
        module, _root, logger = env
        is_allowed, _ = module.check_edit_permission(TICKET_RELPATH, "status: ", logger)
        assert is_allowed is False


class TestFallbackToLiteralCheck:
    """無法定位時退回字面判定（保守側：字面命中保護欄位仍 deny）。"""

    def test_missing_file_falls_back_and_denies_protected_field(self, env):
        module, _root, logger = env
        missing = "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-999.md"
        assert module.old_string_overlaps_frontmatter(missing, "status: x", logger) is None
        is_allowed, _ = module.check_edit_permission(missing, "status: x", logger)
        assert is_allowed is False

    def test_old_string_not_found_falls_back(self, env):
        module, _root, logger = env
        assert (
            module.old_string_overlaps_frontmatter(TICKET_RELPATH, "priority: P0", logger)
            is None
        )
        is_allowed, _ = module.check_edit_permission(TICKET_RELPATH, "priority: P0", logger)
        assert is_allowed is False

    def test_no_frontmatter_falls_back(self, env):
        module, root, logger = env
        path = root / TICKET_RELPATH
        path.write_text("沒有 frontmatter\nstatus: x\n", encoding="utf-8")
        assert module.old_string_overlaps_frontmatter(TICKET_RELPATH, "status: x", logger) is None

    def test_unclosed_frontmatter_falls_back(self, env):
        module, _root, _logger = env
        assert module.frontmatter_end_offset("---\nid: x\n") is None


class TestWriteReasonPaths:
    def test_write_reason_lists_two_edit_paths(self, env):
        module, _root, logger = env
        is_allowed, reason = module.check_write_permission(TICKET_RELPATH, logger)
        assert is_allowed is False
        assert "以 Edit 修改 body 章節" in reason
        assert "append-log" in reason and "--replace" in reason
