#!/usr/bin/env python3
"""
Hook 錯誤恢復機制測試套件

測試目標：
1. 驗證 Hook 攔截後的錯誤訊息格式
2. 驗證錯誤訊息解析邏輯
3. 驗證自動重試機制（模擬）
4. 驗證無限循環防護

版本：v0.12.N.7
作者：rosemary-project-manager
日期：2025-10-18
"""

import pytest
import re
from typing import Dict, Optional, List, Tuple


# ========== 錯誤訊息解析函式 ==========

def parse_agent_dispatch_error(error_message: str) -> Optional[Dict[str, str]]:
    """
    從 Hook 錯誤訊息中解析結構化資訊

    參數:
        error_message: Hook 返回的錯誤訊息

    回傳:
        包含任務類型、當前代理人、正確代理人的字典，無法解析則返回 None
    """
    result = {}

    # 解析任務類型
    task_type_match = re.search(r"任務類型：(.+)", error_message)
    if task_type_match:
        result["task_type"] = task_type_match.group(1).strip()

    # 解析當前代理人
    current_agent_match = re.search(r"當前代理人：(\S+)", error_message)
    if current_agent_match:
        result["current_agent"] = current_agent_match.group(1).strip()

    # 解析正確代理人
    correct_agent_match = re.search(r"正確代理人：(\S+)", error_message)
    if correct_agent_match:
        result["correct_agent"] = correct_agent_match.group(1).strip()

    # 驗證必要欄位
    if "correct_agent" in result:
        return result

    return None


def should_retry(error_message: str) -> bool:
    """
    判斷是否應該自動重試

    參數:
        error_message: 錯誤訊息

    回傳:
        True 如果應該重試，False 否則
    """
    return ("代理人分派錯誤" in error_message and
            "正確代理人：" in error_message)


# ========== 自動重試模擬函式 ==========

class MockHookDenyError(Exception):
    """模擬 Hook deny 錯誤"""
    pass


def simulate_task_dispatch(
    subagent_type: str,
    prompt: str,
    hook_check_func=None
) -> Tuple[bool, Optional[str]]:
    """
    模擬任務分派（用於測試）

    參數:
        subagent_type: 代理人類型
        prompt: 任務描述
        hook_check_func: Hook 檢查函式（可選）

    回傳:
        (是否成功, 錯誤訊息)
    """
    if hook_check_func:
        should_allow, error_msg = hook_check_func(subagent_type, prompt)
        if not should_allow:
            return (False, error_msg)

    return (True, None)


def dispatch_with_auto_retry(
    prompt: str,
    initial_agent: str,
    hook_check_func=None,
    max_retries: int = 1
) -> Tuple[bool, str, List[str]]:
    """
    自動重試的任務分派（測試用模擬）

    參數:
        prompt: 任務描述
        initial_agent: 初始代理人
        hook_check_func: Hook 檢查函式
        max_retries: 最大重試次數

    回傳:
        (是否成功, 最終代理人, 嘗試歷史)
    """
    current_agent = initial_agent
    attempts = [initial_agent]

    for attempt in range(max_retries + 1):
        success, error_msg = simulate_task_dispatch(
            subagent_type=current_agent,
            prompt=prompt,
            hook_check_func=hook_check_func
        )

        if success:
            return (True, current_agent, attempts)

        # 檢查是否應該重試
        if not should_retry(error_msg or ""):
            return (False, current_agent, attempts)

        # 解析正確的代理人
        parsed = parse_agent_dispatch_error(error_msg or "")
        if not parsed or attempt >= max_retries:
            return (False, current_agent, attempts)

        # 更新代理人並重試
        current_agent = parsed["correct_agent"]
        attempts.append(current_agent)

    return (False, current_agent, attempts)


# ========== 測試案例 ==========

