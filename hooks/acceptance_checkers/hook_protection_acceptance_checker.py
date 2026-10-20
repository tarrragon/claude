"""
Hook Protection Acceptance Checker - 防護類 hook ticket 的必含 acceptance +
產生路徑盤點表正本檢查

背景：一個新註冊的 guard hook 可能已註冊卻零效力且日誌零筆，而撰寫者與 PM
皆會因單元測試全綠、settings.json 已註冊、實機 dogfooding 通過三項訊號而誤信
防護已生效。此為結構性風險而非個案，且規則文字層級的預防措施（PC-BAL-033
早已列出對應要求）已證明無法單靠文件落實——用戶因此裁示強制層須為 acceptance
條目加 hook 硬擋。

零效力有兩條各自成立的成因，2026-08-18 實測後範圍已收窄（PC-BAL-033 v2.0.0
「機制更正」節）：檔案缺可執行位時 runtime 無從啟動它，此成因與 runtime 版本
無關、恆成立，一次 `chmod +x` 即恢復且不需重啟 session；session 啟動時一次
快照 hook 命令集則為**版本相依**——2026-08-13 觀測到的 runtime 上成立，
2026-08-18 觀測到的上不成立。故本 checker 要求撰寫者驗的是「本 session 實地
觸發是否落檔」，不是「屬哪個 session 世代」：前者在兩種載入模型下都是有效
證據，後者只在快照模型成立時才有意義。

觸發條件：type 為 IMP 且 where.files 觸及 hooks 目錄——頂層 `.claude/hooks/`
或任一 skill 私有 `.claude/skills/<skill>/hooks/`（後者同屬防護面，見既有
「hook 檔案落地監控」改造票的雙不管地帶教訓：只顧頂層會漏掉 skill hooks）。

必含四個面向：
1. 本 session 實地觸發確認：本次寫入的 hook 是否已於本 session 實地觸發並
   確認落檔；未能確認時說明如何因應（合格填法含「本 wave 該防護不生效，
   改以人工紀律承擔」——這是用戶裁示的部署期政策，檢查器不得因選擇此填法
   而擋）（語意關鍵詞檢查，命中對象為 acceptance）
2. liveness 驗證方式：如何確認 hook 確實被 runtime 載入並執行（日誌比對、
   liveness 探針等）（語意關鍵詞檢查，命中對象為 acceptance）
3. 失敗語意：異常時 fail-open 或 fail-closed（語意關鍵詞檢查，命中對象為
   acceptance）
4. 產生路徑盤點結果：本防護要擋的壞狀態有幾條產生路徑、現行攔截點覆蓋
   幾條、未覆蓋者在哪（table 解析，命中對象為 how.strategy，缺則
   Solution——見下方說明）

前三項為語意關鍵詞比對，非逐字比對，避免措辭差異造成 false negative，命中
對象維持在 acceptance（本項判定不變更）。

第四項改為解析正本而非驗證副本宣告：acceptance 的數字宣告只是副本，正本在
how.strategy（產生路徑盤點表，格式見 `.claude/pm-rules/ticket-body-schema.md`
「防護類 hook ticket 額外 acceptance」節）；對副本設閘門而正本不設是本項改版
所要修正的根因，且該宣告的價值繫於有人對照，而 IMP 的 Phase 4 消費者為
warning-only 的關鍵字 substring 檢查，讀者實質缺席。故本版本直接解析
`how.strategy`（缺則 `Solution`）的盤點表本體，行為三分：

  - 表格完全缺席（`_parse_path_inventory_table` 回傳 status="absent"）→
    阻擋 complete，訊息指出正本應寫於 how.strategy 並附格式範例
  - 表格存在且成功解析（status="ok"）→ 不阻擋，`logger.info` 輸出「本票
    盤點 N 條、覆蓋 M 條、未覆蓋 K 條」三個實際數字
  - 表格存在但解析失敗（status="failed"，如缺覆蓋欄、儲存格非「是/否」等
    非預期結構）→ fail-open：不阻擋、不拋例外，僅 `logger.warning` 記錄
    並略過計數輸出

acceptance 不再要求第四項的數字宣告（迴歸案例：僅含前三項語意而無盤點
數字的 ticket 應可通過）。

不觸發：type 非 IMP（ANA/DOC/ADJ 等）、where.files 不含 hooks 目錄路徑。
"""

