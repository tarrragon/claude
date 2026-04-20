## Ticket #N: [動詞] [目標]

### 1. 背景
[需求來源和上下文]

### 2. 目標
[一句話明確目標，≤ 30 字]

### 3. 步驟
1. [具體步驟 1]
2. [具體步驟 2]
3. [具體步驟 3]

### 4. 驗收條件（SMART）
- [ ] [具體 + 可測量條件 1]
- [ ] [具體 + 可測量條件 2]
- [ ] [具體 + 可測量條件 3]

### 5. 參考文件
- [設計文件連結]
```

**動詞選擇**: 定義 / 撰寫 / 實作 / 整合 / 修復 / 重構

---

## 核心原則：Ticket 引導優先於 Hook 防護

流程改善的根本解法在於 **Ticket 系統本身**——建立、認領、轉階段時主動引導正確行為。Hook 只是最後一道防護網，不是首選方案。

| 層級 | 位置 | 角色 |
|------|------|------|
| **第一層（根本）** | Ticket 建立與轉階段引導 | 告訴 PM 應提供什麼資訊、何時記錄什麼 |
| **第二層（輔助）** | Skill / 方法論 | 提供決策樹、檢查清單、範例 |
| **第三層（防護）** | Hook | 攔截違規行為，作為失敗備援 |

**判斷順序**：

| 問題 | 改善位置 |
|------|---------|
| PM 建立 Ticket 時遺漏關鍵欄位？ | 改善 `/ticket create` 引導與必填檢查（第一層） |
| PM 不知道何時該填什麼？ | 擴充 Ticket 範本與階段轉換提示（第一層） |
| PM 明知要填卻沒填？ | 考慮 Hook 防護（第三層） |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 遇到 PM 行為偏差第一反應是寫 Hook | Hook 是防護，不解決「為什麼 PM 不做」 |
| 用 Hook 強制取代 Ticket 引導設計 | Ticket 引導缺失時 Hook 只會不停觸發，PM 負擔上升 |
| 多層 Hook 疊加以「萬無一失」 | 等同用繃帶處理骨折；根本需修 Ticket 引導 |

**行動驗證**：改善流程時，先問「Ticket 系統的建立 / 認領 / 轉階段引導是否充分？」如果該問題是「PM 沒被提示該做什麼」，解法必須回到引導設計；Hook 只在 PM 明知卻故意不做時才是正確工具。

---

## 執行步驟

1. **領取** - 檢查依賴、標記進行中、記錄開始時間
2. **閱讀** - 理解背景目標、閱讀參考文件
3. **執行** - 按步驟執行、即時記錄問題
4. **自檢** - 逐項檢查驗收條件、執行測試
5. **提交** - 標記 Review 中、通知 Reviewer
6. **處理結果** - 通過則關閉、未通過則修正
7. **經驗記錄** - 記錄學習收穫、更新 error-patterns（如適用）

---

## 經驗傳承機制

> 理論依據：Will Guidara《Unreasonable Hospitality》- "Excellence is the culmination of thousands of details executed perfectly."

### 完成時強制記錄學習

每個 Ticket 完成時，必須回答以下問題：

| 問題 | 目的 |
|------|------|
| 這個任務我們學到了什麼？ | 知識累積 |
| 有沒有可以改進流程的地方？ | 持續改進 |
| 這個經驗可以應用在哪裡？ | 經驗傳承 |
| 是否需要建立 error-pattern？ | 防止重複錯誤 |

### 阻塞狀態處理（積極派發原則）

當 Ticket 進入 Blocked 狀態時，不應被動等待，應**積極派發子 Ticket**解除阻塞：

| 阻塞原因 | 處理方式 | 新 Ticket 類型 |
|---------|---------|---------------|
| 缺少前置條件 | 派發前置任務 | IMP |
| 技術問題不清楚 | 派發調查任務 | INV |
| 需要更多資訊 | 派發研究任務 | RES |
| 需要決策 | 派發評估任務 | EVA |

**原則**：Blocked 狀態不應超過 24 小時，必須採取行動。

---

## 關閉條件檢查清單

### 強制條件（6 項，缺一不可）

- [ ] 所有驗收條件打勾完成
- [ ] Review 通過
- [ ] 相關測試 100% 通過
- [ ] `dart analyze` 0 錯誤
- [ ] 工作日誌已更新
- [ ] **所有子 Ticket 已 completed 或 closed**（父責任履行判準）

### 建議條件（3 項）

- [ ] 程式碼符合專案規範
- [ ] 無技術債務（TODO/FIXME）
- [ ] 文檔同步更新

---

## 父 complete 前置條件

> **核心原則**：父 Ticket 的責任由子 Ticket 的完成來履行。「父文件完成」不等於「父責任履行」。

> 理論依據：`.claude/methodologies/atomic-ticket-methodology.md` 的「任務鏈核心哲學 — 父子責任傳遞」章節。

### 兩個概念的區分

| 概念 | 定義 | 驗證方式 |
|------|------|---------|
| 父文件完成 | 父 Ticket 的 AC 欄位全部勾選、Problem Analysis / Solution 區段寫完 | 檢查 Ticket 檔案 YAML 與區段 |
| 父責任履行 | 父的所有衍生子 Ticket（含遞迴孫層）全部 completed 或 closed | 遍歷 chain 檢查所有後代 |

**父 complete 的必要條件 = 父文件完成 AND 父責任履行**。缺一不可。

### 強制行為

1. **禁止越過未完成的子獨立 complete 父**：即使父 AC 全勾、報告寫完，若有任一子 Ticket 仍 pending/in_progress/blocked，父不可 complete
2. **父任務在等待子完成期間保持 in_progress**：不可回退為 pending，不可跳過為 completed
3. **若父需在子完成前抽離 context**：使用 handoff 而非 complete

### 強制規則落地

- PM 執行 `ticket track complete` 前必須檢查所有子 Ticket 狀態
- CLI 層 Hook 檢查：根任務 complete 時遞迴檢查子孫層，任一未完成 → exit 2 (block)
- PM 行為規則：見 `.claude/pm-rules/ticket-lifecycle.md` 的「父 Ticket complete 前置檢查」章節

### 形式驗證 vs 實質驗收（職責邊界）

| 層級 | 驗證對象 | 執行者 | 可偽造性 |
|------|---------|--------|---------|
| 形式驗證 | 子 Ticket status 欄位是 completed/closed | acceptance-gate-hook | 可手動編輯 frontmatter 偽造 |
| 實質驗收 | AC 實際達成、測試實際通過、執行日誌實際填寫 | acceptance-auditor | 需親自執行驗證 |

Hook 通過只代表子 status 形式合規，不代表子 Ticket 實際完成工作。父 complete 前仍需派發 acceptance-auditor 執行實質驗收。

---

## SMART 驗收條件

| 原則 | 說明 | 錯誤範例 | 正確範例 |
|-----|------|---------|---------|
| **S** 具體 | 避免模糊用語 | 功能正常 | `create()` 回傳 Book 物件 |
| **M** 可測量 | 使用數字 | 測試覆蓋率高 | 測試覆蓋率 >= 80% |
| **A** 可達成 | 範圍合理 | 整合所有 API | 整合 Google Books API |
| **R** 相關 | 與目標相關 | UI 顏色正確 | Repository 測試通過 |
| **T** 完成標準 | 明確何時算完成 | 持續優化 | 響應時間 <= 200ms |

---

## Reference

### 相關方法論

- [Atomic Ticket 方法論](./atomic-ticket-methodology.md) - 單一職責設計原則
- [Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md) - 5W1H 設計標準
- [敏捷重構方法論](./agile-refactor-methodology.md) - TDD 四階段整合

### 模板

- 主版本工作日誌: `.claude/templates/work-log-template.md`
- Ticket 工作日誌: `.claude/templates/ticket-log-template.md`