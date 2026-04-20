# IMP-049: "hook error" 顯示是 Claude Code CLI 已知 Bug，非 Hook 程式碼問題

## 錯誤症狀

- Claude Code CLI 在每次工具呼叫後顯示多個 `PostToolUse:Bash hook error` 和 `PreToolUse:Bash hook error`
- Hook 功能正常（exit 0、無 stderr、日誌正常記錄）
- 手動測試（`uv run --script`）無法複現

## 根因分析

**這是 Claude Code CLI 的已知 Bug，非 Hook 程式碼問題。**

已確認的 GitHub Issues：
- anthropics/claude-code#34713 — False "Hook Error" labels cause Claude to prematurely end turns
- anthropics/claude-code#34859 — Hook error messages shown on every tool call even when hooks exit 0
- anthropics/claude-code#10936 — Hook Status Label Shows "Hook Error" for Successful Executions
- anthropics/claude-code#27886 — PostToolUse hook with exit 0 still shows hook error

**行為描述**：
- 所有三種 hook 類型（PreToolUse、PostToolUse、UserPromptSubmit）都受影響
- 即使 hook exit 0、無 stderr、有效 JSON，仍顯示 "hook error"
- 每個 session 200-400 個假 error 注入 context
- PostToolUse hook 不讀取 stdin 時，pipe break → EPIPE → 顯示 hook error

## 錯誤的修復嘗試（教訓）

### 嘗試 1：修改 run_hook_safely 異常處理（第一次 commit）
- **假設**：exit code 1 導致 hook error
- **修改**：異常時改為 exit 0 + JSON additionalContext
- **結果**：問題未解決（因為 Hook 本來就 exit 0）

### 嘗試 2：stdout 攔截確保 JSON 輸出（第二次 commit）
- **假設**：空 stdout 導致 hook error
- **修改**：用 io.StringIO 攔截 stdout，無輸出時補預設 JSON
- **結果**：問題惡化（從 5 個增加到 16 個），破壞了原本正常的 Hook
- **已回退**

### 根因誤判過程
1. 假設 exit code 問題 → 修改 exit code → 未驗證就 commit
2. 假設 stderr 問題 → 手動測試無 stderr → 轉向下一個假設
3. 假設空 stdout 問題 → 手動測試發現部分 hook 無 stdout → 修改 → 反而惡化
4. 每次假設都「看起來合理」但沒有充分驗證就動手

## 正確的處理方式

1. **先搜尋社群**：這種「所有 hook 都 error」的問題很可能是 CLI bug，應先查 GitHub Issues
2. **用 `claude --debug` 除錯**：Claude Code 提供了內建的 hook 除錯模式
3. **不要修改 Hook 系統核心（run_hook_safely）來繞過 CLI bug**
4. **接受 CLI 的限制**：如果是已知 bug，等待官方修復比自己 hack 更安全

## 防護措施

| 規則 | 說明 |
|------|------|
| 修改 Hook 系統核心前先搜尋社群 | 避免修復 CLI 層面的問題 |
| 手動測試正常 + CLI 仍異常 = 可能是 CLI bug | 不要繼續在 Hook 層面找問題 |
| run_hook_safely 是高影響函式 | 修改會影響所有 70+ 個 Hook，必須極度謹慎 |
| stdout 攔截是危險操作 | 會改變所有 Hook 的 I/O 行為，容易引入副作用 |

## 除錯工具

```bash
# Claude Code 內建除錯
claude --debug

# 手動測試單一 hook
echo '<json_input>' | uv run --quiet --script .claude/hooks/<hook>.py

# 檢查 stderr 輸出
echo '<json_input>' | uv run --quiet --script .claude/hooks/<hook>.py 2>&1 1>/dev/null
```

## 關聯

- **相關模式**: IMP-048（Hook stderr 觸發 hook error 顯示）
- **外部 Issues**: anthropics/claude-code#34713, #34859, #10936, #27886

---

**Created**: 2026-04-10
**Category**: implementation
**Severity**: 低（CLI 顯示問題，Hook 功能正常）
**Key Lesson**: 修改前先搜尋社群確認是否為已知問題
