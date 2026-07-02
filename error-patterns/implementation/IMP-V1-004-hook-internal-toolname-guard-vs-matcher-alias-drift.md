---
id: IMP-V1-004
title: Hook 內部工具名字面守衛因平台工具改名靜默早退（matcher 別名仍投遞）
category: implementation
severity: high
created: 2026-07-02
source_ticket: 1.5.0-W5-002
---

# IMP-V1-004: Hook 內部工具名字面守衛 vs matcher 投遞名漂移

## 症狀

Hook 在 settings.json 註冊正常、matcher 有效收到事件，但 hook 從未實際執行任何檢查——無 log 目錄、零輸出、不報錯。從 hook-health check 與 UI 完全不可見（health check 只驗證註冊與可執行性，不驗證「實際執行到業務邏輯」）。

## 根因

三個條件疊加：

1. **平台工具改名**：CC 將 subagent 派發工具由 `Task` 改名 `Agent`。
2. **matcher 層向後相容**：CC 把 Agent 派發同時投遞給 `Task` 與 `Agent` 兩個 matcher（別名投遞），故註冊在 `Task` matcher 下的 hook 仍被呼叫——註冊層看不出任何異常。
3. **hook 內部字面守衛過時**：hook 開頭的 `if tool_name != "Task": sys.exit(0)` 收到的 `tool_name` 是新名 `Agent`，每次在任何 log 寫入前早退。

結果是「matcher 活著、hook 死了」的分層錯覺：註冊層的相容機制遮蔽了程式層的失效。

**具體案例（1.5.0-W5-002 固定值取證）**：單日 11 次真實 Agent 派發，`askuserquestion-reminder-hook` 的 log 全數記錄「非 Task 工具: Agent，跳過」；`task-dispatch-readiness-check` 因守衛位於 log 初始化之前，連 log 目錄都不存在——代理人分派正確性檢查自工具改名起從未執行。

## 解決方案

1. **守衛寫法**：工具名守衛一律寫成集合比對並同時涵蓋新舊名：`if tool_name not in ("Agent", "Task"): sys.exit(0)`（修復 commit `01f7c7410`）。
2. **偵測手段**：懷疑 hook 是否實際執行時，用固定值證據——比對「同事件下其他 hook 的 log 檔數」與「本 hook 的 log 檔數」；零檔或全數「跳過」紀錄即功能性死亡。
3. **結構性收斂**：matcher 註冊收斂至現行工具名（見 1.5.0-W5-002.2），避免依賴平台別名投遞的未承諾行為。

## 防護措施

- 新增 hook 的工具名守衛必須用集合比對 + 註解記載對應的平台工具名版本
- 平台 release notes 出現「tool renamed / matcher 行為變更」時，掃描 `.claude/hooks/` 內所有 `tool_name ==` / `tool_name !=` 字面比對（cc-release-impact-review 評估時的固定檢查項）
- 回歸測試以真實 hook 契約（stdin JSON + 現行工具名）呼叫 hook，斷言「執行到業務邏輯」而非只斷言 exit code（參照 `.claude/hooks/tests/test_askuserquestion_reminder_hook.py`）

## 與既有 pattern 的邊界

| Pattern | 差異 |
|---------|------|
| IMP-006 hook 隱性故障 | 該模式是「有錯誤但顯示不可辨」；本模式是「無錯誤、無輸出、完全靜默」 |
| IMP-028 early-return 簽名漂移 | 該模式是 API 參數演化；本模式是平台工具名演化，且被 matcher 相容層遮蔽 |
| ARCH-TUNL-001 註冊幽靈 | 該模式是註冊層失效；本模式註冊層正常、程式層失效——正好互補 |
