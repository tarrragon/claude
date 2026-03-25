# IMP-004: Hook 白名單不完整導致誤攔

## 基本資訊

- **Pattern ID**: IMP-004
- **分類**: 程式碼實作
- **來源版本**: v0.31.0
- **發現日期**: 2026-02-26
- **風險等級**: 高
- **來源 Ticket**: 0.31.0-W25-006

## 問題描述

### 症狀

用戶進入 Plan Mode 後無法退出；輸入含「驗證」「記錄」等詞的工作流指令被 Hook 阻擋，但用戶的意圖不是開發命令。

### 根本原因 (5 Why 分析)

1. Why 1: 用戶的 prompt 被 `command-entrance-gate-hook.py` 攔截
2. Why 2: Hook 識別到 prompt 中的「驗證」屬於 `TEST_KEYWORDS`，判定為開發命令
3. Why 3: 白名單 `is_management_operation()` 沒有涵蓋 Plan Mode 和工作流指令
4. Why 4: 白名單設計時只考慮了 Ticket 管理和討論場景，遺漏了其他合法操作場景
5. Why 5 (根本原因): **關鍵字攔截式 Hook 的白名單設計不完整，新的使用場景出現時未同步更新白名單**

### 卡住機制

```
用戶在 Plan Mode 中輸入含開發關鍵字的 prompt
    → UserPromptSubmit hook 將 prompt 識別為開發命令
    → Ticket 未認領 → 阻擋 prompt（exit code 2）
    → Assistant 收不到訊息 → 無法呼叫 ExitPlanMode
    → 用戶卡死在 Plan Mode
```

## 受影響範圍

| 層面 | 說明 |
|------|------|
| Plan Mode | 用戶無法退出 |
| 工作流指令 | 「W25-006 開始」「完成」等被攔 |
| 記錄操作 | 「記錄這個問題」被攔 |
| Commit 指令 | 不帶 `/` 的 `commit` 被攔 |

## 修復方案

在 `is_management_operation()` 的白名單中添加缺漏模式：

| 模式 | 分類 | 用途 |
|------|------|------|
| `"plan"` | management | Plan Mode 進入/退出 |
| `"記錄"` | management | 記錄/文件操作 |
| `"commit"` | management | 不帶 `/` 的 commit |
| `"開始"` | dispatch | Ticket 生命週期指令 |
| `"完成"` | dispatch | Ticket 生命週期指令 |

## 防護措施

### 設計階段

- **白名單優先原則**：關鍵字攔截式 Hook 必須同時設計「攔截清單」和「白名單」，並定期審查白名單完整性
- **新場景觸發更新**：每次新增功能或工作流時，檢查是否需要更新 Hook 白名單

### 測試階段

- **負面測試**：除了測試應攔截的命令，也需測試不應攔截的合法操作
- **場景覆蓋**：測試案例應涵蓋 Plan Mode、Ticket 生命週期、記錄操作等非開發場景

### 檢查清單

修改關鍵字攔截式 Hook 時：

- [ ] 白名單是否涵蓋所有已知的合法操作場景？
- [ ] 新增的攔截關鍵字是否可能誤攔非開發操作？
- [ ] 是否有「卡死」風險（攔截導致用戶無法恢復）？
- [ ] 負面測試（不應攔截的案例）是否足夠？

## 復發記錄

### 復發 1: main-thread-edit-restriction-hook 根目錄配置檔誤攔（2026-03-23）

| 項目 | 說明 |
|------|------|
| **來源 Ticket** | 0.1.2-W3-005.1 |
| **受影響 Hook** | `main-thread-edit-restriction-hook.py` |
| **症狀** | 編輯 `.claude/settings.json` 被攔截，包括 subagent 也無法編輯 |
| **根因** | ALLOWED_PATTERNS 只包含 `.claude/` 子目錄模式（如 `^\.claude/hooks/.*`），遺漏了根目錄下的配置檔（settings.json、settings.local.json） |
| **修復** | 新增 `^\.claude/[^/]+\.(json\|yaml)$` 模式到白名單 |
| **復發原因** | 與初次相同：白名單設計時只考慮子目錄場景，未涵蓋根目錄配置檔 |

**教訓**：白名單設計應區分「目錄層級」和「檔案層級」，避免只考慮子目錄模式而遺漏根目錄下的合法檔案。

## 相關檔案

- `.claude/hooks/command-entrance-gate-hook.py` - 初次受影響的 Hook
- `.claude/hooks/main-thread-edit-restriction-hook.py` - 復發受影響的 Hook
- `.claude/rules/forbidden/skip-gate.md` - Skip-gate 防護機制定義

---

**Last Updated**: 2026-03-23
**Version**: 1.1.0 - 新增復發 1 記錄（main-thread-edit-restriction-hook 根目錄配置檔誤攔）
