# Description 是 Recall Trigger、不是文章摘要

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被 Round 1-C frontmatter 一致性維度引用。
>
> **何時讀**：審查 frontmatter `description` 欄位時。

## 結論

`description` 欄位要回答「讀者在什麼情境下需要回來讀這篇」（情境索引），而非「這篇在講什麼」（內容索引）。

## 判準

- 刪掉 description 後、只看 title 能猜出 description 全部內容 → 沒有增量 → 重寫
- description 的主詞是「本文 / 這篇 / 記錄」→ 可能是摘要不是 trigger
- 掃列表時無法在 3 秒內判斷「這篇跟我現在的問題有沒有關」→ trigger 失敗

## 類比

Claude Code skill 的 `description` 讓系統自動判斷「要不要載入這個 skill」。文章的 description 讓未來的自己在掃列表時自動判斷「要不要進去讀」。兩者降低 recall 認知成本的目的相同。

## 反例句型（摘要而非 trigger）

- 「記錄了 X 的過程」（日記式）
- 「介紹 X 的做法」（教科書式）
- 「從 X 事件整理出 Y」（報告式）

這些把 description 當後設描述（meta-description of the article），而非情境描述（description of when you need it）。

## 寫法準則：精準、無假設、無修辭

description 給人也給機器判斷，每個 token 要有資訊量。三個不要：

1. **不要操作細節**——指令/參數/步驟留內文
2. **不要假設前提**——「想不起來」「卻發現」「卻不確定」不是資訊，直接說用途
3. **不要情緒修辭**——「別被騙」「打架」「空轉」不精準，用事實陳述
4. **不要內嵌數字**——「三項」「6 段」把成員數烤進去，內文增刪就要同步改；description 描述功能不描述結構

150 字上限不是配額，短能到位就短。

## 理想 description 涵蓋的面向（至少一個）

1. 觸發條件：未來會在什麼情境下需要這篇
2. 帶走的能力：這篇給的關鍵判讀或操作
3. 省下的試錯：不讀這篇會踩什麼坑
