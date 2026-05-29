"""W3-089: --acceptance 分隔符拆條 + 反斜線跳脫 + 拆條警告測試。

驗證 _parse_acceptance_items / _split_unescaped 兩 helper：
- 內文含分隔符時的拆條行為與警告
- 反斜線跳脫保留字面分隔符不拆條
- 多值與去空白/去空項處理

設計備註：測試以 SEP 常數組裝含分隔符的字串，避免在原始碼字面散落分隔符
（同時也對應 PC-079 的 CLI 參數 footgun 主題）。
"""
from __future__ import annotations

from ticket_system.commands.create import (
    _ACCEPTANCE_SEP as SEP,
    _parse_acceptance_items,
    _split_unescaped,
)

ESC = "\\"  # 反斜線


def test_single_value_no_separator_keeps_one_item():
    acceptance, warnings = _parse_acceptance_items(["驗收條件 A"])
    assert acceptance == ["驗收條件 A"]
    assert warnings == []


def test_separator_splits_into_multiple_items():
    raw = f"條件一{SEP}條件二"
    acceptance, warnings = _parse_acceptance_items([raw])
    assert acceptance == ["條件一", "條件二"]
    # 單一值被拆成 2 條 → 應發出警告供使用者確認
    assert len(warnings) == 1
    assert "2" in warnings[0]


def test_escaped_separator_preserved_as_literal_no_split():
    # 內文含分隔符（描述 shell pipe），以反斜線跳脫
    raw = f"重現實證 -q {ESC}{SEP} tail 導致 0 行"
    acceptance, warnings = _parse_acceptance_items([raw])
    assert acceptance == [f"重現實證 -q {SEP} tail 導致 0 行"]
    # 跳脫後未拆條 → 無警告
    assert warnings == []


def test_mixed_escaped_and_unescaped_separator():
    # 第一段含跳脫分隔符（字面保留），第二段為真正分隔
    raw = f"shell -q {ESC}{SEP} tail{SEP}另一條件"
    acceptance, warnings = _parse_acceptance_items([raw])
    assert acceptance == [f"shell -q {SEP} tail", "另一條件"]
    assert len(warnings) == 1


def test_multiple_acceptance_args_each_evaluated():
    raw_a = "獨立條件"
    raw_b = f"拆條 X{SEP}拆條 Y"
    acceptance, warnings = _parse_acceptance_items([raw_a, raw_b])
    assert acceptance == ["獨立條件", "拆條 X", "拆條 Y"]
    # 只有第二個值觸發拆條警告
    assert len(warnings) == 1


def test_empty_segments_stripped():
    raw = f"條件{SEP}{SEP}  {SEP}尾"
    acceptance, warnings = _parse_acceptance_items([raw])
    assert acceptance == ["條件", "尾"]
    # 去空項後仍 > 1 條 → 警告
    assert len(warnings) == 1


def test_whitespace_trimmed():
    raw = f"  前後空白  {SEP}  另一條  "
    acceptance, _ = _parse_acceptance_items([raw])
    assert acceptance == ["前後空白", "另一條"]


def test_split_unescaped_basic():
    assert _split_unescaped("a|b|c", "|") == ["a", "b", "c"]


def test_split_unescaped_escape_restores_literal():
    assert _split_unescaped("a\\|b", "|") == ["a|b"]


def test_split_unescaped_no_separator():
    assert _split_unescaped("plain text", "|") == ["plain text"]


def test_split_unescaped_trailing_backslash_preserved():
    # 結尾單獨反斜線（後面非分隔符）原樣保留，不誤判
    assert _split_unescaped("path\\", "|") == ["path\\"]
