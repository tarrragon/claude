"""check_domain_coverage 測試：FR token 展開（逗號/範圍）+ 覆蓋差集判定。"""

import sys

import pytest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_domain_coverage as cdc  # noqa: E402
from domain_coverage import fr_extract  # noqa: E402


def _covered_by(spec_text, map_text, map_name="domain-map.md"):
    """單份 map 的覆蓋差集：走 main() 實際使用的判定路徑（多份 map 聯集版的單元素清單）。"""
    return cdc.check_domain_coverage_union(spec_text, [(map_name, map_text)])


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
    assert _covered_by(spec, domain_map) == []


def test_uncovered_fr_reported():
    """domain map 停在 FR-24，spec 有 FR-25/26 → 回報未覆蓋（已實證缺口）。"""
    spec = "### FR-24: 驗證\n### FR-25: 設定\n### FR-26: 提醒\n"
    domain_map = "覆蓋表\n| FR-24 | Ledger |\n"
    assert _covered_by(spec, domain_map) == [25, 26]


def test_range_coverage_matches_individual_spec_frs():
    spec = "### FR-13: A\n### FR-15: B\n### FR-17: C\n"
    domain_map = "| FR-13~17 | presentation |\n"
    assert _covered_by(spec, domain_map) == []


# --- locate_domain_maps（同目錄與找不到）---

def test_locate_prefers_same_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 隔離 cwd，避免 fallback 命中真實 docs/domain-map.md
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: A\n", encoding="utf-8")
    dmap = tmp_path / "domain-map.md"
    dmap.write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    assert cdc.locate_domain_maps(spec, None) == [dmap]


def test_locate_missing_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 隔離 cwd，確保無 docs/domain-map.md fallback
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: A\n", encoding="utf-8")
    assert cdc.locate_domain_maps(spec, None) == []


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


# --- FR 比對鍵 = (spec 識別, FR 編號) ---

MAP_TAIL = "請於 domain map 補上這些 FR 的歸屬：FR 所在的章節標題含 SPEC-101，或在同一行、該 FR 之前寫出 SPEC-101。"
LAYER_TAIL = "層級 SPEC 以系統層判定，請於系統層補上這些 FR 的歸屬：FR 所在的章節標題含 SPEC-101，或在同一行、該 FR 之前寫出 SPEC-101。"
SPEC_A = "---\nid: SPEC-101\n---\n### FR-01: a\n### FR-02: b\n### FR-03: c\n"
SPEC_B = SPEC_A.replace("SPEC-101", "SPEC-202")
MAP_UNDER_B = "## 8. 覆蓋\n### SPEC-202 小節\n| FR-01~03 | Ledger |\n"


def test_e2_same_number_fr_under_other_spec_is_uncovered(capsys):
    """E2 正向對照：map 只在 SPEC-202 下覆蓋 FR-01~03，SPEC-101 三條全未覆蓋。"""
    assert _covered_by(SPEC_A, MAP_UNDER_B) == [1, 2, 3]


def test_e2_same_map_fully_covers_owning_spec():
    assert _covered_by(SPEC_B, MAP_UNDER_B) == []


def test_same_line_attribution_nearest_spec():
    dm = "## 覆蓋\n| SPEC-101 FR-01、SPEC-202 FR-02 | X |\n"
    assert _covered_by(SPEC_A, dm) == [2, 3]
    assert _covered_by(SPEC_B, dm) == [1, 3]


def test_same_line_multiple_frs_share_preceding_spec():
    dm = "## 覆蓋\n| SPEC-101 FR-01、FR-03 | X |\n"
    assert _covered_by(SPEC_A, dm) == [2]


def test_unattributed_tokens_ignored_when_map_has_attributed():
    dm = "## 3. 其他\n提到 FR-01 FR-02 FR-03\n## SPEC-101 覆蓋\n| FR-02 | X |\n"
    assert _covered_by(SPEC_A, dm) == [1, 3]


def test_unattributed_map_counts_for_inspected_spec(capsys):
    """E1 對照：整份無歸屬的 map 其 FR 計給受檢 SPEC（不走相容），stderr 說明；有歸屬 map 結果不同。"""
    dm = "## 覆蓋\n| FR-01~03 | X |\n"
    assert _covered_by(SPEC_A, dm) == []
    err = capsys.readouterr().err
    assert "依預設計給" in err
    assert "相容模式" not in err
    assert _covered_by(SPEC_A, MAP_UNDER_B) != []


def test_compat_mode_when_only_system_layer_has_unattributed_frs(capsys):
    """相容模式的可達情形之一（spec 識別取得）：非系統層 map 無 FR 編號，系統層帶未歸屬的 FR。

    對照：同內容的非系統層 map 依預設計給，不走相容；差異在於系統層不適用預設計給。
    """
    layer = "## 覆蓋\n| FR-01~03 | X |\n"
    assert _covered_by(SPEC_A, layer, "docs/system-layer.md") == []
    err = capsys.readouterr().err
    assert "走相容模式" in err and "非系統層的 map 無任何 FR 編號" in err


def test_no_fr_map_reports_all_uncovered_with_spec_id(capsys):
    """map 無任何 FR 編號：全數未覆蓋；走相容分支而非預設計給（無 FR 的 map 不得被印成依預設計給）。"""
    assert _covered_by(SPEC_A, "## 覆蓋\n無\n") == [1, 2, 3]
    err = capsys.readouterr().err
    assert "依預設計給" not in err
    assert "走相容模式" in err


@pytest.mark.parametrize("system, uncovered_lines", [
    (None, ["FR-01", "FR-02", "FR-03"]),
    ("## 其他\n無對照\n", ["FR-01", "FR-02", "FR-03"]),
    ("## 其他\n| FR-01~02 | sys |\n", ["FR-03"]),
])
def test_compat_branch_end_to_end_with_spec_id(tmp_path, monkeypatch, capsys, system, uncovered_lines):
    """經 main：取得 spec 識別、map 列入本 SPEC 但無 FR 編號時走相容分支，系統層不存在、無 FR、帶未歸屬 FR 三情形皆然。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", "---\ndomain: \"a\"\nsource_specs: [SPEC-101]\n---\n無\n")
    if system is not None:
        _write(tmp_path / "docs/system-layer.md", system)
    assert cdc.main([str(spec)]) == 1
    captured = capsys.readouterr()
    assert "走相容模式" in captured.err and "依預設計給" not in captured.err
    assert [ln.strip() for ln in captured.out.splitlines() if ln.startswith("  FR-")] == uncovered_lines


def test_compat_mode_warns_when_spec_id_missing(capsys):
    spec = "### FR-01: a\n"
    assert _covered_by(spec, MAP_UNDER_B) == []
    assert "WARNING" in capsys.readouterr().err


def test_spec_id_from_filename_when_no_frontmatter_id(tmp_path):
    p = tmp_path / "SPEC-202-name.md"
    p.write_text("### FR-01: a\n", encoding="utf-8")
    assert cdc.extract_spec_id("### FR-01: a\n", p) == "SPEC-202"


def test_spec_id_not_read_from_body_after_frontmatter():
    """frontmatter 無 id 時，不得把收尾 --- 之後正文的 id: 行當成 spec 識別。"""
    spec = "---\ntitle: x\n---\nid: SPEC-999\n### FR-01: a\n"
    assert cdc.extract_spec_id(spec) is None


def test_spec_id_outside_spec_nnn_form_falls_back_to_compat(capsys):
    """id 不是 SPEC-NNN 形式時 map 的歸屬鍵對不上，須走相容模式並警告，不得全數報未覆蓋。"""
    spec = "---\nid: SPEC-UI-001\n---\n### FR-01: a\n"
    assert _covered_by(spec, MAP_UNDER_B) == []
    assert "WARNING" in capsys.readouterr().err


# --- 多 domain 解析鏈（SPEC 與 domain map 分處不同目錄時的定位）---

def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _multi_domain_fixture(tmp_path, source_specs="[SPEC-101]"):
    """SPEC 在 docs/spec/ui/（無 map）；兩個 domain map 分攤 FR，系統層補 FR-03。"""
    _write(tmp_path / "docs/spec/ui/SPEC-101-x.md", SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md",
           f"---\nsource_specs: {source_specs}\n---\n## SPEC-101\n| FR-01 | A |\n")
    _write(tmp_path / "docs/spec/b/domain-map.md",
           f"---\nsource_specs: {source_specs}\n---\n## SPEC-101\n| FR-02 | B |\n")
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101 覆蓋\n| FR-03 | sys |\n")
    return tmp_path / "docs/spec/ui/SPEC-101-x.md"


def test_multi_map_union_resolves_without_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _multi_domain_fixture(tmp_path)
    found = cdc.locate_domain_maps(Path("docs/spec/ui/SPEC-101-x.md"), None)
    assert [p.as_posix() for p in found] == [
        "docs/spec/a/domain-map.md", "docs/spec/b/domain-map.md", "docs/system-layer.md"]
    assert cdc.main([str(spec)]) == 0  # 聯集覆蓋 FR-01/02/03


def test_multi_map_e1_without_source_specs_differs(tmp_path, monkeypatch, capsys):
    """E1 對照：同 fixture 無 source_specs 列入 -> 解析不到，rc=1 且訊息為「未列入」。"""
    monkeypatch.chdir(tmp_path)
    spec = _multi_domain_fixture(tmp_path, source_specs="[]")
    assert cdc.locate_domain_maps(Path("docs/spec/ui/SPEC-101-x.md"), None) == []
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "無一份" in out and "source_specs" in out


def test_ui_dir_without_any_map_reports_no_map(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "找不到任何 domain map" in out and "無一份" not in out


def test_single_domain_root_map_unchanged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/domain-map.md", "## 覆蓋\n| FR-01~03 | X |\n")
    found = cdc.locate_domain_maps(Path("docs/spec/SPEC-101-x.md"), None)
    assert [p.as_posix() for p in found] == ["docs/domain-map.md"]
    assert cdc.main([str(spec)]) == 0


# --- 多 map 聯集在集合層（跨 map 的 FR 聯集）---

def _map(specs, body):
    return f"---\nsource_specs: [{specs}]\n---\n{body}"


def test_union_event_flow_label_only_in_later_file(tmp_path, monkeypatch, capsys):
    """紅輸入：通道章節標題在每份 map 皆有，標定表只在排最後的系統層。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, "---\nid: SPEC-101\n---\n### FR-01: 掃描通知\n### FR-02: b\n### FR-03: c\n")
    _write(tmp_path / "docs/spec/a/domain-map.md",
           _map("SPEC-101", "## SPEC-101\n| FR-01~03 | A |\n## 通道與協調圖\n無表\n"))
    _write(tmp_path / "docs/system-layer.md",
           "## 通道與協調圖\n### 到達類別與級別實例\n| FR-01 | 級別 |\n")
    assert cdc.main([str(spec), "--check-event-flow-labeling"]) == 0, capsys.readouterr().out


