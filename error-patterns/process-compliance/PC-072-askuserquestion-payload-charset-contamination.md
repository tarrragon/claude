# PC-072: AskUserQuestion payload 生成時混入簡體字與 emoji

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-072 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-17（W12-001.1 執行 session） |
| 姊妹模式 | PC-064（AskUserQuestion 相關，根因互異） |

---

## 症狀

PM 主線程生成 `AskUserQuestion` 工具呼叫的 JSON payload 時，在 `question`、`label`、`description` 等文字欄位中混入：

1. **簡體字**：本應為繁體的字元被替換為簡體對應字，例如「獨立」寫成「独立」、「違反」寫成「违反」
2. **Emoji**：非必要的 emoji 符號滲入文字，例如「⚡」出現在純文字描述中
3. **錯字**：emoji 周邊或 JSON escape 附近的字元選擇錯誤，例如「⚡扯」其實意圖是「精簡」

這類問題在 Markdown 文字回覆中較少，但在 `AskUserQuestion` payload 這種需要 JSON-escape 為 `\uXXXX` 的欄位中比例顯著升高，用戶渲染後才可見，PM 自己不易察覺。

---

## 與 PC-064 的區別

| 維度 | PC-064 無意識疏失 | PC-072 字元集污染 |
|------|------------------|-------------------|
| 違反規則 | AskUserQuestion-rules 規則 1/3（該用未用） | language-constraints 規則 1/3（繁體 + 無 emoji） |
| 發生層 | 決策層（選了文字列表代替 AUQ） | 生成層（用了 AUQ 但文字內容污染） |
| 根因類 | Hook 覆蓋缺失 + 行為慣性 | token 選擇 + JSON escape 審視盲區 |
| 偵測難度 | 看回覆結構即可發現 | 需逐字檢查 unicode code point |

---

## 根本原因

### 已驗證事實

1. **Payload 內容實測**：用戶 session 明確指出「独立原子任務」「⚡扯至 ≤250 字」—— 對應 JSON payload 中的 `\u72ec\u7acb` 和 `\u26a1\u626f`
2. **規則明確存在**：`.claude/rules/core/language-constraints.md` 規則 1（繁體中文）+ 規則 3（禁用 emoji）皆為自動載入
3. **PM 已讀過規則**：本 session 啟動時 CLAUDE.md → rules/README.md → language-constraints.md 全鏈已載入

### 真根因（三層複合失效）

1. **Token 空間相鄰污染（主因）**
   - 繁體/簡體中文 token 在 Claude token pool 中相鄰
   - 生成 JSON-escape 的 `\uXXXX` 時，模型須先選中文字元再編碼
   - 長 payload（此 session 的 AUQ question + 3 個 option label + description 總計 ~800 字）中偶爾挑到相鄰簡體字

2. **JSON Payload 審視盲區（次要）**
   - JSON 中 `\u72ec` 無法憑肉眼判斷是繁是簡
   - Markdown 文字回覆有 highlight / font rendering 輔助，但 JSON payload 在生成階段只有 escape sequence
   - PM 生成後通常直接提交，很少 re-read payload 的字元層級

3. **Emoji 誤植（連帶）**
   - 當生成類似「精簡」「精選」等詞時，`\u7cbe`（精）可能被近鄰的 `\u26a1`（⚡）污染
   - 原因不明（可能與訓練資料中某些 CLI 情境的 emoji 用法有關）

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成違規 |
|---------|--------------|
| 「AUQ 是工具呼叫不是對話文字」 | language-constraints 規則 1/3 適用於**所有輸出**包含工具 payload |
| 「簡體字只是偶發，不影響溝通」 | 本專案為 zh-TW 環境，簡體字會造成渲染 / 搜尋 / 複製貼上錯誤 |
| 「Emoji 只是裝飾無傷大雅」 | 跨平台渲染一致性問題 + 違反專業性要求 + 用戶明確表達不喜好 |
| 「生成時看起來沒問題」 | JSON escape 的 `\u` 序列無法肉眼判讀字元集 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Hook | PreToolUse Hook 掃描 AskUserQuestion payload：偵測簡體字 pattern（CJK unicode 範圍對照）與 emoji（`\u26xx`、`\u27xx`、`\uD83C+`） | 建議實施（W12 後續） |
| 自檢 | 生成 AUQ payload 前自問：「所有 label/description/question 是否為純繁體 + 無 emoji？」 | 行為準則 |
| 規則 | language-constraints.md 補充「AUQ payload 特別脆弱，提交前自檢」章節 | 建議實施 |
| Memory | 記錄本失誤作為跨 session 提醒 | 已實施（配對本檔） |
| 糾錯 | 用戶指出時立即承認、解釋根因、不辯解 | 行為準則 |

