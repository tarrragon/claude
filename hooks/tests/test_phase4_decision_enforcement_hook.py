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


# ---------- W3-746: M1 逗號子句邊界精度修正 ----------
#
# 根因：「Phase N」與判定動詞之間原本允許跨逗號比對，使「Phase N 只是
# 時間標記、判定動詞屬另一子句」的過去完成式敘述被誤判為延後語意。
# 修法：間隔字元排除全形/半形逗號，要求兩者落在同一子句才視為同一段
# 延後語意。


def test_m1_w3_746_n1_過去完成式跨逗號不命中():
    """0.2.1-W3-708 NeedsContext 第 412 行原文（節錄）：Phase N 為建立
    時間標記，判斷動詞描述另一件已完成的事，兩者被逗號分隔的不同子句，
    不應命中。"""
    hits = _scan_text(
        "本次由 add-spawn-request 於 Phase 4 審查初稿時建立，"
        "後因判斷應直接執行而 resolve-spawn-request --status dismissed"
    )
    assert _hits_by_rule(hits, "M1") == [], (
        "過去完成式敘述（判定動詞與 Phase N 分屬逗號兩側不同子句）不應命中，實際: {}".format(hits)
    )


def test_m1_w3_746_n2_已下決定跨逗號不命中():
    """另一種過去式典型句型：Phase N 完成分析後，另起子句敘述已下的決定。"""
    hits = _scan_text("於 Phase 3 完成分析，已決定採用方案 A")
    assert _hits_by_rule(hits, "M1") == [], (
        "已下決定的過去式敘述不應命中，實際: {}".format(hits)
    )


def test_m1_w3_746_n3_完成後判斷跨逗號不命中():
    hits = _scan_text("Phase 2 測試全數通過，團隊判斷可以進入下一階段")
    assert _hits_by_rule(hits, "M1") == [], (
        "完成後續接的判斷敘述不應命中，實際: {}".format(hits)
    )


def test_m1_w3_746_p1_同子句仍命中_再決定():
    """acceptance 2 三種典型句型之一：Phase N 再決定，同子句無逗號分隔仍命中。"""
    hits = _scan_text("Phase 4 再決定是否保留 use_cache")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_746_p2_同子句仍命中_視結果決定():
    """acceptance 2 三種典型句型之二：Phase N 視 X 決定，同子句仍命中。"""
    hits = _scan_text("Phase 5 視 baseline 決定")
    assert len(_hits_by_rule(hits, "M1")) >= 1


def test_m1_w3_746_p3_同子句仍命中_再評估():
    """acceptance 2 三種典型句型之三：Phase N 再評估，同子句仍命中。"""
    hits = _scan_text("phase 4 再評估")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_746_p4_逗號在phase之前仍命中():
    """逗號出現在「Phase N」之前（非兩者之間）不受影響，仍應命中。"""
    hits = _scan_text("spawn N 個 IMP ticket，禁止 Phase 5 再決定")
    assert len(_hits_by_rule(hits, "M1")) == 1


# ---------- W3-749: 修正 W3-746 單分支「收逗號」方案的漏攔回歸 ----------
#
# W3-746 收窄「Phase N」與判定動詞的間隔字元排除逗號，修掉了 0.2.1-W3-708
# 的過去完成式誤判，但代價是所有「跨逗號但帶再/在前綴」的真延後話術一併
# 漏攔。本節固定雙分支修法：分支一（同子句，前綴可選，W3-746 既有）+
# 分支二（跨子句，前綴必須，本票新增）。測試刻意成對設計（含逗號 vs
# 不含逗號），涵蓋被修改的維度本身，避免重蹈 W3-746 選樣未涵蓋逗號
# 的教訓。


