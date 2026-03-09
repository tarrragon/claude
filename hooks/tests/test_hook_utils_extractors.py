#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook_utils.py 中提取函式的單元測試

測試核心功能：
- extract_tool_input(): 提取 tool_input 欄位
- extract_tool_response(): 提取 tool_response 欄位

覆蓋場景：
- 正常情況（有效的 dict 欄位）
- 空輸入（None、空 dict）
- 缺失欄位
- 型別錯誤（非 dict 型別）
- 日誌記錄
"""

import sys
import pytest
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_utils import extract_tool_input, extract_tool_response


# ============================================================================
# 測試 extract_tool_input
# ============================================================================

class TestExtractToolInput:
    """extract_tool_input 函式測試"""

    def test_extract_tool_input_normal(self):
        """測試正常情況：有效的 tool_input dict"""
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/path/to/file.py",
                "content": "code here"
            }
        }
        result = extract_tool_input(input_data)
        assert result == {"file_path": "/path/to/file.py", "content": "code here"}

    def test_extract_tool_input_empty_dict(self):
        """測試 tool_input 為空 dict"""
        input_data = {"tool_input": {}}
        result = extract_tool_input(input_data)
        assert result == {}

    def test_extract_tool_input_missing_field(self):
        """測試 tool_input 欄位缺失"""
        input_data = {"tool_name": "Read", "other": "value"}
        result = extract_tool_input(input_data)
        assert result == {}

    def test_extract_tool_input_none_field(self):
        """測試 tool_input 欄位為 None"""
        input_data = {"tool_input": None}
        result = extract_tool_input(input_data)
        assert result == {}

    def test_extract_tool_input_none_input_data(self):
        """測試 input_data 為 None"""
        result = extract_tool_input(None)
        assert result == {}

    def test_extract_tool_input_empty_input_data(self):
        """測試 input_data 為空 dict"""
        result = extract_tool_input({})
        assert result == {}

    def test_extract_tool_input_non_dict_input_data(self):
        """測試 input_data 為非 dict 型別"""
        assert extract_tool_input("not a dict") == {}
        assert extract_tool_input(123) == {}
        assert extract_tool_input([1, 2, 3]) == {}

    def test_extract_tool_input_non_dict_field(self):
        """測試 tool_input 欄位為非 dict 型別"""
        input_data = {"tool_input": "not a dict"}
        result = extract_tool_input(input_data)
        assert result == {}

        input_data = {"tool_input": ["list", "value"]}
        result = extract_tool_input(input_data)
        assert result == {}

        input_data = {"tool_input": 123}
        result = extract_tool_input(input_data)
        assert result == {}

    def test_extract_tool_input_multiple_fields(self):
        """測試 tool_input 含多個欄位"""
        input_data = {
            "tool_input": {
                "file_path": "test.py",
                "old_string": "old",
                "new_string": "new",
                "extra": "value"
            }
        }
        result = extract_tool_input(input_data)
        assert len(result) == 4
        assert result["file_path"] == "test.py"
        assert result["old_string"] == "old"
        assert result["new_string"] == "new"
        assert result["extra"] == "value"

    def test_extract_tool_input_with_logger(self):
        """測試含 logger 參數"""
        logger = MagicMock(spec=logging.Logger)
        input_data = {"tool_input": {"key": "value"}}
        result = extract_tool_input(input_data, logger=logger)
        assert result == {"key": "value"}
        logger.debug.assert_called()

    def test_extract_tool_input_logger_none_input(self):
        """測試 logger 記錄 None 輸入"""
        logger = MagicMock(spec=logging.Logger)
        extract_tool_input(None, logger=logger)
        logger.debug.assert_called()

    def test_extract_tool_input_logger_missing_field(self):
        """測試 logger 記錄缺失欄位"""
        logger = MagicMock(spec=logging.Logger)
        extract_tool_input({}, logger=logger)
        logger.debug.assert_called()


# ============================================================================
# 測試 extract_tool_response
# ============================================================================

class TestExtractToolResponse:
    """extract_tool_response 函式測試"""

    def test_extract_tool_response_normal(self):
        """測試正常情況：有效的 tool_response dict"""
        input_data = {
            "tool_name": "Bash",
            "tool_response": {
                "stdout": "command output",
                "stderr": "",
                "exit_code": 0
            }
        }
        result = extract_tool_response(input_data)
        assert result == {
            "stdout": "command output",
            "stderr": "",
            "exit_code": 0
        }

    def test_extract_tool_response_empty_dict(self):
        """測試 tool_response 為空 dict"""
        input_data = {"tool_response": {}}
        result = extract_tool_response(input_data)
        assert result == {}

    def test_extract_tool_response_missing_field(self):
        """測試 tool_response 欄位缺失"""
        input_data = {"tool_name": "Bash", "other": "value"}
        result = extract_tool_response(input_data)
        assert result == {}

    def test_extract_tool_response_none_field(self):
        """測試 tool_response 欄位為 None"""
        input_data = {"tool_response": None}
        result = extract_tool_response(input_data)
        assert result == {}

    def test_extract_tool_response_none_input_data(self):
        """測試 input_data 為 None"""
        result = extract_tool_response(None)
        assert result == {}

    def test_extract_tool_response_empty_input_data(self):
        """測試 input_data 為空 dict"""
        result = extract_tool_response({})
        assert result == {}

    def test_extract_tool_response_non_dict_input_data(self):
        """測試 input_data 為非 dict 型別"""
        assert extract_tool_response("not a dict") == {}
        assert extract_tool_response(123) == {}
        assert extract_tool_response([1, 2, 3]) == {}

    def test_extract_tool_response_non_dict_field(self):
        """測試 tool_response 欄位為非 dict 型別"""
        input_data = {"tool_response": "not a dict"}
        result = extract_tool_response(input_data)
        assert result == {}

        input_data = {"tool_response": ["list", "value"]}
        result = extract_tool_response(input_data)
        assert result == {}

        input_data = {"tool_response": 123}
        result = extract_tool_response(input_data)
        assert result == {}

    def test_extract_tool_response_with_stdout_stderr(self):
        """測試含 stdout/stderr 的常見欄位"""
        input_data = {
            "tool_response": {
                "stdout": "success output",
                "stderr": "warning message",
                "exit_code": 0
            }
        }
        result = extract_tool_response(input_data)
        assert result["stdout"] == "success output"
        assert result["stderr"] == "warning message"
        assert result["exit_code"] == 0

    def test_extract_tool_response_with_various_fields(self):
        """測試含各種不同欄位"""
        input_data = {
            "tool_response": {
                "stdout": "output",
                "success": True,
                "data": {"key": "value"},
                "timestamp": "2026-03-10T10:00:00"
            }
        }
        result = extract_tool_response(input_data)
        assert len(result) == 4
        assert result["success"] is True
        assert isinstance(result["data"], dict)

    def test_extract_tool_response_with_logger(self):
        """測試含 logger 參數"""
        logger = MagicMock(spec=logging.Logger)
        input_data = {"tool_response": {"stdout": "test"}}
        result = extract_tool_response(input_data, logger=logger)
        assert result == {"stdout": "test"}
        logger.debug.assert_called()

    def test_extract_tool_response_logger_none_input(self):
        """測試 logger 記錄 None 輸入"""
        logger = MagicMock(spec=logging.Logger)
        extract_tool_response(None, logger=logger)
        logger.debug.assert_called()

    def test_extract_tool_response_logger_missing_field(self):
        """測試 logger 記錄缺失欄位"""
        logger = MagicMock(spec=logging.Logger)
        extract_tool_response({}, logger=logger)
        logger.debug.assert_called()


# ============================================================================
# 整合測試：模擬實際 Hook 使用場景
# ============================================================================

class TestIntegrationWithRealHookPatterns:
    """整合測試：模擬實際 Hook 中的使用模式"""

    def test_pattern_file_access_guard(self):
        """模擬 ticket-file-access-guard-hook 的使用模式"""
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "test.py",
                "content": "code"
            },
            "tool_response": {
                "stdout": "File written",
                "stderr": "",
                "exit_code": 0
            }
        }
        tool_input = extract_tool_input(input_data)
        tool_response = extract_tool_response(input_data)

        file_path = tool_input.get("file_path", "")
        stdout = tool_response.get("stdout", "")
        exit_code = tool_response.get("exit_code", -1)

        assert file_path == "test.py"
        assert stdout == "File written"
        assert exit_code == 0

    def test_pattern_commit_handoff_hook(self):
        """模擬 commit-handoff-hook 的使用模式"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "git commit -m 'test'"
            },
            "tool_response": {
                "stdout": "[main abcd123] test",
                "stderr": "",
                "exit_code": 0
            }
        }
        tool_input = extract_tool_input(input_data)
        tool_response = extract_tool_response(input_data)

        command = tool_input.get("command", "")
        stdout = tool_response.get("stdout", "")

        assert "commit" in command
        assert "[main" in stdout

    def test_pattern_handoff_cleanup_hook(self):
        """模擬 handoff-cleanup-hook 的使用模式"""
        input_data = {
            "tool_response": {
                "stdout": "[OK] handoff 已完成",
                "stderr": "",
                "exit_code": 0
            }
        }
        tool_response = extract_tool_response(input_data)

        stdout = tool_response.get("stdout", "")
        stderr = tool_response.get("stderr", "")
        exit_code = tool_response.get("exit_code", -1)

        is_success = (exit_code == 0) and "[OK]" in stdout

        assert is_success is True
        assert stderr == ""

    def test_pattern_with_missing_tool_response(self):
        """模擬工具不返回 tool_response 的情況（如 SessionStart）"""
        input_data = {
            "event_type": "SessionStart"
            # 無 tool_response
        }
        tool_response = extract_tool_response(input_data)
        assert tool_response == {}

    def test_pattern_with_empty_tool_input(self):
        """模擬無參數的工具調用"""
        input_data = {
            "tool_name": "Read",
            "tool_input": {}
        }
        tool_input = extract_tool_input(input_data)
        file_path = tool_input.get("file_path", "")
        assert file_path == ""


