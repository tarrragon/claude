# IMP-041: Go 代理人產生二進位檔未清理

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | 低（不影響功能，但污染 git status） |
| **發現版本** | v0.2.0 |
| **相關 Ticket** | 0.2.0-W2-001.4.1 |

## 症狀

- git status 出現 `server/ccsession-monitor` untracked 二進位檔
- 代理人在測試過程中執行了 `go build` 產生二進位檔但未清理

## 根因分析

**行為模式**：Go 代理人執行 `go build ./...` 或 `go build` 時，會在當前目錄產生可執行檔。代理人未在完成後清理。

**技術原因**：`server/.gitignore` 未包含二進位檔名稱。

## 防護措施

- `server/.gitignore` 新增 `ccsession-monitor`（已完成）
- Go 代理人 prompt 中提醒：測試用 `go test`，不需要 `go build`
- PM 驗證時檢查是否有意外的 untracked 二進位檔
