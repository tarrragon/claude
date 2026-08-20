"""
Dispatch Staging Phrase Guard Hook 測試

對應 Ticket 0.2.1-W3-677 acceptance：
- hook 於 Agent/Task prompt 涉及 commit 但缺精準 staging 制式句片語時，
  輸出軟提示（stderr），不阻擋派發（exit 0）
- 唯讀派發（Dispatch-Mode: readonly 或 READONLY_AGENT_TYPES）不觸發提示
- worktree 隔離派發（isolation == "worktree"）不觸發提示
- 不涉及 commit 的 prompt 不觸發提示
- 涵蓋 Category A + Category B 片語的 prompt 不觸發提示

多視角審查（linux / basil-writing-critic / thyme-python-developer）後追加：
- Category A 反向探針（禁令詞面不得誤判為滿足）
- Category B 同型反向探針（否定語境不得誤判為滿足）
- tool_input 以 JSON 字串傳入的分支覆蓋（thyme M1）

Ticket 0.2.1-W3-735（範本 A 對齊規則七）後追加/修正：
- AUTHORITATIVE_LINES 全文對齊 agent-dispatch-template.md v1.29.0（precise
  staging + verified bare commit, no pathspec）
- Category A 移除 pathspec 專屬片語（"-- {exact files}" / "-- <paths>" /
  "git commit -- "）；新增 pathspec commit 不再滿足 A 類的反向探針
- Category B 新增 "git diff --cached --name-only" 為現行核對指令
- 既有 prompt 相容性決策：直接切換（無過渡期），並記錄已知殘留限制測試
  （完整舊版四行制式句仍會因 "exact files" 滿足 A 類，見該測試 docstring）
- 否定視窗對照組測試片語由已淘汰的 "path-limited commit" 改為現行
  "精準 staging"（測邏輯方向，非測片語文字）

Ticket 0.2.1-W3-737（ANA：判定需獨立 Category C）+ 0.2.1-W3-739（實作）後
追加/修正：
- 新增獨立 Category C（bare commit, no pathspec）：0.2.1-W3-735 遺留的
  "bare commit"/"no pathspec"/"verified bare commit" 三片語由 Category A
  移出，獨立判定，缺一不足——消除「add 精準與 commit 無 pathspec 兩證據
  可互相頂替」的殘留限制
- 0.2.1-W3-735 記錄殘留限制的測試（原
  test_missing_categories_old_style_full_block_still_satisfies_category_a_via_exact_files）
  改寫為驗證修復：舊版含 pathspec commit 的完整四行制式句現在正確被判定
  缺 Category C，不再靜默通過
- drift-case / 否定視窗對照組 / 通用 commit 提示測試因新增 C 類別，
  missing 清單與 stderr 內容同步更新（多出 "Category C" 提示，反映
  Category C 判準生效，非誤報）
- AUTHORITATIVE_LINES 的 Forbidden 行改採 tuple 多類別標記（("A", "C")），
  對應測試驗證 `_build_soft_hint` 在該行正確顯示 "Category A/Category C"
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "dispatch_staging_phrase_guard_hook",
    _HOOKS_DIR / "dispatch-staging-phrase-guard-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

main = _hook.main
_missing_categories = _hook._missing_categories
_has_commit_intent = _hook._has_commit_intent
_is_dispatch_mode_readonly = _hook._is_dispatch_mode_readonly
_line_missing_codes = _hook._line_missing_codes

# 存證位置：本案例逐字引用自 ticket 0.2.1-W3-677 Context Bundle「活案例」節
# 記錄的觀測樣本（PM 於某次實際派發中的中文改寫句，非本測試虛構）。
# 兩處使用（drift-case 整合測試 + unit 測試）必須逐字一致，避免文字漂移。
DRIFT_CASE_PROMPT = (
    "commit 精準 staging：只 git add 你實際修改的檔案路徑，"
    "禁 git add -A/.（工作區有其他 session 的未 commit 變更，PC-BAL-008）"
)


def _run_hook(monkeypatch, tool_input: dict, tool_name: str = "Agent") -> tuple:
    """執行 main()，回傳 (exit_code, stderr_text)。"""
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    import contextlib
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stderr(stderr_buffer):
        exit_code = main()
    return exit_code, stderr_buffer.getvalue()


def _run_hook_with_string_tool_input(monkeypatch, tool_input: dict, tool_name: str = "Agent") -> tuple:
    """執行 main()，tool_input 以 JSON 字串（而非 dict）傳入——CC runtime 常見形態。"""
    payload = {"tool_name": tool_name, "tool_input": json.dumps(tool_input)}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    import contextlib
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stderr(stderr_buffer):
        exit_code = main()
    return exit_code, stderr_buffer.getvalue()


# ----------------------------------------------------------------------------
# 單元測試：_missing_categories / _has_commit_intent / _is_dispatch_mode_readonly
# ----------------------------------------------------------------------------

def test_missing_categories_both_present_when_full_authoritative_phrase():
    prompt = """Use precise staging + verified bare commit only (no pathspec):
  git add {exact files}
  git diff --cached --name-only   # confirm index contains ONLY {exact files}
  git commit -m "..."             # bare commit; no -- <paths> / --only / -o / -a
