---
title: 註解撰寫方法論
version: 1.0.0
last_updated: 2026-04-19
---

# 註解撰寫方法論

本方法論定義程式碼註解的撰寫原則，聚焦「業務情境 vs 語法選擇」與「註解貼合抽象層級」兩大專項。**Why**: doc comment 佔據最靠近讀者視線的位置；用來解釋語法選擇浪費資源、用來洩漏實作破壞抽象。**Consequence**: 違反時讀者必須跳轉多層才能理解契約，介面與實作的解耦設計被註解抵消。**Action**: 寫 / 改 / 審查註解時依本方法論套用，配合自檢清單對照。

> **上位原則**：本方法論引用 `.claude/rules/core/document-writing-style.md` 三明示元規則（Why / Consequence / Action）作為書面文字的通用要求，不重複定義明示性。本方法論只寫註解專項細節。
>
> **完整指引**：本方法論為入口與分類，詳細範例、自檢清單、踩坑場景見 `.claude/skills/compositional-writing/references/writing-code-comments.md`。
>
> **與 quality-common 的銜接**：`.claude/references/quality-common.md` §1.6 為通用品質基線（命名/結構/常數/註解的最低要求）；本方法論為註解領域的深度展開。

---

## 適用範圍

| 註解類型 | 是否適用 | 說明 |
|---------|---------|------|
| Doc comment（`///`、`/** */`、`"""..."""`） | 是 | 函式/類別/介面/模組宣告前方 |
| 介面 / 抽象類別 docstring | 是（最嚴格） | 必須只寫契約 |
| 模組 README / 檔案頂部 header | 是 | 描述模組解決的問題 |
| Inline comment（`//`、`#`） | 是（決策視角） | 解釋「為什麼這樣做」 |
| Commit message / PR description | 否 | 屬寫作其他情境 |
| 短註解（單行解釋程式碼） | 否（語法翻譯禁令） | 應刪除或重寫為業務情境 |

---

## 核心原則

### 原則 1：Doc comment 描述業務情境，非語法選擇

> **Why**: 語法細節（`while` vs `if`、`async`、`late` 變數等）讀者看 code 即可推斷；doc comment 佔據最靠近視線的位置，應留給「無法從 code 推斷」的資訊——業務情境、觸發條件、產品後果。
> **Consequence**: 用 doc 解釋語法選擇會：(a) 重複 code 已表達的資訊（違反 DRY）；(b) 排擠業務資訊的書寫空間；(c) 維護者改 code 時 doc 與實作脫鉤。
> **Action**: 寫 doc 時自問「讀者看 code 不看註解能否推斷此資訊？」是 → 刪除或改寫；否 → 保留。

#### 業務 vs 語法區分對照

| 層級 | 註解回答的問題 | 範例 |
|------|-------------|------|
| 語法層（禁止寫進 doc） | 為什麼用 `while` 而不是 `if`？為什麼 `late`？為什麼 `async`？ | 讀 code 可推斷 |
| 業務層（doc 聚焦） | 此程式解決什麼業務問題？什麼情境觸發？不這樣做會發生什麼產品後果？ | 「印表機鎖定時，後續任務必須排隊；若跳過鎖定會導致列印頁面交錯」 |

#### 反例（語法選擇解釋）

```dart
/// 使用 while 迴圈而非 if，因為 job queue 可能有多筆任務需要依序處理
/// 使用 async 以避免阻塞 UI thread
/// 使用 late 變數因為 printer 物件在建構時尚未就緒
Future<void> processPrintJobs() async {
  while (jobs.isNotEmpty) { /* ... */ }
}
```

讀者看 code 已能推斷 `async`、`late`、`while` 的技術動機，沒有任何業務資訊。

#### 正例（業務情境聚焦）

```dart
/// 【需求】UC-008 列印佇列管理
/// 印表機一次只能處理一份任務；同時送出多份會造成頁面交錯（使用者投訴 #234）。
/// 此函式確保所有 pending 任務依送出順序處理，直到佇列清空。
/// 約束：佇列處理期間不可接受新任務（由呼叫端的鎖保證）
/// 【相依】[PrinterLockService]
Future<void> processPrintJobs() async { /* ... */ }
```

