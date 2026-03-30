"""list 子命令 — 列出文件清單。

模組名稱使用 list_cmd 避免與 Python 內建 list 衝突。
"""

import argparse
import os

from doc_system.core.constants import TITLE_MAX_DISPLAY_LEN
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


# doc_type 到 FileLocator 列表方法的對應
_TYPE_LISTERS = {
    "proposals": "list_proposals",
    "usecases": "list_usecases",
    "specs": "list_specs",
}


def _print_table(doc_type: str, files: list[str]) -> None:
    """輸出 ID | 標題 | 狀態 表格。"""
    print(f"\n=== {doc_type} ===")
    print(f"{'ID':<15} {'標題':<35} {'狀態':<10}")
    print("-" * 60)

    for file_path in files:
        frontmatter = parse_frontmatter(file_path)
        if frontmatter is None:
            basename = os.path.basename(file_path)
            print(f"{basename:<15} {'(無 frontmatter)':<35} {'-':<10}")
            continue

        fm_id = str(frontmatter.get("id", os.path.basename(file_path)))
        title = str(frontmatter.get("title", "(無標題)"))
        fm_status = str(frontmatter.get("status", "-"))
        # 截斷過長標題（使用共用常數）
        if len(title) > TITLE_MAX_DISPLAY_LEN + 5:
            title = title[: TITLE_MAX_DISPLAY_LEN + 2] + "..."
        print(f"{fm_id:<15} {title:<35} {fm_status:<10}")


def execute(args: argparse.Namespace) -> None:
    """列出指定類型的文件清單，省略 doc_type 則列出全部。"""
    locator = FileLocator(FileLocator.get_project_root())
    doc_type = getattr(args, "doc_type", None)

    if doc_type is not None:
        method_name = _TYPE_LISTERS[doc_type]
        files = getattr(locator, method_name)()
        _print_table(doc_type, files)
    else:
        for dtype, method_name in _TYPE_LISTERS.items():
            files = getattr(locator, method_name)()
            _print_table(dtype, files)
