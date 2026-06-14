# Phase 4：重構評估指引（4a 分析 + 4b 執行 + 4c 再審核）

## Phase 目標

Phase 4 是 TDD 流程的最後一關，確保實作後的程式碼品質達到長期可維護的標準。

**核心問題**：「這段程式碼能持久嗎？有哪些技術債務需要記錄？」

Phase 4 包含三個子階段：

- **Phase 4a**：多維度分析（冗餘、耦合、複雜度）
- **Phase 4b**：重構執行（按分析報告改善）
- **Phase 4c**：多維度再審核（可重用性、品質、效率）

---

## Phase 4 豁免評估

Phase 3b 完成後，首先評估是否符合 Phase 4 豁免條件。

### 豁免條件（任一符合即可簡化）

| 條件 | 說明 |
|------|------|
| 修改 <= 2 個檔案 | 影響範圍有限，多視角分析成本大於收益 |
| 純文件任務 | 不涉及程式碼品質 |
| 任務範圍單純 | 單一模組、修改目的明確 |

### 豁免後流程

```
符合豁免條件
    |
    v
跳過 Phase 4a（多維度分析）
    |
    v
Phase 4b：輕量重構評估（僅由重構者單視角評估）
    |
    v
Phase 4b 結論：
  - 「無需重構」→ 記錄技術債務 → 完成
  - 「需要重構」→ 執行重構 → 記錄技術債務 → 完成
（跳過 Phase 4c 再審核）
```

### 標準流程（不豁免）

```
不符合豁免條件
    |
    v
Phase 4a：多維度交叉分析
    |
    v
Phase 4b：按分析報告執行重構
    |
    v
Phase 4c：多維度再審核
    |
    v
記錄技術債務 → 完成
```

---

## Phase 4a：多維度分析

### 分析維度

| 維度 | 分析問題 | 評估方式 |
|------|---------|---------|
| 冗餘（Redundancy） | 有重複的程式碼或邏輯嗎？ | 識別重複片段，計算重複率 |
| 耦合（Coupling） | 模組間的依賴關係是否過緊？ | 分析 import 關係和呼叫鏈 |
| 複雜度（Complexity） | 認知負擔指數是否過高？ | 計算函式指數，識別過長函式 |

### 分析報告格式

```markdown
## Phase 4a 多維度分析報告

### 分析範圍
- 修改檔案：{列出}
- 分析時間：{日期}

### 冗餘分析
- 發現重複：有 / 無
- 重複位置：{如有，列出}
- 建議：{消除方式}

### 耦合分析
- 耦合等級：低 / 中 / 高
- 問題依賴：{如有，列出}
- 建議：{解耦方式}

### 複雜度分析
- 最高認知指數：{值}（標準 < 10）
- 超標函式：{如有，列出}
- 建議：{拆分方式}

### 重構優先級

| 優先級 | 問題 | 建議方案 |
|--------|------|---------|
| 高 | {問題} | {方案} |
| 中 | {問題} | {方案} |
| 低 | {問題} | {方案} |

### 結論
**建議重構**：是 / 否
**理由**：{說明}
```

> **框架整合**：Phase 4a 使用 `/parallel-evaluation B（Redundancy/Coupling/Complexity）` 執行多視角並行分析，確保交叉驗證。分析報告儲存於任務目錄。

---

## Phase 4b：重構執行

### 重構原則

| 原則 | 說明 |
|------|------|
| 測試先行 | 重構前確保測試全部通過 |
| 小步前進 | 每次只做一個小重構，立即驗證測試 |
| 不改行為 | 重構只改變結構，不改變外部行為 |
| 記錄決策 | 重要的設計決策記錄在程式碼註解 |

### 常見重構模式

| 模式 | 適用情況 |
|------|---------|
| 提取函式 | 函式過長，識別可獨立命名的邏輯片段 |
| 提取類別 | 類別有多個獨立職責 |
| 消除重複 | 相同邏輯出現多次 |
| 解耦依賴 | 直接依賴改為依賴介面 |
| 簡化條件 | 複雜 if/else 改為 Guard Clause 或多型 |

### Phase 4b 最小產出