Forbidden: git add . / git add -A; git commit -- <paths> / --only / -o / -a
Before commit: git diff --cached --name-only to check staged scope; git restore --staged <path> for any non-owned file
""".lower()
    assert _missing_categories(prompt) == []


def test_missing_categories_reverse_probe_pathspec_commit_alone_does_not_satisfy_category_a():
    """0.2.1-W3-735：規則七落地後，pathspec commit（`git commit -- <paths>`）
    不再是 Category A 合格片語。prompt 僅寫 pathspec commit、未提及 add
    精準性（無 "exact files" 等片語）時，不得被 pathspec 語法本身誤判為
    已涵蓋 Category A——舊版曾將 "git commit -- " 收錄為正面片語，規則七
    落地後這是危險語法，不應繼續給予正面credit。0.2.1-W3-739 後同時驗證
    Category C 亦缺（該 prompt 未寫 "bare commit"/"no pathspec" 等片語）。"""
    prompt = 'commit 完成後執行 git commit -m "..." -- file1.py file2.py'.lower()
    missing = _missing_categories(prompt)
    assert "A" in missing
    assert "C" in missing


def test_missing_categories_old_style_full_block_now_correctly_flags_category_c():
    """0.2.1-W3-739：驗證修復（前身為
    test_missing_categories_old_style_full_block_still_satisfies_category_a_via_exact_files，
    0.2.1-W3-735 記錄的已知殘留限制）。完整舊版四行制式句（pathspec commit
    + git status 核對）仍含 "exact files" 片語、Category A 依然判定已涵蓋
    ——但 "bare commit"/"no pathspec"/"verified bare commit" 三片語已移出
    Category A、獨立為 Category C，此 prompt 未提及任一 C 類片語，現在
    正確被判定缺 Category C，不再如舊版測試名稱所述「靜默通過」。
    既有 prompt 相容性決策（0.2.1-W3-735：直接切換，無過渡期）在此進一步
    生效——翻轉方向仍是「原本沉默→現在提示」，非阻斷式变化。"""
    prompt = """Use precise staging + path-limited commit only:
  git add {exact files}
  git commit -m "..." -- {exact files}
Forbidden: git add . / git add -A; git commit without -- <paths>
Before commit: git status to check staged scope; git restore --staged <path> for any non-owned file
""".lower()
    assert _missing_categories(prompt) == ["C"]


def test_missing_categories_detects_missing_category_b_in_drift_case():
    """觀測案例：PM 中文改寫涵蓋 A（禁 git add -A/.）但缺 B（無 git status
    核對）。0.2.1-W3-739 後同時缺 C——drift-case 未提及 "bare commit"/
    "no pathspec" 等片語，這是 Category C 判準生效的預期強化，非回歸。"""
    missing = _missing_categories(DRIFT_CASE_PROMPT.lower())
    assert missing == ["B", "C"]


def test_missing_categories_detects_all_missing_when_generic_prompt():
    """0.2.1-W3-739 後：通用 prompt（無任何制式句片語）三類別皆缺。"""
    prompt = "請完成後 commit 變更".lower()
    missing = _missing_categories(prompt)
    assert missing == ["A", "B", "C"]


def test_missing_categories_reverse_probe_category_a_forbidden_wording():
    """反向探針（PM 驗收回報）：prompt 明確要求廣域 add，禁令子字串
    ("git add .") 不得被誤判為滿足 Category A（正面片語需求）。"""
    prompt = "請用 git add . 把全部變更加入後 commit。".lower()
    assert "A" in _missing_categories(prompt)


def test_missing_categories_reverse_probe_category_b_negated_wording():
    """Category B 同型反向探針（PM 驗收回報項 10）：「不需要 git status」
    不得被純子字串比對誤判為已涵蓋 Category B。"""
    prompt = "commit 時不需要 git status 檢查，也不用 git restore --staged。".lower()
    assert "B" in _missing_categories(prompt)


def test_missing_categories_category_b_positive_wording_still_hits():
    """否定語境排除機制不可過度排除：正常正面表述仍須命中 B。"""
    prompt = "commit 前請先 git status 確認 staged 範圍，再 git restore --staged 排除他人檔案。".lower()
    assert "B" not in _missing_categories(prompt)


def test_has_commit_intent_true_for_commit_keyword():
    assert _has_commit_intent("實作完成後 commit") is True


def test_has_commit_intent_false_for_readonly_prompt():
    assert _has_commit_intent("僅分析程式碼，不需修改") is False


def test_has_commit_intent_false_for_negated_commit():
    """linux #5：裸 commit 若被否定語境包圍（"do not commit"）不應視為涉及 commit。"""
    assert _has_commit_intent("please do not commit any changes") is False


