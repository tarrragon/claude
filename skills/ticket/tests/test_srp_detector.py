"""
SRP（單一職責原則）偵測機制單元測試

測試 SRP 自動偵測機制的兩層分工：
1. create 層輕量提示：what 多目標和 acceptance 跨模組偵測
2. SA 層詳細檢查：四大檢查項目（文件層面，不自動化）
"""
import pytest
from typing import List, Tuple

from ticket_system.lib.acceptance_auditor import (
    _detect_srp_multi_target,
    _detect_srp_cross_module,
    detect_srp_violations,
)
from ticket_system.lib.constants import (
    SRP_WHAT_CONJUNCTIONS,
    SRP_ACCEPTANCE_MODULE_THRESHOLD,
)


# ============================================================
# 測試 _detect_srp_multi_target
# ============================================================

class TestDetectSrpMultiTarget:
    """_detect_srp_multi_target 函式測試"""

    # 場景 1-6：五個連接詞各自觸發及多個並列連接詞

    def test_what_contains_conjunction_和(self):
        """場景 1：what 含並列連接詞「和」"""
        # Given
        what_text = "實作 create 層偵測和 SA 層審查"

        # When
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)

        # Then
        assert has_conjunction is True
        assert "和" in found_conjunctions
        assert isinstance(found_conjunctions, list)

    def test_what_contains_conjunction_與(self):
        """場景 2：what 含並列連接詞「與」"""
        what_text = "新增功能 X 與優化功能 Y"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        assert "與" in found_conjunctions

    def test_what_contains_conjunction_及(self):
        """場景 3：what 含並列連接詞「及」"""
        what_text = "建立模組 A 及更新模組 B"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        assert "及" in found_conjunctions

    def test_what_contains_conjunction_並(self):
        """場景 4：what 含並列連接詞「並」"""
        what_text = "重構 X 並新增 Y"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        assert "並" in found_conjunctions

    def test_what_contains_conjunction_同時(self):
        """場景 5：what 含並列連接詞「同時」"""
        what_text = "同時修復 A 和更新 B"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        # 應該至少找到「同時」或「和」
        assert len(found_conjunctions) > 0

    def test_what_contains_multiple_conjunctions(self):
        """場景 6：what 含多個並列連接詞"""
        what_text = "實作 A 和修復 B 及優化 C"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        assert "和" in found_conjunctions
        assert "及" in found_conjunctions

    # 場景 7-8：不含連接詞或修飾詞不觸發

    def test_what_no_conjunction(self):
        """場景 7：what 不含連接詞"""
        what_text = "實作 SRP 自動偵測機制"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is False
        assert found_conjunctions == []

    def test_what_with_modifier_的(self):
        """場景 8：what 含「的」修飾詞（不觸發）"""
        what_text = "實作 SRP 自動偵測機制的雙層分工"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is False
        assert found_conjunctions == []

    # 場景 9-11：邊界條件

    def test_what_empty_string(self):
        """場景 9：what 為空字串"""
        what_text = ""
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is False
        assert found_conjunctions == []

    def test_what_none_value(self):
        """場景 10：what 為 None（邊界條件，Guard Clause）"""
        what_text = None
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is False
        assert found_conjunctions == []

    def test_what_only_conjunction(self):
        """場景 11：what 只包含連接詞"""
        what_text = "和"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        # 應不觸發：what 長度 1，被 len(cleaned) < 2 Guard Clause 攔截
        assert has_conjunction is False
        assert found_conjunctions == []

    def test_what_with_conjunction_at_end(self):
        """場景 12：what 含連接詞但在句末"""
        what_text = "實作功能和"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        # 根據設計決策，仍會偵測到「和」
        assert has_conjunction is True
        assert "和" in found_conjunctions

    def test_what_with_multiple_same_conjunction(self):
        """場景 13：what 含多個相同連接詞"""
        what_text = "實作 A 和修復 B 和優化 C"
        has_conjunction, found_conjunctions = _detect_srp_multi_target(what_text)
        assert has_conjunction is True
        assert "和" in found_conjunctions


# ============================================================
# 測試 _detect_srp_cross_module
# ============================================================

