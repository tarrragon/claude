# IMP-020: PostToolUse Hook 共存時的觸發碰撞

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | IMP-020 |
| 類別 | implementation |
| 來源版本 | v0.1.0 |
| 發現日期 | 2026-03-06 |
| 風險等級 | 中 |
| 來源 | cli-failure-help-reminder-hook 與 pre-fix-evaluation-hook 共存於 PostToolUse/Bash 觸發點 |

### 症狀

1. 多個 PostToolUse Hook 註冊在同一個 matcher（如 Bash）
2. 同一事件（如測試失敗）觸發多個 Hook，產生重複提醒
3. 使用者收到互相矛盾或冗餘的指導訊息

### 根本原因（5 Why 分析）

1. Why 1：多個 Hook 對同一 matcher 事件各自判斷
2. Why 2：各 Hook 獨立開發，未考慮與現有 Hook 的職責重疊
3. Why 3：缺乏「Hook 觸發排除清單」的設計慣例
4. Why 4：Hook 系統無內建的優先級或互斥機制
5. Why 5：根本原因：**新增 Hook 時未分析同 matcher 下已有 Hook 的觸發範圍**

---

## 解決方案

### 新增 PostToolUse Hook 的設計檢查清單（強制）

新增與現有 Hook 共享 matcher 的 Hook 時，必須完成：

| 步驟 | 動作 | 說明 |
|------|------|------|
| 1 | 列出同 matcher 現有 Hook | 查閱 settings.json 中同 matcher 的所有 Hook |
| 2 | 分析觸發範圍重疊 | 確認哪些事件會同時觸發多個 Hook |
| 3 | 設計排除清單 | 新 Hook 必須排除已由現有 Hook 處理的事件 |
| 4 | 驗證無重複提醒 | 測試重疊場景確認只有一個 Hook 輸出提醒 |

### stderr 作為非零退出指標的注意事項

| 工具 | stderr 行為 | 處理方式 |
|------|------------|---------|
| 一般 CLI | stderr 非空 = 失敗 | 直接偵測 |
| git | 資訊性輸出也寫 stderr | 需排除已知資訊模式（Already up to date 等） |
| grep/find | 無結果時 exit 1 | 排除預期的搜尋命令 |

---

## 預防措施

### 已實作

| 措施 | 說明 | 位置 |
|------|------|------|
| HANDLED_BY_OTHER_HOOKS 排除清單 | cli-failure-help-reminder-hook 排除 pre-fix-evaluation 已處理的命令 | .claude/hooks/cli-failure-help-reminder-hook.py |
| EXPECTED_STDERR_COMMANDS 清單 | 排除 grep/find 等預期有 stderr 的命令 | .claude/hooks/cli-failure-help-reminder-hook.py |
| GIT_INFO_STDERR_PATTERNS 清單 | 排除 git 資訊性 stderr | .claude/hooks/cli-failure-help-reminder-hook.py |

---

## 行為模式分析

此模式屬於「共存設計盲點」類型：

- **獨立開發假設**：假設新 Hook 獨立運作，未考慮同 matcher 下的既有 Hook
- **觸發範圍未分析**：未明確劃分各 Hook 的職責邊界
- **stderr 語義差異**：不同工具對 stderr 的使用慣例不同，不能一視同仁

### 相關錯誤模式

| 模式 | 關係 |
|------|------|
| IMP-006 | 同為 Hook 系統問題，IMP-006 是靜默失敗，IMP-020 是重複觸發 |
| PC-005 | 本 Hook 的防護對象，CLI 失敗假設歸因 |

---

## 相關文件

- .claude/hooks/cli-failure-help-reminder-hook.py - 實作範例
- .claude/hooks/pre-fix-evaluation-hook.py - 同 matcher 的既有 Hook
- .claude/settings.json - Hook 註冊配置
