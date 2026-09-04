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

第四項一致性檢查：acceptance 產出需求與寫入集矛盾偵測，涵蓋兩種訊號來源：

1. 測試類關鍵詞：掃描 acceptance 文字中指向測試產出的關鍵詞（測試/test/
   覆蓋/回歸/regression/涵蓋），若命中但 `where.files` 內無任何測試型態
   路徑，列出具體矛盾條目。動機：PM 撰寫並行寫入集時只考慮哪些檔案會被
   改動，未回頭核對 acceptance 要求的產出需要動哪些檔案，使執行者陷入
   「守寫入集則 acceptance 落空、滿足 acceptance 則違反約束」的兩難。
2. glob 形式路徑提及：acceptance 提及含萬用字元 `*` 的路徑樣式（如
   `app_localizations*.dart`），但 `where.files` 內無檔案可被該樣式
   fnmatch 涵蓋。動機同上，差別在產出以萬用字元描述一組檔案而非單一具名
   檔案，第六項檢查的字面路徑抽取無法涵蓋此形態（萬用字元不落在已知
   副檔名片段的字元類內）。

**與第六項檢查的分工（避免同一 acceptance 條目被兩項檢查以不同 severity
判定）**：字面（不含 `*`）路徑提及一律歸第六項檢查（fail，強制，僅比對
已知副檔名的字面路徑）；本檢查刻意只處理含 `*` 的 token，兩者依「是否含
萬用字元」互斥切分，不重疊。以文件 ID 指稱產物（如 SPEC-002 / PROP-003）
不在本檢查與第六項檢查的範圍內——整條驗收無任何路徑樣態，純文字抽取零
鑑別力，需要獨立的文件 ID 到路徑註冊表，屬不同性質的工程，另案評估。

**語意判定有邊界**：本檢查只輸出警告（`warn`），不產生 `fail`，不影響
exit code 語意（PM 保留覆核空間，未命中不代表無矛盾，關鍵詞比對亦可能
對非測試語境產生 false positive）。

第六項檢查：acceptance 文字提及的具體檔案路徑須落在 `where.files` 內，
否則 FAIL（強制，唯一產生 fail 的啟發式檢查）。動機：acceptance 若明文
點名某檔案（如「核對 SKILL.md 並直接修文件」）但 `where.files` 未列該
檔案，代理人依 acceptance 動了該檔後，commit 時寫入集與宣告範圍不一致
會被 bare-commit-guard 攔下；第四項檢查僅比對測試類關鍵詞，無法涵蓋此
類具名路徑矛盾。本檢查在派發前即從 acceptance 抽取路徑樣式 token（具備
已知副檔名的片段，如 `.py`/`.md`/`.yaml`），與 `where.files` 做前綴或
檔名比對，未涵蓋者直接 FAIL 並提示「把該路徑加進 where.files 或改寫
acceptance」，讓宣告不一致在派發前就被擋下而非留到 commit 時才顯現。

Exit code 語意（與 dispatch-check / dispatch-validate 不共享）：

- 0 = 全通過
- 1 = 軟性警告（任一項超軟上限，或第四項一致性檢查命中矛盾，但未達強制拆分）
- 2 = 硬性失敗（任一項超強制拆分閾值 / 第六項路徑涵蓋性未過 / IO 錯誤 / ticket 不存在）

**Exit code 與 dispatch-check / dispatch-validate 語意不共享**：呼叫端
必須以命令名稱判別語意，禁止以 exit code 跨命令解讀。