def test_union_heading_stack_resets_at_file_boundary(tmp_path, monkeypatch, capsys):
    """紅輸入：前一份以 SPEC-202 標題結尾，後一份無標題的 FR 不得繼承它。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md",
           _map("SPEC-101, SPEC-202", "## SPEC-101\n| FR-01 | A |\n## SPEC-202\n| FR-09 | A |\n"))
    _write(tmp_path / "docs/spec/b/domain-map.md", _map("SPEC-101", "| FR-02~03 | B |\n"))
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_union_untitled_map_falls_back_to_its_source_specs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", _map("SPEC-101", "| FR-02~03 | A |\n"))
    _write(tmp_path / "docs/spec/b/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-01 | B |\n"))
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_union_untitled_multi_source_specs_counts_to_inspected_spec(tmp_path, monkeypatch, capsys):
    """整份無歸屬的 map 其 FR 計給受檢 SPEC，與 source_specs 值數無關。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-01 | A |\n"))
    _write(tmp_path / "docs/spec/b/domain-map.md", _map("SPEC-101, SPEC-202", "| FR-02~03 | B |\n"))
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


# --- 審查的四種由綠轉紅輸入 + 一例反向假綠 ---

def _in_domain_dir(tmp_path, monkeypatch, map_text, system=None, extra_map=None):
    """SPEC-101 在 docs/spec/a/（domain 目錄內），同目錄 map 為未帶 SPEC 標題的 map_text。"""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "docs/spec/a/SPEC-101-x.md", SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", map_text)
    if extra_map:
        _write(tmp_path / "docs/spec/b/domain-map.md", extra_map)
    if system:
        _write(tmp_path / "docs/system-layer.md", system)
    return str(tmp_path / "docs/spec/a/SPEC-101-x.md")


def test_green_to_red_1_multi_source_specs_with_other_spec_in_system(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101, SPEC-202", "| FR-01~03 | A |\n"),
                          system="## SPEC-202\n| FR-09 | s |\n")
    assert cdc.main([spec]) == 0, capsys.readouterr().out


def test_green_to_red_2_no_source_specs_system_mentions_other_spec(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("", "| FR-01~03 | A |\n"),
                          system="SPEC-202 的 FR-09 見此\n")
    assert cdc.main([spec]) == 0, capsys.readouterr().out


def test_green_to_red_3_source_specs_lists_other_spec(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-202", "| FR-01~03 | A |\n"),
                          system="## SPEC-202\n| FR-09 | s |\n")
    assert cdc.main([spec]) == 0, capsys.readouterr().out


def test_green_to_red_4_multi_source_specs_and_other_map_titled(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101, SPEC-202", "| FR-02~03 | A |\n"),
                          extra_map=_map("SPEC-101", "## SPEC-101\n| FR-01 | B |\n"))
    assert cdc.main([spec]) == 0, capsys.readouterr().out


def test_reverse_false_green_verdict_independent_of_neighbours(tmp_path, monkeypatch, capsys):
    """首個 SPEC 標題前的散文 FR 不計入；判定不因旁邊有無系統層而改變。"""
    body = "前言提到 FR-01\n## SPEC-101\n| FR-02~03 | A |\n"
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101", body))
    alone = cdc.main([spec])
    _write(tmp_path / "docs/system-layer.md", "## SPEC-202\n| FR-09 | s |\n")
    with_system = cdc.main([spec])
    assert alone == with_system == 1


def test_union_spec_inside_domain_dir_includes_other_listed_and_system(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "docs/spec/a/SPEC-101-x.md", SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-01 | A |\n"))
    _write(tmp_path / "docs/spec/b/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-02 | B |\n"))
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-03 | sys |\n")
    found = cdc.locate_domain_maps(Path("docs/spec/a/SPEC-101-x.md"), None)
    assert [p.as_posix() for p in found] == [
        "docs/spec/a/domain-map.md", "docs/spec/b/domain-map.md", "docs/system-layer.md"]
    assert cdc.main([str(tmp_path / "docs/spec/a/SPEC-101-x.md")]) == 0


def test_union_filter_loads_only_listing_maps(tmp_path, monkeypatch):
    """過濾對照：未列入本 SPEC 的 map 不載入。"""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "docs/spec/ui/SPEC-101-x.md", SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-01 | A |\n"))
    _write(tmp_path / "docs/spec/c/domain-map.md", _map("SPEC-999", "## SPEC-999\n| FR-02 | C |\n"))
    found = cdc.locate_domain_maps(Path("docs/spec/ui/SPEC-101-x.md"), None)
    assert [p.as_posix() for p in found] == ["docs/spec/a/domain-map.md"]


# --- FR 標題全形冒號 + 空集合兩種性質分流 ---

def test_extract_spec_frs_fullwidth_colon():
    assert cdc.extract_spec_frs("### FR-01：A\n#### FR-02: B\n") == {1, 2}


def _fm(value=None):
    if value is None:
        return "---\nid: SPEC-900\n---\n"
    return f"---\nid: SPEC-900\nhas_functional_requirements: {value}\n---\n"


def _run_nomap(tmp_path, spec_text, capsys, *extra):
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(spec_text, encoding="utf-8")
    rc = cdc.main([str(spec), *extra])
    return rc, capsys.readouterr().out


def _write_map(tmp_path, source_specs="SPEC-001"):
    (tmp_path / "domain-map.md").write_text(
        f"---\nsource_specs: [{source_specs}]\n---\n# 通道與協調圖\n## 到達類別與級別實例\nFR-01\n",
        encoding="utf-8")


def test_declared_false_no_fr_rc0_without_any_map(tmp_path, capsys):
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n元件契約表\n", capsys)
    assert rc == 0
    assert "宣告無 FR" in out and "未執行覆蓋比對" in out
    assert "通過" not in out


def test_declared_false_skips_event_flow_check_even_with_map(tmp_path, capsys):
    # 同目錄有 map 時，若仍跑事件流檢核會印「事件流標定檢核通過」
    _write_map(tmp_path)
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n元件契約表\n", capsys,
                         "--check-event-flow-labeling")
    assert rc == 0
    assert "通過" not in out and "事件流" not in out


def test_declared_false_with_map_not_listing_spec_rc0(tmp_path, capsys):
    _write_map(tmp_path, "SPEC-001")  # 未列入 SPEC-900
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n", capsys)
    assert rc == 0 and "宣告無 FR" in out


def test_declaration_outside_frontmatter_not_honored(tmp_path, capsys):
    body = "# s\nhas_functional_requirements: false\n"
    fenced = "# s\n```yaml\nhas_functional_requirements: false\n```\n"
    for text in (_fm() + body, _fm() + fenced, body, fenced):
        rc, _ = _run_nomap(tmp_path, text, capsys)
        assert rc != 0


def test_declared_false_but_fr_heading_contradicts(tmp_path, capsys):
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n### FR-01: A\n", capsys)
    assert rc != 0 and "矛盾" in out


def test_declared_false_loose_headings_contradict(tmp_path, capsys):
    for h in ("fr-01", "FR01", "FR 01", "FR\uff0d01", "FR\u201301"):
        rc, _ = _run_nomap(tmp_path, _fm("false") + f"# s\n## {h} x\n", capsys)
        assert rc != 0, h


def test_declared_false_nfr_heading_not_contradiction(tmp_path, capsys):
    rc, _ = _run_nomap(tmp_path, _fm("false") + "# s\n## NFR-01 x\n", capsys)
    assert rc == 0


def test_undeclared_zero_fr_fails_regardless_of_wording(tmp_path, capsys):
    for body in ("# s\n元件契約表\n", "# s\n**FR-01** 需求\n"):
        for fm in (_fm(), _fm("true")):
            rc, out = _run_nomap(tmp_path, fm + body, capsys)
            assert rc != 0
            assert "### FR-NN" in out and "has_functional_requirements: false" in out


