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
    """domain map 停在 FR-24，spec 有 FR-25/26 → 回報未覆蓋（已實證缺口）。"""
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


# --- extract_event_signaled_frs：事件流訊號詞掃描 ---

def test_extract_event_signaled_frs_hits_signal_word():
    spec = "### FR-01: 掃描完成的系統層通知\n驗收：發送通知。\n"
    assert cdc.extract_event_signaled_frs(spec) == {1}


def test_extract_event_signaled_frs_no_signal_word():
    spec = "### FR-01: 一般敘述\n驗收：文字對齊正確。\n"
    assert cdc.extract_event_signaled_frs(spec) == set()


def test_extract_event_signaled_frs_english_word_case_insensitive():
    spec = "### FR-02: 背景任務\n改以 Isolate 執行。\n"
    assert cdc.extract_event_signaled_frs(spec) == {2}


def test_extract_event_signaled_frs_multiple_frs_only_some_signaled():
    spec = (
        "### FR-01: 一般敘述\n無訊號。\n"
        "### FR-02: 排程任務\n背景排程處理。\n"
    )
    assert cdc.extract_event_signaled_frs(spec) == {2}


# --- extract_channel_section：以標題文字定位，不依編號 ---

def test_extract_channel_section_locates_by_title_regardless_of_numbering():
    """章節編號可能與既有內容衝突（如本專案既有「## 2.5」），須以標題文字定位。"""
    domain_map = (
        "## 2.5 三個易混淆詞的定義\n其他內容\n"
        "## 9. 通道與協調圖\n通道內容\n"
        "## 10. 下一節\n下一節內容\n"
    )
    section = cdc.extract_channel_section(domain_map)
    assert section is not None
    assert "通道內容" in section
    assert "下一節內容" not in section
    assert "其他內容" not in section


def test_extract_channel_section_missing_returns_none():
    assert cdc.extract_channel_section("## 3. Bundle 界定表\n無此節\n") is None


# --- extract_arrival_level_table：通道節內的到達類別與級別子表 ---

def test_extract_arrival_level_table_locates_subsection():
    channel_section = (
        "## 2.5. 通道與協調圖\n"
        "### 2.5.1 通道清單\n通道清單內容\n"
        "### 2.5.3 到達類別與級別實例\n"
        "| 通道 | 事件/請求 | 到達類別 | 級別 | 引用來源 |\n"
        "|---|---|---|---|---|\n"
        "| toast | 掃描完成通知 | 推送型 | 不可棄 | FR-01 |\n"
    )
    table = cdc.extract_arrival_level_table(channel_section)
    assert table is not None
    assert "FR-01" in table
    assert "通道清單內容" not in table


def test_extract_arrival_level_table_missing_subsection_returns_none():
    channel_section = "## 2.5. 通道與協調圖\n### 2.5.1 通道清單\n僅有通道清單\n"
    assert cdc.extract_arrival_level_table(channel_section) is None


def test_extract_arrival_level_table_none_input_returns_none():
    assert cdc.extract_arrival_level_table(None) is None


# --- check_event_flow_labeling：整合行為 ---

def test_check_event_flow_labeling_no_signal_returns_empty():
    spec = "### FR-01: 一般敘述\n無訊號。\n"
    domain_map = "## 3. Bundle 界定表\n無通道節\n"
    assert cdc.check_event_flow_labeling(spec, domain_map) == []


def test_check_event_flow_labeling_missing_channel_section_reports_all_signaled():
    spec = "### FR-01: 掃描完成通知\n發送通知。\n"
    domain_map = "## 3. Bundle 界定表\n無通道節\n"
    assert cdc.check_event_flow_labeling(spec, domain_map) == [1]


def test_check_event_flow_labeling_labeled_fr_not_reported():
    spec = "### FR-01: 掃描完成通知\n發送通知。\n"
    domain_map = (
        "## 2.5. 通道與協調圖\n"
        "### 2.5.3 到達類別與級別實例\n"
        "| 通道 | 事件/請求 | 到達類別 | 級別 | 引用來源 |\n"
        "|---|---|---|---|---|\n"
        "| toast | 掃描完成通知 | 推送型 | 不可棄 | FR-01 |\n"
    )
    assert cdc.check_event_flow_labeling(spec, domain_map) == []


def test_check_event_flow_labeling_partial_labeling_reports_unlabeled_only():
    spec = (
        "### FR-01: 掃描完成通知\n發送通知。\n"
        "### FR-02: 暫態提示\n事件觸發提示。\n"
    )
    domain_map = (
        "## 2.5. 通道與協調圖\n"
        "### 2.5.3 到達類別與級別實例\n"
        "| 通道 | 事件/請求 | 到達類別 | 級別 | 引用來源 |\n"
        "|---|---|---|---|---|\n"
        "| toast | 掃描完成通知 | 推送型 | 不可棄 | FR-01 |\n"
    )
    assert cdc.check_event_flow_labeling(spec, domain_map) == [2]


# --- CLI：--check-event-flow-labeling ---

def test_main_with_event_flow_flag_reports_missing_labeling(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: 掃描完成通知\n發送通知。\n", encoding="utf-8")
    domain_map = tmp_path / "domain-map.md"
    domain_map.write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    rc = cdc.main([str(spec), "--check-event-flow-labeling"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "事件流標定檢核發現" in out
    assert "FR-01" in out


def test_main_without_event_flow_flag_skips_check(tmp_path, monkeypatch, capsys):
    """未帶 flag 時不執行事件流標定檢核，維持既有行為。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: 掃描完成通知\n發送通知。\n", encoding="utf-8")
    domain_map = tmp_path / "domain-map.md"
    domain_map.write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    rc = cdc.main([str(spec)])
    assert rc == 0
    assert "事件流標定" not in capsys.readouterr().out
