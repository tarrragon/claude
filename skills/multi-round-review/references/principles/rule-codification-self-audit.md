# 規範化跟自審是兩種認知任務

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被「Round 3 self-application frame」引用。
>
> **何時讀**：設計 self-application reviewer prompt 時、了解為什麼需要這層 frame。

## 結論

把反模式抽象成規範卡跟在自己稿件辨識該反模式的局部實例、是兩種不同認知任務。同一個作者可以清楚寫下「X 是反模式」、同一個 batch 內已寫的稿件仍能有多處該反模式未被察覺。

| 認知任務 | 視角               | 處理動作                      | 觸發條件                           |
| -------- | ------------------ | ----------------------------- | ---------------------------------- |
| 規範化   | Outside-in（歸納） | 找 N 個 case 的共同特徵、命名 | 看到不同 case 重複出現同類問題     |
| 自審     | Inside-out（比對） | 把規範當 grep keyword、掃稿件 | 主動把卡片「判讀徵兆」套到自己文字 |

## 三個解耦機制

1. **抽象化耗用認知頻寬**：寫下反模式概念時、工作記憶被 pattern 本質 / 對比 / 邊界佔滿、不會同時掃描已寫稿件
2. **規範化視角是 outside-in**：歸納共同特徵；自審是 inside-out 從具體句子比對 pattern
3. **同 batch 主題語意 attractor**：規範化之前寫的稿件受同 constraint 拉到相似句型、規範化動作不會 retroactive 修

## Self-Application Reviewer 的 4 層機制

1. **字面 grep（keyword 層）**：把新立規範轉成 rg pattern 對 batch 跑、包含同義變體
2. **結構句型 sweep（cadence 層）**：grep 結構骨架（「先 X、再 Y、最後 Z」、「N 個案例可分別對應」）
3. **判讀徵兆 checklist（徵兆層）**：把規範卡的「判讀徵兆」段套到自己稿件
4. **Reviewer in-stream（frame 層）**：用 emergence sampling 補位 — 規範作者自己 catch 不到的

四層按介入點分層、單跑任一層會漏其他層的問題。

## 實證

一次 backend 5 章 + 1 report 卡的 review：才剛立「『看 X 如何 Y』是反模式」這條規範、同 batch 5 篇章節仍有 11 處該句型未被察覺。Round 2 reviewer 用 cadence frame grep 才 catch、修完後 Round 3 又 catch 出同義變體（「展示 X 效應 / 展示 X 邏輯」）。

證明「規範化第一次落地不可能 catch 所有同義變體、需要疊代擴張」是 path 的天然限制、不是 oversight。
