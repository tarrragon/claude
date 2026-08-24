"""YAML `\\u` 逸出殘留孤立代理碼位的修正回歸測試。

根因：PyYAML 雙引號純量的 \\uXXXX 逸出序列不會像 JSON 一樣自動組合合法
UTF-16 代理對，也不拒絕不成對的孤立代理碼位。這些 U+D800-U+DFFF 碼位一旦
進入 Python str，任何後續 UTF-8 編碼（含 save_ticket 寫入）都會拋
UnicodeEncodeError。此類字元不存在於原始檔案位元組（檔案內容是 ASCII
逸出序列），只在 yaml.safe_load 解析後才出現，故修正點在 parse_frontmatter
/ load_ticket 的 YAML 解析完成處。
"""
from __future__ import annotations

import pytest

from ticket_system.lib.parser import (
    _sanitize_surrogates,
    _sanitize_surrogates_deep,
    parse_frontmatter,
)


class TestSanitizeSurrogatesUnit:
    def test_plain_string_unchanged(self):
        assert _sanitize_surrogates("正常文字") == "正常文字"

    def test_valid_pair_combined_into_single_astral_char(self):
        """合法配對逸出（\\uD83D\\uDE00）組合為單一星面字元，可正確編碼 UTF-8。"""
        broken = "😀"
        fixed = _sanitize_surrogates(broken)
        assert fixed == "\U0001F600"
        fixed.encode("utf-8")  # 不應拋出

    def test_lone_high_surrogate_replaced_with_replacement_char(self):
        broken = "prefix \ud83d suffix"
        fixed = _sanitize_surrogates(broken)
        assert "\ud83d" not in fixed
        assert "�" in fixed
        fixed.encode("utf-8")  # 不應拋出

    def test_deep_sanitizes_nested_list_and_dict(self):
        data = {
            "why": "😀 test",
            "acceptance": ["ok", "😁 broken"],
        }
        fixed = _sanitize_surrogates_deep(data)
        assert fixed["why"] == "\U0001F600 test"
        assert fixed["acceptance"][1] == "\U0001F601 broken"


class TestParseFrontmatterSurrogateRegression:
    def test_valid_surrogate_pair_escape_does_not_break_encoding(self):
        """來源票 why 欄位以 \\uD83D\\uDE00 形式表示表情符號時，解析後不得
        殘留無法編碼的代理碼位（W3-1026 root cause 重現）。"""
        content = '---\nwhy: "emoji \\uD83D\\uDE00 test"\n---\nbody\n'
        fm, _body = parse_frontmatter(content)
        fm["why"].encode("utf-8")  # 修正前會拋 UnicodeEncodeError
        assert fm["why"] == "emoji \U0001F600 test"

    def test_lone_surrogate_escape_does_not_break_encoding(self):
        content = '---\nwhy: "broken \\uD83D only"\n---\nbody\n'
        fm, _body = parse_frontmatter(content)
        fm["why"].encode("utf-8")  # 修正前會拋 UnicodeEncodeError
        assert "\ud83d" not in fm["why"]
