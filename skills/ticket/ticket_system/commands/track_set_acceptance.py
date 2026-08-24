"""
ticket track set-acceptance 子命令

提供明確語意的驗收條件勾選/取消勾選介面，取代直接 Edit frontmatter 的路徑。

支援格式：
  ticket track set-acceptance <id> --check <index> [<index>...]
  ticket track set-acceptance <id> --uncheck <index> [<index>...]
  ticket track set-acceptance <id> --all-check
  ticket track set-acceptance <id> --all-uncheck
  ticket track set-acceptance <id> --add <text> [<text>...]
  ticket track set-acceptance <id> --edit <index> <text> [--edit <index> <text>...]
  ticket track set-acceptance <id> --remove <index> [<index>...] [--force]

與既有 check-acceptance 差異：
- --check / --uncheck 明確雙向語意
- 支援多個 index 一次操作
- --all-check / --all-uncheck 取代 --all [--uncheck] 組合

建票後修訂能力（因應建票後範圍變化需修訂 acceptance，但 acceptance-gate
只檢查 frontmatter 勾選狀態，body 補充要求不進入驗收層而新增）：
- --add 追加條目，預設未勾選（`[ ] <text>`）
- --edit 覆寫指定 index 的條目文字，保留原勾選狀態不變
- --remove 移除指定 index，其餘條目的勾選狀態依原內容正確對位（不漂移）；
  移除已勾選（`[x]`）條目須加 --force，防止事後抹除驗收證據
- 三者與 check/uncheck 系列共用 require_in_progress 前置檢查：
  completed 票的修訂同樣需要 --force（防止事後改條件使驗收記錄失真）
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-acceptance")
    sys.exit(1)


import argparse
from pathlib import Path

from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.ticket_loader import get_ticket_path, save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    format_error,
)


# 互斥選項群組
_MODE_FLAGS = ("check", "uncheck", "all_check", "all_uncheck", "add", "edit", "remove")


def _flatten_values(raw: object) -> list[str]:
    """把 nargs="+" 搭 action="append" 的巢狀結果攤平為單層清單。

    argparse 對 `--add A B --add C` 產出 `[["A", "B"], ["C"]]`。同時容忍已是
    單層的輸入，使直接建構 Namespace 的呼叫端（測試、其他命令委派）不需
    改寫。
    """
    if not raw:
        return []
    flat: list[str] = []
    for item in raw:
        if isinstance(item, (list, tuple)):
            flat.extend(str(x) for x in item)
        else:
            flat.append(str(item))
    return flat


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


def _apply_add(acceptance_list: list[str], texts: list[str]) -> int:
    """追加新條目，預設未勾選（`[ ] <text>`）。回傳新增數量。"""
    for text in texts:
        acceptance_list.append(f"[ ] {text}")
    return len(texts)


def _parse_edits(
    raw_edits: list[list[str]], acceptance_list: list[str]
) -> tuple[list[tuple[int, str]], str]:
    """解析 --edit（可重複出現）的 (index, text) 配對，驗證 index 範圍與不重複。

    Returns:
        (1-based index 與新文字的配對清單, error_message)。錯誤時清單為 []。
    """
    total = len(acceptance_list)
    parsed: list[tuple[int, str]] = []
    seen: set[int] = set()
    for raw_idx, text in raw_edits:
        try:
            n = int(raw_idx)
        except ValueError:
            return [], f"index 必須為整數：'{raw_idx}'"
        if n < 1 or n > total:
            return [], f"index 超出範圍：{n}（有效範圍 1-{total}）"
        if n in seen:
            return [], f"index 重複指定：{n}"
        seen.add(n)
        parsed.append((n, text))
    return parsed, ""


def _apply_edit(acceptance_list: list[str], edits: list[tuple[int, str]]) -> int:
    """依 index 覆寫條目文字，保留原勾選狀態。回傳變更數。"""
    for idx, text in edits:
        prefix = "[x]" if acceptance_list[idx - 1].startswith("[x]") else "[ ]"
        acceptance_list[idx - 1] = f"{prefix} {text}"
    return len(edits)


def _apply_remove(
    acceptance_list: list[str], indices: list[int], force: bool
) -> tuple[int, str]:
    """依 index 移除條目，其餘條目依原內容正確對位（不漂移索引）。

    已勾選（`[x]`）條目移除須 force=True，否則拒絕並回報哪些 index 被擋下
    （防止事後抹除驗收證據）。

    Returns:
        (變更數, error_message)。錯誤時變更數為 0。
    """
    checked_indices = [i for i in indices if acceptance_list[i - 1].startswith("[x]")]
    if checked_indices and not force:
        return 0, (
            f"index {checked_indices} 為已勾選條目，移除需加 --force"
            "（防止抹除驗收證據）"
        )
    # 由大到小刪除，避免刪除過程中前面的 index 位移影響後續刪除目標
    for idx in sorted(indices, reverse=True):
        del acceptance_list[idx - 1]
    return len(indices), ""


def execute_set_acceptance(args: argparse.Namespace, version: str) -> int:
    """執行 set-acceptance 命令。"""
    # W1-048: --as 身份申報對照（純前置檢查，deny 不寫入任何狀態）
    # W1-083: 傳入 command 名稱，使 telemetry 可做 per-command 歸因
    from ticket_system.lib.identity_guard import check_identity
    deny = check_identity(
        version,
        args.ticket_id,
        getattr(args, "as_agent", None),
        command="set-acceptance",
    )
    if deny is not None:
        return deny

    mode, err = _pick_mode(args)
    if mode is None:
        print(format_error(ErrorMessages.INVALID_OPERATION, operation=err) if hasattr(ErrorMessages, "INVALID_OPERATION") else f"[ERROR] {err}")
        return 1

    # W14-045: file_lock 包圍 load → modify → save，消除 logical race
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        ticket, load_err = load_and_validate_ticket(version, args.ticket_id)
        if load_err:
            return 1

        # W3-044: body-op precondition（set-acceptance 不允許 completed）。
        # allow_pending=True：acceptance 清單修改分建票期（PM bookkeeping，
        # status=pending）與執行期（agent 認領後勾選，status=in_progress）
        # 兩階段，前者屬例行修訂不應強制 --force。
        import sys as _sys
        force = bool(getattr(args, "force", False))
        ok, error_msg = require_in_progress(
            ticket,
            args.ticket_id,
            "set-acceptance",
            allow_completed=False,
            allow_pending=True,
            force=force,
        )
        if not ok:
            _sys.stderr.write(error_msg + "\n")
            return 2

        acceptance_list = ticket.get("acceptance", [])
        # --add 允許目前無任何條目（追加是唯一不需既有條目的模式）
        if not acceptance_list and mode != "add":
            print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_NOT_FOUND, ticket_id=args.ticket_id))
            return 1

        # 解析 index（僅 check/uncheck/remove 需要；edit 另有 (index, text) 解析）
        indices: list[int] = []
        if mode in ("check", "uncheck", "remove"):
            raw_indices = _flatten_values(getattr(args, mode, None))
            if not raw_indices:
                print(f"[ERROR] --{mode.replace('_', '-')} 需要至少一個 index")
                return 1
            indices, perr = _parse_indices(raw_indices, acceptance_list)
            if perr:
                print(f"[ERROR] {perr}")
                return 1

        if mode in ("check", "uncheck", "all_check", "all_uncheck"):
            changed, total = _apply_mode_to_list(acceptance_list, mode, indices)
        elif mode == "add":
            texts = _flatten_values(getattr(args, "add", None))
            if not texts:
                print("[ERROR] --add 需要至少一個條目文字")
                return 1
            changed = _apply_add(acceptance_list, texts)
            total = len(acceptance_list)
        elif mode == "edit":
            raw_edits = getattr(args, "edit", None) or []
            if not raw_edits:
                print("[ERROR] --edit 需要至少一組 index text")
                return 1
            edits, perr = _parse_edits(raw_edits, acceptance_list)
            if perr:
                print(f"[ERROR] {perr}")
                return 1
            changed = _apply_edit(acceptance_list, edits)
            total = len(acceptance_list)
            indices = [idx for idx, _ in edits]
        else:  # remove
            changed, rerr = _apply_remove(acceptance_list, indices, force)
            if rerr:
                print(f"[ERROR] {rerr}")
                return 1
            total = len(acceptance_list)

        ticket["acceptance"] = acceptance_list
        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        save_ticket(ticket, ticket_path)

        # 0.2.1-W3-258: 寫入後 auto-commit ticket md，與 append-log 同保護等級
        # （path-limited + graceful degrade）。W7-001 根因解：body 停留於未
        # commit 的 working tree 時，git worktree remove --force 會靜默丟棄
        # 變更（0.2.1-W3-256 實驗證實 exit 0 無警告）；set-acceptance 是代理人
        # 收尾唯一必經的 frontmatter 寫入命令，risk 集中於此。auto-commit 置於
        # file_lock 內（與 append-log 的 _execute_append_log_locked 一致設計），
        # 確保 lock 釋放前 commit 已完成或已 graceful degrade，避免並發窗口。
        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), args.ticket_id, "Acceptance Criteria",
                operation="set-acceptance",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[set-acceptance] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[set-acceptance] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )

    action_map = {
        "check": "勾選", "all_check": "勾選",
        "uncheck": "取消勾選", "all_uncheck": "取消勾選",
        "add": "新增", "edit": "編輯", "remove": "移除",
    }
    action = action_map[mode]
    if mode.startswith("all_"):
        scope = f"全部 ({changed}/{total})"
    elif mode == "add":
        scope = f"{changed} 項"
    else:
        scope = f"index {indices}" if indices else f"{changed} 項"
    print(f"[INFO] {args.ticket_id} {action} {scope}：變更 {changed} 項")
    return 0