def test_has_commit_intent_false_for_committee_word_boundary():
    """linux #5：子字串誤判——"committee" 不應被 \\bcommit\\b 詞界比對命中。"""
    assert _has_commit_intent("請聯絡 review committee 確認流程") is False


def test_is_dispatch_mode_readonly_true():
    assert _is_dispatch_mode_readonly("Dispatch-Mode: readonly\n其餘內容") is True


def test_is_dispatch_mode_readonly_false_when_not_first_line():
    assert _is_dispatch_mode_readonly("其他內容\nDispatch-Mode: readonly") is False


# ----------------------------------------------------------------------------
# 整合測試：main() Hook 入口點
# ----------------------------------------------------------------------------

def test_non_agent_task_tool_skipped(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": "commit 變更"}, tool_name="Bash")
    assert exit_code == 0
    assert stderr == ""


def test_empty_prompt_skipped(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": ""})
    assert exit_code == 0
    assert stderr == ""


def test_worktree_isolation_exempt(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "請完成任務後 commit 變更",
        "isolation": "worktree",
    })
    assert exit_code == 0
    assert stderr == ""


def test_dispatch_mode_readonly_exempt(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "Dispatch-Mode: readonly\n請分析後 commit 建議寫入 ticket",
    })
    assert exit_code == 0
    assert stderr == ""


def test_readonly_agent_type_exempt(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "請完成任務後 commit 變更",
        "subagent_type": "Explore",
    })
    assert exit_code == 0
    assert stderr == ""


def test_no_commit_intent_skipped(monkeypatch):
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "請閱讀 ticket 並回報分析結果，不需修改檔案",
    })
    assert exit_code == 0
    assert stderr == ""


def test_commit_intent_missing_all_categories_emits_soft_hint(monkeypatch):
    """0.2.1-W3-739 後：通用 prompt 三類別皆缺，軟提示須列全三類與各自後果。"""
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "請完成實作後 commit 變更",
    })
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category A" in stderr
    assert "Category B" in stderr
    assert "Category C" in stderr
    # basil P0-1：每個 missing 類別自帶後果一行
    assert "PC-092" in stderr
    assert "PC-BAL-008" in stderr
    assert "規則七" in stderr


def test_drift_case_missing_category_b_and_c_emits_soft_hint(monkeypatch):
    """ticket 0.2.1-W3-677 Context Bundle 記錄的活案例：涵蓋 A 缺 B。
    0.2.1-W3-739 後同時缺 C（未提及 bare commit/no pathspec 片語），應觸發
    軟提示且列出 B 與 C，A 已涵蓋不應出現。"""
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": DRIFT_CASE_PROMPT})
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category B" in stderr
    assert "Category C" in stderr
    assert "Category A" not in stderr


def test_reverse_probe_forbidden_wording_does_not_satisfy_category_a(monkeypatch):
    """反向探針（PM 驗收回報）：prompt 明確要求廣域 add，禁令子字串
    ("git add .") 不得被誤判為滿足 Category A（正面片語需求）。此測試通過
    的原因是 prompt 完全未命中任何 CATEGORY_A_PHRASES 正面片語，而非命中
    禁令詞面（禁令詞面已於本檔前版修正移除，見 CATEGORY_A_PHRASES 註解）。
    """
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "Ticket: X\n請用 git add . 把全部變更加入後 commit。",
    })
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category A" in stderr


