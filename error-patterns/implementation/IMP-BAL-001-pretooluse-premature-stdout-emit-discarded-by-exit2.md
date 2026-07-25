---
id: IMP-BAL-001
title: PreToolUse hook 提前 emit stdout JSON，後續分支 exit 2 時訊號被 runtime 丟棄
severity: medium
category: implementation
source_ticket: 0.2.0-W4-009
related: [0.2.0-W4-008, PC-019]
created: 2026-07-25
---

# IMP-BAL-001: PreToolUse hook 提前 emit stdout JSON，後續分支 exit 2 時訊號被 runtime 丟棄

## 症狀

- Hook 含多段檢查（如警告類檢查 + 阻擋類檢查），前段檢查以 `emit_hook_output()` 印出 additionalContext JSON 到 stdout 後繼續執行
- 後段檢查判定 block 並 `return 2` 時，主線程 context 只收到 stderr 阻擋訊息，前段已印出的 additionalContext 完全消失
- 症狀隱蔽：兩段檢查單獨測試各自通過（單元測試綠燈），只有「前段警告 + 後段 block 同時成立」的組合路徑丟訊號

## 根因

CC runtime 對 PreToolUse hook 的輸出通道依 exit code 二選一：exit 0 讀 stdout JSON（hookSpecificOutput），exit 2 讀 stderr（阻擋回饋）。兩通道互斥——exit 2 時 stdout 內容整段丟棄，不合併、不警告。

Hook 實作若把「emit 輸出」寫在檢查函式內部（副作用式輸出），輸出時機早於後續分支的 exit code 決策，即形成「先印 JSON、後定 exit code」的時序倒置；exit code 最終為 2 時前面的 JSON 是白發的。

## 解決方案

輸出決策集中化：檢查函式降為純計算（回傳狀態值，零輸出），所有輸出（emit JSON / stderr 訊息）與 exit code 決策集中在 `main()` 單點，於 exit code 確定後才輸出對應通道：

- 最終 exit 0 → emit additionalContext JSON
- 最終 exit 2 → 警告文字併入 stderr 阻擋訊息（同通道 bundling，訊號零丟失）

實例：`.claude/skills/worktree/hooks/worktree-commit-before-dispatch-hook.py`（0.2.0-W4-009 修復，commit 6ffbf27）——`_check_origin_behind` 純計算回傳 behind_count，main() 依 PC-019 判定結果分流輸出。

## 預防措施

- 撰寫多段檢查的 PreToolUse hook 時，檢查與輸出分離：檢查函式禁止直接 print / emit，統一回傳結果由 main() 輸出
- 驗證矩陣必須含組合路徑：不只逐段測試，須測「警告條件 + 阻擋條件同時成立」的交叉情境，斷言 stdout 與 stderr 的實際內容
- Code review 訊號：hook 內任何 `emit_hook_output()` / `print(file=sys.stderr)` 呼叫點之後仍存在可能 `return 2` 的程式路徑 → 檢查該輸出是否會被丟棄

## 關聯

- Ticket：0.2.0-W4-008（引入警告 additionalContext 化時埋下）、0.2.0-W4-009（修復）
- 相關模式：PC-019（worktree 派發前未 commit 防護，本案的 block 段來源）
