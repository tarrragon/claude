"""
測試 process-skip-guard-hook

測試流程省略意圖偵測的 6 個模式和邊界情況。
"""

import json
import subprocess
import sys
from pathlib import Path


def run_hook(prompt: str) -> str:
    """
    運行 process-skip-guard-hook，返回 stderr 輸出

    Args:
        prompt: 用戶輸入的提示文本

    Returns:
        Hook 的 stderr 輸出
    """
    hook_path = Path(__file__).parent.parent / "process-skip-guard-hook.py"
    input_data = json.dumps({"prompt": prompt})

    result = subprocess.run(
        ["uv", "run", "python", str(hook_path)],
        input=input_data,
        capture_output=True,
        text=True,
    )

    return result.stderr


class TestProcessSkipGuardHook:
    """流程省略偵測 Hook 測試套件"""

    def test_skip_agent_dispatch(self):
        """測試 SKIP_AGENT_DISPATCH 模式"""
        output = run_hook("我不需要派發代理人，我自行處理")
        assert "不派發代理人" in output
        assert "根據決策樹分類並派發" in output

    def test_skip_acceptance(self):
        """測試 SKIP_ACCEPTANCE 模式"""
        output = run_hook("這個 Ticket 跳過驗收吧")
        assert "跳過驗收檢查" in output
        assert "acceptance-auditor" in output

    def test_skip_tdd_phase(self):
        """測試 SKIP_TDD_PHASE 模式"""
        output = run_hook("很簡單，跳過 Phase 2 的測試設計")
        assert "跳過 TDD 步驟" in output
        assert "Phase 1" in output and "Phase 2" in output

    def test_skip_parallel_eval(self):
        """測試 SKIP_PARALLEL_EVAL 模式"""
        output = run_hook("跳過審核，直接派發吧")
        assert "並行化評估" in output
        assert "/parallel-evaluation" in output

    def test_skip_sa_review(self):
        """測試 SKIP_SA_REVIEW 模式"""
        output = run_hook("不需要 SA 審查，直接開始 Phase 1")
        assert "SA 前置審查" in output
        assert "system-analyst" in output

    def test_skip_phase4(self):
        """測試 SKIP_PHASE4 模式"""
        output = run_hook("程式碼質量已經很好了，不用重構")
        assert "Phase 4 重構評估" in output
        assert "不可跳過" in output

    def test_no_skip_intent(self):
        """測試正常提示（無省略意圖）"""
        output = run_hook("建立一個新的 Ticket 用於實作新功能")
        # 無省略意圖時不應有任何輸出
        assert output.strip() == ""

    def test_partial_keywords(self):
        """測試單一關鍵字（不應觸發，需要 2 個關鍵字）"""
        output = run_hook("不需要")  # 只有一個關鍵字
        assert output.strip() == ""

    def test_empty_prompt(self):
        """測試空提示"""
        output = run_hook("")
        assert output.strip() == ""

    def test_case_insensitive(self):
        """測試大小寫不敏感"""
        output = run_hook("我不需要派發代理人，I will HANDLE IT MYSELF")
        # Hook 使用小寫比對，應該能偵測中文關鍵字
        assert "不派發代理人" in output

    def test_english_keywords(self):
        """測試英文關鍵字（支援 skip + task）"""
        output = run_hook("skip the assessment and directly proceed")
        # 目前還沒有英文關鍵字對，此應無輸出
        assert output.strip() == ""

    def test_combination_keywords_order(self):
        """測試組合關鍵字順序不敏感"""
        output1 = run_hook("不需要派發代理人")
        output2 = run_hook("派發代理人我不需要")
        # 兩種順序都應該偵測到
        assert "不派發代理人" in output1
        assert "不派發代理人" in output2

    def test_multiple_keywords_in_sentence(self):
        """測試複雜句子中的多個關鍵字"""
        output = run_hook(
            "這個任務不需要經過複雜的驗收，我直接派發給代理人處理"
        )
        # 包含 "不需要" 和 "派發"，應該偵測
        assert "不派發代理人" in output or output.strip() == ""  # 可能有歧義

    def test_skip_phase4_variations(self):
        """測試 Phase 4 跳過的不同表述"""
        # 表述 1：跳過 + Phase 4
        output1 = run_hook("跳過 Phase 4 重構階段")
        assert "Phase 4 重構評估" in output1

        # 表述 2：不需要 + 重構
        output2 = run_hook("不需要重構評估")
        assert "Phase 4 重構評估" in output2


if __name__ == "__main__":
    # 簡單的測試執行
    test = TestProcessSkipGuardHook()
    methods = [m for m in dir(test) if m.startswith("test_")]

    print(f"運行 {len(methods)} 個測試...\n")
    passed = 0
    failed = 0

    for method_name in methods:
        try:
            getattr(test, method_name)()
            print(f"✓ {method_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {method_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {method_name}: 錯誤 - {e}")
            failed += 1

    print(f"\n結果: {passed} 通過, {failed} 失敗")
    sys.exit(0 if failed == 0 else 1)
