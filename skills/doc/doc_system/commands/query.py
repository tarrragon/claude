"""query 子命令 — 依 ID 查詢文件內容。"""

import argparse

from doc_system.core.constants import REF_FIELDS
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


def execute(args: argparse.Namespace) -> None:
    """依 doc_id 查詢並顯示文件內容。"""
    doc_id = args.doc_id
    locator = FileLocator(FileLocator.get_project_root())

    file_path = locator.resolve_file(doc_id)
    if file_path is None:
        print(f"找不到文件: {doc_id}")
        return

    frontmatter = parse_frontmatter(file_path)
    if frontmatter is None:
        print(f"無法解析 frontmatter: {file_path}")
        return

    fm_id = frontmatter.get("id", doc_id)
    title = frontmatter.get("title", "(無標題)")
    fm_status = frontmatter.get("status", "(未知)")

    print(f"ID:     {fm_id}")
    print(f"標題:   {title}")
    print(f"狀態:   {fm_status}")

    # 輸出引用鏈
    for field in REF_FIELDS:
        value = frontmatter.get(field)
        if value:
            if isinstance(value, list):
                print(f"{field}: {', '.join(str(v) for v in value)}")
            else:
                print(f"{field}: {value}")
