"""Ticket ID pattern SSOT util 測試（收斂 hooks 全域約 10 份 TICKET_ID_PATTERN
定義後的行為快照）。

驗證：
- 各具名變體的比對行為與原各 hook 定義點逐一對齊（byte-exact 正則字面）
- extract_ticket_id_anchored 的標籤錨定優先語意（多票號同行殘留缺口修正）
"""

import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(_hooks_dir))

from lib.ticket_id_pattern import (  # noqa: E402
    SEARCH_NO_SUFFIX_RE,
    SEARCH_SINGLE_SUFFIX_RE,
    SEARCH_WITH_SUFFIX_RE,
    SEARCH_WITH_SUFFIX_AND_SLUG_RE,
    SEARCH_BOUNDED_RE,
    MATCH_GROUPED_STR,
    FULL_ANCHORED_RE,
    BARE_START_BOUNDED_RE,
    BARE_BOTH_BOUNDED_RE,
    extract_ticket_id_anchored,
)

import re


# --- 各變體字面與原定義點逐一對齊（byte-exact，防後續誤改分歧） ---


def test_search_no_suffix_matches_original_literal():
    assert SEARCH_NO_SUFFIX_RE.pattern == r"\d+\.\d+\.\d+-W\d+-\d+"


def test_search_single_suffix_matches_original_literal():
    assert SEARCH_SINGLE_SUFFIX_RE.pattern == r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)?"


def test_search_with_suffix_matches_original_literal():
    assert SEARCH_WITH_SUFFIX_RE.pattern == r"(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)"


def test_search_with_suffix_and_slug_matches_original_literal():
    assert SEARCH_WITH_SUFFIX_AND_SLUG_RE.pattern == (
        r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*(?:-[a-z0-9][a-z0-9-]{0,59})?"
    )


def test_search_bounded_matches_original_literal():
    assert SEARCH_BOUNDED_RE.pattern == r"\b\d+\.\d+\.\d+-W\d+-\d+\b"


def test_match_grouped_str_matches_original_literal():
    assert MATCH_GROUPED_STR == r"(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)"


def test_full_anchored_matches_original_literal():
    assert FULL_ANCHORED_RE.pattern == (
        r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"
    )


def test_bare_start_bounded_matches_original_literal():
    assert BARE_START_BOUNDED_RE.pattern == r"\bW\d+-\d+"


def test_bare_both_bounded_matches_original_literal():
    assert BARE_BOTH_BOUNDED_RE.pattern == r"\bW\d+-\d+\b"


# --- 各變體行為快照（來自原 hook 的實際用法） ---


def test_search_no_suffix_findall_multiple():
    assert SEARCH_NO_SUFFIX_RE.findall(
        "0.2.1-W3-100 and 0.2.1-W3-200"
    ) == ["0.2.1-W3-100", "0.2.1-W3-200"]


def test_search_single_suffix_no_multi_level():
    """單層可選後綴不吃多層（僅取第一層 `.5`，不含 `.2`）。"""
    m = SEARCH_SINGLE_SUFFIX_RE.search("0.2.1-W3-100.5.2")
    assert m.group(0) == "0.2.1-W3-100.5"


def test_search_with_suffix_multi_level_capture():
    m = SEARCH_WITH_SUFFIX_RE.search("0.18.0-W10-017.9.1 執行清理")
    assert m.group(1) == "0.18.0-W10-017.9.1"


def test_match_grouped_str_three_groups():
    m = re.match(MATCH_GROUPED_STR, "0.2.1-W3-100.5")
    assert m.groups() == ("0.2.1", "3", "100.5")


def test_full_anchored_rejects_trailing_garbage():
    """全字串錨定：結尾多餘字元應拒絕（不同於 MATCH_GROUPED_STR 的前綴 match）。"""
    assert FULL_ANCHORED_RE.match("0.2.1-W3-100 trailing") is None
    assert FULL_ANCHORED_RE.match("0.2.1-W3-100") is not None


def test_full_anchored_accepts_optional_slug():
    assert FULL_ANCHORED_RE.match("0.2.1-W3-100-fix-typo") is not None


def test_bare_start_bounded_no_trailing_boundary_required():
    """起始邊界版本：緊接非邊界字元（如 `-extra`）後仍可命中前段。"""
    m = BARE_START_BOUNDED_RE.search("W3-100-extra")
    assert m.group(0) == "W3-100"


def test_bare_both_bounded_rejects_substring():
    assert BARE_BOTH_BOUNDED_RE.search("XW3-100") is None


# --- extract_ticket_id_anchored：標籤錨定優先語意 ---


def test_anchored_label_colon_form():
    assert extract_ticket_id_anchored("Ticket: 1.0.0-W2-001") == "1.0.0-W2-001"


def test_anchored_label_bracket_form():
    assert extract_ticket_id_anchored("[Ticket] 1.5.0-W5-005.2") == "1.5.0-W5-005.2"


def test_anchored_label_hash_dash_form():
    assert (
        extract_ticket_id_anchored("#Ticket-0.18.0-W10-017.9.1 執行清理")
        == "0.18.0-W10-017.9.1"
    )


def test_anchored_no_label_falls_back_to_first_match():
    """無標籤時退回純位置優先（既有行為，不可被本次改動破壞）。"""
    assert extract_ticket_id_anchored("0.2.1-W3-100 依規格實作") == "0.2.1-W3-100"


def test_anchored_no_id_returns_none():
    assert extract_ticket_id_anchored("探索 src/ 目錄結構並回報") is None


def test_anchored_prefers_labeled_over_earlier_positional_decoy():
    """多票號同行殘留缺口修正核心場景：背景票在前（無標籤）、目標票在後
    （有『Ticket:』標籤）時，優先回傳標籤命中的目標票，而非位置在前的
    背景票。"""
    line = "承接 0.2.1-W3-100 的結論，目標票 Ticket: 0.2.1-W3-547"
    assert extract_ticket_id_anchored(line) == "0.2.1-W3-547"


def test_anchored_multiple_unlabeled_ids_uses_first_positional():
    """多票號同行但皆無標籤時，維持原始純位置優先（第一個命中）。"""
    line = "0.2.1-W3-100 與 0.2.1-W3-200 兩票相關"
    assert extract_ticket_id_anchored(line) == "0.2.1-W3-100"
