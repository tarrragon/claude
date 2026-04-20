"""
ticket track set-acceptance 子命令

提供明確語意的驗收條件勾選/取消勾選介面，取代直接 Edit frontmatter 的路徑。

支援格式：
  ticket track set-acceptance <id> --check <index> [<index>...]
  ticket track set-acceptance <id> --uncheck <index> [<index>...]
  ticket track set-acceptance <id> --all-check
  ticket track set-acceptance <id> --all-uncheck

與既有 check-acceptance 差異：
- --check / --uncheck 明確雙向語意
- 支援多個 index 一次操作
- --all-check / --all-uncheck 取代 --all [--uncheck] 組合
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-acceptance")
    sys.exit(1)


import argparse

from ticket_system.lib.ticket_loader import save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    format_error,
)


# 互斥選項群組
_MODE_FLAGS = ("check", "uncheck", "all_check", "all_uncheck")


def _pick_mode(args: argparse.Namespace) -> tuple[str | None, str]:
    """從 args 中選出唯一啟用的模式。

    Returns:
        (mode, error_message)。mode 為 "check"/"uncheck"/"all_check"/"all_uncheck" 其一；
        錯誤時 mode=None，error_message 有值。
    """
    enabled = [flag for flag in _MODE_FLAGS if getattr(args, flag, None)]
    if not enabled:
        return None, "必須指定 --check/--uncheck/--all-check/--all-uncheck 其一"
    if len(enabled) > 1:
        flags_display = ", ".join("--" + f.replace("_", "-") for f in enabled)
        return None, f"選項互斥：{flags_display} 不能同時使用"
    return enabled[0], ""


def _apply_check(item: str) -> tuple[str, bool]:
    """勾選單一項目，回傳 (新項目, 是否變更)。"""
    if item.startswith("[x]"):
        return item, False
    if item.startswith("[ ]"):
        return item.replace("[ ]", "[x]", 1), True
    return f"[x] {item}", True


def _apply_uncheck(item: str) -> tuple[str, bool]:
    """取消勾選單一項目，回傳 (新項目, 是否變更)。"""
    if item.startswith("[x]"):
        return item.replace("[x]", "[ ]", 1), True
    return item, False


def _parse_indices(
    index_args: list[str], acceptance_list: list[str]
) -> tuple[list[int], str]:
    """解析並驗證多個 index 參數（1-based 整數）。

    Returns:
        (1-based index 清單, error_message)。錯誤時 clean=[]，error_message 有值。
    """
    total = len(acceptance_list)
    parsed: list[int] = []
    for raw in index_args:
        try:
            n = int(raw)
        except ValueError:
            return [], f"index 必須為整數：'{raw}'"
        if n < 1 or n > total:
            return [], f"index 超出範圍：{n}（有效範圍 1-{total}）"
        if n not in parsed:
            parsed.append(n)
    return parsed, ""


def _apply_mode_to_list(
    acceptance_list: list[str], mode: str, indices: list[int]
) -> tuple[int, int]:
    """依模式更新 acceptance list（原地修改），回傳 (變更數, 總數)。"""
    total = len(acceptance_list)
    changed = 0

    if mode == "all_check":
        target_range = range(1, total + 1)
        op = _apply_check
    elif mode == "all_uncheck":
        target_range = range(1, total + 1)
        op = _apply_uncheck
    elif mode == "check":
        target_range = indices
        op = _apply_check
    else:  # uncheck
        target_range = indices
        op = _apply_uncheck

    for idx in target_range:
        new_item, did_change = op(acceptance_list[idx - 1])
        if did_change:
            acceptance_list[idx - 1] = new_item
            changed += 1

    return changed, total


def execute_set_acceptance(args: argparse.Namespace, version: str) -> int:
    """執行 set-acceptance 命令。"""
    mode, err = _pick_mode(args)
    if mode is None:
        print(format_error(ErrorMessages.INVALID_OPERATION, operation=err) if hasattr(ErrorMessages, "INVALID_OPERATION") else f"[ERROR] {err}")
        return 1

    ticket, load_err = load_and_validate_ticket(version, args.ticket_id)
    if load_err:
        return 1

    acceptance_list = ticket.get("acceptance", [])
    if not acceptance_list:
        print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 解析 index（僅 check/uncheck 需要）
    indices: list[int] = []
    if mode in ("check", "uncheck"):
        raw_indices = getattr(args, mode, None) or []
        if not raw_indices:
            print(f"[ERROR] --{mode.replace('_', '-')} 需要至少一個 index")
            return 1
        indices, perr = _parse_indices(raw_indices, acceptance_list)
        if perr:
            print(f"[ERROR] {perr}")
            return 1

    changed, total = _apply_mode_to_list(acceptance_list, mode, indices)

    ticket["acceptance"] = acceptance_list
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    action = "勾選" if mode in ("check", "all_check") else "取消勾選"
    scope = f"全部 ({changed}/{total})" if mode.startswith("all_") else f"index {indices}"
    print(f"[INFO] {args.ticket_id} {action} {scope}：變更 {changed} 項")
    return 0