即使評估結論為「無需重構」，也必須產出以下報告：

```markdown
## Phase 4b 重構評估報告

### 評估結果
- 需要重構：是 / 否
- 技術債務發現：有 / 無

### 重構執行摘要（如有重構）
- 重構項目：{列出}
- 主要改善：{說明}
- 測試驗證：全部通過

### 技術債務記錄

| 債務 ID | 描述 | 風險等級 | 建議處理時機 |
|--------|------|---------|------------|
| TD-001 | {描述} | 高/中/低 | {時機} |

### 結論
{說明重構評估結論}
```

> **框架整合**：Phase 4b 由重構者角色執行。完成後管理者執行 git commit，更新任務狀態。技術債務使用 `/tech-debt-capture` 建立追蹤任務。

### 重構驅動的預期管理（Layer 1）

重構的核心不是「執行步驟」，而是「預期管理與驗證」的思考框架。在動手改任何程式碼之前，先預測重構會如何影響測試結果，動手後再驗證預測是否正確。預期與實際的偏差本身就是發現設計問題的訊號。

**為何需要預期管理**：重構若無事前預測，測試由綠轉紅時無法判斷是「預期內的合理調整」還是「破壞了行為」。預先寫下「哪些測試應該繼續通過、哪些會失敗、為什麼」，能在執行後立刻辨識異常，避免把行為破壞誤當成正常重構結果而流入後續階段。

**三步驟流程**：

| 步驟 | 動作 | 產出 |
|------|------|------|
| 1. 預期管理 | 重構前列出「預期通過 / 預期失敗 / 不確定」三類測試，並說明各自理由 | 預期清單 |
| 2. 執行驗證 | 執行重構後跑完整測試套件，逐項對比預期與實際結果 | 對比結果 |
| 3. 偏差處理 | 結果不符預期時，分析偏差原因再決定下一步 | 偏差分析與決策 |

**重構前預期清單格式**：

```markdown
## 重構預期管理

### 預期會通過的測試
- {測試名稱}：為什麼這個測試應該繼續通過（行為未改變）

### 預期會失敗的測試
- {測試名稱}：為什麼會失敗、失敗原因、如何修正

### 不確定的測試
- {測試名稱}：為什麼不確定、需特別注意什麼
```

**執行後偏差處理**：

| 對比結果 | 判斷 | 對應行動 |
|---------|------|---------|
| 符合預期 | 預期通過的都通過、預期失敗的都失敗且原因相符 | 記錄結果，繼續後續優化 |
| 不符預期 | 預期通過的失敗了，或出現預期外的失敗 | 分析偏差原因，三選一：修正問題續行 / 縮小重構範圍 / 回到穩定狀態重新設計 |

**測試需要修改是設計訊號**：重構只改結構不改行為，因此測試理應保持穩定。若重構內部邏輯、改演算法、調整類別結構時測試需要修改，表示測試耦合到實作而非行為，應升級為測試設計問題重新設計（對照 phase2 的 Sociable Unit Tests 原則）。例外：業務規則或可觀察行為本身改變時，測試需修改是正確的。

### 程式碼重構分析指南（Code Refactoring Analysis Guide）

**為何需要結構化分析步驟**：重構若無系統化的分析切入點，容易只憑直覺改動，遺漏真正高價值的改善機會，或誤改已經乾淨的程式碼引入風險。以下步驟提供「先理解、再分析、後提案」的固定順序，確保每次重構都聚焦在可驗證的具體問題上。任何角色觸發 Phase 4b 重構執行時皆適用此通用流程。

When analyzing code for refactoring:

1. **Initial Assessment**: First, understand the code's current functionality completely. Never suggest changes that would alter behavior. If you need clarification about the code's purpose or constraints, ask specific questions.

2. **Systematic Analysis**: Examine the code for these improvement opportunities:
   - **Duplication**: Identify repeated code blocks that can be extracted into reusable functions
   - **Naming**: Find variables, functions, and classes with unclear or misleading names
   - **Complexity**: Locate deeply nested conditionals, long parameter lists, or overly complex expressions
   - **Function Size**: Identify functions doing too many things that should be broken down (recommended max 30 lines)
   - **Design Patterns**: Recognize where established patterns could simplify the structure
   - **Organization**: Spot code that belongs in different modules or needs better grouping
   - **Performance**: Find obvious inefficiencies like unnecessary loops or redundant calculations

