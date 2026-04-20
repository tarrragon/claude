"""
Phase 4 Decision Enforcement Hook 測試（PC-093 YAGNI 累積防護）

對應 Ticket 0.18.0-W10-082 Phase 2 測試計畫（78 案例 / 5 GWT Groups / 7 fixtures）。

分層：
  L1 regex 偵測           40 案例
  L2 exempt 解析          12 案例
  L3 exempt 距離匹配       5 案例
  L4 main() 整合          10 案例
  L5 settings.json 契約    3 案例
  邊界                     8 案例

載入方式：importlib.util（檔名含連字號）
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ----------------------------------------------------------------------------
# Module 動態載入
# ----------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "phase4_decision_enforcement_hook",
    _HOOKS_DIR / "phase4-decision-enforcement-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

build_regex_table = _hook.build_regex_table
detect_hook_self_reference = _hook.detect_hook_self_reference
scan_lines_for_phrases = _hook.scan_lines_for_phrases
parse_exempt_marker = _hook.parse_exempt_marker
validate_exempt_fields = _hook.validate_exempt_fields
collect_exempt_markers = _hook.collect_exempt_markers
is_hit_exempted = _hook.is_hit_exempted
partition_hits = _hook.partition_hits
extract_ticket_id_from_command = _hook.extract_ticket_id_from_command
format_block_message = _hook.format_block_message
format_warn_info_message = _hook.format_warn_info_message
Hit = _hook.Hit
ExemptRef = _hook.ExemptRef
ExemptMarker = _hook.ExemptMarker
main = _hook.main


_FIXTURES = Path(__file__).parent / "fixtures" / "pc093"


def _scan_text(text):
    """Helper: 對單段文字執行 phrase 掃描，回傳 hits。"""
    table = build_regex_table()
    lines = text.split("\n")
    return scan_lines_for_phrases(lines, table)


def _hits_by_rule(hits, rule_id):
    return [h for h in hits if h.rule_id == rule_id]


# ============================================================================
# L1 — Regex 偵測（40 案例：8 regex × (3 正 + 2 負)）
# ============================================================================

# ---------- M1 Phase X 再決定 ----------

def test_m1_p1_phase4_再決定():
    hits = _scan_text("Phase 4 再決定是否保留 use_cache")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_p2_phase5_視_baseline_決定():
    hits = _scan_text("Phase 5 視 baseline 決定")
    assert len(_hits_by_rule(hits, "M1")) >= 1


def test_m1_p3_小寫_phase_再評估():
    hits = _scan_text("phase 4 再評估")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_n1_phase4_完成實作():
    hits = _scan_text("Phase 4 完成實作")
    assert _hits_by_rule(hits, "M1") == []


def test_m1_n2_phase_過渡():
    hits = _scan_text("Phase 1 → Phase 2 過渡")
    assert _hits_by_rule(hits, "M1") == []


# ---------- M2 之後/以後 再決定 ----------

def test_m2_p1_之後再決定():
    hits = _scan_text("use_cache 之後再決定")
    assert len(_hits_by_rule(hits, "M2")) == 1


def test_m2_p2_以後再處理():
    hits = _scan_text("以後再處理 CheckpointStateError")
    assert len(_hits_by_rule(hits, "M2")) == 1


def test_m2_p3_日後再考慮():
    hits = _scan_text("日後再考慮 extension error")
    assert len(_hits_by_rule(hits, "M2")) == 1


def test_m2_n1_之後補充測試():
    # 「之後會補充測試」沒有「再決定/說/考慮/處理」
    hits = _scan_text("之後會補充測試於 Phase 2")
    assert _hits_by_rule(hits, "M2") == []


def test_m2_n2_完成後立即處理():
    hits = _scan_text("完成後立即處理")
    assert _hits_by_rule(hits, "M2") == []


# ---------- M3 保留以防萬一 ----------

def test_m3_p1_保留以防萬一():
    hits = _scan_text("保留 use_cache 以防萬一")
    assert len(_hits_by_rule(hits, "M3")) == 1


def test_m3_p2_保留擴展彈性():
    hits = _scan_text("保留擴展彈性")
    assert len(_hits_by_rule(hits, "M3")) == 1


def test_m3_p3_保留以備不時之需():
    hits = _scan_text("保留以備不時之需")
    assert len(_hits_by_rule(hits, "M3")) == 1


def test_m3_n1_保留原有實作():
    hits = _scan_text("保留原有實作")
    assert _hits_by_rule(hits, "M3") == []


def test_m3_n2_保留此區段註解():
    hits = _scan_text("保留此區段註解")
    assert _hits_by_rule(hits, "M3") == []


# ---------- W1 視 X 結果再決定 ----------

def test_w1_p1_視_baseline_結果再決定():
    hits = _scan_text("視 baseline 結果再決定")
    assert len(_hits_by_rule(hits, "W1")) == 1


def test_w1_p2_視實測情況決定():
    hits = _scan_text("視實測情況決定")
    assert len(_hits_by_rule(hits, "W1")) == 1


def test_w1_p3_視需求結果而評估():
    hits = _scan_text("視需求結果而評估")
    assert len(_hits_by_rule(hits, "W1")) == 1


def test_w1_n1_視需要調整():
    hits = _scan_text("視需要調整")
    assert _hits_by_rule(hits, "W1") == []


def test_w1_n2_結果已評估完成():
    hits = _scan_text("結果已評估完成")
    assert _hits_by_rule(hits, "W1") == []


# ---------- W2 未來/以後 可能需要 ----------

def test_w2_p1_未來可能需要():
    hits = _scan_text("未來可能需要 cache")
    assert len(_hits_by_rule(hits, "W2")) == 1


def test_w2_p2_以後或許會用():
    hits = _scan_text("以後或許會用到")
    assert len(_hits_by_rule(hits, "W2")) == 1


def test_w2_p3_未來也許要用():
    hits = _scan_text("未來也許要用")
    assert len(_hits_by_rule(hits, "W2")) == 1


def test_w2_n1_未來版本實作():
    hits = _scan_text("未來版本實作")
    assert _hits_by_rule(hits, "W2") == []


def test_w2_n2_可能發生競爭條件():
    hits = _scan_text("可能發生競爭條件")
    assert _hits_by_rule(hits, "W2") == []


# ---------- W3 先保留再說 ----------

def test_w3_p1_先保留再說():
    hits = _scan_text("先保留再說")
    assert len(_hits_by_rule(hits, "W3")) == 1


def test_w3_p2_先不動吧():
    hits = _scan_text("先不動吧")
    assert len(_hits_by_rule(hits, "W3")) == 1


def test_w3_p3_先留著():
    hits = _scan_text("先留著")
    assert len(_hits_by_rule(hits, "W3")) == 1


def test_w3_n1_先實作再測試():
    hits = _scan_text("先實作再測試")
    assert _hits_by_rule(hits, "W3") == []


def test_w3_n2_保留以供審查():
    hits = _scan_text("保留以供審查")
    assert _hits_by_rule(hits, "W3") == []


# ---------- I1 TBD/TODO/FIXME ----------

def test_i1_p1_todo_phase4_決定():
    hits = _scan_text("TODO: Phase 4 決定")
    assert len(_hits_by_rule(hits, "I1")) == 1


def test_i1_p2_fixme_之後處理():
    hits = _scan_text("FIXME: 之後處理")
    assert len(_hits_by_rule(hits, "I1")) == 1


def test_i1_p3_tbd_未來補充():
    hits = _scan_text("TBD: 未來補充")
    assert len(_hits_by_rule(hits, "I1")) == 1


def test_i1_n1_todo_實作_foo():
    hits = _scan_text("TODO: 實作 foo()")
    assert _hits_by_rule(hits, "I1") == []


def test_i1_n2_已完成_todo():
    hits = _scan_text("已完成 TODO")
    assert _hits_by_rule(hits, "I1") == []


# ---------- I2 擴展彈性/擴充介面 ----------

def test_i2_p1_保留擴展彈性_共命中():
    # I2-P1 與 M3 可能同時命中；取高級由 partition 處理
    hits = _scan_text("保留擴展彈性")
    assert len(_hits_by_rule(hits, "I2")) == 1


def test_i2_p2_提供擴充介面():
    hits = _scan_text("提供擴充介面")
    assert len(_hits_by_rule(hits, "I2")) == 1


def test_i2_p3_預留擴展空間():
    hits = _scan_text("預留擴展空間")
    assert len(_hits_by_rule(hits, "I2")) == 1


def test_i2_n1_介面已實作():
    hits = _scan_text("介面已實作")
    assert _hits_by_rule(hits, "I2") == []


def test_i2_n2_擴展功能完成():
    hits = _scan_text("擴展功能完成")
    assert _hits_by_rule(hits, "I2") == []


# ============================================================================
# L2 — Exempt 解析與驗證（12 案例）
# ============================================================================

def test_ex_p1_tdd_transition_valid():
    m = parse_exempt_marker("<!-- PC-093-exempt: tdd-transition:Phase 2 補 RED 測試正當 -->")
    assert m is not None and m.category == "tdd-transition"
    valid, err = validate_exempt_fields(m)
    assert valid is True


def test_ex_p2_baseline_gated_valid_含數字():
    m = parse_exempt_marker("<!-- PC-093-exempt: baseline-gated:baseline>80ms 才啟用 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is True


def test_ex_p3_ticket_tracked_valid_含_ticket_id():
    m = parse_exempt_marker("<!-- PC-093-exempt: ticket-tracked:延後至 W11-005 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is True


def test_ex_p4_user_override_valid():
    m = parse_exempt_marker("<!-- PC-093-exempt: user-override:PM 已判斷此為特殊情境必要保留 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is True


def test_ex_n1_unknown_category():
    m = parse_exempt_marker("<!-- PC-093-exempt: unknown-cat:理由充足十字以上啊 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "category-whitelist"


def test_ex_n2_reason_too_short():
    m = parse_exempt_marker("<!-- PC-093-exempt: tdd-transition:短 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "reason-too-short"


def test_ex_n3_baseline_gated_缺數字():
    m = parse_exempt_marker("<!-- PC-093-exempt: baseline-gated:沒有數字理由夠長的啦 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "baseline-need-number"


def test_ex_n4_ticket_tracked_缺_ticket_id():
    # reason 長度 >= 10 但無 ticket id
    m = parse_exempt_marker("<!-- PC-093-exempt: ticket-tracked:這段理由夠長但沒有票號引用的啦 -->")
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "ticket-tracked-need-id"


def test_ex_n5_格式錯誤_missing_colon_reason():
    m = parse_exempt_marker("<!-- PC-093-exempt: missing-reason -->")
    assert m is None


def test_ex_n6_空格寬鬆():
    m = parse_exempt_marker("<!--PC-093-exempt:tdd-transition:無空格寬鬆模式而且夠長十字-->")
    assert m is not None
    valid, err = validate_exempt_fields(m)
    assert valid is True


def test_ex_n7_大小寫敏感():
    m = parse_exempt_marker("<!-- pc-093-exempt: tdd-transition:小寫不認 -->")
    assert m is None


def test_ex_n8_非_html_comment():
    # 純文字非 HTML comment
    m = parse_exempt_marker("PC-093-exempt: tdd-transition:純文字不認")
    assert m is None


# ============================================================================
# L3 — Exempt 距離匹配（5 案例）
# ============================================================================

def _read_fixture(name):
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_dist_1_同行後綴豁免生效():
    content = _read_fixture("ticket_exempt_distance.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)

    # Section A (DIST-1) phrase should be exempted
    section_a_hits = [h for h in exempted if "foo" in h.text or h.line_no <= 10]
    assert any(h.line_no <= 10 for h in exempted), "DIST-1 same-line exempt should work"


def test_dist_2_前_1_行豁免生效():
    content = _read_fixture("ticket_exempt_distance.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)

    # Section B 有一條命中應被豁免（line ~11-13 範圍）
    # 粗略：至少有豁免行數接近 Section B
    assert len(exempted) >= 2, "DIST-2 前 1 行應豁免"


def test_dist_3_前_2_行不豁免():
    content = _read_fixture("ticket_exempt_distance.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)

    # Section C 的 phrase 不應豁免 → blocked 應 >= 1
    assert len(blocked) >= 1, "DIST-3 前 2 行不應生效 → blocked 有殘留"


def test_dist_4_marker_在_phrase_後不豁免():
    # Section D 在 ticket_exempt_distance.md 裡，phrase 行 < marker 行 → 不豁免
    content = _read_fixture("ticket_exempt_distance.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)
    # Section C + Section D 皆應殘留 blocked
    assert len(blocked) >= 2, "DIST-3 + DIST-4 都應殘留"


def test_dist_5_多個_marker_各自對應():
    content = _read_fixture("ticket_with_multi_exempt.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)
    # 4 個 phrase 全部應被個別 marker 豁免
    assert len(blocked) == 0
    assert len(exempted) == 4


# ============================================================================
# L4 — main() 整合測試（10 案例）
# ============================================================================

def _run_main_with_stdin(stdin_payload, monkeypatch, capsys):
    """呼叫 main() 並捕捉 stdin/stdout/stderr + exit。"""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stdin_payload)))
    rc = main()
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _payload(event, command, tool_name="Bash"):
    return {
        "hook_event_name": event,
        "tool_name": tool_name,
        "tool_input": {"command": command},
    }


@pytest.fixture
def mock_find_ticket(monkeypatch):
    """以 fixture 取代 find_ticket_file 使 main 讀 fixture md。"""
    def _mk(fixture_name):
        target = _FIXTURES / fixture_name
        monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, **kw: target)
    return _mk


def test_int_1_clean_ticket_exit_0(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("clean_ticket.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0
    assert err == ""


def test_int_2_must_block_exit_2_stderr(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_must_block.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 2
    assert "PC-093" in err
    assert "強制決斷" in err
    assert "AUQ" in err


def test_int_3_exempt_exit_0_with_audit(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_exempt.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0
    # stdout 應含豁免清單
    assert "豁免清單" in out or "豁免" in out


def test_int_4_warn_only_exit_0_stdout(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_warn_only.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0
    assert err == ""  # IMP-048: WARN 不寫 stderr
    assert "警告" in out or "PC-093" in out


def test_int_5_info_only_exit_0(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_info_only.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0
    assert err == ""


def test_int_6_phase3b_不觸發(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_must_block.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase3b"),
        monkeypatch, capsys,
    )
    # phase3b 不匹配 MAIN_GATE_CMD → early exit 0
    assert rc == 0
    assert err == ""


def test_int_7_pretool_complete_殘留_block(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_must_block.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PreToolUse", "ticket track complete TST-001"),
        monkeypatch, capsys,
    )
    assert rc == 2
    assert "PC-093" in err


def test_int_8_pretool_complete_clean(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("clean_ticket.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PreToolUse", "ticket track complete TST-001"),
        monkeypatch, capsys,
    )
    assert rc == 0


def test_int_9_同行多命中全部列出(monkeypatch, capsys, mock_find_ticket):
    mock_find_ticket("ticket_with_must_block.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 2
    # 至少列出 3 個命中（M1 + M2 + M3 三行）
    assert err.count("line ") >= 3


def test_int_10_非_ticket_命令_不觸發(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        _payload("PostToolUse", "git status")
    )))
    rc = main()
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.err == ""


# ============================================================================
# L5 — settings.json 契約（3 案例）
# ============================================================================

_SETTINGS = _HOOKS_DIR.parent / "settings.json"


def _load_settings():
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


def test_cfg_1_posttooluse_含_phase4_hook():
    settings = _load_settings()
    posttool = settings.get("hooks", {}).get("PostToolUse", [])
    bash_hooks = []
    for entry in posttool:
        if entry.get("matcher") == "Bash":
            bash_hooks.extend(entry.get("hooks", []))
    commands = [h.get("command", "") for h in bash_hooks]
    assert any("phase4-decision-enforcement-hook" in c for c in commands)


def test_cfg_2_pretooluse_含_phase4_hook():
    settings = _load_settings()
    pretool = settings.get("hooks", {}).get("PreToolUse", [])
    bash_hooks = []
    for entry in pretool:
        if entry.get("matcher") == "Bash":
            bash_hooks.extend(entry.get("hooks", []))
    commands = [h.get("command", "") for h in bash_hooks]
    assert any("phase4-decision-enforcement-hook" in c for c in commands)


def test_cfg_3_timeout_設定():
    settings = _load_settings()
    found = False
    for group in ("PostToolUse", "PreToolUse"):
        for entry in settings.get("hooks", {}).get(group, []):
            if entry.get("matcher") != "Bash":
                continue
            for h in entry.get("hooks", []):
                if "phase4-decision-enforcement-hook" in h.get("command", ""):
                    # timeout 欄位為可選，但若存在應 <= 10000
                    if "timeout" in h:
                        assert h["timeout"] <= 10000
                    found = True
    assert found


# ============================================================================
# 邊界案例（8 項）
# ============================================================================

def test_b1_空_ticket_md_不_crash(monkeypatch, capsys, tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, **kw: empty)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        _payload("PostToolUse", "ticket track phase TST-001 phase4")
    )))
    rc = main()
    assert rc == 0


def test_b2_ticket_md_不存在(monkeypatch, capsys):
    monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, **kw: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        _payload("PostToolUse", "ticket track phase TST-001 phase4")
    )))
    rc = main()
    assert rc == 0


def test_b3_unicode_全形標點():
    hits = _scan_text("Phase 4 再決定!")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_b4_極長行不_timeout():
    long_line = "x" * 15000 + " Phase 4 再決定"
    hits = _scan_text(long_line)
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_b5_marker_內含_phrase_不誤判():
    # marker 文字內含「Phase 4 再決定」字樣，應被 strip 後不命中
    text = "<!-- PC-093-exempt: tdd-transition:說明 Phase 4 再決定的規則的原因 -->\n其他內容"
    hits = _scan_text(text)
    assert _hits_by_rule(hits, "M1") == []


def test_b6_phrase_在程式碼區塊內仍命中():
    text = "```\nPhase 4 再決定 cache\n```"
    hits = _scan_text(text)
    # 保守偵測：仍命中
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_b7_同行多_phrase():
    hits = _scan_text("Phase 4 再決定保留擴展彈性")
    # 同行可能命中 M1 + M3 + I2
    rule_ids = {h.rule_id for h in hits}
    assert "M1" in rule_ids
    assert "M3" in rule_ids


def test_b8_stdin_缺_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {},
    })))
    rc = main()
    assert rc == 0


# ============================================================================
# 額外：F8 extract_ticket_id_from_command
# ============================================================================

def test_extract_phase4_mode():
    tid, mode = extract_ticket_id_from_command("ticket track phase 0.18.0-W10-082 phase4")
    assert tid == "0.18.0-W10-082"
    assert mode == "main_gate"


def test_extract_complete_mode():
    tid, mode = extract_ticket_id_from_command("ticket track complete TST-001")
    assert tid == "TST-001"
    assert mode == "residual_gate"


def test_extract_phase3b_不匹配():
    tid, mode = extract_ticket_id_from_command("ticket track phase TST-001 phase3b")
    assert mode is None


def test_extract_無關命令():
    tid, mode = extract_ticket_id_from_command("git status")
    assert tid is None and mode is None


# ============================================================================
# PC-099 — 檔級 self-reference 豁免（meta-ticket 防誤報）
# ============================================================================

def test_self_ref_單行形式():
    content = (
        "---\n"
        "id: X\n"
        "hook_self_reference: phase4-decision-enforcement\n"
        "title: Y\n"
        "---\n"
        "Phase 4 再決定\n"
    )
    assert detect_hook_self_reference(content) is True


def test_self_ref_list_形式():
    content = (
        "---\n"
        "id: X\n"
        "hook_self_reference:\n"
        "  - phase4-decision-enforcement\n"
        "  - other-hook\n"
        "---\n"
    )
    assert detect_hook_self_reference(content) is True


def test_self_ref_引號包裹():
    content = (
        "---\n"
        'hook_self_reference: "phase4-decision-enforcement"\n'
        "---\n"
    )
    assert detect_hook_self_reference(content) is True


def test_self_ref_無_frontmatter():
    assert detect_hook_self_reference("Phase 4 再決定\n") is False


def test_self_ref_其他_hook_值不豁免():
    content = (
        "---\n"
        "hook_self_reference: other-hook\n"
        "---\n"
    )
    assert detect_hook_self_reference(content) is False


def test_self_ref_無此欄位():
    content = "---\nid: X\ntitle: Y\n---\n"
    assert detect_hook_self_reference(content) is False


def test_self_ref_main_整合_豁免整檔(monkeypatch, tmp_path, capsys):
    """Main flow: self-ref ticket 有 M1 命中但整檔豁免 → exit 0 無 stderr。"""
    ticket_md = tmp_path / "TEST-099.md"
    ticket_md.write_text(
        "---\n"
        "id: TEST-099\n"
        "hook_self_reference: phase4-decision-enforcement\n"
        "---\n"
        "Phase 4 再決定是否保留 use_cache\n"
        "保留以防萬一\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, logger=None: ticket_md)
    stdin_json = json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_input": {"command": "ticket track phase TEST-099 phase4"},
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_json))
    rc = main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "PC-093 Phase 4 強制決斷" not in captured.err
