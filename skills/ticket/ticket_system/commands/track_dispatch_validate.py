"""ticket track dispatch-validate 命令（0.18.0-W17-003）。

對 target ticket 的 Context Bundle 自動填料結果做合理性檢查，作為 C 方案
（context_bundle_extractor 自動抽取）的第二道防線。與 W10-017.2 的
`dispatch-check`（活躍派發狀態查詢）職責正交，獨立子命令不互相干擾。

合理性檢查規則（5 項，規則 4 內部再分 4a/4b 兩個子檢查）：

1. 欄位非空 — Context Bundle section 必須存在且 content 非全空白
2. 內容長度 — Context Bundle content >= 50 字元（避免空殼填料）
3. 檔案存在 — frontmatter `where.files` 列出的檔案在檔案系統存在
4. acceptance：
   - 4a 項數 — >= 3 項，4V 原則，少於 3 項視為規格不足（啟發式，軟性）
   - 4b 樣板偵測 — 任一條目含大括號佔位符 token（如 `{feature_name}`）或與
     建立端 `DEFAULT_ACCEPTANCE_CRITERIA`（`ticket_system.lib.ticket_builder`）
     逐字相同，視為未填（確定性，硬性）
5. UC 對齊 — acceptance 中 UC 引用的 SSOT 存在性與指紋漂移（0.38.1-W1-066.3，fail-open）

**4a/4b 分軟硬理由**：4a 是啟發式門檻，會有合理誤報空間，故軟；4b 判準是
「與建立端樣板逐字相同」，沒有中間地帶——命中即代表這張票沒有可驗收的目標，
偵測到卻放行等於明知不可執行仍放行，故硬。

Exit code 語意：

- 0: 全部規則通過
- 1: 軟性警告（規則 2 / 3 / 4a / 5 部分違反，可派發但建議修正）
- 2: 硬性失敗（規則 1 或規則 4b 違反、ticket 不存在、IO 錯誤；兩者同時違反時
  訊息列出所有命中的硬性規則名稱，不只回報其中一項）

**Exit code 與 dispatch-check 語意不共享**：本命令 exit 1 = 軟性警告 /
exit 2 = 硬性失敗或 IO 錯誤；既有 dispatch-check exit 1 = 有活躍派發 /
exit 2 = IO 錯誤。呼叫端必須以命令名稱判別語意，禁止以 exit code
跨命令解讀。

邊界：本 CLI **不** 修改 ticket、**不** 取代 hook / scheduler；僅輸出結構化
診斷供 PM / agent 派發前自檢使用（W17-209 ANA 方案 A）。
"""

from __future__ import annotations

import argparse
import json as _json
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

from ticket_system.lib.checkbox_utils import strip_checkbox_prefix
from ticket_system.lib.dispatch_common import load_and_unpack
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.section_locator import SectionMatch, find_section
from ticket_system.lib.ticket_builder import DEFAULT_ACCEPTANCE_CRITERIA


_CONTEXT_BUNDLE_SECTION = "Context Bundle"
_MIN_CONTENT_CHARS = 50
_MIN_ACCEPTANCE_ITEMS = 3
_DOC_CLI_TIMEOUT_SECONDS = 15

# 規則 4b 樣板偵測的判準來源：建立端唯一權威（不在驗證端另建副本字面，
# 避免兩份清單各自漂移）。攤平所有 ticket 類型的預設樣板為單一集合——
# 未填樣板無論落在哪個類型的預設值都應被判為未填，不需按 ticket 自身類型
# 篩選比對範圍。
_TEMPLATE_ACCEPTANCE_ITEMS = frozenset(
    item for items in DEFAULT_ACCEPTANCE_CRITERIA.values() for item in items
)

# 佔位符 token 樣式：建立端的大括號佔位符（`{feature_name}`、`{N}`、
# `{coverage_target}` 等）皆為單一識別字，不含空白或標點。用此樣式而非
# 「任何含大括號的字串」，避免誤擋描述正常內容（如 JSON/dict 語法）時
# 帶大括號的合法 acceptance 條目。
_PLACEHOLDER_TOKEN_PATTERN = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


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
    """規則 4a：acceptance 至少含 min_items 項（啟發式，軟性）。"""
    n = len(acceptance or [])
    if n < min_items:
        return False, f"acceptance 僅 {n} 項 < {min_items}（規則 4a 違反，4V 原則不足）"
    return True, f"acceptance {n} 項 >= {min_items}"


def _is_placeholder_acceptance_item(item: str) -> bool:
    """判斷單一 acceptance 條目是否為未填的建立端樣板。

    兩種判準（任一命中即視為未填）：
    - 含大括號佔位符 token（如 `{feature_name}`，樣式見
      `_PLACEHOLDER_TOKEN_PATTERN`）——多數樣板類型帶此標記；
    - 與 `_TEMPLATE_ACCEPTANCE_ITEMS`（建立端 `DEFAULT_ACCEPTANCE_CRITERIA`
      攤平集合）逐字相同——補足不帶大括號的樣板條目（如 DOC 型第 2、3 條），
      單靠大括號偵測會漏判。
    """
    _, text = strip_checkbox_prefix(item)
    if _PLACEHOLDER_TOKEN_PATTERN.search(text):
        return True
    return text in _TEMPLATE_ACCEPTANCE_ITEMS


