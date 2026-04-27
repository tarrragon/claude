# Loading / Empty / End 三狀態的區分

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `data-flow-and-filter-composition.md` 的 checklist 與「延伸閱讀」段引用。
>
> **何時讀**：設計分批 / streaming / filter UI 時、判斷該怎麼區分「還沒抓」「沒命中」「抓完無更多」三種視覺類似但語意不同的狀態。

---

## 核心原則

**「Loading」「Empty」「End」是三個語意不同的狀態、UX 必須區分。** 三者在資料層代表完全不同的事實、使用者根據哪一個決定下一步動作；共用畫面 = 使用者沒辦法決定。

| 狀態    | 資料層事實             | 使用者該採取的下一步         |
| ------- | ---------------------- | ---------------------------- |
| Loading | 還在抓、結果未知       | 等                           |
| Empty   | 抓完了、確認無命中     | 改 query / 改 filter         |
| End     | 抓完了、有結果但無更多 | 看當前結果、不要再 load more |

混為一談 = 使用者該等的時候改 query、該改 query 的時候等、該停的時候繼續點 load more。

---

## 為什麼三狀態容易被混為一談

### 視覺上類似

| 狀態    | 常見視覺          |
| ------- | ----------------- |
| Loading | 空白 + spinner    |
| Empty   | 空白 + 「無結果」 |
| End     | 結果 + 灰掉的按鈕 |

Loading 跟 Empty 都是「空白為底」、容易共用畫面。實作時如果只寫 `{{ if results }}...{{ else }}<empty />{{ end }}`、Loading 跟 Empty 會被當成同一件事。

### 資料層常常沒提供區分訊號

```js
const r = await fetch();
if (r.length === 0) showEmpty();
```

`r.length === 0` 只區分有 / 無、不區分「為什麼無」。要區分「還沒抓」vs「抓完無命中」、需要顯式追蹤 fetch 的狀態（pending / done / error），不是看 result。

End 狀態類似：`results.length > 0 && !hasMore` 才是 End、跟「還可以 load more 的當前結果」不同。

---

## 三狀態的可區分訊號

| 狀態    | 必要訊號                                                  |
| ------- | --------------------------------------------------------- |
| Loading | `fetchState === 'pending'`                                |
| Empty   | `fetchState === 'done' && results.length === 0`           |
| End     | `fetchState === 'done' && results.length > 0 && !hasMore` |

實作上至少需要：

- 一個 fetch state machine（不能只看 `results`）
- 一個「還有沒有下一批」的訊號（`hasMore` / cursor / total count）
- UI 對三種組合各畫一個樣子

---

## 多面向：三狀態的延伸

### 面向 1：Filter 加進來、狀態空間擴張

當 view 層有 filter、三狀態擴張為五狀態（Loading / Empty-raw / Empty-filter / Partial / End）。「Empty-filter」跟「Partial」是 [層錯位](./view-layer-filter-vs-source-layer.md) 的 UX 表現 — 共用同個 empty 畫面 = 使用者無法判斷「再 load more 會不會有」。

具體 UX 模板（三數字、五狀態各別 UI）見 [Pattern：誠實進度 UX](./pattern-honest-progress-ui.md)。

### 面向 2：Streaming / SSE 的「無更多」很難判斷

```js
for await (const item of eventSource) { ... }
// 跑完了還是斷線了？
```

Streaming 通常沒明確的 End 訊號 — 需要 server 主動送一個 `event: end`、或 client 用 timeout / heartbeat 判斷。否則使用者看到一段時間沒新資料、不知道是「沒了」還是「還在等」。

### 面向 3：錯誤狀態應該獨立、不混進三狀態

| 狀態    | 跟三狀態的關係              |
| ------- | --------------------------- |
| Error   | 獨立第四個狀態、需要不同 UX |
| Timeout | 通常歸 Error                |
| Offline | 獨立、需要 retry UX         |

把 Error 顯示成 Empty = 使用者誤以為「沒結果」、不會 retry。

---

## 設計取捨：UX 該怎麼呈現三狀態

### A：每個狀態獨立的 UI 元件

- **機制**：Loading 顯示 spinner、Empty 顯示 illustration + 「改 query」CTA、End 顯示「all results loaded」、Error 顯示 retry button
- **選 A 的理由**：四個狀態語意完全清楚、使用者下一步明確
- **代價**：UI 元件多、設計成本高

### B：用文字 + 細節區分、共用 layout

- **機制**：同一個 container、不同狀態填不同文字（"Loading..." / "No results for X" / "Showing all 23 results"）
- **跟 A 的取捨**：B 設計簡單、但區分性弱（使用者要讀文字才知道狀態）
- **B 才合理的情境**：簡單 UI、使用者願意讀文字

### C：只用視覺 cue（spinner / 空白）

- **機制**：spinner = loading、空白 = 沒結果、結果列表 = 有
- **跟 A 的取捨**：C 沒區分 Empty vs End vs Partial
- **C 才合理的情境**：source 沒分批、結果一次給完

### D：完全不區分三狀態（反模式）

- **為什麼是反模式**：把「使用者下一步該做什麼」這個決策丟給使用者自己猜、違反「UI 必須回答下一步問題」原則
- **看起來吸引人的原因**：UI 寫起來最簡單、不用畫 Loading / Empty / End 三版、`{{ if results }}...{{ else }}empty{{ end }}` 一行解決
- **實際發生的代價**：使用者操作不知所措、support tickets 增加、使用者信任損失（「這網站到底有沒有在 load」）

---

## 判讀徵兆

| 訊號                                                    | 該做的行動                                          |
| ------------------------------------------------------- | --------------------------------------------------- |
| UI 寫 `{{ if results }}...{{ else }}<empty />{{ end }}` | 補：Loading / Error / End / Partial 各一個分支      |
| 沒有 `fetchState` / `hasMore` 變數                      | 加 — 否則無法區分三狀態                             |
| Empty UI 上沒有「下一步該做什麼」的 CTA                 | 補：「改 query」「reset filter」「retry」等行動建議 |
| Loading 共用 Empty 畫面（都是空白）                     | 加區分（spinner vs 文字）                           |
| Streaming / async iterator 沒明確 End 訊號              | 加：server-side 送 end event、或 client timeout     |

**核心原則**：三狀態（Loading / Empty / End）是不同事實、不同 UX。共用畫面 = 把「使用者該做什麼」這個決策丟給使用者自己猜。實作要從資料層追蹤 state、不能只看 `results`。

相關概念：動態內容變動的 aria-live region 設計 — 兩者都是「狀態變動需要告知使用者」、本卡告訴的是 sighted 使用者（視覺區分）、aria-live 告訴 screen reader（廣播）。
