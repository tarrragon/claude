"""section_locator helper 測試（W17-117.1）。

涵蓋四處呼叫端的容錯需求：
- 標準格式 / 末尾空白 / 雙空白 / 前綴誤匹配
- SECTION_NOT_FOUND 含 all_headers 列舉
- auditor 雙層級 (##/###)
"""

from ticket_system.lib.section_locator import SectionMatch, find_section


def test_standard_format():
    """標準 `## Section Name` 格式應正確定位。"""
    body = "## Solution\ncontent here\n## Test Results\nother\n"
    result = find_section(body, "Solution")
    assert result.found
    assert result.text.startswith("## Solution")
    assert "content here" in result.content
    assert "other" not in result.content


def test_trailing_whitespace():
    """`## Section Name   ` 末尾空白應容錯（W17-008.9）。"""
    body = "## Solution   \ncontent\n## Next\n"
    result = find_section(body, "Solution")
    assert result.found
    assert "content" in result.content


def test_double_whitespace():
    """`##  Section Name` header 後雙空白應容錯（W17-008.9）。"""
    body = "##  Solution\ncontent\n## Next\n"
    result = find_section(body, "Solution")
    assert result.found
    assert "content" in result.content


def test_prefix_mismatch_protection():
    """`## SolutionPlus` 不應匹配 `Solution`（re.escape + \\s*$ 防護）。"""
    body = "## SolutionPlus\nfake content\n## End\n"
    result = find_section(body, "Solution")
    assert not result.found
    # all_headers 應仍列出實際存在的標題
    assert any("SolutionPlus" in h for h in result.all_headers)


def test_section_not_found_lists_existing_headers():
    """未找到 section 時 all_headers 應列舉所有 ## 標題。"""
    body = "## Problem Analysis\na\n## Solution\nb\n## Test Results\nc\n"
    result = find_section(body, "Nonexistent")
    assert not result.found
    assert len(result.all_headers) == 3
    assert any("Problem Analysis" in h for h in result.all_headers)
    assert any("Solution" in h for h in result.all_headers)
    assert any("Test Results" in h for h in result.all_headers)


def test_empty_body():
    """空 body 應返回 found=False、空 all_headers。"""
    result = find_section("", "Solution")
    assert not result.found
    assert result.all_headers == []


def test_h3_level_for_auditor():
    """levels=(2, 3) 時應接受 `### Section`（acceptance_auditor 雙層級需求）。"""
    body = "## Parent\n### Solution\ncontent\n## Next\n"
    result = find_section(body, "Solution", levels=(2, 3))
    assert result.found
    assert "content" in result.content


def test_h2_priority_over_h3():
    """levels=(2, 3) 同時存在 ## 與 ### 時，## 優先（依 levels 順序）。"""
    body = "## Solution\nh2 content\n## Other\n### Solution\nh3 content\n"
    result = find_section(body, "Solution", levels=(2, 3))
    assert result.found
    assert "h2 content" in result.content
    # 不應誤抓 h3 那段
    assert "h3 content" not in result.content


def test_section_at_eof():
    """section 在文件末尾（無下個 ##）應正確擷取到 len(body)。"""
    body = "## Solution\nfinal content"
    result = find_section(body, "Solution")
    assert result.found
    assert result.end == len(body)
    assert "final content" in result.content


def test_h3_only_with_default_levels_not_found():
    """預設 levels=(2,) 時 `### Solution` 不應被找到。"""
    body = "## Parent\n### Solution\ncontent\n"
    result = find_section(body, "Solution")
    assert not result.found
