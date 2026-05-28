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


# ---- W10-127: Context Bundle [ref] 行豁免（PC-142 case 4 漏網案例） ----

def test_w10_127_ref_line_phase4_不命中():
    """`- [ref] [ ] Phase 4 評估` 行屬 source ticket 引用，不應命中。"""
    text = "- [ref] [ ] Phase 4 評估結論明確（禁止 Phase 5 再決定）  # from 0.18.0-W10-113"
    hits = _scan_text(text)
    assert hits == [], "ref 行不應產生任何命中，實際: {}".format(hits)


def test_w10_127_一般_phase4_仍命中():
    """非 [ref] 行的「Phase 4 再決定」仍應命中（保留既有偵測能力）。"""
    text = "Phase 4 再決定是否保留 use_cache"
    hits = _scan_text(text)
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_w10_127_ref_inline_含其他延後話術也豁免():
    """`[ref]` 開頭行即使 inline 含其他延後話術也整行豁免（trim 後判斷）。"""
    text = "  [ref] 之後再決定處理方式"
    hits = _scan_text(text)
    assert hits == []


def test_w10_127_w10_116_line_186_真實案例():
    """W10-116 line 186 真實命中案例：修復後不應再報 hit。"""
    text = (
        "- [ref] [ ] Phase 4 評估結論明確（無需重構 / 採方案 X / "
        "spawn N 個 IMP ticket，禁止 Phase 5 再決定）  # from 0.18.0-W10-113"
    )
    hits = _scan_text(text)
    assert hits == [], "W10-116 line 186 真實案例不應命中，實際: {}".format(hits)


# ---- W10-122: rule-quote 類別豁免（PC-142 治本） ----

def test_ex_p5_rule_quote_valid_含規則路徑():
    """合法引用：reason 含 .claude/rules/ 路徑，應豁免「Phase 5 再決定」字面誤判。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: rule-quote:引用 .claude/rules/core/decision-trigger-binding.md 規則 1.5 -->"
    )
    assert m is not None and m.category == "rule-quote"
    valid, err = validate_exempt_fields(m)
    assert valid is True and err is None


def test_ex_p6_rule_quote_valid_含_pm_rules_路徑():
    """合法引用：reason 含 .claude/pm-rules/ 路徑也應通過。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: rule-quote:對照 .claude/pm-rules/skip-gate.md 條款 -->"
    )
    valid, err = validate_exempt_fields(m)
    assert valid is True and err is None


def test_ex_n9_rule_quote_缺路徑():
    """非法：rule-quote reason 不含規則路徑，應 invalid 並產出 rule-quote-need-path。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: rule-quote:這是規則引用但沒附路徑說明 -->"
    )
    assert m is not None and m.category == "rule-quote"
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "rule-quote-need-path"


# ---- W11-023: history 類別豁免（引用已完成歷史 / 動機脈絡） ----

def test_ex_p7_history_valid_含_ticket_id():
    """合法引用：reason 含 ticket ID 作歷史錨點，應通過驗證。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: history:本段引用 parent W11-004.7 多視角審查發現作動機脈絡 -->"
    )
    assert m is not None and m.category == "history"
    valid, err = validate_exempt_fields(m)
    assert valid is True and err is None