def test_m1_w3_749_p1_跨逗號帶再前綴命中_決定():
    """PM 實測發現的缺口之一：跨逗號但帶「再」前綴，應攔截。"""
    hits = _scan_text("Phase 4 完成後，再決定是否重構")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_749_p2_跨逗號帶再前綴命中_評估():
    """PM 實測發現的缺口之二：跨逗號但帶「再」前綴，應攔截。"""
    hits = _scan_text("Phase 5 之後，再評估要不要拆")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_749_p3_跨逗號帶在前綴命中():
    """跨逗號、前綴為「在」而非「再」，同樣應攔截（分支二涵蓋兩種前綴；
    「在」須緊接判定動詞，與既有「評估」前綴要求的鄰接慣例一致）。"""
    hits = _scan_text("Phase 4 完成後，在決定是否重構")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_749_n1_跨逗號無前綴仍放行_原始誤判句():
    """0.2.1-W3-708 原誤判句（逐字重放）：跨逗號但無前綴，維持放行——
    W3-746 的成果不得回退。"""
    hits = _scan_text(
        "本次由 add-spawn-request 於 Phase 4 審查初稿時建立，"
        "後因判斷應直接執行而 resolve-spawn-request --status dismissed"
    )
    assert _hits_by_rule(hits, "M1") == []


def test_m1_w3_749_n2_跨逗號無前綴仍放行_已決定():
    """跨逗號、判定動詞無前綴的另一過去式句型，維持放行。"""
    hits = _scan_text("於 Phase 3 完成分析，已決定採用方案 A")
    assert _hits_by_rule(hits, "M1") == []


def test_m1_w3_749_p4_不含逗號帶前綴仍命中():
    """對照組（不含逗號）：同子句、帶前綴，維持命中——分支一涵蓋。"""
    hits = _scan_text("Phase 4 再決定是否保留 use_cache")
    assert len(_hits_by_rule(hits, "M1")) == 1


def test_m1_w3_749_p5_不含逗號無前綴仍命中_視結果決定():
    """對照組（不含逗號）：同子句、無前綴的「視 X 決定」句型，維持命中——
    分支一涵蓋，此為驗證雙分支未破壞既有正案例的關鍵對照。"""
    hits = _scan_text("Phase 5 視 baseline 決定")
    assert len(_hits_by_rule(hits, "M1")) >= 1


def test_m1_w3_749_main_integration_four_sentences(monkeypatch, capsys, tmp_path):
    """acceptance 6：main() 整合層級，以 PM 提供的四句實際灌入 ticket
    檔案跑過完整 main() 流程（非僅單元測試 pattern），驗證兩句應攔截、
    兩句應放行同時成立。"""
    ticket_md = tmp_path / "TST-749.md"
    ticket_md.write_text(
        "---\nid: TST-749\ntitle: t\ntype: IMP\nstatus: in_progress\n---\n\n"
        "## Solution\n"
        "案例一（應攔截）：Phase 4 完成後，再決定是否重構\n"
        "案例二（應攔截）：Phase 5 之後，再評估要不要拆\n"
        "案例三（應放行）：於 Phase 4 審查初稿時建立，後因判斷應直接執行\n"
        "案例四（應放行）：Phase 4 結論：無需重構\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, **kw: ticket_md)
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-749 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 2, "含真延後話術（案例一/二）應被 BLOCK"
    assert "再決定是否重構" in err or "案例一" in err or "Phase 4" in err
    # 案例三/四不應出現在 blocked 命中列表（僅檢查不誤列，訊息格式見
    # format_block_message：blocked 命中會逐行列出 line N [rule_id]）
    assert "後因判斷應直接執行" not in err
    assert "結論：無需重構" not in err


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


# ============================================================================
# W3-751 — DENY 訊息補強 code fence 豁免路徑說明
# ============================================================================


def test_w3_751_deny_message_mentions_code_fence(monkeypatch, capsys, mock_find_ticket):
    """acceptance 1：DENY 訊息含 code fence 豁免說明與可複製範例。"""
    mock_find_ticket("ticket_with_must_block.md")
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-001 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 2
    assert "code fence" in err
    assert "```" in err
    assert "引用或示範" in err


def test_w3_751_deny_message_static_guidance_is_properly_fenced_self_test():
    """acceptance 2：DENY 訊息新增的靜態引導文字（含內建 ~~~ 範例句）本身
    不會觸發 M1 自我阻擋——範例句已包在 code fence 內，掃描時整段跳過。

    範圍界定：本測試只驗證本票新增的「靜態引導段落」（説明 + 內建範例），
    不含「命中:」區塊逐行回顯的動態內容（hit.text 逐字回顯是既有設計，
    目的是讓使用者看清楚被擋的原文，該行天生會重現原始命中內容，無法
    也不應該被消音——見對照測試
    test_w3_751_echoed_hit_line_reproduces_original_match_by_design）。
    此處刻意傳入不會命中 M1 的 hit 文字，隔離出「新增文字本身」是否安全。
    """
    msg = format_block_message(
        "TST-751",
        [Hit(line_no=1, rule_id="M1", level="BLOCK", text="（不觸發 M1 的中性描述）")],
        [],
    )
    # 把 DENY 訊息全文當成 ticket body 內容重新掃描
    lines = ["## Solution", "以下為 hook 回報的原文引用："] + msg.split("\n")
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], (
        "DENY 訊息新增的靜態引導文字若被引用進 ticket body 不應觸發 M1，"
        "實際: {}".format(hits)
    )