def test_non_boolean_declaration_errors(tmp_path, capsys):
    # 本文含 FR 標題：若被當作 true 會走比對，不會出現「須為布林」訊息
    for v in ('"false"', "null", "", "no"):
        rc, out = _run_nomap(tmp_path, _fm(v) + "# s\n### FR-01: A\n", capsys)
        assert rc != 0, v
        assert "須為布林" in out, v


def test_declared_false_letter_continuation_headings_not_contradiction(tmp_path, capsys):
    for h in ("Framework", "FRAME"):
        rc, _ = _run_nomap(tmp_path, _fm("false") + f"# s\n## {h} x\n", capsys)
        assert rc == 0, h


# --- 追修：系統層不適用整份無歸屬規則 + stderr 訊號 ---

SYSTEM_PROSE = "涉及 FR-02 與 FR-03\n"


def test_system_layer_unattributed_not_counted_in_domain_dir(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101", "## SPEC-101\n| FR-01 | A |\n"),
                          system=SYSTEM_PROSE)
    assert cdc.main([spec]) == 1, capsys.readouterr().out


def test_system_layer_unattributed_not_counted_outside_domain_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", _map("SPEC-101", "## SPEC-101\n| FR-01 | A |\n"))
    _write(tmp_path / "docs/system-layer.md", SYSTEM_PROSE)
    assert cdc.main([str(spec)]) == 1, capsys.readouterr().out


def test_default_attribution_signal_on_stderr(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101", "| FR-01~03 | A |\n"))
    assert cdc.main([spec]) == 0
    err = capsys.readouterr().err
    assert "domain-map.md" in err and "無任何 SPEC 歸屬" in err


def test_no_signal_when_explicitly_attributed(tmp_path, monkeypatch, capsys):
    spec = _in_domain_dir(tmp_path, monkeypatch, _map("SPEC-101", "## SPEC-101\n| FR-01~03 | A |\n"))
    assert cdc.main([spec]) == 0
    assert "無任何 SPEC 歸屬" not in capsys.readouterr().err


# --- 層級 SPEC 以系統層判定（層級模式的判定）---

LAYER_SPEC = ("---\nid: SPEC-101\ndomain: \"ui\"\n---\n"
              "### FR-01: A\n### FR-02: B\n")


def _layer_fixture(tmp_path, spec_domain="ui", system="## SPEC-101\n| FR-01~02 | sys |\n"):
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, LAYER_SPEC.replace('"ui"', f'"{spec_domain}"'))
    _write(tmp_path / "docs/spec/a/domain-map.md", "---\ndomain: \"a\"\nsource_specs: [SPEC-999]\n---\n")
    if system is not None:
        _write(tmp_path / "docs/system-layer.md", system)
    return spec


def test_layer_spec_judged_by_system_layer_without_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    assert cdc.main([str(spec)]) == 0
    assert "docs/system-layer.md" in capsys.readouterr().out


def test_layer_spec_e1_declared_domain_keeps_source_specs_message(tmp_path, monkeypatch, capsys):
    """E1 對照：domain 欄改為已宣告的 a 且無 map 列入 -> 維持請補 source_specs。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="a")
    assert cdc.main([str(spec)]) == 1
    assert "source_specs" in capsys.readouterr().out


def test_spec_without_domain_field_unchanged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    spec.write_text("---\nid: SPEC-101\n---\n### FR-01: A\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 1
    assert "source_specs" in capsys.readouterr().out


def test_layer_spec_system_layer_missing_fr_points_to_system_layer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="## 其他\n無對照\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "FR-01" in out and LAYER_TAIL in out and "domain map §7" not in out


def test_layer_spec_without_system_layer_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system=None)
    assert cdc.main([str(spec)]) == 1
    assert "系統層" in capsys.readouterr().out


def test_single_domain_project_domain_field_not_layer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/SPEC-101-x.md"
    _write(spec, LAYER_SPEC)
    _write(tmp_path / "docs/domain-map.md", "## 覆蓋\n| FR-01~02 | X |\n")
    assert cdc.main([str(spec)]) == 0
    assert "docs/domain-map.md" in capsys.readouterr().out


# --- 層級判定優先序：原定位鏈有 map 時照原鏈（R1/R2/R3）---

def _listing_map(tmp_path, body):
    _write(tmp_path / "docs/spec/a/domain-map.md",
           f"---\ndomain: \"a\"\nsource_specs: [SPEC-101]\n---\n## SPEC-101\n{body}")


def test_r1_map_listing_spec_wins_over_layer_red_to_green(tmp_path, monkeypatch, capsys):
    """有 map 列入且覆蓋，系統層無對照：舊版因 domain 欄非已宣告而走系統層為紅，新版照原鏈為綠。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="## 其他\n無對照\n")
    _listing_map(tmp_path, "| FR-01~02 | A |\n")
    assert cdc.main([str(spec)]) == 0


def test_r1_map_listing_uncovered_fr_is_red_without_system_layer_attribution(tmp_path, monkeypatch, capsys):
    """有 map 列入但未覆蓋 FR-02，系統層只有無歸屬的 FR 文字：照原鏈判定為紅（系統層無 SPEC 歸屬的 FR 不計入）。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="| FR-01~02 | sys |\n")
    _listing_map(tmp_path, "| FR-01 | A |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    # 判定優先序守護：有 map 列入時不得走層級判定（層級判定優先時，此處改印層級橫幅與系統層標題）
    assert "FR-02" in out and "層級 SPEC" not in out and "未在 domain map 覆蓋" in out


def test_no_map_anywhere_with_domain_field_reports_no_map_not_layer(tmp_path, monkeypatch, capsys):
    """已宣告集合條件守護：專案完全無 map（宣告集合為空）時，domain 欄不是層級依據，
    即使系統層完整覆蓋仍報找不到任何 domain map。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, LAYER_SPEC)
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-01~02 | sys |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "找不到任何 domain map" in out and "層級 SPEC" not in out


@pytest.mark.parametrize("raw", ["[a, b]", "[a,b]", "[ui]", "a b", "'my domain'", "a,b"])
def test_domain_field_not_single_name_is_format_error(tmp_path, monkeypatch, capsys, raw):
    """domain 欄含方括號、逗號或空白：格式錯誤 rc=1，印出實際值，不走層級判定。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    spec.write_text(LAYER_SPEC.replace('"ui"', raw), encoding="utf-8")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert raw in out and "單一 domain 名稱" in out and "層級 SPEC" not in out


@pytest.mark.parametrize("raw", ["~", "null", "Null"])
def test_domain_field_tilde_or_null_treated_as_unset(tmp_path, monkeypatch, capsys, raw):
    """波浪號與 null 視同未填：不走層級判定（無 map 列入時報請補 source_specs）。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    spec.write_text(LAYER_SPEC.replace('"ui"', raw), encoding="utf-8")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "層級 SPEC" not in out and "單一 domain 名稱" not in out and "source_specs" in out


def test_domain_field_misspelled_single_name_still_layer(tmp_path, monkeypatch, capsys):
    """對照：拼錯的單一名稱維持現行，走層級判定並印橫幅。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="corpuss")
    assert cdc.main([str(spec)]) == 0
    assert "層級 SPEC" in capsys.readouterr().out


def test_domain_field_with_trailing_comment_is_plain_name(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    spec.write_text(LAYER_SPEC.replace('"ui"', "ui  # 層級"), encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "'ui'" in capsys.readouterr().out


def test_system_layer_directory_with_listing_map_reports_error(tmp_path, monkeypatch, capsys):
    """非層級路徑：map 列入本 SPEC 時系統層是聯集成員；系統層為目錄須報錯非 0，不得靜默略過。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system=None)
    (tmp_path / "docs/system-layer.md").mkdir()
    _listing_map(tmp_path, "| FR-01~02 | A |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "是目錄" in out and "通過" not in out


def test_directory_as_spec_path_reports_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "somedir").mkdir()
    assert cdc.main(["somedir"]) == 1
    assert "是目錄" in capsys.readouterr().out


def test_directory_error_message_separates_flag_name(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-101-x.md"
    _write(spec, LAYER_SPEC)
    (tmp_path / "mapdir").mkdir()
    cdc.main([str(spec), "--domain-map", "mapdir"])
    assert "--domain-map 是目錄" in capsys.readouterr().out


def test_directory_as_domain_map_reports_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-101-x.md"
    _write(spec, LAYER_SPEC)
    (tmp_path / "mapdir").mkdir()
    assert cdc.main([str(spec), "--domain-map", "mapdir"]) == 1
    assert "是目錄" in capsys.readouterr().out


def test_directory_as_system_layer_reports_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system=None)
    (tmp_path / "docs/system-layer.md").mkdir()
    assert cdc.main([str(spec)]) == 1
    assert "是目錄" in capsys.readouterr().out


def test_r1_no_map_declared_domain_is_red_not_system_layer(tmp_path, monkeypatch, capsys):
    """無 map 且 domain 欄為已宣告：系統層即使完整覆蓋仍為紅（漏登記），舊版同為紅（對照守住不退化）。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="a")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "source_specs" in out and "層級 SPEC" not in out


def test_r2_system_layer_output_shows_domain_and_declared_set(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="corpuss")
    assert cdc.main([str(spec)]) == 0
    out = capsys.readouterr().out
    assert "'corpuss'" in out and "[a]" in out


def test_r3_flag_to_system_layer_for_declared_domain_spec_uses_plain_message(tmp_path, monkeypatch, capsys):
    """已宣告 domain 的 SPEC 帶旗標指向系統層、FR 未覆蓋：訊息不得稱層級 SPEC。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="a", system="## 其他\n無對照\n")
    assert cdc.main([str(spec), "--domain-map", "docs/system-layer.md"]) == 1
    out = capsys.readouterr().out
    assert "FR-01" in out and "層級 SPEC" not in out and MAP_TAIL in out


