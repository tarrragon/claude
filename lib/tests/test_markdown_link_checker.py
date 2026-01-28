#!/usr/bin/env python3
"""
markdown_link_checker 模組單元測試

測試 Markdown 連結檢查工具的各項功能。
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import sys

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from markdown_link_checker import (
    BrokenLink,
    LinkCheckResult,
    MarkdownLinkChecker,
    check_markdown_links,
    check_directory,
    format_check_report,
)


class TestBrokenLink(unittest.TestCase):
    """測試 BrokenLink 資料類別"""

    def test_basic_broken_link(self):
        """測試基本失效連結建立"""
        link = BrokenLink(
            file="docs/README.md",
            line=10,
            link_text="說明文件",
            link_target="./missing.md",
            suggestion="檢查檔案是否存在"
        )
        self.assertEqual(link.file, "docs/README.md")
        self.assertEqual(link.line, 10)
        self.assertEqual(link.link_text, "說明文件")
        self.assertEqual(link.link_target, "./missing.md")
        self.assertEqual(link.suggestion, "檢查檔案是否存在")


class TestLinkCheckResult(unittest.TestCase):
    """測試 LinkCheckResult 資料類別"""

    def test_result_with_no_broken_links(self):
        """測試無失效連結的結果"""
        result = LinkCheckResult(
            file_path="docs/README.md",
            total_links=5,
            broken_links=[]
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.total_links, 5)
        self.assertEqual(len(result.broken_links), 0)

    def test_result_with_broken_links(self):
        """測試有失效連結的結果"""
        result = LinkCheckResult(
            file_path="docs/README.md",
            total_links=5,
            broken_links=[
                BrokenLink(
                    file="docs/README.md",
                    line=10,
                    link_text="Test",
                    link_target="./missing.md",
                    suggestion=""
                )
            ]
        )
        self.assertFalse(result.is_valid)


class TestMarkdownLinkChecker(unittest.TestCase):
    """測試 MarkdownLinkChecker 核心功能"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.checker = MarkdownLinkChecker(str(self.temp_path))

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_parse_markdown_links(self):
        """測試解析 Markdown 連結"""
        content = """
# Title

This is a [link](./file.md) and another [link2](./other.md).

Here is an [external link](https://example.com).
"""
        links = self.checker.parse_markdown_links(content)

        # 應該找到 3 個連結
        self.assertEqual(len(links), 3)

        # 驗證第一個連結
        self.assertEqual(links[0]["text"], "link")
        self.assertEqual(links[0]["target"], "./file.md")

    def test_valid_internal_link(self):
        """測試有效的內部連結"""
        # 建立目標檔案
        (self.temp_path / "docs").mkdir()
        (self.temp_path / "docs" / "README.md").write_text("# README")
        (self.temp_path / "docs" / "other.md").write_text("# Other")

        # 建立含有連結的檔案
        md_content = """# Test
[Other Document](./other.md)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.broken_links), 0)

    def test_broken_internal_link(self):
        """測試失效的內部連結"""
        # 建立測試檔案（但不建立連結目標）
        (self.temp_path / "docs").mkdir()

        md_content = """# Test
[Missing Document](./missing.md)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.broken_links), 1)
        self.assertEqual(result.broken_links[0].link_target, "./missing.md")

    def test_anchor_link_ignored(self):
        """測試錨點連結被忽略（不檢查）"""
        (self.temp_path / "docs").mkdir()

        md_content = """# Test

[Jump to section](#section-name)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        # 錨點連結不應該被視為失效
        self.assertTrue(result.is_valid)

    def test_external_link_ignored(self):
        """測試外部連結被忽略（不檢查）"""
        (self.temp_path / "docs").mkdir()

        md_content = """# Test

[External](https://example.com)
[Another](http://example.org)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        # 外部連結不應該被檢查
        self.assertTrue(result.is_valid)
        self.assertEqual(result.total_links, 0)  # 外部連結不計入

    def test_relative_path_resolution(self):
        """測試相對路徑解析"""
        # 建立目錄結構
        (self.temp_path / "docs" / "guide").mkdir(parents=True)
        (self.temp_path / "docs" / "reference.md").write_text("# Ref")

        md_content = """# Guide
[Reference](../reference.md)
"""
        test_file = self.temp_path / "docs" / "guide" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        self.assertTrue(result.is_valid)

    def test_broken_relative_path(self):
        """測試失效的相對路徑"""
        (self.temp_path / "docs" / "guide").mkdir(parents=True)

        md_content = """# Guide
[Missing](../missing.md)
"""
        test_file = self.temp_path / "docs" / "guide" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.broken_links), 1)

    def test_link_with_anchor_suffix(self):
        """測試連結帶有錨點後綴"""
        # 建立目標檔案
        (self.temp_path / "docs").mkdir()
        (self.temp_path / "docs" / "reference.md").write_text("# Ref")

        md_content = """# Test
[Section](./reference.md#section-name)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        # 檔案存在，即使帶有錨點也應該通過
        self.assertTrue(result.is_valid)

    def test_broken_link_with_anchor_suffix(self):
        """測試失效連結帶有錨點後綴"""
        (self.temp_path / "docs").mkdir()

        md_content = """# Test