class TestErrorMessageParsing:
    """TC_ERROR_RECOVERY_002: 錯誤訊息解析測試"""

    def test_parse_hook_development_error(self):
        """測試 Hook 開發錯誤訊息解析"""
        error_msg = """❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：parsley-flutter-developer
正確代理人：basil-hook-architect

原因：Hook 開發是專業任務，應優先判斷任務類型而非專案類型。"""

        result = parse_agent_dispatch_error(error_msg)

        assert result is not None
        assert result["task_type"] == "Hook 開發"
        assert result["current_agent"] == "parsley-flutter-developer"
        assert result["correct_agent"] == "basil-hook-architect"

    def test_parse_documentation_integration_error(self):
        """測試文件整合錯誤訊息解析"""
        error_msg = """❌ 代理人分派錯誤：
任務類型：文件整合
當前代理人：parsley-flutter-developer
正確代理人：thyme-documentation-integrator"""

        result = parse_agent_dispatch_error(error_msg)

        assert result is not None
        assert result["task_type"] == "文件整合"
        assert result["correct_agent"] == "thyme-documentation-integrator"

    def test_parse_phase4_refactor_error(self):
        """測試 Phase 4 重構錯誤訊息解析"""
        error_msg = """❌ 代理人分派錯誤：
任務類型：Phase 4 重構
當前代理人：basil-hook-architect
正確代理人：cinnamon-refactor-owl"""

        result = parse_agent_dispatch_error(error_msg)

        assert result is not None
        assert result["task_type"] == "Phase 4 重構"
        assert result["correct_agent"] == "cinnamon-refactor-owl"

    def test_parse_invalid_error_message(self):
        """測試無效錯誤訊息"""
        error_msg = "這是一個無效的錯誤訊息"

        result = parse_agent_dispatch_error(error_msg)

        assert result is None

    def test_parse_partial_error_message(self):
        """測試部分錯誤訊息（缺少正確代理人）"""
        error_msg = """任務類型：Hook 開發
當前代理人：parsley-flutter-developer"""

        result = parse_agent_dispatch_error(error_msg)

        assert result is None


class TestShouldRetry:
    """測試重試判斷邏輯"""

    def test_should_retry_agent_dispatch_error(self):
        """測試代理人分派錯誤應該重試"""
        error_msg = """❌ 代理人分派錯誤：
正確代理人：basil-hook-architect"""

        assert should_retry(error_msg) is True

    def test_should_not_retry_other_error(self):
        """測試其他錯誤不應該重試"""
        error_msg = "缺少 UseCase 參考"

        assert should_retry(error_msg) is False

    def test_should_not_retry_empty_message(self):
        """測試空訊息不應該重試"""
        assert should_retry("") is False


class TestAutoRetryMechanism:
    """TC_ERROR_RECOVERY_001 & 003: 自動重試機制測試"""

    def test_correct_dispatch_no_retry(self):
        """測試正確分派無需重試"""
        def mock_hook(agent, prompt):
            # Hook 相關任務 + basil-hook-architect → 允許
            if "Hook" in prompt and agent == "basil-hook-architect":
                return (True, None)
            return (False, f"正確代理人：basil-hook-architect")

        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="開發 Hook 腳本",
            initial_agent="basil-hook-architect",
            hook_check_func=mock_hook
        )

        assert success is True
        assert final_agent == "basil-hook-architect"
        assert len(attempts) == 1

    def test_wrong_dispatch_auto_correct(self):
        """測試錯誤分派自動糾正"""
        def mock_hook(agent, prompt):
            # Hook 相關任務 + parsley → 攔截
            if "Hook" in prompt and agent == "parsley-flutter-developer":
                return (False, """❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：parsley-flutter-developer
正確代理人：basil-hook-architect""")
            # Hook 相關任務 + basil → 允許
            if "Hook" in prompt and agent == "basil-hook-architect":
                return (True, None)
            return (False, "未知錯誤")

        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="開發 Hook 腳本",
            initial_agent="parsley-flutter-developer",
            hook_check_func=mock_hook
        )

        assert success is True
        assert final_agent == "basil-hook-architect"
        assert len(attempts) == 2
        assert attempts == ["parsley-flutter-developer", "basil-hook-architect"]

    def test_multiple_error_corrections(self):
        """測試多次錯誤糾正（階段性）"""
        correction_history = []

        def mock_hook(agent, prompt):
            # 文件整合任務
            if "文件整合" in prompt:
                if agent == "parsley-flutter-developer":
                    correction_history.append((agent, "basil-hook-architect"))
                    return (False, """❌ 代理人分派錯誤：
正確代理人：basil-hook-architect""")
                elif agent == "basil-hook-architect":
                    correction_history.append((agent, "thyme-documentation-integrator"))
                    return (False, """❌ 代理人分派錯誤：
正確代理人：thyme-documentation-integrator""")
                elif agent == "thyme-documentation-integrator":
                    return (True, None)
            return (False, "未知錯誤")

        # 第一次嘗試：parsley → basil (失敗)
        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="文件整合任務",
            initial_agent="parsley-flutter-developer",
            hook_check_func=mock_hook,
            max_retries=1
        )

        # 只重試 1 次，所以會在 basil-hook-architect 停止
        assert success is False
        assert final_agent == "basil-hook-architect"
        assert len(attempts) == 2


