"""
Acceptance Auditor 驗收檢查模組

負責執行四步驟驗收流程：
1. 結構完整性檢查
2. 子任務完成狀態檢查
3. 執行日誌完整性檢查
4. 驗收條件一致性檢查
"""
# 防止直接執行此模組
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .ticket_loader import load_ticket, resolve_version, get_project_root, get_tickets_dir
from .parser import parse_frontmatter
from .constants import STATUS_COMPLETED, VAGUE_ACCEPTANCE_WORDS, SRP_WHAT_CONJUNCTIONS, SRP_ACCEPTANCE_MODULE_THRESHOLD


# ============================================================
# 資料結構
# ============================================================

@dataclass
class AuditStep:
    """驗收檢查步驟結果"""
    name: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped: bool = False

    def is_success(self) -> bool:
        """判斷步驟是否成功（通過或警告）"""
        return self.passed or (not self.issues and self.warnings)

    def get_status_label(self) -> str:
        """取得狀態標籤"""
        if self.skipped:
            return "SKIP"
        if self.passed:
            return "PASS" if not self.warnings else "WARN"
        return "FAIL"


@dataclass
class AuditReport:
    """驗收報告"""
    ticket_id: str
    title: str
    timestamp: str
    steps: List[AuditStep] = field(default_factory=list)
    overall_passed: bool = False

    def add_step(self, step: AuditStep) -> None:
        """加入檢查步驟"""
        self.steps.append(step)

    def get_result_label(self) -> str:
        """取得整體結果標籤"""
        return "通過" if self.overall_passed else "未通過"

    def get_failed_steps(self) -> List[AuditStep]:
        """取得所有失敗的步驟"""
        return [s for s in self.steps if not s.passed and not s.skipped]

    def get_warning_steps(self) -> List[AuditStep]:
        """取得有警告的步驟"""
        return [s for s in self.steps if s.warnings and s.passed]


# ============================================================
# Step 1: 結構完整性檢查
# ============================================================