# ============================================================================
# 邊界測試
# ============================================================================

class TestEdgeCases:
    """邊界和異常情況測試"""

    def test_deeply_nested_tool_input(self):
        """測試深層嵌套的 tool_input"""
        input_data = {
            "tool_input": {
                "level1": {
                    "level2": {
                        "level3": "value"
                    }
                }
            }
        }
        result = extract_tool_input(input_data)
        assert result["level1"]["level2"]["level3"] == "value"

    def test_tool_input_with_special_characters(self):
        """測試含特殊字元的 tool_input"""
        input_data = {
            "tool_input": {
                "file_path": "/path/with/special/chars/[].txt",
                "content": "content\nwith\nnewlines\t and tabs",
                "unicode": "中文內容 emoji 😀"
            }
        }
        result = extract_tool_input(input_data)
        assert "[" in result["file_path"]
        assert "\n" in result["content"]
        assert "中文" in result["unicode"]

    def test_tool_response_with_null_values(self):
        """測試 tool_response 含 null 值的欄位"""
        input_data = {
            "tool_response": {
                "stdout": "output",
                "stderr": None,
                "extra": None
            }
        }
        result = extract_tool_response(input_data)
        assert result["stdout"] == "output"
        assert result["stderr"] is None
        assert result["extra"] is None

    def test_tool_input_with_boolean_values(self):
        """測試 tool_input 含布林值"""
        input_data = {
            "tool_input": {
                "is_valid": True,
                "has_error": False,
                "count": 0
            }
        }
        result = extract_tool_input(input_data)
        assert result["is_valid"] is True
        assert result["has_error"] is False
        assert result["count"] == 0

    def test_large_tool_response(self):
        """測試大型 tool_response（如長 stdout）"""
        large_output = "x" * 100000
        input_data = {
            "tool_response": {
                "stdout": large_output,
                "exit_code": 0
            }
        }
        result = extract_tool_response(input_data)
        assert len(result["stdout"]) == 100000

    def test_multiple_calls_independence(self):
        """測試多次調用相互獨立（不污染 default 值）"""
        input_data1 = {"tool_input": {"key1": "value1"}}
        input_data2 = {"tool_input": {"key2": "value2"}}

        result1 = extract_tool_input(input_data1)
        result2 = extract_tool_input(input_data2)

        assert "key1" in result1
        assert "key2" in result2
        assert "key1" not in result2
        assert "key2" not in result1


# ============================================================================
# 執行測試
# ============================================================================

if __name__ == "__main__":
    # 可直接執行此檔案進行測試
    pytest.main([__file__, "-v", "-s"])