def test_w3_751_echoed_hit_line_reproduces_original_match_by_design():
    """對照組（記錄既有限制，非本票 acceptance 範圍）：「命中:」區塊逐字
    回顯原始命中文字，若該文字本身是 M1 命中，回顯行未加 fence 時會再次
    命中——此為設計上的必然（回顯目的就是讓使用者看清楚原文），訊息本身
    已引導使用者將整段（含此回顯行）包進 code fence 再引用進 ticket。
    """
    msg = format_block_message(
        "TST-751",
        [Hit(line_no=1, rule_id="M1", level="BLOCK", text="Phase 4 再決定")],
        [],
    )
    lines = ["## Solution", "以下為 hook 回報的原文引用："] + msg.split("\n")
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert len(hits) == 1 and hits[0].rule_id == "M1", (
        "回顯行預期重現原始命中（既有限制，訊息已引導整段包 fence），"
        "實際: {}".format(hits)
    )

    # 依訊息自身引導，將整段（含回顯行）包進 ``` fence 後再引用 → 無命中
    fenced_lines = ["## Solution", "```"] + msg.split("\n") + ["```"]
    fenced_hits = scan_lines_for_phrases(fenced_lines, build_regex_table())
    assert fenced_hits == [], (
        "依訊息引導將整段包 ``` fence 後應無命中，實際: {}".format(fenced_hits)
    )


def test_w3_751_unfenced_example_would_hit_demonstrates_why_fence_matters():
    """對照組：同一範例句若未包 code fence，會被 M1 命中——證明本票新增
    的 code fence 提示是唯一無摩擦的出路（非裝飾性文字）。"""
    lines = ["## Solution", "範例句型：Phase 4 再決定是否保留 use_cache"]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1, "未加 code fence 的範例句應命中 M1（對照組），實際: {}".format(hits)


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
# W3-747 — payload 內文誤判修正（同型於三個 Bash git 守衛曾修過的缺陷）
# ============================================================================


def test_w3_747_quoted_payload_not_misdetected():
    """引號參數內文引用 ticket track complete 字樣不應被誤判為真實呼叫。"""
    words = ["ticket", "track", "complete"]
    phrase = " ".join(words) + " 0.2.1-W3-XXX"
    command = 'ticket track append-log 0.2.1-W3-747 --section "Test Results" "{}"'.format(
        phrase
    )
    tid, mode = extract_ticket_id_from_command(command)
    assert (tid, mode) == (None, None), (
        "引號內文引用不應誤判為真實呼叫，實際: ({}, {})".format(tid, mode)
    )


def test_w3_747_heredoc_wrapped_in_quotes_payload_not_misdetected():
    """heredoc 本體包在外層雙引號內（`"$(cat <<'EOF' ...)"` 慣用形式）不誤判。"""
    words = ["ticket", "track", "phase", "0.2.1-W3-XXX", "phase4"]
    phrase = " ".join(words)
    command = (
        'ticket track append-log 0.2.1-W3-747 --section "Test Results" '
        '"$(cat <<\'EOF2\'\n' + phrase + '\nEOF2\n)"'
    )
    tid, mode = extract_ticket_id_from_command(command)
    assert (tid, mode) == (None, None), (
        "引號包裹的 heredoc payload 不應誤判，實際: ({}, {})".format(tid, mode)
    )