def test_ex_p8_history_valid_含_versioned_ticket_id():
    """合法引用：reason 含 versioned ticket ID（0.18.0-W11-004 含 W11-004 子字串）也應通過。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: history:引用 0.18.0-W11-004.7.1 的 Problem Analysis 作背景 -->"
    )
    valid, err = validate_exempt_fields(m)
    assert valid is True and err is None


def test_ex_n10_history_缺_ticket_id():
    """非法：history reason 不含 ticket ID 錨點，應 invalid 並產出 history-need-anchor。"""
    m = parse_exempt_marker(
        "<!-- PC-093-exempt: history:這是歷史脈絡但沒有票號錨點的說明 -->"
    )
    assert m is not None and m.category == "history"
    valid, err = validate_exempt_fields(m)
    assert valid is False and err == "history-need-anchor"


def test_ex_n11_history_invalid_message_contains_anchor_hint():
    """history-need-anchor 訊息應在 ERR_MESSAGE_MAP 中，含修復範例。"""
    err_map = _hook.ERR_MESSAGE_MAP
    assert "history-need-anchor" in err_map
    title, hint = err_map["history-need-anchor"]
    assert "history" in title
    assert "W" in hint  # 範例含 W{wave}-{seq} 格式


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
    # W11-018: 此測試在 GREEN 階段需更新為「不命中」（fenced block 豁免）
    # 暫保留為 RED 紀錄，Phase 3b 實作後改為 assert == 0
    text = "```\nPhase 4 再決定 cache\n```"
    hits = _scan_text(text)
    # W11-018 後預期：fenced block 內豁免，M1 不命中
    assert len(_hits_by_rule(hits, "M1")) == 0, "W11-018: fenced block 內應豁免"


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


# ============================================================================
# W17-085 — invalid exempt marker humanization
# ============================================================================

def test_format_warn_info_humanizes_ticket_tracked_need_id():
    """ticket-tracked 類別缺 ticket ID 時，輸出含 grep 訊號 + humanized hint。"""
    # 構造一份 ticket md 內容，含 W2 phrase 與 invalid exempt marker（無 W{wave}-{seq}）
    lines = [
        "<!-- PC-093-exempt: ticket-tracked:這是沒有 ticket id 的長理由說明 -->",
        "未來可能需要快取機制",
    ]
    refs = collect_exempt_markers(lines)
    # 該 marker 應 invalid 且 err code = ticket-tracked-need-id
    invalid = [r for r in refs if not r.valid]
    assert len(invalid) == 1
    assert invalid[0].err == "ticket-tracked-need-id"

    msg = format_warn_info_message(warned=[], info=[], exempted_refs=refs)
    # 保留 grep 訊號（向後相容）
    assert "ticket-tracked-need-id" in msg
    assert "[INVALID:" in msg
    # humanized hint 含 W{wave}-{seq} 關鍵字
    assert "W{wave}-{seq}" in msg or "W17-085" in msg
    assert "修復提示" in msg


def test_format_warn_info_humanizes_format_error():
    """格式錯誤（缺 cat:reason）時，輸出含 grep 訊號 + humanized 範例。"""
    lines = [
        "<!-- PC-093-exempt -->",
    ]
    refs = collect_exempt_markers(lines)
    invalid = [r for r in refs if not r.valid]
    assert len(invalid) == 1
    assert invalid[0].err == "format-error"

    msg = format_warn_info_message(warned=[], info=[], exempted_refs=refs)
    # 保留 grep 訊號
    assert "format-error" in msg
    assert "[INVALID:" in msg
    # humanized 範例含正確 marker 格式
    assert "<!-- PC-093-exempt:" in msg
    assert "修復提示" in msg


# ============================================================================
# W10-108 — Block 訊息可達性（白名單清單 + inline 提示）
# ============================================================================

def test_w10_108_block_message_lists_all_exempt_categories():
    """拒絕訊息必須完整列出 6 個合法 category（避免 agent 因不知道路徑而走字串繞過）。"""
    hits = [Hit(line_no=10, rule_id="M1", level="BLOCK", text="Phase 5 再決定")]
    msg = format_block_message("0.18.0-W10-108", hits, exempted=[])
    for category in ("tdd-transition", "baseline-gated", "ticket-tracked",
                     "user-override", "rule-quote", "history"):
        assert category in msg, "白名單必含 category: {}".format(category)


def test_w10_108_block_message_starts_with_inline_hint():
    """訊息開頭（標題後）必須含「優先嘗試 inline」提示，引導 agent 走 inline 路徑。"""
    hits = [Hit(line_no=10, rule_id="M1", level="BLOCK", text="Phase 5 再決定")]
    msg = format_block_message("0.18.0-W10-108", hits, exempted=[])
    # 提示文字存在
    assert "優先嘗試 inline" in msg
    # 位置：在「命中」清單之前（標題行之後第一個實質提示）
    inline_pos = msg.index("優先嘗試 inline")
    hit_pos = msg.index("命中:")
    assert inline_pos < hit_pos, "inline 提示必須在命中清單之前"


def test_w10_108_block_message_categories_have_use_case():
    """每個 category 後附『適用情境』一行說明（非僅列名稱）。"""
    hits = [Hit(line_no=10, rule_id="M1", level="BLOCK", text="Phase 5 再決定")]
    msg = format_block_message("0.18.0-W10-108", hits, exempted=[])
    # 每個 category 行格式包含「— 」說明分隔符
    for category in ("tdd-transition", "baseline-gated", "ticket-tracked",
                     "user-override", "rule-quote", "history"):
        # 找該 category 所在行
        for line in msg.split("\n"):
            if category in line and "—" in line:
                break
        else:
            raise AssertionError("category {} 缺『—』適用情境說明".format(category))


def test_w10_108_block_message_references_decision_trigger_binding_rule():
    """訊息應指向權威規則路徑，讓 agent 知道完整規格何處查詢。"""
    hits = [Hit(line_no=10, rule_id="M1", level="BLOCK", text="Phase 5 再決定")]
    msg = format_block_message("0.18.0-W10-108", hits, exempted=[])
    assert "decision-trigger-binding" in msg


# ============================================================================
# W10-130 — Placeholder template 區塊內 PC-093-exempt 範例字串豁免
# ============================================================================

def test_w10_130_schema_placeholder_block_skips_example_exempt_marker():
    """<!-- Schema[...]: ... --> placeholder 區塊內的 PC-093-exempt 範例字串
    不應被解析為實際 marker（避免誤判 cat:reason 為 INVALID category-whitelist）。"""
    lines = [
        "## Problem Analysis",
        "<!-- Schema[IMP/Problem Analysis]: 選填 -->",
        "",
        "範例: <!-- PC-093-exempt: cat:reason -->",
        "另一範例: <!-- PC-093-exempt: <category>:<reason> -->",
        "",
        "---",
        "",
        "## Solution",
        "實際內容",
    ]
    refs = collect_exempt_markers(lines)
    # placeholder 區塊內的範例字串不應被收集為 marker
    assert len(refs) == 0, (
        "placeholder 區塊內的 PC-093-exempt 範例應被跳過，"
        "但收到 {} markers: {}".format(len(refs), refs)
    )


def test_w10_130_schema_placeholder_block_terminates_at_next_h2():
    """placeholder 區塊在下個 H2（## ）處結束；之後的 marker 仍應被解析。"""
    lines = [
        "<!-- Schema[IMP/Problem Analysis]: 選填 -->",
        "<!-- PC-093-exempt: cat:reason -->",  # 範例（區塊內）— 跳過
        "## Solution",
        "<!-- PC-093-exempt: ticket-tracked:W10-130 hook 修復 -->",  # 區塊外 — 解析
    ]
    refs = collect_exempt_markers(lines)
    # 只剩第 4 行的真實 marker
    assert len(refs) == 1
    assert refs[0].line_no == 4
    assert refs[0].valid is True


