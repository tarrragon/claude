"""nav 子命令 — 導覽文件關聯。"""

import argparse

from doc_system.core.constants import REF_FIELDS
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


def _extract_refs(frontmatter: dict) -> dict[str, list[str]]:
    """從 frontmatter 提取所有引用欄位，回傳 {欄位名: [引用值]}。"""
    refs: dict[str, list[str]] = {}

    for field in REF_FIELDS:
        value = frontmatter.get(field)
        if value is None:
            continue

        if isinstance(value, dict):
            # outputs 是巢狀結構，展開子欄位
            for sub_key, sub_value in value.items():
                if sub_value:
                    if isinstance(sub_value, list):
                        refs[sub_key] = [str(v) for v in sub_value]
                    else:
                        refs[sub_key] = [str(sub_value)]
        elif isinstance(value, list):
            if value:
                refs[field] = [str(v) for v in value]
        else:
            refs[field] = [str(value)]

    return refs


def execute(args: argparse.Namespace) -> None:
    """從任一文件 ID 導航到相關文件，輸出引用地圖。"""
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

    print(f"=== 引用地圖: {fm_id} — {title} ===")
    print()

    refs = _extract_refs(frontmatter)
    if not refs:
        print("(無引用關聯)")
        return

    for field_name, ref_list in refs.items():
        print(f"  {field_name}:")
        for ref in ref_list:
            print(f"    - {ref}")
