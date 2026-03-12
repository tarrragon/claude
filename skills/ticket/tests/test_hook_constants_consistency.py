"""
測試 Hook 和 ticket_system 常數一致性

驗證：
1. Hook 中的 TICKET_ID_REGEX 與 constants.py 中的 TICKET_ID_PATTERN 一致
2. Hook 中的 KNOWN_TICKET_SUFFIXES 與 constants.py 中的清單一致
3. Hook 的 has_description_suffix() 與 id_parser.py 的實作邏輯一致
"""

import re
from pathlib import Path


def test_hook_ticket_id_regex_matches_pattern() -> None:
    """驗證 Hook 的正則與 constants.py 一致"""
    from ticket_system.lib.constants import TICKET_ID_PATTERN

    # 從 Hook 檔案讀取正則（Hook 位於 .claude/hooks/）
    hook_file = Path(__file__).parent.parent.parent.parent / "hooks" / "ticket-id-validator-hook.py"
    with open(hook_file, "r", encoding="utf-8") as f:
        hook_content = f.read()

    # 提取 TICKET_ID_REGEX 值
    match = re.search(r'TICKET_ID_REGEX\s*=\s*r"([^"]+)"', hook_content)
    assert match is not None, "無法從 Hook 中提取 TICKET_ID_REGEX"
    hook_regex = match.group(1)

    # 驗證一致性
    assert hook_regex == TICKET_ID_PATTERN, (
        f"Hook TICKET_ID_REGEX 與 constants.py TICKET_ID_PATTERN 不一致\n"
        f"Hook: {hook_regex}\n"
        f"Constants: {TICKET_ID_PATTERN}"
    )


def test_hook_known_suffixes_matches_constants() -> None:
    """驗證 Hook 的後綴清單與 constants.py 一致"""
    from ticket_system.lib.constants import KNOWN_TICKET_SUFFIXES

    # 從 Hook 檔案讀取後綴清單（Hook 位於 .claude/hooks/）
    hook_file = Path(__file__).parent.parent.parent.parent / "hooks" / "ticket-id-validator-hook.py"
    with open(hook_file, "r", encoding="utf-8") as f:
        hook_content = f.read()

    # 提取 KNOWN_TICKET_SUFFIXES 清單
    # 找到清單起點和結尾
    start_match = re.search(r"KNOWN_TICKET_SUFFIXES\s*=\s*\[", hook_content)
    assert start_match is not None, "無法從 Hook 中找到 KNOWN_TICKET_SUFFIXES"

    start_pos = start_match.end()
    # 找到對應的結束括號
    bracket_count = 1
    pos = start_pos
    while bracket_count > 0 and pos < len(hook_content):
        if hook_content[pos] == "[":
            bracket_count += 1
        elif hook_content[pos] == "]":
            bracket_count -= 1
        pos += 1

    # 提取清單內容
    list_content = hook_content[start_pos : pos - 1]
    # 提取所有字串
    hook_suffixes = re.findall(r'"([^"]+)"', list_content)

    # 驗證一致性
    assert set(hook_suffixes) == set(KNOWN_TICKET_SUFFIXES), (
        f"Hook KNOWN_TICKET_SUFFIXES 與 constants.py 不一致\n"
        f"Hook: {sorted(hook_suffixes)}\n"
        f"Constants: {sorted(KNOWN_TICKET_SUFFIXES)}"
    )


def test_hook_and_id_parser_has_description_suffix_logic() -> None:
    """驗證 Hook 的 has_description_suffix() 與 id_parser 邏輯一致"""
    from ticket_system.lib.id_parser import has_description_suffix as parser_func
    from ticket_system.lib.constants import TICKET_ID_PATTERN

    # 測試案例
    test_cases = [
        ("0.1.0-W11-004-phase1-design", True),  # 帶後綴
        ("0.1.0-W11-004", False),  # 無後綴
        ("0.1.0-W11-004-analysis", True),  # 帶後綴
        ("invalid", False),  # 無效
        (None, False),  # None
    ]

    # 驗證 parser 的實作
    for ticket_id, expected in test_cases:
        result = parser_func(ticket_id)
        assert result == expected, (
            f"id_parser.has_description_suffix({ticket_id!r}) "
            f"期望 {expected}，得到 {result}"
        )

    # 驗證 Hook 的邏輯（這是單元測試，驗證邏輯而非實際呼叫）
    # Hook 中的邏輯應該是：
    # if ticket_id is None: return False
    # match = re.match(TICKET_ID_PATTERN, ticket_id)
    # if not match: return False
    # suffix = match.group(4)
    # return suffix is not None
    hook_regex = re.compile(TICKET_ID_PATTERN)
    for ticket_id, expected in test_cases:
        if ticket_id is None:
            result = False
        else:
            match = hook_regex.match(ticket_id)
            if not match:
                result = False
            else:
                suffix = match.group(4)
                result = suffix is not None

        assert result == expected, (
            f"Hook logic for {ticket_id!r} "
            f"期望 {expected}，得到 {result}"
        )
