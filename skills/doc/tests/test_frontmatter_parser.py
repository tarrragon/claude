"""frontmatter_parser 單元測試。"""

from doc_system.core.frontmatter_parser import parse_frontmatter


class TestParseFrontmatter:
    """parse_frontmatter 的測試案例。"""

    def test_valid_frontmatter(self, tmp_path):
        """正常的 YAML frontmatter 應回傳 dict。"""
        md = tmp_path / "valid.md"
        md.write_text("---\ntitle: Hello\nstatus: draft\n---\n# Content\n")

        result = parse_frontmatter(str(md))

        assert result == {"title": "Hello", "status": "draft"}

    def test_no_frontmatter(self, tmp_path):
        """無 frontmatter 的檔案應回傳 None。"""
        md = tmp_path / "no_fm.md"
        md.write_text("# Just a heading\nSome content.\n")

        result = parse_frontmatter(str(md))

        assert result is None

    def test_empty_file(self, tmp_path):
        """空檔案應回傳 None。"""
        md = tmp_path / "empty.md"
        md.write_text("")

        result = parse_frontmatter(str(md))

        assert result is None

    def test_multiple_frontmatter_blocks_takes_first(self, tmp_path):
        """多個 frontmatter 區塊只取第一個。"""
        md = tmp_path / "multi.md"
        md.write_text(
            "---\ntitle: First\n---\nContent\n---\ntitle: Second\n---\n"
        )

        result = parse_frontmatter(str(md))

        assert result == {"title": "First"}

    def test_invalid_yaml_returns_none(self, tmp_path):
        """frontmatter 中的非法 YAML 應回傳 None。"""
        md = tmp_path / "bad_yaml.md"
        md.write_text("---\n: : : invalid\n---\n")

        result = parse_frontmatter(str(md))

        assert result is None

    def test_nonexistent_file_returns_none(self, tmp_path):
        """不存在的檔案應回傳 None。"""
        result = parse_frontmatter(str(tmp_path / "nonexistent.md"))

        assert result is None
