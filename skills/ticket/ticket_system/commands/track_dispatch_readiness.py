"""ticket track dispatch-readiness 命令（0.18.0-W17-053）。

派發前認知負擔閾值與綜合就緒度檢查。讀取 ticket frontmatter `where.files`
與 Context Bundle section 自動計算三項核心指標，輸出 pass/warn/fail 與
建議，取代 PM 手動對照 `.claude/rules/core/cognitive-load.md` 的閾值。

三項核心閾值（源自 `.claude/references/cognitive-load-execution-details.md`
「3b 派發前閾值」）：

1. 功能職責數 > 2 → 須拆分（軟警告，CLI 無法精確自動推導，沿用 ticket
   的 `how.task_type` / acceptance 數量為近似訊號，最終由 PM 判定）
2. 修改檔案數 > 5 → 須拆分（軟警告；> 10 視為強制拆分）
3. Context Bundle tokens > 3000 軟上限 / > 5000 強制拆分（以 wc -c
   近似估算，4 chars ≈ 1 token）

第四項一致性檢查（0.2.1-W3-249）：acceptance 產出需求與寫入集矛盾偵測。
掃描 acceptance 文字中指向測試產出的關鍵詞（測試/test/覆蓋/回歸/regression/
涵蓋），若命中但 `where.files` 內無任何測試型態路徑，輸出警告列出具體矛盾
條目。動機：PM 撰寫並行寫入集時只考慮哪些檔案會被改動，未回頭核對
acceptance 要求的產出需要動哪些檔案，使執行者陷入「守寫入集則 acceptance
落空、滿足 acceptance 則違反約束」的兩難（0.2.1-W3-234、0.2.1-W3-233 兩次
同型實例）。**語意判定有邊界**：本檢查只輸出警告（`warn`），不產生 `fail`，
不影響 exit code 語意（PM 保留覆核空間，未命中不代表無矛盾，關鍵詞比對亦可能
對非測試語境產生 false positive）。

Exit code 語意（與 dispatch-check / dispatch-validate 不共享）：

- 0 = 全通過
- 1 = 軟性警告（任一項超軟上限，或第四項一致性檢查命中矛盾，但未達強制拆分）
- 2 = 硬性失敗（任一項超強制拆分閾值 / IO 錯誤 / ticket 不存在）

**Exit code 與 dispatch-check / dispatch-validate 語意不共享**：呼叫端
必須以命令名稱判別語意，禁止以 exit code 跨命令解讀。

邊界：本 CLI **不** 修改 ticket、**不** 取代 hook / scheduler；僅輸出
結構化診斷供 PM / agent 派發前自檢使用（W17-209 ANA 方案 A 邊界）。
不觸碰既有 `dispatch-check`（W10-017.2）與 `dispatch-validate`（W17-003）。
"""

from __future__ import annotations

import argparse
import re
from typing import List, Tuple

from ticket_system.lib.dispatch_common import load_and_unpack
from ticket_system.lib.section_locator import find_section


_CONTEXT_BUNDLE_SECTION = "Context Bundle"

# 三項核心閾值（與 cognitive-load-execution-details.md 對齊）
# W17-213: 原 _RESPONSIBILITY_SOFT_MAX 重命名為 _RESPONSIBILITY_PASS_MAX
# 「PASS」更貼合 > N 即離開 pass 區的閘門語意（rules/cognitive-load.md 3b 派發前閾值）
_RESPONSIBILITY_PASS_MAX = 2  # > 2 軟警告
_RESPONSIBILITY_HARD_MAX = 4  # > 4 視為強制拆分（依據 7±2 取下限保守）
_FILES_SOFT_MAX = 5  # > 5 軟警告
_FILES_HARD_MAX = 10  # > 10 強制拆分
_CB_TOKENS_SOFT_MAX = 3000  # > 3000 軟上限
_CB_TOKENS_HARD_MAX = 5000  # > 5000 強制拆分
_CHARS_PER_TOKEN = 4  # 粗估換算（OpenAI cl100k 平均）

