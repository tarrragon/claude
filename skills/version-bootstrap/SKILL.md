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

**跨提案依賴檢查（強制，0.4.1-W2-007 新增）**：接著執行依賴檢查腳本，偵測「本版提案依賴的提案排在更晚版本」的排序矛盾。

```bash
uv run .claude/skills/version-bootstrap/scripts/check_proposal_dependencies.py --version 0.4.0
```

腳本讀 `docs/proposals-tracking.yaml` 各提案的 `depends_on` 欄位（選填，格式見該檔案頭部註解）比對 `target_version` 排序。輸出 `[WARNING]` 時，PM 必須在本 Checkpoint 前二擇一處理：(1) 把依賴提案移入本版或更早版本一起排入，(2) 把本提案移至依賴提案完成之後的版本。**動機案例**：0.4.0 曾以 PROP-008 + PROP-010 雙提案啟動，PROP-010 依賴 PROP-011（排在 v0.5.0）卻排入 v0.4.0，矛盾拖到 W1 中段才由用戶手動發現，最終移版至 v0.5.0 與 PROP-011 同節點（詳見 0.4.1-W1-001 Solution「版本切分決策評估」）。若此檢查在 Step 1 就位，矛盾可在提案確認階段被攔截。

**Checkpoint**：PM 確認版本範圍——哪些提案納入本版、哪些延後；依賴檢查腳本無 `[WARNING]` 輸出，或警告已處理（移版/補前置）。

---

### Step 2：建 Spec 骨架（半自動）

**動作**：用 `/doc batch-init` 批量建立 spec 骨架。

```bash
doc batch-init --proposals PROP-007,PROP-008 --domain collector
```

**輸出**：每個提案對應 1 份 spec 骨架檔案。

**PM 工作**：填寫每份 spec 的 FR 列表、介面定義、約束條件。這是規劃波最耗時的人工步驟。

**UI 類提案元件庫前置檢查（強制，元件庫雙向約束方法論落地）**：Why——UI 類提案若跳過 design token 層與元件庫規劃直接進入實作，設計端與工程端會各自決定元件形狀，產生重複造輪與樣式漂移，已上線元件難以回溯套用 token 體系。Consequence——未在本步驟攔截，UI 實作票會在 Step 6 匯總建票時直接開出，等到 Phase 3b 實作階段才發現缺 token 層或元件庫章節，需回頭補規劃甚至推翻已完成的實作。Action——填寫 spec FR 時逐一判別提案是否涉及 UI/頁面/元件（FR 描述含「畫面」「頁面」「元件」「介面」「UI」等關鍵字），判為 UI 類提案者須先確認下列兩項存在，缺則先補齊才可繼續本提案的 UI 實作票規劃：

| 檢查項 | 對應載體 | 缺失時動作 |
|--------|---------|-----------|
| design token 層 | 專案 design-system 樣式檔（顏色/間距/字體/圓角/陰影參數集中管理） | 先建立 design token 層 |
| L3 元件庫章節 | spec 文件的元件庫章節（元件清單 + 原生元件禁用對照表 + 豁免清單） | 先建立或補齊 L3 元件庫章節 |

判準與分層依據（L1/L2/L3 分層、狀態綁定判準、流程整合點）見 `.claude/methodologies/component-library-bidirectional-constraint-methodology.md`。非 UI 類提案略過本檢查。

**Checkpoint**：所有 spec FR 填寫完成；UI 類提案已完成元件庫前置檢查（design token 層與 L3 元件庫章節存在，或已補齊），非 UI 類提案略過本項。

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

## 移版硬耦合盤點 SOP（0.4.1-W2-007 新增）

提案因跨提案依賴矛盾（Step 1 檢查結果）或其他理由決定移版時，禁止整包提案原封不動搬到新版本——必須先盤點該提案在**本版**留下的 schema / DDL / 契約級殘留耦合，比照 0.4.0-W1-011 模式先行定形，斬斷後才能讓移出的主體與留在本版的部分變成獨立軌道。

**動機**：0.4.0 曾規劃 PROP-008 + PROP-010 雙提案，PROP-010 因依賴 PROP-011 整體移至 v0.5.0，但其 checklist 第 1 項「Event schema `_flags` metadata 擴充」會動 `schema/event.schema.json`（契約 SOT）並牽動 PostgreSQL DDL——若放任不管、等 v0.4.0 的 PG DDL 凍結後才在 v0.5.0 定形 `_flags`，會重演 `batch_id` 式三段漂移（`docs/challenges/006-*.md` 實證）。0.4.0-W1-011 提前在 DDL 凍結前定形 `_flags` 形狀，才讓兩個提案真正解耦。

**盤點步驟**：

| 步驟 | 動作 | 產出 |
|------|------|------|
| 1. 契約掃描 | 對照移版提案的 checklist，逐項檢查是否觸及 `schema/*.schema.json`、`docs/spec/**/*.md` 的 DDL 章節、或其他跨版本共用契約檔案 | 觸及項清單 |
| 2. 凍結時序確認 | 確認本版是否有「DDL 凍結」「schema 定案」類的既定時間點（通常在 PG/儲存實作票之前） | 凍結時間點 + 是否早於移版提案原訂完成時間 |
| 3. 硬耦合分級 | 觸及項逐一判斷：純程式邏輯（無耦合，可整包移版）vs 契約形狀（硬耦合，需本版先定形） | 硬耦合項清單 |
| 4. 定形票建立 | 對每個硬耦合項建立獨立 IMP ticket（比照 0.4.0-W1-011），範圍限定「只定形契約形狀，不含業務邏輯實作」 | 定形 ticket（本版 Wave 排入） |
| 5. 教學比對 | 依 CLAUDE.md 強制操作 2，定形前讀 blog 對應模組確認欄位設計是否已有教學定義；有則優先採用，無則先在 blog 補完 | Solution 段落記錄教學比對結論 |
| 6. Ticket 交叉標記 | 定形票 `why` 欄位引用移版提案 ID + 目標版本；移版提案的 `checklist` 對應項標記 `verified_by` 指向定形票 | 雙向可追溯 |

**判斷準則（步驟 3 分級）**：

| 觸及類型 | 是否硬耦合 | 處理方式 |
|---------|-----------|---------|
| 修改 `schema/event.schema.json` 等契約 SOT 檔案 | 是 | 建定形票，本版執行 |
| 修改 DDL（`CREATE TABLE` 欄位定義） | 是 | 建定形票，本版執行 |
| 純業務邏輯（middleware、演算法、UI） | 否 | 整包隨提案移版 |
| 僅讀取既有契約、不新增欄位 | 否 | 整包隨提案移版 |

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

**Version**: 1.1.0 — Step 2 新增「UI 類提案元件庫前置檢查」小節：判別提案是否涉及 UI/頁面/元件，涉及則須先確認 design token 層與 L3 元件庫章節存在（缺則先補齊），才可繼續 UI 實作票規劃，落地元件庫雙向約束方法論流程整合點 1
**Last Updated**: 2026-07-09
