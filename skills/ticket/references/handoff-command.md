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

1. **必須**執行 `/ticket handoff` 或 `/ticket handoff <ticket-id>`
2. **禁止**手動建立 `.claude/handoff/*.md` 交接文件
3. 命令建立 `pending/*.json` → 下一個 session 的 `resume --list` 自動偵測

## 五種情境

| 情境 | 方向     | 觸發條件                 |
| ---- | -------- | ------------------------ |
| 1    | 父→子    | 父完成，有子任務待執行   |
| 2    | 父→子    | 父被阻塞，需先完成子任務 |
| 3    | 子→父    | 子完成且平行任務全部完成 |
| 4    | 兄弟可選 | 子完成但有平行任務待處理 |
| 5    | 等待     | 有依賴未滿足             |
