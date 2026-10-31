---
name: asd-ste100
description: "Applies ASD-STE100 controlled-language principles (one term per concept, short sentences, active voice, can/will/must) as a language-agnostic core, then loads the en or zh-TW pack by output language. zh-TW discourse structure: compositional-writing."
metadata:
  version: 1.1.0
---

# ASD-STE100 受控寫作

ASD-STE100（Simplified Technical English，簡化技術英文）是航太維修手冊的受控語言標準。本 skill 只取其中**不依附英文**的原則作為核心，再依輸出語言載入對應的 pack（依語言分開的一組規則檔，見〈依輸出語言載入 pack〉）。

## 核心原則（語言無關）

寫完一段文字，逐條對照下表。下表刻意只放這幾條，因為規則條數越多，每一條被記住、被套用的機會越低。

| # | 原則 | 對照問題 |
|---|------|---------|
| 1 | 一事一名 | 同一個概念在全文是否只用同一個詞？ |
| 2 | 一詞一義 | 同一個詞是否只承擔一個意思？ |
| 3 | 短句 | 一句是否只說一件事？太長就拆句，不刪內容（中文：目標 40 單位以內，硬上限 60 單位。一個中文字、一個英文詞各算 1 單位。一段行內程式碼（一對反引號之間的內容）不論多長都只算 1 單位。標點不算。細則見 `references/zh-TW-rules.md` 規則 8） |
| 4 | 主動語態 | 每個動作是否寫出動作者？ |
| 5 | 一句一指令 | 指令句是否一句只下一個指令，條件寫在指令之前？ |
| 6 | 情態詞三級 | 情態詞是否只用「可以」「會」「必須」這三個詞（對應 can、will、must），沒有寫進「應該」「或許」「可能」這類詞？每一個沒有證據支持的推測都寫出「未驗證」這三個字，不改寫成確定的事實。證據是指讀者可以重新查證的東西，例如指令輸出、檔案內容、測試結果。有證據的，寫出證據，不標「未驗證」。證據要寫到讀者可以照著重查，例如寫出指令或檔名 |
| 7 | 名詞串上限 | 連續堆疊的名詞是否不超過 3 個？ |
| 8 | 只留帶事實的詞 | 誇飾詞與空泛詞是否已刪？術語首次出現是否已定義？ |

## 依輸出語言載入 pack

| 輸出語言 | 讀哪些檔 | 內容 |
|---------|---------|------|
| 英文（英文 description、發佈庫 README、對外英文文件） | `references/en-rules.md` | 標準現行版 Issue 9（2025 年 1 月發行）的九節寫作規則目錄（改寫）與官方字典連結 |
| 正體中文（ticket、worklog、規則檔、回覆） | `references/zh-TW-rules.md`，再讀 `references/zh-TW-lexicon.md` | 中文句子規則（句型層）與本專案詞庫（用詞層） |

**正體中文交接文字的篇章結構**（章節安排、段落順序）不在本 skill 範圍，走 `compositional-writing` skill（`.claude/skills/compositional-writing/SKILL.md`）。本 skill 只管句子與用詞。ticket 欄位、worklog、規則檔都同時有結構和句子，所以兩者都要用，順序如下：

1. 讀 compositional-writing，排好章節與段落順序
2. 讀 `references/zh-TW-rules.md` 與 `references/zh-TW-lexicon.md`
3. 寫正文
4. 寫完後，用上面的核心原則表逐句對照

## 語言邊界

- **預設寫法**：輸出正體中文時，直接以正體中文套用核心原則與 zh-TW pack。
- **英文 STE 只用於思考過程**：可以先用英文 STE 整理想法，但寫入 ticket、log、回覆的文字必須維持正體中文（`language-constraints` 規則 1 不變）。
- **不採英文中轉**：英文中轉是指先寫英文 STE，再轉成正體中文。正體中文回報直接寫，不經英文稿。實測（2026-10-30，5 則回報情境，每則每組 3 名讀者）結果：兩種寫法的誤讀數相同，追問數相差 1 條，英文中轉沒有帶來可觀察的好處。另外，英文中轉有一項機制上的風險：英文 STE 的情態詞只有 can、will、must，沒有表示推測的詞。所以原文的「可能」在英文稿中會被改成 can（能力），推測的標記就此消失。用戶只讀中文版，看不到這處漂移。

## 合規的界線

**沒有任何工具能保證 STE 合規。** ASD 不認證任何工具。模型手上沒有完整的 STE 字典，產出只是近似 STE。對照本 skill 的規則只能降低違規，不能宣稱「已符合 ASD-STE100」。

## 範例

【原句】這個問題應該是因為設定被改掉了，或許可以考慮先把快取清掉再重新跑一次測試看看。

【改寫】推測原因（未驗證）：設定檔被改過，動作者未知。先清除快取，再重跑測試。

【對照】原則 6：刪掉「應該」「或許」這兩個詞。原句用它們表示這是推測，改寫後改用「推測原因（未驗證）」標明，不改成確定的直述句。「考慮」原本是指令，改為直接的指令。原則 4：原句沒說是誰改了設定，所以寫「動作者未知」，不自行補上一個動作者。原則 5：兩個指令拆成兩句，依執行順序排列。原則 3：一句只說一件事。

## 來源

改寫自三個 MIT 授權的社群 skill（AminBlg/SimpleEnglish、nuelcyoung/asd-ste100、sdsheeks/ste100-skill），署名與連結見 `LICENSE`。ASD-STE100 標準與字典的著作權屬 ASD，本 skill 只連結、不複製也不翻譯字典內容（<https://www.asd-ste100.org/>）。ASD-STE100 是 ASD 的註冊商標。本 skill 非官方，與 ASD 及 STEMG 無隸屬關係。

版本紀錄在同目錄的 `CHANGELOG.md`。
