"""Checkbox 前綴處理共用工具。

統一 ac_parser 與 acceptance_auditor 的 checkbox 剝除邏輯（0.18.0-W11-001.5）。
避免雙寫風險：之前兩模組分別使用 `split("]", 1)` 與 `startswith + 切片` 兩種策略。

公開 API：
    strip_checkbox_prefix(text) -> tuple[bool, str]
"""

from __future__ import annotations


# Checkbox 前綴常數（支援小寫 x、大寫 X、未勾選）
CHECKBOX_CHECKED_LOWER = "[x]"
CHECKBOX_CHECKED_UPPER = "[X]"
CHECKBOX_UNCHECKED = "[ ]"
CHECKBOX_PREFIX_LEN = 3  # 三者長度均為 3


def strip_checkbox_prefix(text: str) -> tuple[bool, str]:
    """剝除 checkbox 前綴並判斷勾選狀態。

    支援格式：`[x] 內容`、`[X] 內容`、`[ ] 內容`。
    輸入前後空白會先被剝除；剝除前綴後的文字亦會 lstrip。

    Args:
        text: 原始字串（可能含 leading whitespace 與 checkbox 前綴）。

    Returns:
        (checked, stripped): checked 表示是否勾選；stripped 為剝除前綴後的純文字。
        若輸入不含 checkbox 前綴，回傳 `(False, text.strip())`（保守視為未勾選，
        技術債 4.2：未帶 checkbox 的項目語義待釐清）。
    """
    stripped = text.lstrip()

    if stripped.startswith((CHECKBOX_CHECKED_LOWER, CHECKBOX_CHECKED_UPPER)):
        return True, stripped[CHECKBOX_PREFIX_LEN:].lstrip()
    if stripped.startswith(CHECKBOX_UNCHECKED):
        return False, stripped[CHECKBOX_PREFIX_LEN:].lstrip()
    return False, stripped
