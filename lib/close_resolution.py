"""closed 票 `closed_by`（CLI 旗標 `--resolved-by`）值域的單一驗證函式。

背景（tarrragon/claude#60、#106）：寫入或檢查 `closed_by` 的端點原本各有
一套值域——`ticket track close` 對四種 reason 不驗、`set-closed-by` 只收
Ticket ID（連 `none` 也拒收）、`version-tracking-consistency-guard-hook`
只收 Ticket ID 或 `none`。端點值域不一致時，以 A 端點合法寫入的值會在
B 端點被判為異常，且沒有 CLI 路徑可改正。本模組是三個端點共同呼叫的
值域權威。

值域（依 close_reason 限定）：

| close_reason | closed_by 允許值 |
|--------------|-----------------|
| superseded_by、duplicate | Ticket ID |
| transferred_to_issue | issue 參照 `owner/repo#N` |
| 其餘（含 retrospective 的 unknown、缺 close_reason 的存量票） | `none` 或 Ticket ID |

本模組只判定格式（值域）；Ticket ID 是否指向存在的票屬 I/O 檢查，由
CLI 端點自行執行（hook 只做格式稽核，不載入他票）。

設計約束：僅依賴標準函式庫與同套件的 `ticket_id_pattern`，不 import
ticket_system——hook 以 `uv run --script` 執行，拉入 ticket_system 會連帶
引入其依賴鏈。ticket_system 端以 `claude_lib_loader.load_claude_lib` 載入。
"""

import re
from typing import FrozenSet, Optional

from .ticket_id_pattern import FULL_ANCHORED_RE

NONE_TOKEN = "none"

KIND_TICKET_ID = "ticket_id"
KIND_ISSUE_REF = "issue_ref"
KIND_NONE = "none"
KIND_INVALID = "invalid"

REASON_TRANSFERRED_TO_ISSUE = "transferred_to_issue"

REASONS_REQUIRE_TICKET_ID: FrozenSet[str] = frozenset({"superseded_by", "duplicate"})
REASONS_REQUIRE_ISSUE_REF: FrozenSet[str] = frozenset({REASON_TRANSFERRED_TO_ISSUE})

_DEFAULT_KINDS: FrozenSet[str] = frozenset({KIND_NONE, KIND_TICKET_ID})

# GitHub owner：英數與連字號，首字英數，長度上限 39；repo：英數與 . _ -，
# 長度上限 100；issue 編號為正整數。
ISSUE_REF_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}#[1-9]\d*$"
)

_KIND_LABELS = {
    KIND_TICKET_ID: "Ticket ID",
    KIND_ISSUE_REF: "issue 參照（owner/repo#N）",
    KIND_NONE: f"'{NONE_TOKEN}'",
}


def classify_closed_by(value: Optional[str]) -> str:
    """判定 closed_by 值屬於哪一類（Ticket ID／issue 參照／none／不合法）。

    `none` 不分大小寫（沿用 hook 既有判定，避免存量票因大小寫新增警告）。
    """
    text = (value or "").strip()
    if not text:
        return KIND_INVALID
    if text.lower() == NONE_TOKEN:
        return KIND_NONE
    if FULL_ANCHORED_RE.match(text):
        return KIND_TICKET_ID
    if ISSUE_REF_RE.match(text):
        return KIND_ISSUE_REF
    return KIND_INVALID


def allowed_kinds(close_reason: Optional[str]) -> FrozenSet[str]:
    """回傳某個 close_reason 允許的 closed_by 類別。"""
    reason = (close_reason or "").strip()
    if reason in REASONS_REQUIRE_TICKET_ID:
        return frozenset({KIND_TICKET_ID})
    if reason in REASONS_REQUIRE_ISSUE_REF:
        return frozenset({KIND_ISSUE_REF})
    return _DEFAULT_KINDS


def describe_allowed(close_reason: Optional[str]) -> str:
    """以人讀字串描述某個 close_reason 允許的值域（供錯誤訊息使用）。"""
    order = (KIND_TICKET_ID, KIND_ISSUE_REF, KIND_NONE)
    kinds = allowed_kinds(close_reason)
    return " 或 ".join(_KIND_LABELS[k] for k in order if k in kinds)


def validate_closed_by(close_reason: Optional[str], value: Optional[str]) -> Optional[str]:
    """驗證 closed_by 是否落在 close_reason 允許的值域內。

    Returns:
        不合法時回傳一行錯誤描述（不含前綴，由呼叫端加上 `[Error]` 或
        票號）；合法時回傳 None。
    """
    kind = classify_closed_by(value)
    if kind in allowed_kinds(close_reason):
        return None
    reason_label = close_reason or "（未記錄 close_reason）"
    return (
        f"close_reason={reason_label} 的 closed_by 須為 "
        f"{describe_allowed(close_reason)}，收到：{value!r}"
    )