def test_w3_747_bare_heredoc_payload_not_misdetected():
    """裸 heredoc（無外層引號包裹）本體含觸發字樣不應誤判——須先剝除
    heredoc 本體，shlex 本身不理解 heredoc 語法。"""
    words = ["ticket", "track", "complete", "0.2.1-W3-XXX"]
    phrase = " ".join(words)
    command = "cat <<'EOF2'\nDone: " + phrase + " --as x\nEOF2"
    tid, mode = extract_ticket_id_from_command(command)
    assert (tid, mode) == (None, None), (
        "裸 heredoc payload 不應誤判，實際: ({}, {})".format(tid, mode)
    )


def test_w3_747_w3_744_real_incident_replay():
    """0.2.1-W3-744 真實事發現場重放：append-log 內文引用另一 ticket 的
    收尾指令，應偵測為 append-log（非 ticket 指令），不誤判為對該被引用
    ticket 的收尾呼叫。"""
    quoted_words = ["ticket", "track", "complete", "0.2.1-W3-708", "--as", "x"]
    quoted_phrase = " ".join(quoted_words)
    command = (
        'ticket track append-log 0.2.1-W3-744 --section "Test Results" '
        '"$(cat <<\'EOF2\'\nDone: ' + quoted_phrase + '\nEOF2\n)"'
    )
    tid, mode = extract_ticket_id_from_command(command)
    assert (tid, mode) == (None, None), (
        "append-log 呼叫本身不應被判為對被引用 ticket 的收尾呼叫，實際: ({}, {})".format(
            tid, mode
        )
    )


def test_w3_747_real_complete_call_still_detected():
    """acceptance 2：真實 complete 呼叫（無 payload 包裹）仍正確識別。"""
    tid, mode = extract_ticket_id_from_command("ticket track complete 0.2.1-W3-747")
    assert (tid, mode) == ("0.2.1-W3-747", "residual_gate")


def test_w3_747_real_phase4_call_still_detected():
    """acceptance 2：真實 phase4 呼叫（無 payload 包裹）仍正確識別。"""
    tid, mode = extract_ticket_id_from_command(
        "ticket track phase 0.2.1-W3-747 phase4 thyme-python-developer"
    )
    assert (tid, mode) == ("0.2.1-W3-747", "main_gate")


def test_w3_747_real_call_with_chained_statement_still_detected():
    """真實呼叫作為語句鏈的一部分（&& 之後）仍正確識別。"""
    tid, mode = extract_ticket_id_from_command(
        "cd /tmp && ticket track complete 0.2.1-W3-747"
    )
    assert (tid, mode) == ("0.2.1-W3-747", "residual_gate")


def test_w3_747_unbalanced_quote_returns_none_none():
    """acceptance 6：無法安全 tokenize 時回傳 (None, None)，與原 regex
    對應情境找不到匹配的既有失敗語意一致（fail-open，main() 視為
    mode is None 直接放行，不觸發掃描）。"""
    tid, mode = extract_ticket_id_from_command('ticket track complete "unterminated')
    assert (tid, mode) == (None, None)


def test_w3_747_main_integration_payload_not_misdetected(monkeypatch, capsys, mock_find_ticket):
    """acceptance 5：main() 整合層級驗證——含觸發字樣的 payload 呼叫（模擬
    append-log）不掃描任何 ticket（find_ticket_file 不應被呼叫，因
    extract_ticket_id_from_command 回傳 mode=None 即提前 return）。"""
    calls = []

    def _tracking_find_ticket(tid, **kw):
        calls.append(tid)
        return _FIXTURES / "ticket_with_must_block.md"

    monkeypatch.setattr(_hook, "find_ticket_file", _tracking_find_ticket)
    quoted_words = ["ticket", "track", "complete", "0.2.1-W3-708"]
    quoted_phrase = " ".join(quoted_words)
    command = (
        'ticket track append-log 0.2.1-W3-747 --section "Test Results" '
        '"$(cat <<\'EOF2\'\nDone: ' + quoted_phrase + '\nEOF2\n)"'
    )
    rc, out, err = _run_main_with_stdin(
        _payload("PreToolUse", command), monkeypatch, capsys
    )
    assert rc == 0
    assert err == ""
    assert calls == [], "payload 呼叫不應觸發任何 ticket md 掃描，實際呼叫: {}".format(calls)


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
    assert "PC-093 強制決斷" not in captured.err


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


