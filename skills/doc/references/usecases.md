# UseCase 文件規範

## 核心原則

> **UseCase 是跨 domain 的使用場景**，一個 UC 可能涉及多個 domain。
> UC 的價值在於定義「使用者能做什麼」和「系統如何回應」。

## UC 測試對應要求

### 資訊鏈整合測試（核心要求）

每個 UC 必須有至少一個**完整資訊鏈整合測試**，驗證從頭到尾的資料流串接。

> 只要整合測試通過，就能確認系統運作正常 — 這是測試保護的核心價值。

> 測試路徑為撰寫時快照（2026-03-30），實際位置以 `grep -r "describe.*{測試名稱}" tests/` 查詢為準。

| UC | 資訊鏈 | 測試名稱 pattern | 測試路徑（快照） |
|----|--------|-----------------|-----------------|
| UC-01 | 頁面偵測 → Content Script → DOM 擷取 → 驗證 → 訊息傳遞 → 儲存 → 顯示 | `Data Flow End-to-End` | tests/integration/chrome-extension/data-flow-end-to-end.test.js |
| UC-02 | 選擇格式 → Storage 讀取 → 格式轉換 → 檔案產生 → 下載 | (缺少，W2-002 待建立) | - |
| UC-05 | 頁面載入 → Storage 讀取 → Grid 渲染 → 搜尋/篩選 → 匯出觸發 | `UI 互動流程整合測試` | tests/e2e/integration/ui-interaction-flow.test.js |
| UC-07 | 變更偵測 → 匯出 → 匯入 → 衝突偵測 → 解決 → 一致性驗證 | `UC-05 跨設備同步` | tests/e2e/workflows/cross-device-sync.test.js |
| UC-08 | 錯誤發生 → 捕獲 → 分類 → 恢復策略 → 執行 → 通知 | `錯誤恢復工作流程` | tests/integration/workflows/error-recovery-workflow.test.js |

### 外部依賴邊界測試

每個 UC 涉及的外部依賴邊界必須有 exception 處理和錯誤拋出。

> **原則**：不要求完美容錯，但必須在邊界點正確偵測外部變動並報錯。

| 外部依賴 | 說明 | 要求 |
|---------|------|------|
| Readmoo DOM 結構 | 書城改版會導致選擇器失效 | 每個 DOM 操作必須有 try/catch + 日誌 |
| Chrome Extension API | API 行為變更 | 每個 Chrome API 呼叫必須有錯誤處理 |
| 使用者環境 | 記憶體、效能、網路 | 有監控和降級策略 |

### 外部依賴邊界測試的驗證標準

整合測試應包含以下場景：

```
場景 1：正常路徑（外部依賴正常）→ 功能正常運作
場景 2：外部依賴異常 → 正確拋出錯誤 + 使用者看到明確錯誤訊息
場景 3：外部依賴恢復 → 系統可恢復正常運作
```

## 平台歸屬

| 標記 | 說明 |
|------|------|
| both | Chrome Extension 和 Flutter APP 都適用 |
| app | 僅 Flutter APP |
| extension | 僅 Chrome Extension |

## Extension 實作狀態

| 狀態 | 說明 |
|------|------|
| implemented | Chrome Extension 已完整實作 |
| partial | 部分實作或概念相通但細節不同 |
| not-applicable | 不適用於 Chrome Extension |

## 模板

模板位置：`.claude/skills/doc/templates/usecase-template.md`

### 必填 frontmatter

| 欄位 | 說明 |
|------|------|
| id | UC-XX |
| platform | both / app / extension |
| extension_status | implemented / partial / not-applicable |
| related_specs | 對應的 SPEC |
| ticket_refs | 實作此 UC 的 ticket |

### 正文結構

| 章節 | 必填 | 說明 |
|------|------|------|
| 基本資訊 | 是 | 行為者、前置條件、成功保證 |
| 主要成功場景 | 是 | 正常流程步驟 |
| 替代場景 | 否 | 替代路徑 |
| 例外場景 | 是 | 錯誤處理（外部依賴邊界） |
| 驗收條件 | 是 | 功能驗收 + 邊界條件 |

## 命名規範

格式：`UC-{XX}-{簡短描述}.md`
範例：`UC-01-import.md`