import os
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath
from typing import List, NamedTuple, Optional, Tuple

_hooks_dir = Path(__file__).parent.parent
_claude_dir = _hooks_dir.parent
if str(_claude_dir) not in sys.path:
    sys.path.insert(0, str(_claude_dir))
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ticket_parser import extract_where_files_write_only

_APPLICABLE_TYPES = {"IMP"}

_TOP_LEVEL_HOOKS_PREFIX = PurePosixPath(".claude/hooks")

# 三項必含類別（substring 關鍵詞機制，維持不動）：
# label -> 命中任一關鍵詞即視為該項已提及（大小寫不敏感）
#
# 第一項的 label 於 2026-08-18 由「既有 session 生效策略」改為「本 session
# 實地觸發確認」，關鍵詞清單**刻意不動**：label 只用於缺項訊息的顯示，偵測
# 全靠 substring 命中，改動清單會使既有 pending 票的原措辭（含「重啟」
# 「restart」者）由通過翻為被擋。保留舊模型用詞於清單內不造成誤導——它們
# 是偵測用的寬鬆網，不是對撰寫者的填法建議；建議在 label 與 _format_block_message
# 的範例段給出。
_CATEGORY_KEYWORDS = {
    # 「實地觸發」為後補字面：實地觸發與 liveness 合寫一條的條目不含
    # 其餘字面時會被誤判缺項；只放寬（不會使既有通過者翻為被擋）。
    "本 session 實地觸發確認": ["session", "重啟", "生效", "restart", "實地觸發"],
    "liveness 驗證方式": ["liveness", "存活驗證", "存活探針"],
    "失敗語意（fail-open/fail-closed）": [
        "fail-open",
        "fail-closed",
        "fail open",
        "fail closed",
        "失敗語意",
        "失效語意",
    ],
}

# 第四項「產生路徑盤點結果」：命中對象為 how.strategy（缺則 Solution）的
# markdown 表格正本，不再檢查 acceptance 的數字宣告（副本）。表格格式見
# .claude/pm-rules/ticket-body-schema.md「防護類 hook ticket 額外
# acceptance」節：
#     | 產生路徑 | 是否覆蓋 | 未覆蓋原因 |
#     |---------|---------|-----------|
#     | ...     | 是/否    | ...       |
_PATH_INVENTORY_LABEL = "產生路徑盤點結果"
_INVENTORY_HEADER_MARKER = "產生路徑"
_COVERAGE_HEADER_MARKER = "覆蓋"
_TABLE_SEPARATOR_ROW_RE = re.compile(r"^\|?[\s:|-]+\|?$")
_COVERED_VALUES = frozenset({"是"})
_UNCOVERED_VALUES = frozenset({"否"})

