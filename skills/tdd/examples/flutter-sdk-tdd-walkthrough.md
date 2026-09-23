# TDD 全流程 Walkthrough — 以一個 Flutter 監測 SDK 為例

這份走查記錄一個 Flutter 端監測 SDK 從零到驗收的完整 TDD 流程，驗收時 62 個測試全數通過、Phase 4 品質評級 A-。角色一律以職能稱呼（系統分析者、設計者、測試設計者、實作者），因為各專案的代理人命名不同而流程相同。

TDD 四階段：Phase 0 系統一致性 → Phase 1 功能設計 → Phase 2 測試設計（紅燈＝預期失敗的測試） → Phase 3a 策略規劃 + 3b 程式碼實作（綠燈＝測試通過） → Phase 4 重構評估。Phase 3 分為 3a（語言無關策略）和 3b（實際程式碼），讓策略規劃和實作關注點分離。

---

## Phase 0：系統一致性確認

系統分析者把這份功能規格逐項比對既有系統的資料收集端 schema 與傳輸協議文件，確認每一條需求都要新寫、沒有現成實作可以接。

## Phase 1：功能設計

設計者產出功能規格，含 6 條功能需求：

| FR | 功能 | 複雜度 |
|----|------|--------|
| FR-01 | MonitorConfig + init/close | 中 |
| FR-02 | Buffer + Flush（三觸發） | 高 |
| FR-03 | 離線容錯（FIFO 丟棄） | 中 |
| FR-04 | 自動攔截（FlutterError + PlatformDispatcher） | 高 |
| FR-05 | Lifecycle Observer + Isolate 安全 | 高 |
| FR-06 | Source 欄位自動填充 | 低 |

規格品質閘門對這份規格跑完維度 1-4，全數通過。

## Phase 2：紅燈測試設計

測試設計者寫出 44 個通過 + 4 個預期失敗的測試，分布在 3 個測試檔：

```text
test/
  monitor_offline_test.dart     — 離線容錯測試
  monitor_protocol_test.dart    — 協議行為測試
  monitor_integration_test.dart — 整合測試
```

**FR↔AC 覆蓋矩陣**（Phase 2 必要 checkpoint）：

| FR | 對應測試場景 | 狀態 |
|----|------------|------|
| FR-01 | init/close/重複 init | 已覆蓋 |
| FR-02 | buffer size/interval/手動 flush | 已覆蓋 |
| FR-03 | FIFO 丟棄 | 已覆蓋 |
| FR-04 | **（空）** | **未覆蓋** |
| FR-05 | paused/resumed/detached | 已覆蓋 |
| FR-06 | source 欄位 | 已覆蓋 |

**教訓**：矩陣裡 FR-04 那一列在實際操作中留白，而當時的 Phase 2 退出條件沒有把留白的格子列進去，流程因此直接走到 Phase 3；後續另開一張 ticket 補建 10 個測試才補回覆蓋。這個矩陣因此被列為 Phase 2 的退出條件——留白的格子要在離開 Phase 2 之前就被看見。

## Phase 3a：實作策略

策略規劃者產出語言無關的實作策略（虛擬碼加流程圖），交給 Phase 3b 的實作者執行。

關鍵策略決策：

- `data` 的展開順序寫成 `{...userData, ...builtIn}`，內建欄位排在後面覆蓋同名鍵，使用者傳入的資料因此改不動 `source.sdk` 這類識別欄位
- 離線 buffer 的每一個成長點都呼叫 `_enforceMaxBufferSize()`，佇列長度在任何路徑上都有上界
- 攔截器把 500ms 時間窗內的重複事件丟掉，同一個 error 只送出一次

## Phase 3b：GREEN 實作

實作者拿到 5 張 ticket，每張對應一條功能需求：

| Ticket | FR | 測試結果 |
|--------|-----|---------|
| 第 1 張 | FR-01 | 13/13 passed |
| 第 2 張 | FR-02 | 26/26 passed |
| 第 3 張 | FR-03 | 45/46 passed（1 red 非本票範圍） |
| 第 4 張 | FR-04 | 48/48 passed |
| 第 5 張 | FR-05 | 48/48 passed |

**前置重構**（在第 2 張 ticket 之前執行）：

- 引入 MonitorEvent 型別取代裸的 Map
- 兩個 bool 旗標合併成 enum MonitorState
- 移除死碼 `_instance`

**並行安全**：5 張 ticket 各自修改不同檔案（`monitor.dart` 除外），可平行開發。

## Phase 3b 整合測試

整合測試者另開一張 ticket 寫出 `lifecycle_test.dart`（4 個測試），並逐項核對彙總表上的四個項目各自對應到一個實際執行的測試。最終 62/62 passed。

## Phase 4：重構評估

Phase 4 派出三個視角平行審查同一份程式碼，得到品質評級 A- 與 5 個發現：

| 發現 | 嚴重度 | 處理 |
|------|--------|------|
| `monitor.dart` 累積的 domain 過載 | 中 | 升級為架構議題 |
| `_doFlush` 的 catch 區塊缺 observability | 低 | 當輪修復 |
| Phase 2 的行為測試缺口 | 中 | 升級為測試議題 |
| Clock 時間炸彈 | 高 | 升級為測試議題 |
| Worktree base 問題 | 低 | 升級為實作議題 |

## 整體時間線

```text
Wave 1（規劃）: Phase 0 + Phase 1 + Phase 2 紅燈 + 事件回應
Wave 2（實作）: Phase 3b（5 條 FR + 整合 + 補測試 + 合規修復）
Wave 3（驗收）: E2E 驗收 + Phase 4 重構評估 + 總檢討
```

每個 Wave 有明確邊界：Wave 1 只做規格和紅燈、Wave 2 只做 GREEN、Wave 3 只做驗收。
