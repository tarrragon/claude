# handoff 子命令

任務鏈管理與 Context 交接。建立標準 `pending/*.json` 檔案，供下一個 session 的 `resume --list` 偵測。

## 用法

```bash
# 自動偵測（搜尋最近 completed 的 ticket）
/ticket handoff

# 指定 ticket 自動判斷方向
/ticket handoff <ticket-id>

# 明確指定方向
/ticket handoff <ticket-id> --to-parent    # 返回父任務
/ticket handoff <ticket-id> --to-child <id>  # 切換到子任務
/ticket handoff <ticket-id> --to-sibling <id>  # 切換到兄弟任務

# 查看狀態
/ticket handoff --status
```

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

0. **前置檢查（強制）**：先執行 `ticket handoff --status` 確認無殘留 pending handoff；若有殘留，執行 `ticket handoff --gc --execute` 清理後再繼續
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

**禁止行為**：在 `completed` ticket 使用 `--context-refresh`（此旗標僅適用 `in_progress`，會直接報錯）

---

## 任務鏈結束時的替代流程

當 completed ticket 無有效 handoff 目標時（無子任務、無兄弟任務、任務鏈已全部完成），handoff 不適用。此時應使用以下替代方式：

| 情境 | 判斷條件 | 替代操作 |
|------|---------|---------|
| 同 Wave 有其他 pending 任務 | 同 Wave 有未認領的 ticket | `/ticket`（列出待辦任務供選擇） |
| 同 Wave 全部完成 | 無 pending/in_progress ticket | Wave 收尾流程（決策樹第八層情境 C） |
| 跨 Wave 繼續 | 當前 Wave 完成，下個 Wave 有任務 | `/ticket`（列出下一 Wave 待辦） |

**為什麼 completed ticket 不能 handoff 到無關任務？**

handoff 設計為**任務鏈內的 context 交接**（父→子、子→父、兄弟間），不是通用的「下一個任務」路由器。任務鏈結束後，應回到 `/ticket` 入口重新選擇任務。

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