def validate_structure(ticket: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    檢查 Ticket YAML frontmatter 的必填欄位

    必填欄位（13個）：
    - id, title, type, status, version, wave, priority
    - who.current（巢狀欄位）
    - what, why
    - acceptance（非空陣列）
    - assigned（為 true）, started_at（非空）

    Returns:
        (passed: bool, issues: list[str])
    """
    issues = []

    # 檢查簡單欄位
    required_simple = ["id", "title", "type", "status", "version", "wave", "priority", "what", "why"]
    for field in required_simple:
        value = ticket.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            issues.append(f"缺失或為空：{field}")

    # 檢查 who.current（巢狀）
    who = ticket.get("who")
    if not who or not isinstance(who, dict):
        issues.append("缺失或無效：who（應為字典）")
    if not who or not who.get("current") or not str(who.get("current")).strip():
        issues.append("缺失或為空：who.current")

    # 檢查 acceptance（非空陣列）
    acceptance = ticket.get("acceptance")
    if not isinstance(acceptance, list) or len(acceptance) == 0:
        issues.append("缺失或為空：acceptance（應為非空陣列）")

    # 檢查 assigned（為 true）
    assigned = ticket.get("assigned")
    if assigned is not True:
        issues.append("缺失或無效：assigned（應為 true）")

    # 檢查 started_at（非空）
    started_at = ticket.get("started_at")
    if not started_at or not str(started_at).strip():
        issues.append("缺失或為空：started_at")

    # 檢查有效的 type
    valid_types = ["IMP", "TST", "ADJ", "RES", "ANA", "INV", "DOC"]
    if ticket.get("type") not in valid_types:
        issues.append(f"無效的 type：{ticket.get('type')}（有效值：{', '.join(valid_types)}）")

    # 檢查有效的 status
    valid_statuses = ["pending", "in_progress", "completed", "blocked"]
    if ticket.get("status") not in valid_statuses:
        issues.append(f"無效的 status：{ticket.get('status')}（有效值：{', '.join(valid_statuses)}）")

    # 檢查有效的 priority
    valid_priorities = ["P0", "P1", "P2", "P3"]
    if ticket.get("priority") not in valid_priorities:
        issues.append(f"無效的 priority：{ticket.get('priority')}（有效值：{', '.join(valid_priorities)}）")

    passed = len(issues) == 0
    return passed, issues


# ============================================================
# Step 2: 子任務完成狀態檢查
# ============================================================

def _check_children_recursive(children_ids: List[str], version: str, visited: Optional[set] = None) -> Tuple[bool, List[str]]:
    """
    遞迴檢查子任務是否全部完成

    Args:
        children_ids: 子任務 ID 列表
        version: 版本號
        visited: 已訪問的 ID 集合（防止循環參照）

    Returns:
        (all_completed: bool, incomplete_ids: list[str])
    """
    if visited is None:
        visited = set()

    incomplete = []

    for child_id in children_ids:
        # 防止循環參照
        if child_id in visited:
            continue
        visited.add(child_id)

        # 載入子任務
        child_ticket = load_ticket(version, child_id)
        if not child_ticket:
            incomplete.append(f"找不到檔案：{child_id}")
            continue

        # 檢查子任務狀態
        if child_ticket.get("status") != STATUS_COMPLETED:
            incomplete.append(child_id)

        # 遞迴檢查孫任務
        grandchildren = child_ticket.get("children", [])
        if grandchildren:
            _, grandchild_incomplete = _check_children_recursive(grandchildren, version, visited)
            incomplete.extend(grandchild_incomplete)

    all_completed = len(incomplete) == 0
    return all_completed, incomplete


def validate_children_completed(ticket: Dict[str, Any], version: str) -> Tuple[bool, List[str], bool]:
    """
    檢查子任務全部完成

    Returns:
        (passed: bool, issues: list[str], skipped: bool)
    """
    children = ticket.get("children", [])

    # 無子任務時跳過
    if not children or len(children) == 0:
        return True, [], True

    # 檢查子任務
    all_completed, incomplete = _check_children_recursive(children, version)

    if not all_completed:
        issues = [f"未完成的子任務：{', '.join(incomplete)}"]
        return False, issues, False

    return True, [], False


# ============================================================
# Step 3: 執行日誌完整性檢查
# ============================================================

def _is_placeholder(text: str) -> bool:
    """
    判斷文字是否為佔位符

    佔位符模式：
    - HTML 註解：<!-- ... -->
    - 待填寫標記：(pending), TBD, TODO, N/A
    - 空白或僅有換行
    """
    if not text or not isinstance(text, str):
        return True

    stripped = text.strip()

    # 空白或僅有換行
    if not stripped:
        return True

    # HTML 註解
    if re.search(r"<!--.*?-->", stripped, re.DOTALL):
        return True

    # 待填寫標記
    if re.search(r"\(pending\)|TBD|TODO|N/A", stripped, re.IGNORECASE):
        return True

    return False


def validate_execution_log_completeness(body: str) -> Tuple[bool, List[str]]:
    """
    檢查執行日誌（Execution Log）區段是否已填寫

    必檢查的三個區段：
    - ## Problem Analysis
    - ## Solution
    - ## Test Results

    Returns:
        (passed: bool, issues: list[str])
    """
    required_sections = ["Problem Analysis", "Solution", "Test Results"]
    missing_sections = []

    # Guard Clause：無 body 內容時視為未填寫
    if not body or not isinstance(body, str):
        return False, [f"所有區段未填寫：{', '.join(required_sections)}"]

    for section in required_sections:
        # 搜尋區段標題（支援 ## 或 ### 層級）
        patterns = [
            rf"^##\s+{re.escape(section)}\s*$",
            rf"^###\s+{re.escape(section)}\s*$"
        ]

        section_match = None
        for pattern in patterns:
            section_match = re.search(pattern, body, re.MULTILINE)
            if section_match:
                break

        # 找不到區段標題
        if not section_match:
            missing_sections.append(section)
            continue

        # 擷取區段內容（從標題到下一個同層級 ## 標題或文件結尾）
        # 注意：### 子標題屬於父區段內容，不作為邊界
        content_start = section_match.end()

        # 找到下一個同層級區段的開頭
        next_section_pattern = r"\n## "
        next_match = re.search(next_section_pattern, body[content_start:])

        if next_match:
            section_content = body[content_start:content_start + next_match.start()]
        else:
            section_content = body[content_start:]

        # 檢查區段內容是否為佔位符或空白
        if _is_placeholder(section_content):
            missing_sections.append(section)

    if missing_sections:
        issues = [f"未填寫的區段：{', '.join(missing_sections)}"]
        return False, issues

    return True, []


# ============================================================
# Step 4: 驗收條件一致性檢查
# ============================================================

def _extract_keywords(text: str, max_words: int = 3) -> List[str]:
    """
    從文字中提取關鍵詞（前幾個有意義的詞）

    Args:
        text: 要提取的文字
        max_words: 最多提取的詞數

    Returns:
        關鍵詞列表
    """
    # 移除特殊字符，只保留字母、數字和中文
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", text)
    # 分割成詞
    words = cleaned.split()
    # 取前 max_words 個詞，轉小寫便於比較
    return [w.lower() for w in words[:max_words]]


def validate_acceptance_consistency(
    acceptance_list: Optional[List[str]],
    solution_text: str,
    test_results_text: str
) -> Tuple[bool, List[str]]:
    """
    檢查驗收條件與執行日誌的一致性

    使用關鍵字比對方法：
    - 從驗收條件提取關鍵詞
    - 在 Solution 和 Test Results 中搜尋對應記錄
    - 找到 → PASS；找不到 → WARN（不是 FAIL）

    Returns:
        (passed: bool, warnings: list[str])
    """
    if not acceptance_list or len(acceptance_list) == 0:
        return True, []

    # 合併日誌文本便於搜尋
    log_text = f"{solution_text}\n{test_results_text}".lower()

    warnings = []

    for idx, condition in enumerate(acceptance_list, 1):
        if not isinstance(condition, str):
            continue

        # 提取關鍵詞
        keywords = _extract_keywords(condition)

        # 跳過空條件
        if not keywords:
            continue

        # 檢查是否在日誌中找到對應記錄
        found = False
        for keyword in keywords:
            if keyword in log_text:
                found = True
                break

        # 未找到 → 標記為警告
        if not found:
            condition_preview = condition[:50]
            warnings.append(f"AC-{idx}：無法自動確認「{condition_preview}...」的對應記錄")

    # 警告不導致失敗，只返回 True + 警告清單
    return True, warnings


# ============================================================
# Step 4.5: 含糊驗收條件偵測
# ============================================================

def detect_vague_acceptance(
    acceptance_list: Optional[List[str]],
) -> List[str]:
    """
    偵測驗收條件中的模糊詞彙

    掃描驗收條件中的模糊詞彙清單。若條件只包含模糊詞而無量化指標，輸出 WARNING。
    判斷邏輯：條件文字（去除 `[ ]` 前綴後）若只由模糊詞 + 連接詞組成，
    沒有數字、百分比、具體檔案名、具體功能名等量化指標，則標記為 vague。

    Args:
        acceptance_list: 驗收條件清單（YAML list 或 None）

    Returns:
        List[str]: 警告訊息清單
        - []: 無模糊詞或有量化指標
        - [warnings...]: 偵測到的模糊詞警告
    """
    if not acceptance_list or len(acceptance_list) == 0:
        return []

    warnings = []

    for idx, condition in enumerate(acceptance_list, 1):
        if not isinstance(condition, str):
            continue

        # 移除 [ ] 或 [x] 前綴
        cleaned = condition.strip()
        if cleaned.startswith("[") and "]" in cleaned:
            # 移除 [ ] 或 [x] 及其後的空白
            cleaned = cleaned.split("]", 1)[1].strip()

        # 判斷是否只包含模糊詞
        has_vague_word = False
        vague_found = []

        for vague_word in VAGUE_ACCEPTANCE_WORDS:
            if vague_word in cleaned:
                has_vague_word = True
                vague_found.append(vague_word)

        # 若有模糊詞，檢查是否有量化指標
        if has_vague_word:
            # 檢查是否包含量化指標：數字、百分比、具體名稱等
            has_metrics = bool(re.search(r'\d+|%|個|次|項|檔|行|秒|分|小時|天', cleaned))

            # 若無量化指標，標記為含糊
            if not has_metrics:
                vague_preview = cleaned[:50]
                vague_words_str = ", ".join(set(vague_found))
                warnings.append(
                    f"AC-{idx} 含糊：「{vague_preview}...」只有模糊詞（{vague_words_str}），"
                    f"建議補充量化指標（如：「5 個案例」「100% 通過」等）"
                )

    return warnings


# ============================================================
# SRP 違規偵測（create 層輕量提示）
# ============================================================

def _detect_srp_multi_target(what_text: str) -> Tuple[bool, List[str]]:
    """
    偵測 what 欄位中的多目標連接詞。

    掃描 what 文字是否包含並列連接詞（和/與/及/並/同時），
    暗示 Ticket 可能包含多個獨立目標。

    Args:
        what_text: what 欄位文字

    Returns:
        (has_conjunction, found_conjunctions):
        - has_conjunction: 是否找到並列連接詞
        - found_conjunctions: 找到的連接詞清單
    """
    # Guard Clause：空值或無意義文字
    if not what_text or not isinstance(what_text, str):
        return False, []

    cleaned = what_text.strip()
    if not cleaned or len(cleaned) < 2:
        return False, []

    # 掃描並列連接詞
    found_conjunctions = []
    for conjunction in SRP_WHAT_CONJUNCTIONS:
        if conjunction in cleaned:
            found_conjunctions.append(conjunction)

    # 回傳結果
    if found_conjunctions:
        return True, found_conjunctions
    return False, []


def _detect_srp_cross_module(acceptance_list: Optional[List[str]]) -> Tuple[bool, List[str]]:
    """
    偵測驗收條件中的跨模組特徵。

    從驗收條件文字中識別模組名稱（.py 檔案）。
    若不同模組數量超過閾值，視為跨模組。

    Args:
        acceptance_list: 驗收條件清單

    Returns:
        (is_cross_module, detected_modules):
        - is_cross_module: 是否偵測到跨模組特徵
        - detected_modules: 識別到的模組名稱清單
    """
    # Guard Clause：空值或無意義清單
    if not acceptance_list or len(acceptance_list) == 0:
        return False, []

    detected_modules = set()

    # 掃描驗收條件並提取模組名稱
    for item in acceptance_list:
        # 跳過非字串元素
        if not isinstance(item, str):
            continue

        # 識別方式：檔案路徑（含 .py）
        # 匹配 xxx.py 或 xxx_yyy.py 格式
        file_matches = re.findall(r'\b(\w+)\.py\b', item)
        detected_modules.update(m.lower() for m in file_matches)

    # 判斷是否跨模組
    module_count = len(detected_modules)
    if module_count > SRP_ACCEPTANCE_MODULE_THRESHOLD:
        return True, sorted(list(detected_modules))
    return False, []


def detect_srp_violations(
    what_text: str,
    acceptance_list: Optional[List[str]],
) -> List[str]:
    """
    偵測 Ticket 是否有潛在的 SRP（單一職責原則）違規。

    執行兩項輕量偵測：
    1. what 欄位多目標連接詞偵測
    2. 驗收條件跨模組偵測

    此函式僅用於建立時的輕量提示，不作為阻止建立的依據。
    詳細 SRP 審查由 SA 層（saffron-system-analyst）在 Phase 0 執行。

    Args:
        what_text: Ticket 的 what 欄位文字（不可為 None）
        acceptance_list: 驗收條件清單（可為 None）

    Returns:
        List[str]: 警告訊息清單
        - []: 未偵測到 SRP 疑慮
        - [warning_messages...]: 偵測到的疑慮，回傳警告訊息清單

    Note:
        回傳為警告清單，調用端用 `if warnings:` 判斷有無疑慮。
        偵測結果只用於輸出 WARNING，不影響 create 命令的回傳碼。
    """
    # Guard Clause
    if not what_text:
        what_text = ""
    if not acceptance_list:
        acceptance_list = []

    warning_messages = []

    # Lazy import：只在需要時才載入（減少依賴開銷）
    from .command_lifecycle_messages import CreateMessages

    # 執行 what 欄位偵測
    has_what_issue, conjunctions = _detect_srp_multi_target(what_text)
    if has_what_issue and conjunctions:
        message = CreateMessages.SRP_MULTI_TARGET_WARNING.format(
            conjunctions="、".join(conjunctions)
        )
        warning_messages.append(message)

    # 執行 acceptance 欄位偵測
    has_accept_issue, modules = _detect_srp_cross_module(acceptance_list)
    if has_accept_issue and modules:
        message = CreateMessages.SRP_CROSS_MODULE_WARNING.format(
            modules="、".join(modules)
        )
        warning_messages.append(message)

    return warning_messages


# ============================================================
# Step 5: 後續任務銜接檢查
# ============================================================

def _extract_root_ticket_id(ticket_id: str) -> str:
    """
    從 Ticket ID 提取任務鏈根 ID

    例如：
    - "0.31.0-W4-052.4.1" → "0.31.0-W4-052"
    - "0.31.0-W4-052" → "0.31.0-W4-052"

    Args:
        ticket_id: Ticket ID

    Returns:
        任務鏈根 ID
    """
    # 移除小數點後的子任務編號
    parts = ticket_id.split(".")
    # 取前三個部分（版本-Wave-序號）
    return ".".join(parts[:3])


def _get_all_siblings_in_chain(root_id: str, version: str) -> List[Dict[str, Any]]:
    """
    取得同一任務鏈中所有的兄弟 Ticket

    Args:
        root_id: 任務鏈根 ID（如 "0.31.0-W4-052"）
        version: 版本號

    Returns:
        同任務鏈的所有 Ticket 列表
    """
    try:
        from .ticket_loader import list_tickets
    except ImportError:
        return []

    # 取得所有 Ticket
    all_tickets = list_tickets(version)

    # 過濾出同任務鏈的 Ticket（ID 以 root_id 開頭）
    siblings = [
        t for t in all_tickets
        if isinstance(t.get("id"), str) and t.get("id").startswith(root_id)
    ]

    return siblings


def _has_impl_or_adj_child(ticket: Dict[str, Any], version: str) -> bool:
    """
    檢查 children 中是否包含 IMP 或 ADJ 類型的子任務

    Args:
        ticket: Ticket 資料
        version: 版本號

    Returns:
        True 若有 IMP/ADJ 子任務，False 否則
    """
    children_ids = ticket.get("children", [])
    if not children_ids:
        return False

    for child_id in children_ids:
        child_ticket = load_ticket(version, child_id)
        if child_ticket and child_ticket.get("type") in ["IMP", "ADJ"]:
            return True

    return False


def _has_followup_in_spawned(ticket: Dict[str, Any]) -> bool:
    """
    檢查 spawned_tickets 中是否有後續任務

    Args:
        ticket: Ticket 資料

    Returns:
        True 若有後續任務，False 否則
    """
    spawned = ticket.get("spawned_tickets", [])
    return len(spawned) > 0


def _has_followup_in_chain(ticket_id: str, version: str) -> bool:
    """
    檢查同任務鏈中是否有序號更大的 Ticket

    例如：
    - 若當前為 "0.31.0-W4-052.1"，檢查是否有 "0.31.0-W4-052.2"、"0.31.0-W4-052.3" 等

    Args:
        ticket_id: Ticket ID
        version: 版本號

    Returns:
        True 若有後續 Ticket，False 否則
    """
    root_id = _extract_root_ticket_id(ticket_id)
    siblings = _get_all_siblings_in_chain(root_id, version)

    # 提取當前 Ticket 的序號深度和值
    # 例如："0.31.0-W4-052.1.2" → [52, 1, 2]
    current_parts = ticket_id.split(".")
    root_parts = root_id.split(".")
    current_sequence = [int(p) for p in current_parts[3:]]  # 去掉版本-Wave-序號部分

    # Guard Clause：如果當前沒有子序號，則檢查是否有 ".1" 的子任務
    if not current_sequence:
        for sibling in siblings:
            sibling_id = sibling.get("id", "")
            if sibling_id.startswith(ticket_id + "."):
                return True
        return False

    # 檢查是否有序號更大的同層任務
    for sibling in siblings:
        sibling_id = sibling.get("id", "")

        # 跳過自己
        if sibling_id == ticket_id:
            continue

        # 提取兄弟的序號
        sibling_parts = sibling_id.split(".")
        sibling_sequence = [int(p) for p in sibling_parts[3:]]  # 去掉版本-Wave-序號部分

        # 檢查是否同層且序號更大
        # 同層 = 序號深度相同且前面的部分相同
        if len(sibling_sequence) == len(current_sequence):
            if sibling_sequence[:-1] == current_sequence[:-1]:  # 前面部分相同
                if sibling_sequence[-1] > current_sequence[-1]:  # 最後一層更大
                    return True

        # 檢查是否有子任務（同層但序號深度更深）
        if len(sibling_sequence) > len(current_sequence):
            if sibling_sequence[:len(current_sequence)] == current_sequence:
                return True

    return False


def _has_no_followup_declaration(body: str) -> bool:
    """
    檢查 Ticket body 中是否有「不需後續」的明確聲明

    Args:
        body: Ticket body 文字

    Returns:
        True 若有不需後續聲明，False 否則
    """
    if not body or not isinstance(body, str):
        return False

    # 搜尋「不需後續」或「無需後續行動」等文字
    patterns = [
        r"不需後續",
        r"無需後續",
        r"不需要後續",
        r"後續任務已規劃|後續已規劃",
        r"此為獨立任務|獨立任務|自成一體",
    ]

    for pattern in patterns:
        if re.search(pattern, body):
            return True

    return False


def validate_followup_tasks(ticket: Dict[str, Any], version: str, body: str) -> Tuple[bool, List[str], bool]:
    """
    檢查是否有後續任務（設計/分析/調查/研究類任務應有後續行動 Ticket）

    核心規則：
    - 「應有後續」的類型：RES, ANA, INV，以及 Phase 1/2/3a（從 title 識別）
    - 「不需後續」的類型：IMP, ADJ, DOC, TST, Phase 3b, Phase 4
    - 後續任務識別優先級：children (IMP/ADJ) → spawned_tickets → 同鏈 Ticket
    - 豁免條件：body 中明確聲明「不需後續」

    Args:
        ticket: Ticket 資料
        version: 版本號
        body: Ticket body 文字

    Returns:
        (passed: bool, warnings: list[str], skipped: bool)
        - passed: 通過（有後續或豁免）
        - warnings: 警告訊息清單
        - skipped: 是否跳過（不需檢查的類型）
    """
    ticket_type = ticket.get("type", "")
    ticket_id = ticket.get("id", "")
    title = ticket.get("title", "")

    # Guard Clause：不需檢查的類型直接跳過
    if ticket_type in ["IMP", "ADJ", "DOC", "TST"]:
        return True, [], True

    # 檢查 Phase 型任務（從 title 中識別）
    # Phase 3b / Phase 4 不需後續
    if re.search(r"Phase\s*(?:3b|4)|Phase3b|Phase4", title, re.IGNORECASE):
        return True, [], True

    # 檢查豁免條件：body 中有「不需後續」聲明
    if _has_no_followup_declaration(body):
        return True, [], False

    # 現在開始檢查是否有後續任務
    # 優先級 1：children 中有 IMP/ADJ 類型
    if _has_impl_or_adj_child(ticket, version):
        return True, [], False

    # 優先級 2：spawned_tickets 中有後續任務
    if _has_followup_in_spawned(ticket):
        return True, [], False

    # 優先級 3：同任務鏈中有序號更大的 Ticket
    if _has_followup_in_chain(ticket_id, version):
        return True, [], False

    # 無後續任務 → 失敗
    warnings = [
        f"[後續任務銜接] {ticket_type} 類型任務應有後續行動 Ticket，"
        f"但未在 children、spawned_tickets 或同任務鏈中找到。"
        f"建議檢查是否遺漏後續任務或在 Ticket body 中說明不需後續的理由。"
    ]

    return False, warnings, False


# ============================================================
# 主函式
# ============================================================

def run_audit(ticket_id: str, version: Optional[str] = None) -> AuditReport:
    """
    執行完整驗收檢查

    五步驟：
    1. 結構完整性檢查
    2. 子任務完成狀態檢查
    3. 執行日誌完整性檢查
    4. 驗收條件一致性檢查
    5. 後續任務銜接檢查

    Args:
        ticket_id: Ticket ID
        version: 版本號（若為 None 則自動偵測）

    Returns:
        AuditReport: 驗收報告

    Raises:
        ValueError: 若找不到 Ticket 檔案
    """
    # 解析版本號
    if version is None:
        try:
            version = resolve_version(None)
        except ValueError as e:
            raise ValueError(f"無法解析版本號：{e}")

    # 載入 Ticket
    ticket = load_ticket(version, ticket_id)
    if not ticket:
        raise ValueError(f"找不到 Ticket：{ticket_id}")

    # 建立報告
    report = AuditReport(
        ticket_id=ticket_id,
        title=ticket.get("title", "N/A"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # 載入原始檔案以取得 body
    ticket_path = None
    try:
        from .paths import get_ticket_path
        ticket_path = get_ticket_path(version, ticket_id)
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()
        _, body = parse_frontmatter(content)
    except Exception:
        body = ""

    # Step 1: 結構完整性檢查
    struct_passed, struct_issues = validate_structure(ticket)
    report.add_step(AuditStep(
        name="結構完整性檢查",
        passed=struct_passed,
        issues=struct_issues
    ))

    # Step 2: 子任務完成狀態檢查
    children_passed, children_issues, children_skipped = validate_children_completed(ticket, version)
    report.add_step(AuditStep(
        name="子任務完成狀態檢查",
        passed=children_passed,
        issues=children_issues,
        skipped=children_skipped
    ))

    # Step 3: 執行日誌完整性檢查
    log_passed, log_issues = validate_execution_log_completeness(body)
    report.add_step(AuditStep(
        name="執行日誌完整性檢查",
        passed=log_passed,
        issues=log_issues
    ))

    # Step 4: 驗收條件一致性檢查（Bug 2 修正）
    # 從 body 中提取 Solution 和 Test Results 區段
    # 使用 lookahead (?=^##\s+[^#]|\Z) 確保只在 ## 後跟非 # 時截斷，允許 ### 子標題
    solution_match = re.search(r"^(?:##|###)\s+Solution\s*$(.*?)(?=^##\s+[^#]|\Z)", body, re.MULTILINE | re.DOTALL)
    test_results_match = re.search(r"^(?:##|###)\s+Test Results\s*$(.*?)(?=^##\s+[^#]|\Z)", body, re.MULTILINE | re.DOTALL)

    solution_text = solution_match.group(1).strip() if solution_match else ""
    test_results_text = test_results_match.group(1).strip() if test_results_match else ""

    acceptance = ticket.get("acceptance", [])
    consistency_passed, consistency_warnings = validate_acceptance_consistency(
        acceptance,
        solution_text,
        test_results_text
    )
    report.add_step(AuditStep(
        name="驗收條件一致性檢查",
        passed=consistency_passed,
        warnings=consistency_warnings
    ))

    # Step 4.5: 含糊驗收條件偵測
    vague_warnings = detect_vague_acceptance(acceptance)
    report.add_step(AuditStep(
        name="含糊驗收條件偵測",
        passed=len(vague_warnings) == 0,
        warnings=vague_warnings
    ))

    # Step 5: 後續任務銜接檢查
    followup_passed, followup_warnings, followup_skipped = validate_followup_tasks(
        ticket,
        version,
        body
    )
    report.add_step(AuditStep(
        name="後續任務銜接檢查",
        passed=followup_passed,
        warnings=followup_warnings,
        skipped=followup_skipped
    ))

    # 判定整體結果
    # 規則：任一 step 的 passed=False → overall FAIL
    #      有 warnings 但無 FAIL → PASS_WITH_WARNINGS
    failed_steps = [s for s in report.steps if not s.passed and not s.skipped]
    report.overall_passed = len(failed_steps) == 0

    return report


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