def test_w10_130_schema_placeholder_block_terminates_at_hr_separator():
    """placeholder 區塊在 `---` 分隔符處結束；之後的 marker 仍應被解析。"""
    lines = [
        "<!-- Schema[IMP/Problem Analysis]: 選填 -->",
        "<!-- PC-093-exempt: cat:reason -->",  # 範例 — 跳過
        "",
        "---",
        "",
        "<!-- PC-093-exempt: ticket-tracked:W10-130 真實 marker -->",  # 解析
    ]
    refs = collect_exempt_markers(lines)
    assert len(refs) == 1
    assert refs[0].line_no == 6
    assert refs[0].valid is True


def test_w10_130_no_schema_placeholder_normal_marker_still_works():
    """無 Schema placeholder 區塊時，正常 marker 行為不變（regression guard）。"""
    lines = [
        "## Solution",
        "<!-- PC-093-exempt: ticket-tracked:W10-130 hook 修復說明 -->",
    ]
    refs = collect_exempt_markers(lines)
    assert len(refs) == 1
    assert refs[0].valid is True


def test_w10_130_schema_placeholder_also_skips_phrase_scanning():
    """placeholder 區塊內的延後話術（若有）也應跳過，避免範例字串觸發誤判。"""
    lines = [
        "<!-- Schema[IMP/Problem Analysis]: 範例：填入根因，例如 Phase 5 再決定的問題 -->",
        "<!-- PC-093-exempt: cat:reason -->",  # 範例 marker
        "",
        "---",
        "",
        "## Solution",
        "正常內容",
    ]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)
    # placeholder 區塊內即使 Schema note 含「Phase 5 再決定」字樣也應跳過
    assert len(blocked) == 0
    assert len(warned) == 0