# 第四項一致性檢查（0.2.1-W3-249）：acceptance 測試類關鍵詞 + 測試路徑判定
# 啟發式限制：關鍵詞比對無法涵蓋所有表述方式，未命中不代表無矛盾；「回歸」等
# 泛用詞亦可能在非測試語境誤判（如「回歸原設計」）——故本檢查上限為 warn。
_TEST_KEYWORDS = ("測試", "test", "覆蓋", "回歸", "regression", "涵蓋")
_TEST_PATH_PATTERN = re.compile(r"(^|[/\\])tests?([/\\]|_|$)|_test\.", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 純函式：閾值檢查（便於單元測試）
# ---------------------------------------------------------------------------


def check_responsibility_count(
    acceptance: List,
    *,
    soft_max: int = _RESPONSIBILITY_PASS_MAX,
    hard_max: int = _RESPONSIBILITY_HARD_MAX,
) -> Tuple[str, int, str]:
    """閾值 1：功能職責數估算。

    CLI 無法精確推導職責數，沿用 acceptance 條目數作為近似訊號（每條
    acceptance 對應一個可驗證目標，間接反映職責複雜度）。

    Returns:
        (status, count, msg) — status ∈ {"pass", "warn", "fail"}
    """
    n = len(acceptance or [])
    if n > hard_max:
        return "fail", n, f"acceptance 條目 {n} > {hard_max}（強制拆分；功能職責複雜度過高）"
    if n > soft_max:
        return "warn", n, f"acceptance 條目 {n} > {soft_max}（軟警告；建議拆分為多個 ticket）"
    return "pass", n, f"acceptance 條目 {n} ≤ {soft_max}"


def check_file_count(
    where_files: List[str],
    *,
    soft_max: int = _FILES_SOFT_MAX,
    hard_max: int = _FILES_HARD_MAX,
) -> Tuple[str, int, str]:
    """閾值 2：修改檔案數。

    Returns:
        (status, count, msg)
    """
    n = len([f for f in (where_files or []) if f])
    if n > hard_max:
        return "fail", n, f"where.files {n} > {hard_max}（強制拆分；跨檔一致性維護成本過高）"
    if n > soft_max:
        return "warn", n, f"where.files {n} > {soft_max}（軟警告；建議依 domain 邊界拆分）"
    return "pass", n, f"where.files {n} ≤ {soft_max}"


def check_context_bundle_tokens(
    body: str,
    *,
    soft_max: int = _CB_TOKENS_SOFT_MAX,
    hard_max: int = _CB_TOKENS_HARD_MAX,
    chars_per_token: int = _CHARS_PER_TOKEN,
) -> Tuple[str, int, str]:
    """閾值 3：Context Bundle token 數（以字元數 / 4 近似）。

    Returns:
        (status, est_tokens, msg)
    """
    match = find_section(body or "", _CONTEXT_BUNDLE_SECTION)
    if not match.found:
        return "pass", 0, "Context Bundle section 不存在（視為 0 tokens）"
    chars = len(match.content.strip())
    est_tokens = chars // chars_per_token
    if est_tokens > hard_max:
        return (
            "fail",
            est_tokens,
            f"Context Bundle ~{est_tokens} tokens > {hard_max}（強制拆分；建議限定 2-3 個 source ticket）",
        )
    if est_tokens > soft_max:
        return (
            "warn",
            est_tokens,
            f"Context Bundle ~{est_tokens} tokens > {soft_max}（軟上限；審視 PCB 是否含無關歷史段落）",
        )
    return "pass", est_tokens, f"Context Bundle ~{est_tokens} tokens ≤ {soft_max}"


def _acceptance_mentions_test(item: str) -> bool:
    """判定單條 acceptance 文字是否含測試類關鍵詞（大小寫不敏感）。"""
    lowered = (item or "").lower()
    return any(kw.lower() in lowered for kw in _TEST_KEYWORDS)


def _is_test_path(path: str) -> bool:
    """判定路徑是否為測試型態路徑（含 tests?/ 目錄段或 test_ / _test. 檔名慣例）。"""
    return bool(_TEST_PATH_PATTERN.search(path or ""))


def check_acceptance_writeset_consistency(
    acceptance: List,
    where_files: List[str],
) -> Tuple[str, List[str], str]:
    """檢查 4：acceptance 產出需求與寫入集（where.files）矛盾偵測（0.2.1-W3-249）。

    掃描 acceptance 文字中指向測試產出的關鍵詞，若命中且 where.files 內無
    任何測試型態路徑，回傳 warn 並列出具體矛盾條目。不產生 fail——語意判定
    有邊界，PM 保留覆核空間（未命中不代表無矛盾，亦可能對非測試語境的關鍵詞
    產生 false positive）。

    Returns:
        (status, matched_items, msg) — status ∈ {"pass", "warn"}（不含 fail）
    """
    matched_items = [
        item for item in (acceptance or []) if _acceptance_mentions_test(item)
    ]
    if not matched_items:
        return "pass", [], "acceptance 無測試類關鍵詞命中"

    if any(_is_test_path(f) for f in (where_files or []) if f):
        return (
            "pass",
            [],
            f"acceptance 含 {len(matched_items)} 項測試類關鍵詞，where.files 已含測試路徑",
        )

    msg = (
        f"acceptance 含 {len(matched_items)} 項測試類關鍵詞但 where.files 無測試路徑，"
        "可能使執行者陷入寫入集與 acceptance 矛盾（啟發式限制：未命中不代表無矛盾，"
        "亦可能對非測試語境的關鍵詞產生 false positive，需 PM 覆核）"
    )
    return "warn", matched_items, msg


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


_STATUS_TAG = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}


