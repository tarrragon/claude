"""
Test: commit_content_guards._check_presence_detection 只回報 pre->post 淨增量。

Source: 0.5.0-W1-482.3（純排版 diff 因 added_text 含重排行而被誤判為新增）
"""

import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB_DIR))

import commit_content_guards as ccg  # noqa: E402

DART_PATH = "lib/components/loading_state.dart"
EXISTING = (
    "Widget build() {\n"
    "  return Padding(\n"
    "    padding: EdgeInsets.only(left: isHeader ? 0 : LayoutSize.treeIndent.w),\n"
    "  );\n"
    "}\n"
)
REINDENTED = (
    "Widget build() {\n"
    "  return Center(\n"
    "    child: Padding(\n"
    "        padding: EdgeInsets.only(left: isHeader ? 0 : LayoutSize.treeIndent.w),\n"
    "    ),\n"
    "  );\n"
    "}\n"
)


def _run(pre: str, post: str):
    added = "\n".join(l for l in post.split("\n") if l not in pre.split("\n"))
    return ccg._check_presence_detection(
        ccg.StagedFile(DART_PATH, pre, post, added), None
    )


def test_format_only_reflow_yields_no_finding():
    assert _run(EXISTING, REINDENTED) == []


def test_multiline_merged_into_one_line_yields_no_finding():
    """482.2 實況：多行 EdgeInsets.only(...) 被 dart format 合併為一行。"""
    pre = (
        "Widget build() {\n"
        "  return Padding(\n"
        "    padding: EdgeInsets.only(\n"
        "      left: isHeader ? 0 : LayoutSize.treeIndent.w,\n"
        "    ),\n"
        "  );\n"
        "}\n"
    )
    assert _run(pre, EXISTING) == []


def test_new_magic_number_in_existing_file_still_denied():
    """正向對照（規則 E2）：同檔新增魔術數字仍須 deny。"""
    post = REINDENTED.replace(
        "  );\n}\n",
        "  );\n}\nWidget gap() => SizedBox(height: 17);\n",
    )
    findings = _run(EXISTING, post)
    assert findings and findings[0].severity == "deny"


def test_new_file_still_detected():
    findings = _run("", EXISTING)
    assert findings and findings[0].severity == "deny"
