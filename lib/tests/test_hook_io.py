#!/usr/bin/env python3
"""
hook_io 模組單元測試
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json
from io import StringIO
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
    create_posttooluse_output,
    create_simple_output,
)


class TestReadHookInput(unittest.TestCase):
    """測試 read_hook_input 函式"""

    def test_valid_json_input(self):
        """測試有效的 JSON 輸入"""
        test_input = '{"tool_name": "Edit", "tool_input": {"file_path": "/test.py"}}'
        with patch('sys.stdin', StringIO(test_input)):
            result = read_hook_input()
            self.assertEqual(result["tool_name"], "Edit")
            self.assertEqual(result["tool_input"]["file_path"], "/test.py")

    def test_invalid_json_input(self):
        """測試無效的 JSON 輸入"""
        with patch('sys.stdin', StringIO("invalid json")):
            result = read_hook_input()
            self.assertEqual(result, {})

    def test_empty_input(self):
        """測試空輸入"""
        with patch('sys.stdin', StringIO("")):
            result = read_hook_input()
            self.assertEqual(result, {})


class TestWriteHookOutput(unittest.TestCase):
    """測試 write_hook_output 函式"""

    def test_write_output(self):
        """測試輸出寫入"""
        output = {"decision": "allow", "reason": "test"}
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            write_hook_output(output)
            result = json.loads(mock_stdout.getvalue())
            self.assertEqual(result["decision"], "allow")
            self.assertEqual(result["reason"], "test")


class TestCreatePretoolUseOutput(unittest.TestCase):
    """測試 create_pretooluse_output 函式"""

    def test_basic_output(self):
        """測試基本輸出格式"""
        output = create_pretooluse_output("allow", "Test reason")
        self.assertIn("hookSpecificOutput", output)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecisionReason"], "Test reason")

    def test_output_with_user_prompt(self):
        """測試包含用戶提示的輸出"""
        output = create_pretooluse_output("ask", "Need confirmation", "Continue?")
        self.assertEqual(output["hookSpecificOutput"]["userPrompt"], "Continue?")

    def test_output_with_system_message(self):
        """測試包含系統訊息的輸出"""
        output = create_pretooluse_output("deny", "Blocked", system_message="Error occurred")
        self.assertEqual(output["systemMessage"], "Error occurred")

    def test_output_with_suppress(self):
        """測試抑制輸出標記"""
        output = create_pretooluse_output("deny", "Blocked", suppress_output=True)
        self.assertTrue(output["suppressOutput"])


class TestCreatePosttoolUseOutput(unittest.TestCase):
    """測試 create_posttooluse_output 函式"""

    def test_basic_output(self):
        """測試基本輸出格式"""
        output = create_posttooluse_output("allow", "Passed")
        self.assertEqual(output["decision"], "allow")
        self.assertEqual(output["reason"], "Passed")
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")

    def test_output_with_context(self):
        """測試包含上下文的輸出"""
        output = create_posttooluse_output("allow", "Passed", "## Report")
        self.assertEqual(output["hookSpecificOutput"]["additionalContext"], "## Report")


class TestCreateSimpleOutput(unittest.TestCase):
    """測試 create_simple_output 函式"""

    def test_basic_output(self):
        """測試基本輸出"""
        output = create_simple_output("approve")
        self.assertEqual(output["decision"], "approve")
        self.assertNotIn("reason", output)

    def test_output_with_reason(self):
        """測試包含原因的輸出"""
        output = create_simple_output("approve", "All checks passed")
        self.assertEqual(output["decision"], "approve")
        self.assertEqual(output["reason"], "All checks passed")


if __name__ == "__main__":
    unittest.main()