3. **Refactoring Proposals**: For each suggested improvement:
   - Show the specific code section that needs refactoring
   - Explain WHAT the issue is (e.g., "This function has 5 levels of nesting")
   - Explain WHY it's problematic (e.g., "Deep nesting makes the logic flow hard to follow and increases cognitive load")
   - Provide the refactored version with clear improvements
   - Confirm that functionality remains identical

4. **Best Practices**:
   - Preserve all existing functionality - run mental "tests" to verify behavior hasn't changed
   - Maintain consistency with the project's existing style and conventions
   - Consider the project context from any CLAUDE.md files
   - Make incremental improvements rather than complete rewrites
   - Prioritize changes that provide the most value with least risk

5. **Boundaries**: You must NOT:
   - Add new features or capabilities
   - Change the program's external behavior or API
   - Make assumptions about code you haven't seen
   - Suggest theoretical improvements without concrete code examples
   - Refactor code that is already clean and well-structured

Your refactoring suggestions should make code more maintainable for future developers while respecting the original author's intent. Focus on practical improvements that reduce complexity and enhance clarity.

---

## Phase 4c：多維度再審核

### 再審核目的

確認 Phase 4b 的重構效果，並從更高層次評估品質。

### 審核維度

| 維度 | 審核問題 |
|------|---------|
| 可重用性（Reuse） | 新增/修改的元件能被其他地方重用嗎？ |
| 品質水準（Quality） | 程式碼達到長期可維護的品質嗎？ |
| 效率（Efficiency） | 有沒有明顯的效能問題或資源浪費？ |

### 再審核報告格式

```markdown
## Phase 4c 多維度再審核報告

### 可重用性
- 評估結果：高 / 中 / 低
- 發現：{說明}

### 品質水準
- 評估結果：A+ / A / B / C
- 主要優點：{列出}
- 遺留問題：{如有}

### 效率
- 評估結果：良好 / 需改善
- 效能問題：{如有}

### 總體結論
**品質等級**：{等級}
**遺留技術債務**：{有/無，若有列出}
**建議**：{後續改善建議}
```

> **框架整合**：Phase 4c 使用 `/parallel-evaluation A（Reuse/Quality/Efficiency）` 執行多視角並行審核。

---

## 技術債務記錄

Phase 4 必須記錄所有發現的技術債務，無論優先級高低。

### 記錄格式

| 欄位 | 說明 |
|------|------|
| 描述 | 技術債務的具體描述 |
| 風險等級 | 高（影響穩定性）/ 中（降低效率）/ 低（輕微問題） |
| 發現版本 | 在哪個版本發現 |
| 建議處理時機 | 下個 Patch / 下個 Minor / 技術債務清理版本 |

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 忽略技術債務 | 所有發現都必須記錄 |
| 只追蹤高優先級 | 中低優先級也必須記錄 |
| 口頭記錄 | 必須有書面記錄和追蹤 |

---

## 轉換條件

### 進入 Phase 4 的條件

- Phase 3b 所有測試通過（100%）
- Phase 4 豁免評估已完成

### 退出 Phase 4a 的條件（進入 Phase 4b）

- [ ] 冗餘、耦合、複雜度三維度分析完成
- [ ] 重構優先級報告完成

### 退出 Phase 4b 的條件

- [ ] 重構評估報告完成（即使結論為「無需重構」）
- [ ] 技術債務記錄完成
- [ ] 所有測試仍然通過（100%）

### 退出 Phase 4c 的條件（完成 TDD 流程）

- [ ] 可重用性、品質、效率三維度再審核完成
- [ ] 技術債務最終記錄完成

---

**Last Updated**: 2026-06-14
**Version**: 1.1.0 — 納入 cinnamon 外移的「程式碼重構分析指南（Code Refactoring Analysis Guide）」通用步驟（流程與人格解耦，任何角色觸發 Phase 4b 得同一流程，W8-009.3.4）