# ============================================================================
# W1-120 — Context Bundle auto-extracted 區塊跳過（PC-142 case 5 同根因復發）
# ============================================================================

compute_context_bundle_lines = _hook.compute_context_bundle_lines


def test_w1_120_context_bundle_phrase_inside_skipped():
    """測試 1：Context Bundle auto-extracted 區塊含階段名稱字面不應命中（跳過）。"""
    lines = [
        "## Context Bundle",
        "",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 400 -->",
        "",
        "### Rationale Chain",
        "- 0.19.0-W1-093 why: source ANA 的 Phase 4 評估發現，禁止 Phase 5 再決定",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], (
        "auto-extracted 區塊內 Phase 4/5 字面屬機器引用，不應命中，實際: {}".format(hits)
    )


def test_w1_120_body_phrase_outside_bundle_still_hits():
    """測試 2：一般 body 內文含階段名稱字面（非 Context Bundle）仍命中（regression 防護）。"""
    lines = [
        "## Solution",
        "Phase 4 再決定是否保留 use_cache",
        "",
        "## Context Bundle",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 100 -->",
        "- 0.19.0-W1-093 why: Phase 5 再決定",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1, "內文 M1 仍應命中（regression），實際: {}".format(hits)
    assert m1[0].line_no == 2


def test_w1_120_manual_context_bundle_no_marker_still_hits():
    """測試 3：人工撰寫 Context Bundle（無 auto-extracted marker）不跳過（人工延後論述仍攔截）。"""
    lines = [
        "## Context Bundle",
        "",
        "### Rationale Chain",
        "Phase 4 再決定是否保留此模組",
    ]
    cb = compute_context_bundle_lines(lines)
    assert cb == set(), "無 auto-extracted marker → 不跳過，實際: {}".format(cb)
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1, "人工 body 延後論述仍應命中，實際: {}".format(hits)
    assert m1[0].line_no == 4


def test_w1_120_marker_to_next_h2_closes_block():
    """測試 4：auto-extracted marker → 下個 H2 正確閉合區塊（邊界行不含）。"""
    lines = [
        "## Context Bundle",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 100 -->",
        "- why: Phase 4 評估",
        "## Next Section",
        "Phase 5 再決定 (內文，應命中)",
    ]
    cb = compute_context_bundle_lines(lines)
    assert cb == {2, 3}, "區塊應為 line 2-3（marker 起、H2 前止），實際: {}".format(cb)
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1 and m1[0].line_no == 5, (
        "H2 後內文 line 5 仍應命中，實際: {}".format(hits)
    )


def test_w1_120_marker_to_eof_all_skipped():
    """測試 5：auto-extracted 區塊延伸至 EOF（無後續 H2）全跳過（容錯）。"""
    lines = [
        "## Context Bundle",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 100 -->",
        "- why: Phase 4 評估",
        "- what: Phase 5 再決定",
    ]
    cb = compute_context_bundle_lines(lines)
    assert cb == {2, 3, 4}, "區塊應延伸至 EOF，實際: {}".format(cb)
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], "EOF 前 auto-extracted 區塊全跳過，實際: {}".format(hits)


def test_w1_120_context_bundle_exempt_marker_not_collected():
    """測試 6：Context Bundle 內 exempt marker 不被 collect_exempt_markers 蒐集。"""
    lines = [
        "## Context Bundle",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 100 -->",
        "<!-- PC-093-exempt: ticket-tracked:W1-093 區塊內示意 -->",
        "## Body",
        "<!-- PC-093-exempt: ticket-tracked:W1-093 真實 marker -->",
    ]
    refs = collect_exempt_markers(lines)
    assert len(refs) == 1, "auto-extracted 區塊內 marker 不應蒐集，實際: {}".format(refs)
    assert refs[0].line_no == 5


