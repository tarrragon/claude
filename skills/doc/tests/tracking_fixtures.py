"""測試用 tracking 資料生成 helper，統一引用 tracking_schema SSOT。

背景：手寫 fixture（dict-keyed proposals）與真實 docs/proposals-tracking.yaml
的 list-based 結構不一致，會遮蔽消費端程式碼對 list 格式的處理是否正確
（IMP-APP-002 同族）。本模組提供 `make_test_tracking`，生成的資料結構固定
為 list-based，欄位名不手寫猜測，供各測試檔統一引用。
"""

from __future__ import annotations

from doc_system.core.tracking_schema import PROPOSALS_TRACKING_SCHEMA


def make_test_tracking(prop_id: str, status: str, overrides: dict | None = None) -> dict:
    """生成單筆 proposal 的 list-based tracking 資料。

    回傳 `{"proposals": [entry]}`，entry 至少含 SSOT 定義的必要欄位
    （見 `PROPOSALS_TRACKING_SCHEMA["proposal_entry_required"]`）。
    `overrides` 可補上選填欄位（如 target_version、confirmed_at）。
    """
    entry = {"id": prop_id, "title": "Test Proposal", "status": status}
    entry.update(overrides or {})

    required = PROPOSALS_TRACKING_SCHEMA["proposal_entry_required"]
    missing = required - set(entry.keys())
    assert not missing, f"make_test_tracking 產生的 entry 缺少必要欄位：{missing}"

    return {"proposals": [entry]}


def find_entry(entries: list, prop_id: str) -> dict | None:
    """在 list-based proposals 中找出對應 prop_id 的 entry（測試斷言輔助）。"""
    return next((item for item in entries if item.get("id") == prop_id), None)
