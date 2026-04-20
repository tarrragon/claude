# PC-064: PM 列純文字選項而未使用 AskUserQuestion

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-064 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 姊妹模式 | PC-014（合理化跳過，根因互異） |

### 症狀

1. PM 在對話回覆中以 Markdown 列表呈現選項（「A. xxx / B. xxx」「選項 1 / 選項 2」）讓用戶以自然語言回覆「A」「選 2」等
2. PM 在回覆結尾出現「要選哪個？」「需要先做 X 還是 Y？」「要不要繼續？」等純文字問句
3. 整個 session 中 AskUserQuestion 只在 Hook 強制觸發（如 commit 後錯誤學習提醒）時使用過，其他自主決策點全部為純文字
4. 用戶必須糾正多次同一類疏失後，PM 才意識到應使用 AskUserQuestion

### 與 PC-014 的區別（必讀）

| 維度 | PC-014 合理化跳過 | PC-064 無意識疏失 |
|------|------------------|-------------------|
| 意識層 | 明知規則，以「非正式任務」「太小」豁免 | 完全未想到應用 AUQ |
| 觸發點 | Hook 提醒出現後仍選擇跳過 | 連 Hook 都沒覆蓋的對話中途決策點 |
| 根因層 | 規則豁免邊界不明 | Hook 覆蓋缺失 + 行為慣性 + 規則落地深度 |
| 防護 | 規則 4（無 Ticket 場景仍適用） | Hook 新增 + 規則行為循環增補 + CLAUDE.md 顯眼提醒 |

### 根本原因（Reality Test 驗證後）

本模式的根因已透過 Reality Test 驗證並區分「已驗證事實」與「被反證假設」：

**被反證的假設**：

| 假設 | 反證依據 |
|------|---------|
| ToolSearch 載入摩擦主導 | 首次載入後後續決策點仍未用 AUQ，摩擦僅首次成立 |
| 規則文件不明確 | askuserquestion-rules.md 通用觸發原則（規則 1/3）極明確 |

**已驗證的真根因（三層複合失效）**：

1. **Hook 層覆蓋缺失（主因）**
   - askuserquestion-reminder-hook 只偵測 Task 派發含多個 Ticket 的場景
   - **沒有 Hook 在 PM 對話輸出文字含「A. / B. / C.」或「要選哪個？」pattern 時攔截或提醒**
   - 對話中途決策點（commit 之間的 session 決策）無任何自動預警

2. **Claude base model 行為慣性（次要）**
   - 訓練資料中 CLI 對話列 Markdown 選項讓用戶選是常見自然模式
   - 無 Hook 預警時，主動意識容易被 session context 稀釋

3. **規則落地深度不足（連帶）**
   - askuserquestion-rules.md 在 pm-rules/ 下，非自動載入
   - pm-rules/behavior-loop-details.md 的「AUQ 強制觸發」章節（拆分前位於 pm-role.md 行為循環）
   - session 中後期 context 擁擠時，主動 Read 的記憶可能稀釋

### 常見陷阱模式

| 陷阱表述 | 為何仍構成違規 |
|---------|--------------|
| 「這只是快速確認，用純文字比較方便」 | 通用觸發原則（規則 1）不因「方便」豁免 |
| 「選項很簡單用戶看一眼就懂」 | 重點不是用戶理解難度，是避免 Hook 誤判用戶自然語言回覆 |
| 「我已經在文字中說明選項了」 | 純文字選項讓用戶輸入自由文字，正是規則 3 禁止的情境 |
| 「這是提案不是決策」 | 只要等待用戶回應決定方向，就是選擇型決策 |

### 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Hook | 新增 Hook 偵測 PM 回覆文字含選項 pattern（A./B.、「要選哪個」等）並輸出提醒 | 建議實施 |
| 規則 | pm-role.md「行為循環（精簡）」AUQ 觸發速查 + pm-rules/behavior-loop-details.md AUQ 強制觸發章節 | 已實施 |
| CLAUDE.md | 頂部加入 AUQ 強制使用顯眼提醒（自動載入最終防線） | 建議實施 |
| Memory | 原則保留 memory 作為跨 session 索引 | 已實施 |
| 自我檢查 | 每次準備列選項時自問：「是否需用戶做決策？」是 → 先 ToolSearch select:AskUserQuestion → 用 AUQ | 行為準則 |

### 檢查清單（PM 對話回覆前自我檢查）

- [ ] 本回覆是否列出 2 個以上供用戶選擇的選項？ → 是 → 必用 AUQ
- [ ] 本回覆是否以「要繼續嗎？」「先做 X 還是 Y？」等問句結尾？ → 是 → 必用 AUQ
- [ ] 本回覆是否等待用戶回應決定方向？ → 是 → 必用 AUQ
- [ ] 以上任一為「是」，是否已執行 `ToolSearch("select:AskUserQuestion")`？ → 否 → 先載入再使用

### 教訓

規則 1 + 規則 3（askuserquestion-rules.md）+ 通用觸發原則都已明確要求，仍可能因「Hook 無覆蓋 + 行為慣性 + 規則稀釋」三重失效而疏失。**單一層防護不足，必須多層（Hook + 規則 + CLAUDE.md）並行**。

自我糾錯策略失效的判準：若同一 session 內同一類疏失重複 ≥ 3 次（用戶糾正或自己察覺），即為系統性落地失敗訊號，必須升級為跨 session 學習資產（error-pattern + 規則升級 + Hook 覆蓋），而非僅記錄於 session 中。

### 象限歸類

本模式的防護屬**摩擦力管理 C 象限（增加摩擦）**：列選項時強制透過 AUQ 工具增加一步操作，換取用戶回覆消除自然語言歧義與 Hook 誤判風險。代價（額外工具呼叫）遠低於收益（避免 Hook 誤判 + 對話流程不被糾正打斷）。

---

## 相關文件

- `.claude/pm-rules/askuserquestion-rules.md` — 通用觸發原則與 18 個場景
- `.claude/rules/core/pm-role.md` + `.claude/pm-rules/behavior-loop-details.md` — 行為循環章節（列選項觸發條件）
- `.claude/rules/core/tool-discovery.md` — ToolSearch 載入 deferred tool 通用機制
- `.claude/error-patterns/process-compliance/PC-014-askuserquestion-rationalization-skip.md` — 姊妹模式（合理化跳過）
- `.claude/methodologies/friction-management-methodology.md` — 摩擦力管理方法論（C 象限）