def test_reverse_probe_category_b_negated_wording_emits_hint(monkeypatch):
    """Category B 同型反向探針整合測試（PM 驗收回報項 10）。"""
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "commit 時不需要 git status 檢查，也不用 git restore --staged。",
    })
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category B" in stderr


def test_full_authoritative_phrase_no_hint(monkeypatch):
    prompt = (
        "Ticket: 0.2.1-W3-999\n\n"
        "Use precise staging + verified bare commit only (no pathspec):\n"
        '  git add {exact files}\n'
        '  git diff --cached --name-only   # confirm index contains ONLY {exact files}\n'
        '  git commit -m "..."             # bare commit; no -- <paths> / --only / -o / -a\n'
        "Forbidden: git add . / git add -A; git commit -- <paths> / --only / -o / -a\n"
        "Before commit: git diff --cached --name-only to check staged scope; git restore --staged <path> for any non-owned file\n"
    )
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    assert stderr == ""


def test_hook_never_blocks(monkeypatch):
    """Layer 2 定位：任何情況皆不回傳 exit code 2。"""
    exit_code, _ = _run_hook(monkeypatch, {"prompt": "commit 變更但完全缺制式句"})
    assert exit_code == 0


def test_tool_input_as_json_string_still_detected(monkeypatch):
    """thyme M1：tool_input 以 JSON 字串傳入（CC runtime 常見形態）須走
    同一套判定邏輯，缺制式句時仍觸發軟提示。0.2.1-W3-739 後三類別皆檢查。"""
    exit_code, stderr = _run_hook_with_string_tool_input(monkeypatch, {
        "prompt": "請完成實作後 commit 變更",
    })
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category A" in stderr
    assert "Category B" in stderr
    assert "Category C" in stderr


def test_tool_input_as_json_string_exempt_worktree(monkeypatch):
    """thyme M1：JSON 字串分支下豁免邏輯（isolation）仍須生效。"""
    exit_code, stderr = _run_hook_with_string_tool_input(monkeypatch, {
        "prompt": "請完成任務後 commit 變更",
        "isolation": "worktree",
    })
    assert exit_code == 0
    assert stderr == ""


def test_tool_input_as_invalid_json_string_skips(monkeypatch):
    """tool_input 為無法解析的 JSON 字串時放行，不拋例外。"""
    payload = {"tool_name": "Agent", "tool_input": "{not valid json"}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    exit_code = main()
    assert exit_code == 0


# ----------------------------------------------------------------------------
# 追加測試：否定視窗方向修正（PM 驗收回報，A/B/C 三組對照）
# ----------------------------------------------------------------------------
#
# 背景：`_has_negation_free_hit` 第一版採前後夾（雙向）視窗，與
# `_has_commit_intent` 犯了同型錯誤——相鄰兩句時，後句開頭的否定詞會
# 誤配給前句片語。修正為僅檢查片語前方視窗，以下三組對照驗證修正後行為：
#   A：兩句緊鄰（否定詞與 A 類片語相距 < 15 字元）→ 缺 B/C（A 類不得被誤傷）
#   B：兩句分隔較遠（否定詞與 A 類片語相距 >= 15 字元）→ 缺 B/C（既有行為）
#   C：無否定詞 → 缺 B/C（既有行為）
#
# 0.2.1-W3-735：測試片語由 "path-limited commit"（已淘汰詞面，v1.29.0 起
# 不再出現於權威版）改為 "精準 staging"（現行 Category A 片語），驗證的是
# 否定視窗方向邏輯本身，與具體片語文字無關。
#
# 0.2.1-W3-739：以下三組對照組的 prompt 皆未提及 Category C 片語（"bare
# commit"/"no pathspec" 等），三組原本 missing == ["B"] 均改為
# ["B", "C"]——對照組驗證的是「A 不得被否定詞誤傷」的方向邏輯，與新增的
# C 類別缺失無關，C 缺失是預期的獨立事實，非對照組要驗證的目標。

def test_missing_categories_negation_window_case_a_adjacent_sentences():
    """對照組 A：否定詞緊鄰 A 類片語之後，不得誤判 A 類也被否定。"""
    prompt = "commit 時用精準 staging，不需要 git status 核對。".lower()
    assert _missing_categories(prompt) == ["B", "C"]


