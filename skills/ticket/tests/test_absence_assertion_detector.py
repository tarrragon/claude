"""缺席斷言未查證提示（承接 PC-BAL-053）。

Why: 同一 session 內連續兩次以「同名檔案全庫搜尋不到」為前提直接判定
「功能缺口」，事後查證皆被推翻，兩次判斷共同漏掉 PC-BAL-053 記載的第三層
「反向搜尋層」。建票當下即時提示，可在源頭把「這裡查過了嗎」放到眼前。

設計：提示不阻擋（比照 machine_path_detector / spec_reference_checker 的
輕量提示定位）——缺席斷言有時是對的，阻擋會產生誤報並被繞過。判定以「同一
欄位」為單位：查證痕跡若寫在別的欄位不算數。
"""

from ticket_system.lib.absence_assertion_detector import (
    detect_unverified_absence_claims,
    find_unverified_absence_claims,
)


# ============================================================
# 單元：find_unverified_absence_claims 欄位級判定
# ============================================================


def test_absence_keyword_without_verification_trace_hits_field():
    ticket = {"why": "該檔案自建立起從未存在於工作區。", "what": "處置缺失腳本"}
    assert find_unverified_absence_claims(ticket) == ["why"]


def test_absence_keyword_with_verification_trace_in_same_field_not_hit():
    """查證痕跡與缺席斷言同段時不觸發（PC-BAL-053 第三層已完成）。"""
    ticket = {
        "why": "此腳本從未存在（git log 全歷史無此路徑、settings.json 無事件註冊）。",
        "what": "建立缺失腳本",
    }
    assert find_unverified_absence_claims(ticket) == []


def test_verification_trace_in_different_field_does_not_count():
    """查證痕跡寫在另一欄位不算數——讀者不該自行拼湊散落線索。"""
    ticket = {
        "why": "該 Hook 已移除。",
        "what": "已完成反向搜尋層查證，settings.json 無事件註冊",
    }
    assert find_unverified_absence_claims(ticket) == ["why"]


def test_both_fields_can_hit_independently():
    ticket = {
        "why": "查無同名檔案。",
        "what": "該功能無接手者",
    }
    assert find_unverified_absence_claims(ticket) == ["why", "what"]


def test_no_absence_keyword_no_hit():
    ticket = {"why": "路徑已更名為新檔案。", "what": "更新文件引用"}
    assert find_unverified_absence_claims(ticket) == []


def test_non_string_or_missing_field_ignored():
    assert find_unverified_absence_claims({"why": None, "what": 123}) == []
    assert find_unverified_absence_claims({}) == []


def test_non_dict_input_returns_empty():
    assert find_unverified_absence_claims(None) == []
    assert find_unverified_absence_claims("從未存在") == []


# ============================================================
# 單元：detect_unverified_absence_claims 提示文字
# ============================================================


def test_hint_names_third_layer_reverse_search():
    """提示文字必須點名第三層反向搜尋層，否則等於沒寫（PC-BAL-053 教訓）。"""
    ticket = {"why": "該腳本從未實作。"}
    hints = detect_unverified_absence_claims(ticket)
    assert len(hints) == 1
    assert "反向搜尋層" in hints[0]
    assert "settings.json" in hints[0]
    assert "合併" in hints[0]


def test_hint_does_not_block_only_prints():
    """提示為軟性引導，不改變回傳值語意（呼叫端仍是 List[str] 提示清單）。"""
    ticket = {"why": "已移除該功能。"}
    hints = detect_unverified_absence_claims(ticket)
    assert isinstance(hints, list)
    assert all(isinstance(h, str) for h in hints)


def test_no_hint_when_fully_verified():
    ticket = {"why": "三層查證後確認該腳本從未存在。"}
    assert detect_unverified_absence_claims(ticket) == []


# ============================================================
# 整合：真實票面原文（0.2.1-W3-962 / 0.2.1-W3-992 / 0.2.1-W4-001）
# ============================================================


def test_real_ticket_why_field_with_no_registry_check_triggers():
    """0.2.1-W3-962 原文：查過同名檔全庫搜尋，但未查 settings.json 事件註冊。"""
    why = (
        "失效引用全域複查的類型 B 判定結果：pre-fix-eval skill 的 SKILL.md "
        "明文宣稱「PostToolUse Hook 自動識別四種錯誤類型」、INDEX.md 的文件"
        "關係圖以 .claude/hooks/pre-fix-evaluation-hook.py 為整條流程的入口，"
        "但該檔案全庫搜尋不到（排除 archived），settings.json 亦無任何 "
        "pre-fix 相關註冊。同批發現 .claude/hooks/test-timeout-post.py 同樣"
        "不存在且僅出現於該 skill references 下的 settings.json 歷史片段"
        "（test-timeout-pre.py 存在且已註冊，post 版未部署）。"
    )
    assert find_unverified_absence_claims({"why": why}) == ["why"]


def test_real_ticket_why_field_asserting_never_existed_triggers():
    """0.2.1-W3-992 原文：僅斷言「從未存在」，無任何查證痕跡字樣。"""
    why = (
        "`strategic-compact/SKILL.md` 的 Hook Setup 範例在 settings.json "
        "配置中引用 `.claude/skills/strategic-compact/suggest-compact.sh`，"
        "該腳本自 skill 建立起從未存在。與一般失效引用的差別在於 skill 本身"
        "是活躍的，故這是功能缺口不是文件過時：文件描述的自動化機制從未被"
        "實作，而讀者依 SKILL.md 設定 hook 時會配置一個不存在的腳本。"
    )
    assert find_unverified_absence_claims({"why": why}) == ["why"]


def test_real_ticket_why_field_with_full_trace_does_not_trigger():
    """0.2.1-W4-001 原文：缺席斷言與 git 全歷史 + settings.json 註冊查證同段。"""
    why = (
        "dry-run-guide.md 描述 Phase 2 語意層驗收的前置條件是 Phase 1 自動化"
        "形式掃描（portability-check.sh）exit 0，但此腳本自專案初始匯入起"
        "從未存在（broken-link 修復查證：git log 全歷史無此路徑、"
        "settings.json 無事件註冊）。文件描述的驗收流程目前無法被實際執行，"
        "屬功能缺口而非路徑漂移"
    )
    assert find_unverified_absence_claims({"why": why}) == []
