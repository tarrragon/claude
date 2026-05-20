"""pytest fixtures for ticket_system tests.

W11-015 (TD-F): 為 track_snapshot 測試提供 autouse fixture，避免真實掃描
`docs/work-logs/` 全目錄。背景：

- `track_snapshot._render_full_snapshot` / `_render_degraded_snapshot` 兩條路徑
  均無條件呼叫 `_scan_all_versions()`，掃描 169+ 版本目錄
- `_print_version_progress` / `_print_in_progress_tasks` / `_print_pending_summary`
  對每個版本呼叫 `list_tickets(version)`，每次重新 parse ticket md frontmatter
- baseline 量測：17 tests × ~46s/test = 779s 真實 I/O

Fixture 設計（最小 mock 原則）：

- mock `track_snapshot._scan_all_versions` → 回傳極小假版本清單（單一 version）
- mock `track_snapshot.list_tickets` → 回傳空清單（測試多數不關心版本進度內容）
- autouse=True：所有 ticket_system/tests 自動套用
- 個別測試若需要特定 ticket 內容，可在測試內 monkeypatch 覆寫

不 mock 範圍：
- checkpoint_state（既有 `_patch_checkpoint_state` helper 已處理）
- subprocess git branch（S8 測試需要原始 subprocess 行為）
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mock_track_snapshot_filesystem_scan(monkeypatch):
    """Autouse fixture: 屏蔽 track_snapshot 對 docs/work-logs/ 真實掃描。

    W11-015：避免 _scan_all_versions + list_tickets 真實 I/O 拖慢測試。
    回傳穩定假版本清單 + 空 ticket 集合，覆蓋 _render_full_snapshot 與
    _render_degraded_snapshot 兩條路徑。
    """
    try:
        from ticket_system.commands import track_snapshot as mod
    except ImportError:
        # track_snapshot 模組不存在時跳過（不影響其他測試）
        return

    fake_versions = ["0.0.0-fixture"]

    def _fake_scan_all_versions():
        return list(fake_versions)

    def _fake_list_tickets(version):
        return []

    monkeypatch.setattr(mod, "_scan_all_versions", _fake_scan_all_versions, raising=False)
    monkeypatch.setattr(mod, "list_tickets", _fake_list_tickets, raising=False)
