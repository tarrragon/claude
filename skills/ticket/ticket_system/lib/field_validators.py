"""建票參數的欄位合法性驗證。

建票前需確認多類欄位的形態與所指對象是否成立：where.files 的路徑 token 形態、
blockedBy 所引用的 ticket 是否存在且未完成、source_ticket 是否存在、
decision_tree 三參數是否齊備並可組成 decision_tree_path。這些檢查共通的性質是
**在任何持久化動作之前執行**——驗證失敗即中止建票，不留下半成品。

自 commands/create.py 抽出（0.2.1-W3-834 分群結論第 C+D 群）：where 驗證與關聯欄位
驗證合併為單一模組，因兩者皆為「建票前的欄位合法性檢查」，分成兩個模組會讓呼叫端
import 兩次同性質函式。
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

from ticket_system.lib.command_lifecycle_messages import CreateMessages
from ticket_system.lib.constants import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    WHEN_TICKET_REF_RE,
)
from ticket_system.lib.messages import (
    ErrorEnvelope,
    format_error,
    format_warning,
)
from ticket_system.lib.ticket_loader import list_tickets, load_ticket
from ticket_system.lib.ticket_validator import (
    extract_version_from_ticket_id,
    validate_blocked_by,
    validate_ticket_id,
)


def validate_blocked_by_references(
    version: str,
    ticket_id: str,
    blocked_by: Optional[List[str]],
) -> bool:
    """
    驗證 blockedBy 欄位的存在性和循環依賴。

    執行兩個驗證：
    1. 存在性檢查：所有 blockedBy 中的 Ticket ID 必須存在
    2. 循環依賴檢測：設定 blockedBy 不應產生循環依賴

    Args:
        version: Ticket 版本號
        ticket_id: 當前要建立的 Ticket ID
        blocked_by: blockedBy 欄位清單（可為 None）

    Returns:
        bool: True 表示驗證通過，False 表示有錯誤（已輸出錯誤訊息）
    """
    # Guard Clause：無 blockedBy 欄位
    if not blocked_by:
        return True

    # 驗證 1：blockedBy 存在性檢查
    for bid in blocked_by:
        blocked_ticket = load_ticket(version, bid)
        if blocked_ticket is None:
            print(format_error(ErrorEnvelope(
                component="create",
                action="validate_blocked_by",
                errno="BLOCKED_BY_NOT_FOUND",
                hint=f"找不到依賴的 Ticket: {bid}（請確認 ID 正確且已建立）",
            )))
            return False

    # 驗證 2：blockedBy 循環依賴檢測
    all_tickets = list_tickets(version)
    valid, cycle_msg, cycle_path = validate_blocked_by(
        ticket_id,
        blocked_by,
        all_tickets
    )
    if not valid and cycle_msg:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_blocked_by",
            errno="BLOCKED_BY_CYCLE",
            hint=cycle_msg,
        )))
        return False

    return True


def check_when_blocked_by_consistency(
    when: Optional[str],
    blocked_by: Optional[List[str]],
) -> None:
    """檢查 when 欄位提及的 ticket 引用是否已同步進 blockedBy（僅警告，不阻擋）。

    when 欄位若命中短格式 ticket 引用（如「W3-<序號>」）但 blockedBy 為空，
    代表此依賴未進入結構化欄位，dashboard/runqueue 的 ready 判定會忽略此依賴
    恆為真。僅發 WARNING：when 句型含方向性語彙（「先於」「協調」）或顯性
    不阻塞宣告（「即刻可執行」）時依賴方向可能與 blockedBy 相反，不可機械
    阻擋建票（2026-08-20）。

    Args:
        when: when 欄位原始字串（可為 None）
        blocked_by: blockedBy 欄位清單（可為 None）
    """
    if blocked_by:
        return
    if not when:
        return

    matches = WHEN_TICKET_REF_RE.findall(when)
    if not matches:
        return

    deduped = list(dict.fromkeys(matches))  # 去重且保留出現順序
    # 敘述位置用頓號（人類閱讀）；指令範例位置用空格（set-blocked-by 的
    # value 為單一 positional，要求空格分隔多個 ID，見 `set-blocked-by --help`）
    print(format_warning(
        CreateMessages.WHEN_BLOCKED_BY_INCONSISTENT_WARNING,
        ref_ids_display="、".join(deduped),
        ref_ids_cli=" ".join(deduped),
    ))


def validate_decision_tree_params(
    entry: Optional[str],
    decision: Optional[str],
    rationale: Optional[str],
) -> bool:
    """驗證 decision_tree 參數值的基本正確性。

    檢查內容：
    1. 無空字串值

    Args:
        entry: entry_point 參數值
        decision: final_decision 參數值
        rationale: rationale 參數值

    Returns:
        True 如果驗證通過，False 如果有空字串或其他問題
    """
    params = [(entry, "entry_point"), (decision, "final_decision"), (rationale, "rationale")]
    for value, name in params:
        if value == "":  # 空字串值
            print(format_error(ErrorEnvelope(
                component="create",
                action="validate_decision_tree",
                errno="DECISION_TREE_EMPTY_VALUE",
                hint=f"欄位 {name} 不可為空字串",
            )))
            return False
    return True

def build_decision_tree_path(
    entry: Optional[str],
    decision: Optional[str],
    rationale: Optional[str],
    is_child: bool,
    ticket_type: str,
) -> Optional[Dict[str, str]]:
    """驗證並構建 decision_tree_path 字典。

    邏輯：
    1. 豁免條件：子任務（is_child=True）或 DOC 類型
    2. 豁免時無參數 → 返回 None
    3. 豁免時有完整參數 → 返回字典（驗證後）
    4. 豁免時部分參數 → raise ValueError（拒絕）
    5. 非豁免時無參數 → 返回 None（不提前退出，交 _validate_create_checklist
       與其他必填欄位一次列全，W1-029 A2 同手法）
    6. 非豁免時有完整參數 → 返回字典（驗證後）
    7. 非豁免時部分參數 → raise ValueError（拒絕，保留參數級精確 hint）

    Args:
        entry: --decision-tree-entry 參數值
        decision: --decision-tree-decision 參數值
        rationale: --decision-tree-rationale 參數值
        is_child: 是否為子任務（args.parent 非空）
        ticket_type: Ticket 類型（args.type）

    Returns:
        - Dict[str, str]：包含 entry_point, final_decision, rationale 三個鍵
        - None：豁免且無參數

    Raises:
        ValueError: 驗證失敗（參數不完整或其他問題）
    """
    # 判斷是否豁免
    is_exempted = is_child or ticket_type == "DOC"

    # 計算提供的參數個數
    params = [entry, decision, rationale]
    provided_count = sum(1 for p in params if p is not None)

    # 使用 early return 簡化邏輯
    if provided_count == 0:
        # 無參數：豁免或非豁免皆 return None，不在此提前退出。
        # 非豁免全缺交給 _validate_create_checklist 的 decision_tree_path
        # 完整性檢查，與 when/who/how_strategy 等必填一次列全，避免跨階段
        # 分批報錯造成多輪試錯（W1-029，A2 同手法，對齊本檔 why 修復 796-799）。
        # PARTIAL（provided_count 1-2）與 EMPTY_VALUE 仍即時精確報錯，不退化。
        return None

    if provided_count == 3:
        # 完整三參數 - 驗證後返回字典
        if not validate_decision_tree_params(entry, decision, rationale):
            raise ValueError("決策樹參數驗證失敗")
        return {
            "entry_point": entry,
            "final_decision": decision,
            "rationale": rationale,
        }

    # 部分參數 - 全部拒絕
    if is_exempted:
        print(format_error(ErrorEnvelope(
            component="create",
            action="build_decision_tree",
            errno="EXEMPTED_PARTIAL_PARAMS",
            hint="子任務或 DOC 類型可豁免 decision-tree 參數，但若提供必須三參數齊備",
        )))
    else:
        missing_fields = []
        if entry is None:
            missing_fields.append("entry_point")
        if decision is None:
            missing_fields.append("final_decision")
        if rationale is None:
            missing_fields.append("rationale")
        print(format_error(ErrorEnvelope(
            component="create",
            action="build_decision_tree",
            errno="DECISION_TREE_MISSING_PARTIAL",
            hint=f"缺少欄位: {', '.join(missing_fields)}（三參數必須齊備）",
        )))
    raise ValueError("決策樹參數不完整")

def validate_where_file_token(token: str) -> tuple:
    """驗證單一 --where 路徑 token 是否為合法檔案路徑。

    防護 where.files 髒值：曾出現將 'key=value' 形式（如 src=.claude/x、
    layer=core）誤當路徑傳入 --where，髒值寫進 where.files 後致下游路徑
    分類器誤判（含前綴的 token 被當非框架路徑），級聯成派發誤診。

    判定規則：取路徑「第一段」（首個 '/' 之前的字串），若其中含 '='，
    視為 key=value 前綴髒值並 reject。'=' 出現在第一段之後（路徑中段或
    檔名）屬合法檔名字元，放行。空字串由上游過濾，此處視為合法。

    Args:
        token: 單一路徑 token

    Returns:
        (is_valid, hint) tuple：
        - is_valid: True 表示合法路徑；False 表示髒值
        - hint: 髒值時的修正提示（含剝除前綴後的建議路徑）；合法時為空字串
    """
    if not token:
        return True, ""

    first_segment = token.split("/", 1)[0]
    if "=" not in first_segment:
        return True, ""

    # 第一段含 '='：視為 key=value 前綴髒值，提供剝除前綴的修正建議
    stripped = token.split("=", 1)[1]
    hint = (
        f"路徑 token 含非路徑前綴（'='）於首段: '{token}'。"
        f"請改用純路徑，例如剝除前綴後的 '{stripped}'"
    )
    return False, hint

def validate_where_files(tokens: List[str]) -> List[str]:
    """批次驗證 --where 路徑 token，收集所有髒值錯誤訊息。

    Args:
        tokens: 已 strip 的路徑 token 列表

    Returns:
        錯誤訊息列表（每個髒值 token 一條）；全部合法時回空 list
    """
    errors: List[str] = []
    for token in tokens:
        is_valid, hint = validate_where_file_token(token)
        if not is_valid:
            errors.append(hint)
    return errors


# 讀取型建議預設的 ticket type（ANA/DOC 建票時不知會碰哪些檔案而先宣告目錄，
# 屬合理場景，優先建議加 ::read 而非改精確路徑；其餘型別優先建議改精確路徑）
_READ_SUGGESTED_TYPES = frozenset({"ANA", "DOC"})


def directory_declaration_warnings(
    tokens: List[str], ticket_type: Optional[str] = None
) -> List[str]:
    """批次檢查 where.files token 是否為目錄級宣告，回傳 WARNING 訊息清單
    （PC-BAL-040：create / set-where 對目錄級宣告發 WARNING，非硬擋——建票
    時檔案未必可知；`ticket track dispatch` 對無 `::read` 的目錄級寫入宣告
    才硬擋，見 track_dispatch.py）。

    token 已帶 `::read` 標記者不觸發 WARNING（唯讀宣告本就不會造成寫入衝突，
    是本規則要豁免的合法用法，非漏檢）。

    Args:
        tokens: 已 strip 的 where.files token 清單（未剝除意圖標記）
        ticket_type: 票類型（ANA/DOC 預設建議加 ::read，其餘建議改精確路徑）

    Returns:
        WARNING 訊息清單（每個目錄級宣告一條）；全部合法或皆為 ::read 時回空 list
    """
    from ticket_system.lib.file_conflict import is_directory_declaration, parse_file_intent

    warnings: List[str] = []
    suggest_read = ticket_type in _READ_SUGGESTED_TYPES
    for token in tokens:
        path, intent = parse_file_intent(token)
        if intent == "read":
            continue
        if not is_directory_declaration(path):
            continue
        stripped = path.rstrip("/")
        template = (
            CreateMessages.DIRECTORY_DECLARATION_WARNING_READ_SUGGESTED
            if suggest_read
            else CreateMessages.DIRECTORY_DECLARATION_WARNING
        )
        warnings.append(format_warning(template, path=path, stripped=stripped))
    return warnings

def missing_where_paths(project_root: Path, tokens: List[str]) -> List[str]:
    """回傳 where.files token 清單中，在 project_root 下不存在的路徑清單。

    純存在性檢查，不做形態或語意判斷（是否為新建語意、是否為目錄級宣告等
    交由呼叫端判斷）。輸入 token 允許帶 `::read` / `::write` 意圖標記，本函式
    以 `parse_file_intent` 剝除後再檢查存在性；回傳值保留原始 token 字面值，
    供呼叫端原樣顯示於 WARNING。供 create / set-where / dispatch-readiness
    三處防線共用。

    Args:
        project_root: 專案根目錄（呼叫端以 `ticket_system.lib.paths.get_project_root`
            解析後傳入，本函式不自行解析，維持純函式可測性）
        tokens: 待檢查的 where.files token 清單（已 strip，可含 `::read` 等標記）

    Returns:
        不存在的路徑 token 清單（保留原始字面值與輸入順序）；全部存在時回空 list
    """
    from ticket_system.lib.file_conflict import parse_file_intent

    missing: List[str] = []
    for token in tokens:
        if not token:
            continue
        path, _intent = parse_file_intent(token)
        if not (project_root / path).exists():
            missing.append(token)
    return missing


def validate_source_ticket_arg(args: argparse.Namespace) -> bool:
    """Step 1.5：--source-ticket 參數前置驗證（PC-073）。

    檢查順序（fail-fast，三視角共識）：
    1. 互斥檢查：--source-ticket 與 --parent 不可同用
    2. ID 格式檢查：沿用 validate_ticket_id
    3. 存在性檢查：載入 source ticket
    4. 狀態警告：completed / in_progress 皆允許但顯示 WARNING（allow + warning，
       不阻擋）。in_progress 分支在建票當下就提示改掛上游，取代原本依賴 PM
       記得告知的文件條款（parallel-dispatch.md）

    所有錯誤路徑在持久化前結束；fail-fast 順序一致。

    Args:
        args: 命令行參數（含 source_ticket 和 parent）

    Returns:
        bool: True 表示驗證通過（或未提供 --source-ticket）；False 表示應 early return 1
    """
    # Guard Clause：未提供 --source-ticket 則跳過
    if not args.source_ticket:
        return True

    # 子步驟 1：互斥檢查（最先；測試 B4 的 ordering 斷言依此成立）
    if args.parent:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_PARENT_MUTUALLY_EXCLUSIVE",
            hint="--source-ticket 與 --parent 不可同時使用（前者為衍生關係，後者為父子關係）",
        )))
        return False

    # 子步驟 2：ID 格式檢查（沿用 validate_ticket_id）
    if not validate_ticket_id(args.source_ticket):
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="INVALID_TICKET_ID_FORMAT",
            hint=f"--source-ticket ID 格式無效: {args.source_ticket}",
        )))
        return False

    # 子步驟 3：存在性檢查
    source_version = extract_version_from_ticket_id(args.source_ticket)
    if source_version is None:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_TICKET_NOT_FOUND",
            hint=f"無法從 ID 推斷版本: {args.source_ticket}",
        )))
        return False
    source_ticket = load_ticket(source_version, args.source_ticket)
    if source_ticket is None:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_TICKET_NOT_FOUND",
            hint=f"找不到 source ticket: {args.source_ticket}（請確認 ID 正確且檔案存在）",
        )))
        return False

    # 子步驟 4：狀態警告（allow + warning；不阻擋）
    if source_ticket.get("status") == STATUS_COMPLETED:
        print(format_warning(
            CreateMessages.SOURCE_TICKET_COMPLETED_WARN,
            source_id=args.source_ticket,
        ))
        # 非 ANA type 無額外警告（pepper §8 決策：消除特例）
    elif source_ticket.get("status") == STATUS_IN_PROGRESS:
        parent_id = source_ticket.get("parent_id")
        parent_hint = f"（--parent {parent_id}）" if parent_id else ""
        print(format_warning(
            CreateMessages.SOURCE_TICKET_IN_PROGRESS_WARN,
            source_id=args.source_ticket,
            parent_hint=parent_hint,
        ))

    return True


def validate_discovered_during_arg(args: argparse.Namespace) -> bool:
    """--discovered-during 參數前置驗證：與 --source-ticket 互斥。

    --discovered-during 標記發現衍生（執行中撞到跨主題問題，記錄脈絡但
    不繼承主題），與 --source-ticket 的規劃衍生語意（繼承上游主題）互相
    矛盾，兩者同時指定時直接拒絕。

    只做互斥檢查，不做 ID 格式/存在性檢查：與 --source-ticket 不同，
    discovered_during 只作血緣記錄，不驅動 update_source_spawned_tickets
    等後續持久化步驟，無需同等的驗證深度。

    Args:
        args: 命令行參數（含 discovered_during 和 source_ticket）

    Returns:
        bool: True 表示驗證通過（或未提供 --discovered-during）；
              False 表示應 early return 1
    """
    if not getattr(args, "discovered_during", None):
        return True

    if args.source_ticket:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_discovered_during",
            errno="DISCOVERED_DURING_SOURCE_MUTUALLY_EXCLUSIVE",
            hint=(
                "--discovered-during 與 --source-ticket 不可同時使用"
                "（前者為發現衍生，記錄脈絡但不繼承主題；後者為規劃衍生，"
                "繼承上游主題）"
            ),
        )))
        return False

    return True
