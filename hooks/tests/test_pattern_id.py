"""error-pattern ID SSOT util 測試（1.0.0-W1-019.2）。

驗證 PATTERN_ID_RE 同時支援：
- flat 凍結核心格式：PC-099、IMP-049（既有共享 base）
- Model 1 前綴格式：PC-V1-001、IMP-APP-012（<CAT>-<PROJ>-NNN）

並驗證回溯正確性（前綴段字元集含數字，flat 編號不得被誤當前綴）與
word boundary 防 substring 誤判（PC-113 家族）。
"""

import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib.pattern_id import PATTERN_ID_RE, extract_pattern_id  # noqa: E402


def _match(text):
    m = PATTERN_ID_RE.search(text)
    return m.group(0) if m else None


# --- flat 凍結核心格式 ---


def test_matches_flat_pc():
    assert _match("PC-099") == "PC-099"


def test_matches_flat_in_filename():
    assert _match("PC-099-meta-ticket.md") == "PC-099"


def test_flat_001_not_consumed_as_prefix():
    """回溯正確性：flat 三位數編號不得被 optional 前綴段吞掉。"""
    assert _match("PC-001") == "PC-001"
    assert _match("PC-001-slug.md") == "PC-001"


# --- Model 1 前綴格式 ---


def test_matches_prefixed_pc():
    assert _match("PC-V1-001") == "PC-V1-001"


def test_matches_prefixed_in_filename():
    assert _match("PC-V1-001-some-slug.md") == "PC-V1-001"


def test_matches_prefix_with_digits():
    """專案代碼本身含數字（V1 / C2C）須正確匹配。"""
    assert _match("PC-C2C-012") == "PC-C2C-012"
    assert _match("IMP-V1-049") == "IMP-V1-049"


# --- 全 category ---


def test_matches_all_categories_flat():
    for cid in ("PC-001", "IMP-049", "ARCH-010", "ANA-003", "DOC-007", "CQ-002", "TEST-006"):
        assert _match(cid) == cid


def test_matches_all_categories_prefixed():
    for cid in ("IMP-APP-012", "ARCH-SCLK-003", "DOC-CCS-001"):
        assert _match(cid) == cid


# --- word boundary 防 substring 誤判（PC-113 家族）---


def test_word_boundary_no_leading_substring():
    """前綴黏連 word char 不得誤判（XPC-099 不應匹配 PC-099）。"""
    assert _match("XPC-099") != "PC-099"


# --- extract_pattern_id 大小寫正規化 ---


def test_extract_normalizes_case():
    assert extract_pattern_id("pc-v1-001-foo.md") == "PC-V1-001"


def test_extract_returns_none_when_absent():
    assert extract_pattern_id("README.md") is None
