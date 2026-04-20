# IMP-048: Hook stderr 輸出觸發 Claude Code "hook error" 顯示

## 錯誤症狀

- Claude Code UI 反覆顯示 "PostToolUse:Bash hook error"
- 每個 Bash 工具呼叫觸發 1 個或多個 hook error
- Hook 功能正常（exit 0），但用戶看到錯誤訊息

## 根因分析

**直接原因**：Hook 將已處理的錯誤訊息寫入 stderr。

**行為鏈**：
1. Claude Code stdin 傳遞的 JSON 中 `tool_output` 含控制字元（raw newlines、ANSI codes）
2. Hook 的 `json.load(sys.stdin)` 拋出 `JSONDecodeError`
3. 兩種路徑觸發 stderr 輸出：
   - **路徑 A**：無 try-except 保護 → 異常被 `run_hook_safely` 捕獲 → `_log_exception` 寫入 stderr
   - **路徑 B**：有 try-except 保護但用 `logger.error()` → StreamHandler（指向 stderr，level=WARNING）輸出
4. Claude Code 偵測到 stderr 有輸出 → 顯示 "hook error"

**設計問題**：`hook_logging.py` 的 `_create_stream_handler` 建立了指向 stderr 的 StreamHandler，level 設為 WARNING，導致所有 WARNING/ERROR 級別日誌都寫入 stderr 並觸發 UI 顯示。

## 解決方案

### 修復 1：無保護的 json.load 加 try-except

5 個 Hook（test-timeout-post, changelog-update-hook, post-commit-fetch-hook, pre-test-hook, test-timeout-pre）在 `json.load(sys.stdin)` 外加 `try-except (json.JSONDecodeError, ValueError)` 保護。

### 修復 2：StreamHandler level 提升為 CRITICAL

`hook_logging.py` 的 `STREAM_HANDLER_LEVEL_NORMAL` 從 `logging.WARNING` 改為 `logging.CRITICAL`，只有 `_log_exception`（真正的未處理異常）才會寫入 stderr。

## 防護措施

### Hook 開發規範

| 規則 | 說明 |
|------|------|
| json.load 必須有 try-except | 防止 stdin 控制字元導致崩潰 |
| 已處理錯誤用 logger.info/debug | 不用 logger.error/warning，避免觸發 stderr |
| stderr 僅限未處理異常 | 只有 _log_exception 才寫 stderr |

### Code Review 檢查項目

- [ ] 新增的 Hook 是否有 `json.load(sys.stdin)` 的 try-except 保護？
- [ ] Hook 的錯誤處理是否避免使用 `logger.error()`/`logger.warning()`？
- [ ] Hook 是否有直接的 `sys.stderr.write()` 呼叫？如有，是否為真正的異常情況？

## 相關資訊

- **修復 Commits**: 81961bf, 327385f
- **影響範圍**: 13 個 PostToolUse:Bash hooks
- **嚴重度**: 低（功能正常，僅 UI 干擾）

---

**Created**: 2026-04-06
**Category**: implementation