# ============================================================================
# W11-018 — Fenced Code Block 範例語境豁免（Phase 2 RED 測試骨架）
#
# 對應 Phase 1 規格 §2.1 FENCE-1~7 / §2.2 豁免效果 / §2.5 EDGE-1~12 / §3 AC1-13
# 函式 compute_fenced_block_lines() 在 Phase 3b 實作前不存在 → 整段 RED。
#
# 分組：
#   FENCE-CORE   核心邊界規則（FENCE-1~7） — 純函式單元測試
#   FENCE-EDGE   邊界條件（EDGE-1~12） — 純函式單元測試
#   FENCE-INTEG  整合（scan_lines + collect_markers + partition + main）
#   FENCE-AC     AC1~AC13 對應驗收（含 regression 防護）
# ============================================================================

# 取得 compute_fenced_block_lines（Phase 3b 實作後存在；當前 AttributeError → RED）
def _get_fenced_fn():
    """延遲讀取，避免 module import 時整檔 fail。"""
    return getattr(_hook, "compute_fenced_block_lines", None)


# ---------- FENCE-CORE: 核心邊界規則（FENCE-1~7） ----------

def test_fence_1_basic_backtick_fence():
    """FENCE-1: 3+ backtick 起始 fence 識別。"""
    fn = _get_fenced_fn()
    assert fn is not None, "compute_fenced_block_lines 未實作（RED 預期）"
    lines = ["```", "content", "```"]
    result = fn(lines)
    assert result == {1, 2, 3}, "起始/結束 fence 與內容皆屬區塊"


def test_fence_1_tilde_fence():
    """FENCE-1: 3+ tilde 等效處理。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["~~~", "content", "~~~"]
    assert fn(lines) == {1, 2, 3}


def test_fence_2_close_must_match_char():
    """FENCE-2: backtick 不可被 tilde 閉合。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "content", "~~~", "still in"]
    # 未閉合 → 至檔尾
    assert fn(lines) == {1, 2, 3, 4}


def test_fence_2_close_length_must_ge_open():
    """FENCE-2: 結束 fence 長度必須 >= 起始長度。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["````", "content", "```", "still in", "````"]
    # 4-backtick 起始，3-backtick 不閉合（< 起始長度），4-backtick 閉合
    assert fn(lines) == {1, 2, 3, 4, 5}


def test_fence_3_language_hint_ignored():
    """FENCE-3: info string 不影響邊界。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```python", "code", "```"]
    assert fn(lines) == {1, 2, 3}


def test_fence_4_fence_lines_included():
    """FENCE-4: fence 起始與結束行自身屬區塊範圍。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "x", "```"]
    result = fn(lines)
    assert 1 in result and 3 in result


def test_fence_5_unclosed_to_eof():
    """FENCE-5: 未閉合 fence 視為至檔尾。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "line2", "line3"]
    assert fn(lines) == {1, 2, 3}


def test_fence_6_indented_3_spaces_still_valid():
    """FENCE-6: indent <= 3 空格的 fence 仍有效。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["   ```", "x", "   ```"]
    assert fn(lines) == {1, 2, 3}


def test_fence_6_indented_4_spaces_not_fence():
    """FENCE-6: indent >= 4 空格屬 indented code block（不啟用 fenced 豁免）。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["    ```", "x", "    ```"]
    assert fn(lines) == set(), "4 空格縮排不視為 fenced block"


def test_fence_7_nested_smaller_inner_stays_content():
    """FENCE-7: 內層相同字元 fence 長度 < 外層起始長度，仍屬內容。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["````", "```", "inner", "```", "````"]
    assert fn(lines) == {1, 2, 3, 4, 5}


# ---------- FENCE-EDGE: EDGE-1~12 邊界條件 ----------

def test_edge_1_empty_fenced_block():
    """EDGE-1: 空 fenced block。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "```"]
    assert fn(lines) == {1, 2}


def test_edge_2_language_hint_boundary():
    """EDGE-2: language hint 起始行屬區塊。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```python", "x", "```"]
    assert 1 in fn(lines)


def test_edge_3_tilde_fence_equivalent():
    """EDGE-3 / AC5: tilde fence 與 backtick 等效。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["~~~", "Phase 5 再決定", "~~~"]
    fenced = fn(lines)
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == [], "tilde fence 內 phrase 應豁免"
    assert 2 in fenced


