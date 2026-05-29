"""
Worktree SKILL 訊息常數

集中管理所有使用者可見的提示、警告和錯誤訊息。
"""


class CommonMessages:
    """兩個以上子命令共用的訊息常數"""

    WORKTREE_NOT_FOUND = "[錯誤] 找不到 Ticket {ticket_id} 對應的 worktree。"

    # M7 修復：集中 Ticket ID 驗證錯誤訊息
    INVALID_TICKET_ID_FORMAT = "[錯誤] 無效的 Ticket ID 格式：\"{ticket_id}\"\n\nTicket ID 格式應為 X.X.X-WN-NNN（如：0.1.1-W9-002.1）"


class MergeMessages:
    """merge 子命令訊息常數"""

    # ===== 阻擋訊息（exit 1）=====
    TICKET_NOT_COMPLETED = "[阻擋] Ticket {ticket_id} 狀態為 {status}，尚未完成。\n請先執行：\n  /ticket track complete {ticket_id}"

    DIRTY_WORKING_TREE = "[阻擋] Working tree 有 {count} 個未 commit 的變更。\n請先 commit 或 stash 後再執行 merge。"

    # ===== 警告/提示訊息（不阻擋，exit 0）=====
    TICKET_STATUS_UNAVAILABLE = "[警告] 無法查詢 Ticket 狀態（ticket CLI 不可用）。\n跳過狀態驗證，請自行確認 Ticket 已完成。"

    NO_NEW_COMMITS = "[提示] 此分支沒有超前 {base} 的新 commit（ahead = 0）。\n可能此分支已合併，或尚未進行任何開發。"

    BRANCH_BEHIND_BASE = "[提示] 此分支落後 {base} {count} 個 commit。\n建議先執行 rebase：\n  git rebase {base}"

    # ===== 驗證進度訊息 =====
    VERIFICATION_IN_PROGRESS = "正在驗證 Ticket 的合併前置條件..."

    VERIFICATION_TICKET_STATUS = "  Ticket 狀態：checked"

    VERIFICATION_WORKING_TREE = "  Working tree：乾淨（無未 commit 變更）"

    # ===== 成功輸出 =====
    MERGE_COMMAND_HEADER = "驗證通過。執行以下指令合併分支："

    MERGE_COMMAND_HINT = "（合併後建議執行 /worktree cleanup {ticket_id} 清理 worktree）"


class CleanupMessages:
    """cleanup 子命令訊息常數"""

    # ===== Level 1 拒絕訊息（永不可繞過）=====
    LEVEL1_REJECTED = "[拒絕] Working tree 有 {count} 個未 commit 的變更。\n此安全閘門無法繞過（--force 無效）。\n請先 commit 或 stash 後再清理。"

    # ===== Level 2 警告訊息 =====
    LEVEL2_WARNING = "[警告] 分支 {branch} 尚未 push 到 origin。\n若繼續清理，此分支的本地 commit 將無法恢復。\n使用 --force 略過此警告。"

    # ===== Level 3 警告訊息 =====
    LEVEL3_WARNING = "[警告] 分支 {branch} 尚未合併到 {base}。\n若繼續清理，未合併的 commit 將無法恢復。\n使用 --force 略過此警告。"

    # ===== 成功訊息 =====
    CLEANUP_SUCCESS = "清理完成：\n  已移除 worktree：{path}\n  已刪除分支：{branch}"

    BRANCH_DELETE_FAILED = "[提示] Worktree 已移除，但分支 {branch} 刪除失敗（可能未完全合併）。\n若確認不需要，可手動執行：\n  git branch {force_flag} {branch}"

    # ===== 掃描模式訊息 =====
    SCAN_HEADER = "Worktree 清理建議報告"

    SCAN_SAFE_TO_CLEAN = "建議清理（已合併，無未儲存工作）："

    SCAN_WARNING = "需注意（警告）："

    SCAN_UNSAFE = "不安全（有未 commit 變更）："

    SCAN_NO_CLEANUP_NEEDED = "目前沒有需要清理的 worktree。"

    SCAN_CLEANUP_HINT = "  執行清理：/worktree cleanup {ticket_id}"

    SCAN_FORCE_HINT = "  強制清理（略過警告）：/worktree cleanup {ticket_id} --force"

    # ===== 錯誤訊息 =====
    REMOVE_FAILED = "[錯誤] 移除 worktree 失敗：{error}"
