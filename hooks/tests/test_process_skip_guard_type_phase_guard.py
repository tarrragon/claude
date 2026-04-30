"""
RED tests for process-skip-guard-hook.py — type/phase guard + 關鍵字精確化

Ticket: 0.18.0-W11-004.2 (Phase 2)

覆蓋 6 條 AC：
- AC1 派發前查詢當前 Ticket 的 type 和 current_phase
- AC2 IMP type + Phase 4 排除 SA 提醒
- AC3 DOC/ANA type 全面排除 SA 提醒
- AC4 移除/改寫高假陽性關鍵字 pair
- AC5 三場景排除測試（Phase 4 IMP / DOC / ANA）
- AC6 既有測試持續 GREEN（由 test_process_skip_guard_hook.py 保證）

以及失敗回退：
- 無 in_progress ticket → 維持原行為（觸發提醒）
- read_ticket 拋例外 → 不阻擋，原行為觸發提醒

Phase 3b 預期實作介面（測試以 monkeypatch 驅動）：
- process_skip_guard_hook.get_active_in_progress_ticket() -> Optional[dict]
  回傳 {"type": "IMP"|"DOC"|"ANA"|..., "current_phase": "Phase 4"|...} 或 None
- detect_skip_intent 內部會呼叫此函式作為 SA_REVIEW guard 條件

注意：本檔為 RED 測試骨架，測試在實作前會 FAIL（預期）。
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util

import pytest

# 動態導入 Hook 檔案
hook_path = Path(__file__).parent.parent / "process-skip-guard-hook.py"
spec = importlib.util.spec_from_file_location("process_skip_guard_hook", hook_path)
process_skip_guard_hook = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(__file__).parent.parent))
spec.loader.exec_module(process_skip_guard_hook)

detect_skip_intent = process_skip_guard_hook.detect_skip_intent
SKIP_PATTERNS = process_skip_guard_hook.SKIP_PATTERNS
main = process_skip_guard_hook.main


# ============================================================================
# AC4：關鍵字精確化（pair 移除）
# ============================================================================

class TestKeywordPrecisionRemoval:
    """AC4：移除高假陽性關鍵字 pair"""

    def test_skip_acceptance_removes_直接_完成_pair(self):
        """SKIP_ACCEPTANCE.pairs 不再含 ('直接','完成')

        理由：「直接修復後完成」是合法重構/修復措辭，假陽性過高
        """
        pairs = SKIP_PATTERNS["SKIP_ACCEPTANCE"]["pairs"]
        assert ("直接", "完成") not in pairs, \
            "SKIP_ACCEPTANCE 應移除 ('直接','完成') pair（高 FP）"

    def test_skip_sa_review_removes_不做_審查_pair(self):
        """SKIP_SA_REVIEW.pairs 不再含 ('不做','審查')

        理由：與一般審查討論重疊度過高，且原本錯放在 SKIP_ACCEPTANCE
        """
        pairs = SKIP_PATTERNS["SKIP_SA_REVIEW"]["pairs"]
        assert ("不做", "審查") not in pairs, \
            "SKIP_SA_REVIEW 應移除 ('不做','審查') pair（高 FP）"

    def test_skip_acceptance_removes_不做_審查_pair(self):
        """SKIP_ACCEPTANCE.pairs 不再含 ('不做','審查')

        理由：原本錯放在 SKIP_ACCEPTANCE 中（語意屬 SA 審查），與其他模式重疊
        """
        pairs = SKIP_PATTERNS["SKIP_ACCEPTANCE"]["pairs"]
        assert ("不做", "審查") not in pairs, \
            "SKIP_ACCEPTANCE 應移除 ('不做','審查') pair（與 SA_REVIEW 語意重疊）"

    def test_explicit_sa_keywords_preserved(self):
        """顯式 SA 詞 pair 應保留

        ('跳過','sa') 和 ('不需要','sa') 是明確意圖，必須保留
        """
        pairs = SKIP_PATTERNS["SKIP_SA_REVIEW"]["pairs"]
        assert ("跳過", "sa") in pairs, "保留顯式 ('跳過','sa') pair"
        assert ("不需要", "sa") in pairs, "保留顯式 ('不需要','sa') pair"

    def test_legitimate_phrase_直接修復後完成_not_misfire(self):
        """合法句「直接修復後完成」不再誤觸 SKIP_ACCEPTANCE"""
        user_input = "直接修復後完成這個 bug"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type != "SKIP_ACCEPTANCE", \
            f"合法句不應誤觸 SKIP_ACCEPTANCE，實際: {skip_type}"

    def test_legitimate_phrase_不做架構審查改良_not_misfire(self):
        """合法句「這次不做架構審查改良」不再誤觸 SKIP_SA_REVIEW/SKIP_ACCEPTANCE"""
        user_input = "這次不做架構審查的改良工作"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type not in ("SKIP_SA_REVIEW", "SKIP_ACCEPTANCE"), \
            f"合法句不應誤觸，實際: {skip_type}"


# ============================================================================
# AC1 / AC2 / AC3 / AC5：type/phase guard 排除規則
# ============================================================================

def _make_active_ticket_input(prompt: str) -> str:
    return json.dumps({"prompt": prompt})


def _run_main_capture(input_data: str, mock_active_ticket=None, mock_has_active_dispatch=False):
    """執行 main 並捕獲 stdout/stderr，可選 mock 當前 in_progress ticket 與 active-dispatch"""
    with patch("sys.stdin", StringIO(input_data)):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                    with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                        # mock active ticket lookup（Phase 3b 需實作此函式）
                        with patch.object(
                            process_skip_guard_hook,
                            "get_active_in_progress_ticket",
                            return_value=mock_active_ticket,
                            create=True,  # 允許 attribute 尚不存在（RED 階段）
                        ):
                            # mock active-dispatch guard（W11-004.3）：預設 False，
                            # 避免測試環境讀到實際 dispatch-active.json
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                return_value=mock_has_active_dispatch,
                                create=True,
                            ):
                                exit_code = main()
    return exit_code, mock_stdout.getvalue(), mock_stderr.getvalue()


def _has_reminder(stdout: str, stderr: str) -> bool:
    """判斷輸出是否含提醒（additionalContext + stderr 訊息）"""
    parsed = json.loads(stdout)
    has_context = "additionalContext" in parsed.get("hookSpecificOutput", {})
    has_stderr = bool(stderr.strip())
    return has_context or has_stderr


class TestTypePhaseGuardExclusion:
    """AC1/AC2/AC3/AC5：依 ticket type/current_phase 排除 SA 提醒"""

    def test_ac1_hook_queries_active_ticket_helper(self):
        """AC1：hook 在 SA skip 偵測時應呼叫 get_active_in_progress_ticket"""
        assert hasattr(process_skip_guard_hook, "get_active_in_progress_ticket"), \
            "Phase 3b 必須在 process_skip_guard_hook 模組新增 get_active_in_progress_ticket() 函式"

    def test_ac2_imp_phase4_excludes_sa_reminder(self):
        """AC2：active ticket type=IMP, current_phase='Phase 4' + SA skip 詞 → 不觸發提醒"""
        active_ticket = {"type": "IMP", "current_phase": "Phase 4"}
        input_data = _make_active_ticket_input("跳過 sa 直接重構")
        exit_code, stdout, stderr = _run_main_capture(input_data, active_ticket)
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "IMP + Phase 4 應排除 SA 提醒"

    def test_ac3_doc_type_excludes_sa_reminder(self):
        """AC3：active ticket type=DOC + SA skip 詞 → 不觸發提醒（任何 phase）"""
        active_ticket = {"type": "DOC", "current_phase": "Phase 1"}
        input_data = _make_active_ticket_input("跳過 sa 審查直接寫文件")
        exit_code, stdout, stderr = _run_main_capture(input_data, active_ticket)
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "DOC type 應全面排除 SA 提醒"

    def test_ac3_ana_type_excludes_sa_reminder(self):
        """AC3：active ticket type=ANA + SA skip 詞 → 不觸發提醒"""
        active_ticket = {"type": "ANA", "current_phase": "Phase 1"}
        input_data = _make_active_ticket_input("不需要 sa 前置審查")
        exit_code, stdout, stderr = _run_main_capture(input_data, active_ticket)
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "ANA type 應全面排除 SA 提醒"

    def test_ac2_imp_phase1_does_not_exclude_sa_reminder(self):
        """負向：IMP + Phase 1（非 Phase 4）+ SA skip 詞 → 仍觸發提醒"""
        active_ticket = {"type": "IMP", "current_phase": "Phase 1"}
        input_data = _make_active_ticket_input("跳過 sa 直接做")
        exit_code, stdout, stderr = _run_main_capture(input_data, active_ticket)
        assert exit_code == 0
        assert _has_reminder(stdout, stderr), \
            "IMP + 非 Phase 4 不應排除 SA 提醒"

    def test_imp_phase4_does_not_affect_non_sa_skip_patterns(self):
        """IMP + Phase 4 只靜音 SKIP_SA_REVIEW，其他 skip 模式仍觸發

        例如 SKIP_AGENT_DISPATCH 不受 type/phase guard 影響
        """
        active_ticket = {"type": "IMP", "current_phase": "Phase 4"}
        input_data = _make_active_ticket_input("我自行處理，不用代理人")
        exit_code, stdout, stderr = _run_main_capture(input_data, active_ticket)
        assert exit_code == 0
        assert _has_reminder(stdout, stderr), \
            "type/phase guard 僅影響 SKIP_SA_REVIEW，其他模式（SKIP_AGENT_DISPATCH）應照常觸發"


# ============================================================================
# 失敗回退測試
# ============================================================================

class TestFallbackBehavior:
    """失敗回退：找不到/讀不到 active ticket 時維持原行為"""

    def test_no_active_in_progress_ticket_keeps_original_behavior(self):
        """無 in_progress ticket → SA skip 詞仍觸發提醒"""
        input_data = _make_active_ticket_input("跳過 sa 審查")
        exit_code, stdout, stderr = _run_main_capture(input_data, mock_active_ticket=None)
        assert exit_code == 0
        assert _has_reminder(stdout, stderr), \
            "無 active ticket 應回退至原行為（觸發提醒）"

    def test_get_active_ticket_raises_exception_does_not_block(self):
        """get_active_in_progress_ticket 拋例外 → 不阻擋 hook，原行為觸發提醒"""
        input_data = _make_active_ticket_input("跳過 sa 審查")

        def _raise(*args, **kwargs):
            raise RuntimeError("simulated read_ticket failure")

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            with patch.object(
                                process_skip_guard_hook,
                                "get_active_in_progress_ticket",
                                side_effect=_raise,
                                create=True,
                            ):
                                with patch.object(
                                    process_skip_guard_hook,
                                    "has_active_dispatch",
                                    return_value=False,
                                    create=True,
                                ):
                                    exit_code = main()

        assert exit_code == 0, "讀取例外不應阻擋 hook"
        assert _has_reminder(mock_stdout.getvalue(), mock_stderr.getvalue()), \
            "讀取例外應回退至原行為（觸發提醒），不靜音"


# ============================================================================
# AC5：三場景排除整合驗證（cold path 性能假設）
# ============================================================================

class TestColdPathPerformance:
    """性能假設：active ticket 只在偵測到 skip intent 後才讀取

    Phase 3b 實作時，無 skip intent 的 prompt 不應呼叫 get_active_in_progress_ticket
    """

    def test_no_skip_intent_does_not_query_active_ticket(self):
        """無 skip intent 的 prompt 不應觸發 active ticket 查詢"""
        input_data = _make_active_ticket_input("繼續執行下一個任務")

        call_counter = {"n": 0}

        def _spy(*args, **kwargs):
            call_counter["n"] += 1
            return None

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO):
                with patch("sys.stderr", new_callable=StringIO):
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            with patch.object(
                                process_skip_guard_hook,
                                "get_active_in_progress_ticket",
                                side_effect=_spy,
                                create=True,
                            ):
                                main()

        assert call_counter["n"] == 0, \
            "無 skip intent 不應呼叫 get_active_in_progress_ticket（cold path 違規）"
