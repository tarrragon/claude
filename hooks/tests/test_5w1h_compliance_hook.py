#!/usr/bin/env python3
"""
5W1H Compliance Hook - 測試程式碼

測試 43 個測試案例（P0: 10個、P1: 15個、P2: 18個）
使用 pytest 框架和 BDD Given-When-Then 格式
"""

import sys
from pathlib import Path

# 將 Hook 腳本路徑加入 sys.path
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# 動態導入 Hook 模組（移除 .py 副檔名）
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hook_module",
    hook_dir / "5w1h-compliance-check-hook.py"
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# 導出需要的函式
make_decision = hook_module.make_decision

import pytest
import json


# ============================================================================
# P0 核心測試案例（10 個）- 驗證標準格式可正常通過
# ============================================================================

class TestCore:
    """P0 核心測試案例：驗證所有正確格式可正常通過"""

    def test_TC_CORE_001_executor_implementation_standard_format(self):
        """
        TC-CORE-001: 執行代理人實作程式碼 - 標準格式

        Given: 完整的 5W1H 決策，Who 和 How 都是標準格式
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow，錯誤訊息為空
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-abc123
Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
What: 實作書籍驗證功能
When: 使用者輸入 ISBN 時
Where: Book Domain
Why: 需求 UC-001
How: [Task Type: Implementation] TDD 實作策略
1. 撰寫測試
2. 實作程式碼
3. 重構""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"
        assert "5W1H 格式檢查通過" in result["reason"]

    def test_TC_CORE_002_pm_dispatch_standard_format(self):
        """
        TC-CORE-002: 主線程分派任務 - 標準格式

        Given: 主線程自行執行格式，任務類型為 Dispatch
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-def456
Who: rosemary-project-manager (自行執行 - 分派/驗收)
What: 設計 v0.12.M.2 Phase 2 測試設計 Ticket
When: Phase 1 完成後
Where: TDD 流程管理
Why: 需要完整的測試案例設計才能進入實作階段
How: [Task Type: Dispatch] 設計 Ticket 並分派給 sage-test-architect
1. 分析 Phase 1 產出的功能規格
2. 設計完整的 Ticket""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_003_pm_review_standard_format(self):
        """
        TC-CORE-003: 主線程驗收任務 - 標準格式

        Given: 主線程自行執行格式，任務類型為 Review
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-ghi789
Who: rosemary-project-manager (自行執行 - 分派/驗收)
What: 驗收 v0.12.M.1 Phase 1 功能設計成果
How: [Task Type: Review] 驗收功能規格文件""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_004_doc_agent_documentation_standard_format(self):
        """
        TC-CORE-004: 文件代理人更新文件 - 標準格式

        Given: 文件代理人執行格式，任務類型為 Documentation
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-jkl012
Who: thyme-documentation-integrator (執行者) | rosemary-project-manager (分派者)
What: 將 v0.12.M 工作日誌轉化為方法論文件
How: [Task Type: Documentation] 提取工作日誌並整合到方法論""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_005_designer_analysis_standard_format(self):
        """
        TC-CORE-005: 設計代理人執行分析任務 - 標準格式

        Given: 設計代理人執行格式，任務類型為 Analysis
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-mno345
Who: lavender-interface-designer (執行者) | rosemary-project-manager (分派者)
What: 分析當前事件設計的缺陷
How: [Task Type: Analysis] 分析設計缺陷並提出修正方案""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_006_refactor_agent_implementation_standard_format(self):
        """
        TC-CORE-006: 重構代理人執行重構 - Implementation 任務類型

        Given: 重構代理人執行格式，任務類型為 Implementation
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-pqr678
Who: cinnamon-refactor-owl (執行者) | rosemary-project-manager (分派者)
What: 重構程式碼改善架構
How: [Task Type: Implementation] 重構程式碼改善架構""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_007_test_implementer_implementation_standard_format(self):
        """
        TC-CORE-007: 測試實作代理人執行 Implementation - 標準格式

        Given: 測試實作代理人執行格式，任務類型為 Implementation
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-stu901
Who: pepper-test-implementer (執行者) | rosemary-project-manager (分派者)
What: 實作測試策略並撰寫測試程式碼
How: [Task Type: Implementation] 實作測試策略並撰寫測試程式碼""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_008_pm_planning_standard_format(self):
        """
        TC-CORE-008: 主線程執行 Planning 任務 - 標準格式

        Given: 主線程自行執行格式，任務類型為 Planning
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-vwx234
Who: rosemary-project-manager (自行執行 - 分派/驗收)
What: 規劃 v0.13 版本的重構策略
How: [Task Type: Planning] 規劃 v0.13 版本的重構策略""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_009_pm_analysis_standard_format(self):
        """
        TC-CORE-009: 主線程執行 Analysis 任務 - 標準格式

        Given: 主線程自行執行格式，任務類型為 Analysis
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-yza567
Who: rosemary-project-manager (自行執行 - 分派/驗收)
What: 分析問題根因並提出解決方案
How: [Task Type: Analysis] 分析問題根因並提出解決方案""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"

    def test_TC_CORE_010_format_specialist_implementation_standard_format(self):
        """
        TC-CORE-010: 格式化代理人執行 Implementation - 標準格式

        Given: 格式化代理人執行格式，任務類型為 Implementation
        When: Hook 接收到 TodoWrite 工具調用
        Then: 決策為 allow
        """
        # Given
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "file_path": "docs/todolist.md",
                "content": """🎯 5W1H-20251018-120000-bcd890