讀完可獨立理解：業務情境（印表機獨佔）、觸發條件（多份任務同時送出）、失敗後果（頁面交錯 + 投訴）、約束（外部鎖）。技術細節由 code 自明。

---

### 原則 2：Doc comment 不寫 TODO / placeholder / 「暫時這樣」

> **Why**: Doc comment 是穩定契約，描述「此程式現在保證做什麼」；TODO / placeholder / 「之後會改」屬臨時性內容，混入 doc 會讓讀者無法分辨「哪些是契約」「哪些是待辦」。
> **Consequence**: 維護者讀 doc 後建立的心智模型可能混入待辦項目；新人接手時無法判斷現行行為是否應依賴。
> **Action**: 待辦工作放 inline `// TODO(<ticket-id>): ...` 並建 ticket 追蹤；doc 描述當前真實契約（即使是「暫時策略」也寫成「當前的契約」）。

#### 內容歸位表

| 內容類型 | 應放位置 |
|---------|---------|
| 未完成工作 | Inline `// TODO(<ticket-id>): ...` + ticket |
| 暫時實作說明 | Inline comment + ticket |
| 臨時 workaround | Inline comment 指向 issue link |
| 穩定契約（即使現行為「暫時」策略） | Doc comment（描述當前契約） |

> 詳細反例 / 正例見 `writing-code-comments.md` §3.3。

---

### 原則 3：註解貼合所在抽象層級（介面 doc 不洩漏實作）

> **Why**: 程式刻意解耦（介面 vs 實作、模組 vs 模組）是為了讓讀 / 改某一層時不需通盤理解其他層。若介面 doc 主動告知「目前實作用什麼方式」，讀介面等於要先認識實作，抽象帶來的好處被註解抵消。
> **Consequence**: 介面消費端被迫知道實作細節（如「目前是輪詢」），實作層更換時消費端的心智模型失準；測試 stub 也被綁定到具體實作。
> **Action**: 介面 doc 只寫契約（做什麼、輸入輸出語意、使用情境）；指向依賴用命名引用（如 `資料來源：[IOnlineOrderService]`），讓想知道細節者跳轉、不想知道者跳過。

**核心命題**：註解的認知依賴必須跟著程式依賴一起降低。

#### 反例（介面 doc 洩漏實作）

```dart
abstract class OrderRepository {
  /// 取得訂單清單。
  /// 資料來源由實作層決定（目前為定時輪詢 [IOnlineOrderService]），
  /// 消費端不需關心來源為輪詢或推播。
  Future<List<Order>> fetchOrders();
}
```

既說「不需關心」又主動告知「目前是輪詢」，自相矛盾且洩漏實作。讀者反而**被迫知道**實作策略。

#### 正例（只寫契約 + 命名引用）

```dart
abstract class OrderRepository {
  /// 取得訂單清單。
  /// 保證按建立時間由新到舊排序。空結果回傳空陣列（不拋例外）。
  /// 資料來源：[IOnlineOrderService]
  Future<List<Order>> fetchOrders();
}
```

#### 同理適用範圍

| 位置 | 只寫什麼 | 不寫什麼 |
|------|--------|--------|
| 介面 doc | 契約（做什麼、輸入輸出語意、使用情境） | 「目前實作用什麼方式」 |
| 模組 README | 此模組解決的問題、對外 API | 內部類別結構、用了什麼演算法 |
| 函式 docstring | 解決什麼問題、輸入輸出約定 | 內部怎麼解決（除非行為細節是契約） |
| 抽象類別 doc | 子類需實作的契約、行為承諾 | 某個子類的具體實作方式 |

**例外**：行為細節本身就是契約的一部分時（如「保證冪等」「保證依序處理」「保證 O(1) 查詢」），這些細節**就是契約**，必須寫在 doc。判別關鍵：消費端會因此細節改變使用方式嗎？是 → 寫進 doc；否 → 留給實作層。

