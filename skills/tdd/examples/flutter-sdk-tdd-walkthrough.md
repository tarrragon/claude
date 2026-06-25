# TDD 全流程 Walkthrough — 以 v0.2 Flutter SDK 為例

62 個測試全綠、Phase 4 評級 A-。以下是 Flutter SDK 從零到驗收的完整 TDD 流程（Phase 0-4）。

TDD 四階段：Phase 0 系統一致性 → Phase 1 功能設計 → Phase 2 測試設計（紅燈＝預期失敗的測試） → Phase 3a 策略規劃 + 3b 程式碼實作（綠燈＝測試通過） → Phase 4 重構評估。Phase 3 分為 3a（語言無關策略）和 3b（實際程式碼），讓策略規劃和實作關注點分離。

---

## Phase 0：系統一致性確認

saffron-system-analyst（系統分析專家）確認 SPEC-008 與既有系統（collector schema、transport.md）一致，無重複造輪子。

## Phase 1：功能設計

lavender-interface-designer（功能設計專家）產出 SPEC-008 功能規格：
**產出**：SPEC-008 功能規格，含 6 個 FR：

| FR | 功能 | 複雜度 |
|----|------|--------|
| FR-01 | MonitorConfig + init/close | 中 |
| FR-02 | Buffer + Flush（三觸發） | 高 |
| FR-03 | 離線容錯（FIFO 丟棄） | 中 |
| FR-04 | 自動攔截（FlutterError + PlatformDispatcher） | 高 |
| FR-05 | Lifecycle Observer + Isolate 安全 | 高 |
| FR-06 | Source 欄位自動填充 | 低 |

**`/spec validate` 確認**：維度 1-4 通過。

## Phase 2：紅燈測試設計

sage-test-architect（測試設計專家）設計出 44 個通過 + 4 個預期失敗的測試，分布在 3 個測試檔：

```
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

**教訓**：FR-04 空行在 v0.2 實際操作中被遺漏，事後才由 W2-012 補建 10 個測試。Q12 矩陣現已加入 Phase 2 退出條件。

## Phase 3a：實作策略

**派發**：pepper-test-implementer
**產出**：語言無關實作策略（虛擬碼 + 流程圖），指導 Phase 3b。

關鍵策略決策：
- `data` spread 順序：`{...userData, ...builtIn}` 內建欄位在後，確保不被用戶資料覆蓋（防止用戶意外或惡意覆蓋 `source.sdk` 等安全欄位）
- 離線 buffer：`_enforceMaxBufferSize()` 套用所有 buffer 成長點，避免記憶體無限增長
- 500ms dedup：自動攔截事件在時間窗內去重，避免同一 error 重複上報

## Phase 3b：GREEN 實作

**派發**：parsley-flutter-developer（5 張 ticket 各對應 1 個 FR）

| Ticket | FR | 測試結果 |
|--------|-----|---------|
| W2-001 | FR-01 | 13/13 passed |
| W2-002 | FR-02 | 26/26 passed |
| W2-003 | FR-03 | 45/46 passed（1 red 非本票範圍） |
| W2-004 | FR-04 | 48/48 passed |
| W2-005 | FR-05 | 48/48 passed |

**前置重構**（W2-002 前）：
- D1：引入 MonitorEvent 型別取代 raw Map
- D2：雙 bool → enum MonitorState
- D3：移除死碼 _instance

**並行安全**：5 張 ticket 各自修改不同檔案（`monitor.dart` 除外），可平行開發。

## Phase 3b 整合測試

**派發**：coriander-integration-tester（W2-006）
**產出**：lifecycle_test.dart（4 tests），rollup 驗證四項皆有真實測試。最終 62/62 passed。

## Phase 4：重構評估

**派發**：parallel-evaluation（三視角審查，W4-003）
**產出**：品質評級 A-，5 個發現：

| 發現 | 嚴重度 | 處理 |
|------|--------|------|
| monitor.dart 累積 domain 過載 | 中 | 升級 ARCH-MON-001 |
| _doFlush catch 缺 observability | 低 | W4-004 修復 |
| Phase 2 行為測試缺口 | 中 | 升級 TEST-MON-002 |
| Clock 時間炸彈 | 高 | 升級 TEST-MON-001 |
| Worktree base 問題 | 低 | 升級 IMP-MON-002 |

## 整體時間線

```
W1（規劃）: Phase 0 + Phase 1 + Phase 2 紅燈 + 事件回應
W2（實作）: Phase 3b Flutter SDK（5 FR + 整合 + 補測試 + 合規修復）
W4（驗收）: E2E 驗收 + Phase 4 重構評估 + 總檢討
```

每個 Wave 有明確邊界：W1 只做規格和紅燈、W2 只做 GREEN、W4 只做驗收。