# --- 第二輪補修：層級模式不走相容後備、旗標判 None ---

def test_m1_layer_mode_prose_only_system_layer_is_red(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="散文提到 FR-01~02 但沒有任何 SPEC 歸屬。\n")
    assert cdc.main([str(spec)]) == 1
    assert "FR-01" in capsys.readouterr().out


def test_m1_layer_mode_without_spec_id_is_red(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    spec.write_text('---\nid: SPEC-UI-1\ndomain: "ui"\n---\n### FR-01: A\n', encoding="utf-8")
    assert cdc.main([str(spec)]) == 1


def test_m2_layer_spec_with_missing_flag_file_reports_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    assert cdc.main([str(spec), "--domain-map", "nope.md"]) == 1
    out = capsys.readouterr().out
    assert "指定的檔案不存在" in out and "層級" not in out


def test_m3_empty_domain_map_flag_is_red_not_unflagged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path)
    assert cdc.main([str(spec), "--domain-map", ""]) == 1
    out = capsys.readouterr().out
    assert "指定的檔案不存在" in out and "層級" not in out


# --- 定位失敗訊息依成因輸出 ---

def _spec_and_map(tmp_path, monkeypatch, map_frontmatter, spec_text=SPEC_A, spec_name="SPEC-101-x.md"):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui" / spec_name
    _write(spec, spec_text)
    _write(tmp_path / "docs/spec/a/domain-map.md",
           f"---\n{map_frontmatter}\n---\n## SPEC-101\n| FR-01~03 | A |\n")
    return spec


def test_block_list_source_specs_resolves(tmp_path, monkeypatch, capsys):
    """紅輸入：YAML 區塊清單寫法的 source_specs 過去讀成空集合。"""
    spec = _spec_and_map(tmp_path, monkeypatch, "source_specs:\n  - SPEC-101\n  - SPEC-202")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_block_list_not_listing_this_spec_reports_not_listed(tmp_path, monkeypatch, capsys):
    """對照：區塊清單可解析但未含本 SPEC，仍為「未列入」。"""
    spec = _spec_and_map(tmp_path, monkeypatch, "source_specs:\n  - SPEC-202")
    assert cdc.main([str(spec)]) == 1
    assert "無一份的 source_specs 列入本 SPEC" in capsys.readouterr().out


def test_unparseable_source_specs_reports_format_problem(tmp_path, monkeypatch, capsys):
    spec = _spec_and_map(tmp_path, monkeypatch, "source_specs: SPEC-101")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "source_specs 格式無法解析" in out and "docs/spec/a/domain-map.md" in out
    assert "補上本 SPEC id" not in out


def test_unrecognized_spec_id_reports_id_problem(tmp_path, monkeypatch, capsys):
    spec = _spec_and_map(tmp_path, monkeypatch, "source_specs: [SPEC-101]",
                         spec_text="---\nid: SPEC-UI-001\n---\n### FR-01: a\n", spec_name="ui-spec.md")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "spec id 無法辨識" in out
    assert "補上本 SPEC id" not in out


def test_locate_domain_map_compat_entry_removed():
    assert not hasattr(cdc, "locate_domain_map")


# --- 層級模式訊息不稱 domain map（併入項）---

