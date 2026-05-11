# False sense of security 是高 stakes 寫作的主要失敗模式

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 `references/auditing-articles.md` 跟 `references/principles/writing-multi-pass-review.md` 的「stakes-conditional 追加輪」段引用。
>
> **何時讀**：寫高 stakes 內容（資安 / concurrency 正確性 / distributed consistency / financial / medical 等 reader 照做後錯誤不可逆的領域）、或對既有高 stakes 內容跑 reviewer-style audit 時、用本卡定位主要要 catch 的失敗模式。

---

## 結論

**高 stakes 內容的主要失敗模式不是「reader 學不到」、是「reader 以為學到了」。** 學不到是 active failure（reader 知道自己沒會、會去查補）、以為學到是 silent failure（reader 跳過驗證、直接 implement、破口在生產系統累積）。

| 失敗模式     | Reader 狀態            | 後續行為                 | 系統端後果                       |
| ------------ | ---------------------- | ------------------------ | -------------------------------- |
| 讀不懂       | 知道自己沒會           | 去查標準 / 問人 / 重學   | 學習延遲、實作前找補             |
| **以為學會** | 不知道自己沒會         | 跳過驗證、直接 implement | **生產破口、事件偵測前無人警覺** |
| 讀懂並會驗證 | 知道邊界、知道何時失效 | 實作 + 持續驗證          | 安全 baseline 達成               |

中間那行（false sense of security）是高 stakes 寫作要消滅的目標。**比沒讀過更糟**——沒讀過會去查，讀過含糊版會跳過。

---

## 識別 false-sense 句子的判準

每段論述跑這個反向驗證：

1. **Reader 讀完會在心裡形成什麼結論？**（例：「我做了 X mitigation 就安全」）
2. **這個結論能不能拆成可驗證子句？**
   - 對什麼具體 threat / failure mode 安全？
   - 在什麼 deployment / runtime 條件下成立？
   - 什麼前提失效時這個保護失效？
   - 跟其他既有實作疊加會不會 silent 干擾？
3. **如果不能拆、補哪一塊讓它能？**

走完三步、原文若仍是「讀完會 false confidence」、必須改寫——加 contrast、加 boundary、加前提、或拆成更小的可驗證單元。

---

## 訊號詞清單

下列詞彙在高 stakes 內容是 high-risk、預設要被 audit：

| 訊號詞                     | 為什麼是 risk                                                              |
| -------------------------- | -------------------------------------------------------------------------- |
| 「能擋」「能防」「可避免」 | 沒指定擋什麼、預設讀者會自行補完整 threat space、實際只擋作者腦中的 subset |
| 「最佳實踐」「業界標準」   | 隱含 universal validity、跳過 context-dependence                           |
| 「使用 X 即可」            | 把 mitigation 當成銀彈、跳過邊界跟疊加                                     |
| 「業界常用」「常見做法」   | Appeal to convention、不是 mitigation 對位驗證                             |
| 「應該足夠」「通常足夠」   | 沒給「足夠」的定義、reader 會用最寬鬆詮釋                                  |
| 「有效」「有用」           | 對什麼 threat 有效？reader 預設「對所有」、實際只對 subset                 |

每出現一個訊號詞、檢查段落有沒有對應的 boundary 補述；沒有 → 補完或改寫。

### Methodology-layer 訊號詞（多 layer false sense）

False sense of security 不只發生在 mitigation layer——還會在 **methodology / framework / process layer** 出現。Reader 讀完「我們有方法論 / 有路由系統 / 有 maturity stage / 有 release gate / 有 tripwire」、形成「**有 system / framework = 安全**」結論、跳過驗證下游 control 是否真擋 threat / failure mode。

| Layer             | 失敗模式                               | Reader 形成的 false 結論                            |
| ----------------- | -------------------------------------- | --------------------------------------------------- |
| Mitigation layer  | 上一張表訊號詞                         | 「我做了 X mitigation 就安全」                      |
| Methodology layer | 把 framework / routing 當成已治理 risk | 「我們有 routing system / framework 了 = 風險可控」 |
| Process layer     | 把 gate / checklist 當成 risk reduce   | 「跑了 release gate / 例外有 tripwire = 安全」      |
| Maturity layer    | 把 stage 等級當成 mitigation 強度      | 「我們在可稽核閉環 stage = 風險低」                 |

Methodology-layer 訊號詞清單：