# Solution 章節擷取邊界：下一個 `## ` 起始的標題或檔案結尾。與
# execution_log_checker._is_section_empty 用途不同（該函式只判斷「是否為
# 空」，不回傳內容），故此處另建輕量擷取函式，不共用其私有 regex。
_SOLUTION_SECTION_RE = re.compile(r"^## Solution\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


class PathInventoryResult(NamedTuple):
    """產生路徑盤點表解析結果。

    status 四態：
      - "no_separator"：找到含「產生路徑」的表頭列，但其下一行不是分隔列
        （表頭與分隔列之間夾空行等）→ 與 absent 同樣阻擋，僅訊息不同
      - "absent"：找不到含「產生路徑」表頭的表格 → 呼叫端應阻擋 complete
      - "failed"：表格存在但欄位/內容不符預期（缺覆蓋欄、儲存格非「是/否」
        等）→ 呼叫端應 fail-open（不阻擋、不拋例外，僅記錄 warning 並略過
        計數輸出）
      - "ok"：成功解析，total/covered/uncovered 為實際計數
    """

    status: str
    total: int = 0
    covered: int = 0
    uncovered: int = 0


def _extract_solution_section(content: str) -> str:
    """從 ticket body 擷取 Solution 章節文字，供 how.strategy 為空時的
    fallback 來源（產生路徑盤點表正本次選位置）。

    Args:
        content: Ticket 檔案完整文字內容（含 frontmatter 與 body）。

    Returns:
        str - Solution 章節內文字（已 strip），找不到則回傳空字串。
    """
    if not content:
        return ""
    match = _SOLUTION_SECTION_RE.search(content)
    return match.group(1).strip() if match else ""


def _split_table_row(line: str) -> List[str]:
    """把一行 markdown 表格列拆成各儲存格文字（去除前後 `|` 與空白）。"""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_path_inventory_table(text: str) -> PathInventoryResult:
    """解析文字中的產生路徑盤點表（markdown table）。

    偵測邏輯：逐行尋找「以 `|` 開頭且含『產生路徑』字樣，且下一行為表格
    分隔列（僅由 `|`、`-`、`:`、空白組成）」的表頭列；找不到即回傳
    status="absent"。表頭找到後，找出標示「覆蓋」的欄位索引，逐一解析後續
    以 `|` 開頭的資料列直到遇到非表格列為止；欄位缺失、儲存格值非「是/否」
    或無任何資料列，皆回傳 status="failed"（fail-open，交由呼叫端不阻擋）。

    Args:
        text: 待解析文字（how.strategy 或 Solution 章節內容）。

    Returns:
        PathInventoryResult
    """
    if not text or not text.strip():
        return PathInventoryResult(status="absent")

    lines = text.split("\n")
    header_idx = None
    header_without_separator = False
    for i in range(len(lines) - 1):
        stripped = lines[i].strip()
        if not (stripped.startswith("|") and _INVENTORY_HEADER_MARKER in stripped):
            continue
        if _TABLE_SEPARATOR_ROW_RE.match(lines[i + 1].strip()):
            header_idx = i
            break
        header_without_separator = True

    if header_idx is None:
        return PathInventoryResult(
            status="no_separator" if header_without_separator else "absent"
        )

    header_cells = _split_table_row(lines[header_idx])
    coverage_idx = next(
        (idx for idx, cell in enumerate(header_cells) if _COVERAGE_HEADER_MARKER in cell),
        None,
    )
    if coverage_idx is None:
        return PathInventoryResult(status="failed")

    data_rows = []
    for line in lines[header_idx + 2:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        data_rows.append(_split_table_row(stripped))

    if not data_rows:
        return PathInventoryResult(status="failed")

    covered = 0
    uncovered = 0
    for row in data_rows:
        if coverage_idx >= len(row):
            return PathInventoryResult(status="failed")
        value = row[coverage_idx]
        if value in _COVERED_VALUES:
            covered += 1
        elif value in _UNCOVERED_VALUES:
            uncovered += 1
        else:
            return PathInventoryResult(status="failed")

    return PathInventoryResult(
        status="ok", total=len(data_rows), covered=covered, uncovered=uncovered
    )


# 各項通過（should_block=False）時附帶提示，指向 ticket-body-schema 的攔截點
# 分工節。純提示，不影響 should_block 回傳值；透過 logger.info 輸出
# （liveness 驗證方式與既有三項一致：比對 hook-logs）。
_INTERCEPTION_POINT_HINT = (
    "提醒：本必含項檢查驗證的是「驗收手段與覆蓋範圍宣告」（防護是否在跑、"
    "擋住幾條路徑），另有一組正交要求管「防護攔截點寫在哪」（威脅事件寫"
    "acceptance，攔截點寫 how.strategy），兩者皆須滿足，見 "
    ".claude/pm-rules/ticket-body-schema.md「防護類 ticket：威脅事件寫 "
    "acceptance，攔截點寫 how.strategy」節"
)


def _normalize_path(raw: str) -> PurePosixPath:
    """以 PurePosixPath 標準化路徑，避免 string startswith 誤判（規則層要求，
    沿用 ticket_system.commands.track_parallel_check 既有慣例）。
    """
    return PurePosixPath(posixpath.normpath(raw.strip().strip("/")))


_PROJECT_ROOT = _claude_dir.parent


def _escapes_root(path: PurePosixPath) -> bool:
    """normpath 後仍以 `..` 開頭，即跳出專案根。"""
    return bool(path.parts) and path.parts[0] == ".."


def _resolve_real_relative(
    normalized: PurePosixPath, project_root: Path
) -> Optional[PurePosixPath]:
    """檔案存在時以 realpath 取實際路徑，回傳相對專案根的路徑。

    不存在則回傳 None（無 symlink 可解）；實際路徑落在專案根外則回傳以 `..`
    開頭的路徑，由呼叫端 fail-closed。
    """
    candidate = project_root / normalized.as_posix()
    if not candidate.exists():
        return None
    real = Path(os.path.realpath(candidate))
    real_root = Path(os.path.realpath(project_root))
    try:
        return PurePosixPath(real.relative_to(real_root).as_posix())
    except ValueError:
        return PurePosixPath("..")


def _is_under(path: PurePosixPath, prefix: PurePosixPath) -> bool:
    """path 是否等於 prefix 或為其子路徑。"""
    if path == prefix:
        return True
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False


def _is_skill_hooks_path(path: PurePosixPath) -> bool:
    """path 是否位於 `.claude/skills/<skill>/hooks/` 下（含該目錄本身）。"""
    parts = path.parts
    if len(parts) < 3 or parts[0] != ".claude" or parts[1] != "skills":
        return False
    # parts[2] 為 skill 名稱；第 4 段（index 3）須為 "hooks"，或路徑本身
    # 恰好在 skill 目錄下（parts 長度僅 3，無法判定，視為不命中——
    # 觸發範圍只關心 hooks 子目錄本身，不含整個 skill 目錄）
    return len(parts) >= 4 and parts[3] == "hooks"


def _is_hooks_tests_path(path: PurePosixPath) -> bool:
    """path 是否位於 `.claude/hooks/tests/` 或 `.claude/skills/<skill>/hooks/tests/` 下。

    測試檔不是會被 runtime 載入的 hook，只改它的票不需要實地觸發等四項。
    """
    if _is_under(path, _TOP_LEVEL_HOOKS_PREFIX / "tests"):
        return True
    parts = path.parts
    return _is_skill_hooks_path(path) and len(parts) >= 5 and parts[4] == "tests"


# 頂層 hooks/ 下的 pytest 基礎設施檔：不經 run_hook_safely、不產生 hook-logs，
# 也不被 runtime 當 hook 載入，只改它們的票無從提供 hook 四項證據。
# conftest.py 與其匯入的 testpaths_coverage_warning.py 為明列清單（名稱比對，
# 無 I/O）；新增同類檔須在此增列，漏列的方向是多要求證據（fail-closed）。
_PYTEST_INFRA_FILENAMES = frozenset({"conftest.py", "testpaths_coverage_warning.py"})


def _is_pytest_infra_path(path: PurePosixPath) -> bool:
    """path 是否為頂層 `.claude/hooks/` 直屬的 pytest 基礎設施檔（子目錄、
    skill hooks 下的同名檔不豁免）。"""
    return path.parent == _TOP_LEVEL_HOOKS_PREFIX and path.name in _PYTEST_INFRA_FILENAMES


def _in_hook_scope(path: PurePosixPath) -> bool:
    """已正規化路徑是否命中 hook 範圍（tests 排除在外）。"""
    if _is_hooks_tests_path(path):
        return False
    return _is_under(path, _TOP_LEVEL_HOOKS_PREFIX) or _is_skill_hooks_path(path)


def touches_hook_protection_scope(
    file_path: str, project_root: Optional[Path] = None
) -> bool:
    """單一路徑是否落在防護類 hook 觸發範圍（頂層 hooks/ 或 skill hooks/）。

    hooks/tests/ 下的路徑不命中；寫入集混合 tests 與 hook 本體時，
    hook 本體路徑仍會使整票命中（由 `_any_path_touches_hook_scope` 的 any 達成）。

    判定前先 normpath 解析 `.`、`..`；跳出專案根一律視為 hook 票（fail-closed）。
    檔案存在時另以 realpath 的實際路徑再判定一次（tests 下 symlink 指向 hook 本體）。
    """
    if not file_path:
        return False
    normalized = _normalize_path(file_path)
    if _escapes_root(normalized):
        return True
    if _is_pytest_infra_path(normalized):
        # 檔案存在時以實際路徑再判一次：同名 symlink 指向 hook 本體仍視為 hook
        real = _resolve_real_relative(normalized, project_root or _PROJECT_ROOT)
        if real is None:
            return False
        return _escapes_root(real) or (
            not _is_pytest_infra_path(real) and _in_hook_scope(real)
        )
    if _in_hook_scope(normalized):
        return True
    if not _is_hooks_tests_path(normalized):
        return False
    real = _resolve_real_relative(normalized, project_root or _PROJECT_ROOT)
    if real is None:
        return False
    return _escapes_root(real) or _in_hook_scope(real)


def _any_path_touches_hook_scope(where_files: List[str], logger=None) -> bool:
    """寫入集任一路徑命中即 True。判定例外時 fail-closed：視為 hook 票。"""
    try:
        return any(touches_hook_protection_scope(f) for f in where_files)
    except Exception as exc:  # fail-closed：寧可多要求四項也不放行
        if logger is not None:
            logger.warning(f"hook 票範圍判定例外，fail-closed 視為 hook 票：{exc}")
        return True


_PLACEHOLDER = "<待填>"


# 276.1 的模板（create.py 的 _HOOK_ACCEPTANCE_TEMPLATES）一律以「：<待填>」
# 結尾；只有此形式視為未填寫，條目中段敘述性提及 <待填> 不阻擋。
_TEMPLATE_SUFFIX = "：" + _PLACEHOLDER


def _is_template_placeholder(line: str) -> bool:
    """條目是否為未填寫模板：以「：<待填>」結尾，或以「：<待填：…>」指引形式結尾。"""
    stripped = line.rstrip()
    if stripped.endswith(_TEMPLATE_SUFFIX):
        return True
    return stripped.endswith(">") and "：<待填：" in stripped


def _placeholder_acceptance_items(frontmatter: dict) -> List[str]:
    """回傳 acceptance 中仍為模板形式（以「：<待填>」結尾）的條目文字。

    判定例外時 fail-closed：視為該條目未填寫。
    """
    items = []
    for line in _join_acceptance_text(frontmatter).split("\n"):
        try:
            if _is_template_placeholder(line):
                items.append(line)
        except Exception:  # fail-closed：判定失敗仍阻擋
            items.append(line)
    return items


def _join_acceptance_text(frontmatter: dict) -> str:
    """把 frontmatter.acceptance 正規化為單一文字區塊供關鍵詞掃描。"""
    raw = frontmatter.get("acceptance") or []
    if isinstance(raw, list):
        items = [str(item) for item in raw]
    elif isinstance(raw, str):
        items = raw.split("\n")
    else:
        items = []
    return "\n".join(items)


def _missing_categories(acceptance_text: str) -> List[str]:
    """回傳 acceptance 文字中未命中任一關鍵詞的類別標籤清單（空清單表示皆已提及）。

    僅涵蓋前三項（substring 關鍵詞機制）。第四項見 `parse_path_inventory_table`
    （命中對象已改為 how.strategy／Solution，不再檢查 acceptance）。
    """
    lowered = acceptance_text.lower()
    missing = []
    for label, keywords in _CATEGORY_KEYWORDS.items():
        if not any(keyword.lower() in lowered for keyword in keywords):
            missing.append(label)
    return missing


# 前三項改為檢查 Test Results／Solution 的證據（格式固定字串），
# acceptance 字面僅在過渡期作為「放行但 WARN」的依據。
_LABEL_TRIGGER = "本 session 實地觸發確認"
_LABEL_LIVENESS = "liveness 驗證方式"
_LABEL_FAILURE = "失敗語意（fail-open/fail-closed）"

# 日誌行引文（hook-logs/ 路徑後接檔名）或 `ticket track hook-liveness` 輸出標頭
# （「解析名稱: <name>」）。單純提及 hook-liveness 指令名稱或「記入 Solution」不算。
_LOG_EVIDENCE_RE = re.compile(r"hook-logs/[^\s`'\"]+|解析名稱\s*[:：]\s*\S")
_FAIL_DECLARATION_RE = re.compile(r"fail[- ]?(open|closed)", re.IGNORECASE)
_TRIGGER_CONDITION_RE = re.compile(r"觸發條件\s*[:：]\s*\S")
_EVIDENCE_SECTION_NAMES = ("Solution", "Test Results")
# 過渡期 WARN 的固定前綴，供統計誤擋率的下游工具比對
_TRANSITION_LOG_PREFIX = "[evidence-transition]"


def _extract_section(content: str, name: str) -> str:
    """擷取 `## <name>` 章節文字（至下一個 `## ` 或結尾）；缺席回傳空字串。"""
    if not content:
        return ""
    pattern = re.compile(
        r"^## " + re.escape(name) + r"\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(content)
    return match.group(1) if match else ""


def missing_evidence_categories(content: str) -> List[str]:
    """回傳在 Test Results／Solution 找不到證據的類別標籤（空清單表示齊備）。

    - 實地觸發、liveness：需有 hook-logs/ 日誌行引文或 hook-liveness 輸出標頭
    - 失敗語意：需有 fail-open／fail-closed 宣告，且同處有「觸發條件：<內容>」
    """
    evidence_text = "\n".join(_extract_section(content, n) for n in _EVIDENCE_SECTION_NAMES)
    missing = []
    if not _LOG_EVIDENCE_RE.search(evidence_text):
        missing.extend([_LABEL_TRIGGER, _LABEL_LIVENESS])
    if not (
        _FAIL_DECLARATION_RE.search(evidence_text)
        and _TRIGGER_CONDITION_RE.search(evidence_text)
    ):
        missing.append(_LABEL_FAILURE)
    return missing


def _extract_how_strategy(frontmatter: dict) -> str:
    """從 frontmatter.how.strategy 取出文字（非 dict 或欄位缺失時回傳空字串）。"""
    how_field = frontmatter.get("how")
    if not isinstance(how_field, dict):
        return ""
    return str(how_field.get("strategy") or "")


def check_hook_protection_acceptance(
    frontmatter: dict, logger, content: str = ""
) -> Tuple[bool, Optional[str]]:
    """檢查防護類 hook ticket 的必含項目：前三項命中 acceptance，第四項
    （產生路徑盤點結果）命中 how.strategy（缺則 Solution）的盤點表正本。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件
        content: Ticket 檔案完整文字內容（含 frontmatter 與 body）。第四項
            在 how.strategy 為空時，用本參數擷取 Solution 章節作為 fallback
            來源；呼叫端未傳入時（預設空字串）僅檢查 how.strategy。

    Returns:
        (should_block, message)
            - should_block=True：阻擋 complete（含完整阻擋訊息，列出缺項）
            - should_block=False：不適用或已通過（message 恆為 None；通過時
              另透過 logger.info 輸出攔截點分工節提示與（若第四項表格解析
              成功）盤點計數，見 `_INTERCEPTION_POINT_HINT`）
    """
    ticket_type = (frontmatter.get("type") or "").strip().upper()
    if ticket_type not in _APPLICABLE_TYPES:
        logger.debug(f"ticket type={ticket_type} 非 IMP，跳過防護類 hook acceptance 檢查")
        return False, None

    # 觸發判定以寫入集為據：以 ::read 標記的 hooks 路徑屬唯讀引用（如查證
    # stdout 比對邏輯），不代表本 ticket 會寫入 hook 檔案，不應觸發防護類
    # 要求；未標記與 ::write 標記維持既有觸發行為（預設視為寫入）。
    where_files = extract_where_files_write_only(frontmatter, logger)
    if not _any_path_touches_hook_scope(where_files, logger):
        logger.info(
            "write-set where.files 未觸及 hook 本體（無 hooks 路徑，或全落在 hooks/tests/），"
            "排除判定：跳過防護類 hook acceptance 檢查"
        )
        return False, None

    ticket_id = frontmatter.get("id", "未知")
    placeholders = _placeholder_acceptance_items(frontmatter)
    if placeholders:
        listed = "\n".join(f"  - {item}" for item in placeholders)
        logger.error(f"Ticket {ticket_id} acceptance 殘留 {_PLACEHOLDER} - 阻擋 complete")
        return True, (
            f"[ERROR] Acceptance Gate: 防護類 hook ticket 的 acceptance 殘留 "
            f"{_PLACEHOLDER}\n\nTicket: {ticket_id}\n"
            f"以下條目尚未填寫，請改寫為實際內容：\n{listed}\n"
        )
    acceptance_text = _join_acceptance_text(frontmatter)
    literal_missing = _missing_categories(acceptance_text)
    evidence_missing = missing_evidence_categories(content)
    # 過渡期：證據缺失但 acceptance 字面命中 → WARN 放行並記 log；
    # 證據缺失且字面也缺 → 阻擋（維持原有強度）
    missing = [label for label in evidence_missing if label in literal_missing]
    for label in evidence_missing:
        if label not in literal_missing:
            logger.warning(
                f"{_TRANSITION_LOG_PREFIX} ticket={ticket_id} category={label} "
                "acceptance 字面命中但 Test Results／Solution 無證據，過渡期放行",
                extra={
                    "ticket_id": ticket_id,
                    "category": label,
                    "missing_evidence": _EVIDENCE_FORMS[label],
                },
            )

    how_strategy = _extract_how_strategy(frontmatter)
    inventory_source = how_strategy if how_strategy.strip() else _extract_solution_section(content)
    inventory_result = parse_path_inventory_table(inventory_source)

    if inventory_result.status in ("absent", "no_separator"):
        missing.append(_PATH_INVENTORY_LABEL)
    elif inventory_result.status == "failed":
        logger.warning(
            f"Ticket {ticket_id} 產生路徑盤點表格式不符預期（欄位缺失或內容非"
            "預期結構），fail-open：不阻擋 complete，僅略過本項計數輸出"
        )
    else:  # "ok"
        logger.info(
            f"Ticket {ticket_id} 產生路徑盤點：盤點 {inventory_result.total} 條、"
            f"覆蓋 {inventory_result.covered} 條、未覆蓋 {inventory_result.uncovered} 條"
        )

    if not missing:
        logger.info(
            f"Ticket {ticket_id} 防護類 hook 必含項目齊備，通過。"
            f"{_INTERCEPTION_POINT_HINT}"
        )
        return False, None

    msg = _format_block_message(
        ticket_id, missing, header_without_separator=inventory_result.status == "no_separator"
    )
    logger.error(
        f"Ticket {ticket_id} where.files 觸及 hooks 目錄但缺必含項目 "
        f"{len(missing)} 項（{'、'.join(missing)}） - 阻擋 complete"
    )
    return True, msg


_EVIDENCE_FORMS = {
    _LABEL_TRIGGER: "Test Results 或 Solution 引用 .claude/hook-logs/ 下的日誌行"
    "（路徑加該行內容），證明本 session 實地觸發並落檔",
    _LABEL_LIVENESS: "Test Results 或 Solution 貼 `ticket track hook-liveness` 輸出"
    "（含「解析名稱: ...」標頭），或 hook-logs/ 路徑下的日誌行引文",
    _LABEL_FAILURE: "Solution 寫 fail-open 或 fail-closed 二擇一，並附"
    "「觸發條件：<何種情況觸發>」",
}


def _format_required_evidence(missing: List[str]) -> str:
    """列出缺項各自所需的證據形式與位置（僅前三項；第四項為表格判定，不適用）。"""
    lines = []
    for label in missing:
        form = _EVIDENCE_FORMS.get(label)
        if form:
            lines.append(f"  - {label}：{form}\n")
    return "".join(lines)


_NO_SEPARATOR_NOTICE = (
    "格式限制（為何被擋）：已找到含「產生路徑」的表頭列，但它的下一行不是分隔列，"
    "故被判為沒有表。表頭與分隔列之間、各資料列之間不可夾空行；"
    "下方範例即合格寫法（逐列緊接）。\n"
    "\n"
)


def _format_block_message(
    ticket_id: str, missing: List[str], header_without_separator: bool = False
) -> str:
    missing_list = "\n".join(f"  - {label}" for label in missing)
    msg = (
        f"[ERROR] Acceptance Gate: 防護類 hook ticket 缺必含項目\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"where.files 觸及 .claude/hooks/ 或 .claude/skills/<skill>/hooks/，"
        f"依規範必須補齊以下項目，缺少：\n"
        f"{missing_list}\n"
        f"\n"
        f"判定方式：檢查 ticket 的 Test Results 與 Solution 是否有證據，不比對 "
        f"acceptance 字句；只寫「記入 Solution」之類指向句不算證據。各項所需證據：\n"
        f"{_format_required_evidence(missing)}"
        f"\n"
        f"合格填法範例（寫在 Test Results 或 Solution）：\n"
        f"  - 實地觸發與 liveness：.claude/hook-logs/<hook 名>/<日期>.log "
        f"出現 `[INFO] ...` 該行（引文）\n"
        f"  - 失敗語意：fail-closed；觸發條件：判定函式拋例外時\n"
    )
    if _PATH_INVENTORY_LABEL in missing:
        if header_without_separator:
            msg += "\n" + _NO_SEPARATOR_NOTICE
        msg += (
            f"\n"
            f"產生路徑盤點結果——讀取優先序（為何會被擋）：checker 只判斷 "
            f"how.strategy 是否『非空』，不是『是否含盤點表』——how.strategy 只要"
            f"有任何文字（哪怕與盤點表無關），就完全不會讀 Solution；只有 "
            f"how.strategy 為空白時才 fallback 讀 Solution。表格寫在 Solution "
            f"卻仍被擋，通常是因為 how.strategy 已有其他策略文字擋住了 "
            f"fallback（後果：反覆修改 Solution 也不會過，因為根本沒被讀取）。\n"
            f"\n"
            f"正確寫入位置（下一步）：\n"
            f"  - how.strategy 目前完全空白 → 表格留在 Solution 或改寫入 "
            f"how.strategy 皆可\n"
            f"  - how.strategy 已有其他策略文字 → 表格須併入 how.strategy 本體"
            f"（--strategy 為整欄覆寫，需連同原文字一起帶入）：\n"
            f"      ticket track set-how {ticket_id} --strategy \"<原有策略文字>\n"
            f"\n"
            f"      <盤點表>\"\n"
            f"\n"
            f"格式為 markdown 表格（一條產生路徑一列，「是否覆蓋」欄僅接受「是」或"
            f"「否」）：\n"
            f"  | 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n"
            f"  |---------|---------|-----------|\n"
            f"  | 經工具正常寫入 | 是 | — |\n"
            f"  | 先寫註冊後建檔（順序調換） | 否 | 檢查時目標尚不存在，走 "
            f"fail-open |\n"
            f"\n"
            f"acceptance 不需重複宣告數字。\n"
        )
    msg += "\n參考：.claude/pm-rules/ticket-body-schema.md\n"
    return msg
