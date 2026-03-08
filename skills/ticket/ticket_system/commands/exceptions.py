"""
Handoff 系統 Exception 階層

將 handoff 例外情況從「SKILL 描述 → AI 判斷」遷移至
「程式碼偵測 → 程式碼拋出帶指引的 exception」。

設計原則：每個例外情況 = 1 個具名 Exception + 1 段可操作的指引文字。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


class HandoffError(Exception):
    """
    Handoff 系統基底 Exception。

    所有 handoff 相關例外都繼承自此類，確保可以統一捕捉。
    guidance 欄位提供使用者可操作的指引文字。
    """

    def __init__(self, message: str, guidance: str = ""):
        self.guidance = guidance
        super().__init__(message)


class HandoffTargetNotFoundError(HandoffError):
    """
    to-sibling 或 to-child handoff 的目標 ticket 不存在。

    產生原因：指定 --to-sibling 或 --to-child 時，目標 ticket ID 尚未建立。
    後果：若不攔截，會產生永遠無法被 resume 的 orphan handoff。
    """

    def __init__(self, target_id: str):
        message = f"目標 ticket 不存在：{target_id}"
        guidance = (
            f"目標 ticket '{target_id}' 尚未建立。\n"
            f"請先建立目標 ticket，再執行 handoff：\n"
            f"  ticket create --version <版本> --wave <波次> --action <動詞> --target <目標>\n"
            f"  ticket handoff <ticket_id> --to-sibling {target_id}"
        )
        super().__init__(message, guidance)
        self.target_id = target_id


class HandoffDuplicateError(HandoffError):
    """
    待恢復清單中已有指向相同目標的 pending handoff。

    產生原因：對相同目標重複執行 handoff，前一個 handoff 尚未被 resume。
    後果：若不攔截，resume --list 會顯示重複條目，AI 需自行選擇。
    """

    def __init__(self, ticket_id: str, existing_timestamp: str):
        message = f"已存在指向 {ticket_id} 的 pending handoff"
        guidance = (
            f"已有一個 pending handoff 指向 '{ticket_id}'（建立於 {existing_timestamp}）。\n"
            f"請先處理現有 handoff，再建立新的：\n"
            f"  ticket resume {ticket_id}    # 恢復現有 handoff\n"
            f"  ticket handoff gc --execute  # 清理 stale handoffs（若現有 handoff 已過期）"
        )
        super().__init__(message, guidance)
        self.ticket_id = ticket_id
        self.existing_timestamp = existing_timestamp


class HandoffSchemaError(HandoffError):
    """
    Handoff JSON 缺少必填欄位，格式不符合規格。

    產生原因：handoff JSON 被手動修改，或由舊版產生缺少新欄位。
    後果：若不攔截，格式錯誤的 handoff 無法正確 resume，且無提示。
    """

    def __init__(self, file_path: str, missing_fields: list):
        fields_str = ", ".join(missing_fields)
        message = f"Handoff JSON 缺少必填欄位：{fields_str}（檔案：{file_path}）"
        guidance = (
            f"Handoff 檔案 '{file_path}' 格式錯誤，缺少欄位：{fields_str}。\n"
            f"此 handoff 無法正確 resume。建議處理方式：\n"
            f"  1. 手動補齊欄位後重試\n"
            f"  2. 刪除損壞的 handoff 檔案：rm {file_path}\n"
            f"  3. 執行 ticket handoff gc --execute 清理 stale handoffs"
        )
        super().__init__(message, guidance)
        self.file_path = file_path
        self.missing_fields = missing_fields


class HandoffDirectionUnknownError(HandoffError):
    """
    Handoff JSON 的 direction 值不在已知 enum 範圍內。

    已知 direction 值：context-refresh、to-parent、to-sibling[:target]、to-child[:target]、auto
    產生原因：handoff JSON 被手動修改為不認識的 direction 值。
    """

    def __init__(self, direction: str, file_path: str):
        message = f"未知的 handoff direction：'{direction}'（檔案：{file_path}）"
        guidance = (
            f"Handoff 檔案 '{file_path}' 的 direction 欄位值 '{direction}' 不在已知範圍。\n"
            f"已知的 direction 值：context-refresh、to-parent、to-sibling、to-child、auto\n"
            f"建議刪除此 handoff 檔案：rm {file_path}"
        )
        super().__init__(message, guidance)
        self.direction = direction
        self.file_path = file_path