| 訊號詞                                    | 為什麼是 risk                                                                                          |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 「有方法論」「有 framework」              | 方法論不擋 threat、是把 threat 路由到對應控制面、實際擋 threat 仍靠下游控制                            |
| 「能路由」「decision system」「分類治理」 | Routing 提供分類、不提供 mitigation；reader 不點下游控制可能停留在 routing layer                       |
| 「有 maturity stage / process」           | Maturity 是 process metric、不等於 risk reduction；mature process 可在某 deployment 條件下 silent 失效 |
| 「跑了 gate / 過了 checklist」            | Gate / checklist 通過 ≠ control 真擋 threat、可能是 ceremonial false sense（字面層 vs 行為層 ceiling） |
| 「設了 tripwire」「有重評估機制」         | Tripwire 沒 quantify（threshold / cadence / owner）等同沒設                                            |
| 「能治理」「可控」「閉環」                | 治理 / 閉環是流程語、reader 預設「閉環 = 風險擋住」、實際閉環只是流程 cycle、不保證 mitigation 強度    |

驗證方式跟 mitigation layer 同：reader 讀完能否拆 falsifiable 子句？能不能列出**具體下游 control + 各自 boundary + 各自驗證訊號**？不能 → methodology-layer false sense 產地、補「下一步路由 / 必連控制面 / 各 control 的 verification check」。

---

## 危險 vs 安全寫法對照

跟 [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md) 同骨——便利寫法（universal-flavored）跟對齊意圖（讓 reader 能反向驗證）反向。

| 危險寫法                      | 安全寫法                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| 「使用 HTTPS 保護傳輸」       | 「使用 HTTPS 防中間人讀取、不防 endpoint 信任失效（CA compromise / cert pinning bypass）」 |
| 「JWT 用簽章驗證身分」        | 「簽章驗 token 沒被竄改、不驗 token 沒被竊取（XSS / 明文存儲）、需配 rotation + 短 TTL」   |
| 「rate limit 擋 brute force」 | 「per-IP rate limit 擋單來源連續嘗試、不擋分散來源（botnet / credential stuffing）」       |

差別在 reader 實作時的覆蓋判斷——前者讀完跳過 endpoint 驗證、後者讀完知道要補。

---

## 為什麼 silent failure 比 noisy failure 貴

Noisy failure（reader 讀不懂、實作報錯、被 reviewer 抓到）發生在開發前期、修復成本是 commit 等級。silent failure（reader 以為對了、ship 進生產）發生在生產系統、可能等到事件才被發現、修復成本跳到事件處理 + 通報 + 復盤 + 信任修復。

跟 [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) 同病——該卡的核心是「驗證工具的字面層 vs 行為層 ceiling」：CI 字面層通過不代表行為層沒問題、但 CI 通過會建立 false confidence、阻止後續行為層檢查。本卡是該模式在「**內容寫作 vs reader 實作**」的具體展現：含糊的論述提供字面 mitigation、reader 讀完建立 false confidence、阻止實作端的行為層 verify。

---

## 教學擴散讓單篇 silent gap 變系統性 risk

含糊的高 stakes 內容若被多團隊引用 / 翻譯 / 二次教材化、原始 misinterpretation pattern 會被批量繼承。攻擊者 / failure event 只需找一次 misinterpretation、就可以利用所有 implementation。一般教學的錯誤是個別 reader 的學習成本、高 stakes 教學的錯誤是 risk surface 集體放大。

---

## 適用範圍與邊界

- **適用**：資安內容（auth / crypto / 防護 / 標準引用 / mitigation 設計）、concurrency 正確性 claims、distributed consistency claims、financial / medical 計算、任何「reader 照做後錯誤不可逆」的內容
- **不適用**：純概念說明 / 歷史背景內容（reader 不會直接照做）、研究探討文章（reader 預期自行驗證）、一般技術教學（layout / refactor / debug、錯誤可逆）
- **邊界**：「消滅 false sense of security」≠「把所有邊界寫到極致」——是讓 reader 讀完能列出邊界、不是讓 reader 讀完什麼都不敢做。Audit bar 是 verifiability、不是完備性
- **過度警覺反例**：對所有句子都打防呆 disclaimer、把高 stakes 內容寫成 legal-style 「在 X 條件下、若無 Y 前提、且不考慮 Z 路徑、可能可以」——reader 讀不到任何 actionable 結論、退化成「什麼都不要做」式 paranoia、跟 silent failure 一樣有害

---

## 跟其他 principle 的關係

| 原則                                                                                                | 關係                                                                                                            |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | 本卡是該卡在內容寫作維度的具體化——含糊論述是字面層 mitigation、reader 行為層 verify 被 false confidence 阻止    |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 含糊敘述是寫作最便利選擇、跟「讓 reader 實作正確」反向、本卡是該卡在 silent failure 維度的展現                  |
| [risk-asymmetric-audit-standard](./risk-asymmetric-audit-standard.md)                               | 本卡是該卡定義的「為什麼要 verifiability-first」的主要失敗模式——audit standard 升級的目標就是消滅 false sense   |
| [writing-multi-pass-review](./writing-multi-pass-review.md)                                         | 本卡是「stakes-conditional 追加輪 E」的主軸——輪 E 的 5 sub-check 都在回答「false sense of security 在哪裡產生」 |