def test_layer_mode_coverage_title_says_system_layer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="## 其他\n無對照\n")
    assert cdc.main([str(spec)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "domain 覆蓋檢核發現 2 個 FR 未在系統層覆蓋：" in lines


def test_non_layer_coverage_title_unchanged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: A\n### FR-02: B\n", encoding="utf-8")
    (tmp_path / "domain-map.md").write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "domain 覆蓋檢核發現 1 個 FR 未在 domain map 覆蓋：" in lines


EVENT_TAIL = "請於「通道與協調圖」節之「到達類別與級別實例」子表補上標定。"


def test_layer_mode_event_flow_tail_says_system_layer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="## SPEC-101\n| FR-01~02 | sys |\n")
    spec.write_text(LAYER_SPEC.replace("### FR-01: A", "### FR-01: 掃描完成通知\n發送通知。"),
                    encoding="utf-8")
    cdc.main([str(spec), "--check-event-flow-labeling"])
    lines = capsys.readouterr().out.splitlines()
    assert f"（系統層：{cdc.SYSTEM_LAYER_PATH}）{EVENT_TAIL}" in lines


def test_non_layer_event_flow_tail_unchanged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-001.md"
    spec.write_text("### FR-01: 掃描完成通知\n發送通知。\n", encoding="utf-8")
    (tmp_path / "domain-map.md").write_text("| FR-01 | Ledger |\n", encoding="utf-8")
    cdc.main([str(spec), "--check-event-flow-labeling"])
    lines = capsys.readouterr().out.splitlines()
    map_path = (tmp_path / "domain-map.md").resolve()
    assert f"（domain map：{map_path}）{EVENT_TAIL}" in lines


# --- source_specs 解析的修正與變異守衛（審查 R1-R5）---

MSG_NOT_LISTED = ("domain 覆蓋檢核：有 domain map（docs/spec/*/domain-map.md），但無一份的 source_specs 列入本 SPEC。"
                  "請於對應 domain map frontmatter 的 source_specs 補上本 SPEC id，或以 --domain-map 指定。")
MSG_ID_UNRECOGNIZED = ("domain 覆蓋檢核：spec id 無法辨識（frontmatter id 與檔名皆取不到 SPEC-NNN 形式），"
                       "無法比對 domain map 的 source_specs。請修正 spec 的 id 為 SPEC-NNN 形式，或以 --domain-map 指定。")
MSG_UNPARSEABLE = ("domain 覆蓋檢核：下列 domain map 的 source_specs 格式無法解析：docs/spec/a/domain-map.md。"
                   "接受行內清單 `[SPEC-001, SPEC-002]` 或逐行 `- SPEC-001` 的區塊清單；"
                   "請改成可解析的寫法，或以 --domain-map 指定。")


def _run_ss(tmp_path, monkeypatch, capsys, frontmatter, **kw):
    spec = _spec_and_map(tmp_path, monkeypatch, frontmatter, **kw)
    rc = cdc.main([str(spec)])
    return rc, capsys.readouterr().out.splitlines()


def test_r1_block_item_trailing_comment_not_a_member(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n  - SPEC-202 # not SPEC-101")
    assert rc == 1 and MSG_NOT_LISTED in lines


def test_r2_key_line_comment_then_block_list(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: # list below\n  - SPEC-101")
    assert rc == 0


@pytest.mark.parametrize("fm", [
    "source_specs:\n  - SPEC-202\n\n  - SPEC-101",
    "source_specs:\n  - SPEC-202\n  # note\n  - SPEC-101",
    "source_specs:\n  # note\n  - SPEC-101",
    "source_specs:\n\n  - SPEC-101",
])
def test_r3_blank_and_comment_lines_do_not_truncate_block(tmp_path, monkeypatch, capsys, fm):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, fm)
    assert rc == 0


@pytest.mark.parametrize("fm", ["source_specs:\n[SPEC-101]", "source_specs:\n  [SPEC-101, SPEC-202]"])
def test_r4_flow_list_on_line_after_key(tmp_path, monkeypatch, capsys, fm):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, fm)
    assert rc == 0


def test_inline_list_missing_close_bracket_unparseable(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: [SPEC-101")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_inline_list_trailing_comment_parses(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: [SPEC-101] # note")
    assert rc == 0


@pytest.mark.parametrize("fm", ["source_specs: [spec-101]", "source_specs:\n  - spec-101"])
def test_lowercase_ids_treated_as_uppercase(tmp_path, monkeypatch, capsys, fm):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, fm)
    assert rc == 0


def test_key_without_items_is_unparseable_not_empty_set(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_block_list_does_not_absorb_following_key_list(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys,
                        "source_specs:\n  - SPEC-202\nother_specs:\n  - SPEC-101")
    assert rc == 1 and MSG_NOT_LISTED in lines


def test_undeclared_key_keeps_not_listed_message(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "domain: a")
    assert rc == 1 and MSG_NOT_LISTED in lines


def test_map_without_frontmatter_keeps_not_listed_message(tmp_path, monkeypatch, capsys):
    spec = _spec_and_map(tmp_path, monkeypatch, "domain: a")
    _write(tmp_path / "docs/spec/a/domain-map.md", "## SPEC-101\n| FR-01~03 | A |\n")
    assert cdc.main([str(spec)]) == 1
    assert MSG_NOT_LISTED in capsys.readouterr().out.splitlines()


def test_id_problem_reported_before_unparseable_map(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: SPEC-101",
                        spec_text="---\nid: SPEC-UI-001\n---\n### FR-01: a\n", spec_name="ui-spec.md")
    assert rc == 1 and MSG_ID_UNRECOGNIZED in lines and MSG_UNPARSEABLE not in lines


# --- source_specs 下一行 flow 清單與井號邊界（各邊界附相鄰對照輸入）---

def test_b1_flow_list_after_blank_and_comment_lines_accepted(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n\n# note\n[SPEC-101]")
    assert rc == 0


def test_b1_contrast_flow_list_after_blank_and_comment_is_read_not_defaulted(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n\n# note\n[SPEC-202]")
    assert rc == 1 and MSG_NOT_LISTED in lines


def test_b2_close_bracket_followed_by_hash_without_space_unparseable(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: [SPEC-101]# note")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_b2_contrast_close_bracket_followed_by_spaced_hash_accepted(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: [SPEC-101] # note")
    assert rc == 0


def test_b3_scalar_on_key_line_not_overridden_by_next_line_flow_list(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs: SPEC-202\n[SPEC-101]")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_b3_contrast_empty_key_line_takes_next_line_flow_list(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n[SPEC-101]")
    assert rc == 0


def test_b4_next_line_flow_list_with_trailing_comment_accepted(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n[SPEC-101] # note")
    assert rc == 0


def test_b4_contrast_next_line_flow_list_hash_without_space_unparseable(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\n[SPEC-101]# note")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_b5_flow_list_after_another_key_not_taken_as_this_keys_list(tmp_path, monkeypatch, capsys):
    rc, lines = _run_ss(tmp_path, monkeypatch, capsys, "source_specs:\nother: x\n[SPEC-101]")
    assert rc == 1 and MSG_UNPARSEABLE in lines


def test_b5_contrast_other_key_before_source_specs_does_not_matter(tmp_path, monkeypatch, capsys):
    rc, _ = _run_ss(tmp_path, monkeypatch, capsys, "other: x\nsource_specs:\n[SPEC-101]")
    assert rc == 0


# --- FR 抽取完整性（部分漏抓警告 / 略過圍欄 / 全形冒號端到端）---

def _map_covering(tmp_path, frs="FR-01,02"):
    (tmp_path / "domain-map.md").write_text(
        f"---\nsource_specs: [SPEC-900]\n---\n# SPEC-900\n{frs}\n", encoding="utf-8")


@pytest.mark.parametrize("missed", ["### FR-02 b", "**FR-02** b", "## FR-02: b"])
def test_partial_miss_warns_with_number(tmp_path, monkeypatch, capsys, missed):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path)
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + f"### FR-01: a\n{missed}\n", encoding="utf-8")
    rc = cdc.main([str(spec)])
    err = capsys.readouterr().err
    assert rc == 0  # 預設僅警告
    assert "WARNING" in err and "FR-02" in err


def test_partial_miss_no_false_positive_on_nfr_and_prefixed_ref(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(
        _fm() + "### FR-01: a\n### NFR-07: n\n**NFR-08** n\n**SPEC-001 FR-09** 引用\n## SPEC-002 FR-08 引用\n",
        encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "WARNING" not in capsys.readouterr().err


def test_fenced_block_fr_heading_not_extracted():
    spec = "### FR-01: a\n```\n### FR-02: 範例\n```\n~~~md\n### FR-03: 範例\n~~~\n### FR-04: b\n"
    assert cdc.extract_spec_frs(spec) == {1, 4}


def test_fullwidth_colon_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + "### FR-01：全形\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "通過" in capsys.readouterr().out


def test_fenced_like_line_no_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + "### FR-01: a\n```\n## FR-05 範例\n**FR-06** 範例\n```\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "未被抽出" not in capsys.readouterr().err  # 漏抓警告不出現；略過區段提醒另計


def test_unclosed_fence_fails_with_line_number(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01,02,03")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + "### FR-01: a\n```\n### FR-02: b\n### FR-03: c\n", encoding="utf-8")
    rc = cdc.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1 and "未閉合" in out and "第 5 行" in out
    assert "通過" not in out


def test_inline_triple_backtick_line_is_not_fence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01,02,03")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + "### FR-01: a\n```inline``` 說明\n### FR-02: b\n### FR-03: c\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "通過" in capsys.readouterr().out


def test_fence_close_needs_length_and_no_trailing_text():
    spec = "### FR-01: a\n````\n```\n### FR-02: x\n```x\n### FR-03: y\n````\n### FR-04: b\n"
    assert cdc.extract_spec_frs(spec) == {1, 4}


def test_inline_triple_backtick_extracts_all():
    assert cdc.extract_spec_frs("### FR-01: a\n```inline``` 說明\n### FR-02: b\n") == {1, 2}


# --- 宣告讀取（重複鍵 / 多行字串續行）與宣告矛盾比對（漏放 / 誤判 / 共用判定）---

def _fm_raw(*lines):
    return "---\nid: SPEC-900\n" + "".join(f"{ln}\n" for ln in lines) + "---\n"


def test_duplicate_declaration_key_errors(tmp_path, capsys):
    for first, second in (("false", "true"), ("true", "false"), ("false", "false")):
        fm = _fm_raw(f"has_functional_requirements: {first}", f"has_functional_requirements: {second}")
        rc, out = _run_nomap(tmp_path, fm + "# s\n", capsys)
        assert rc != 0, (first, second)
        assert "重複" in out and "宣告無 FR" not in out


def test_declaration_key_inside_multiline_string_not_counted(tmp_path, capsys):
    fm = _fm_raw('note: "第一行', "has_functional_requirements: false", '收尾"')
    rc, out = _run_nomap(tmp_path, fm + "# s\n元件契約表\n", capsys)
    assert rc != 0 and "本 SPEC 宣告無 FR" not in out  # 未宣告且抽出 0 個


def test_single_quoted_multiline_string_not_counted(tmp_path, capsys):
    fm = _fm_raw("note: 'it''s", "has_functional_requirements: false", "end'")
    rc, out = _run_nomap(tmp_path, fm + "# s\n", capsys)
    assert rc != 0 and "本 SPEC 宣告無 FR" not in out


def test_declaration_after_closed_quote_still_read(tmp_path, capsys):
    fm = _fm_raw('note: "單行"', "has_functional_requirements: false")
    rc, out = _run_nomap(tmp_path, fm + "# s\n", capsys)
    assert rc == 0 and "宣告無 FR" in out


def test_invalid_value_message_lists_legal_forms(tmp_path, capsys):
    rc, out = _run_nomap(tmp_path, _fm("True") + "# s\n", capsys)
    assert rc != 0 and "true" in out and "false" in out and "'True'" in out


MISSED_CONTRADICTIONS = [
    "## **FR-01** x", "## 3.1 FR-01 x", "## 需求 FR-01 x", "## [FR-01] x", "## `FR-01` x",
    "## ＦＲ-01 x", "## ＦＲ－０１ x", "  ## FR-01 x", "**FR-01** x", "FR-01 x\n=====", "FR-01 x\n-----",
    "## _FR-01_ x",
]


@pytest.mark.parametrize("heading", MISSED_CONTRADICTIONS)
def test_declared_false_previously_missed_heading_contradicts(tmp_path, capsys, heading):
    rc, out = _run_nomap(tmp_path, _fm("false") + f"# s\n{heading}\n", capsys)
    assert rc != 0 and "矛盾" in out


FALSE_CONTRADICTIONS = [
    "## FR", "## FR 與 NFR 的界線", "## FR/NFR 不適用說明", "## FR：不適用", "## Fr. 縮寫",
    "#FR-01 x", "```\n## FR-01: x\n```", "~~~\n**FR-01** x\n~~~",
    "<!--\n## FR-01: x\n-->", "<!-- ## FR-01 x -->", "前文 <!-- a -->\n<!--\nFR-02 x\n=====\n-->",
    "- 見 FR-01 的說明", "| FR-01 | 引用 |", "    ## FR-01 縮排程式碼",
]


@pytest.mark.parametrize("body", FALSE_CONTRADICTIONS)
def test_declared_false_non_definition_fr_text_not_contradiction(tmp_path, capsys, body):
    rc, out = _run_nomap(tmp_path, _fm("false") + f"# s\n{body}\n", capsys)
    assert rc == 0 and "宣告無 FR" in out


def test_contradiction_reports_line_numbers_after_masking(tmp_path, capsys):
    text = _fm("false") + "# s\n```\nx\n```\n## 需求 FR-01 x\n"
    rc, out = _run_nomap(tmp_path, text, capsys)
    assert rc != 0 and "第 9 行" in out


def test_unclosed_fence_still_precedes_declaration(tmp_path, capsys):
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n```\n元件\n", capsys)
    assert rc == 1 and "未閉合" in out and "宣告無 FR" not in out


def test_fr_header_in_html_comment_not_extracted():
    assert cdc.extract_spec_frs("### FR-01: a\n<!--\n### FR-02: b\n-->\n### FR-03: c\n") == {1, 3}


SHARED_CORPUS = MISSED_CONTRADICTIONS + [
    "## FR-01: a", "### FR-02 b", "**FR-03** c", "## NFR-01 x", "**SPEC-001 FR-09** 引用",
    "## FR：不適用", "#FR-01 x",
]


@pytest.mark.parametrize("line", SHARED_CORPUS)
def test_extraction_warning_and_contradiction_agree(tmp_path, capsys, line):
    text = f"# s\n{line}\n"
    warned = bool(cdc.fr_like_lines(text))
    rc, _ = _run_nomap(tmp_path, _fm("false") + text, capsys)
    assert (rc != 0) == warned


def test_both_consumers_use_shared_fr_like_judgment(tmp_path, capsys, monkeypatch):
    # 只改共用判定的一端：兩個消費端都必須跟著變，任一端自帶規則則此測試翻紅
    # 兩個消費端分居不同模組（find_unextracted_fr_lines 在 fr_extract、judge_fr_declaration 在入口檔），
    # 各自以模組全域名稱解析 fr_like_lines，故兩處都換成同一個哨兵
    monkeypatch.setattr(fr_extract, "fr_like_lines", lambda text: [(3, "SENTINEL-LINE", 7)])
    monkeypatch.setattr(cdc, "fr_like_lines", lambda text: [(3, "SENTINEL-LINE", 7)])
    assert cdc.find_unextracted_fr_lines("# s\n元件\n") == [(3, "SENTINEL-LINE")]
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\n元件\n", capsys)
    assert rc != 0 and "SENTINEL-LINE" in out


# --- 審查必修：註解遮蔽的行內程式碼邊界 / 略過區段提醒 / 誤判方向守護 ---

CODE_SPAN_OPEN = "說明 `<!--` 是註解開頭\n"


def test_inline_code_comment_opener_does_not_swallow_headings():
    spec = "### FR-01: a\n" + CODE_SPAN_OPEN + "### FR-02: b\n結尾寫作 `-->` 即可\n### FR-03: c\n"
    assert cdc.extract_spec_frs(spec) == {1, 2, 3}


def test_inline_code_opener_with_real_comment_later_does_not_swallow():
    spec = "### FR-01: a\n" + CODE_SPAN_OPEN + "### FR-02: b\n<!-- 真註解 -->\n### FR-03: c\n"
    assert cdc.extract_spec_frs(spec) == {1, 2, 3}


def test_real_comment_still_masked_after_inline_code():
    spec = "### FR-01: a\n`x` <!--\n### FR-02: b\n-->\n### FR-03: c\n"
    assert cdc.extract_spec_frs(spec) == {1, 3}


def _skipped_warnings(tmp_path, monkeypatch, capsys, body):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm() + body, encoding="utf-8")
    rc = cdc.main([str(spec)])
    return rc, capsys.readouterr().err


def test_masked_region_fr_lines_warn_with_line_numbers(tmp_path, monkeypatch, capsys):
    body = "### FR-01: a\n```\n### FR-02: 範例\n```\n<!--\n**FR-03** 註解掉\n-->\n"
    rc, err = _skipped_warnings(tmp_path, monkeypatch, capsys, body)
    assert rc == 0  # 不改 exit code
    assert err.count("略過的區段") == 2
    assert "第 6 行" in err and "第 9 行" in err
    assert "未被抽出" not in err


def test_masked_region_warning_absent_when_nothing_hidden(tmp_path, monkeypatch, capsys):
    rc, err = _skipped_warnings(tmp_path, monkeypatch, capsys, "### FR-01: a <!-- 註 -->\n```\n普通\n```\n")
    assert rc == 0 and "略過的區段" not in err


def test_masked_region_warning_skips_frontmatter(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _map_covering(tmp_path, "FR-01")
    spec = tmp_path / "SPEC-900-x.md"
    spec.write_text(_fm_raw("# FR-02 備註") + "### FR-01: a\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0
    assert "略過的區段" not in capsys.readouterr().err


def test_declared_false_frontmatter_fr_like_comment_not_contradiction(tmp_path, capsys):
    fm = _fm_raw("# FR-01 暫不適用", "has_functional_requirements: false")
    rc, out = _run_nomap(tmp_path, fm + "# s\n", capsys)
    assert rc == 0 and "本 SPEC 宣告無 FR" in out


def test_declared_false_paragraph_without_underline_not_contradiction(tmp_path, capsys):
    rc, out = _run_nomap(tmp_path, _fm("false") + "# s\nFR-01 見他處說明\n接續的段落\n", capsys)
    assert rc == 0 and "本 SPEC 宣告無 FR" in out


def test_declared_false_inline_comment_before_heading_not_contradiction(tmp_path, capsys):
    rc, _ = _run_nomap(tmp_path, _fm("false") + "# s\n<!-- c --> ## FR-01 x\n", capsys)
    assert rc == 0


def test_declared_false_heading_after_comment_line_contradicts(tmp_path, capsys):
    rc, _ = _run_nomap(tmp_path, _fm("false") + "# s\n<!-- c -->\n## FR-01 x\n", capsys)
    assert rc != 0


# --- domain 欄格式檢查的適用範圍：只在 domain 欄會被消費處（定位鏈為空且未帶旗標）---

BAD_DOMAIN_RAWS = ["[a, b]", "a b"]


@pytest.mark.parametrize("raw", BAD_DOMAIN_RAWS)
def test_bad_domain_field_ignored_when_same_dir_map_covers(tmp_path, monkeypatch, capsys, raw):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-101-x.md"
    _write(spec, LAYER_SPEC.replace('"ui"', raw))
    _write(tmp_path / "domain-map.md", "---\nsource_specs: [SPEC-101]\n---\n## SPEC-101\n| FR-01~02 | A |\n")
    assert cdc.main([str(spec)]) == 0


@pytest.mark.parametrize("raw", BAD_DOMAIN_RAWS)
def test_bad_domain_field_ignored_with_explicit_domain_map(tmp_path, monkeypatch, capsys, raw):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-101-x.md"
    _write(spec, LAYER_SPEC.replace('"ui"', raw))
    _write(tmp_path / "m.md", "## SPEC-101\n| FR-01~02 | A |\n")
    assert cdc.main([str(spec), "--domain-map", "m.md"]) == 0


@pytest.mark.parametrize("raw", BAD_DOMAIN_RAWS)
def test_bad_domain_field_ignored_when_declared_no_fr(tmp_path, monkeypatch, capsys, raw):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "SPEC-101-x.md"
    _write(spec, f"---\nid: SPEC-101\ndomain: {raw}\nhas_functional_requirements: false\n---\n# s\n")
    assert cdc.main([str(spec)]) == 0


# --- 引號與井號殘留：去掉瑕疵後是已宣告 domain 的值不得改走系統層通過 ---

@pytest.mark.parametrize("raw", ["\"a", "a#b", "\"a#b\"", "'a"])
def test_malformed_quote_or_hash_domain_is_format_error_not_layer(tmp_path, monkeypatch, capsys, raw):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, spec_domain="a", system="## SPEC-101\n| FR-01~02 | sys |\n")
    spec.write_text(LAYER_SPEC.replace('"ui"', raw), encoding="utf-8")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "通過" not in out and "單一 domain 名稱" in out


# --- map 端的 domain 欄維持舊讀法（本票的讀取修改只作用於 SPEC 端）---

def _map_domain_fixture(tmp_path, map_domain, spec_domain):
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, LAYER_SPEC.replace('"ui"', spec_domain))
    _write(tmp_path / "docs/spec/a/domain-map.md", f"---\ndomain: {map_domain}\nsource_specs: [SPEC-999]\n---\n")
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-01~02 | sys |\n")
    return spec


def test_map_domain_left_quote_only_reads_as_bare_name(tmp_path, monkeypatch, capsys):
    """map 的 domain 欄只有左引號：維持舊讀法（去掉引號），SPEC 的同名 domain 是已宣告而非層級，請補 source_specs。"""
    monkeypatch.chdir(tmp_path)
    spec = _map_domain_fixture(tmp_path, '"a', "a")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "source_specs" in out and "層級 SPEC" not in out


def test_map_domain_tilde_keeps_declared_set_nonempty(tmp_path, monkeypatch, capsys):
    """唯一的 map 的 domain 欄為波浪號：舊讀法視為名稱 ~，已宣告集合非空，SPEC 仍走層級判定。"""
    monkeypatch.chdir(tmp_path)
    spec = _map_domain_fixture(tmp_path, "~", "ui")
    assert cdc.main([str(spec)]) == 0
    assert "層級 SPEC" in capsys.readouterr().out


# --- source_specs 格式無法解析的 map：有其他路徑接手時也列出檔名（stderr 提醒，不改 exit code） ---

def _unparseable_fixture(tmp_path, monkeypatch, b_source_specs="SPEC-101", spec_domain="ui", layer=False):
    """spec 在 docs/spec/ui；a 為合法 map；b 的 source_specs 預設為純量（格式無法解析）。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, f"---\nid: SPEC-101\ndomain: \"{spec_domain}\"\n---\n### FR-01: A\n### FR-02: B\n")
    a_listing = "[SPEC-999]" if layer else "[SPEC-101]"
    _write(tmp_path / "docs/spec/a/domain-map.md",
           f"---\ndomain: \"a\"\nsource_specs: {a_listing}\n---\n## SPEC-101\n| FR-01 | A |\n")
    _write(tmp_path / "docs/spec/b/domain-map.md",
           f"---\ndomain: \"b\"\nsource_specs: {b_source_specs}\n---\n## SPEC-101\n| FR-02 | B |\n")
    if layer:
        _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-01~02 | sys |\n")
    return spec


B_PATH = "docs/spec/b/domain-map.md"


def test_unparseable_map_listed_when_another_map_lists_spec(tmp_path, monkeypatch, capsys):
    spec = _unparseable_fixture(tmp_path, monkeypatch)
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 1  # FR-02 只在 b，a 未覆蓋；b 被拒讀不改變 rc
    assert B_PATH in cap.err and "格式無法解析" in cap.err


def test_unparseable_map_e1_valid_syntax_emits_nothing(tmp_path, monkeypatch, capsys):
    """E1 對照：同 fixture 把 b 改為合法寫法（列入本 SPEC），stderr 不含格式無法解析提醒。"""
    spec = _unparseable_fixture(tmp_path, monkeypatch, b_source_specs="[SPEC-101]")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 0
    assert "格式無法解析" not in cap.err


def test_unrelated_unparseable_map_is_listed_too(tmp_path, monkeypatch, capsys):
    """格式無法解析的 map 讀不出是否與本 SPEC 有關，一律列出（寧多勿漏）。"""
    spec = _unparseable_fixture(tmp_path, monkeypatch, b_source_specs="SPEC-999")
    cdc.main([str(spec)])
    assert B_PATH in capsys.readouterr().err


def test_unparseable_map_listed_in_layer_mode_and_banner_not_claim_none(tmp_path, monkeypatch, capsys):
    spec = _unparseable_fixture(tmp_path, monkeypatch, layer=True)
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 0
    assert B_PATH in cap.err and "格式無法解析" in cap.err
    assert "無任何 map 列入" not in cap.out
    assert "層級 SPEC" in cap.out


def test_layer_mode_e1_valid_syntax_keeps_banner_and_silent(tmp_path, monkeypatch, capsys):
    """E1 對照：b 改合法寫法（列他人）後橫幅維持原字樣，stderr 無提醒。"""
    spec = _unparseable_fixture(tmp_path, monkeypatch, b_source_specs="[SPEC-999]", layer=True)
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 0
    assert "無任何 map 列入" in cap.out
    assert "格式無法解析" not in cap.err


# --- 層級 SPEC 的 id 無法辨識：與非層級路徑共用同一句成因訊息 ---

def _layer_id_fixture(tmp_path, monkeypatch, spec_id):
    """兩則測試的 fixture 除 id 外完全相同；系統層只歸屬 FR-01，FR-02 未覆蓋。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, f"---\nid: {spec_id}\ndomain: \"ui\"\n---\n### FR-01: A\n### FR-02: B\n")
    _write(tmp_path / "docs/spec/a/domain-map.md", "---\ndomain: \"a\"\nsource_specs: [SPEC-999]\n---\n")
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-01 | sys |\n")
    return spec


def test_layer_spec_unrecognized_id_reports_id_cause(tmp_path, monkeypatch, capsys):
    spec = _layer_id_fixture(tmp_path, monkeypatch, "SPEC-UI-101")
    rc = cdc.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1
    assert out.splitlines()[-1] == (
        "domain 覆蓋檢核：spec id 無法辨識（frontmatter id 與檔名皆取不到 SPEC-NNN 形式），"
        "無法比對系統層的 SPEC 歸屬。請修正 spec 的 id 為 SPEC-NNN 形式。")
    assert cdc.ID_UNRECOGNIZED_CAUSE in cdc.describe_missing_map(cdc.REASON_ID_UNRECOGNIZED)  # 成因子句共用
    assert "--domain-map" not in out  # 層級模式不走相容比對，不得引導使用者帶旗標
    assert "未在系統層覆蓋" not in out and "FR-01" not in out and "FR-02" not in out


def test_layer_spec_e1_recognized_id_keeps_system_layer_message(tmp_path, monkeypatch, capsys):
    """E1 對照：同 fixture 把 id 改為 SPEC-101，回到以系統層歸屬判定的既有訊息。"""
    spec = _layer_id_fixture(tmp_path, monkeypatch, "SPEC-101")
    rc = cdc.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "1 個 FR 未在系統層覆蓋" in out and "FR-02" in out
    assert "spec id 無法辨識" not in out


def test_unrecognized_id_no_map_lists_unparseable_map(tmp_path, monkeypatch, capsys):
    """範圍外缺口：id 無法辨識且找不到 map 時，source_specs 無法解析的 map 也要列名。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/x.md"
    _write(spec, "---\nid: SPEC-UI-101\n---\n### FR-01: A\n")
    _write(tmp_path / "docs/spec/b/domain-map.md", "---\ndomain: \"b\"\nsource_specs: SPEC-101\n---\n")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 1
    assert "spec id 無法辨識" in cap.out
    assert "docs/spec/b/domain-map.md" in cap.err and "格式無法解析" in cap.err


def test_layer_id_check_runs_after_system_layer_existence_check(tmp_path, monkeypatch, capsys):
    """守護攔截順序：id 無法辨識且系統層不存在時，仍先報系統層不存在。"""
    spec = _layer_id_fixture(tmp_path, monkeypatch, "SPEC-UI-101")
    (tmp_path / "docs/system-layer.md").unlink()
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "但該檔不存在" in out and "spec id 無法辨識" not in out


def test_unparseable_map_not_repeated_on_stderr_when_stdout_names_it(tmp_path, monkeypatch, capsys):
    """成因為 source_specs 無法解析時 stdout 已列名，stderr 不重複（不限成因的一律列名會使此測試翻紅）。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, "---\nid: SPEC-101\n---\n### FR-01: A\n")
    _write(tmp_path / "docs/spec/b/domain-map.md", "---\ndomain: \"b\"\nsource_specs: SPEC-101\n---\n")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 1
    assert "docs/spec/b/domain-map.md" in cap.out and cap.err == ""


# --- 同目錄 map 與警告的單點輸出 ---

def test_same_dir_unparseable_map_in_use_is_not_reported_as_excluded(tmp_path, monkeypatch, capsys):
    """同目錄 map 已被選入判定，不得以「未納入本次判定」列名。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, "---\nid: SPEC-101\n---\n### FR-01: A\n### FR-02: B\n")
    _write(tmp_path / "docs/spec/ui/domain-map.md",
           "---\ndomain: \"ui\"\nsource_specs: SPEC-101\n---\n## SPEC-101\n| FR-01 | A |\n")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 1 and "FR-02" in cap.out
    assert cap.err == ""


def test_unparseable_unrelated_map_warned_exactly_once_and_rc_zero(tmp_path, monkeypatch, capsys):
    spec = _unparseable_fixture(tmp_path, monkeypatch)
    (tmp_path / "docs/spec/a/domain-map.md").write_text(
        "---\ndomain: \"a\"\nsource_specs: [SPEC-101]\n---\n## SPEC-101\n| FR-01~02 | A |\n", encoding="utf-8")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.err.count(B_PATH) == 1 and cap.err.count("WARNING") == 1


def test_unparseable_map_warned_once_when_domain_field_format_error(tmp_path, monkeypatch, capsys):
    """domain 欄格式錯誤而提前結束的路徑也列名（單點輸出於定位完成後）。"""
    spec = _unparseable_fixture(tmp_path, monkeypatch, b_source_specs="SPEC-999")
    (tmp_path / "docs/spec/a/domain-map.md").unlink()
    spec.write_text("---\nid: SPEC-101\ndomain: \"[a, b]\"\n---\n### FR-01: A\n", encoding="utf-8")
    _write(tmp_path / "docs/spec/c/domain-map.md", "---\ndomain: \"c\"\nsource_specs: [SPEC-999]\n---\n")
    rc = cdc.main([str(spec)])
    cap = capsys.readouterr()
    assert rc == 1
    assert cap.err.count(B_PATH) == 1


# --- 未覆蓋尾行的補法與部分歸屬檔的未歸屬提示 ---

PARTIAL_MARK = "為部分歸屬的檔"


def _partial_fixture(tmp_path, monkeypatch, a_body, b_body=None, source_specs="[SPEC-101, SPEC-202]"):
    """SPEC-101 在 docs/spec/ui；a（與可選的 b）為 source_specs 含本 SPEC 的 map。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/ui/SPEC-101-x.md"
    _write(spec, SPEC_A)
    _write(tmp_path / "docs/spec/a/domain-map.md", f"---\nsource_specs: {source_specs}\n---\n{a_body}")
    if b_body is not None:
        _write(tmp_path / "docs/spec/b/domain-map.md", f"---\nsource_specs: {source_specs}\n---\n{b_body}")
    return spec


def test_multi_value_source_specs_partial_map_unattributed_fr_not_counted(tmp_path, monkeypatch, capsys):
    """多值 source_specs 且部分歸屬：未歸屬的 FR-01 不計入，他 SPEC 的 FR-03 也不計入，只有 FR-02 被覆蓋。"""
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "| FR-01 | A |\n## SPEC-101\n| FR-02 | B |\n## SPEC-202\n| FR-03 | C |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "發現 2 個 FR" in out and "FR-01" in out and "FR-03" in out and "FR-02\n" not in out


def test_hint_lists_file_when_uncovered_fr_in_its_unattributed_set(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "| FR-01 | A |\n## SPEC-101\n| FR-02,03 | B |\n")
    assert cdc.main([str(spec)]) == 1
    err = capsys.readouterr().err
    assert err == ("WARNING: docs/spec/a/domain-map.md 為部分歸屬的檔，下列未覆蓋的 FR 在其中"
                   "未歸屬到任何 SPEC，故不計入：FR-01\n")


def test_hint_e1_unattributed_fr_not_in_spec_prints_nothing(tmp_path, monkeypatch, capsys):
    """E1 對照一：部分歸屬的檔有未歸屬 FR，但該 FR 不在 SPEC 內，未覆蓋的 FR-03 則不在任何 map。"""
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "| FR-09 | Z |\n## SPEC-101\n| FR-01,02 | B |\n")
    assert cdc.main([str(spec)]) == 1
    cap = capsys.readouterr()
    assert "FR-03" in cap.out and cap.err == ""


def test_hint_e1_fully_attributed_prints_nothing(tmp_path, monkeypatch, capsys):
    """E1 對照二：全歸屬的檔，未覆蓋的 FR 屬他 SPEC 的歸屬，無未歸屬集合。"""
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "## SPEC-101\n| FR-01,02 | B |\n## SPEC-202\n| FR-03 | C |\n")
    assert cdc.main([str(spec)]) == 1
    assert capsys.readouterr().err == ""


def test_hint_e1_no_attribution_file_uses_default_message_not_partial_hint(tmp_path, monkeypatch, capsys):
    """E1 對照三：整份無歸屬的檔 FR 計給受檢 SPEC（既有訊息），不印部分歸屬提示。"""
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01,02 | A |\n")
    assert cdc.main([str(spec)]) == 1
    err = capsys.readouterr().err
    assert "依預設計給受檢 SPEC" in err and PARTIAL_MARK not in err


def test_hint_same_fr_in_two_files_listed_once_each(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "| FR-01 | A |\n## SPEC-101\n| FR-02,03 | B |\n",
                            "| FR-01 | A2 |\n## SPEC-101\n| FR-02 | B2 |\n")
    assert cdc.main([str(spec)]) == 1
    err = capsys.readouterr().err
    assert err.count(PARTIAL_MARK) == 2
    assert err.count("docs/spec/a/domain-map.md") == 1 and err.count("docs/spec/b/domain-map.md") == 1


def test_hint_not_printed_when_check_passes(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch,
                            "| FR-09 | Z |\n## SPEC-101\n| FR-01~03 | B |\n")
    assert cdc.main([str(spec)]) == 0
    assert capsys.readouterr().err == ""


def test_tail_has_no_hardcoded_section_number(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch, "## SPEC-101\n| FR-01 | B |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert MAP_TAIL in out and "§" not in out


def test_tail_without_spec_id_does_not_name_an_id(tmp_path, monkeypatch, capsys):
    """取不到 SPEC 識別時走相容模式，補法不指名識別。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "docs/spec/x.md"
    _write(spec, "### FR-01: a\n### FR-02: b\n")
    _write(tmp_path / "docs/domain-map.md", "| FR-01 | A |\n")
    assert cdc.main([str(spec)]) == 1
    assert "請於 domain map 補上這些 FR。" in capsys.readouterr().out


def test_following_the_tail_with_section_title_turns_check_green(tmp_path, monkeypatch, capsys):
    """訊息即指令：依尾行把未覆蓋的 FR 放到含 SPEC-101 的章節標題下，檢核轉為通過。"""
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01 | A |\n## SPEC-101\n| FR-02,03 | B |\n")
    assert cdc.main([str(spec)]) == 1
    assert MAP_TAIL in capsys.readouterr().out
    a = tmp_path / "docs/spec/a/domain-map.md"
    a.write_text(a.read_text(encoding="utf-8").replace("| FR-01 | A |\n## SPEC-101\n", "## SPEC-101\n| FR-01 | A |\n"),
                 encoding="utf-8")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_same_line_id_after_the_fr_does_not_attribute(tmp_path, monkeypatch, capsys):
    """尾行說明識別須在 FR 之前：寫在 FR 之後不歸屬（歸屬取同行 FR 之前最近的識別）。"""
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01 | A | SPEC-101 |\n## SPEC-101\n| FR-02,03 | B |\n")
    assert cdc.main([str(spec)]) == 1


def test_following_the_tail_with_same_line_id_turns_check_green(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01 | A |\n## SPEC-101\n| FR-02,03 | B |\n")
    assert cdc.main([str(spec)]) == 1
    capsys.readouterr()
    a = tmp_path / "docs/spec/a/domain-map.md"
    a.write_text(a.read_text(encoding="utf-8").replace("| FR-01 | A |", "| SPEC-101 | FR-01 | A |"), encoding="utf-8")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_following_layer_tail_turns_check_green(tmp_path, monkeypatch, capsys):
    """層級路徑：系統層只列 FR 不帶 SPEC 識別時為紅；依尾行補識別後轉綠。"""
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="## 覆蓋\n| FR-01~02 | sys |\n")
    assert cdc.main([str(spec)]) == 1
    assert LAYER_TAIL in capsys.readouterr().out
    (tmp_path / "docs/system-layer.md").write_text("## SPEC-101 覆蓋\n| FR-01~02 | sys |\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


# --- 各 map 形態照尾行操作（整份無歸屬、並存、系統層）---

DEFAULT_MARK = "目前無任何 SPEC 歸屬，直接列出這些 FR 即可；若於該檔寫入任一 SPEC id，檔內其餘 FR 須一併歸屬到 SPEC-101。"


def _no_attr_fixture(tmp_path, monkeypatch, body="| FR-01 | A |\n"):
    return _partial_fixture(tmp_path, monkeypatch, body, source_specs="[SPEC-101]")


def _rewrite_a(tmp_path, body):
    (tmp_path / "docs/spec/a/domain-map.md").write_text("---\nsource_specs: [SPEC-101]\n---\n" + body, encoding="utf-8")


def test_no_attribution_map_tail_names_file_and_warns_about_whole_file(tmp_path, monkeypatch, capsys):
    spec = _no_attr_fixture(tmp_path, monkeypatch)
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "docs/spec/a/domain-map.md " + DEFAULT_MARK in out and MAP_TAIL in out


def test_no_attribution_map_following_tail_listing_fr_turns_green(tmp_path, monkeypatch, capsys):
    spec = _no_attr_fixture(tmp_path, monkeypatch)
    assert cdc.main([str(spec)]) == 1
    _rewrite_a(tmp_path, "| FR-01~03 | A |\n")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_no_attribution_map_following_tail_all_with_id_turns_green(tmp_path, monkeypatch, capsys):
    spec = _no_attr_fixture(tmp_path, monkeypatch)
    assert cdc.main([str(spec)]) == 1
    _rewrite_a(tmp_path, "| SPEC-101 | FR-01~03 | A |\n")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_no_attribution_map_id_on_single_fr_turns_other_fr_red(tmp_path, monkeypatch, capsys):
    """尾行所預告的行為：只對單一 FR 補 id，檔轉為部分歸屬，其餘 FR 不再計入。"""
    spec = _no_attr_fixture(tmp_path, monkeypatch, "| FR-01,03 | A |\n")
    assert cdc.main([str(spec)]) == 1  # FR-02 未覆蓋
    capsys.readouterr()
    _rewrite_a(tmp_path, "| FR-01,03 | A |\n| SPEC-101 | FR-02 | B |\n")
    assert cdc.main([str(spec)]) == 1
    out = capsys.readouterr().out
    assert "FR-01" in out and "FR-03" in out and "FR-02\n" not in out


def test_default_sentence_absent_when_all_files_have_attribution(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01 | A |\n## SPEC-101\n| FR-02 | B |\n")
    assert cdc.main([str(spec)]) == 1
    assert "目前無任何 SPEC 歸屬" not in capsys.readouterr().out


def test_mixed_files_sentence_names_only_default_file_and_hint_only_partial_file(tmp_path, monkeypatch, capsys):
    spec = _partial_fixture(tmp_path, monkeypatch, "| FR-01 | A |\n",
                            "| FR-03 | x |\n## SPEC-101\n| FR-02 | B |\n", source_specs="[SPEC-101]")
    assert cdc.main([str(spec)]) == 1
    cap = capsys.readouterr()
    assert "docs/spec/a/domain-map.md " + DEFAULT_MARK in cap.out and "docs/spec/b/domain-map.md 目前" not in cap.out
    assert cap.err.count(PARTIAL_MARK) == 1 and "docs/spec/b/domain-map.md" in cap.err
    b = tmp_path / "docs/spec/b/domain-map.md"
    b.write_text("---\nsource_specs: [SPEC-101]\n---\n## SPEC-101\n| FR-03 | x |\n| FR-02 | B |\n", encoding="utf-8")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_system_layer_without_attribution_current_output_is_silent(tmp_path, monkeypatch, capsys):
    """固定現況（不改行為）：系統層整份無歸屬且含未覆蓋的 FR，stderr 與尾行皆無說明。"""
    spec = _no_attr_fixture(tmp_path, monkeypatch, "## SPEC-101\n| FR-01 | A |\n")
    _write(tmp_path / "docs/system-layer.md", "| FR-02,03 | s |\n")
    assert cdc.main([str(spec)]) == 1
    cap = capsys.readouterr()
    assert cap.err == "" and "目前無任何 SPEC 歸屬" not in cap.out and "FR-02" in cap.out


def test_system_layer_partial_attribution_gets_hint_and_following_tail_turns_green(tmp_path, monkeypatch, capsys):
    spec = _no_attr_fixture(tmp_path, monkeypatch, "## SPEC-101\n| FR-01 | A |\n")
    _write(tmp_path / "docs/system-layer.md", "| FR-02 | s |\n## SPEC-101\n| FR-03 | s |\n")
    assert cdc.main([str(spec)]) == 1
    cap = capsys.readouterr()
    assert cap.err.startswith("WARNING: docs/system-layer.md " + PARTIAL_MARK) and "FR-02" in cap.err
    _write(tmp_path / "docs/system-layer.md", "## SPEC-101\n| FR-02 | s |\n| FR-03 | s |\n")
    assert cdc.main([str(spec)]) == 0, capsys.readouterr().out


def test_layer_mode_prints_no_partial_hint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    spec = _layer_fixture(tmp_path, system="| FR-02 | z |\n## SPEC-101\n| FR-01 | s |\n")
    assert cdc.main([str(spec)]) == 1
    cap = capsys.readouterr()
    assert LAYER_TAIL in cap.out and PARTIAL_MARK not in cap.err