---

## 檢查清單（PM 生成 AskUserQuestion 前自我檢查）

- [ ] Payload 所有 label 長度 ≤12 字元且無 emoji？
- [ ] Payload 所有 description 為純繁體，無「独/违/没/务/实/觉/决/个/隶/遗/设/长」等常見簡體字？
- [ ] Payload 所有 question 內文無 ⚡⚠️✅❌🔴🟢 等 emoji？
- [ ] 若 description 含「精簡/精選/精確」類詞彙，已確認不是誤植「⚡」？
- [ ] JSON payload 的 `\uXXXX` 未落在 emoji unicode 範圍（`\u26xx-\u27xx`、`\uD83C`+）？

---

## 檢查清單（通用回覆層）

- [ ] 生成結束後快速掃視整段文字，檢查是否有明顯簡體字（獨/為/與/關/實/決）
- [ ] 檢查是否有非必要 emoji（✅ ❌ 📝 ⚡ 🔴）
- [ ] 若發現，立即自主修正，不等用戶糾錯

---

## 教訓

1. **規則載入 ≠ 規則生效**：CLAUDE.md 已自動載入 language-constraints，PM 仍可能在 token 生成層失誤。規則文件是最後防線而非唯一防線。
2. **Payload 等工具呼叫內容與對話文字同一視之**：所有輸出（對話、JSON payload、ticket append-log、commit message）一律適用 language-constraints。
3. **用戶糾正時的正確回應**：承認 → 解釋真實根因（不是「讀到外部簡體源」這類推諉）→ 承諾防護。本 session 用戶主動問「是不是從文件讀到簡體字？」PM 正確回答「不是，是我生成 token 時失誤」，保住信任。

---

## 再現紀錄（W12-002 調查 completed 後仍再現）

| 日期 | Session 情境 | 污染字元 | 備註 |
|------|-------------|---------|------|
| 2026-04-17 W12-001.1 | 首發，AUQ label「独立」「⚡扯」 | 独/违/决/⚡ | PC-072 v1.0.0 來源 |
| 2026-04-17 W12-002 | ANA 調查過程多次復現 | 同上 | W12-002 建立 4 個子 IMP Ticket（Hook + 字串清洗）並 completed |
| 2026-04-17 W11-005 收尾 | AUQ label `\u8865 spawned_tickets` 用戶收到顯示為「补 spawned_tickets」 | 补 | **W12-002 completed 後仍再現**，防護未落實 |
| 2026-04-17 W12-001 完結（本次） | AUQ description `\u96b6\u5c6c`（本應「隸屬」）、`\u9057\u7559`（本應「遺留」） | 隶 (\u96B6)、遗 (\u9057) | **PC-072 發表後仍再現**；新建 W13-003 IMP 補強檢測清單 |

**訊號強度升級**：從「token 偶發」升級為「系統性污染持續存在」。

**解讀**：
- W12-002 雖 completed，但 4 個子 IMP Ticket（W12-002.1-.4 PreToolUse Hook / emoji 清洗 / language-constraints 範例修正）**皆為 pending 狀態**，防護層未實作
- W11-005 收尾屬「W12-002 completed 後」時間線，再現符合「調查完成但修復未落地」的推論
- 需另起 ANA 追蹤「completed ANA 下游 IMP 未實作也算污染未根除」的落差

---

