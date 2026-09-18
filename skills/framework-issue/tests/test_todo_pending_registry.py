"""todo_pending_registry.py 測試：schema 讀寫、ack-based 同步語意
（正向對照：應印而印 / 不該印而沒印）、狀態遺失退化行為。

registry_path() 皆以 project_root 引數顯式指定 tmp_path，避免真實 git
subprocess 呼叫或觸碰開發者本機的 .claude/state/。
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import todo_pending_registry as registry  # noqa: E402


# --- registry_path：路徑組成 ---


def test_registry_path_appends_relative_parts_to_project_root(tmp_path):
    path = registry.registry_path(tmp_path)
    assert path == tmp_path / ".claude" / "state" / "framework-issue-todo-pending.json"


# --- normalize_source_ticket：反引號包法正規化 ---


def test_normalize_source_ticket_strips_backticks_and_whitespace():
    assert registry.normalize_source_ticket("`0.1.0-W3-329`") == "0.1.0-W3-329"
    assert registry.normalize_source_ticket("  0.1.0-W3-329  ") == "0.1.0-W3-329"
    assert registry.normalize_source_ticket("0.1.0-W3-329") == "0.1.0-W3-329"


# --- load_pending / pending_entries：退化語意（None＝無法判定，[]＝已確認無） ---


def test_load_pending_returns_none_when_file_missing(tmp_path):
    assert registry.load_pending(tmp_path) is None


def test_load_pending_returns_none_on_corrupt_json(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert registry.load_pending(tmp_path) is None


def test_load_pending_returns_none_on_schema_version_mismatch(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 999, "pending": []}), encoding="utf-8")
    assert registry.load_pending(tmp_path) is None


def test_pending_entries_returns_none_when_registry_missing(tmp_path):
    """狀態遺失（缺檔）—— 呼叫端（hook）應據此走全列沉默退化路徑。"""
    assert registry.pending_entries(tmp_path) is None


def test_pending_entries_returns_empty_list_when_registry_has_no_pending(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": registry.SCHEMA_VERSION, "pending": []}),
        encoding="utf-8",
    )
    assert registry.pending_entries(tmp_path) == []


# --- sync_section_rows：新增列會印（正向對照：應印而印） ---


def _row(來源票="0.1.0-W3-329", 狀態="待裁票", 做什麼="做點什麼", 優先級="P1", 階段="可立即執行"):
    return {
        "來源票": 來源票,
        "做什麼": 做什麼,
        "acceptance 條數": "3",
        "優先級": 優先級,
        "階段": 階段,
        "狀態": 狀態,
    }


def test_sync_section_rows_adds_new_pending_row(tmp_path):
    added, removed = registry.sync_section_rows(
        33, "graph-project-docs-manager-66", [_row()], "2026-09-12T00:00:00+00:00", tmp_path
    )
    assert (added, removed) == (1, 0)
    entries = registry.pending_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["issue"] == 33
    assert entries[0]["owner"] == "graph-project-docs-manager-66"
    assert entries[0]["source_ticket"] == "0.1.0-W3-329"


def test_sync_section_rows_normalizes_backtick_source_ticket(tmp_path):
    registry.sync_section_rows(
        33, "owner-1", [_row(來源票="`0.1.0-W3-329`")], "t1", tmp_path
    )
    entries = registry.pending_entries(tmp_path)
    assert entries[0]["source_ticket"] == "0.1.0-W3-329"


# --- sync_section_rows：ack 後不再印（正向對照：不該印而沒印） ---


def test_sync_section_rows_removes_entry_when_status_no_longer_pending(tmp_path):
    """ack-based：狀態從「待裁票」改為「已裁票」視為已處理，應從 pending
    移除——這是本機制的 ack 訊號來源（不是被 SessionStart 印過就消失，
    見模組 docstring 對 seen-based 的排斥）。"""
    registry.sync_section_rows(33, "owner-1", [_row()], "t1", tmp_path)
    assert len(registry.pending_entries(tmp_path)) == 1

    added, removed = registry.sync_section_rows(
        33, "owner-1", [_row(狀態="已裁票")], "t2", tmp_path
    )
    assert (added, removed) == (0, 1)
    assert registry.pending_entries(tmp_path) == []


def test_sync_section_rows_removes_entry_when_row_disappears(tmp_path):
    """整列從表格消失（非狀態改變）同樣視為已處理並移除。"""
    registry.sync_section_rows(33, "owner-1", [_row()], "t1", tmp_path)
    added, removed = registry.sync_section_rows(33, "owner-1", [], "t2", tmp_path)
    assert (added, removed) == (0, 1)
    assert registry.pending_entries(tmp_path) == []


def test_sync_section_rows_leaves_unchanged_pending_row_untouched(tmp_path):
    """同一列狀態仍為「待裁票」時，重複同步不應計為新增（避免虛報 delta）。"""
    registry.sync_section_rows(33, "owner-1", [_row()], "t1", tmp_path)
    added, removed = registry.sync_section_rows(33, "owner-1", [_row()], "t2", tmp_path)
    assert (added, removed) == (0, 0)


def test_sync_section_rows_scopes_by_issue_and_owner(tmp_path):
    """不同 (issue, owner) 範圍互不影響：對範圍 A 的同步不應清掉範圍 B
    的既有 pending 項目。"""
    registry.sync_section_rows(33, "owner-a", [_row(來源票="ticket-a")], "t1", tmp_path)
    registry.sync_section_rows(34, "owner-b", [_row(來源票="ticket-b")], "t1", tmp_path)

    registry.sync_section_rows(33, "owner-a", [], "t2", tmp_path)

    entries = registry.pending_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["issue"] == 34
    assert entries[0]["source_ticket"] == "ticket-b"


def test_sync_section_rows_swallows_oserror_without_raising(tmp_path, monkeypatch):
    """best-effort 快取：寫入失敗不應向呼叫端拋例外（同 owned_issues_registry
    取向）。"""
    def _raise_mkdir(*args, **kwargs):
        raise OSError("模擬磁碟寫入失敗")

    monkeypatch.setattr(Path, "mkdir", _raise_mkdir)
    added, removed = registry.sync_section_rows(
        33, "owner-1", [_row()], "t1", tmp_path
    )
    assert (added, removed) == (0, 0)