邊界：本 CLI **不** 修改 ticket、**不** 取代 hook / scheduler；僅輸出
結構化診斷供 PM / agent 派發前自檢使用（W17-209 ANA 方案 A 邊界）。
不觸碰既有 `dispatch-check`（W10-017.2）與 `dispatch-validate`（W17-003）。
"""

from __future__ import annotations

import argparse
import fnmatch
import re
from typing import List, Tuple

from ticket_system.lib.dispatch_common import load_and_unpack
from ticket_system.lib.field_validators import missing_where_paths
from ticket_system.lib.paths import get_project_root
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

# 第五項檢查（where.files 路徑存在性）：acceptance 含「建立/新增/新檔」類
# 關鍵詞時，視為新檔案宣告的合理場景，不對不存在路徑發 WARN——啟發式限制：
# 未命中不代表路徑無誤，仍需 PM 覆核（與檢查 4 共用邊界聲明）。
_CREATION_KEYWORDS = ("建立", "新增", "新檔", "create", "add")

# 第六項檢查（acceptance 提及路徑須落在 where.files 內）：僅比對具備已知
# 副檔名的片段，避免「3a/3b」等 Phase 標號或版本號/ticket ID 誤判為路徑。
# lookbehind/lookahead 限定 ASCII 字元（非 Unicode \w），使中英夾雜文字中
# 緊貼中文字元（無空格分隔）的檔名仍可正確匹配邊界。
_MENTIONED_PATH_EXTENSIONS = (
    "py",
    "md",
    "yaml",
    "yml",
    "json",
    "dart",
    "txt",
    "sh",
    "toml",
)
_MENTIONED_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])([A-Za-z0-9_\-./]+\.(?:"
    + "|".join(_MENTIONED_PATH_EXTENSIONS)
    + r"))(?![A-Za-z0-9_])"
)

# 第四項一致性檢查的 glob 子路徑：字元類額外納入 `*`，讓
# `app_localizations*.dart` 這類萬用字元寫法可被抽取（`_MENTIONED_PATH_PATTERN`
# 的字元類不含 `*`，遇萬用字元會斷開匹配，抽不出完整 token）。抽取後仍須
# 以 `"*" in token` 篩選，只保留真正含萬用字元的 token——不含 `*` 的字面
# token 一律歸第六項檢查，兩者依此互斥切分（見模組 docstring「與第六項
# 檢查的分工」）。
_GLOB_MENTIONED_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])([A-Za-z0-9_\-./*]+\.(?:"
    + "|".join(_MENTIONED_PATH_EXTENSIONS)
    + r"))(?![A-Za-z0-9_])"
)


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


def _extract_glob_mentions(item: str) -> List[str]:
    """從單條 acceptance 文字抽取含萬用字元 `*` 的路徑樣式 token。

    不含 `*` 的字面 token 一律過濾掉（歸第六項檢查專屬範圍），見模組
    `_GLOB_MENTIONED_PATH_PATTERN` 註解。
    """
    return [
        m.group(1)
        for m in _GLOB_MENTIONED_PATH_PATTERN.finditer(str(item or ""))
        if "*" in m.group(1)
    ]


def _glob_mention_covered(token: str, where_files: List[str]) -> bool:
    """判定含萬用字元的路徑 token 是否被 where.files 涵蓋（fnmatch）。

    比對兩種粒度：完整 token 對完整路徑（token 含目錄結構時），與
    basename 對 basename（token 或 where.files 任一側只寫裸檔名時）——
    兩側正規化至同一粒度才不會把「acceptance 寫裸檔名、where.files 寫
    完整路徑」誤判為未涵蓋。比對前剝除 `::read` / `::write` 逐檔意圖標記，
    與檢查 6 的 `_path_covered_by_where_files` 一致。
    """
    token_basename = token.rsplit("/", 1)[-1]
    for raw in where_files or []:
        path = str(raw or "").split("::", 1)[0]
        if not path:
            continue
        if fnmatch.fnmatch(path, token):
            return True
        if fnmatch.fnmatch(path.rsplit("/", 1)[-1], token_basename):
            return True
    return False


def check_acceptance_writeset_consistency(
    acceptance: List,
    where_files: List[str],
) -> Tuple[str, List[str], str]:
    """檢查 4：acceptance 產出需求與寫入集（where.files）矛盾偵測。

    涵蓋兩種訊號來源，見模組 docstring「第四項一致性檢查」：測試類關鍵詞
    （原始邏輯）與 glob 形式路徑提及（擴充邏輯，與第六項檢查依「是否含
    萬用字元」互斥切分）。不產生 fail——語意判定有邊界，PM 保留覆核空間
    （未命中不代表無矛盾，亦可能對非測試語境的關鍵詞產生 false positive；
    以文件 ID 指稱產物不在本檢查範圍）。

    Returns:
        (status, matched_items, msg) — status ∈ {"pass", "warn"}（不含 fail）
    """
    keyword_hits = [
        item for item in (acceptance or []) if _acceptance_mentions_test(item)
    ]
    keyword_has_test_path = any(_is_test_path(f) for f in (where_files or []) if f)
    keyword_matched = [] if (not keyword_hits or keyword_has_test_path) else keyword_hits

    glob_matched = [
        item
        for item in (acceptance or [])
        if any(
            not _glob_mention_covered(token, where_files or [])
            for token in _extract_glob_mentions(item)
        )
    ]

    matched_items = list(keyword_matched)
    for item in glob_matched:
        if item not in matched_items:
            matched_items.append(item)

    if not matched_items:
        return "pass", [], "acceptance 無測試類關鍵詞命中，亦無未涵蓋的 glob 路徑提及"

    detail_parts = []
    if keyword_matched:
        detail_parts.append(
            f"{len(keyword_matched)} 項測試類關鍵詞但 where.files 無測試路徑"
        )
    if glob_matched:
        detail_parts.append(f"{len(glob_matched)} 項 glob 路徑提及未被 where.files 涵蓋")

    msg = (
        "acceptance 含 "
        + "、".join(detail_parts)
        + "，可能使執行者陷入寫入集與 acceptance 矛盾（啟發式限制：未命中不代表無矛盾，"
        "亦可能對非測試語境的關鍵詞產生 false positive；以文件 ID 指稱產物（如 SPEC-002 "
        "/ PROP-003）不在本檢查範圍，需 PM 覆核）"
    )
    return "warn", matched_items, msg


def _acceptance_mentions_creation(acceptance: List) -> bool:
    """判定 acceptance 是否含新建語意關鍵詞（大小寫不敏感）。"""
    for item in acceptance or []:
        lowered = str(item or "").lower()
        if any(kw.lower() in lowered for kw in _CREATION_KEYWORDS):
            return True
    return False


def check_where_paths_existence(
    where_files: List[str],
    acceptance: List,
    project_root,
) -> Tuple[str, List[str], str]:
    """檢查 5：where.files 路徑存在性。

    where.files 含不存在路徑，且 acceptance 無新建語意（建立/新增/新檔類
    關鍵詞）時回傳 warn，提示 PM 覆核是否路徑錯置或漏加新建關鍵詞。
    acceptance 含新建語意時視為合理的新檔案宣告，不警告——不阻擋，因
    dispatch-readiness 全套件皆為軟性檢查（見模組 docstring exit code 語意）。

    Returns:
        (status, missing_paths, msg) — status ∈ {"pass", "warn"}（不含 fail）
    """
    missing = missing_where_paths(project_root, where_files or [])
    if not missing:
        return "pass", [], "where.files 路徑全數存在"

    if _acceptance_mentions_creation(acceptance):
        return (
            "pass",
            [],
            f"where.files 含 {len(missing)} 項不存在路徑，acceptance 含新建語意，視為合理",
        )

    msg = (
        f"where.files 含 {len(missing)} 項不存在路徑，acceptance 未見新建語意"
        "（建立/新增/新檔），可能是測試檔待建或路徑寫錯，請 PM 覆核（啟發式限制："
        "未命中新建關鍵詞不代表路徑必誤）"
    )
    return "warn", missing, msg


def _extract_mentioned_paths(acceptance: List) -> List[str]:
    """從 acceptance 文字抽取路徑樣式 token（具備已知副檔名的片段）。

    保留出現順序、去重；純數字版本號或 ticket ID 因無已知副檔名不會命中，
    見模組層級 `_MENTIONED_PATH_PATTERN` 註解。
    """
    found: List[str] = []
    for item in acceptance or []:
        for match in _MENTIONED_PATH_PATTERN.finditer(str(item or "")):
            token = match.group(1)
            if token not in found:
                found.append(token)
    return found


def _path_covered_by_where_files(token: str, where_files: List[str]) -> bool:
    """判定路徑樣式 token 是否被 where.files 涵蓋（前綴或檔名比對）。

    比對前剝除 `::read` / `::write` 逐檔意圖標記（與 `where.files` 其他
    消費端一致的 `::` 分隔慣例）。
    """
    basename = token.rsplit("/", 1)[-1]
    for raw in where_files or []:
        path = str(raw or "").split("::", 1)[0]
        if not path:
            continue
        if path == token or path.endswith("/" + token) or token.endswith("/" + path):
            return True
        if path.rsplit("/", 1)[-1] == basename:
            return True
    return False


def check_acceptance_path_coverage(
    acceptance: List,
    where_files: List[str],
) -> Tuple[str, List[str], str]:
    """檢查 6：acceptance 提及的檔案路徑須落在 where.files 內。

    從 acceptance 文字抽取路徑樣式 token（見 `_extract_mentioned_paths`），
    逐一與 `where.files` 做前綴或檔名比對；未涵蓋者判定為宣告不一致，
    直接 fail（強制，與檢查 4 / 檢查 5 的 warn-only 語意不同——本檢查的
    誤判成本已由已知副檔名 + ASCII 邊界收斂至可接受範圍，見模組 docstring
    「第六項檢查」動機）。

    Returns:
        (status, uncovered_tokens, msg) — status ∈ {"pass", "fail"}
    """
    mentioned = _extract_mentioned_paths(acceptance)
    if not mentioned:
        return "pass", [], "acceptance 未偵測到路徑樣式 token"

    uncovered = [
        token for token in mentioned if not _path_covered_by_where_files(token, where_files)
    ]
    if not uncovered:
        return (
            "pass",
            [],
            f"acceptance 提及 {len(mentioned)} 項路徑，where.files 已全數涵蓋",
        )

    msg = (
        f"acceptance 提及 {len(uncovered)} 項路徑未被 where.files 涵蓋，"
        "請把該路徑加進 where.files 或改寫 acceptance"
    )
    return "fail", uncovered, msg


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
    r5_status, r5_items, r5_msg = check_where_paths_existence(
        where_files or [], acceptance, get_project_root()
    )
    r6_status, r6_items, r6_msg = check_acceptance_path_coverage(
        acceptance, where_files or []
    )

    print(f"dispatch-readiness {ticket_id}:")
    print(_format_result("閾值 1 功能職責數（acceptance 近似）", r1_status, r1_msg))
    print(_format_result("閾值 2 修改檔案數（where.files）", r2_status, r2_msg))
    print(_format_result("閾值 3 Context Bundle tokens", r3_status, r3_msg))
    print(_format_result("檢查 4 acceptance 與寫入集一致性（啟發式）", r4_status, r4_msg))
    for item in r4_items:
        print(f"      - {item}")
    print(_format_result("檢查 5 where.files 路徑存在性（啟發式）", r5_status, r5_msg))
    for item in r5_items:
        print(f"      - {item}")
    print(_format_result("檢查 6 acceptance 提及路徑涵蓋性（強制）", r6_status, r6_msg))
    for item in r6_items:
        print(f"      - {item}")

    statuses = [r1_status, r2_status, r3_status, r4_status, r5_status, r6_status]
    if "fail" in statuses:
        print("[FAIL] 至少一項超強制拆分閾值，建議拆 ticket 後重新派發")
        return 2
    if "warn" in statuses:
        print("[WARN] 軟性警告：建議審視拆分必要性")
        return 1
    print("[PASS] 三項閾值 + 一致性檢查 + 路徑存在性檢查 + 路徑涵蓋性檢查全數通過")
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
