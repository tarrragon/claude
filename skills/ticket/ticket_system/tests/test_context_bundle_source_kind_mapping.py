"""Context Bundle 抽取器來源鍵名雙態相容測試（0.2.1-W3-854）。

CONTEXT_BUNDLE_SOURCE_KINDS 為 snake_case（source_ticket / blocked_by /
related_to），frontmatter dict 對 blocked_by / related_to 用 camelCase
（blockedBy / relatedTo），source_ticket 兩端皆為 snake_case。
本檔驗證 _collect_source_ids 與 detect_self_reference 兩個讀取點皆能正確
解析三種來源鍵名（含雙態相容對照本身）。
"""

from __future__ import annotations

from ticket_system.lib import context_bundle_extractor as cbe

TARGET_ID = "0.1.0-W1-100"
SOURCE_ID = "0.1.0-W1-001"


def test_source_kind_frontmatter_keys_explicit_mapping():
    """對照須為顯式定義：source_ticket 維持不變，非機械轉成 sourceTicket。"""
    assert cbe.SOURCE_KIND_FRONTMATTER_KEYS == {
        "source_ticket": "source_ticket",
        "blocked_by": "blockedBy",
        "related_to": "relatedTo",
    }


def test_collect_source_ids_resolves_source_ticket():
    """source_ticket 為來源時行為未變（回歸確認）。"""
    target = {"id": TARGET_ID, "source_ticket": SOURCE_ID}
    collected = cbe._collect_source_ids(target)
    assert (SOURCE_ID, "source_ticket") in collected


def test_collect_source_ids_resolves_blocked_by_camel_case():
    """blockedBy（camelCase frontmatter 鍵）為來源時能被抽取到。"""
    target = {"id": TARGET_ID, "blockedBy": [SOURCE_ID]}
    collected = cbe._collect_source_ids(target)
    assert (SOURCE_ID, "blocked_by") in collected


def test_collect_source_ids_resolves_related_to_camel_case():
    """relatedTo（camelCase frontmatter 鍵）為來源時能被抽取到。"""
    target = {"id": TARGET_ID, "relatedTo": [SOURCE_ID]}
    collected = cbe._collect_source_ids(target)
    assert (SOURCE_ID, "related_to") in collected


def test_collect_source_ids_snake_case_key_not_present_is_noop():
    """驗證修復前的失效樣態：若 dict 只放 snake_case 的 blocked_by（frontmatter
    實際不會這樣產出），_collect_source_ids 不應誤命中——確保對照精準指向
    camelCase，而非同時接受兩種鍵名造成語意混淆。"""
    target = {"id": TARGET_ID, "blocked_by": [SOURCE_ID]}
    collected = cbe._collect_source_ids(target)
    assert collected == []


def test_detect_self_reference_true_for_blocked_by_camel_case():
    """detect_self_reference 對 camelCase blockedBy 來源同樣生效。"""
    target = {"id": TARGET_ID, "blockedBy": [TARGET_ID]}
    assert cbe.detect_self_reference(target) is True


def test_detect_self_reference_true_for_related_to_camel_case():
    """detect_self_reference 對 camelCase relatedTo 來源同樣生效。"""
    target = {"id": TARGET_ID, "relatedTo": [TARGET_ID]}
    assert cbe.detect_self_reference(target) is True


def test_detect_self_reference_true_for_source_ticket():
    """source_ticket 自我引用偵測維持不變（回歸確認）。"""
    target = {"id": TARGET_ID, "source_ticket": TARGET_ID}
    assert cbe.detect_self_reference(target) is True


def test_detect_self_reference_false_when_no_self_match():
    target = {"id": TARGET_ID, "blockedBy": [SOURCE_ID], "relatedTo": [SOURCE_ID]}
    assert cbe.detect_self_reference(target) is False