class TestDetectSrpCrossModule:
    """_detect_srp_cross_module 函式測試"""

    # 場景 1：3 個以上模組，超過閾值

    def test_acceptance_three_modules(self):
        """場景 1：驗收條件提及 3 個不同模組（超過閾值 2）"""
        # Given
        acceptance = [
            "確保 create.py 實作正確",
            "驗證 acceptance_auditor.py 邏輯",
            "檢查 constants.py 常數"
        ]

        # When
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)

        # Then
        assert is_cross_module is True
        assert len(detected_modules) >= 3

    # 場景 2：2 個模組（等於閾值，不觸發）

    def test_acceptance_two_modules(self):
        """場景 2：驗收條件提及 2 個模組（等於閾值，不觸發）"""
        acceptance = [
            "create.py 實作完成",
            "constants.py 常數定義完成"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 3：1 個模組

    def test_acceptance_single_module(self):
        """場景 3：驗收條件提及 1 個模組"""
        acceptance = [
            "create.py 實作完成",
            "create 命令執行成功"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 4：無法識別模組（純中文）

    def test_acceptance_no_module_identification(self):
        """場景 4：驗收條件無法識別模組（純中文，不誤報）"""
        acceptance = [
            "實作完成",
            "測試通過",
            "文件完成"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 5：空陣列

    def test_acceptance_empty_list(self):
        """場景 5：驗收條件為空陣列"""
        acceptance = []
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 6：None（邊界條件）

    def test_acceptance_none_value(self):
        """場景 6：驗收條件為 None（邊界條件）"""
        acceptance = None
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 7：僅 .py 檔案識別（不支援 PascalCase）

    def test_acceptance_with_pascal_case(self):
        """場景 7：驗收條件含 PascalCase（不識別，無需超過閾值）"""
        acceptance = [
            "SrpDetector 類別設計",
            "CreateMessages 常數新增",
            "ParallelAnalyzer 整合"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        # PascalCase 不被識別為模組，無法滿足跨模組偵測條件
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 8：混合檔案路徑（PascalCase 不被識別）

    def test_acceptance_mixed_identification_types(self):
        """場景 8：驗收條件混合檔案路徑和 PascalCase（只識別 .py）"""
        acceptance = [
            "ticket_system/lib/acceptance_auditor.py 新增函式",
            "CreateMessages 新增常數",  # PascalCase 不識別
            "constants.py 新增定義"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        # 只識別 2 個 .py 檔案，不超過閾值 2
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 9：重複模組名稱

    def test_acceptance_with_duplicate_modules(self):
        """場景 9：驗收條件含重複模組名稱"""
        acceptance = [
            "create.py 功能 1",
            "create.py 功能 2",
            "acceptance_auditor.py 功能 1",
            "acceptance_auditor.py 功能 2"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        # 應識別出 2 個不同模組，不超過閾值
        assert is_cross_module is False
        assert detected_modules == []

    # 場景 10：含非字串元素

    def test_acceptance_with_non_string_elements(self):
        """場景 10：驗收條件清單含非字串元素"""
        acceptance = [
            "create.py 實作",
            123,
            None,
            "constants.py 定義"
        ]
        is_cross_module, detected_modules = _detect_srp_cross_module(acceptance)
        # 應優雅處理，不拋出例外
        # 結果應與 ["create.py 實作", "constants.py 定義"] 相同
        assert isinstance(is_cross_module, bool)
        assert isinstance(detected_modules, list)


# ============================================================
# 測試 detect_srp_violations（整合測試）
# ============================================================

class TestDetectSrpViolations:
    """detect_srp_violations 函式整合測試"""

    # 場景 1：what 含連接詞，acceptance 為空

    def test_srp_what_conjunction_no_acceptance(self):
        """場景 1：what 含連接詞，acceptance 為空"""
        # Given
        what = "實作 A 和修復 B"
        acceptance = None

        # When
        warnings = detect_srp_violations(what, acceptance)

        # Then
        assert len(warnings) > 0
        # 應包含 what 多目標的警告
        assert any("連接詞" in w for w in warnings)

    # 場景 2：what 無連接詞，acceptance 含 3 個模組

    def test_srp_no_what_conjunction_cross_module(self):
        """場景 2：what 無連接詞，acceptance 含 3 個模組"""
        what = "實作 SRP 機制"
        acceptance = [
            "create.py 實作",
            "auditor.py 檢查",
            "constants.py 定義"
        ]
        warnings = detect_srp_violations(what, acceptance)
        assert len(warnings) > 0
        # 應包含跨模組的警告
        assert any("模組" in w for w in warnings)

    # 場景 3：what 含連接詞，acceptance 也含 3 個模組

    def test_srp_both_what_and_acceptance_issues(self):
        """場景 3：what 含連接詞，acceptance 也含 3 個模組"""
        what = "實作 A 和修復 B"
        acceptance = [
            "create.py 實作",
            "auditor.py 檢查",
            "constants.py 定義"
        ]
        warnings = detect_srp_violations(what, acceptance)
        assert len(warnings) >= 2  # 應有兩個警告

    # 場景 4：what 無連接詞，acceptance 無跨模組

    def test_srp_no_issues(self):
        """場景 4：what 無連接詞，acceptance 無跨模組"""
        what = "實作 SRP 機制"
        acceptance = [
            "功能實作完成",
            "測試通過"
        ]
        warnings = detect_srp_violations(what, acceptance)
        assert warnings == []

    # 場景 5：what 為 None

    def test_srp_what_none(self):
        """場景 5：what 為 None"""
        what = None
        acceptance = []
        warnings = detect_srp_violations(what, acceptance)
        assert warnings == []

    # 場景 6：what 和 acceptance 都為 None

    def test_srp_both_none(self):
        """場景 6：what 和 acceptance 都為 None"""
        what = None
        acceptance = None
        warnings = detect_srp_violations(what, acceptance)
        assert warnings == []

    # 場景 7：acceptance 為空陣列

    def test_srp_what_conjunction_empty_acceptance(self):
        """場景 7：acceptance 為空陣列"""
        what = "實作 A 和修復 B"
        acceptance = []
        warnings = detect_srp_violations(what, acceptance)
        assert len(warnings) > 0
        # 只有 what 觸發
        assert any("連接詞" in w for w in warnings)

    # 場景 8：acceptance 清單含 None 元素

    def test_srp_acceptance_with_none_element(self):
        """場景 8：acceptance 清單含 None 元素"""
        what = "實作 SRP"
        acceptance = [
            "create.py 實作",
            None,
            "constants.py 定義"
        ]
        warnings = detect_srp_violations(what, acceptance)
        # 應優雅處理，與 ["create.py 實作", "constants.py 定義"] 相同
        # 2 個模組，不超過閾值
        assert warnings == []


# ============================================================
# 整合測試：在 create 流程中的行為
# ============================================================

class TestSrpInCreateCommand:
    """create 命令中的 SRP 偵測整合測試"""

    def test_create_with_srp_multi_target_warning(self):
        """場景 1：create 執行時，what 含連接詞"""
        # Given
        what = "實作A和修復B"
        acceptance = None

        # When
        warnings = detect_srp_violations(what, acceptance)

        # Then
        # 應偵測到 SRP 疑慮
        # 應包含警告訊息
        assert len(warnings) > 0
        # 警告應包含「連接詞」或「Atomic Ticket」字樣
        assert any("Atomic" in w or "連接詞" in w for w in warnings)

    def test_create_with_srp_cross_module_warning(self):
        """場景 2：create 執行時，acceptance 跨模組"""
        # Given
        what = "實作 SRP 機制"
        acceptance = [
            "create.py 實作完成",
            "auditor.py 驗收通過",
            "constants.py 常數定義完成"
        ]

        # When
        warnings = detect_srp_violations(what, acceptance)

        # Then
        assert len(warnings) > 0
        # 警告應包含「模組」或「Atomic Ticket」字樣
        assert any("模組" in w or "Atomic" in w for w in warnings)

    def test_create_without_srp_warning(self):
        """場景 3：create 執行時，無 SRP 警告"""
        # Given
        what = "實作 SRP 機制"
        acceptance = [
            "功能完成",
            "測試通過"
        ]

        # When
        warnings = detect_srp_violations(what, acceptance)

        # Then
        # 應無 SRP 疑慮
        assert warnings == []
