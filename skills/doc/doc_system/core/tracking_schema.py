"""Doc skill tracking 檔案 schema 單一真相源（SSOT）。

per-file 定義：不同 tracking 檔（proposals-tracking.yaml / traceability.yaml）
schema 互不相同，各自獨立定義，消費端一律引用本模組常數，禁止 inline 猜測欄位名。

背景：IMP-APP-002 同族 bug（欄位假設無真實資料驗證）已發生多起
（confirmed_at、last_updated 等欄位命名假設歷次偏離真實 schema）。
詳見歷次欄位/schema 對齊修復 ANA。
"""

from __future__ import annotations

# docs/proposals-tracking.yaml 的權威 schema。
# 頂層結構：{proposals: [...], usecases: [...], specs: [...]}
# proposals 為 list-based（非 dict-keyed-by-id）。
PROPOSALS_TRACKING_SCHEMA = {
    "top_level_keys": {"proposals", "usecases", "specs"},
    "proposals_format": "list",
    "proposal_entry_required": {"id", "title", "status"},
    "proposal_entry_optional": {
        "priority",
        "confirmed_at",
        "completed_note",
        "target_version",
        "proposed",
        "source",
        "spec_refs",
        "usecase_refs",
        "ticket_refs",
        "checklist",
        "canonical_ssot",
        "tracking_ticket",
        # list of str（提案 id）：本提案依賴的前置提案，供
        # version-bootstrap/scripts/check_proposal_dependencies.py 檢查跨提案
        # 排序矛盾（W1-017：補齊宣告，格式由消費端用法與既有測試 fixture
        # 雙重佐證確認，非獨立文件宣告）。
        "depends_on",
    },
    # 確認日期欄位名為 confirmed_at，非 confirmed（欄位名須對齊真實 schema）。
    "confirm_date_field": "confirmed_at",
}

# docs/traceability.yaml 的權威 schema（按需由 batch_init 建立）。
# 與 PROPOSALS_TRACKING_SCHEMA 完全獨立，last_updated 是本檔合法自洽欄位
# （per-file schema 獨立，勿跨檔套用頂層鍵假設）。
TRACEABILITY_SCHEMA = {
    "top_level_keys": {"version", "mappings", "last_updated"},
    "mappings_format": "list",
    "mapping_entry_required": {"spec", "usecase", "title"},
    "mapping_entry_optional": {"scenarios", "tests"},
}