def _format_result(label: str, status: str, msg: str) -> str:
    return f"  {_STATUS_TAG.get(status, '[?]')} {label}: {msg}"


def execute_dispatch_readiness(args: argparse.Namespace, version: str) -> int:
    """執行 dispatch-readiness 命令。

    Returns:
        0: 全通過；1: 軟性警告；2: 硬性失敗 / IO 錯誤。
    """
    loaded = load_and_unpack(args, version)
    if loaded.error_exit_code is not None:
        return loaded.error_exit_code
    body = loaded.body
    where_files = loaded.where_files
    acceptance = loaded.acceptance
    ticket_id = args.ticket_id

    r1_status, _, r1_msg = check_responsibility_count(acceptance)
    r2_status, _, r2_msg = check_file_count(where_files or [])
    r3_status, _, r3_msg = check_context_bundle_tokens(body)
    r4_status, r4_items, r4_msg = check_acceptance_writeset_consistency(
        acceptance, where_files or []
    )

    print(f"dispatch-readiness {ticket_id}:")
    print(_format_result("閾值 1 功能職責數（acceptance 近似）", r1_status, r1_msg))
    print(_format_result("閾值 2 修改檔案數（where.files）", r2_status, r2_msg))
    print(_format_result("閾值 3 Context Bundle tokens", r3_status, r3_msg))
    print(_format_result("檢查 4 acceptance 與寫入集一致性（啟發式）", r4_status, r4_msg))
    for item in r4_items:
        print(f"      - {item}")

    statuses = [r1_status, r2_status, r3_status, r4_status]
    if "fail" in statuses:
        print("[FAIL] 至少一項超強制拆分閾值，建議拆 ticket 後重新派發")
        return 2
    if "warn" in statuses:
        print("[WARN] 軟性警告：建議審視拆分必要性")
        return 1
    print("[PASS] 三項閾值 + 一致性檢查全數通過")
    return 0


def register_dispatch_readiness(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 dispatch-readiness 子命令。"""
    p = subparsers.add_parser(
        "dispatch-readiness",
        help="派發前認知負擔閾值與綜合就緒度檢查（0=pass/1=warn/2=fail）",
    )
    p.add_argument("ticket_id", help="目標 ticket ID")
    p.add_argument("--version", help="版本（可選；預設由 ticket_id 推斷）")
    return p
