"""test-map 子命令 — 顯示需求-測試對應表。"""

import argparse
import os

import yaml

from doc_system.core.constants import (
    TEST_FILE_EXTENSIONS,
    TEST_SCAN_DIRS,
    TITLE_MAX_DISPLAY_LEN,
)
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter

TRACEABILITY_REL_PATH = os.path.join("docs", "traceability.yaml")


def _load_traceability_tests(project_root: str) -> dict[str, list[str]]:
    """讀取 docs/traceability.yaml 的 mappings 軸，回傳 {uc_id: tests}。

    只收錄 tests 非空的條目——tests 為空代表尚未回填，
    留給檔案掃描（_scan_test_files）補上。
    """
    path = os.path.join(project_root, TRACEABILITY_REL_PATH)
    if not os.path.isfile(path):
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[str, list[str]] = {}
    for entry in data.get("mappings") or []:
        if not isinstance(entry, dict):
            continue
        uc_id = str(entry.get("usecase", ""))
        tests = entry.get("tests") or []
        if uc_id and tests:
            result[uc_id.upper()] = list(tests)

    return result


def _scan_test_files(tests_dir: str, uc_id: str) -> list[str]:
    """掃描單一測試目錄，搜尋包含 UC ID 的測試檔案。"""
    matches: list[str] = []
    if not os.path.isdir(tests_dir):
        return matches

    uc_id_lower = uc_id.lower()
    # 同時搜尋帶連字號（UC-01）和不帶（UC01）的格式
    uc_id_no_dash = uc_id_lower.replace("-", "")

    for root, _dirs, files in os.walk(tests_dir):
        for filename in sorted(files):
            if not filename.endswith(TEST_FILE_EXTENSIONS):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read().lower()
            except OSError:
                continue
            if uc_id_lower in content or uc_id_no_dash in content:
                matches.append(file_path)

    return matches


def _build_test_content_index(project_root: str) -> dict[str, str]:
    """建立 {file_path: content_lower} 索引，掃描 TEST_SCAN_DIRS 內所有測試目錄。"""
    index: dict[str, str] = {}

    for scan_dir in TEST_SCAN_DIRS:
        tests_dir = os.path.join(project_root, scan_dir)
        if not os.path.isdir(tests_dir):
            continue
        for root, _dirs, files in os.walk(tests_dir):
            for filename in sorted(files):
                if not filename.endswith(TEST_FILE_EXTENSIONS):
                    continue
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        index[file_path] = f.read().lower()
                except OSError:
                    continue

    return index


def _search_in_index(
    index: dict[str, str], uc_id: str
) -> list[str]:
    """從已建立的索引中搜尋包含 UC ID 的測試檔案。"""
    uc_id_lower = uc_id.lower()
    uc_id_no_dash = uc_id_lower.replace("-", "")
    return [
        fp
        for fp, content in index.items()
        if uc_id_lower in content or uc_id_no_dash in content
    ]


def _resolve_tests_for_uc(
    fm_id: str, traceability_tests: dict[str, list[str]], content_index: dict[str, str]
) -> list[str]:
    """依優先順序解析 UC 的測試清單：traceability.yaml 有回填則優先採用，
    否則退回檔案掃描結果。"""
    yaml_tests = traceability_tests.get(fm_id.upper())
    if yaml_tests:
        return yaml_tests
    return _search_in_index(content_index, fm_id)


def execute(args: argparse.Namespace) -> None:
    """顯示 UC 與測試檔案對應。可選 uc_id 篩選特定 UC。

    資料來源優先序：docs/traceability.yaml 的 mappings.tests 為主要來源
    （已人工回填、可信度高）；該欄位為空時退回檔案掃描（test/、
    integration_test/ 內容比對 UC ID 字串）作為輔助。
    """
    locator = FileLocator(FileLocator.get_project_root())
    project_root = locator.project_root
    uc_id = getattr(args, "uc_id", None)

    uc_files = locator.list_usecases()
    if not uc_files:
        print("沒有找到任何 UC 文件。")
        return

    traceability_tests = _load_traceability_tests(project_root)
    # 單次掃描建立索引，避免每個 UC 重複讀取測試檔案
    content_index = _build_test_content_index(project_root)

    print("=== UC 測試對應表 ===")
    print(f"{'UC ID':<12} {'標題':<30} {'測試檔案數'}")
    print("-" * 55)

    for uc_file in uc_files:
        frontmatter = parse_frontmatter(uc_file)
        if frontmatter is None:
            continue

        fm_id = str(frontmatter.get("id", ""))
        title = str(frontmatter.get("title", "(無標題)"))
        if len(title) > TITLE_MAX_DISPLAY_LEN:
            title = title[: TITLE_MAX_DISPLAY_LEN - 3] + "..."

        # 若指定 uc_id，只顯示該 UC
        if uc_id is not None and fm_id.upper() != uc_id.upper():
            continue

        test_files = _resolve_tests_for_uc(fm_id, traceability_tests, content_index)
        count = len(test_files)
        print(f"{fm_id:<12} {title:<30} {count}")

        if test_files:
            for tf in test_files:
                rel_path = os.path.relpath(tf, project_root) if os.path.isabs(tf) else tf
                print(f"{'':>12}   {rel_path}")
