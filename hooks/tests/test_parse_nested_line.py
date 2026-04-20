#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 _parse_nested_line 重構後的行為

重構目標：
1. 消除副作用（不再修改 result dict）
2. 使回傳值語義明確（使用 NamedTuple）
3. 保持 parse_ticket_frontmatter 的公開行為不變
"""

import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_utils import parse_ticket_frontmatter
from hook_utils.hook_ticket import _parse_nested_line, _NestedLineResult


class TestParseNestedLine:
    """測試 _parse_nested_line 函式的重構後行為"""

    def test_multiline_mode_with_key(self):
        """測試多行模式（multiline_marker 已設定）"""
        result = _parse_nested_line(
            line="  This is a line",
            current_key="description",
            multiline_marker="|"
        )

        # 驗證回傳值型別
        assert isinstance(result, _NestedLineResult)
        assert result.multiline_marker == "|"
        assert result.update_action is not None

        # 驗證回傳的動作
        key, value, is_nested_dict = result.update_action
        assert key == "description"
        assert value == "This is a line"
        assert is_nested_dict is False

    def test_multiline_mode_without_key(self):
        """測試多行模式但沒有當前鍵"""
        result = _parse_nested_line(
            line="  This is a line",
            current_key=None,
            multiline_marker="|"
        )

        assert isinstance(result, _NestedLineResult)
        assert result.multiline_marker == "|"
        assert result.update_action is None

    def test_nested_dict_mode(self):
        """測試嵌套鍵值對模式"""
        result = _parse_nested_line(
            line="  author: John Doe",
            current_key="metadata",
            multiline_marker=None
        )

        assert isinstance(result, _NestedLineResult)
        assert result.multiline_marker is None
        assert result.update_action is not None

        key, value, is_nested_dict = result.update_action
        assert key == "metadata"
        assert isinstance(value, dict)
        assert value == {"author": "John Doe"}
        assert is_nested_dict is True

    def test_nested_dict_with_quoted_value(self):
        """測試嵌套鍵值對的引號移除"""
        result = _parse_nested_line(
            line='  priority: "high"',
            current_key="metadata",
            multiline_marker=None
        )

        key, value, is_nested_dict = result.update_action
        assert value == {"priority": "high"}

    def test_nested_dict_without_key(self):
        """測試無當前鍵時的嵌套鍵值對"""
        result = _parse_nested_line(
            line="  author: test",
            current_key=None,
            multiline_marker=None
        )

        assert result.update_action is None

    def test_line_with_no_colon_multiline_mode(self):
        """測試無冒號的行在非多行模式"""
        result = _parse_nested_line(
            line="  Some text without colon",
            current_key="key",
            multiline_marker=None
        )

        assert result.multiline_marker is None
        assert result.update_action is None


class TestParseTicketFrontmatter:
    """測試 parse_ticket_frontmatter 的端到端行為"""

    def test_simple_frontmatter(self):
        """測試簡單的 frontmatter"""
        content = """---
ticket_id: "0.1.0-W1-001"
version: "0.1.0"
status: "pending"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['ticket_id'] == "0.1.0-W1-001"
        assert result['version'] == "0.1.0"
        assert result['status'] == "pending"

    def test_nested_dict_frontmatter(self):
        """測試包含嵌套結構的 frontmatter"""
        content = """---
ticket_id: "0.1.0-W1-002"
metadata:
  author: "test-author"
  priority: "high"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['ticket_id'] == "0.1.0-W1-002"
        assert isinstance(result['metadata'], dict)
        assert result['metadata']['author'] == "test-author"
        assert result['metadata']['priority'] == "high"

    def test_multiline_string(self):
        """測試包含多行字串的 frontmatter"""
        content = """---
