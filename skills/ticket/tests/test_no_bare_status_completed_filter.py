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

# Allowlist：合法 success-only 站點（檔名:行號 + 註記）
# 加入新項目時需附說明，並在 ANA / IMP 文件記錄
ALLOWED_FILTER_SITES: dict[str, str] = {
    # resume.py: from_status != "completed" 是 handoff record 的快照狀態，
    # 表達「非任務鏈交接」語意，與 ticket terminal 狀態正交，不應改 TERMINAL_STATUSES
    "commands/resume.py:195": "from_status 語意 (handoff snapshot)",
    # W17-163 L1-A: handoff_gc.py:79 站點已隨 _collect_stale_handoffs delegate
    # 至 handoff_utils.is_handoff_stale 而消除（ARCH-020 同構修復）
}


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
        rel_key = f"{_file_relative_key(file_path)}:{line_no}"
        if rel_key in ALLOWED_FILTER_SITES:
            continue
        violations.append(f"  {rel_key}: {line_text}")

    assert not violations, (
        "偵測到新增 hard-code != STATUS_COMPLETED / != \"completed\" 過濾用法。\n"
        "正確做法：使用 'not in TERMINAL_STATUSES'（涵蓋 completed + closed）\n"
        "若為 success-only 語意（如 from_status snapshot），請加入 ALLOWED_FILTER_SITES：\n\n"
        + "\n".join(violations)
    )


def test_allowlist_sites_still_exist():
    """allowlist 中的站點必須實際存在（防止 allowlist 漂移）。"""
    missing = []
    for key in ALLOWED_FILTER_SITES:
        rel_path, line_no_str = key.rsplit(":", 1)
        line_no = int(line_no_str)
        file_path = SKILL_ROOT / "ticket_system" / rel_path
        if not file_path.exists():
            missing.append(f"{key}: 檔案不存在")
            continue
        lines = file_path.read_text(encoding="utf-8").splitlines()
        if line_no > len(lines):
            missing.append(f"{key}: 行號超出檔案長度 ({len(lines)} 行)")
            continue
        line = lines[line_no - 1]
        if not (NEGATION_PATTERN.search(line) or HARDCODE_PATTERN.search(line)):
            missing.append(f"{key}: 該行已不含 != STATUS_COMPLETED / != \"completed\"")

    assert not missing, (
        "ALLOWED_FILTER_SITES 已漂移，請更新行號或移除過時項目：\n"
        + "\n".join(missing)
    )
