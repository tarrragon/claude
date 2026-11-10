"""test-map 子命令 — 顯示需求-測試對應表。"""

import argparse
import os
import sys

import yaml

from doc_system.core.constants import (
    TEST_FILE_EXTENSIONS,
    TEST_SCAN_DIRS,
    TEST_SCAN_DIRS_CONFIG_KEY,
    TITLE_MAX_DISPLAY_LEN,
)
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter

TRACEABILITY_REL_PATH = os.path.join("docs", "traceability.yaml")


def _load_traceability_data(project_root: str) -> dict:
    """讀取 docs/traceability.yaml 全文；檔案缺席、不可解析或非 mapping 時回傳空 dict。"""
    path = os.path.join(project_root, TRACEABILITY_REL_PATH)
    if not os.path.isfile(path):
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        sys.stderr.write(f"[test-map] WARNING：無法讀取 {TRACEABILITY_REL_PATH}，視為未回填：{e}\n")
        return {}

    return data if isinstance(data, dict) else {}


def _resolve_scan_dirs(traceability_data: dict) -> list[str]:
    """取得掃描目錄：traceability.yaml 有設定則整份取代預設，否則用 TEST_SCAN_DIRS。"""
    configured = traceability_data.get(TEST_SCAN_DIRS_CONFIG_KEY)
    if configured is None:
        return list(TEST_SCAN_DIRS)

    valid = isinstance(configured, list) and configured and all(
        isinstance(d, str) and d.strip() for d in configured
    )
    if not valid:
        sys.stderr.write(
            f"[test-map] WARNING：{TRACEABILITY_REL_PATH} 的 {TEST_SCAN_DIRS_CONFIG_KEY} "
            f"須為非空的目錄字串清單，實際為 {configured!r}；改用預設 {TEST_SCAN_DIRS}\n"
        )
        return list(TEST_SCAN_DIRS)
    return [d.strip() for d in configured]


def _load_traceability_tests(project_root: str) -> dict[str, list[str]]:
    """讀取 docs/traceability.yaml 的 mappings 軸，回傳 {uc_id: tests}。

    只收錄 tests 非空的條目——tests 為空代表尚未回填，
    留給檔案掃描（_scan_test_files）補上。
    """
    return _extract_mapping_tests(_load_traceability_data(project_root))


def _extract_mapping_tests(data: dict) -> dict[str, list[str]]:
    """從 traceability.yaml 內容取 mappings 軸中 tests 非空的條目，回傳 {uc_id: tests}。"""
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


def _build_test_content_index(
    project_root: str, scan_dirs: list[str] | None = None
) -> dict[str, str]:
    """建立 {file_path: content_lower} 索引；scan_dirs 省略時掃描 TEST_SCAN_DIRS。"""
    index: dict[str, str] = {}

    for scan_dir in scan_dirs if scan_dirs is not None else TEST_SCAN_DIRS:
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


def _describe_scan_dirs(
    project_root: str, scan_dirs: list[str], content_index: dict[str, str]
) -> str:
    """列出每個掃描目錄的實況：不存在，或含幾個測試檔。"""
    parts: list[str] = []
    for scan_dir in scan_dirs:
        abs_dir = os.path.join(project_root, scan_dir)
        if not os.path.isdir(abs_dir):
            parts.append(f"{scan_dir}/（不存在）")
            continue
        prefix = abs_dir.rstrip(os.sep) + os.sep
        count = sum(1 for fp in content_index if fp.startswith(prefix))
        parts.append(f"{scan_dir}/（{count} 個測試檔）")
    return "、".join(parts)


def _warn_zero_scan_hits(
    project_root: str, scan_dirs: list[str], content_index: dict[str, str], scanned_uc_count: int
) -> None:
    """改走檔案掃描的 UC 全數零命中時寫 stderr，避免追溯矩陣看似全部未覆蓋而無訊號。"""
    sys.stderr.write(
        f"[test-map] WARNING：檔案掃描零命中（{scanned_uc_count} 個 UC 未在 "
        f"{TRACEABILITY_REL_PATH} 回填 tests，改以檔案掃描，皆未找到引用該 UC 的測試檔）。"
        f"掃過的目錄：{_describe_scan_dirs(project_root, scan_dirs, content_index)}。"
        f"測試放在其他目錄時，於 {TRACEABILITY_REL_PATH} 設定 {TEST_SCAN_DIRS_CONFIG_KEY}。\n"
    )


def execute(args: argparse.Namespace) -> None:
    """顯示 UC 與測試檔案對應。可選 uc_id 篩選特定 UC。

    資料來源優先序：docs/traceability.yaml 的 mappings.tests 為主要來源
    （已人工回填、可信度高）；該欄位為空時退回檔案掃描（掃描目錄見
    _resolve_scan_dirs，內容比對 UC ID 字串）作為輔助。改走掃描的 UC
    全數零命中時寫 stderr 警示並列出掃過的目錄。
    """
    locator = FileLocator(FileLocator.get_project_root())
    project_root = locator.project_root
    uc_id = getattr(args, "uc_id", None)

    uc_files = locator.list_usecases()
    if not uc_files:
        print("沒有找到任何 UC 文件。")
        return

    traceability_data = _load_traceability_data(project_root)
    traceability_tests = _extract_mapping_tests(traceability_data)
    scan_dirs = _resolve_scan_dirs(traceability_data)
    # 單次掃描建立索引，避免每個 UC 重複讀取測試檔案
    content_index = _build_test_content_index(project_root, scan_dirs)
    scanned_uc_count = 0
    scan_hit_count = 0

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
        if not traceability_tests.get(fm_id.upper()):
            scanned_uc_count += 1
            scan_hit_count += len(test_files)
        count = len(test_files)
        print(f"{fm_id:<12} {title:<30} {count}")

        if test_files:
            for tf in test_files:
                rel_path = os.path.relpath(tf, project_root) if os.path.isabs(tf) else tf
                print(f"{'':>12}   {rel_path}")

    if scanned_uc_count and not scan_hit_count:
        _warn_zero_scan_hits(project_root, scan_dirs, content_index, scanned_uc_count)
