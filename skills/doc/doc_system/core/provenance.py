"""由 SPEC／UC 的 source_proposal 反查 PROP 導出的文件（PROP→SPEC／UC 的權威來源）。"""

import sys

from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter

PROP_ID_PREFIX = "PROP"
SOURCE_FIELD = "source_proposal"
NON_AUTHORITATIVE_NOTE = "（非權威）"


def _normalize_to_list(value) -> list[str]:
    """source_proposal 基數為 many：純量視為單項清單，空值為空清單。"""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _find_derived_ids(paths: list[str], prop_id: str) -> list[str]:
    """回傳 source_proposal 含 prop_id 的文件 id。解析失敗的檔案略過並寫 stderr。"""
    found: list[str] = []
    for path in paths:
        frontmatter = parse_frontmatter(path)
        if frontmatter is None:
            sys.stderr.write(f"provenance: 無法解析 frontmatter，略過 {path}\n")
            continue
        sources = _normalize_to_list(frontmatter.get(SOURCE_FIELD))
        if prop_id in sources:
            found.append(str(frontmatter.get("id", path)))
    return sorted(found)


def is_proposal_id(doc_id: str) -> bool:
    """ID 是否為 PROP 前綴。"""
    return doc_id.upper().startswith(PROP_ID_PREFIX)


def find_derived_documents(
    locator: FileLocator, prop_id: str
) -> dict[str, list[str]]:
    """依 source_proposal 反查，回傳 {"specs": [...], "usecases": [...]}（排序穩定）。"""
    return {
        "specs": _find_derived_ids(locator.list_specs(), prop_id),
        "usecases": _find_derived_ids(locator.list_usecases(), prop_id),
    }


def print_derived_documents(locator: FileLocator, prop_id: str) -> None:
    """輸出反查結果並標明來源；spec_refs 非權威，與反查並列顯示。"""
    derived = find_derived_documents(locator, prop_id)
    print(f"  反查（來源: {SOURCE_FIELD}，權威）:")
    for label, key in (("SPEC", "specs"), ("UC", "usecases")):
        ids = derived[key]
        print(f"    {label}: {', '.join(ids) if ids else '(無)'}")