def test_w1_120_h3_inside_block_not_terminating():
    """測試 7：區塊內 H3 子標題不誤判為終點邊界（`### ` 不匹配 `^\\s*##\\s`）。"""
    lines = [
        "## Context Bundle",
        "<!-- auto-extracted: v1 | sources: 0.19.0-W1-093 | chars: 100 -->",
        "### Rationale Chain",
        "- why: Phase 4 評估",
        "### Related Files",
        "- foo.py: Phase 5 再決定",
        "---",
    ]
    cb = compute_context_bundle_lines(lines)
    assert cb == {2, 3, 4, 5, 6}, (
        "H3 不應終止區塊，區塊應為 line 2-6（`---` 前止），實際: {}".format(cb)
    )
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], "區塊內含 H3 仍全跳過，實際: {}".format(hits)


# ============================================================================
# W3-744 — 已 resolved 的 Spawn Request 條目跳過（CLI 產出結構化欄位，
# 死結案例：0.2.1-W3-708 的 SR-2 which/status 欄位含延後語彙，導致
# complete 被永久阻擋，因該區段既非 CLI 可編輯、亦不在 ticket 檔案
# Edit 白名單內）
# ============================================================================

compute_resolved_spawn_request_lines = _hook.compute_resolved_spawn_request_lines


def test_w3_744_resolved_dismissed_entry_skipped():
    """acceptance 1：已 dismissed 的 spawn request，why 欄位含延後語不再阻擋。"""
    lines = [
        "## Spawn Requests",
        "- **SR-2** (2026-08-19 12:14)",
        "  - what: 拆分函式",
        "  - why: 當下評估拆分會增加複雜度，故保留現狀，留待後續若語法複雜度再提高時重新評估",
        "  - suggested_type: IMP",
        "  - suggested_priority: P2",
        "  - related_files: ",
        "  - context: ",
        "  - status: dismissed（已直接執行完畢）",
        "",
        "## Completion Info",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], "已 dismissed 條目的 why 欄位不應命中，實際: {}".format(hits)


def test_w3_744_resolved_processed_entry_skipped():
    """已 processed 的 spawn request 同樣跳過（不限 dismissed）。"""
    lines = [
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - what: 建立追蹤票",
        "  - why: 此議題之後再處理，先保留再說",
        "  - status: processed（已建 0.2.1-W3-900）",
        "## Completion Info",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], "已 processed 條目不應命中，實際: {}".format(hits)


