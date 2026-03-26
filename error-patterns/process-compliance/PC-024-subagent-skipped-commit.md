# PC-024: 代理人完成實作但跳過 git commit

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Process Compliance |
| **嚴重性** | 低（PM 可補 commit，不影響產出品質） |
| **發現版本** | v0.2.0 |
| **相關 Ticket** | 0.2.0-W2-001.4.1 |

## 症狀

- fennel-go-developer 完成所有實作和測試（18/18 通過），但未執行 git commit
- PM 在驗證階段發現所有變更仍在 working directory，需手動 commit

## 根因分析

**行為模式**：Phase 3b 代理人的 commit 責任在 PM（見 parallel-dispatch.md Commit 責任邊界），但 prompt 中要求代理人 commit 時代理人可能因 context 限制或流程遺漏而跳過。

**技術原因**：代理人 context 接近上限時，最後的 commit 步驟容易被省略。代理人優先確保測試通過，commit 被視為低優先級。

## 防護措施

- PM 在 Phase 3b 代理人回報後，必須先執行 `git status` 確認是否有未 commit 的變更
- 不依賴代理人 commit，PM 統一管理 Phase 3b+ 的 commit

## 教訓

Phase 3b+ 的 commit 責任本來就在 PM（見 parallel-dispatch.md），代理人跳過 commit 是預期行為而非錯誤。PM 不應在 prompt 中要求代理人 commit，避免混淆責任。