---

## 禁止的註解類別

下表列舉應在 CR 時要求修改的註解模式（在通用品質基線禁止表之上補充註解專項）：

| 類別 | 反例 | 問題 | 替代做法 |
|------|------|------|---------|
| 程式碼翻譯 | `// 將計數器加 1` | 重述 code 已表達的資訊 | 刪除或改寫為「為什麼加 1」 |
| 技術實作描述 | `// 用 Map 做快速查找` | 讀 code 可推斷 | 若效能是契約，寫「保證 O(1) 查詢」 |
| 過時 TODO | `// TODO: 加驗證`（已完成） | 誤導維護者 | 刪除 |
| **語法選擇解釋** | `// 用 while 因為要處理多筆` | 讀 code 可推斷，浪費 doc 視線位置 | 改寫為業務情境（為什麼有多筆） |
| **Doc 寫 TODO/placeholder** | `/// TODO: 之後加驗證` / `/// 暫時這樣` | 契約混入待辦 | 移到 inline + 建 ticket |
| **介面洩漏實作** | 介面 doc 寫「目前用輪詢」 | 破壞抽象，認知依賴爆增 | 改為命名引用 + 只寫契約 |
| 模糊業務描述 | `// 處理書籍相關邏輯` | 語意黑洞，grep 無法命中 | 具體描述觸發情境和規則 |
| 無索引業務邏輯 | 純技術描述，無需求編號 | 無法回溯需求 | 加 `【需求】UC-XXX` |

> 完整禁止模式清單與替代寫法：`writing-code-comments.md`「禁止模式清單」章節。

---

## 自檢清單

寫完註解後依序自問：

- [ ] 註解描述的是業務問題還是語法選擇？（後者刪除或改寫）
- [ ] 若是 doc comment，讀者不看實作能理解契約嗎？
- [ ] 若是介面註解，有洩漏「目前實作用什麼」嗎？
- [ ] 含 TODO / placeholder / 「暫時」嗎？（若是移到 inline + ticket）
- [ ] 一則註解只解釋一個概念嗎？（否則拆函式）
- [ ] 註解貼合所在抽象層嗎？（介面寫契約、實作寫策略、inline 寫決策）
- [ ] 模組 README / 函式 docstring 描述「解決什麼問題」而非「內部怎麼解決」？

---

## 與其他規則的邊界

| 規則 / 文件 | 聚焦 | 與本方法論差異 |
|------------|------|---------------|
| `.claude/rules/core/document-writing-style.md` | 書面文字三明示元規則 | 上位原則；本方法論引用，不重複定義 |
| `.claude/references/quality-common.md` §1.6 | 通用品質基線中的註解最低要求 | 基線指標；本方法論為深度展開 |
| `.claude/skills/compositional-writing/references/writing-code-comments.md` | 五大寫作原則 × 註解的完整實踐 | 完整實作指引（範例最豐富）；本方法論為精簡入口與分類 |
| `.claude/rules/core/language-constraints.md` | 繁體中文、禁用詞彙、Emoji 禁令 | 字元層規範；本方法論為論述結構 |

**DRY 銜接**：本方法論不重述明示性原則（已在 `document-writing-style.md`）、不重述五大寫作原則的完整範例（已在 `writing-code-comments.md`）；只整理註解專項的兩大核心（業務 vs 語法、抽象層級）作為入口和規範錨點。

---

## 相關文件

- `.claude/rules/core/document-writing-style.md` — 上位明示性元規則
- `.claude/references/quality-common.md` §1.6 — 通用註解標準
- `.claude/skills/compositional-writing/references/writing-code-comments.md` — 五大原則 × 註解完整指引
- `.claude/rules/core/language-constraints.md` — 字元層語言規範

---

**Last Updated**: 2026-04-19
**Version**: 1.0.0 — 從 `writing-code-comments.md` 提煉註解專項規範入口；補上業務 vs 語法、抽象層級兩大核心