class TestInfiniteLoopProtection:
    """TC_ERROR_RECOVERY_004: 無限循環防護測試"""

    def test_max_retries_limit(self):
        """測試最大重試次數限制"""
        retry_count = 0

        def mock_hook(agent, prompt):
            nonlocal retry_count
            retry_count += 1
            # 總是返回錯誤，測試是否會無限循環
            return (False, """❌ 代理人分派錯誤：
正確代理人：another-agent""")

        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="測試任務",
            initial_agent="initial-agent",
            hook_check_func=mock_hook,
            max_retries=3
        )

        assert success is False
        assert len(attempts) <= 4  # 初始 + 最多 3 次重試
        assert retry_count <= 4

    def test_unparseable_error_stops_retry(self):
        """測試無法解析的錯誤停止重試"""
        def mock_hook(agent, prompt):
            # 返回無法解析的錯誤訊息
            return (False, "無效的錯誤訊息格式")

        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="測試任務",
            initial_agent="test-agent",
            hook_check_func=mock_hook,
            max_retries=3
        )

        assert success is False
        assert len(attempts) == 1  # 無法解析，不重試


# ========== 實際場景模擬測試 ==========

class TestRealWorldScenarios:
    """實際場景模擬測試"""

    def test_scenario_hook_development_wrong_dispatch(self):
        """場景：Hook 開發任務錯誤分派給 Flutter 開發者"""
        def mock_hook(agent, prompt):
            if "Hook" in prompt:
                if agent == "parsley-flutter-developer":
                    return (False, """❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：parsley-flutter-developer
正確代理人：basil-hook-architect""")
                elif agent == "basil-hook-architect":
                    return (True, None)
            return (True, None)

        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="開發 Hook 腳本來檢查代理人分派",
            initial_agent="parsley-flutter-developer",
            hook_check_func=mock_hook
        )

        assert success is True
        assert final_agent == "basil-hook-architect"
        assert "parsley-flutter-developer" in attempts
        assert "basil-hook-architect" in attempts

    def test_scenario_phase4_refactor_keyword_confusion(self):
        """場景：Phase 4 重構評估因關鍵字混淆被誤判"""
        def mock_hook(agent, prompt):
            # 如果 prompt 包含 "Hook" 且不是 basil-hook-architect
            if "Hook" in prompt and "Phase 4" in prompt:
                # 這是 v0.12.N 實際發生的誤判
                if agent == "cinnamon-refactor-owl":
                    return (False, """❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：cinnamon-refactor-owl
正確代理人：basil-hook-architect""")
                elif agent == "basil-hook-architect":
                    return (True, None)
            return (True, None)

        # 模擬實際情況：Phase 4 重構評估被誤判為 Hook 開發
        success, final_agent, attempts = dispatch_with_auto_retry(
            prompt="v0.12.N Phase 4: 代理人分派檢查 Hook 重構評估",
            initial_agent="cinnamon-refactor-owl",
            hook_check_func=mock_hook
        )

        # 當前會被糾正為 basil-hook-architect（誤判）
        # 這證明了需要改進關鍵字檢測邏輯
        assert success is True
        assert final_agent == "basil-hook-architect"  # 實際是誤判


# ========== 執行測試 ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
