"""
5W1H 欄位操作模組

責任：處理 Ticket 的 5W1H 欄位（who, what, when, where, why, how）
- 通用欄位讀取：execute_get_field
- 通用欄位設定：execute_set_field
- 12 個欄位包裝器（向後相容）

設計原則：DRY（不重複原則）
- 原始 track.py 有 12 個重複函式（95% 重複代碼）
- 本模組提供 2 個通用函式，減少代碼重複率至 5%
- 使用包裝層維持向後相容的 API
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from ticket_system.lib import ticket_loader
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    format_error,
    format_info,
    format_warning,
)
from ticket_system.lib.command_lifecycle_messages import (
    CreateMessages,
    FieldsMessages,
)
from ticket_system.lib.ticket_loader import get_ticket_path
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)


DICT_FIELD_SUBKEY: Dict[str, str] = {
    "who": "current",
    "where": "layer",
    "how": "strategy",
}
"""dict 型欄位與主要子欄位的對應表（W10-086 修復）。

Why: set-who/set-where/set-how 應僅更新子欄位（current/layer/strategy），
保留 dict 其他 key（history/files/task_type）；原實作直接覆寫整個 dict 為 string，
導致後續 dict.get 操作 AttributeError。

How to apply: execute_set_field 依此表分流 dict 與 string 欄位的寫入邏輯。
"""


_DICT_FIELD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "who": {"current": "pending", "history": {}},
    "where": {"layer": "待定義", "files": []},
    "how": {"task_type": "Implementation", "strategy": "待定義"},
}


def _build_dict_field(field_name: str, subkey: str, new_value: Any) -> Dict[str, Any]:
    """為降級（原值已被壓扁為 string）/ 初始化場景重建完整 dict 結構。"""
    result = {k: v for k, v in _DICT_FIELD_DEFAULTS[field_name].items()}
    result[subkey] = new_value
    return result


def _has_extension(item: str) -> bool:
    """最後一段是否帶副檔名。

    點號位於段首不算（`framework/.claude` 的 `.claude` 是隱藏目錄名而非
    `claude` 的副檔名），否則所有 dotfile 形態的層級描述都會被誤判為路徑。
    """
    last = item.rsplit("/", 1)[-1]
    return "." in last[1:]


def _exists_in_repo(item: str) -> bool:
    """項目是否為 repo 內實際存在的檔案或目錄；解析失敗一律回 False。"""
    try:
        from ticket_system.lib.paths import get_project_root

        return (get_project_root() / item).exists()
    except Exception:
        # 專案根解析失敗不得使判定崩潰——退回字面啟發式即可
        return False


def _looks_like_path(item: str) -> bool:
    """單一項目是否為檔案系統路徑（非架構層級描述）。"""
    if any(ch.isspace() for ch in item) or "/" not in item:
        return False
    return item.endswith("/") or _has_extension(item) or _exists_in_repo(item)


def _parse_where_path_entries(value: Any) -> Optional[list]:
    """解析 set-where 輸入值為路徑清單；非路徑型輸入回傳 None（W1-078 修復）。

    Why: agent-dispatch-validation-hook 以 where.files 為 scope source of truth
    （L3 純 .claude/ 覆蓋），set-where 僅寫 where.layer 會讓 files 保留 stale 值，
    導致 dispatch 誤擋。

    路徑判定要求每個逗號分隔項目同時滿足三項：不含空白、含 `/`、且看起來
    像檔案系統路徑（副檔名 / 尾隨 `/` / 在 repo 內實際存在其一）。

    - 全為路徑（如 ".claude/hooks/,src/core/x.js"）→ 回傳清單，同步 where.files
    - 任一項不符（如 "Domain Layer"、"Presentation/UI"、"N/A"）→ 回傳 None，
      僅更新 layer 描述

    **為何只看「含 /」不夠**（2026-08-11 修正）：架構層級描述本身就可能含
    斜線——`Presentation/UI`、`Domain/Application layer`、`N/A`、
    `framework/.claude` 皆是。舊判定把它們當路徑，結果是 layer 完全寫不進去、
    描述文字反而進了 where.files，正是本函式要避免的 dispatch hook
    has_other=True 污染，只是換個方向發生。

    存在性檢查用於補副檔名與尾隨 `/` 都沒有的目錄路徑（如 `.claude/hooks`）：
    這類與 `Presentation/UI` 在字面上無法區分，只能問檔案系統。查不到時
    退回描述型，代價是使用者需補尾隨 `/`——比誤把層級描述塞進 files 輕。
    """
    entries = [item.strip() for item in str(value).split(",") if item.strip()]
    if entries and all(_looks_like_path(item) for item in entries):
        return entries
    return None


def _sync_where_files(where_dict: Dict[str, Any], new_value: Any) -> Optional[list]:
    """路徑型 set-where 輸入同步寫入 where.files；回傳同步後清單或 None（未同步）。"""
    path_entries = _parse_where_path_entries(new_value)
    if path_entries is not None:
        where_dict["files"] = path_entries
    return path_entries


def _get_str_arg(args: argparse.Namespace, name: str) -> Optional[str]:
    """安全讀取可選 CLI flag 的字串值（W1-009：子欄位寫入路徑）。

    僅接受字串型別；None 與非字串（含測試替身 Mock 未顯式設定時自動生成的屬性）
    一律視為未提供，避免誤判觸發子欄位寫入分支（讓既有以 Mock() 建構 args 的
    測試無需逐一補設新 flag 屬性仍可通過）。
    """
    value = getattr(args, name, None)
    return value if isinstance(value, str) else None


def _parse_comma_list(value: str) -> list:
    """將逗號分隔字串解析為去除前後空白後的清單（供 --files 明確輸入使用）。"""
    return [item.strip() for item in value.split(",") if item.strip()]


def _execute_set_dict_subfields(
    args: argparse.Namespace,
    version: str,
    field_name: str,
    subfields: Dict[str, Any],
) -> int:
    """設定 dict 型欄位（who/where/how）的個別子欄位（W1-009：補齊子欄位寫入路徑）。

    與 execute_set_field 的整體覆寫（位置參數 value）路徑互補：呼叫端偵測到至少一個
    子欄位 flag 被提供時才呼叫本函式。若 value 同時提供，先套用至 DICT_FIELD_SUBKEY
    定義的主要子欄位，subfields 隨後逐一覆寫（顯式 flag 優先於位置參數）。

    Args:
        subfields: 子欄位名稱 -> 使用者提供值，僅含已提供（非 None）的項目
    """
    value = getattr(args, "value", None)

    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        subkey = DICT_FIELD_SUBKEY[field_name]
        existing = ticket.get(field_name)
        working = dict(existing) if isinstance(existing, dict) else dict(_DICT_FIELD_DEFAULTS[field_name])

        applied: Dict[str, Any] = {}
        if value is not None:
            working[subkey] = value
            applied[subkey] = value
        for key, val in subfields.items():
            working[key] = val
            applied[key] = val

        ticket[field_name] = working
        ticket_type = ticket.get("type")

        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name=field_name))
    for key, val in applied.items():
        display = ", ".join(val) if isinstance(val, list) else val
        print(f"   {key}: {display}")

    # 目錄級 where.files 宣告 WARNING（PC-BAL-040）：--files 子欄位路徑不經過
    # execute_set_field 的 _sync_where_files 啟發式，需在此另行檢查。
    if field_name == "where" and "files" in applied:
        from ticket_system.lib.field_validators import (
            directory_declaration_warnings,
            missing_where_paths,
        )
        from ticket_system.lib.paths import get_project_root

        for warning in directory_declaration_warnings(applied["files"], ticket_type):
            print(warning)
        for missing in missing_where_paths(get_project_root(), applied["files"]):
            print(format_warning(CreateMessages.WHERE_PATH_NOT_FOUND_WARNING, path=missing))

        # where.files 範圍宣告變更 auto-commit：與 set-acceptance / append-log
        # 同保護等級，使範圍宣告調整可獨立於其他操作被稽核。
        import sys as _sys
        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), args.ticket_id, "where.files", operation="set-where",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[set-where] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[set-where] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )
    return 0


def execute_get_field(
    args: argparse.Namespace,
    version: str,
    field_name: Optional[str] = None,
) -> int:
    """
    通用欄位讀取函式

    支援讀取任意 Ticket 欄位（who, what, when, where, why, how 等）

    Args:
        args: 命令行參數
            - ticket_id: Ticket ID
            - field: 欄位名稱（可選，若無則使用 field_name 參數）
        version: 版本號
        field_name: 欄位名稱（若提供，優先於 args.field）

    Returns:
        int: 0 表示成功，1 表示失敗

    使用場景：
        - ticket track who <ticket-id>
        - ticket track what <ticket-id>
        - ticket track when <ticket-id>
        - ticket track where <ticket-id>
        - ticket track why <ticket-id>
        - ticket track how <ticket-id>
    """
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    # 決定欄位名稱（優先使用參數傳入，否則從 args 中取得）
    actual_field_name = field_name or getattr(args, "field", None)
    if not actual_field_name:
        print(format_error(ErrorMessages.MISSING_FIELD_NAME))
        return 1

    # 檢查欄位是否存在
    if actual_field_name not in ticket:
        print(format_error(ErrorMessages.FIELD_NOT_FOUND, ticket_id=args.ticket_id, field_name=actual_field_name))
        return 1

    # 取得欄位值
    value = ticket.get(actual_field_name, "?")

    # 格式化顯示
    if isinstance(value, dict):
        # 如果是字典，取得 'current' 欄位或直接顯示
        if "current" in value:
            display_value = value.get("current", "?")
        else:
            display_value = str(value)
    else:
        display_value = str(value) if value is not None else "?"

    print(f"{actual_field_name.capitalize()}{FieldsMessages.FIELD_VALUE_SEPARATOR}{display_value}")
    return 0


def execute_set_field(
    args: argparse.Namespace,
    version: str,
    field_name: Optional[str] = None,
) -> int:
    """
    通用欄位設定函式

    支援更新 5W1H 欄位（who, what, when, where, why, how）

    Args:
        args: 命令行參數
            - ticket_id: Ticket ID
            - value: 新欄位值
            - field: 欄位名稱（可選，若無則使用 field_name 參數）
        version: 版本號
        field_name: 欄位名稱（若提供，優先於 args.field）

    Returns:
        int: 0 表示成功，1 表示失敗

    使用場景：
        - ticket track set-who <ticket-id> <value>
        - ticket track set-what <ticket-id> <value>
        - ticket track set-when <ticket-id> <value>
        - ticket track set-where <ticket-id> <value>
        - ticket track set-why <ticket-id> <value>
        - ticket track set-how <ticket-id> <value>
    """
    # W14-045: file_lock 包圍 load → modify → save，消除 logical race。
    # Lock target 用 get_ticket_path 計算路徑（不依賴 load 後的 _path）。
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        # 決定欄位名稱（優先使用參數傳入，否則從 args 中取得）
        actual_field_name = field_name or getattr(args, "field", None)
        if not actual_field_name:
            print(format_error(ErrorMessages.MISSING_FIELD_NAME))
            return 1

        # 取得新值
        new_value = args.value

        # 更新欄位：dict 型欄位僅更新子欄位（W10-086 修復，防止壓扁 dict 為 string）
        synced_files: Optional[list] = None
        if actual_field_name in DICT_FIELD_SUBKEY:
            subkey = DICT_FIELD_SUBKEY[actual_field_name]
            existing = ticket.get(actual_field_name)
            if not isinstance(existing, dict):
                # 原值已被壓扁為 string：重建完整結構，主要子欄位先取預設值，
                # 是否寫入 new_value 由下方路徑型判定決定。
                existing = _build_dict_field(
                    actual_field_name, subkey, _DICT_FIELD_DEFAULTS[actual_field_name][subkey]
                )
            # W1-078 修復：set-where 路徑型輸入同步更新 where.files，
            # 維持 layer/files 一致（dispatch hook 消費契約）
            if actual_field_name == "where":
                synced_files = _sync_where_files(existing, new_value)
            # 路徑型輸入只餵 files，不寫 layer（2026-08-10 定案）：layer 語意是
            # 架構層級（Domain / Application / Infrastructure / Presentation），
            # 塞入逗號串接的檔案清單會使該欄位失去意義，且操作者不會察覺——CLI
            # 回報只顯示 files 已同步。既成代價：god_ticket_scale_checker 因
            # layer 已有誤填樣本而整個放棄層級跨度指標。要設定 layer 請用
            # --layer 子欄位旗標（execute_set_where 的子欄位路徑）。
            if synced_files is None:
                existing[subkey] = new_value
            ticket[actual_field_name] = existing
        else:
            ticket[actual_field_name] = new_value

        # 儲存
        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name=actual_field_name))
    if synced_files is None:
        print(f"   新值: {new_value}")
    else:
        # 路徑型輸入未寫 layer，印「新值」會讓操作者以為整個 where 被替換
        print("   where.layer 未變更（路徑型輸入只同步 files；需改 layer 請用 --layer）")
    if synced_files is not None:
        print(FieldsMessages.WHERE_FILES_SYNCED.format(count=len(synced_files)))
        for entry in synced_files:
            print(f"      - {entry}")
        # 目錄級 where.files 宣告 WARNING（PC-BAL-040）
        from ticket_system.lib.field_validators import (
            directory_declaration_warnings,
            missing_where_paths,
        )
        from ticket_system.lib.paths import get_project_root

        for warning in directory_declaration_warnings(synced_files, ticket.get("type")):
            print(warning)
        # where.files 路徑存在性 WARNING：set-where 路徑型輸入同上，僅警告不阻擋。
        for missing in missing_where_paths(get_project_root(), synced_files):
            print(format_warning(CreateMessages.WHERE_PATH_NOT_FOUND_WARNING, path=missing))

        # where.files 範圍宣告變更 auto-commit：與 --files 子欄位路徑
        # （_execute_set_dict_subfields）同保護等級，使範圍宣告調整可獨立於
        # 其他操作被稽核。
        import sys as _sys
        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), args.ticket_id, "where.files", operation="set-where",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[set-where] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[set-where] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )
    return 0


# ===========================
# 包裝層 - 向後相容 API
# ===========================
# 這些函式保持原有的 API，並委派給通用函式


def execute_get_who(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 who 欄位"""
    return execute_get_field(args, version, "who")


