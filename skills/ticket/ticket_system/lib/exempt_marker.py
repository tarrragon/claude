"""PC-093 exempt marker 格式驗證與生成。

背景：`.claude/hooks/phase4-decision-enforcement-hook.py` 定義
`<!-- PC-093-exempt: <category>:<reason> -->` 標記語法（category 白名單 +
reason 規則）。自由撰寫章節（Solution / Test Results / NeedsContext 等）以
`append-log` 寫入後即無法修改——`append-log` 僅能追加、CLI 無編輯指令、
該區段不在 `ticket-file-access-guard-hook` 的白名單內故 Edit 工具被拒。
本模組供 `commands/track_exempt_marker.py` 使用，讓 CLI 能對既有行補上
格式合法的 marker，而不需事後修改原文字。

SSOT 邊界（刻意不 import）：category 白名單 / reason 規則的權威定義在上述
hook 檔案內。本模組複製而非 import 該定義——該 hook 檔案另有他票並行維護
中不宜同時觸碰，且以連字號檔名 + PEP 723 script header 存在，非套件化
模組，無法安全 import。複製範圍已縮至驗證規則本身（category 白名單 +
reason 規則），不含 phrase 偵測表——因為 marker 是否真正生效，最終仍由
該 hook 在 phase4 轉換 / complete 時重新掃描整份 ticket body 判定；本模組
的驗證只是寫入前的 fail-fast，不是唯一把關層。兩處清單若不同步，最壞
情況是 CLI 端誤放行一個 hook 端仍會擋下的格式，使用者仍會在下一個檢查點
看到錯誤，不構成安全性後門（詳見 track_exempt_marker.py 模組文件的防濫用
結論）。
"""
from __future__ import annotations

import re
from typing import Optional, Pattern, Tuple

# 與 phase4-decision-enforcement-hook.py 的 EXEMPT_CATEGORIES 逐字同步。
EXEMPT_CATEGORIES = frozenset({
    "tdd-transition",
    "baseline-gated",
    "ticket-tracked",
    "user-override",
    "rule-quote",
    "history",
})

REASON_MIN_LEN = 10

# rule-quote 類別：reason 必須含 .claude/rules/ 或 .claude/pm-rules/ 路徑
RULE_PATH_PATTERN = re.compile(r"\.claude/(?:rules|pm-rules)/")

# 人類可讀錯誤訊息對照表（與 hook 的 ERR_MESSAGE_MAP 同語意，濃縮為單行）
ERR_MESSAGE_MAP = {
    "category-whitelist": (
        "Exempt category 不在白名單（合法值：" + ", ".join(sorted(EXEMPT_CATEGORIES)) + "）"
    ),
    "reason-too-short": f"Exempt reason 太短（< {REASON_MIN_LEN} 字元）",
    "baseline-need-number": "baseline-gated 類別的 reason 必須含數字（量化基線）",
    "ticket-tracked-need-id": "ticket-tracked 類別的 reason 必須含 W{wave}-{seq} 格式 ticket ID",
    "rule-quote-need-path": "rule-quote 類別的 reason 必須含規則檔案路徑（.claude/rules/ 或 .claude/pm-rules/）",
    "history-need-anchor": "history 類別的 reason 必須含 W{wave}-{seq} 格式 ticket ID 作歷史錨點",
}


def resolve_ticket_id_pattern() -> "Pattern[str]":
    """取得 bare-form ticket ID pattern（`W{wave}-{seq}`）。

    優先透過 `.claude/lib/ticket_id_pattern.py`（單一權威，`hook` 本身也用
    這份定義的 `BARE_START_BOUNDED_RE`）動態載入；找不到 `.claude/` 目錄的
    孤立測試環境則退回內嵌等價 regex（與 `BARE_START_BOUNDED_RE` 逐字相同）。
    """
    from ticket_system.lib.claude_lib_loader import load_claude_lib

    module = load_claude_lib("ticket_id_pattern")
    if module is not None:
        return module.BARE_START_BOUNDED_RE
    return re.compile(r"\bW\d+-\d+")


def validate_exempt_fields(
    category: str, reason: str, *, ticket_id_pattern: "Pattern[str]"
) -> Tuple[bool, Optional[str]]:
    """驗證 category 白名單 + reason 規則（與 hook 的同名函式同規則）。

    Returns:
        (is_valid, err_code)。err_code 為 None 時代表通過；否則對照
        ERR_MESSAGE_MAP 取得人類可讀訊息。
    """
    if category not in EXEMPT_CATEGORIES:
        return (False, "category-whitelist")
    if len(reason) < REASON_MIN_LEN:
        return (False, "reason-too-short")
    if category == "baseline-gated" and not re.search(r"\d", reason):
        return (False, "baseline-need-number")
    if category == "ticket-tracked" and not ticket_id_pattern.search(reason):
        return (False, "ticket-tracked-need-id")
    if category == "rule-quote" and not RULE_PATH_PATTERN.search(reason):
        return (False, "rule-quote-need-path")
    if category == "history" and not ticket_id_pattern.search(reason):
        return (False, "history-need-anchor")
    return (True, None)


def build_marker_line(category: str, reason: str) -> str:
    """組出 `<!-- PC-093-exempt: category:reason -->` 標記行（不含結尾換行）。"""
    return f"<!-- PC-093-exempt: {category}:{reason} -->"


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
