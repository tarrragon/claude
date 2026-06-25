# 版本規劃波 Walkthrough — 以 v0.2.0 為例

v0.2.0 從 4 個提案展開到 34 張可執行 ticket，規劃波花了約 40% 時間在 spec 和教學比對上。以下還原這個過程，展示 `/version-bootstrap` 6 步 pipeline 的實際操作。

版本開發分為多個 Wave（工作波次）：W1 規劃（spec + 測試設計）→ W2-W3 實作（GREEN 程式碼）→ W4 驗收（E2E + Phase 4 重構評估）。本 walkthrough 聚焦 W1 規劃波。

---

## 前置條件

- `todolist.yaml` 已有版本定義和提案清單
- 提案（PROP-002/004/005/006）狀態為 confirmed
- blog 教學文章已寫到對應模組

## Step 1：列出提案清單

```bash
doc list proposals
```

輸出：

```
PROP-002  Flutter SDK                     confirmed  v0.2.0
PROP-004  Benchmark CLI                   confirmed  v0.2.0
PROP-005  JSONL 匯出與備份                confirmed  v0.2.0
PROP-006  Container 部署                  confirmed  v0.2.0
```

**PM 決策**：4 個提案全部納入 v0.2.0。PROP-002 範圍最大（Flutter SDK 6 FR），其餘各 3-4 FR。

## Step 2：建 Spec 骨架

```bash
doc batch-init --proposals PROP-004,PROP-005,PROP-006 --domain collector
```

輸出：

```
=== batch-init 建置報告 ===

處理 3 個提案：

  PROP-004 (Benchmark CLI)
    Spec: SPEC-010 → docs/spec/collector/SPEC-010-benchmark-cli.md
    UC:   UC-06 → docs/usecases/UC-06-benchmark.md

  PROP-005 (JSONL 匯出與備份)
    Spec: SPEC-011 → docs/spec/collector/SPEC-011-jsonl.md
    UC:   UC-07 → docs/usecases/UC-07-jsonl.md

  PROP-006 (Container 部署)
    Spec: SPEC-012 → docs/spec/collector/SPEC-012-container.md
    UC:   UC-08 → docs/usecases/UC-08-container.md
```

**PM 工作**（最耗時步驟）：逐一填寫每份 spec 的 FR 列表。以 SPEC-010 為例：

```markdown
## Functional Requirements

### FR-01: Seed — 確定性事件產生
以 EventTypeDistribution 分配各 type 筆數，容忍 ±2%。

### FR-02: Write — 分批量測 p50/p95/p99
批次寫入事件，統計延遲分位數（單調遞增）。

### FR-03: Query — 三模式查詢基準
type/group-by/session-id 三種查詢模式。
```

PROP-002（Flutter SDK）因已有 SPEC-008，不需要 batch-init，直接進 Step 3。

## Step 3：教學比對

對每份完成的 spec 執行 `/spec validate`（Full 模式）：

```
/spec validate docs/spec/collector/SPEC-010-benchmark-cli.md
```

維度 4 輸出範例：

```
#### 維度 4: 教學一致性

| 偏移面向 | Spec 值 | 教學值 | 嚴重度 |
|---------|---------|--------|--------|
| （無偏移） | — | — | — |

教學缺口：
- Benchmark CLI 的 seed 策略在教學中未涵蓋 → 建議先在 blog 補完
```

**v0.2 實際遭遇**：SPEC-011 的查詢端點路徑 (`/v1/query` vs 教學的 `/v1/events`) 被維度 4 偵測為高嚴重度偏移。修正：對齊教學設計。詳細教學比對操作見 `spec/examples/teaching-consistency-check.md`。

## Step 4：建 UC + traceability

Step 2 已同時建立 UC 骨架。PM 填寫 GWT 場景：

```markdown
### 場景 1: Benchmark 資訊鏈完整性
Given: collector 已啟動且 DB 為空
When: 執行 `collector benchmark --events 1000`
Then: Seed 產生 1000 事件 → Write 批次寫入 → Query 能查到全部事件
```

更新 traceability 映射（將 TODO 佔位替換為實際場景編號）。

## Step 5：紅燈測試設計

對每份 spec 派發 sage-test-architect（Phase 2）。多 spec 可並行：

v0.2 實際操作：W1-003 拆 3 子票（W1-003.1/003.2/003.3）並行派發 sage，各自獨立產出紅燈測試規格。

**關鍵 checkpoint**：確認 FR↔AC 覆蓋矩陣（Q12）無空行。v0.2 在此步驟遺漏了 SPEC-008 FR-04 的獨立測試，事後才補建。詳細 TDD 全流程見 `tdd/examples/flutter-sdk-tdd-walkthrough.md`。

## Step 6：匯總建票

根據 Step 2-5 的產出建立 W2/W3/W4 ticket：

v0.2 的 Wave 分配：

| Wave | 內容 | 票數 |
|------|------|------|
| W2 | Flutter SDK 5 FR 實作 + 整合測試 + 流程改善 | 12 |
| W3 | Collector 3 功能 GREEN + CLI 接線 | 6 |
| W4 | E2E 驗收 + Phase 4 + 總檢討 | 5 |

**並行安全注意**：W3 各票禁止改 `main.go`（共用接觸點），由 W3-006 整合票統一接線。

---

## 實際時間分配

| 步驟 | 佔比 | 說明 |
|------|------|------|
| Step 1 | 5% | 讀提案確認範圍 |
| Step 2-3 | 40% | 建 spec + 填 FR + 教學比對（最耗時） |
| Step 4 | 15% | 填 UC 場景 + traceability |
| Step 5 | 25% | 紅燈設計（可並行但需驗收） |
| Step 6 | 10% | 建票 + Wave 分配 |
| 反應式 | +額外 | Clock 時間炸彈修復（W1-008/009/010） |

## 教訓

1. Step 3 教學比對不可跳過——v0.2 跳過後產生 5 項 spec×教學偏移，修復成本遠高於預防
2. Step 5 的 FR↔AC 矩陣是必要 checkpoint——v0.2 遺漏 FR-04 測試
3. 反應式工作（既有測試回歸）會打斷 pipeline，需要彈性應對
