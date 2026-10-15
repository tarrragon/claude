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


    # ===== 驗證進度訊息 =====
    VERIFICATION_IN_PROGRESS = "正在驗證 Ticket 的合併前置條件..."

    VERIFICATION_TICKET_STATUS = "  Ticket 狀態：checked"

    VERIFICATION_WORKING_TREE = "  Working tree：乾淨（無未 commit 變更）"

    # ===== 成功輸出 =====
    MERGE_COMMAND_HEADER = "驗證通過。執行以下指令合併分支："

    MERGE_COMMAND_HINT = "（合併後建議執行 /worktree cleanup {ticket_id} 清理 worktree）"

    MERGE_EXECUTING = "正在合併分支 {branch} 到 {base}..."

    MERGE_SUCCESS = "合併成功。\n建議執行 /worktree cleanup {ticket_id} 清理 worktree。"

    MERGE_FAILED = "[錯誤] 合併失敗：{error}"

    # ===== 隔離索引 CAS 合併 =====
    CAS_CONFLICT = "合併有文字衝突，已中止，未寫入任何 ref：{detail}"
    CAS_MERGE_TREE_FAILED = "merge-tree 失敗"
    CAS_CHECK_RAISED = "合併前檢查執行失敗：{error}"
    CAS_CHECK_FAILED = "合併前檢查未通過"
    CAS_REF_UNRESOLVED = "無法解析 {base} 或 {branch}"
    CAS_ALREADY_MERGED = "分支 {branch} 已被 {base} 包含，無可合併內容"
    CAS_EMPTY_MERGE = "拒絕空合併：合併結果的 tree 等於第一親代，分支變更全未進入結果"
    CAS_COMMIT_TREE_FAILED = "commit-tree 失敗：{error}"
    CAS_RETRY_LIMIT = "CAS 重試超過上限 {limit} 次，已中止，未寫入任何 ref；最後一次失敗原因：{error}"
    SKIP_GATE_NEEDS_REASON = "[錯誤] --skip-gate 必須附理由"
    CAS_SYNC_FAILED = "(同步共用 index 失敗：{error})"
    CAS_RESULT = "合併提交：{commit}（嘗試 {attempts} 次）\n同步共用 index/工作區：{synced} 檔；三平面核對不一致：{bad} 檔"
    CAS_SKIPPED_FILE = "  [未同步，index 或工作區已被改動] {path}"
    CAS_PLANE_MISMATCH = "  [三平面不一致] {path}"


class CreateMessages:
    """create 子命令訊息常數"""

    # blockedBy 依賴合併
    DEPENDENCY_MERGED = "已合併依賴分支：{branch}"
    DEPENDENCY_MERGE_FAILED = "[警告] 合併依賴分支失敗：{branch}，請手動處理"
    DEPENDENCY_BRANCH_NOT_FOUND = "依賴分支不存在，跳過：{branch}"
    DEPENDENCY_TICKET_NOT_COMPLETED = "依賴 Ticket {ticket_id} 狀態非 completed（{status}），跳過合併"
    DEPENDENCY_SECTION_HEADER = "正在檢查 blockedBy 依賴分支..."
    TICKET_FILE_NOT_FOUND = "[警告] 找不到 Ticket 檔案：{path}"
    TICKET_FILE_PARSE_ERROR = "[警告] 解析 Ticket 檔案失敗：{error}"

    # main baseline 同步（issue #77 決議 A：worktree 建立後確定性 merge main，
    # 消除 base 解析與 worktree 可用之間，其他 worktree 併行推進 main 的競態視窗）
    MAIN_MERGE_HEADER = "正在同步最新 {base}..."
    MAIN_MERGE_UP_TO_DATE = "{base} 無新變更，worktree 已是最新。"
    MAIN_MERGE_SUCCESS = "已合併 {base}，worktree 為最新狀態。"
    MAIN_MERGE_CONFLICT = (
        "[阻擋] 合併 {base} 發生衝突，worktree 需要人工處理才能安全使用。\n\n"
        "衝突詳情：\n{output}\n\n"
        "請手動處理：\n"
        "  cd {worktree_path}\n"
        "  git status              # 檢視衝突檔案\n"
        "  # 編輯解決衝突後：\n"
        "  git add <file>\n"
        "  git commit\n\n"
        "或放棄本次合併：\n"
        "  cd {worktree_path} && git merge --abort"
    )
    MAIN_MERGE_FAILED = (
        "[警告] 合併 {base} 失敗：{error}\n"
        "請手動檢查 worktree 狀態：\n"
        "  cd {worktree_path} && git status"
    )

    # macOS 建置前置檔案自動補齊
    MACOS_XCCONFIG_SYNCED = "已補齊 macOS 建置所需的 xcconfig 檔案（{files}）。"
    MACOS_PODS_HINT = (
        "提示：如需執行 flutter build macos / flutter test -d macos，"
        "請先安裝 CocoaPods 依賴：\n"
        "  cd {worktree_path}/macos && pod install"
    )


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
