"""check_domain_coverage 測試：FR token 展開（逗號/範圍）+ 覆蓋差集判定。"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_domain_coverage as cdc  # noqa: E402


# --- extract_fr_ids：token 展開 ---

def test_extract_single_fr():
    assert cdc.extract_fr_ids("FR-04 覆蓋") == {4}


def test_extract_comma_list():
    assert cdc.extract_fr_ids("FR-01,02,03 群") == {1, 2, 3}


def test_extract_range_tilde():
    assert cdc.extract_fr_ids("FR-13~17 各畫面") == {13, 14, 15, 16, 17}


def test_extract_range_hyphen():
    assert cdc.extract_fr_ids("FR-19-21 cross-cutting") == {19, 20, 21}


def test_extract_mixed_tokens():
    ids = cdc.extract_fr_ids("| FR-04,07,12 | Networth |\n| FR-19,20,21,25 | presentation |")
    assert ids == {4, 7, 12, 19, 20, 21, 25}


# --- extract_spec_frs：從 ### FR-XX: 標題 ---

def test_extract_spec_frs_from_headers():
    spec = "# spec\n### FR-01: A\nbody\n### FR-25: B\nbody\n"
    assert cdc.extract_spec_frs(spec) == {1, 25}


def test_extract_spec_frs_handles_h4_headers():
    """真實 SPEC-001 用 #### FR-XX:（H4）——不可只認 H3（Round 2-C 假通過回歸）。"""
    spec = "## FR\n#### FR-01: A\nbody\n#### FR-26: B\nbody\n"
    assert cdc.extract_spec_frs(spec) == {1, 26}


# --- check_domain_coverage：差集 ---

def test_all_covered_returns_empty():
    spec = "### FR-01: A\n### FR-02: B\n"
    domain_map = "§7\n| FR-01,02 | Ledger |\n"
    assert cdc.check_domain_coverage(spec, domain_map) == []


def test_uncovered_fr_reported():
    """domain map 停在 FR-24，spec 有 FR-25/26 → 回報未覆蓋（W2-014 實證缺口）。"""
    spec = "### FR-24: 驗證\n### FR-25: 設定\n### FR-26: 提醒\n"
    domain_map = "覆蓋表\n| FR-24 | Ledger |\n"
    assert cdc.check_domain_coverage(spec, domain_map) == [25, 26]


def test_range_coverage_matches_individual_spec_frs():
    spec = "### FR-13: A\n### FR-15: B\n### FR-17: C\n"
    domain_map = "| FR-13~17 | presentation |\n"
    assert cdc.check_domain_coverage(spec, domain_map) == []


# --- locate_domain_map ---

def test_locate_prefers_same_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 隔離 cwd，避免 fallback 命中真實 docs/domain-map.md
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: A\n", encoding="utf-8")
    dmap = tmp_path / "domain-map.md"
    dmap.write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    assert cdc.locate_domain_map(spec, None) == dmap


def test_locate_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 隔離 cwd，確保無 docs/domain-map.md fallback
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: A\n", encoding="utf-8")
    assert cdc.locate_domain_map(spec, None) is None