[Section](./missing.md#section-name)
"""
        test_file = self.temp_path / "docs" / "README.md"
        test_file.write_text(md_content)

        result = self.checker.check_file(str(test_file))

        self.assertFalse(result.is_valid)


class TestDirectoryCheck(unittest.TestCase):
    """測試目錄遞迴檢查"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_check_directory_recursive(self):
        """測試遞迴檢查目錄"""
        # 建立目錄結構
        (self.temp_path / "docs" / "sub").mkdir(parents=True)
        (self.temp_path / "docs" / "README.md").write_text("# Root\n[Link](./sub/page.md)")
        (self.temp_path / "docs" / "sub" / "page.md").write_text("# Sub Page")

        checker = MarkdownLinkChecker(str(self.temp_path))
        results = checker.check_directory(str(self.temp_path / "docs"))

        self.assertEqual(len(results), 2)  # 2 個 .md 檔案

    def test_check_directory_non_recursive(self):
        """測試非遞迴檢查目錄"""
        # 建立目錄結構
        (self.temp_path / "docs" / "sub").mkdir(parents=True)
        (self.temp_path / "docs" / "README.md").write_text("# Root")
        (self.temp_path / "docs" / "sub" / "page.md").write_text("# Sub Page")

        checker = MarkdownLinkChecker(str(self.temp_path))
        results = checker.check_directory(str(self.temp_path / "docs"), recursive=False)

        self.assertEqual(len(results), 1)  # 只有根目錄的 1 個檔案


class TestFormatReport(unittest.TestCase):
    """測試報告格式化"""

    def test_format_empty_report(self):
        """測試格式化空報告"""
        results = []
        report = format_check_report(results)
        self.assertIn("Markdown 連結檢查報告", report)
        self.assertIn("總計: 0", report)

    def test_format_report_with_results(self):
        """測試格式化包含結果的報告"""
        results = [
            LinkCheckResult(
                file_path="/path/to/file1.md",
                total_links=3,
                broken_links=[
                    BrokenLink(
                        file="/path/to/file1.md",
                        line=10,
                        link_text="Test",
                        link_target="./missing.md",
                        suggestion="檢查檔案是否存在"
                    )
                ]
            ),
            LinkCheckResult(
                file_path="/path/to/file2.md",
                total_links=2,
                broken_links=[]
            ),
        ]
        report = format_check_report(results)
        self.assertIn("總計: 2", report)
        self.assertIn("有效: 1", report)
        self.assertIn("有問題: 1", report)


class TestPublicAPI(unittest.TestCase):
    """測試公開 API"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_check_markdown_links_api(self):
        """測試 check_markdown_links 公開函式"""
        (self.temp_path / "test.md").write_text("# Test\n[Link](./other.md)")
        (self.temp_path / "other.md").write_text("# Other")

        result = check_markdown_links(
            str(self.temp_path / "test.md"),
            str(self.temp_path)
        )
        self.assertIsInstance(result, LinkCheckResult)
        self.assertTrue(result.is_valid)

    def test_check_directory_api(self):
        """測試 check_directory 公開函式"""
        (self.temp_path / "docs").mkdir()
        (self.temp_path / "docs" / "README.md").write_text("# Test")

        results = check_directory(
            str(self.temp_path / "docs"),
            str(self.temp_path)
        )
        self.assertIsInstance(results, dict)


class TestEdgeCases(unittest.TestCase):
    """測試邊界情況"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.checker = MarkdownLinkChecker(str(self.temp_path))

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_empty_file(self):
        """測試空檔案"""
        test_file = self.temp_path / "empty.md"
        test_file.write_text("")

        result = self.checker.check_file(str(test_file))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.total_links, 0)

    def test_file_without_links(self):
        """測試無連結的檔案"""
        test_file = self.temp_path / "no_links.md"
        test_file.write_text("# Title\n\nSome text without links.")

        result = self.checker.check_file(str(test_file))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.total_links, 0)

    def test_image_links_ignored(self):
        """測試圖片連結被忽略"""
        test_file = self.temp_path / "images.md"
        test_file.write_text("# Images\n\n![Image](./missing.png)")

        result = self.checker.check_file(str(test_file))
        # 圖片連結不檢查
        self.assertTrue(result.is_valid)

    def test_reference_style_links(self):
        """測試引用式連結"""
        (self.temp_path / "other.md").write_text("# Other")
        test_file = self.temp_path / "ref_links.md"
        test_file.write_text("""# Reference Links

[Link][ref1]

[ref1]: ./other.md
""")

        result = self.checker.check_file(str(test_file))
        # 引用式連結應該被正確解析
        self.assertTrue(result.is_valid)

    def test_nonexistent_file(self):
        """測試不存在的檔案"""
        result = self.checker.check_file(str(self.temp_path / "nonexistent.md"))
        self.assertFalse(result.is_valid)
        self.assertTrue(any("不存在" in link.suggestion for link in result.broken_links))


if __name__ == "__main__":
    unittest.main()
