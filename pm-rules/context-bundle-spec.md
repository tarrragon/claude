# Context Bundle 規範

> **目標**：PM 在派發代理人前，將該代理人需要的所有資訊寫入 Ticket，代理人只需讀取 Ticket 即可開始工作。

---

## 定義

**Context Bundle** 是 Ticket 執行日誌中的一個區段，包含下一階段代理人執行任務所需的全部前置資訊。

PM 在每次派發代理人前，透過 `ticket track append-log --section "Context Bundle"` 寫入。

---

## 核心原則

| 原則 | 說明 |
|------|------|
| **Inline 優先** | 關鍵資訊直接寫入 Ticket，不是只給路徑讓代理人自己去讀 |
| **1 Read 原則** | 代理人理想情況只需 1 次 Read（讀 Ticket）就能獲得全部 context |
| **5K token 預算** | 每個 Context Bundle 不超過 5K tokens，避免 Ticket 過大 |
| **階段覆寫** | 新 Phase 的 Context Bundle 覆寫舊的，不累積 |

---

## 按 TDD Phase 的 Context Bundle 模板

### → Phase 1（功能設計，派發 lavender）

```markdown
### Context Bundle (→ Phase 1)

**需求來源**: {UC 編號或提案編號}
**SA 審查結論**: {通過/有條件通過 + 條件摘要}
**現有相關模組**:
- {模組名稱} — {路徑} — {一句話職責}
**約束和限制**: {平台限制、相容性要求等}
```

### → Phase 2（測試設計，派發 sage）

```markdown
### Context Bundle (→ Phase 2)

**Phase 1 規格路徑**: {path}
**關鍵 API 簽名**:
  - `functionName(param1, param2) → ReturnType`
  - `ClassName.method(options) → Result`
**驗收條件**:
  1. {條件 1}
  2. {條件 2}
**測試範圍**: {哪些模組/函式需要測試}
**現有測試檔案**: {path} （行數、現有 describe 結構摘要）
**測試風格要點**: {require 模式、mock 策略、命名慣例}
```

### → Phase 3a（策略規劃，派發 pepper）

```markdown
### Context Bundle (→ Phase 3a)

**Phase 1 API 簽名**: {同上，inline}
**Phase 2 測試群組摘要**:
  - 群組 A（{職責}）: {N} 個案例
  - 群組 B（{職責}）: {N} 個案例
**Phase 2 設計路徑**: {path}
**依賴模組介面**: {被依賴的模組的 exports 摘要}
```

### → Phase 3b（實作，派發 parsley/thyme）

```markdown
### Context Bundle (→ Phase 3b)

**目標檔案**: {src path}
**測試檔案**: {test path}
**Phase 3a 策略路徑**: {path}（含虛擬碼和流程圖）
**關鍵 API 簽名**: {inline}
**測試指令**: {npm test -- path}
**預期結果**: {N} 個測試從 RED → GREEN
```

> Phase 3b 的完整 prompt 模板見 `.claude/references/phase3b-prompt-template.md`

### → Phase 4a（多視角分析，派發審查代理人）

```markdown
### Context Bundle (→ Phase 4a)

**變更檔案清單**: {git diff --name-only 的結果}
**測試結果摘要**: {PASS/FAIL 數量}
**Phase 1 驗收條件**: {inline}
**Phase 3b 關鍵實作決策**: {1-3 個決策摘要}
```

### → 多視角審查（任何 Phase 後）

```markdown
### Context Bundle (→ 多視角審查)

**審查標的**: {檔案清單或規格名稱}
**關鍵內容摘要**: {待審查文件的核心區段，inline}
**變更背景**: {為什麼做這個變更}
**已知限制**: {PM 已知但審查者可能不知道的約束}
```

---

## 代理人標準化產出格式

每個代理人完成任務後，必須往 Ticket Solution 區段寫入標準化摘要：

```markdown
### Phase {N} 完成摘要

**產出物**: {路徑}
**關鍵決策**: {1-3 個}
**下一階段需注意**: {代理人認為下一階段應知道的事}
**測試/驗證結果**: {數字摘要}
```

PM 讀取此摘要後，提取關鍵資訊填入下一個 Context Bundle。

---

## PM 的 Context Bundle 填寫流程

```
代理人完成 Phase N
    ↓
PM 讀取代理人的「Phase N 完成摘要」
    ↓
PM 從完成摘要 + 設計文件中提取關鍵資訊
    ↓
PM 用 ticket track append-log --section "Context Bundle" 寫入
    ↓
PM 派發下一階段代理人（prompt 只含 Ticket 路徑 + 動作指令）
```

---

## 派發 prompt 的理想格式

```
執行 Ticket {path} 的 Phase {N}。
Context Bundle 已在 Ticket 中準備好。
讀取 Ticket 後直接開始工作。
完成後將結果寫入 Ticket Solution 區段（使用標準化產出格式）。
```

---

## 禁止行為

| 禁止 | 原因 |
|------|------|
| Context Bundle 只給路徑不給內容 | 代理人還是要花 tool calls 讀檔案 |
| 要求代理人「自行探索現有架構」 | 浪費 50%+ tool calls 在重複查詢 |
| Context Bundle 超過 5K tokens | Ticket 過大，代理人讀取也會佔用過多 context |
| 跳過 Context Bundle 直接派發 | 代理人大概率 context 耗盡失敗 |

---

## 子任務的 Context Bundle 繼承

父 Ticket 的 Context Bundle 中標記為通用的部分（如 API 簽名、測試策略），PM 在建立子任務時應複製到子 Ticket。

這是 PM 的流程規範，不需要工具自動化。

---

## 產出契約（補充 contracts.yaml）

> contracts.yaml 位於 `.claude/tdd/` 無法由主線程直接修改。Context Bundle 的契約定義放在此處。

每個 Phase output 除了原有的 artifact（feature-spec、test-design 等）外，額外要求：

| Phase | Context Bundle artifact | 必填 | 填寫者 |
|-------|------------------------|------|--------|
| Phase 1 → 2 | Context Bundle (→ Phase 2) | 是 | PM |
| Phase 2 → 3a | Context Bundle (→ Phase 3a) | 是 | PM |
| Phase 3a → 3b | Context Bundle (→ Phase 3b) | 是 | PM |
| Phase 3b → 4a | Context Bundle (→ Phase 4a) | 是 | PM |
| 任何 → 多視角審查 | Context Bundle (→ 多視角審查) | 是 | PM |

**驗證規則**：Phase 轉換時，若 Ticket 無 Context Bundle 區段，decision-tree 的「派發前 Context Bundle 檢查」會阻塞派發。

---

## 與現有規則的關係

| 規則 | 關係 |
|------|------|
| tdd-flow.md | 階段轉換時 PM 填寫 Context Bundle 為強制動作 |
| decision-tree.md | 派發前檢查 Context Bundle 是否已填寫 |
| phase3b-dispatch-guide.md | Phase 3b 的 Context Bundle 是本規範的特化版 |
| two-stage-dispatch.md | 任務 A 產出寫入 Context Bundle |
| claude-code-platform-limits.md | Context Bundle 設計的背景約束 |

---

**Last Updated**: 2026-04-06
**Version**: 1.0.0 - 初始建立（0.17.2-W2-021）
