#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Layer 1/2 邊界驗證 Hook 測試

測試覆蓋：
- T1-T7: 7 大禁止項單元測試
- T8: 排除規則綜合測試
- T9: 檔案識別測試
- I1-I3: 集成測試
- E1-E3: 邊界測試
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# 動態載入 hook 模組
sys.path.insert(0, str(Path(__file__).parent.parent))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "layer_boundary_validator_hook",
    Path(__file__).parent.parent / "layer-boundary-validator-hook.py",
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_logger():
    """模擬 Logger 物件"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


# ============================================================================
# T1 - Ticket CLI 指令檢測
# ============================================================================


class TestTicketCLIDetection:
    """T1 - /ticket CLI 指令檢測"""

    def test_basic_ticket_create_detection(self, mock_logger):
        """T1.1: 檢測 /ticket create 指令"""
        content = "執行 /ticket create 建立新任務"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 1
        assert violations[0]["type"] == "/ticket CLI 指令"
        assert "/ticket create" in violations[0]["content"]

    def test_multiple_ticket_commands(self, mock_logger):
        """T1: 檢測多個 /ticket 指令"""
        content = "執行 /ticket track\n執行 /ticket handoff\n執行 /ticket resume"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 3

    def test_ticket_in_blockquote_excluded(self, mock_logger):
        """T1.2: blockquote 中的 /ticket 應被排除"""
        content = "> 格式示例：/ticket create"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0

    def test_ticket_in_code_block_excluded(self, mock_logger):
        """T1.3: 程式碼區塊中的 /ticket 應被排除"""
        content = "```\n執行 /ticket create\n```"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0

    def test_ticket_in_inline_code_excluded(self, mock_logger):
        """T1.3b: 行內程式碼中的 /ticket 應被排除"""
        content = "執行 `` /ticket create `` 命令"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0

    def test_ticket_in_html_comment_excluded(self, mock_logger):
        """T1.4: HTML 註解中的 /ticket 應被排除"""
        content = "<!-- 舊版本使用 /ticket create -->"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0


# ============================================================================
# T2 - Agent 名稱檢測
# ============================================================================


class TestAgentNameDetection:
    """T2 - Agent 名稱檢測"""

    def test_all_agent_names_detected(self, mock_logger):
        """T2.1: 檢測所有 Agent 名稱"""
        agents = [
            "lavender-interface-designer",
            "parsley-flutter-developer",
            "sage-test-architect",
            "pepper-test-implementer",
            "cinnamon-refactor-owl",
            "saffron-system-analyst",
            "basil-hook-architect",
            "rosemary-project-manager",
            "oregano-data-miner",
            "thyme-python-developer",
            "ginger-performance-tuner",
        ]

        for agent in agents:
            content = f"派發給 {agent}"
            exclusions = hook_module.extract_exclusions(content, mock_logger)
            violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)
            assert len(violations) >= 1, f"未檢測到 {agent}"

    def test_designer_not_misdetected(self, mock_logger):
        """T2.2: 「設計者」不被誤判"""
        content = "由設計者完成設計"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0

    def test_agent_in_link_excluded(self, mock_logger):
        """T2.3: 參考連結中的 agent 名稱被排除"""
        content = "見 [參考](./agents/lavender-interface-designer.md)"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0


# ============================================================================
# T3 - Hook 系統引用檢測
# ============================================================================


class TestHookSystemDetection:
    """T3 - Hook 系統引用檢測"""

    def test_hook_path_detected(self, mock_logger):
        """T3.1: 檢測 .claude/hooks/ 路徑"""
        content = "Hook 位於 .claude/hooks/ 目錄"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1
        assert ".claude/hooks/" in str([v["content"] for v in violations])

    def test_hook_file_name_detected(self, mock_logger):
        """T3.1b: 檢測 hook 檔案名"""
        content = "ticket-id-validator-hook.py 的實現"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_posttooluse_detected(self, mock_logger):
        """T3.2: 檢測 PostToolUse Hook 類型"""
        content = "使用 PostToolUse 事件"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_hook_in_code_block_excluded(self, mock_logger):
        """T3.3: 程式碼區塊中的 Hook 實作排除"""
        content = '```python\nfrom .claude/hooks/ import hook\n```'
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0


# ============================================================================
# T4 - Decision-Tree 引用檢測
# ============================================================================


class TestDecisionTreeDetection:
    """T4 - Decision-Tree 引用檢測"""

    def test_decision_tree_chinese_detected(self, mock_logger):
        """T4.1: 檢測「決策樹」中文詞彙"""
        content = "見決策樹進行路由"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_decision_tree_english_detected(self, mock_logger):
        """T4.1b: 檢測 decision-tree 英文名稱"""
        content = "按 decision-tree 進行路由"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_decision_tree_level_detected(self, mock_logger):
        """T4.2: 檢測「決策樹第 N 層」引用"""
        layers = ["決策樹第零層", "決策樹第二層", "決策樹第四層"]
        for layer in layers:
            content = f"參考 {layer}"
            exclusions = hook_module.extract_exclusions(content, mock_logger)
            violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)
            assert len(violations) >= 1, f"未檢測到 {layer}"

    def test_single_layer_not_misdetected(self, mock_logger):
        """T4.3: 單獨「第一層」不誤判"""
        content = "在第一層進行檢查"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        # 應該檢測不到違規或只檢測到層級
        found_decision_tree = any(
            "decision-tree" in v["type"].lower() for v in violations
        )
        assert not found_decision_tree


# ============================================================================
# T5 - /parallel-evaluation 工具引用檢測
# ============================================================================


class TestParallelEvaluationDetection:
    """T5 - /parallel-evaluation 工具引用檢測"""

    def test_parallel_evaluation_command_detected(self, mock_logger):
        """T5.1: 檢測 /parallel-evaluation 指令"""
        content = "執行 /parallel-evaluation 進行分析"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_parallel_evaluation_tool_name_detected(self, mock_logger):
        """T5.1b: 檢測 parallel-evaluation 工具名稱"""
        content = "parallel-evaluation 工具"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_multi_perspective_not_misdetected(self, mock_logger):
        """T5.2: 「多視角評估」通用概念不誤判"""
        content = "執行多視角評估"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        found_parallel = any(
            "parallel-evaluation" in v["content"].lower() for v in violations
        )
        assert not found_parallel


# ============================================================================
# T6 - 路徑硬編碼檢測
# ============================================================================


class TestPathDetection:
    """T6 - 路徑硬編碼檢測"""

    def test_claude_path_detected(self, mock_logger):
        """T6.1: 檢測 .claude/ 路徑硬編碼"""
        content = "配置位於 .claude/ 目錄"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_docs_work_logs_detected(self, mock_logger):
        """T6.2: 檢測 docs/work-logs/ 路徑硬編碼"""
        content = "工作日誌存放於 docs/work-logs/ 目錄"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_path_in_link_excluded(self, mock_logger):
        """T6.3: 排除 Markdown 連結中的路徑"""
        content = "[參考](./docs/work-logs/v0.1.0/tickets/)"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0


# ============================================================================
# T7 - Wave/Patch 版本概念檢測
# ============================================================================


class TestVersionConceptDetection:
    """T7 - Wave/Patch 版本概念檢測"""

    def test_wave_number_detected(self, mock_logger):
        """T7.1: 檢測 W 開頭的 Wave 號"""
        waves = ["W3", "W48", "W100"]
        for wave in waves:
            content = f"分配到 {wave}"
            exclusions = hook_module.extract_exclusions(content, mock_logger)
            violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)
            assert len(violations) >= 1, f"未檢測到 {wave}"

    def test_patch_level_detected(self, mock_logger):
        """T7.2: 檢測「Patch」版本級別名詞"""
        content = "推進到下一個 Patch 版本"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1

    def test_minor_level_detected(self, mock_logger):
        """T7.2b: 檢測「Minor」版本級別名詞"""
        content = "發布 Minor 版本"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1


# ============================================================================
# T8 - 排除規則綜合測試
# ============================================================================


class TestExclusionRules:
    """T8 - 排除規則綜合測試"""

    def test_nested_blockquote_and_code(self, mock_logger):
        """T8.1: blockquote 內含程式碼區塊"""
        content = "> 示例：\n> ```\n> /ticket create\n> ```"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0

    def test_unclosed_code_block(self, mock_logger):
        """T8.2: 未閉合的程式碼區塊"""
        content = "```\n/ticket create\n（無閉合反引號）"
        exclusions = hook_module.extract_exclusions(content, mock_logger)

        # 應該視為在程式碼區塊中
        assert len(exclusions) >= 2

    def test_multiple_inline_code(self, mock_logger):
        """T8.2b: 嵌套反引號"""
        content = "執行 `` /ticket create `` 命令"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) == 0


# ============================================================================
# T9 - 檔案識別測試
# ============================================================================


class TestFileIdentification:
    """T9 - Layer 1 檔案識別測試"""

    def test_rules_core_identified_as_layer1(self, mock_logger):
        """T9.1: .claude/rules/core/ 檔案識別"""
        assert hook_module.is_layer1_file(
            ".claude/rules/core/decision-tree.md", mock_logger
        )

    def test_rules_flows_identified_as_layer1(self, mock_logger):
        """T9.1b: .claude/rules/flows/ 檔案識別"""
        assert hook_module.is_layer1_file(
            ".claude/rules/flows/tdd-flow.md", mock_logger
        )

    def test_rules_guides_identified_as_layer1(self, mock_logger):
        """T9.1c: .claude/rules/guides/ 檔案識別"""
        assert hook_module.is_layer1_file(
            ".claude/rules/guides/parallel-dispatch.md", mock_logger
        )

    def test_portable_design_boundary_identified(self, mock_logger):
        """T9.1d: phase0/rules.md 識別"""
        assert hook_module.is_layer1_file(
            ".claude/skills/tdd/references/phase0/rules.md", mock_logger
        )

    def test_agents_not_identified_as_layer1(self, mock_logger):
        """T9.2: .claude/agents/ 檔案排除"""
        assert not hook_module.is_layer1_file(
            ".claude/agents/lavender-interface-designer.md", mock_logger
        )

    def test_ticket_not_identified_as_layer1(self, mock_logger):
        """T9.2b: Ticket 檔案排除"""
        assert not hook_module.is_layer1_file(
            "docs/work-logs/v0.1.0/tickets/0.1.0-W48-001.md", mock_logger
        )


# ============================================================================
# I1 - Hook 執行流程測試
# ============================================================================


class TestHookExecution:
    """I1 - Hook 執行流程測試"""

    def test_format_warning_message(self, mock_logger):
        """I3.1: 警告訊息格式驗證"""
        violations = [
            {
                "line_num": 10,
                "column": 5,
                "type": "/ticket CLI 指令",
                "content": "/ticket create",
                "replacement": "任務系統",
                "item_id": "ticket_cli",
            }
        ]

        message = hook_module.format_warning_message(
            violations, "test.md"
        )

        assert "[WARNING]" in message
        assert "test.md" in message
        assert "Line 10" in message
        assert "/ticket CLI 指令" in message
        assert "任務系統" in message

    def test_generate_hook_output_with_violations(self, mock_logger):
        """I3.1b: 含違規的 Hook 輸出"""
        output = hook_module.generate_hook_output(
            has_violations=True,
            file_path="test.md",
            message="[WARNING] Test",
        )

        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "additionalContext" in output["hookSpecificOutput"]

    def test_generate_hook_output_without_violations(self, mock_logger):
        """I3.1c: 無違規的 Hook 輸出"""
        output = hook_module.generate_hook_output(
            has_violations=False,
            file_path="test.md",
        )

        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


# ============================================================================
# E1-E3 - 邊界測試
# ============================================================================


class TestEdgeCases:
    """E1-E3 - 邊界測試"""

    def test_multiline_violations(self, mock_logger):
        """E1: 多行文字中的違規檢測"""
        content = "執行 /ticket create\n建立 /ticket track\n修改 /ticket resume"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 3

    def test_chinese_characters_handling(self, mock_logger):
        """E1b: 中文字符混合"""
        content = "執行 /ticket create 建立新任務"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1
        assert violations[0]["content"] == "/ticket create"

    def test_table_content_not_excluded(self, mock_logger):
        """E2: 表格內容不被排除"""
        content = "| 欄位 | 說明 |\n| --- | --- |\n| /ticket create | 建立 Ticket |"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        # 表格內容應被掃描
        assert len(violations) >= 1

    def test_utf8_special_chars(self, mock_logger):
        """E3: UTF-8 編碼特殊字符"""
        content = "執行 /ticket create 📌"
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        assert len(violations) >= 1


# ============================================================================
# 集成測試
# ============================================================================


class TestIntegration:
    """集成測試"""

    def test_comprehensive_layer1_scan(self, mock_logger):
        """I2: 綜合 Layer 1 檔案掃描"""
        content = """
# Layer 1 規則文件

## 禁止項示例

應該被檢測的違規項：
- 執行 /ticket create 建立任務
- 派發 lavender-interface-designer
- 使用 PostToolUse Hook
- 見決策樹進行路由
- 執行 /parallel-evaluation
- 配置位於 .claude/ 目錄
- 在 W48 發布

排除的內容：

> 格式示例：
> - 執行 /ticket track
> - 見 [規則](./.claude/rules/core/)

```python
from .claude/hooks/ import hook
execute_hook(/ticket create)
```

<!-- 舊版本使用 /ticket create -->
"""
        exclusions = hook_module.extract_exclusions(content, mock_logger)
        violations = hook_module.scan_prohibited_items(content, exclusions, mock_logger)

        # 應該檢測到多個違規
        assert len(violations) >= 7

        # 驗證排除規則有效
        violation_types = [v["item_id"] for v in violations]
        assert "ticket_cli" in violation_types
        assert "agent_names" in violation_types
        assert "hook_system" in violation_types
        assert "decision_tree" in violation_types
        assert "parallel_evaluation" in violation_types
        assert "path_hardcoding" in violation_types
        assert "version_concepts" in violation_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
