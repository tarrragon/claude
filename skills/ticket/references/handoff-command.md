# handoff 子命令

> **何時讀**：任務鏈交接時——需確認交接方向（子→父/父→子/兄弟→兄弟/絕對指向）、`source` vs `target` 指向語意、Session 結束時的使用方式，或任務鏈結束時的替代流程。**亦由此進入**：`workflow-handoff.md`〈交接流程決策樹〉節內「讀取端」段（`source` vs `target` 指向語意指標）。
>
> **同目錄**：`workflow-handoff.md`（交接決策樹）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在；本機 git log 僅見後續章節 TOC 補齊，未見原始拆分點（可用 `git log --oneline -- references/handoff-command.md` 查證）。

本檔章節：〈移動方向與旗標對照〉〈指向語意：source vs target〉〈用法〉〈自動偵測行為〉〈Session 結束時的使用方式〉〈按 Ticket 狀態選擇命令〉〈任務鏈結束時的替代流程〉〈五種情境〉。

## 移動方向與旗標對照

handoff 是**任務鏈內的 context 移動機制**，不是通用的「下一個任務」路由器。

> **設計原則**：handoff = 純指針 + 必要 metadata，禁止重複 ticket md 已承擔的任務內容。完整原則、違反案例與自檢清單見 `.claude/methodologies/handoff-design-principle-methodology.md`。

| 移動方向 | handoff 旗標 | 用途 |
|---------|------------|------|
| 子 → 父 | `--to-parent` | 子完成返回父驗收 |
| 父 → 子 | `--to-child <id>` | 父分派責任給子 |
| 兄弟 → 兄弟 | `--to-sibling <id>` | 同父下水平協調 |
| 任務鏈繼續 | 無旗標 | 自動判斷方向（基於 source ticket） |
| 絕對指向 | `--next <target-id>` | 顯式指向下 session 該做的 target ticket（W17-164 / L2-A） |

## 指向語意：source vs target

> 來源：W17-164

handoff JSON 同時保留兩個指向欄位：

| 欄位 | 語意 | 寫入時機 |
|------|------|---------|
| `from_ticket` | source（剛完成 / 當前的 ticket） | 必填，所有模式 |
| `direction` | 相對方向（to-parent / to-child / to-sibling / context-refresh，可加 `:TARGET_ID` 後綴） | 必填，所有模式 |
| `target_ticket_id` | 絕對指向（下 session 該做的 ticket id），選填，可空 | `--next` 必填；`--auto` 從 direction 後綴提取；`--to-parent/--to-child/--to-sibling` 由 CLI 解析 |

**讀取端優先序**（透過 `handoff_utils.resolve_target(record)` helper）：

1. 顯式 `target_ticket_id` 欄位（非空字串）
2. fallback 至 `direction` 後綴（如 `to-child:X` → `X`）
3. 兩者皆無則回傳 `None`

**向後相容**：舊 JSON 不含 `target_ticket_id` 仍可由 fallback 路徑正確解析；新生 JSON 統一寫入 `target_ticket_id` 讓指向絕對化。

設計原理見 `.claude/methodologies/atomic-ticket-methodology.md` 的「任務鏈核心哲學」章節（結構：三種移動方向、Context 保留機制）。

---

## 用法

任務鏈管理與 Context 交接。建立標準 `pending/*.json` 檔案，供下一個 session 的 `resume --list` 偵測。

```bash
# 自動偵測（搜尋最近 completed 的 ticket）
/ticket handoff

# 指定 ticket 自動判斷方向
/ticket handoff <ticket-id>

# 明確指定方向
/ticket handoff <ticket-id> --to-parent    # 返回父任務
/ticket handoff <ticket-id> --to-child <id>  # 切換到子任務
/ticket handoff <ticket-id> --to-sibling <id>  # 切換到兄弟任務

# 絕對指向：顯式指定下 session 該做的 target ticket（W17-164 / L2-A）
/ticket handoff --next <target-ticket-id> --from-ticket-id <source-id>

# 查看狀態
/ticket handoff --status

# 從 worklog 批次補建 handoff（W17-083.2）
/ticket handoff --from-worklog                    # 解析當前 active version worklog
/ticket handoff --from-worklog --worklog-path P   # 指定 worklog 路徑
/ticket handoff --from-worklog --dry-run          # 預演模式（只顯示將執行命令，不寫檔）

# 清理已完成票的 stale pending handoff JSON（Session 結束前置檢查，見下方步驟 0）
/ticket handoff --gc --dry-run                    # 只列出將清理的檔案，不刪除
/ticket handoff --gc --execute                    # 實際刪除
```