def test_edge_4_4backtick_outer_3backtick_inner_content():
    """EDGE-4: 4-backtick 外層，內部 3-backtick 視為內容。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["````", "```", "Phase 5 再決定", "```", "````"]
    fenced = fn(lines)
    assert fenced == {1, 2, 3, 4, 5}


def test_edge_5_unclosed_to_eof():
    """EDGE-5 / AC7: 未閉合 fence 至檔尾。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "Phase 5 再決定 unclosed", "後續行"]
    assert fn(lines) == {1, 2, 3}


def test_edge_6_backtick_tilde_mixed_unclosed():
    """EDGE-6: backtick 起 + tilde 終 視為不閉合。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "x", "~~~", "y"]
    # tilde 不閉合 backtick → 至檔尾
    assert fn(lines) == {1, 2, 3, 4}


def test_edge_7_indented_fence_not_in_scope():
    """EDGE-7 / AC8: indented fence (>= 4 空格) 不啟用，正常掃描。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["    ```", "    Phase 5 再決定", "    ```"]
    assert fn(lines) == set()
    # phrase 仍命中
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_edge_8_tab_indent_not_fence():
    """EDGE-8 / AC8: Tab 視為 4 空格，不視為 fence。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["\t```", "x", "\t```"]
    assert fn(lines) == set()


def test_edge_9_two_blocks_one_blank_line_between():
    """EDGE-9: 兩個 fenced block 間空行不屬任一區塊。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["```", "a", "```", "", "```", "b", "```"]
    result = fn(lines)
    assert 4 not in result
    assert result == {1, 2, 3, 5, 6, 7}


def test_edge_10_inline_backtick_not_handled():
    """EDGE-10 / AC9: inline backtick 不在範圍，行內延後話術仍命中。"""
    fn = _get_fenced_fn()
    assert fn is not None
    lines = ["這是 inline `Phase 5 再決定` 仍命中"]
    assert fn(lines) == set()
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_edge_11_fenced_exempt_marker_not_collected():
    """EDGE-11 / AC4: fenced block 內 PC-093-exempt 範例不收集為 marker。"""
    lines = [
        "```",
        "<!-- PC-093-exempt: cat:reason -->",
        "<!-- PC-093-exempt: <category>:<reason> -->",
        "```",
    ]
    refs = collect_exempt_markers(lines)
    assert refs == [], "fenced 內範例 marker 不應蒐集，實際: {}".format(refs)


def test_edge_12_fenced_m1_phrase_not_hit():
    """EDGE-12 / AC1: fenced 內 M1 phrase 不命中。"""
    lines = ["```", "Phase 5 再決定", "```"]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == [], "fenced 內 M1 phrase 應整行豁免"


# ---------- FENCE-AC: AC1~AC13 對應驗收 ----------

def test_ac1_m1_m2_m3_all_exempted_in_fence():
    """AC1: fenced 內 M1/M2/M3 三條 BLOCK 規則全豁免。"""
    lines = [
        "```",
        "Phase 5 再決定",  # M1
        "之後再決定處理",  # M2
        "保留 cache 以防萬一",  # M3
        "```",
    ]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == []


def test_ac2_w1_w2_w3_all_exempted_in_fence():
    """AC2: fenced 內 W1/W2/W3 三條 WARN 規則全豁免。"""
    lines = [
        "```",
        "視 baseline 結果再決定",  # W1
        "未來可能需要 cache",  # W2
        "先保留再說",  # W3
        "```",
    ]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == []


def test_ac3_i1_i2_all_exempted_in_fence():
    """AC3: fenced 內 I1/I2 兩條 INFO 規則全豁免。"""
    lines = [
        "```",
        "TODO: Phase 4 決定",  # I1
        "保留擴展彈性",  # I2
        "```",
    ]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == []


def test_ac4_invalid_marker_in_fence_not_audit():
    """AC4: fenced 內格式不符的 PC-093-exempt 範例不誤報 INVALID。"""
    lines = [
        "```",
        "<!-- PC-093-exempt -->",  # 缺 cat:reason
        "<!-- PC-093-exempt: unknown-cat:short -->",  # 非白名單 + 太短
        "```",
    ]
    refs = collect_exempt_markers(lines)
    assert refs == []