def test_missing_categories_negation_window_case_b_distant_sentences():
    """對照組 B：否定詞與 A 類片語相距較遠，維持既有正確行為（不得回歸）。"""
    prompt = (
        "commit 時請使用精準 staging 的方式處理本次變更範圍。"
        "另外說明一點：本任務不需要 git status 核對。"
    ).lower()
    assert _missing_categories(prompt) == ["B", "C"]


def test_missing_categories_negation_window_case_c_no_negation():
    """對照組 C：無否定詞，維持既有正確行為（不得回歸）。"""
    prompt = "commit 時用精準 staging。".lower()
    assert _missing_categories(prompt) == ["B", "C"]


def test_missing_categories_negation_only_applies_forward():
    """既有已驗證正確行為（修改後不得回歸）：否定詞出現在片語之後、與片語
    語意無關時（"git status 核對 staged 範圍，不需要再問我確認"，"不需要"
    否定的是「再問我確認」而非 git status 本身），不得誤判 B 類被否定。"""
    prompt = "git status 核對 staged 範圍，不需要再問我確認。".lower()
    assert "B" not in _missing_categories(prompt)


def test_reverse_probe_negation_window_case_a_integration(monkeypatch):
    """對照組 A 整合測試：軟提示列 Category B 與 C，不得誤列 Category A。"""
    exit_code, stderr = _run_hook(monkeypatch, {
        "prompt": "commit 時用精準 staging，不需要 git status 核對。",
    })
    assert exit_code == 0
    assert "提示" in stderr
    assert "Category B" in stderr
    assert "Category C" in stderr
    assert "Category A" not in stderr


# ----------------------------------------------------------------------------
# 追加測試：0.2.1-W3-739 獨立 Category C（bare commit, no pathspec）
# ----------------------------------------------------------------------------

def test_missing_categories_category_c_phrase_satisfies_c_only():
    """C 類正面片語（"no pathspec"）僅滿足 C，不連帶滿足 A（兩類已獨立）。"""
    prompt = "commit 時 git add {exact files}，並確保 no pathspec bare commit。".lower()
    assert _missing_categories(prompt) == ["B"]


def test_missing_categories_category_c_negated_wording_not_satisfied():
    """C 類同型否定語境防護：「不需要 no pathspec 檢查」不得誤判為已涵蓋 C。"""
    prompt = "commit 時不需要 no pathspec 檢查，git add {exact files}，git status 核對。".lower()
    assert "C" in _missing_categories(prompt)


def test_line_missing_codes_expands_tuple_and_filters_by_missing():
    """`_line_missing_codes` 對 tuple 標記（Forbidden 行的 ("A", "C")）須
    展開並只回傳實際缺失的代碼，保持宣告順序。"""
    assert _line_missing_codes(("A", "C"), ["A", "B", "C"]) == ["A", "C"]
    assert _line_missing_codes(("A", "C"), ["C"]) == ["C"]
    assert _line_missing_codes(("A", "C"), ["B"]) == []
    assert _line_missing_codes("A", ["A", "B"]) == ["A"]
    assert _line_missing_codes(None, ["A", "B", "C"]) == []


def test_forbidden_line_shows_multi_category_tag_when_both_a_and_c_missing(monkeypatch):
    """整合測試：Forbidden 行同時涉及 A（git add 禁令）與 C（pathspec commit
    禁令），A、C 皆缺時該行須顯示 "Category A/Category C" 複合標記，而非
    只顯示其中一個或漏標。"""
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": "請完成後 commit 變更"})
    assert exit_code == 0
    assert "Forbidden: git add . / git add -A" in stderr
    assert "Category A/Category C" in stderr


def test_forbidden_line_shows_only_category_c_tag_when_only_c_missing(monkeypatch):
    """整合測試：僅 C 缺失（A 已涵蓋）時 Forbidden 行只標 Category C，不得
    誤標 Category A（該行涉及 A 但 A 本身並未缺失）。"""
    prompt = 'commit 完成後執行 git commit -m "..." -- {exact files}'.lower()
    exit_code, stderr = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    forbidden_line = next(
        line for line in stderr.splitlines() if line.strip().startswith("Forbidden:")
    )
    assert "Category C" in forbidden_line
    assert "Category A" not in forbidden_line
