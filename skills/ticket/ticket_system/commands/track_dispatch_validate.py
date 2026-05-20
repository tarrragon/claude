"""ticket track dispatch-validate 命令（0.18.0-W17-003）。

對 target ticket 的 Context Bundle 自動填料結果做合理性檢查，作為 C 方案
（context_bundle_extractor 自動抽取）的第二道防線。與 W10-017.2 的
`dispatch-check`（活躍派發狀態查詢）職責正交，獨立子命令不互相干擾。

合理性檢查規則（5 項，源自 W17-003 Problem Analysis）：

1. 欄位非空 — Context Bundle section 必須存在且 content 非全空白
2. 內容長度 — Context Bundle content >= 50 字元（避免空殼填料）
3. 檔案存在 — frontmatter `where.files` 列出的檔案在檔案系統存在
4. acceptance >= 3 項 — 4V 原則，少於 3 項視為規格不足
5. LLM 審查 — 未實作（不在 W17-003 範圍；未來如需加入須另起 ticket）

Exit code 語意：

- 0: 全部規則通過
- 1: 軟性警告（規則 2 / 3 / 4 部分違反，可派發但建議修正）
- 2: 硬性失敗（規則 1 違反、ticket 不存在、IO 錯誤）

**Exit code 與 dispatch-check 語意不共享**：本命令 exit 1 = 軟性警告 /
exit 2 = 硬性失敗或 IO 錯誤；既有 dispatch-check exit 1 = 有活躍派發 /
exit 2 = IO 錯誤。呼叫端必須以命令名稱判別語意，禁止以 exit code
跨命令解讀。

邊界：本 CLI **不** 修改 ticket、**不** 取代 hook / scheduler；僅輸出結構化
診斷供 PM / agent 派發前自檢使用（W17-209 ANA 方案 A）。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

from ticket_system.lib.dispatch_common import load_and_unpack
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.section_locator import SectionMatch, find_section


_CONTEXT_BUNDLE_SECTION = "Context Bundle"
_MIN_CONTENT_CHARS = 50
_MIN_ACCEPTANCE_ITEMS = 3


# ---------------------------------------------------------------------------
# 純函式：規則檢查（便於單元測試）
# ---------------------------------------------------------------------------


def check_section_present(
    body: str, *, match: SectionMatch | None = None
) -> Tuple[bool, str]:
    """規則 1：Context Bundle section 存在且 content 非全空白。

    `match` 可選；若呼叫端已 `find_section` 過則傳入避免重複解析。
    """
    if match is None:
        match = find_section(body or "", _CONTEXT_BUNDLE_SECTION)
    if not match.found:
        return False, "Context Bundle section 不存在（規則 1 違反）"
    if not match.content.strip():
        return False, "Context Bundle section 內容全空白（規則 1 違反）"
    return True, "Context Bundle section 存在且非空"


def check_content_length(
    body: str,
    *,
    min_chars: int = _MIN_CONTENT_CHARS,
    match: SectionMatch | None = None,
) -> Tuple[bool, str]:
    """規則 2：Context Bundle content 長度 >= min_chars。

    `match` 可選；若呼叫端已 `find_section` 過則傳入避免重複解析。
    """
    if match is None:
        match = find_section(body or "", _CONTEXT_BUNDLE_SECTION)
    if not match.found:
        return False, f"Context Bundle section 不存在，無法計算長度（< {min_chars}）"
    length = len(match.content.strip())
    if length < min_chars:
        return False, f"Context Bundle 內容長度 {length} < {min_chars}（規則 2 違反，疑似空殼填料）"
    return True, f"Context Bundle 內容長度 {length} >= {min_chars}"


def check_where_files_exist(
    where_files: List[str], *, project_root: Path
) -> Tuple[bool, str]:
    """規則 3：where.files 列出的檔案在檔案系統存在。

    空清單視為通過（DOC 類 ticket 可能未指定 where.files）。
    新建檔案路徑（尚未存在於 fs）回 False，由呼叫端決定是否警告。
    """
    if not where_files:
        return True, "where.files 為空（跳過檔案存在檢查）"
    missing: List[str] = []
    for rel in where_files:
        if not rel:
            continue
        path = project_root / rel
        if not path.exists():
            missing.append(rel)
    if missing:
        return False, f"where.files 有 {len(missing)} 個檔案不存在: {missing}"
    return True, f"where.files {len(where_files)} 個檔案皆存在"


def check_acceptance_count(
    acceptance: List, *, min_items: int = _MIN_ACCEPTANCE_ITEMS
) -> Tuple[bool, str]:
    """規則 4：acceptance 至少含 min_items 項。"""
    n = len(acceptance or [])
    if n < min_items:
        return False, f"acceptance 僅 {n} 項 < {min_items}（規則 4 違反，4V 原則不足）"
    return True, f"acceptance {n} 項 >= {min_items}"


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def _format_result(label: str, passed: bool, msg: str) -> str:
    tag = "[PASS]" if passed else "[FAIL]"
    return f"  {tag} {label}: {msg}"


def execute_dispatch_validate(args: argparse.Namespace, version: str) -> int:
    """執行 dispatch-validate 命令。

    Returns:
        0: 全部規則通過；1: 軟性警告；2: 硬性失敗 / IO 錯誤。
    """
    loaded = load_and_unpack(args, version)
    if loaded.error_exit_code is not None:
        return loaded.error_exit_code
    body = loaded.body
    where_files = loaded.where_files
    acceptance = loaded.acceptance
    ticket_id = args.ticket_id

    project_root = get_project_root()

    # 規則 1 + 規則 2 共用一次 find_section 結果（避免重複解析）
    cb_match = find_section(body, _CONTEXT_BUNDLE_SECTION)

    # 規則 1 硬性；規則 2/3/4 軟性
    r1_ok, r1_msg = check_section_present(body, match=cb_match)
    r2_ok, r2_msg = check_content_length(body, match=cb_match)
    r3_ok, r3_msg = check_where_files_exist(where_files or [], project_root=project_root)
    r4_ok, r4_msg = check_acceptance_count(acceptance)

    print(f"dispatch-validate {ticket_id}:")
    print(_format_result("規則 1 欄位非空", r1_ok, r1_msg))
    print(_format_result("規則 2 內容長度", r2_ok, r2_msg))
    print(_format_result("規則 3 檔案存在", r3_ok, r3_msg))
    print(_format_result("規則 4 acceptance 項數", r4_ok, r4_msg))

    # where.files 空時補 INFO 提示（避免靜默通過遮蔽 W17-002 抽取漏掉）
    if not (where_files or []):
        print(
            "  [INFO] where.files 為空：規則 3 自動通過。若本 ticket 應修改檔案，"
            "請確認 frontmatter where.files 已正確填寫（DOC 類 ticket 可忽略）"
        )

    # 規則 1 = 硬性失敗 → exit 2
    if not r1_ok:
        print("[FAIL] 規則 1 違反，視為硬性失敗")
        return 2

    # 規則 2/3/4 任一違反 → 軟性警告 exit 1
    soft_violations = [
        ("規則 2", r2_ok),
        ("規則 3", r3_ok),
        ("規則 4", r4_ok),
    ]
    failed = [name for name, ok in soft_violations if not ok]
    if failed:
        print(f"[WARN] 軟性警告：{', '.join(failed)} 違反，建議修正後派發")
        return 1

    print("[PASS] 全部規則通過")
    return 0


def register_dispatch_validate(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 dispatch-validate 子命令。"""
    p = subparsers.add_parser(
        "dispatch-validate",
        help="檢查 Context Bundle 自動填料合理性（0=pass/1=warn/2=fail）",
    )
    p.add_argument("ticket_id", help="目標 ticket ID")
    p.add_argument("--version", help="版本（可選；預設由 ticket_id 推斷）")
    return p