def test_ac10_regression_outside_fence_still_hits():
    """AC10 regression: fenced block 外的命中正常運作。"""
    content = _read_fixture("ticket_fenced_basic.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    # Section D "Phase 5 再決定真實命中" 必中
    m1_hits = _hits_by_rule(hits, "M1")
    assert any("真實命中" in h.text or h.line_no >= 20 for h in m1_hits), (
        "區塊外實際命中應保留"
    )


def test_ac11_regression_outside_fence_marker_collected():
    """AC11 regression: fenced block 外實際 exempt marker 正常蒐集。"""
    content = _read_fixture("ticket_fenced_basic.md")
    lines = content.split("\n")
    refs = collect_exempt_markers(lines)
    valid = [r for r in refs if r.valid]
    assert len(valid) >= 1, "Section E 的真實 marker 應被收集"


def test_ac12_integration_multi_mechanism_coexist():
    """AC12: fenced + Schema + REF + 真實命中共存無互相干擾。"""
    content = _read_fixture("ticket_fenced_integration.md")
    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted = partition_hits(hits, markers)
    # 應有「之後再決定 real-hit」殘留為 blocked
    # Hit.text 為 regex 命中片段（中文 phrase），real-hit 為 fixture 行內 marker
    # 採與 test_ac10 同模式：line_no 或 text 任一含 marker 即可（PC-093 fixture 慣例）
    real_hit_line = next(
        (i for i, l in enumerate(lines, start=1) if "real-hit" in l), None
    )
    assert real_hit_line is not None, "fixture 應含 real-hit 標記行"
    assert any(
        h.line_no == real_hit_line or "real-hit" in h.text for h in blocked
    ), "fenced/schema/ref 機制不應誤豁免實際命中 (real-hit 行)"
    # 不應有 fenced 內範例命中（fenced-example marker 行不應出現任一 hit）
    fenced_example_lines = {
        i for i, l in enumerate(lines, start=1) if "fenced-example" in l
    }
    for h in hits:
        assert h.line_no not in fenced_example_lines, (
            "fenced 內範例不應命中（line {} 應屬 fenced 豁免）".format(h.line_no)
        )


def test_ac13_fence_self_line_not_phrase_hit():
    """AC13: fence 起始行（含 language hint）與結束行不被 phrase 掃描誤判。"""
    lines = ["```python", "code", "```"]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    # fence 自身行不含 phrase（無 Phase X / 之後 等），本來就不會命中
    # 此測試確保 fence 行被 fenced_lines 涵蓋（即使將來 phrase regex 擴張也安全）
    assert hits == []


# ---------- FENCE-INTEG: main() 整合 ----------

def test_integ_fenced_only_block_main_exit_0(monkeypatch, capsys, mock_find_ticket):
    """fenced block 內含 BLOCK phrase 範例 + 區塊外無命中 → main exit 0。"""
    mock_find_ticket("ticket_fenced_basic.md")
    # 但 ticket_fenced_basic.md 區塊外有 Section D "真實命中" → 應 exit 2
    # 改用獨立 fixture：只有 fenced 範例，無區塊外命中
    pass  # 此測試由下方 ac12 整合替代


def test_integ_fenced_unclosed_exempts_to_eof(monkeypatch, capsys, mock_find_ticket):
    """EDGE-5 整合：未閉合 fence 至檔尾豁免，main exit 0。"""
    mock_find_ticket("ticket_fenced_unclosed.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0, "未閉合 fence 內全部豁免，不應觸發 BLOCK"
    assert err == ""


def test_integ_fenced_integration_main_blocks_real_hit(monkeypatch, capsys, mock_find_ticket):
    """AC12 整合：fenced/schema/ref 共存時，僅實際命中觸發 BLOCK。"""
    mock_find_ticket("ticket_fenced_integration.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 2, "real-hit 應觸發 BLOCK"
    # err 包含命中 line_no；驗證 real-hit 行有出現於 block 訊息（line {n} 格式）
    content = _read_fixture("ticket_fenced_integration.md")
    fixture_lines = content.split("\n")
    real_hit_line = next(
        (i for i, l in enumerate(fixture_lines, start=1) if "real-hit" in l), None
    )
    assert real_hit_line is not None
    assert "line {}".format(real_hit_line) in err, (
        "real-hit 行（line {}）應出現於 BLOCK 訊息".format(real_hit_line)
    )
    # fenced 範例（fenced-example marker 所在行）不應出現於錯誤訊息
    fenced_example_lines = [
        i for i, l in enumerate(fixture_lines, start=1) if "fenced-example" in l
    ]
    for ln in fenced_example_lines:
        assert "line {}".format(ln) not in err, (
            "fenced 範例行 {} 不應出現於 BLOCK 訊息".format(ln)
        )


# ============================================================================
# W1-092 — YAML Frontmatter 區塊跳過（PC-142 case 5 修復）
# ============================================================================

compute_frontmatter_lines = _hook.compute_frontmatter_lines


def test_w1_092_frontmatter_lines_basic():
    """基本案例：第一行 `---` 起，到下一個 `---` 止，含起訖行。"""
    lines = [
        "---",
        "id: 0.19.0-W1-039",
        "title: foo",
        "---",
        "",
        "## Body",
    ]
    fm = compute_frontmatter_lines(lines)
    assert fm == {1, 2, 3, 4}


def test_w1_092_frontmatter_phrase_inside_skipped():
    """frontmatter why 含 source ticket history 引用「Phase 4 評估」「Phase 5 再決定」不應命中。"""
    lines = [
        "---",
        "id: 0.19.0-W1-039",
        "why: source ticket W1-029.1 的 Phase 4 評估發現，禁止 Phase 5 再決定",
        "---",
        "",
        "## Solution",
        "正常實作",
    ]
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    assert hits == [], (
        "frontmatter 內 Phase 4/5 字面屬結構化元資料，不應命中，實際: {}".format(hits)
    )


def test_w1_092_body_phrase_outside_frontmatter_still_hits():
    """純內文 Phase 4 / Phase 5 仍應命中（regression guard）。"""
    lines = [
        "---",
        "id: 0.19.0-W1-039",
        "title: foo",
        "---",
        "",
        "## Solution",
        "Phase 4 再決定是否保留 use_cache",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1, "內文 M1 仍應命中（regression），實際: {}".format(hits)
    assert m1[0].line_no == 7


def test_w1_092_body_separator_dash_dash_dash_not_terminating_frontmatter():
    """PM WRAP P 防護：邊界匹配限「行首僅有 `---` 三字元」，內文 `---` 水平分隔符
    不應被視為 frontmatter 結束，否則內文 phrase 會被誤豁免。"""
    lines = [
        "---",
        "id: 0.19.0-W1-039",
        "---",
        "",
        "## Section",
        "正常段落",
        "",
        "---",  # 水平分隔符
        "",
        "Phase 4 再決定 (內文，應命中)",
    ]
    fm = compute_frontmatter_lines(lines)
    # 應為 1-3，不可延伸到 line 8
    assert fm == {1, 2, 3}, "frontmatter 應終止於 line 3，實際: {}".format(fm)
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1 and m1[0].line_no == 10, (
        "內文 line 10 的 Phase 4 仍應命中，實際: {}".format(hits)
    )


def test_w1_092_no_frontmatter_returns_empty():
    """檔案第一行非 `---` → 視為無 frontmatter，回傳空集合。"""
    lines = [
        "# Title",
        "Phase 4 再決定",
    ]
    assert compute_frontmatter_lines(lines) == set()


def test_w1_092_unclosed_frontmatter_returns_empty():
    """未閉合 frontmatter（無第二個 `---`）→ 回傳空集合（容錯）。"""
    lines = [
        "---",
        "id: foo",
        "title: bar",
    ]
    assert compute_frontmatter_lines(lines) == set()


def test_w1_092_frontmatter_exempt_marker_not_collected():
    """frontmatter 內 PC-093-exempt 標記不應被蒐集（YAML 非豁免宣告載體）。"""
    lines = [
        "---",
        "title: <!-- PC-093-exempt: ticket-tracked:W1-039 引用 -->",
        "---",
        "",
        "## Body",
        "<!-- PC-093-exempt: ticket-tracked:W1-039 真實 marker -->",
    ]
    refs = collect_exempt_markers(lines)
    assert len(refs) == 1, "frontmatter 內 marker 不應蒐集，實際: {}".format(refs)
    assert refs[0].line_no == 6
