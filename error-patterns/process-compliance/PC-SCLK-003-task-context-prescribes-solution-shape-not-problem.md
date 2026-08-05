---
id: PC-SCLK-003
title: 任務 context 指定解法形態而非問題，使執行者實作弱手段並將其固化為驗收條件
severity: medium
---

# PC-SCLK-003: 任務 context 指定解法形態而非問題，使執行者實作弱手段並將其固化為驗收條件

---

## 基本資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-SCLK-003 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-07-31（screen_clock 1.4.0-W1-001.3 Context Bundle 指定「換算點須具名或註解」，使實作偏離規格已訂的型別解） |
| 姊妹模式 | PC-040（context 塞 prompt 未進 ticket）、PC-088（LLM 工具選擇偏誤） |

---

## 症狀

派發者在任務 context（Context Bundle / prompt / acceptance）中寫下的不是**要解決的問題**，而是**解決問題的形態**。執行者忠實實作該形態，於是：

1. 語言或框架已提供的強手段（型別、既有 API、框架機制）沒有進入考慮範圍
2. 弱手段（命名慣例、註解、額外測試）被實作出來，且因為寫在 acceptance 裡而被驗收為達成
3. 弱手段的存在需要額外解釋成本（註解解釋命名、測試釘住本不必存在的決策），這些成本又被視為盡責的表現
4. 後續審查若只檢視程式碼，會修掉症狀而留下 context 中的來源，下一張同類任務再長出同一形態

關鍵特徵：**沒有任何一步出錯**。執行者符合指令、測試全綠、acceptance 全勾、審查看不出違規——缺陷是在指令層被引入的。

---

## 實例（2026-07-31，screen_clock 1.4.0-W1-001）

規格 SPEC-008 已明訂介面為 `Future<void> play({required Duration duration, required Color tint})`。

PM 撰寫子票 Context Bundle 時，關注點放在「單位變更沒有機械訊號」這個真實風險（有同專案實測依據：單位或語意變更無法被現行持久化機制偵測），並寫下：

> 換算須在此發生且有明確命名或註解標示——單位變更無任何機械訊號，換算點若隱含在運算式中，日後修改者無從察覺。

另一張子票的 acceptance 寫：

> 時長類常數名含單位（如 `DurationMs`），命名本身表達意圖，不使用無單位的 duration

執行結果：實作將簽章改為 `double durationSeconds`，加上具名轉換函式 `_durationSecondsToMs`、六行解釋該函式為何具名的註解、一條釘住 `round()` 行為的測試。三者皆為達成 acceptance 的產物。

多視角審查後才發現：`Duration` 型別存在的唯一理由就是不讓「數字加單位藏在變數名裡」跨越 API 邊界。改用 `Duration` 後具名函式、六行註解、那條測試全部不需要存在，而且單位變更從「靠人讀註解」升級為「編譯器擋下」。

同一方法內的兩個參數形成對照：`tint` 收 `Color` 領域型別，`toARGB32()` 自己命名自己，零註解需求；`durationSeconds` 收裸 `double`，需要具名 wrapper 加六行註解。色彩拿到型別，時長拿到註解。

三明示角度的診斷：**Why 正確**（單位變更無機械訊號）、**Consequence 正確**（日後修改者無從察覺）、**Action 跳過了一層**——直接給出「命名或註解」兩個選項，沒有先問「有沒有型別能承載這個概念」。

加重因素：acceptance 中的「不使用無單位的 duration」在讀作變數名時成立，但字面上與型別名 `Duration` 難以區分。執行者若讀成後者，這條 acceptance 恰好禁止了唯一的正解。

---

## 根因

| 層次 | 說明 |
|------|------|
| 直接原因 | Context Bundle 的 Action 層寫的是解法形態（具名或註解），不是問題（單位變更需要機械訊號） |
| 結構原因 | 派發者為了讓執行者好執行，傾向把 Action 寫得具體。具體到指定形態時，就關閉了執行者的方案空間 |
| 放大機制 | 形態一旦寫進 acceptance 就成為驗收標準，執行者實作它會被判定為達成，偏離它反而需要舉證 |
| 遮蔽機制 | 弱手段的附帶產物（解釋性註解、防護測試）看起來像盡責，使審查者更難察覺形態本身是錯的 |

---

## 解決方案

### 防護 A：Action 層寫問題與判準，不寫形態

| 反模式 | 正確寫法 |
|--------|---------|
| 「換算點須具名或加註解」 | 「單位變更須有機械訊號。優先考慮語言是否提供承載單位的型別；若無，說明為何退回命名慣例」 |
| 「用 X 模式實作」 | 「須滿足 X 性質。若採用不同做法，於 Solution 說明取捨」 |
| 「加一個 helper 函式處理 Y」 | 「Y 的重複須消除。實作方式由執行者判斷並記錄理由」 |

判準：寫完 Action 後自問「這句話是否已經替執行者選好了方案？」是 → 改寫為性質或判準，並明示「若有更強手段請採用並說明」。

### 防護 B：先查規格既有宣告

任務涉及既有介面、資料契約或已定案設計時，Context Bundle 撰寫前必須先讀規格中的對應宣告，並在 Context Bundle 引用其位置。本案的 SPEC-008 介面宣告一直存在，四張子票的 Context Bundle 無一引用，直到 Phase 4 才被比對出來。

### 防護 C：acceptance 中的否定式約束須排除型別歧義

「不使用無單位的 X」這類否定式約束，若 X 同時是型別名與常見變數名，須明確標示所指層次。改為「變數與常數的命名不得省略單位；型別層若有承載單位的型別應優先採用」。

### 防護 D：修正時同步修 context 來源

程式碼層發現此類缺陷時，修正範圍必須包含產生它的 Context Bundle / acceptance / prompt。只修程式碼會讓下一張同類任務複製同一形態。若來源 ticket 已完成歸檔，在修正票的 Solution 中明確記錄來源位置與應改寫方向。

---

## 預防措施

以下任一出現時，回頭檢查 context 來源是否指定了形態：

- 程式碼中出現「解釋某個命名為何如此命名」的註解
- 測試在釘住一個本可由型別或框架保證的行為
- 實作加了具名 wrapper，而該 wrapper 只是呼叫一次算術或型別轉換
- 審查者指出「若改用 X 型別，這一整串都不需要」
- acceptance 條目描述的是實作形態而非可觀察性質

---

## 相關規則與方法論

- `.claude/rules/core/ai-communication-rules.md` 規則 1（意圖前置：約束附理由）與規則 3（欄位不混合）
- `.claude/rules/core/document-writing-style.md`（三明示：本模式是 Action 層失準，Why 與 Consequence 皆正確）
- `.claude/pm-rules/context-bundle-spec.md`
- `.claude/error-patterns/process-compliance/PC-040-context-in-prompt-not-ticket.md`（context 該進 ticket；本模式進一步要求 context 的內容形態正確）

---

**相關 Ticket**：1.4.0-W1-001（Phase 4 多視角評估）、1.4.0-W1-001.5（本輪修正）、1.4.0-W2-017（文字層修正，含 context 來源同步）

**Last Updated**: 2026-07-31 | **Source**: screen_clock 1.4.0-W1-001 Phase 4 多視角評估（linux 架構視角發現偏離、basil 文字視角追溯至 Context Bundle 來源）