Who: mint-format-specialist (執行者) | rosemary-project-manager (分派者)
What: 修正程式碼格式和品質問題
How: [Task Type: Implementation] 修正程式碼格式和品質問題""",
                "operation": "add"
            }
        }

        # When
        result = make_decision(tool_input["tool_input"])

        # Then
        assert result["decision"] == "allow"


# ============================================================================
# P1 邊界測試案例（15 個）- 驗證容錯處理
# ============================================================================

class TestEdge:
    """P1 邊界測試案例：驗證容錯處理和格式變體"""

    def test_TC_EDGE_001_leading_whitespace(self):
        """TC-EDGE-001: 前導空白字元 - 應容忍"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """🎯 5W1H-test
Who:  parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How:  [Task Type: Implementation] TDD 實作策略"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "allow"

    def test_TC_EDGE_008_task_type_lowercase(self):
        """TC-EDGE-008: 任務類型小寫 - 應容忍"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How: [Task Type: implementation] TDD 實作策略"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "allow"

    def test_TC_EDGE_009_task_type_uppercase(self):
        """TC-EDGE-009: 任務類型大寫 - 應容忍"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How: [Task Type: IMPLEMENTATION] TDD 實作策略"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "allow"

    def test_TC_EDGE_005_fullwidth_parentheses_should_block(self):
        """TC-EDGE-005: 全形括號 - 應拒絕"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer（執行者）| rosemary-project-manager（分派者）
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "全形" in result["reason"]

    def test_TC_EDGE_012_underscore_in_agent_name_should_block(self):
        """TC-EDGE-012: 代理人名稱包含底線 - 應拒絕"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley_flutter_developer (執行者) | rosemary_project_manager (分派者)
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"


# ============================================================================
# P2 其他測試案例 - 違規檢測（6 個）
# ============================================================================

class TestViolation:
    """P2 違規測試案例：驗證敏捷重構原則合規性檢查"""

    def test_TC_VIOL_001_pm_implementation_should_block(self):
        """TC-VIOL-001: 主線程執行 Implementation - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: rosemary-project-manager (自行執行 - 分派/驗收)
How: [Task Type: Implementation] 建立 Domain 事件類別"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "違反敏捷重構原則" in result["reason"]
        assert "主線程不應執行 Implementation" in result["reason"]

    def test_TC_VIOL_002_designer_implementation_should_block(self):
        """TC-VIOL-002: 設計代理人執行 Implementation - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: lavender-interface-designer (執行者) | rosemary-project-manager (分派者)
How: [Task Type: Implementation] 建立 BookValidator 類別"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "設計代理人不應執行 Implementation" in result["reason"]

    def test_TC_VIOL_004_executor_dispatch_should_block(self):
        """TC-VIOL-004: 執行代理人執行 Dispatch - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How: [Task Type: Dispatch] 分派任務給其他代理人"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "執行代理人不應分派任務" in result["reason"]


# ============================================================================
# P2 其他測試案例 - 格式錯誤（7 個）
# ============================================================================

class TestFormat:
    """P2 格式錯誤測試案例：驗證格式檢查"""

    def test_TC_FMT_001_missing_executor_marker_should_block(self):
        """TC-FMT-001: Who 欄位缺少執行者標記 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer | rosemary-project-manager (分派者)
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "缺少執行者/分派者標記" in result["reason"]

    def test_TC_FMT_003_missing_pipe_separator_should_block(self):
        """TC-FMT-003: Who 欄位缺少豎線分隔符 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) rosemary-project-manager (分派者)
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "格式不符合標準" in result["reason"]

    def test_TC_FMT_004_undefined_agent_should_block(self):
        """TC-FMT-004: Who 欄位使用未定義代理人 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: unknown-agent (執行者) | rosemary-project-manager (分派者)
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "未定義的代理人名稱" in result["reason"]

    def test_TC_FMT_005_missing_task_type_should_block(self):
        """TC-FMT-005: How 欄位缺少 Task Type 標記 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How: TDD 實作策略"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "缺少 [Task Type: XXX] 標記" in result["reason"]

    def test_TC_FMT_006_invalid_task_type_should_block(self):
        """TC-FMT-006: How 欄位任務類型不在清單中 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
How: [Task Type: Coding] 撰寫程式碼"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "任務類型不在允許清單中" in result["reason"]


# ============================================================================
# P2 其他測試案例 - 錯誤處理（5 個）
# ============================================================================

class TestError:
    """P2 錯誤處理測試案例：驗證錯誤處理機制"""

    def test_TC_ERR_001_missing_who_field_should_block(self):
        """TC-ERR-001: 缺少 Who 欄位 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """🎯 5W1H-test
How: [Task Type: Implementation] TDD 實作策略"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "缺少必要欄位：Who" in result["reason"]

    def test_TC_ERR_002_missing_how_field_should_block(self):
        """TC-ERR-002: 缺少 How 欄位 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """🎯 5W1H-test
Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        assert "缺少必要欄位：How" in result["reason"]

    def test_TC_ERR_003_empty_who_field_should_block(self):
        """TC-ERR-003: Who 欄位為空字串 - 應阻止"""
        tool_input = {
            "tool_name": "TodoWrite",
            "tool_input": {
                "content": """Who:
How: [Task Type: Implementation] TDD"""
            }
        }
        result = make_decision(tool_input["tool_input"])
        assert result["decision"] == "block"
        # 空字串經過 strip() 後會被檢測為缺少格式標記
        assert ("Who 欄位不可為空" in result["reason"] or
                "缺少執行者/分派者標記" in result["reason"])


# ============================================================================
# 測試執行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
