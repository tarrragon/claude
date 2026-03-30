"""domain 子命令 — 依 domain 篩選文件。"""

import argparse
import os

from doc_system.core.constants import TITLE_MAX_DISPLAY_LEN
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


def _list_domains(spec_dir: str) -> list[str]:
    """列出 spec/ 目錄下所有子目錄名稱（即 domain 清單）。"""
    if not os.path.isdir(spec_dir):
        return []
    return sorted(
        name
        for name in os.listdir(spec_dir)
        if os.path.isdir(os.path.join(spec_dir, name))
    )


def _print_domain_specs(locator: FileLocator, domain_name: str) -> None:
    """顯示指定 domain 的 spec 清單和關聯 UC。"""
    specs = locator.list_specs(domain=domain_name)
    if not specs:
        print(f"Domain '{domain_name}' 沒有 spec 文件。")
        return

    print(f"\n=== Domain: {domain_name} ===")
    print(f"{'ID':<15} {'標題':<30} {'關聯 UC'}")
    print("-" * 65)

    for file_path in specs:
        frontmatter = parse_frontmatter(file_path)
        if frontmatter is None:
            basename = os.path.basename(file_path)
            print(f"{basename:<15} {'(無 frontmatter)':<30} -")
            continue

        fm_id = str(frontmatter.get("id", os.path.basename(file_path)))
        title = str(frontmatter.get("title", "(無標題)"))
        if len(title) > TITLE_MAX_DISPLAY_LEN:
            title = title[: TITLE_MAX_DISPLAY_LEN - 3] + "..."
        related_ucs = frontmatter.get("related_usecases", [])
        uc_str = ", ".join(str(uc) for uc in related_ucs) if related_ucs else "-"
        print(f"{fm_id:<15} {title:<30} {uc_str}")


def execute(args: argparse.Namespace) -> None:
    """無參數：列出所有 domain。有參數：顯示該 domain 的 spec 和關聯 UC。"""
    locator = FileLocator(FileLocator.get_project_root())
    domain_name = getattr(args, "domain_name", None)

    if domain_name is None:
        domains = _list_domains(locator.spec_dir)
        if not domains:
            print("沒有找到任何 domain。")
            return

        print("=== Domain 清單 ===")
        for d in domains:
            print(f"  - {d}")
    else:
        _print_domain_specs(locator, domain_name)