### --from-worklog 子命令

> 來源：W17-083.2

修復「worklog 寫了 handoff 段但未執行 CLI」的雙軌不同步缺口。掃描 worklog 「下個 Session 接手 Context」段提取 ticket ID，逐項補建 `.claude/handoff/pending/<id>.json`。已存在的 ticket 自動 skip。

| 條件 | 行為 |
|------|------|
| ticket ID 已有 pending handoff | `[SKIP] <id>: 已存在 pending handoff` |
| ticket ID 缺 pending handoff | 呼叫 `_execute_handoff` 建立 |
| `--dry-run` | 顯示「將執行：ticket handoff <id>」不實際寫檔 |
| worklog 無交接關鍵字 | 靜默退出 |

搭配 `stop-worklog-handoff-sync-check-hook.py`（Stop event 偵測）形成自動防護：Stop 時偵測雙軌不一致 → 警告 PM → PM 用本子命令一鍵補齊。詳見 `.claude/pm-rules/session-switching-sop.md`「Worklog 交接與 CLI handoff 同步」章節「自動化落地」小節。

### --next 子旗標

> 來源：W17-164 / L2-A

以**絕對指向**語意建立 handoff，直接寫入 `target_ticket_id` 頂層欄位，讓下 session 從「該做的 ticket」（target）讀取，不依賴 source + direction 間接推導。

| 條件 | 行為 |
|------|------|
| `--next <id>` 搭配 `--from-ticket-id <src>` | 建立 JSON：`from_ticket=src` / `direction="context-refresh"` / `target_ticket_id=id` / `auto_generated=False` |
| `--next` 與 `--auto` 同時出現 | 直接報錯 `--next 與 --auto 互斥，請擇一使用` |
| `--next` 缺 `--from-ticket-id` | 直接報錯 `--next 需要 --from-ticket-id 參數` |
| `--next` target id 格式無效 | 直接報錯並退出 |

**為何 direction 用 `context-refresh`**：避免新增 direction 類型造成 schema 連鎖變更（constants.py / `_KNOWN_DIRECTION_VALUES` / GC / hooks）。target_ticket_id 欄位已承擔絕對指向語意，direction 退為「跨 session 對焦」描述符。

**與 `--auto` 的差異**：

| 項目 | `--next` | `--auto` |
|------|---------|---------|
| 寫入意圖 | 顯式（PM 知道下個 ticket id） | 自動生成（scheduler / Hook 自動觸發） |
| target_ticket_id 來源 | CLI 直接提供 | 從 direction 後綴（如 `to-child:X`）提取 |
| auto_generated | False | True |
| direction | `context-refresh`（固定） | 可為 to-parent / to-child / to-sibling / context-refresh（`_VALID_AUTO_DIRECTIONS`，四值） |

> 上表 `--auto` 值域不含歷史值 `next-wave`：該值僅供讀取端（`resume.py`）辨識，`--auto --direction next-wave` 會被 CLI 拒絕（`_VALID_AUTO_DIRECTIONS` 不含此值），詳見下方「Wave-level 交接」段。

## 自動偵測行為

當不提供 `ticket-id` 時，命令會自動搜尋最近 completed 的 tickets：

| 結果 | 行為 |
|------|------|
| 0 個已完成 | 提示「沒有已完成的任務可供交接」 |
| 1 個已完成 | 自動選擇，執行 handoff |
| 多個已完成 | 列出清單，提示指定 ticket-id |

搜尋範圍：今天完成的 tickets（若無，則最近 5 個）。

## Session 結束時的使用方式

commit-handoff-hook 偵測到 `git commit` 成功後，PM 會用 AskUserQuestion 確認下一步。用戶選擇「Handoff」後：

0. **前置檢查（強制）**：先執行 `ticket handoff --gc --dry-run` 確認是否有已完成票的 stale pending handoff JSON（GC 僅清已完成票的殘留，不動待接手者的合法 pending）；若有，執行 `ticket handoff --gc --execute` 清理後再繼續
1. **必須**執行 `/ticket handoff` 或 `/ticket handoff <ticket-id>`
2. **禁止**手動建立 `.claude/handoff/*.md` 交接文件
3. 命令建立 `pending/*.json` → 下一個 session 的 `resume --list` 自動偵測

