# 事件回應流程

本文件定義 incident-responder 的完整事件回應流程，這是 Skip-gate 防護機制的核心。

---

## 流程總覽

```
錯誤/失敗發生
    |
    v
[強制] 執行 /pre-fix-eval
    |
    v
[強制] 派發 incident-responder
    |
    v
incident-responder 分析
    |
    +-- 收集錯誤上下文
    +-- 分類錯誤類型
    +-- 判斷根本原因
    +-- 安全敏感區域檢查
    |
    v
產出 Incident Report
    |
    v
建立對應 Ticket
    |
    v
提供派發建議
    |
    v
rosemary-project-manager 決定派發
    |
    v
對應代理人執行修復
```

---

## 強制觸發條件

以下情況**必須強制**派發 incident-responder：

| 觸發情境 | 識別關鍵字 |
|---------|-----------|
| 測試失敗 | "test failed", "測試失敗", "FAILED" |
| 編譯錯誤 | "compile error", "編譯錯誤", "build failed" |
| 執行時錯誤 | "runtime error", "exception", "crash" |
| 用戶回報問題 | "bug", "問題", "不正常", "出錯" |

> 詳細觸發條件：[incident-responder](../agents/incident-responder.md)

---

## 執行步驟

### Step 1：收集錯誤上下文

- 錯誤訊息、發生時間、發生位置
- 相關檔案
- 重現步驟

### Step 2：分類錯誤類型

| 錯誤分類 | 子分類 | 識別特徵 |
|---------|-------|---------|
| 編譯錯誤 | 依賴問題 | "version solving", "package not found" |
| 編譯錯誤 | 類型錯誤 | "Type mismatch", "isn't a valid override" |
| 編譯錯誤 | 語法錯誤 | "Unexpected token", "Syntax error" |
| 測試失敗 | 測試本身問題 | 測試邏輯錯誤 |
| 測試失敗 | 實作與預期不符 | 實作行為錯誤 |
| 測試失敗 | 設計邏輯錯誤 | 需求理解錯誤 |
| 執行時錯誤 | 環境問題 | 環境變數、權限 |
| 執行時錯誤 | 資料問題 | 資料格式、遺失 |
| 執行時錯誤 | 程式錯誤 | 空指標、越界 |
| 效能問題 | - | 回應時間、資源使用 |

### Step 3：判斷根本原因

使用 5 Why 分析法追蹤根本原因。

### Step 4：安全敏感區域檢查

| 區域 | 識別關鍵字 | 風險等級 |
|------|-----------|---------|
| 認證 | login, auth, password, token, session | 高 |
| 授權 | permission, role, access, admin | 高 |
| 支付 | payment, transaction, billing | 嚴重 |
| 個資 | profile, personal, user data | 高 |

---

## 派發對應表

| 錯誤分類 | 子分類 | 派發代理人 |
|---------|-------|-----------|
| 編譯錯誤 | 依賴問題 | [system-engineer](../agents/system-engineer.md) |
| 編譯錯誤 | 類型錯誤 | [parsley-flutter-developer](../agents/parsley-flutter-developer.md) |
| 測試失敗 | 測試本身問題 | [sage-test-architect](../agents/sage-test-architect.md) |
| 測試失敗 | 實作與預期不符 | [parsley-flutter-developer](../agents/parsley-flutter-developer.md) |
| 測試失敗 | 設計邏輯錯誤 | [system-analyst](../agents/system-analyst.md) |
| 執行時錯誤 | 環境問題 | [system-engineer](../agents/system-engineer.md) |
| 執行時錯誤 | 資料問題 | [data-administrator](../agents/data-administrator.md) |
| 執行時錯誤 | 程式錯誤 | [parsley-flutter-developer](../agents/parsley-flutter-developer.md) |
| 效能問題 | - | ginger-performance-tuner |
| 安全問題 | - | [security-reviewer](../agents/security-reviewer.md) |

---

## 安全問題嚴重等級

| 等級 | 判定標準 | 處理時限 |
|------|---------|---------|
| **嚴重** | 繞過認證、資料外洩、遠端執行 | 24 小時內有計畫 |
| **高** | 權限提升、敏感資料存取 | 48 小時內修復 |
| **中** | 資訊洩漏、DoS 可能 | 本版本修復 |
| **低** | 最佳實踐問題、理論風險 | 排入後續版本 |

### Ticket 優先級對應

| 嚴重等級 | Ticket 優先級 | 特殊要求 |
|---------|--------------|---------|
| 嚴重 | P0 | 立即升級 PM、考慮暫停功能 |
| 高 | P1 | 優先排程 |
| 中 | P2 | 正常優先級 |
| 低 | P3 | 記錄技術債務 |

---

## Incident Report 格式

```markdown
# Incident Report

## 報告資訊
- **Incident ID**: INC-[YYYYMMDD]-[序號]
- **報告時間**: [時間]
- **嚴重程度**: 高 / 中 / 低

## 錯誤摘要
[一句話描述錯誤]

## 錯誤分類
- **主分類**: [分類]
- **子分類**: [子分類]

## 根本原因分析
[5 Why 分析]

## 安全風險評估
- **位於安全敏感區域**: 是/否
- **建議安全審查**: 是/否

## 派發建議
- **建議代理人**: [代理人名稱]
- **建議理由**: [理由]
```

---

## 禁止行為

incident-responder **禁止**：

| 禁止行為 | 說明 |
|---------|------|
| 直接修改程式碼 | 只能分析，不能修復 |
| 跳過 Ticket 建立 | 必須建立 Ticket |
| 自行決定派發 | 只提供建議，PM 決定 |
| 省略 Incident Report | 必須產出報告 |

---

## 相關文件

- [incident-responder](../agents/incident-responder.md) - 代理人定義
- [skip-gate](../forbidden/skip-gate.md) - Skip-gate 防護
- [decision-tree](../core/decision-tree.md) - 主線程決策樹

---

**Last Updated**: 2026-01-23
**Version**: 2.0.0
