"""
AskUserQuestion 執行時指引模組 - 關鍵決策點 PM 操作提醒

此模組提供 PM（rosemary-project-manager）在關鍵決策點所需的操作指引。
每個常數是一個完整的指引文件，嵌入逐步操作說明，無需查閱規則檔案即可行動。

設計意圖：
- 這些不是簡短的訊息常數（hook_messages.py 的職責）
- 這些是執行時指引文件，幫助 PM 正確使用 AskUserQuestion 工具
- Source of Truth 仍是 .claude/rules/core/askuserquestion-rules.md
- 當規則更新時，此模組的對應常數也應同步更新

覆蓋場景：
- 驗收方式確認（場景 #1）
- Complete 後下一步（場景 #2）
- Wave 收尾（場景 #3）
- 多任務派發確認（場景 #7）
- 決策場景通用提醒
- Commit 後 Handoff（場景 #11/16）
- 流程省略偵測（場景 #12）
- 後續任務路由（場景 #13/14）
- 批量變更備份（場景 #15）
- 錯誤學習確認（場景 #17）
- Handoff 方向選擇（場景 #9）
- Ticket complete 後 Checkpoint 提醒
"""


class AskUserQuestionReminders:
    """AskUserQuestion 強制場景提醒訊息 - 關鍵決策點使用

    覆蓋場景：驗收方式確認、Complete 後下一步、Wave 收尾、派發方式選擇、決策確認、
    Commit Handoff、流程省略偵測、後續任務路由、parallel-evaluation 觸發、批量變更備份。
    Source of Truth: .claude/rules/core/decision-tree.md
    """

    COMPLETE_REMINDER = """============================================================
[AskUserQuestion 強制提醒] complete 流程
============================================================

complete 前必須使用 AskUserQuestion 確認驗收方式：
- 標準驗收 (Recommended) - 派發 acceptance-auditor
- 簡化驗收 - DOC 類型或任務範圍單純
- 先完成後補驗收 - P0 緊急任務

complete 後必須使用 AskUserQuestion 選擇下一步。

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md
============================================================"""

    COMPLETE_NEXT_STEP_REMINDER = """============================================================
[AskUserQuestion 強制提醒] 完成後下一步（場景 #2）
============================================================

Ticket 完成後的下一步決策（完成驗收後執行）。

選項指南（必須使用 AskUserQuestion）：
1. 繼續執行下一個 Ticket
   - 條件：當前 Wave 有其他 pending Ticket
   - 操作：/ticket track list --wave {n} → 選擇下一個 Ticket

2. Wave 收尾確認
   - 條件：當前 Wave 無其他 pending Ticket
   - 操作：確認版本進展，準備關閉 Wave

3. 版本發布檢查
   - 條件：所有 Wave 完成，版本目標達成
   - 操作：/version-release check → 準備新版本發布

4. 清空 Session 結束
   - 條件：任何時候都可選
   - 操作：/clear（保護 context 資源）

規則（來源: askuserquestion-rules.md 場景 #2）：
- 禁止用純文字提問（如「要繼續嗎？」）
- 必須使用 AskUserQuestion tool 呈現選項
- 選項應基於當前 Wave/版本的實際狀態

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/askuserquestion-rules.md（場景 #2）
============================================================"""

    WAVE_WRAP_UP_REMINDER = """============================================================
[AskUserQuestion 強制提醒] Wave 收尾
============================================================

[用途說明]：
此提醒為「被動觸發」類型，在用戶主動說「繼續」時觸發。
這是簡短的即時提醒，告知用戶 Wave 可能已完成。
不同於 WAVE_COMPLETION_REMINDER（主動強制，含 Step 1-2 詳細指引）。

偵測到 Wave 可能已完成（無待處理任務）。
PM 必須使用 AskUserQuestion 確認收尾動作。

收尾前步驟（必須先執行）：
1. 列出本次修改的檔案清單
2. 告知 git 未提交狀態

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md
============================================================"""

    DISPATCH_REMINDER = """============================================================
[AskUserQuestion 提醒] 多任務派發
============================================================

派發多任務前，建議使用 AskUserQuestion 確認派發方式：
- Task subagent（各 Agent 獨立完成）
- Agent Teams（Agent 間需要即時互動）
- 序列派發（有依賴關係）

如果已經確認，請忽略此提醒。

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/guides/parallel-dispatch.md
============================================================"""

    DECISION_REMINDER = """============================================================
[AskUserQuestion 提醒] 偵測到{scenario}
============================================================

此場景建議使用 AskUserQuestion 工具而非文字提問，
避免用戶回答被 Hook 系統誤判為開發命令。

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md
============================================================"""

    # ========================================================================
    # 場景 11: Commit 後 Handoff 確認
    # ========================================================================

    COMMIT_HANDOFF_REMINDER = """============================================================
[AskUserQuestion 強制提醒] Commit 後情境感知路由
============================================================

偵測到 git commit 成功完成。

[核心原則 - PC-009]：
  Handoff first，繼續 session 是例外，不是預設。
  Context 是有限資源，每次 Ticket 完成後 handoff 能保護下一個任務的思考品質。

[強制要求] AskUserQuestion #16（錯誤學習確認）的雙通道記錄：
  選擇「記錄錯誤學習」時，必須同時執行以下兩項，缺一不可：
    (1) /error-pattern add — 寫入 .claude/error-patterns/（結構化知識庫）
    (2) 更新 memory — 寫入使用者 auto-memory（跨對話記憶）
  [WARNING] 只寫 memory 或只執行 /error-pattern add 均不符合規範

[第一步 - 強制，不可跳過] AskUserQuestion #16（錯誤學習確認）：
  即使非 Ticket 工作，commit 後仍必須執行。無「非正式任務」豁免（規則 4）。
  → ToolSearch("select:AskUserQuestion") 載入後使用
  → 選項：無需記錄 (Recommended) / 記錄錯誤學習
  → 選擇「記錄」→ 執行上述「強制要求」的雙通道記錄
  → 重新確認 #16 直到選擇「無需記錄」

[第二步 - 強制] 執行查詢：
  ticket track list --wave {n} --status pending
  （{n} 為當前 Wave 編號，例如 30）

[第三步] 根據查詢結果 AskUserQuestion #11：
  有 in_progress ticket → 情境 A，使用 AskUserQuestion #11a
  有 pending ticket     → 情境 B，使用 AskUserQuestion #11b
  皆無（Wave 完成）     → 情境 C，再執行：
    ticket track list --status pending
    → 有其他 Wave pending → #3a（Wave 收尾）
    → 無任何 pending    → #3b（/version-release check）

[情境說明]：
  情境 A:  ticket 仍 in_progress → Handoff Context 刷新（Recommended），繼續是例外
  情境 B:  ticket completed + 同 Wave 有 pending → Handoff 到下一 ticket（Recommended）
  情境 C1: 版本有其他 Wave pending → AskUserQuestion #3a（Wave 收尾 + 開始下一 Wave）
  情境 C2: 版本無任何 pending → /version-release check → AskUserQuestion #13

[AskUserQuestion 共通規則]：
  1. question 中必須包含本次 session 的完成摘要（已完成項目 + commit hash）
  2. 選項中必須包含「/clear 結束 session」（清空對話，不建立 handoff）
  3. Handoff 必須是第一選項且標記 (Recommended)，繼續在此 session 為次選

詳見: .claude/rules/core/askuserquestion-rules.md（場景 11/16 共通規則）
============================================================"""

    COMMIT_HANDOFF_SKIP16_REMINDER = """============================================================
[AskUserQuestion 強制提醒] Commit 後情境感知路由（已跳過 #16）
============================================================

偵測到 git commit 成功完成。
commit 類型為文件/格式/維護類（docs/chore/style/revert/test/ci/build），自動跳過場景 #16。

[核心原則 - PC-009]：
  Handoff first，繼續 session 是例外，不是預設。

[第一步 - 強制] 執行查詢：
  ticket track list --wave {n} --status pending
  （{n} 為當前 Wave 編號）

[第二步] 根據查詢結果 AskUserQuestion #11：
  有 in_progress ticket → 情境 A，使用 AskUserQuestion #11a
  有 pending ticket     → 情境 B，使用 AskUserQuestion #11b
  皆無（Wave 完成）     → 情境 C，再執行：
    ticket track list --status pending
    → 有其他 Wave pending → #3a（Wave 收尾）
    → 無任何 pending    → #3b（/version-release check）

[AskUserQuestion 共通規則]：
  1. question 中必須包含本次 session 的完成摘要（已完成項目 + commit hash）
  2. 選項中必須包含「/clear 結束 session」（清空對話，不建立 handoff）
  3. Handoff 必須是第一選項且標記 (Recommended)，繼續在此 session 為次選

詳見: .claude/rules/core/askuserquestion-rules.md（場景 11）
============================================================"""

    # ========================================================================
    # 場景 C: Wave 完成審查提醒（決策樹 Checkpoint 2 情境 C）
    # ========================================================================
    # [用途區分說明]：
    # WAVE_COMPLETION_REMINDER：主動觸發類型（commit 後自動檢測）
    #   - 由 commit-handoff-hook 在 commit 成功後主動偵測 Wave 完成狀態
    #   - 包含 Step 1-2 詳細指引，強制執行 /parallel-evaluation 審查
    #   - 用途：確保當前 Wave 的品質檢查不被遺漏
    #   - 觸發時機：commit 完成後，若同 Wave 無 pending Ticket
    #
    # 區別於 WAVE_WRAP_UP_REMINDER（被動觸發類型）：
    #   - 用戶主動說「繼續」或類似言詞時觸發
    #   - 簡短提醒，不含詳細步驟
    #   - 用途：提醒用戶檢查收尾前必要步驟
    # ========================================================================

    WAVE_COMPLETION_REMINDER = """============================================================
[AskUserQuestion 強制提醒] Wave 完成審查（情境 C）
============================================================

[用途說明]：
此提醒為「主動強制」類型，在 commit 成功後由 commit-handoff-hook 自動觸發。
包含 Step 1-2 詳細指引，確保當前 Wave 的品質檢查完整。

偵測到當前 Wave 已完成（同 Wave 無 pending Ticket）。

[核心步驟 - 強制]：

[Step 1] 執行 Wave 完成審查：
  /parallel-evaluation

  說明：掃描完成的 Ticket 程式碼品質、依賴關係、技術債務，
  確保沒有遺漏的改進機會。若發現問題，立即建立 Ticket 追蹤。

[Step 2] 根據 Wave 審查結果，判斷版本狀態：

  情境 C1（版本有其他 Wave pending）：
    → 執行: ticket track list --status pending
    → 查看哪些 Wave 還有待處理
    → 使用 AskUserQuestion #3a（Wave 收尾 + 開始下一 Wave）
    → 決定是否並行開始下一個 Wave

  情境 C2（版本無任何 pending Ticket）：
    → 執行: ticket track list --status pending（確認無任何 pending）
    → 執行: /version-release check
    → 準備新版本發布
    → 使用 AskUserQuestion #13（後續任務路由）

[決策樹參考]：
  decision-tree.md - 第八層 Checkpoint 2（情境 C 的完整流程）

[AskUserQuestion 規則]：
  根據「情境 C1」或「情境 C2」選擇對應的 AskUserQuestion 場景。
  詳見: .claude/rules/core/askuserquestion-rules.md（場景 #3a 和 #13）

============================================================"""

    # ========================================================================
    # 場景 12: 流程省略確認
    # ========================================================================

    PROCESS_SKIP_REMINDER = """============================================================
[AskUserQuestion 強制提醒] 流程省略偵測
============================================================

偵測到可能的流程省略意圖：{skip_description}

完整流程：{full_process}

PM 必須使用 AskUserQuestion 確認：
- 不省略，執行完整流程 (Recommended)
- 確認省略 - 用戶明確同意
- 簡化執行 - 精簡版本

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/forbidden/skip-gate.md
============================================================"""

    # ========================================================================
    # 場景 13: 後續任務路由確認
    # ========================================================================

    POST_TASK_ROUTE_REMINDER = """============================================================
[AskUserQuestion 提醒] 後續任務路由（{task_type}）
============================================================

任務完成後，PM 必須使用 AskUserQuestion 確認後續路由。
根據 task_type 提供對應選項。

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md（第八層）
============================================================"""

    POST_PHASE3B_ROUTE_REMINDER = """============================================================
[AskUserQuestion 提醒] Phase 3b 完成後路由
============================================================

Phase 3b（實作執行）已完成。建議下一步：
- 執行 /parallel-evaluation A（程式碼審查）(Recommended)
- 直接進入 Phase 4（重構評估）
- 先 commit 再決定

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md（第八層）
============================================================"""

    POST_PHASE4_ROUTE_REMINDER = """============================================================
[AskUserQuestion 提醒] Phase 4 完成後路由
============================================================

Phase 4（重構評估）已完成。建議下一步：
- 執行 /tech-debt-capture 並 commit (Recommended)
- 查看待處理 Ticket
- Wave 收尾

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md（第八層）
============================================================"""

    # ========================================================================
    # 場景 14: parallel-evaluation 觸發確認
    # ========================================================================

    PARALLEL_EVAL_TRIGGER_REMINDER = """============================================================
[AskUserQuestion 提醒] parallel-evaluation 建議
============================================================

建議執行 /parallel-evaluation 情境 {scenario}（{scenario_name}）

PM 必須使用 AskUserQuestion 確認：
- 執行 /parallel-evaluation {scenario} (Recommended)
- 跳過，直接進入下一步（觸發省略確認）
- 執行其他情境

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/skills/parallel-evaluation/SKILL.md
============================================================"""

    # ========================================================================
    # 場景 15: Bulk 變更前備份確認
    # ========================================================================

    BULK_CHANGE_BACKUP_REMINDER = """============================================================
[AskUserQuestion 強制提醒] 批量變更前備份確認
============================================================

即將進行批量修改（多檔案變更）。

PM 必須使用 AskUserQuestion 確認：
- 先 commit 備份 (Recommended) - 建立回退點
- 直接開始 - 不備份
- 查看變更範圍 - 確認後再決定

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/decision-tree.md（第八層）
============================================================"""

    # ========================================================================
    # Checkpoint 1/1.5 強制提醒：ticket complete 成功後（PostToolUse）
    # ========================================================================

    # ========================================================================
    # 場景 17: 錯誤學習經驗確認（ticket complete 時）
    # ========================================================================

    ERROR_PATTERN_REMINDER = """============================================================
[AskUserQuestion 強制提醒] 錯誤學習經驗確認（場景 #17）
============================================================

偵測到本 Ticket 執行期間有新增或修改的 error-pattern：

{file_list}

根據專案規範（ticket-lifecycle.md v5.2.0），此時應確認
是否需要建立改進 Ticket 來解決這些已識別的問題。

PM 必須使用 AskUserQuestion 選擇下一步：

1. 建立改進 Ticket（Recommended）
   - 為新增/修改的 error-pattern 建立修復或防護 Ticket
   - 後續版本排程解決

2. 已有對應 Ticket
   - error-pattern 相關修復已在現有 Ticket 中
   - 可跳過建立新 Ticket

3. 延後處理
   - 記錄到 todolist.yaml，後續版本排程
   - 但建議至少建立 Ticket 追蹤

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/flows/ticket-lifecycle.md（場景 #17）
============================================================"""

    HANDOFF_DIRECTION_REMINDER = """============================================================
[AskUserQuestion 強制提醒] Handoff 方向選擇（場景 #9）
============================================================

偵測到同 Wave 中有 {sibling_count} 個 pending sibling tickets：

{sibling_list}

完成此 ticket 後，PM 必須使用 AskUserQuestion 確認 Handoff 方向：

選項指南（必須使用 AskUserQuestion）：
1. 繼續執行特定 sibling ticket
   - 選擇同 Wave 中的下一個 pending ticket
   - 執行: /ticket track claim {next_ticket_id}

2. 等待依賴完成
   - 當前 ticket 完成後，檢查是否有依賴項
   - 完成依賴後再執行下一個 sibling

3. 讓用戶決定下一步
   - 由用戶通過 AskUserQuestion 選擇下一個 ticket

提示: ToolSearch("select:AskUserQuestion") 載入後使用。
詳見: .claude/rules/core/askuserquestion-rules.md（場景 #9）
============================================================"""

    POST_TICKET_COMPLETE_CHECKPOINT_REMINDER = """============================================================
[強制提醒] Checkpoint 1/1.5/2 — ticket complete 後必須執行
============================================================

ticket track complete 已成功。下一步強制流程：

[Checkpoint 1] 檢查未提交變更
  → 執行: git status
  → 有未提交變更 → 執行 /commit-as-prompt → [進入路徑 A]
  → 無未提交變更 → [進入路徑 B]

[路徑 A] 執行了 commit
  |
  v
[Checkpoint 1.5] AskUserQuestion #16（錯誤學習確認）
  → 本 Ticket 執行期間是否有新發現的錯誤模式？
  → 使用: ToolSearch("select:AskUserQuestion") 載入後使用
  → 選項: 無需記錄 (Recommended) / 記錄錯誤學習 / 稍後記錄
  |
  v
[Checkpoint 2] 由 commit-handoff-hook 自動觸發（無需手動執行）

[路徑 B] 無未提交變更（無 commit）
  |
  v
[Checkpoint 1.5] AskUserQuestion #16（錯誤學習確認）
  → 本 Ticket 執行期間是否有新發現的錯誤模式？
  → 使用: ToolSearch("select:AskUserQuestion") 載入後使用
  → 選項: 無需記錄 (Recommended) / 記錄錯誤學習 / 稍後記錄
  |
  v
[Checkpoint 2] 直接執行（commit-handoff-hook 不會自動觸發）
  → 執行: ticket track list --wave {n} --status pending in_progress
  → 有 pending/in_progress → 評估情境，執行對應流程
  → 無任何待處理 → AskUserQuestion #13（後續任務路由）

禁止：直接結束回應或進入下一個 Ticket（跳過 Checkpoint 1/1.5/2）
詳見: .claude/rules/core/decision-tree.md（第八層）
============================================================"""


# ============================================================================
# Backward-Compatible Alias
# ============================================================================

# 保持向後相容性：舊版引用 AskUserQuestionMessages 的程式碼仍可運作
# 新程式碼應使用 AskUserQuestionReminders
AskUserQuestionMessages = AskUserQuestionReminders


# ============================================================================
# Module Guard
# ============================================================================


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("[ERROR] 此檔案不支援直接執行")
    print("=" * 60)
    print()
    print("正確使用方式：")
    print("  from lib.ask_user_question_reminders import AskUserQuestionReminders")
    print("  msg = AskUserQuestionReminders.COMPLETE_REMINDER")
    print()
    print("詳見各 Hook 檔案的使用範例")
    print("=" * 60)
    sys.exit(1)