ticket_id: "0.1.0-W1-003"
description: |
  This is a multi-line
  description that spans
  multiple lines
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['ticket_id'] == "0.1.0-W1-003"
        assert isinstance(result['description'], str)
        assert "multi-line" in result['description']
        assert "multiple lines" in result['description']
        # 檢查換行符
        lines = result['description'].split('\n')
        assert len(lines) == 3
        assert lines[0] == "This is a multi-line"
        assert lines[2] == "multiple lines"

    def test_mixed_structure(self):
        """測試混合結構（簡單值、嵌套字典、多行字串）"""
        content = """---
id: "0.1.0-W1-004"
config:
  env: "production"
  timeout: "30s"
notes: |
  Note line 1
  Note line 2
status: "active"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        # 簡單值
        assert result['id'] == "0.1.0-W1-004"
        assert result['status'] == "active"

        # 嵌套字典
        assert isinstance(result['config'], dict)
        assert result['config']['env'] == "production"
        assert result['config']['timeout'] == "30s"

        # 多行字串
        assert "Note line 1" in result['notes']
        assert "Note line 2" in result['notes']

    def test_empty_frontmatter(self):
        """測試空的 frontmatter"""
        content = """---
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)
        assert result == {} or result is None

    def test_no_frontmatter(self):
        """測試無 frontmatter 的內容"""
        content = """# 執行日誌

Some content
"""
        result = parse_ticket_frontmatter(content)
        assert result == {}

    def test_multiline_with_different_markers(self):
        """測試不同的多行標記"""
        # 測試 |
        content1 = """---
text1: |
  Line 1
  Line 2
---

# 執行日誌
"""
        result1 = parse_ticket_frontmatter(content1)
        assert "Line 1" in result1['text1']
        assert "Line 2" in result1['text1']

        # 測試 |-（去除末尾換行）
        content2 = """---
text2: |-
  Line 1
  Line 2
---

# 執行日誌
"""
        result2 = parse_ticket_frontmatter(content2)
        assert "Line 1" in result2['text2']
        assert "Line 2" in result2['text2']

    def test_nested_dict_multiple_keys(self):
        """測試嵌套字典有多個鍵"""
        content = """---
metadata:
  author: "Alice"
  role: "engineer"
  level: "senior"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert len(result['metadata']) == 3
        assert result['metadata']['author'] == "Alice"
        assert result['metadata']['role'] == "engineer"
        assert result['metadata']['level'] == "senior"

    def test_no_side_effects(self):
        """測試確認無副作用（調用多次結果相同）"""
        content = """---
id: "0.1.0-W1-005"
config:
  debug: "true"
---

# 執行日誌
"""
        # 第一次調用
        result1 = parse_ticket_frontmatter(content)
        assert result1['id'] == "0.1.0-W1-005"
        assert result1['config']['debug'] == "true"

        # 第二次調用（應該得到相同結果，無副作用污染）
        result2 = parse_ticket_frontmatter(content)
        assert result2['id'] == "0.1.0-W1-005"
        assert result2['config']['debug'] == "true"

        # 驗證結果相同
        assert result1 == result2

    def test_two_space_indented_list_items(self):
        """測試 2 格縮排的列表項目（真實 Ticket 格式）"""
        content = """---
id: "0.1.0-W34-011"
where:
  layer: hooks
  files:
  - hook_utils/hook_ticket.py
  - tests/test_parse.py
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        # 驗證結構
        assert result['id'] == "0.1.0-W34-011"
        assert isinstance(result['where'], dict)
        assert result['where']['layer'] == "hooks"

        # 驗證列表項目被正確累積
        files = result['where']['files']
        assert isinstance(files, str)
        assert "hook_utils/hook_ticket.py" in files
        assert "tests/test_parse.py" in files

        # 驗證項目用換行符分隔
        file_list = [f for f in files.split('\n') if f]
        assert len(file_list) == 2
        assert file_list[0] == "hook_utils/hook_ticket.py"
        assert file_list[1] == "tests/test_parse.py"

    def test_four_space_indented_list_items(self):
        """測試 4 格縮排的列表項目（深層嵌套）"""
        content = """---
id: "0.1.0-W34-012"
where:
  files:
    - deep_item1.py
    - deep_item2.py
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        # 驗證結構
        assert result['id'] == "0.1.0-W34-012"
        assert isinstance(result['where'], dict)

        # 驗證 4 格縮排的列表項目
        files = result['where']['files']
        assert isinstance(files, str)
        assert "deep_item1.py" in files
        assert "deep_item2.py" in files

        file_list = [f for f in files.split('\n') if f]
        assert len(file_list) == 2
        assert file_list[0] == "deep_item1.py"
        assert file_list[1] == "deep_item2.py"

    def test_mixed_nested_structure_with_lists(self):
        """測試混合嵌套結構：字典 + 列表項目"""
        content = """---
id: "0.1.0-W34-013"
where:
  layer: hooks
  files:
  - file1.py
  - file2.py
  depth: 2
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        # 驗證結構
        assert result['id'] == "0.1.0-W34-013"
        where = result['where']

        # 驗證字典項目
        assert where['layer'] == "hooks"
        assert where['depth'] == "2"

        # 驗證列表項目
        files = where['files']
        file_list = [f for f in files.split('\n') if f]
        assert len(file_list) == 2
        assert file_list[0] == "file1.py"
        assert file_list[1] == "file2.py"


if __name__ == "__main__":
    # 執行所有測試
    import traceback

    test_classes = [TestParseNestedLine, TestParseTicketFrontmatter]
    passed = 0
    failed = 0

    for test_class in test_classes:
        test_instance = test_class()
        methods = [m for m in dir(test_instance) if m.startswith('test_')]

        for method_name in methods:
            try:
                method = getattr(test_instance, method_name)
                method()
                print(f"✓ {test_class.__name__}.{method_name}")
                passed += 1
            except Exception as e:
                print(f"✗ {test_class.__name__}.{method_name}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")
    if failed > 0:
        sys.exit(1)
