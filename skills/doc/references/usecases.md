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
| UC-02 | 選擇格式 → Storage 讀取 → 格式轉換 → 檔案產生 → 下載 | (缺少，待建立) | - |
| UC-05 | 頁面載入 → Storage 讀取 → Grid 渲染 → 搜尋/篩選 → 匯出觸發 | `UI 互動流程整合測試` | tests/e2e/integration/ui-interaction-flow.test.js |
| UC-07 | 變更偵測 → 匯出 → 匯入 → 衝突偵測 → 解決 → 一致性驗證 | `UC-05 跨設備同步` | tests/e2e/workflows/cross-device-sync.test.js |
| UC-08 | 錯誤發生 → 捕獲 → 分類 → 恢復策略 → 執行 → 通知 | `錯誤恢復工作流程` | tests/integration/workflows/error-recovery-workflow.test.js |

### 外部依賴邊界測試

每個 UC 涉及的外部依賴邊界必須有 exception 處理和錯誤拋出。

> **原則**：不要求完美容錯，但必須在邊界點正確偵測外部變動並報錯。

| 外部依賴 | 說明 | 要求 |
|---------|------|------|
| 目標站點 DOM 結構 | 站點改版會導致選擇器失效 | 每個 DOM 操作必須有 try/catch + 日誌 |
| 平台/瀏覽器 API | API 行為變更 | 每個平台 API 呼叫必須有錯誤處理 |
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
| 流程拓撲（結構化 Flow 區塊） | 否（選填，FlowStep 屬提案中型別） | 步驟拓撲的機器可讀表示，見下方「流程拓撲」章節 |
| 例外場景 | 是 | 錯誤處理（外部依賴邊界） |
| 驗收條件 | 是 | 功能驗收 + 邊界條件 |

## 流程拓撲（結構化 Flow 區塊）

UC 文件本文可選擇性附加一個結構化 `flow` YAML 區塊，把「主要成功場景」與
「替代場景」的步驟拓撲（分岔點、回歸點）升格為可解析節點，供 `doc uc` CLI
與外部視覺化工具讀取，不需再靠散文 heuristic 推斷。欄位骨架與填寫範例見模板
`.claude/skills/doc/templates/usecase-template.md`「流程拓撲（結構化 Flow
區塊，選填）」章節。

### 欄位定義

| 欄位 | 必填/選填 | 說明 |
|------|----------|------|
| id | 必填 | 不透明穩定識別符，不得編碼位置或父步驟（具體格式待首個 UC 完成結構化回填後定案） |
| name | 必填 | 步驟名稱，對應散文標題 |
| next | 選填 | 後續步驟 id 列表；主要成功場景步驟填寫，場景結尾留空陣列 |
| branch_from | 選填（替代場景步驟填） | 分岔自哪個主要成功場景步驟 id（`branching` 邊，唯一儲存欄位落在替代場景側） |
| return_to | 選填（替代場景步驟填） | 回歸到哪個步驟 id（`returning` 邊，back-edge，排除於 DAG 佈局） |
| implements | 選填 | 對應 FR 編號 |
| emits / consumes | 選填 | 對應 EVT 編號，EVT 型別現階段屬提案中，尚未進 validator 必填契約 |

**「由某步驟分岔出哪些替代場景」不另存欄位**：只有 `branch_from`（替代場景
側）是儲存欄位；反向查詢（某主流程步驟分岔出哪些替代場景）由消費端掃描所有
步驟的 `branch_from` 衍生取得，避免正反向欄位不同步。

### 填寫時機

| UC 狀態 | 是否需填寫 |
|---------|-----------|
| 新建 UC | 建議填寫（模板已內建骨架） |
| 既有 UC（尚未回填） | 選填；`uc_registry.py` 未偵測到本區塊時 fallback 既有散文解析，不影響既有功能 |
| FlowStep 升級為正式契約後 | 待首個 UC 完成結構化回填驗證後另行裁定是否轉為必填 |

### 與 uc_registry.py 的關係

`uc_registry.py` 對 flow 步驟解析採**雙軌策略**：UC 文件含結構化 `flow`
區塊時優先解析該區塊；不存在時 fallback 既有的散文 heuristic 解析（掃描
`### 主要成功場景` 標題、正則抓 `N. **步驟名稱**`）。兩條路徑互不覆蓋，
舊格式 UC 的既有解析行為不受影響。

## 銜接 TDD 流程

若專案已採用 `tdd` skill，UC 步驟→GWT 行為場景種子、UC 資訊鏈→整合測試映射會由 TDD 端消費（`/tdd start` 時偵測 doc 文件自動觸發），doc 端不需額外操作，詳見 tdd skill 的 doc-handoff 銜接說明（若已安裝）。若未採用 tdd skill，UC 文件仍可獨立作為用例規格使用，只是不會有自動銜接進測試流程的種子產出。

## 命名規範

格式：`UC-{XX}-{簡短描述}.md`
範例：`UC-01-import.md`