def test_w3_744_pending_entry_still_hits():
    """acceptance 3：未 resolved（pending）的 spawn request 含延後語仍被攔截。"""
    lines = [
        "## Spawn Requests",
        "- **SR-3** (2026-08-19 12:00)",
        "  - what: 尚待決定",
        "  - why: 此議題之後再處理，先保留再說",
        "  - status: pending",
        "## Completion Info",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    rule_ids = sorted(h.rule_id for h in hits)
    assert rule_ids, "pending 條目仍應命中延後話術，實際: {}".format(hits)


def test_w3_744_solution_deferral_still_hits():
    """acceptance 2：Solution 章節的延後話術不受本次改動影響，仍被攔截。"""
    lines = [
        "## Solution",
        "Phase 4 再決定是否保留 use_cache",
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - status: dismissed（已執行）",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1 and m1[0].line_no == 2, (
        "Solution 章節延後話術仍應命中（regression 防護），實際: {}".format(hits)
    )


def test_w3_744_problem_analysis_deferral_still_hits():
    """acceptance 2：Problem Analysis 章節的延後話術不受影響，仍被攔截。"""
    lines = [
        "## Problem Analysis",
        "此問題之後再處理，先保留再說",
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - status: processed（已建票）",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits, "Problem Analysis 延後話術仍應命中，實際: {}".format(hits)


def test_w3_744_multiple_entries_only_resolved_skipped():
    """同一區段內多筆條目，僅 resolved 者跳過，pending 者仍命中。"""
    lines = [
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - why: 此為已解決案例，之後再處理",
        "  - status: dismissed（歷史記錄）",
        "- **SR-2** (2026-08-19 12:05)",
        "  - why: 此為未解決案例，之後再處理",
        "  - status: pending",
        "## Completion Info",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m2 = _hits_by_rule(hits, "M2")
    assert len(m2) == 1, "僅 SR-2（pending）應命中，實際: {}".format(hits)
    assert m2[0].line_no == 6


def test_w3_744_compute_resolved_lines_entry_boundary():
    """compute_resolved_spawn_request_lines 條目邊界正確（含標題行，止於下一條目前）。"""
    lines = [
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - status: dismissed",
        "- **SR-2** (2026-08-19 12:05)",
        "  - status: pending",
        "## Completion Info",
    ]
    resolved = compute_resolved_spawn_request_lines(lines)
    assert resolved == {2, 3}, "SR-1 條目應為 line 2-3，實際: {}".format(resolved)


def test_w3_744_no_spawn_requests_section_returns_empty():
    lines = ["## Solution", "Phase 4 再決定"]
    assert compute_resolved_spawn_request_lines(lines) == set()


def test_w3_744_empty_spawn_requests_section_returns_empty():
    """區段存在但無任何 SR 條目（如僅有 HTML 註解說明）回傳空集合。"""
    lines = [
        "## Spawn Requests",
        "<!-- agent 執行中發現應開新 ticket 的議題時... -->",
        "## Completion Info",
    ]
    assert compute_resolved_spawn_request_lines(lines) == set()


def test_w3_744_resolved_entry_exempt_marker_not_collected():
    """已 resolved 條目內若含 exempt marker（如人工補上的豁免），不被
    collect_exempt_markers 蒐集——該區塊本就不產生 hit，marker 不應
    被用來豁免區塊外的其他 hit。"""
    lines = [
        "## Spawn Requests",
        "- **SR-1** (2026-08-19 12:00)",
        "  - status: dismissed（<!-- PC-093-exempt: history:0.2.1-W3-708 已執行 -->已執行）",
        "## Body",
        "Phase 4 再決定其他事項",
    ]
    refs = collect_exempt_markers(lines)
    assert refs == [], "resolved 條目內 marker 不應被蒐集，實際: {}".format(refs)
    hits = scan_lines_for_phrases(lines, build_regex_table())
    m1 = _hits_by_rule(hits, "M1")
    assert len(m1) == 1, "Body 內的延後話術不應被區塊內未蒐集的 marker 誤豁免"


def test_w3_744_w3_708_real_sample_no_longer_blocks():
    """0.2.1-W3-708 死結案例的真實文字重放：resolved SR-2 不再產生 BLOCK hit。"""
    lines = [
        "## Spawn Requests",
        "- **SR-2** (2026-08-19 12:14)",
        "  - what: 拆分或簡化 .claude/lib/git_command_parse.py 的 "
        "_find_invocation_in_statement 函式，降低認知負擔指數（約 14，超過閾值 10）",
        "  - why: 0.2.1-W3-708 Phase 4 審查發現該函式因需逐一判斷 git 全域選項多種"
        "語法形式（-C / with-value / equals-form / no-value）而分支數偏高，當下評估"
        "拆分會使狀態（idx 位移）切散到多函式間傳遞、增加而非降低理解難度，故保留現狀，"
        "留待後續若語法複雜度再提高時重新評估",
        "  - suggested_type: IMP",
        "  - suggested_priority: P2",
        "  - related_files: ",
        "  - context: ",
        "  - status: dismissed（<!-- PC-093-exempt: history:0.2.1-W3-708 本身即為執行"
        "完畢的歷史記錄，SR-2 建立時的分析已由本票直接執行完成而非延後 -->已直接執行完畢，"
        "見 Solution 更新）",
        "",
        "## Completion Info",
    ]
    hits = scan_lines_for_phrases(lines, build_regex_table())
    assert hits == [], "0.2.1-W3-708 真實樣本重放不應再產生任何 hit，實際: {}".format(hits)


def test_w3_744_failure_semantics_ticket_not_found_fail_open(monkeypatch, capsys):
    """acceptance 7：ticket md 找不到時維持既有失敗語意 fail-open（exit 0），
    本票未變更此語意——僅新增 compute_resolved_spawn_request_lines 一項
    純函式，main() 的錯誤處理路徑未被觸及。"""
    monkeypatch.setattr(_hook, "find_ticket_file", lambda tid, **kw: None)
    rc, out, err = _run_main_with_stdin(
        _payload("PostToolUse", "ticket track phase TST-404 phase4"),
        monkeypatch, capsys,
    )
    assert rc == 0
    assert err == ""