## 按 Ticket 狀態選擇命令

| Ticket 狀態 | 目標 | 命令 | 說明 |
|-------------|------|------|------|
| `completed` | 切換到兄弟任務 | `/ticket handoff <id> --to-sibling <target>` | 任務完成，切換平行任務 |
| `completed` | 返回父任務 | `/ticket handoff <id> --to-parent` | 子任務完成，返回父任務 |
| `completed` | 進入子任務 | `/ticket handoff <id> --to-child <target>` | 父任務完成，執行子任務 |
| `completed` | 自動判斷 | `/ticket handoff <id>` | 讓 CLI 根據任務鏈決定方向 |
| `in_progress` | Context 刷新 | `/ticket handoff <id> --context-refresh` | 乾淨 context 繼續同一任務 |
| `in_progress` | 先處理子任務 | `/ticket handoff <id> --to-child <target>` | 被子任務阻塞，先切換 |

**Wave-level 交接**（非 ticket 綁定）：

| 情境 | Direction | 說明 |
|------|-----------|------|
| Wave 完成，進入下一 Wave | `next-wave` | 不綁定特定 ticket |

`next-wave` handoff 的 JSON 若含 `from_version`、`to_version`、`session_summary` 等 wave-level 欄位，`resume.py` 會讀取並顯示（來源 Wave／目標 Wave／Session 摘要）。**產生端不在本 skill 內**：`ticket_system` 與 `skills/ticket/hooks/` 對這三個欄位名零命中，本 skill 沒有任何程式碼會寫入它們；若由外部腳本或人工建立 `next-wave` handoff JSON，欄位名須自行對齊 `resume.py` 的讀取邏輯，`ticket_id` 則為描述性名稱（如 `v{version}-W{wave}-planning`）。**`--auto --direction next-wave` 會被 CLI 拒絕**（`handoff.py:_VALID_AUTO_DIRECTIONS` 不含 `next-wave`）：本 skill 目前無 CLI 路徑產生 `next-wave` handoff，只能靠外部腳本或人工建立 JSON。

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 在 `completed` ticket 使用 `--context-refresh` | 此旗標僅適用 `in_progress`，在 completed 上會直接報錯 |
| 在 `in_progress` ticket 使用 `--to-sibling` / `--to-parent` | 任務未完成不可切換，CLI 會拒絕 |

---

## 任務鏈結束時的替代流程

當 completed ticket 無有效 handoff 目標時（無子任務、無兄弟任務、任務鏈已全部完成），handoff 不適用。此時應使用以下替代方式：

| 情境 | 判斷條件 | 替代操作 |
|------|---------|---------|
| 同 Wave 有其他 pending 任務 | 同 Wave 有未認領的 ticket | `/ticket`（列出待辦任務供選擇） |
| 同 Wave 全部完成 | 無 pending/in_progress ticket | Wave 收尾流程（決策樹第八層情境 C） |
| 跨 Wave 繼續 | 當前 Wave 完成，下個 Wave 有任務 | `/ticket`（列出下一 Wave 待辦） |

completed ticket 不 handoff 到無關任務：理由見〈移動方向與旗標對照〉。任務鏈結束後，應回到 `/ticket` 入口重新選擇任務。

**快速參考**：

```
completed ticket，想繼續工作？
    |
    v
有子任務/兄弟待處理? ─是→ /ticket handoff <id> --to-child/--to-sibling
    |
    └─否→ /ticket（查看所有待辦任務，選擇下一個）
```

---

## 五種情境

| 情境 | 方向     | 觸發條件                 |
| ---- | -------- | ------------------------ |
| 1    | 父→子    | 父完成，有子任務待執行   |
| 2    | 父→子    | 父被阻塞，需先完成子任務 |
| 3    | 子→父    | 子完成且平行任務全部完成 |
| 4    | 兄弟可選 | 子完成但有平行任務待處理 |
| 5    | 等待     | 有依賴未滿足             |

> **`--next`（絕對指向）不在此表**：此表列的是任務鏈狀態自動判斷方向的觸發條件；`--next` 為顯式旗標指定下 session 該做的 target ticket，不依賴任務鏈狀態推導。語意見上方〈移動方向與旗標對照〉表第五列與〈--next 子旗標〉節。