def check_acceptance_placeholder(acceptance: List) -> Tuple[bool, str]:
    """規則 4b：acceptance 不含未填的建立端樣板（確定性，硬性）。

    命中即代表這張票尚未填寫真正的驗收條件，判準無中間地帶（見模組
    docstring「4a/4b 分軟硬理由」）。
    """
    hits = [
        str(item) for item in (acceptance or [])
        if _is_placeholder_acceptance_item(str(item))
    ]
    if hits:
        return False, f"acceptance 含 {len(hits)} 項未填樣板（規則 4b 違反）: {hits}"
    return True, "acceptance 無未填樣板"


def check_acceptance_uc_alignment(
    ticket_id: str,
) -> Tuple[bool, str]:
    """規則 5：acceptance 中 UC 引用的存在性與指紋漂移對齊。

    透過 subprocess 呼叫 ``doc uc acceptance-check --json``，fail-open：
    doc CLI 不可用或執行失敗時回傳 (True, info)，不阻擋派發。
    """
    try:
        result = subprocess.run(
            ["doc", "uc", "acceptance-check", ticket_id, "--json"],
            capture_output=True,
            text=True,
            timeout=_DOC_CLI_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return True, "doc CLI 不可用，UC 對齊檢查已略過"

    if result.returncode == 2:
        return True, f"UC 對齊檢查 IO 錯誤，已略過: {result.stderr.strip()}"

    try:
        data = _json.loads(result.stdout)
    except (ValueError, _json.JSONDecodeError):
        return True, "UC 對齊檢查輸出無法解析，已略過"

    results = data.get("results", [])
    if not results:
        return True, "acceptance 中無 UC 引用（略過對齊檢查）"

    summary = data.get("summary", {})
    drift = summary.get("drift", 0)
    missing = summary.get("missing", 0)

    if drift > 0 or missing > 0:
        issues = [
            f"{r['uc_id']}={r['status']}"
            for r in results
            if r.get("status") in ("DRIFT", "MISSING")
        ]
        return False, f"acceptance 中 {len(issues)} 個 UC 對齊問題: {', '.join(issues)}"

    return True, f"acceptance 中 {summary.get('pass', 0)} 個 UC 引用全部對齊"


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

    # 規則 1 + 規則 4b 硬性；規則 2/3/4a/5 軟性
    r1_ok, r1_msg = check_section_present(body, match=cb_match)
    r2_ok, r2_msg = check_content_length(body, match=cb_match)
    r3_ok, r3_msg = check_where_files_exist(where_files or [], project_root=project_root)
    r4a_ok, r4a_msg = check_acceptance_count(acceptance)
    r4b_ok, r4b_msg = check_acceptance_placeholder(acceptance)

    # 規則 5：acceptance 中 UC 引用對齊（fail-open）
    r5_ok, r5_msg = check_acceptance_uc_alignment(ticket_id)

    print(f"dispatch-validate {ticket_id}:")
    print(_format_result("規則 1 欄位非空", r1_ok, r1_msg))
    print(_format_result("規則 2 內容長度", r2_ok, r2_msg))
    print(_format_result("規則 3 檔案存在", r3_ok, r3_msg))
    print(_format_result("規則 4a acceptance 項數", r4a_ok, r4a_msg))
    print(_format_result("規則 4b 樣板偵測", r4b_ok, r4b_msg))
    print(_format_result("規則 5 UC 對齊", r5_ok, r5_msg))

    # where.files 空時補 INFO 提示（避免靜默通過遮蔽 W17-002 抽取漏掉）
    if not (where_files or []):
        print(
            "  [INFO] where.files 為空：規則 3 自動通過。若本 ticket 應修改檔案，"
            "請確認 frontmatter where.files 已正確填寫（DOC 類 ticket 可忽略）"
        )

    # 規則 1 或規則 4b 違反 → 硬性失敗 exit 2。兩者可能同時違反（未填樣板的票
    # 通常同時缺 Context Bundle），訊息須列出所有命中的硬性規則，不只回報其一。
    hard_violations = [
        name for name, ok in (("規則 1", r1_ok), ("規則 4b", r4b_ok)) if not ok
    ]
    if hard_violations:
        print(f"[FAIL] {', '.join(hard_violations)} 違反，視為硬性失敗")
        return 2

    # 規則 2/3/4a/5 任一違反 → 軟性警告 exit 1
    soft_violations = [
        ("規則 2", r2_ok),
        ("規則 3", r3_ok),
        ("規則 4a", r4a_ok),
        ("規則 5", r5_ok),
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
