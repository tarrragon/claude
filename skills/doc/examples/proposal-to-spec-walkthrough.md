# 從提案到規格的完整流程 — 以 PROP-004 Benchmark CLI 為例

提案確認後，怎麼展開成可執行的規格？以下走一次從提案到 spec（功能規格）+ UC（Use Case 用例）+ traceability（需求→測試追溯映射）的完整建立流程。每個新版本的規劃波都會走這個流程。

---

## 1. 查詢提案內容

```bash
doc query PROP-004
```

確認提案的 checklist 項目——每個 checklist 項通常對應一個 spec FR（Functional Requirement，功能需求）或一個獨立功能。

## 2. 建立 Spec

### 單一建立

```bash
doc create spec SPEC-010 --title "Benchmark CLI" --domain collector
```

產出：`docs/spec/collector/SPEC-010-benchmark-cli.md`

### 批量建立（多個提案）

```bash
doc batch-init --proposals PROP-004,PROP-005,PROP-006 --domain collector
```

一次建立 3 份 spec + 3 份 UC + traceability 映射。

## 3. 填寫 Spec FR

開啟骨架檔案，填寫 Functional Requirements。每個 FR 需要：
- 行為描述（一句話）
- 輸入/輸出定義
- 約束條件

v0.2 範例（SPEC-010）：

```markdown
### FR-01: Seed — 確定性事件產生
- 輸入：EventTypeDistribution（各 type 百分比）+ 事件總數
- 輸出：指定數量的事件寫入 DB
- 約束：各 type 實際比例與指定比例誤差 ≤ 2%
```

## 4. 驗證 Spec 完善度

```
/spec validate docs/spec/collector/SPEC-010-benchmark-cli.md
```

跳過 validate 的話，spec 中的邊界/錯誤路徑/教學偏移會延到 Phase 2 甚至 Phase 3b 才暴露，修復成本指數上升。

Layer 1 檢查結構完整性，Layer 2 用維度 1-4 掃描：
- 維度 1：邊界條件（事件數為 0？超大？）
- 維度 2：錯誤路徑（DB 不存在？磁碟滿？）
- 維度 3a/3b：狀態轉換和約束違反
- 維度 4：與 blog 教學一致性

## 5. 建立 UseCase

如果 Step 2 用 `batch-init`，UC 骨架已建好。填寫 GWT 場景：

```bash
doc query UC-06  # 確認骨架內容
```

## 6. 更新 Traceability

```bash
doc test-map UC-06  # 查看 UC→測試對應
```

確認 traceability.yaml 中 spec FR → UC scenario → 測試的映射完整。

## 7. 跨文件導航

```bash
doc nav SPEC-010  # 從 spec 導航到相關提案/UC/ticket
```
