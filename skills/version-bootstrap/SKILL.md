---
name: version-bootstrap
description: "版本規劃波 orchestrator。封裝「提案→spec→教學比對→UC→紅燈測試→建票」6 步 pipeline，標準化每版的規劃波啟動流程。Use for: (1) 新版本開始時的規劃波啟動, (2) 從提案到可執行 ticket 的標準化轉換, (3) 確保教學比對不被跳過。Use when: todolist.yaml 中有新版本的 proposals 待展開、準備進入新版本的 W1 規劃波時。"
---

# /version-bootstrap — 版本規劃波 Orchestrator

把版本提案展開成可執行的 ticket，中間不漏教學比對。

---

## 定位

| 工具 | 問的問題 | 關係 |
|------|---------|------|
| /version-bootstrap | 「這個版本要做什麼？怎麼拆成可執行單位？」 | 規劃波 orchestrator |
| /doc | 「文件建好了沒？格式對嗎？」 | 文件系統工具（被呼叫） |
| /spec validate | 「規格夠清楚嗎？和教學一致嗎？」 | 品質閘門（被呼叫） |
| /tdd | 「測試怎麼設計？」 | TDD 流程（Phase 2 被呼叫） |
| /ticket | 「工作怎麼追蹤？」 | 票務系統（被呼叫） |

---

## 使用方式

```
/version-bootstrap --version 0.3.0
```

PM 執行後，依 6 步流程逐步推進。每步有 checkpoint（PM 確認後才進下一步），不是全自動 pipeline。

---

## 6 步流程

### Step 1：列出提案清單（全自動）

**動作**：讀取 `docs/todolist.yaml` 中指定版本的 `proposals` 欄位，列出提案清單和摘要。

```bash
doc list proposals  # 確認提案狀態
```

**輸出**：提案 ID + 標題 + 狀態表格。

**Checkpoint**：PM 確認版本範圍——哪些提案納入本版、哪些延後。

---

### Step 2：建 Spec 骨架（半自動）

**動作**：用 `/doc batch-init` 批量建立 spec 骨架。

```bash
doc batch-init --proposals PROP-007,PROP-008 --domain collector
```

**輸出**：每個提案對應 1 份 spec 骨架檔案。

**PM 工作**：填寫每份 spec 的 FR 列表、介面定義、約束條件。這是規劃波最耗時的人工步驟。

**Checkpoint**：所有 spec FR 填寫完成。

---

### Step 3：教學比對（半自動）

**動作**：對每份完成的 spec 執行 `/spec validate`（Full 模式，含維度 4 教學一致性）。

**前置**：確認 CLAUDE.md「教學模組對應表」中有對應模組。

**PM 工作**：
- 偏移（高/中）：對齊教學設計或先在 blog 補完
- 教學缺口：在 blog 對應模組補完後再回來

**Checkpoint**：維度 4 無高嚴重度偏移。教學缺口已處理或標記 sync-pending。

---

### Step 4：建 UC + traceability（半自動）

**動作**：Step 2 的 `batch-init` 已同時建立 UC 骨架和 traceability 映射佔位。

**PM 工作**：填寫每份 UC 的 GWT 場景、更新 traceability 映射（spec FR → UC scenario）。

**Checkpoint**：所有 UC 場景填寫完成，traceability 映射無 TODO 佔位。

---

### Step 5：紅燈測試設計（半自動，可並行）

**動作**：對每份 spec 派發 sage-test-architect 做 Phase 2 紅燈測試設計。

多 spec 可並行派發（每個 spec 1 張子票）。派發時使用 `/tdd` Phase 2 流程，sage 產出紅燈測試規格。

**PM 工作**：驗收 sage 產出——確認 FR↔AC 覆蓋矩陣（Q12）無空行。

**Checkpoint**：所有 spec 的 Phase 2 完成，紅燈測試規格已提交。

---

### Step 6：匯總建票（半自動）

**動作**：根據 Step 2-5 的產出，建立 W2/W3/W4 的 IMP ticket。

- W2/W3：GREEN 實作票（每個 spec FR 或功能模組 1 張）
- W4：驗收票（E2E + Phase 4）

**建票來源**：
- spec FR 列表 → IMP ticket
- Phase 2 紅燈規格 → 確認 ticket 粒度（每張 ticket 的紅燈數）
- UC 場景 → 整合測試 ticket

**PM 工作**：確認 Wave 分配、並行安全（共用檔案需整合票）。

**Checkpoint**：所有 ticket 建立完成，Wave 分配確認。

---

## 反應式工作（不納入 bootstrap）

以下工作在規劃波過程中可能發生，但不屬於 bootstrap pipeline：

| 類型 | 處理方式 |
|------|---------|
| 既有測試回歸 | incident-responder 分析，建 ANA/IMP ticket |
| Spec 約束邊界發現 | 建 ANA ticket，可在 Step 2 填寫時順帶處理 |
| 流程改善發現 | 建 ANA ticket，排入後續 Wave |

---

## 與 v0.2 W1 的對照

| v0.2 W1（手動） | /version-bootstrap |
|----------------|-------------------|
| 手動 cp 模板建 spec | Step 2 `/doc batch-init` |
| 手動讀 blog 比對 | Step 3 `/spec validate --dim 4` |
| 手動 cp 模板建 UC | Step 2 `/doc batch-init`（同步建立） |
| 手動編輯 traceability | Step 2 自動佔位 + Step 4 填寫 |
| 逐一派 sage | Step 5 批量並行派發 |
| 手動建票 | Step 6 依產出匯總 |

---

**Version**: 1.0.0
**Last Updated**: 2026-06-24
