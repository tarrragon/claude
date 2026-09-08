"""Tests for dashboard [Handoff Target] vs resume --list 計數分岔修復
（0.2.1-W3-1312 item 1）。

Bug：dashboard.load_handoff_targets 只讀 handoff record 頂層 `target_ticket_id`
欄位；resume --list 走 `handoff_utils.resolve_target()`（優先讀頂層欄位，
無則從 `direction` 後綴 fallback 解析）。當一筆 pending handoff 只有
`direction="to-sibling:<target>"` 而無頂層 `target_ticket_id`（互動式
to-sibling/to-child/to-parent handoff 的既有產出格式，見
`_create_handoff_file_internal`），dashboard 判定 0 筆 target，
resume --list 判定 1 筆 target，兩者對同一批 pending handoff 分岔。

修復：dashboard 改用 `resolve_target()` 統一解析，兩者計數一致。
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from ticket_system.commands import track_dashboard


def _mk(tid: str, status: str = "pending") -> Dict[str, Any]:
    return {
        "id": tid,
        "title": f"title-{tid}",
        "status": status,
        "blockedBy": [],
        "children": [],
        "priority": "P2",
        "wave": 10,
        "version": "0.18.0",
        "started_at": None,
        "who": {},
        "trigger_bound": False,
        "_body": "",
    }


def _ns(**kwargs) -> argparse.Namespace:
    defaults = dict(
        top=track_dashboard.DEFAULT_TOP,
        wave=None,
        no_stale=True,
        stale_threshold=track_dashboard.DEFAULT_STALE_THRESHOLD_MIN,
        format=track_dashboard.FORMAT_TEXT,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _patch_loader(monkeypatch, tickets: List[Dict], handoff_info: Optional[Dict] = None):
    monkeypatch.setattr(track_dashboard, "list_tickets", lambda v: tickets)
    monkeypatch.setattr(
        track_dashboard, "_get_pending_handoff_info", lambda: (handoff_info or {})
    )
    monkeypatch.setattr(
        track_dashboard.lease, "load_registry_snapshot", lambda: ({}, None)
    )


def test_direction_suffix_only_target_counted_via_resolve_target(monkeypatch, capsys):
    """target 僅編碼於 direction 後綴（無頂層 target_ticket_id）時，
    dashboard 仍須經 resolve_target() 解析出 target，與 resume --list 同計數。

    這是 `_get_pending_handoff_info()` 真實回傳的資料形態之一——互動式
    handoff（`_create_handoff_file_internal`）從不寫入頂層 target_ticket_id
    欄位，僅有 direction 後綴；本測試不使用 `_mk_handoff_info` 那種已含
    target_ticket_id 欄位的合成資料，避免掩蓋此分岔。
    """
    tickets = [_mk("0.18.0-W10-950", status="pending")]
    handoff_info = {
        # `_get_pending_handoff_info()` 第一輪一律以 source ticket_id 為 key；
        # 此筆記錄無頂層 target_ticket_id，故不會有第二輪的 target-key 項目。
        "0.18.0-W10-949": {
            "ticket_id": "0.18.0-W10-949",
            "direction": "to-sibling:0.18.0-W10-950",
            "timestamp": "2026-09-08T00:00:00",
            "from_status": "completed",
        },
    }
    _patch_loader(monkeypatch, tickets, handoff_info)

    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    handoff_section = out.split("[Handoff Target]")[1].split("[Ready")[0]

    assert "[Handoff Target] 1 ticket(s)" in out
    assert "0.18.0-W10-950" in handoff_section


def test_json_count_matches_resolve_target(monkeypatch, capsys):
    """JSON 輸出的 handoff_targets 筆數同樣須反映 resolve_target 解析結果。"""
    tickets = [_mk("0.18.0-W10-952", status="pending")]
    handoff_info = {
        "0.18.0-W10-951": {
            "ticket_id": "0.18.0-W10-951",
            "direction": "to-child:0.18.0-W10-952",
            "timestamp": "2026-09-08T00:00:00",
            "from_status": "completed",
        },
    }
    _patch_loader(monkeypatch, tickets, handoff_info)

    track_dashboard.dashboard_main(_ns(format="json"), "0.18.0")
    import json as _json
    payload = _json.loads(capsys.readouterr().out)
    assert [item["id"] for item in payload["handoff_targets"]] == ["0.18.0-W10-952"]
