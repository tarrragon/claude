# PC-004: Command 引導與腳本實作行為不符

**分類**: process-compliance
**嚴重度**: 中
**發現日期**: 2026-03-06
**相關 Ticket**: fix/sync-push-verify

---

## 症狀

Command 引導中的驗證步驟假設存在某個 git remote 或系統狀態，但腳本實際上使用不同的機制執行，導致驗證步驟失敗。

典型症狀：
- 執行 command 引導中的驗證指令時，出現 `fatal: '...' does not appear to be a git repository`
- 或驗證指令返回空結果，但腳本本身已成功執行
- Command 驗證步驟與腳本輸出結果不一致

## 根因

Command（`.claude/commands/`）的驗證步驟是**手動撰寫**的，未追蹤腳本的實際實作行為。

當腳本實作改變（例如從「設定 remote」改為「臨時 clone」），Command 引導的驗證步驟沒有同步更新，導致引導描述的環境狀態與實際不符。

**本次具體案例**：
- 腳本 `sync-claude-push.sh` 的設計是：clone 到臨時目錄 → 複製檔案 → push → 刪除臨時目錄
- Command 引導的驗證步驟寫的是 `git fetch claude-shared`，假設主專案有 `claude-shared` remote
- 但主專案從未設定此 remote，腳本完全在臨時目錄操作

## 解決方案

1. 閱讀腳本的實際執行流程，確認腳本的輸出訊息（stdout/stderr）
2. 將驗證步驟改為「確認腳本輸出包含成功訊息」，而非假設特定系統狀態存在

**修正後的驗證步驟範例**：
```markdown
4. **驗證推送結果**
   - 確認腳本輸出最後出現「成功推送 .claude 到獨立 repo！」訊息
   - 確認腳本輸出包含 `To https://github.com/...` 推送記錄
   - 注意：腳本使用臨時目錄操作，主專案沒有對應 remote，**禁止**執行 `git fetch <remote-name>`
```

## 預防措施

### 撰寫 Command 引導時的檢查清單

- [ ] 驗證步驟是否依賴腳本輸出訊息（而非系統狀態）？
- [ ] 如果依賴系統狀態（git remote、目錄、設定檔），確認腳本**確實**會建立這個狀態
- [ ] 腳本修改後，對應的 Command 引導是否同步更新？

### 核心原則

> Command 驗證步驟應以腳本的**輸出訊息**為準，而非假設腳本會建立特定的系統狀態。
> 若需要依賴系統狀態，須在腳本中明確建立（如 `git remote add`），並在 Command 中說明。

## 相關文件

- `.claude/commands/sync-push.md` - 已修正的 Command 引導
- `.claude/scripts/sync-claude-push.sh` - 腳本實作（使用臨時目錄，非 remote）
