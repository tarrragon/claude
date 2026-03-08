# IMP-028: Hook Early-Return 路徑 API 簽名漂移

## 基本資訊

- **Pattern ID**: IMP-028
- **分類**: 程式碼實作
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-09
- **風險等級**: 中
- **關聯 Ticket**: 0.1.0-W22-022

## 問題描述

### 症狀

Hook 函式在重構後，核心函式的簽名新增了參數（如 `generate_hook_output(ticket_id, check_result, project_dir, logger)`），但早期的 early-return 路徑仍呼叫舊的 2-arg 版本（`generate_hook_output(False, None)`）。

Python 不會在定義時報錯，只有在 early-return 路徑實際觸發時才會拋出 `TypeError`。由於 early-return 路徑（非 Bash 工具、非 complete 命令）在測試中較少覆蓋，此 bug 可能長期潛伏。

### 根因

函式簽名在重構過程中演化，但 early-return 路徑（只為了「快速放行」的路徑）沒有同步更新。這些路徑的作者在新增 early-return 時，使用了最簡化的呼叫形式，而非查閱當前函式簽名。

**具體案例（W22-022，發現於 W22-022 Phase 4b 重構）**：

```python
# 函式簽名（正確）
def generate_hook_output(
    ticket_id: str,
    check_result: AcceptanceCheckResult,
    project_dir: Path,
    logger,
) -> Dict[str, Any]:

# Early-return 路徑（錯誤 - 舊版本的 2-arg 呼叫）
if tool_name != "Bash":
    output = generate_hook_output(False, None)  # TypeError!
    ...

if not is_complete_command(command):
    output = generate_hook_output(False, None)  # TypeError!
    ...
```

## 解決方案

### 方案：Early-return 路徑直接輸出 allow JSON，不呼叫主流程函式

Early-return 路徑的語義是「直接放行，不需要完整檢查」，因此不應呼叫需要完整參數的 `generate_hook_output`，而是直接輸出最小的 allow 回應：

```python
# 正確的 early-return 模式
_ALLOW_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow"
    }
}

if tool_name != "Bash":
    print(json.dumps(_ALLOW_OUTPUT, ensure_ascii=False))
    return EXIT_SUCCESS
```

這樣 `generate_hook_output` 只需處理需要完整邏輯的正常路徑，不需要為 early-return 設計 sentinel 值。

## 防護措施

### 重構函式簽名後的 early-return 審查

重構函式新增/移除參數後，立即掃描所有呼叫點：

```bash
grep -n "generate_hook_output\|函式名稱" .claude/hooks/acceptance-gate-hook.py
```

確認所有呼叫點的參數數量與新簽名一致。

### Early-return 設計原則

Early-return 路徑應盡量自給自足，避免呼叫需要複雜參數的主流程函式：

- 如果 early-return 只需「放行」，直接 print 最小 allow JSON
- 如果 early-return 需要「拒絕」，直接 print 最小 deny JSON
- 不要在 early-return 中呼叫需要完整上下文的函式

### 程式碼審查檢查項

- [ ] 函式簽名修改後，是否掃描了所有呼叫點？
- [ ] Early-return 路徑是否呼叫了需要完整參數的主流程函式？
- [ ] Python 動態型別的 hook 是否有對應的 smoke test 覆蓋各類 early-return？

### 識別信號

- Hook 的 `if tool_name != ...` 或 `if not is_xxx_command(...)` 後呼叫了需要多個參數的函式
- 函式呼叫中出現 `False`, `None`, `0` 等 sentinel 值作為複雜物件參數
- 重構後的函式簽名與某些呼叫點的參數數量不一致

## 與既有模式的關係

| 模式 | 關係 |
|------|------|
| IMP-003（重構作用域回歸） | 本模式是 IMP-003 的特例：重構時變更函式簽名，但 early-return 呼叫點未同步更新 |
| IMP-006（Hook 靜默失敗） | 此 bug 在 early-return 觸發時會導致 Hook 拋出 TypeError，可能被 run_hook_safely 吞掉（靜默失敗） |
