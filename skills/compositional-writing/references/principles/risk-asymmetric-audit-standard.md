# 審查標準要對應風險不對稱（Risk-Asymmetric Audit Standard）

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 `references/auditing-articles.md` 跟 `references/principles/writing-multi-pass-review.md` 的「stakes-conditional 追加輪」段引用。
>
> **何時讀**：判斷某內容是否需要追加 epistemic rigor pass、或對既有內容跑 audit 前、用本卡決定 audit bar 拉到哪個層級。

---

## 結論

**內容的 audit 標準不該由「reader 讀不讀得懂」決定、該由「reader 照做後出錯的代價」決定。** 讀懂是學習端的成本、出錯的代價可能落在生產端、兩者級數不同。

| 教學類型                                  | 寫不清楚的代價                  | 代價發生位置 | 可逆性               |
| ----------------------------------------- | ------------------------------- | ------------ | -------------------- |
| 一般工程教學（layout / refactor / debug） | reader 學不會、要重學           | 學習端       | 可逆（再學一次）     |
| **高 stakes 內容**（資安 / 並行 / 醫療）  | reader **以為**學會、實作留破口 | 生產端       | **不可逆**（被利用） |

級數不對稱的後果：一般教學的 audit bar 是「reader 能不能拿到 reasoning」、高 stakes 教學的 audit bar 必須升級為「reader 照做後的實作可不可被驗證為無破口」。預設 reader 會 implement、不只 read。

---

## 高 stakes 內容的識別判準

四個訊號之一觸發、即視為高 stakes、audit bar 拉到 verifiability-first：

1. **錯誤不可逆**：reader 照做後若有 bug、無法靠後續 commit 修復（破口已被利用 / 資料已被損毀 / 患者已被誤治）
2. **錯誤系統層**：bug 影響不限於該 reader、會傳到其他 user / 系統 / 信任鏈（auth bypass 影響全 user / 弱 crypto 影響全資料）
3. **錯誤 silent**：bug 不會在開發 / 測試階段被 catch（false sense of security 主要產地）
4. **錯誤高擴散**：reader 跟著教 / 翻譯 / 二次教材化、misinterpretation 被批量繼承

四訊號代表領域：

- 資安（auth / crypto / 防護 / 標準引用 / mitigation 設計）
- Concurrency 正確性 / memory model claims
- Distributed consistency / consensus 演算法
- Financial 計算 / accounting / settlement
- Medical / safety-critical 計算
- 任何「reader 照做後錯誤不可逆 / 系統層」的內容

---

## Audit bar 升級的兩個維度

### 維度 1：從 readability-first 升級到 verifiability-first

| 階段   | 一般教學                 | 高 stakes 教學                                                   |
| ------ | ------------------------ | ---------------------------------------------------------------- |
| 草稿   | 寫得通、有 reasoning     | + 列 scope 範圍 + 列「不在範圍內的 case」                        |
| Review | 跑 5 輪基本 frame review | + 跑輪 E（epistemic rigor）                                      |
| 引用   | 引用即可                 | + 標版本 + 驗證引用句意沒被扭曲 + 確認當前版本仍是 best practice |
| 完稿   | reader 讀完能套用        | + reader 實作後的正確性可被反向驗證                              |

### 維度 2：從評語式 review 升級到 ship-gate tier 化

一般教學 review 給「找到問題、找時間改」flat list 即可、團隊有空再修。高 stakes 內容 review 必須給 ship-gate tier：

- **Accept**：無 weakness 或在容忍範圍
- **Minor revise**：補 boundary / contrast / 版本標記類小改、不阻擋 ship
- **Major revise**：結構性 false sense、需重寫、ship 前必須修
- **Withdraw**：教錯主動誤導 reader、保留 = 增加生產系統 risk、必須移除或全換

withdraw tier 是高 stakes 跟一般內容的關鍵差異——一般 review 沒有「保留 = 增加 risk」的硬決策、高 stakes 必須有。

---

## 為什麼一般 audit standard 在高 stakes 場景失效

**Silent failure 比 noisy failure 貴**：一般教學寫不清楚 = noisy（reader 知道沒會、會去查）；高 stakes 寫不清楚 = silent（reader 以為對了、跳過驗證）。一般 audit 抓得到 noisy issue（typo、絕對主義、grep）、抓不到 silent issue（false sense of security、defense theater、context 沒寫）——因為 silent issue 在表面看不出來、要用 reviewer 視角反向 verify 才浮現。

**教學擴散讓單篇 silent gap 變系統性 risk**：含糊高 stakes 內容被多團隊引用 / 翻譯 / 二次教材化、原始 misinterpretation pattern 被批量繼承。攻擊者 / failure event 只需找一次 misinterpretation、就可以利用所有 implementation。

**事故發生後 root cause 無法 trace**：含糊原文難以判定是「教學錯」還是「reader 誤解」——含糊本身就是 ambiguity 來源、責任邊界模糊。verifiability-first 讓「實作 vs 教學」可被 1:1 對照。

---

## 適用範圍與邊界

- **適用**：撰寫或 audit 高 stakes 內容（資安、concurrency、distributed、financial、medical 及任何錯誤不可逆領域）
- **不適用**：純概念說明（reader 不會直接照做）、實驗性 / playful 內容（reader 預期自行驗證）、一般技術教學（錯誤可逆）
- **邊界**：「verifiability-first」≠「百科全書化」——不是把所有邊界都寫滿、是讓 audit 標準對應風險量級、必要時引用更深的標準文件而不重述
- **過度應用反例**：把每個高 stakes 句子都加滿 boundary / threat / context 補述、文章變密度爆炸、reader 讀不下去——audit 標準對應風險量級、低風險段落（背景介紹 / 概念 anchor）保持簡潔、把 verifiability 投資集中在 mitigation / 標準引用 / 實作 step 段落

---

## 跟其他 principle 的關係

| 原則                                                                                                | 關係                                                                                                                |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| [false-sense-of-security-as-primary-failure](./false-sense-of-security-as-primary-failure.md)       | 本卡定義「為什麼要 verifiability-first」、該卡定義「audit 主要要找什麼」；兩卡是動機 → 目標的因果鏈                 |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | 本卡是該卡 ceiling pattern 的高風險版本——高 stakes 內容 stop at 字面 audit 的代價是不可逆生產破口                   |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 高 stakes 寫作最便利（通用敘述 / 省略邊界 / 不標版本）跟意圖對齊（precise threat / boundary / standard）反向        |
| [writing-multi-pass-review](./writing-multi-pass-review.md)                                         | 本卡是 multi-pass review 的「stakes-conditional 追加輪 E」啟動判準的依據——高 stakes 識別出來 → 觸發 epistemic rigor |