def execute_set_who(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 who 欄位（整體覆寫 value 或子欄位 --current，W1-009）。

    value 位置參數已改為可選（nargs='?'），使 --current 可獨立使用；
    兩者皆未提供時視為呼叫錯誤，避免 value=None 誤寫入 who.current。
    """
    current = _get_str_arg(args, "current")
    if current is not None:
        return _execute_set_dict_subfields(args, version, "who", {"current": current})
    if getattr(args, "value", None) is None:
        print(format_error(ErrorMessages.MISSING_FIELD_VALUE, ticket_id=args.ticket_id, field_name="who"))
        return 1
    return execute_set_field(args, version, "who")


def execute_get_what(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 what 欄位"""
    return execute_get_field(args, version, "what")


def execute_set_what(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 what 欄位"""
    return execute_set_field(args, version, "what")


def execute_get_title(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 title 欄位"""
    return execute_get_field(args, version, "title")


def execute_set_title(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 title 欄位（2026-08-18 新增）。

    title 與 what 是兩個獨立欄位，本函式刻意不連帶更新 what——量測 741 張票
    有 124 張（17%）兩者不同，模式為 title 作清單顯示用的短標籤、what 作含
    檔案清單與括號補充的完整敘述。同步兩者會抹平該分工。

    本命令補上的是 title 原本不存在的更新途徑：CLI 無設定命令、set-what 只改
    what、直接編輯 frontmatter 被 guard 阻擋，三者交集使 title 一旦寫錯即無法
    修復（PC-BAL-047）。清單類視圖（dashboard / runqueue）顯示的是 title，故
    過期的 title 會持續誤導接手者對票範圍的判斷。
    """
    return execute_set_field(args, version, "title")


def execute_get_when(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 when 欄位"""
    return execute_get_field(args, version, "when")


def execute_set_when(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 when 欄位"""
    return execute_set_field(args, version, "when")


def execute_get_where(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 where 欄位"""
    return execute_get_field(args, version, "where")


def execute_set_where(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 where 欄位（整體覆寫 value 或子欄位 --layer/--files，W1-009）。

    value 位置參數已改為可選（nargs='?'），使 --layer/--files 可獨立使用；
    三者皆未提供時視為呼叫錯誤，避免 value=None 誤寫入 where.layer。
    子欄位路徑不套用 value 專屬的路徑型輸入同步 where.files 啟發式（該啟發式
    僅服務位置參數場景的語意判定，--files 已是明確輸入，不需要再推斷）。

    2026-09-02 修復：value 與 --layer 同時提供、且未另帶 --files 時，
    先前 value（路徑清單）會被 _execute_set_dict_subfields 的通用子欄位覆寫
    邏輯吃掉——先寫入 layer 子欄位再被 --layer 覆寫，files 完全未同步，且
    CLI 無任何提示。此處補上：value 為路徑型輸入時同步寫入 where.files（與
    純 value、或 value + --files 情境的同步行為一致），--files 顯式提供時
    仍優先於 value 推斷（不變）。
    """
    layer = _get_str_arg(args, "layer")
    files_raw = _get_str_arg(args, "files")
    if layer is None and files_raw is None:
        if getattr(args, "value", None) is None:
            print(format_error(ErrorMessages.MISSING_FIELD_VALUE, ticket_id=args.ticket_id, field_name="where"))
            return 1
        return execute_set_field(args, version, "where")

    subfields: Dict[str, Any] = {}
    if layer is not None:
        subfields["layer"] = layer
    if files_raw is not None:
        subfields["files"] = _parse_comma_list(files_raw)
    elif getattr(args, "value", None) is not None:
        path_entries = _parse_where_path_entries(args.value)
        if path_entries is not None:
            subfields["files"] = path_entries
    return _execute_set_dict_subfields(args, version, "where", subfields)


def execute_get_why(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 why 欄位"""
    return execute_get_field(args, version, "why")


def execute_set_why(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 why 欄位"""
    return execute_set_field(args, version, "why")


def execute_get_how(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 how 欄位"""
    return execute_get_field(args, version, "how")


def execute_set_how(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 how 欄位（整體覆寫 value 或子欄位 --task-type/--strategy，W1-009）。

    value 位置參數已改為可選（nargs='?'），使 --task-type/--strategy 可獨立使用；
    三者皆未提供時視為呼叫錯誤，避免 value=None 誤寫入 how.strategy。
    """
    task_type = _get_str_arg(args, "task_type")
    strategy = _get_str_arg(args, "strategy")
    if task_type is None and strategy is None:
        if getattr(args, "value", None) is None:
            print(format_error(ErrorMessages.MISSING_FIELD_VALUE, ticket_id=args.ticket_id, field_name="how"))
            return 1
        return execute_set_field(args, version, "how")

    subfields: Dict[str, Any] = {}
    if task_type is not None:
        subfields["task_type"] = task_type
    if strategy is not None:
        subfields["strategy"] = strategy
    return _execute_set_dict_subfields(args, version, "how", subfields)


def execute_set_priority(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 priority 欄位"""
    return execute_set_field(args, version, "priority")


def execute_add_acceptance(args: argparse.Namespace, version: str) -> int:
    """追加驗收條件到 Ticket。

    與 set-acceptance 對齊三維度（原實作遺漏，實作於 fields.py 簡單欄位
    操作群，044 引入 require_in_progress 時未回頭涵蓋）：
    - identity guard：--as 申報對照 who.current（warn-only，未強制）
    - status guard：allow_pending=True（建票期例行修訂），completed/blocked/
      closed 需 --force
    - auto-commit：寫入後同 set-acceptance 保護等級
    """
    import sys as _sys
    from ticket_system.lib.identity_guard import check_identity
    deny = check_identity(
        version,
        args.ticket_id,
        getattr(args, "as_agent", None),
        command="add-acceptance",
    )
    if deny is not None:
        return deny

    # W14-045: file_lock 包圍 load → modify → save
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        force = bool(getattr(args, "force", False))
        ok, error_msg = require_in_progress(
            ticket,
            args.ticket_id,
            "add-acceptance",
            allow_completed=False,
            allow_pending=True,
            force=force,
        )
        if not ok:
            _sys.stderr.write(error_msg + "\n")
            return 2

        acceptance = ticket.get("acceptance") or []
        new_item = f"[ ] {args.value}"
        acceptance.append(new_item)
        ticket["acceptance"] = acceptance

        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

        # 與 set-acceptance 同保護等級的 auto-commit（path-limited + graceful
        # degrade）。
        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), args.ticket_id, "Acceptance Criteria",
                operation="add-acceptance",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[add-acceptance] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[add-acceptance] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="acceptance"))
    print(f"   新增: {new_item}")
    print(f"   目前共 {len(acceptance)} 項")
    return 0


def execute_remove_acceptance(args: argparse.Namespace, version: str) -> int:
    """移除驗收條件（按 index，從 1 開始）"""
    import sys

    # W14-045: file_lock 包圍 load → modify → save
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        acceptance = ticket.get("acceptance") or []
        index = args.index - 1

        if index < 0 or index >= len(acceptance):
            print(format_error(f"索引超出範圍：{args.index}（共 {len(acceptance)} 項）"), file=sys.stderr)
            return 1

        removed = acceptance.pop(index)
        ticket["acceptance"] = acceptance

        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="acceptance"))
    print(f"   移除: {removed}")
    print(f"   剩餘 {len(acceptance)} 項")
    return 0


def execute_add_spawned(args: argparse.Namespace, version: str) -> int:
    """追加 spawned_tickets 項目（支援多 ID，對齊 Unix 慣例）"""
    # W14-045: file_lock 包圍 load → modify → save
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        # args.value 為 list（nargs='+'），可能含 1 至多個 ID
        values = args.value if isinstance(args.value, list) else [args.value]

        spawned = ticket.get("spawned_tickets") or []
        added: list[str] = []
        skipped: list[str] = []
        for value in values:
            if value in spawned:
                skipped.append(value)
                continue
            spawned.append(value)
            added.append(value)

        ticket["spawned_tickets"] = spawned

        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="spawned_tickets"))
    if added:
        print(f"   新增: {', '.join(added)}")
    if skipped:
        print(f"   已存在略過: {', '.join(skipped)}")
    print(f"   目前共 {len(spawned)} 項")
    return 0


def execute_set_decision_tree(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 decision_tree_path 欄位（3 個子欄位）"""
    # W14-045: file_lock 包圍 load → modify → save
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 1

        dt = ticket.get("decision_tree_path") or {}
        if args.entry:
            dt["entry_point"] = args.entry
        if args.decision:
            dt["final_decision"] = args.decision
        if args.rationale:
            dt["rationale"] = args.rationale

        ticket["decision_tree_path"] = dt

        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="decision_tree_path"))
    for key, val in dt.items():
        print(f"   {key}: {val}")
    return 0
