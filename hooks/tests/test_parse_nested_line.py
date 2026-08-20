#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 parse_ticket_frontmatter 巢狀結構解析行為

歷史：本檔原含 `TestParseNestedLine`，直接測試手寫逐行 parser 的內部函式
`_parse_nested_line`（回傳 `_NestedLineResult` NamedTuple）。該函式已隨
parse_ticket_frontmatter 遷移至 `yaml.safe_load` 而退役，內部函式測試一併
移除；本檔原有的 `TestParseTicketFrontmatter`（測公開行為）保留並更新斷言
以反映 yaml.safe_load 的正確 YAML 型別語意（見各測試方法內註解）。
"""

import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import parse_ticket_frontmatter


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

    def test_field_value_containing_markdown_table_separator(self):
        """欄位值含 markdown 表格分隔列（連續三個以上減號）不應誤判為邊界"""
        content = """---
id: "0.1.0-W1-008"
note: "表格 |---------|---------|"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['id'] == "0.1.0-W1-008"
        assert result['note'] == "表格 |---------|---------|"

    def test_field_value_containing_diff_hunk_marker(self):
        """欄位值含 diff hunk 標記（連續三個減號）不應誤判為邊界"""
        content = """---
id: "0.1.0-W1-009"
note: "diff 標記 --- a/file.py"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['id'] == "0.1.0-W1-009"
        assert result['note'] == "diff 標記 --- a/file.py"

    def test_field_value_containing_em_dash_sequence(self):
        """欄位值含 em-dash 序列（連續三個減號）不應誤判為邊界"""
        content = """---
id: "0.1.0-W1-010"
note: "重點強調---特別注意---結尾"
---

# 執行日誌
"""
        result = parse_ticket_frontmatter(content)

        assert result['id'] == "0.1.0-W1-010"
        assert result['note'] == "重點強調---特別注意---結尾"

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
        """測試 2 格縮排的列表項目（真實 Ticket 格式）

        yaml.safe_load 語意：巢狀列表回傳真正的 list（非舊 parser 的
        `\\n` 併接字串——此為 W3-645 矩陣 `nested_list_multi` 案例的
        MISMATCH 修復對象，改用 yaml.safe_load 後自然還原為 list）。
        """
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

        # 驗證列表項目為真正的 list
        files = result['where']['files']
        assert isinstance(files, list)
        assert files == ["hook_utils/hook_ticket.py", "tests/test_parse.py"]

    def test_four_space_indented_list_items(self):
        """測試 4 格縮排的列表項目（深層嵌套，yaml.safe_load 回傳真正 list）"""
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

        # 驗證 4 格縮排的列表項目為真正的 list
        files = result['where']['files']
        assert isinstance(files, list)
        assert files == ["deep_item1.py", "deep_item2.py"]

    def test_mixed_nested_structure_with_lists(self):
        """測試混合嵌套結構：字典 + 列表項目

        `depth: 2`（無引號）由 yaml.safe_load 正確推斷為 int（W3-645 矩陣
        `bool_null_int` 案例的 MISMATCH 修復對象，舊 parser 一律轉字串）。
        """
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

        # 驗證字典項目（depth 為 int，非字串）
        assert where['layer'] == "hooks"
        assert where['depth'] == 2
        assert isinstance(where['depth'], int)

        # 驗證列表項目為真正的 list
        files = where['files']
        assert files == ["file1.py", "file2.py"]


if __name__ == "__main__":
    # 執行所有測試
    import traceback

    test_classes = [TestParseTicketFrontmatter]
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
