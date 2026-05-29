"""
Lint 防護測試：偵測 status 過濾誤用 hard-code != STATUS_COMPLETED 的反模式。

來源：W17-097 ANA Step 3。

設計原則：
- 過濾「未終結 ticket」的場景應使用 TERMINAL_STATUSES（完整覆蓋 completed + closed）
- 賦值 / 業務規則 / 顯示分支 / from_status 語意等 success-only 場景才直接用 STATUS_COMPLETED
- 本測試確保 commands/ 和 lib/ 不再新增「過濾類」的 hard-code != STATUS_COMPLETED 用法

維護方式：
- 新增合法的 success-only 站點需加入 ALLOWED_FILTER_SITES
- 注意：本測試只擋 != STATUS_COMPLETED（過濾排除模式），不擋 == STATUS_COMPLETED
  （後者可能是 success-only 的賦值或精確判斷，誤判風險較高）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).parent.parent
SCAN_DIRS = [
    SKILL_ROOT / "ticket_system" / "commands",
    SKILL_ROOT / "ticket_system" / "lib",
]

# Pattern：偵測 != STATUS_COMPLETED 用法（包括變體）
NEGATION_PATTERN = re.compile(r"!=\s*STATUS_COMPLETED\b")
# Pattern：偵測 != "completed" hard-code（更嚴重的反模式）
HARDCODE_PATTERN = re.compile(r'!=\s*[\'"]completed[\'"]')

# Allowlist：合法 success-only 站點。
#
# W3-085 去耦合（脆弱設計修正）：
# 原 allowlist 以 "檔名:行號" 為 key（如 commands/resume.py:195），任何上游插入行都會
# 使行號漂移（W3-018.1 插入 target_id 反向查找後 195→201，導致 lint 測試誤報）。
# 改用 "檔名 + 行內容子串" 為錨點（content-anchored）：只要該語意行存在於檔案中即視為
# 合法站點，與其物理行號無關，徹底消除行號耦合。
#
# 結構：{ relative_file: [ (content_substring, 註記), ... ] }
# content_substring 為 strip 後行文字的穩定子串（足以唯一識別該站點）。
# 加入新項目時需附說明，並在 ANA / IMP 文件記錄。
ALLOWED_FILTER_SITES: dict[str, list[tuple[str, str]]] = {
    # resume.py: from_status != "completed" 是 handoff record 的快照狀態，
    # 表達「非任務鏈交接」語意，與 ticket terminal 狀態正交，不應改 TERMINAL_STATUSES
    "commands/resume.py": [
        ('record.from_status != "completed"', "from_status 語意 (handoff snapshot)"),
    ],
    # W17-163 L1-A: handoff_gc.py:79 站點已隨 _collect_stale_handoffs delegate
    # 至 handoff_utils.is_handoff_stale 而消除（ARCH-020 同構修復）
}


def _is_allowed_site(rel_file: str, line_text: str) -> bool:
    """判斷某 (檔案, 行內容) 是否為 allowlist 中的合法站點（content-anchored）。"""
    for substring, _note in ALLOWED_FILTER_SITES.get(rel_file, []):
        if substring in line_text:
            return True
    return False


def _file_relative_key(file_path: Path) -> str:
    """產生 allowlist 用的 relative key (commands/foo.py)。"""
    rel = file_path.relative_to(SKILL_ROOT / "ticket_system")
    return str(rel)


def _scan_python_files():
    """yield (file_path, line_no, line_text) for all matched lines.

    跳過：行首註解 (#)、docstring 內部（簡易偵測：在 triple-quote 區塊內）。
    """
    for scan_dir in SCAN_DIRS:
        for py_file in scan_dir.rglob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            text = py_file.read_text(encoding="utf-8")
            in_docstring = False
            for line_no, line in enumerate(text.splitlines(), start=1):
                # 偵測 triple-quote 進出（簡易：奇數次出現翻轉狀態）
                triple_count = line.count('"""') + line.count("'''")
                if triple_count % 2 == 1:
                    in_docstring = not in_docstring
                    continue  # 包含 triple-quote 的行本身略過
                if in_docstring:
                    continue
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if NEGATION_PATTERN.search(line) or HARDCODE_PATTERN.search(line):
                    yield (py_file, line_no, line.strip())


def test_no_bare_status_completed_negation_filter():
    """commands/ 與 lib/ 內禁止 hard-code != STATUS_COMPLETED 過濾，除非在 allowlist。

    為什麼：closed status 在 ticket lifecycle 也算終結，過濾應使用 TERMINAL_STATUSES。
    歷史 bug：W17-011.2 superseded 後 ticket track board 仍以 P0 顯示（W17-097）。
    """
    violations = []
    for file_path, line_no, line_text in _scan_python_files():
        rel_file = _file_relative_key(file_path)
        if _is_allowed_site(rel_file, line_text):
            continue
        violations.append(f"  {rel_file}:{line_no}: {line_text}")

    assert not violations, (
        "偵測到新增 hard-code != STATUS_COMPLETED / != \"completed\" 過濾用法。\n"
        "正確做法：使用 'not in TERMINAL_STATUSES'（涵蓋 completed + closed）\n"
        "若為 success-only 語意（如 from_status snapshot），請加入 ALLOWED_FILTER_SITES：\n\n"
        + "\n".join(violations)
    )


def test_allowlist_sites_still_exist():
    """allowlist 中的站點必須實際存在（防止 allowlist 漂移）。

    W3-085 去耦合後：改以「行內容子串實際存在於檔案某行」驗證，不再依賴精確行號，
    避免上游插入行造成 false negative（行號漂移）。
    """
    missing = []
    for rel_path, entries in ALLOWED_FILTER_SITES.items():
        file_path = SKILL_ROOT / "ticket_system" / rel_path
        if not file_path.exists():
            for substring, _note in entries:
                missing.append(f"{rel_path} [{substring}]: 檔案不存在")
            continue
        lines = file_path.read_text(encoding="utf-8").splitlines()
        for substring, _note in entries:
            # 站點必須仍是被 lint pattern 命中的過濾行（含 substring 且匹配 != completed）
            found = any(
                substring in line
                and (NEGATION_PATTERN.search(line) or HARDCODE_PATTERN.search(line))
                for line in lines
            )
            if not found:
                missing.append(
                    f"{rel_path} [{substring}]: 找不到符合 != STATUS_COMPLETED / != \"completed\" 的對應行"
                )

    assert not missing, (
        "ALLOWED_FILTER_SITES 已漂移，請更新行內容錨點或移除過時項目：\n"
        + "\n".join(missing)
    )