## 真根因確認：H3 假設（W17-144.1.1.1.1 收斂 + 外部佐證）

W17-144 系列五層 ANA 鏈經實證收斂於 **H3 假設**：

> **模型在生成 AUQ JSON 時切換到「結構化資料 mode」，繁體 prime 被簡體中文網站 / SaaS 訓練樣本稀釋，短 label 中 token 預測偶爾挑簡體形。**

### 本專案實證（W17-144.1.1.1.1）

| 載體 | 簡體字命中率 |
|------|-----------|
| 對話正文 / commit message | ≈ 0%（本 session 12 commit msg 0 命中）|
| AUQ payload | ≈ 60-70%（本 session 9 次嘗試 18 處污染）|

差異 100x+，完全證實 AUQ-specific 機制（非普遍 token 偶發）。

### 外部佐證：Anthropic 已知 bug（同構現象）

| 來源 | 內容 | 對 H3 的支持 |
|------|------|------------|
| [anthropic/claude-code#46846](https://github.com/anthropics/claude-code/issues/46846)（OPEN, labels: area:model, bug）| Tool call（git/gh）後 Claude 切換到日文/韓文/簡中，違反 CLAUDE.md 繁體指示 | 直接同構：tool call 周邊 context 稀釋目標語言 prime |
| [#34779](https://github.com/anthropics/claude-code/issues/34779) / [#39502](https://github.com/anthropics/claude-code/issues/39502) / [#19471](https://github.com/anthropics/claude-code/issues/19471) | 同類 duplicate（廣泛現象，非單一用戶）| 證明 H3 機制涵蓋整個漢字家族（繁/簡/日/韓漢字）|
| Issue #46846 marlvinvu 評論 | 「Claude has a problem with pattern-matching ... confusion around language when classifying languages that belong to the **logographic script family**」| 揭示物理機制 — 漢字系統家族 pattern-matching 混淆，與 PC-085 codepoint 鄰近性同源 |

**結論**：H3 從「外部黑盒推論」升級為「Anthropic OPEN bug + 廣泛現象 + 已知物理機制」。本專案防護策略（hook 攔截 + detector + memory feedback）為已知機制下的最佳工程實踐，無法從專案層消除根因（屬模型內部）。

### Follow-up 追蹤

由 W17-144.2（本檔對應 follow-up tracker ticket）追蹤 Anthropic 修復進度。Issue 修復前本 PC 持續適用。

---

## 象限歸類

本模式的防護屬 **摩擦力管理 C 象限（增加摩擦）**：生成 AUQ payload 前多一步自檢增加摩擦，換取下游不需用戶反覆糾正。代價（自檢成本）遠低於收益（避免用戶信任損耗）。

若未來 Hook 層偵測實施，則可將防護降級至 **A 象限（自動護欄）**，PM 只需正常生成，Hook 在違規時攔截提示。

---

## 相關文件

- `.claude/rules/core/language-constraints.md` — 規則 1（繁體）+ 規則 3（emoji）
- `.claude/rules/core/document-format-rules.md` — 規則 1（禁用 emoji）呼應
- `.claude/pm-rules/askuserquestion-rules.md` — AUQ 使用通用規則
- `.claude/error-patterns/process-compliance/PC-064-pm-text-options-without-askuserquestion.md` — 姊妹模式（該用 AUQ 未用）
- `.claude/methodologies/friction-management-methodology.md` — C 象限摩擦力

---

**Last Updated**: 2026-05-05
**Version**: 1.2.0 — W17-144 五層 ANA 鏈收斂於 H3 假設「AUQ JSON 結構化資料 mode 繁體 prime 弱化」+ 外部佐證 Anthropic Issue #46846 / 3 duplicate（已知 OPEN bug，logographic script family pattern-matching confusion）；新增 W17-144.2 follow-up tracker
**Version**: 1.1.0 — 新增 W12-001 完結 session 再現紀錄（隶/遗 兩字元），檢查清單補充常見簡體字
**Source**: 用戶即時指出 session 中 AUQ payload 的簡體字「独立」與 emoji「⚡扯」失誤
