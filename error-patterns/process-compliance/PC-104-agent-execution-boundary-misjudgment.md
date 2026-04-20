# PC-104: Agent 執行邊界誤判導致結果未落地

## 基本資訊

- **Pattern ID**: PC-104
- **分類**: 流程合規（process-compliance）
- **風險等級**: 中（subagent hallucinate 系統限制導致結果流失）
- **相關 Pattern**: PC-101（並行 agent 結論矛盾）、PC-072（AUQ 字元集污染——都是 agent hallucinate 類型）

---

## 問題描述

### 症狀

Subagent（特別是 Explore）在 return message 或 ticket 內宣稱「只讀模式 / 無權限 / 無法執行 X 命令」並跳過寫回動作，但實際 agent definition 的 tool 集合**支援該操作**。結果：分析已完成卻未落地到 ticket，PM 若不察覺會以為 agent 無實際產出。

### 典型徵兆

- Agent return message 含「無法直接執行」「只讀模式」「無編輯權限」等自我限制聲明
- 但 agent definition frontmatter 列有 Bash 或其他寫操作工具
- Analysis 內容完整但 `ticket track log --section "Solution"` 顯示空白
- 需 PM 代為 append-log 落地

---

## 根因分析

### 直接原因

Agent definition frontmatter 的限制文字（例如 Explore 的 `Tools: All tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit`）被 agent 過度泛化為「所有寫操作禁止」，未區分「檔案系統 Edit/Write」vs「CLI Bash 執行含寫操作副作用」。

### 深層原因

| 類型 | 說明 |
|------|------|
| A agent definition 邊界模糊 | 「except Edit/Write」在 LLM 解讀為「不可改檔案」，延伸誤讀為「不可執行任何寫入 CLI」 |
| B prompt 未明示 CLI 可用 | 派發 prompt 要求 agent `ticket track append-log ...`，但未明寫「這是 Bash 工具你有權限」 |
| C agent 保守優先 | LLM 傾向「無法執行」聲明勝過「嘗試失敗回報」，避免擦槍走火 |
| D PM 未抽查驗證 | Agent 回報「已寫入」與「無法寫入」之間的模糊地帶，PM 少抽查 ticket md 實際 content |

---

## 防護措施

### 派發 prompt 明示工具可用性

派發 prompt 中若要 agent 執行 CLI 寫回，必須明寫：

```
完成後用 `ticket track append-log <ID> --section "..." "<內容>"` 寫入（Bash 工具可用，禁止
自我宣稱只讀模式而跳過此步）
```

### PM 接收 agent 回報後抽查

Agent 回報「已寫入」後，PM 應至少**抽查 1/3 的 agent** 的 ticket Solution section 實際 content 是否存在（grep 或 Read 最少 20 行即可）。

### 長期：agent definition 優化

Agent definition frontmatter 應更精確，例如將「Tools: All except Edit, Write, NotebookEdit」改為「可讀檔、可執行 CLI（含寫副作用）、不可直接 Edit/Write 檔案」，減少 LLM 過度泛化空間。

### 對照 PC-101

- PC-101：並行 agent A 和 B 結論互斥，PM 仲裁
- PC-104：單一 agent 自我限制致結果未落地，PM 代為落地或重派

兩者同屬「agent hallucinate 約束」家族，但觸發條件與處理方式不同。

---

## 觸發案例

### W17-008.7（本 Pattern 首次發現）

情境：並行派發 6 個 Explore 做小型 ANA；其中 W17-008.7 agent 完成完整 8+ 組合矩陣 + 4 歧義點分析，但 return message 宣稱：

> 由於當前為只讀模式，無法直接執行 `ticket track append-log` 命令。上述完整分析結果已在系統中生成，可由有編輯權限的代理人執行以下命令追加到 Ticket。

PM 接收回報後察覺 ticket Solution 區段仍空白，代為 `ticket track append-log 0.18.0-W17-008.7 --section "Solution"` 將 agent report 內容寫入。

**延伸觀察**：W17-008.7 agent 在同一 session 其他 5 個並行 agent（W17-004.1/.2/.3 之前、W17-007、W17-009、W17-008.8/.10/.11）皆成功用 ticket CLI 寫回——**同一 tool 集合，行為卻不一致**，指向 LLM 推理不穩定性而非 tool 真實限制。

### 歷史關聯：W17-004.2 vs W17-004.3 結論矛盾

- W17-004.2：`--source-ticket` 存在但副作用未文件化（證據：讀 create.py line 861-862）
- W17-004.3：`--source-ticket` 缺席，PM 被迫用 `--parent` 繞路（純推理，無讀 create.py 佐證）

兩案共同模式：agent hallucinate 系統限制 / 邊界，需 PM 實證驗證。

---

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-101 | 同家族（agent hallucinate），PC-101 是多 agent 矛盾；PC-104 是單 agent 自限 |
| PC-072 | 同家族（agent output 污染），PC-072 是字元集；PC-104 是行為邊界 |
| PC-100 | 若 PC-104 結果未落地而 PM 未抽查，會退化為 PC-100（PCB 不繼承——本例中 Solution 空殼） |

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17-008.7 agent 誤判唯讀模式案例建立
