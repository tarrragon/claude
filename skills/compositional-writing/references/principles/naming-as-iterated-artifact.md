# Naming 是 iterated artifact：第一個名字幾乎不對、四輪 review 才收斂

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 SKILL.md 第 6 原則「Multi-pass Review」引用為「Naming 是這條原則最容易跳的子場景」、被 `references/writing-code-comments.md` 在「Naming 子場景：四輪 review」段引用。
>
> **何時讀**：要為變數 / 函式 / 檔名 / slug / API endpoint 命名時、或察覺命名一直在改、想理解「重命名是常態還是失敗」。

---

## 結論

第一次寫的名字幾乎都不對 — 不是因為命名能力不夠、是因為**第一版命名只能基於「寫的當下看到的 context」**、而正確的名字需要看到「未來所有 call-site / grep 結果 / 重構場景」。

命名的正確設計是 **iterated artifact**：寫 → re-read → 改 → 再 re-read → 收斂。每輪用不同 frame：

| 輪  | Frame           | 抓什麼                                         |
| --- | --------------- | ---------------------------------------------- |
| 1   | 第一版          | 把概念變字串                                   |
| 2   | Grep-ability    | 能單次 grep 命中嗎？跟其他 entity 名字不撞嗎？ |
| 3   | Cross-call-site | 從 caller 角度看、名字暗示的契約對嗎？         |
| 4   | Impl 洩漏檢查   | 名字洩漏了 impl 細節嗎？換 impl 名字會錯嗎？   |

每輪可能 catch 到「上一輪沒看到」的問題、迫使重命名。**接受重命名是命名工作的常態、不是失敗**。

---

## 為什麼第一版幾乎不對

寫第一版時、認知資源都在「概念是什麼」、剩下的給命名只夠：

- 看到當前 function 在做的事 → 命名只反映當前
- 不知道未來會有 N 個 call-site → 沒考慮一致性
- 不知道未來會有 grep / refactor → 沒考慮 unique-ness
- 不知道未來會換 impl → 命名容易洩漏現在的 impl 細節

第一版命名是**對「現在的 context」過度擬合**。下一輪 review 換 frame 才能看到擬合方向之外。

---

## 四輪 review 的具體 checklist

### 輪 1：第一版

- [ ] 名字反映「做什麼 / 是什麼」、不是「怎麼做」
- [ ] 動詞 / 名詞符合語言慣例（function 動詞、value 名詞）
- [ ] 不超過 4 個單字（長 ≠ 清楚）
- [ ] 跑得到 next step、不在這輪糾結

### 輪 2：Grep-ability

- [ ] `grep -r "<name>"` 能命中目標、不會被別的 entity 蓋過
- [ ] 跟 framework / library reserved name 不撞（避免 `data`、`type`、`value` 等過泛）
- [ ] 名字不是其他名字的子字串（`get` 會匹配 `getName` `getUser`...）
- [ ] 中英混合場景下、英文部分能 grep（不要用 `處理器handler` 這種 mixed）
- [ ] 縮寫慎用（`usr` `cfg` `mgr` 增加 grep 失敗率）

### 輪 3：Cross-call-site 一致性

- [ ] 從 caller 角度看、名字暗示的契約對嗎？
- [ ] 跟同 module 其他類似 entity 命名格式一致嗎？（`getUser` vs `fetchUser` 不該混用）
- [ ] 同一個概念在不同 file 用同名嗎？（不該 `userId` / `user_id` / `uid` 三個並存）
- [ ] 動詞時態一致嗎？（`fetched` vs `fetching` vs `fetch` 對應狀態 / 動作 / 命令、不該混用）

### 輪 4：Impl 洩漏檢查

- [ ] 名字含 impl 細節嗎？（`fetchUserViaSql` ≠ `fetchUser`、後者較好）
- [ ] 換 impl 後名字還對嗎？（`cacheGetUser` 改成走 DB 後名字錯了）
- [ ] 名字洩漏 data structure 細節嗎？（`userArray` ≠ `users`、後者不綁 array）
- [ ] 介面層名字 vs 實作層名字區分嗎？（介面用「做什麼」、實作用「怎麼做」可加細節）

---

## 套用到不同命名場景

### 變數 / 函式

完整跑 1-4 輪。

額外注意：

- **作用域** — 越窄作用域越可短（loop counter `i`、close-up var `tmp`）；越寬作用域越要明確
- **類型暗示** — boolean 用 `is` / `has` / `should` 開頭

### 檔名 / module

跑 1-4 + 加：

- **層級表達** — 檔名能否反映在 directory 結構中的位置？
- **避免 `utils` / `helpers` / `common`** — 這類是「不知該叫什麼」的訊號、強制再過一次輪 1-4

### URL slug / route

跑 1-4 + 加：

- **SEO** — 跟 search query 的 substring match 對齊
- **kebab-case 一致**
- **不含 stop words**（`the`、`a`、`is`、`of`、`with`、`and`）— 跟搜尋引擎 stemming 對齊

### API endpoint / DB column

跑 1-4 + 加：

- **跨 service 一致性** — 同一概念在 client / server / DB 用同名（避免 `user_id` / `userId` / `uid` 跨 layer 不一致）
- **不可變更性** — DB column / API endpoint 改名成本極高、輪 1-4 多跑幾次值得

---

## 反模式：放棄重命名

| 反模式                                                  | 後果                                                    |
| ------------------------------------------------------- | ------------------------------------------------------- |
| 「先這樣、之後再改」                                    | 結構性跳過 — 永遠不改                                   |
| 「重命名 PR 風險高、別做」                              | 累積成 cognitive debt、後續 onboarding / debug 成本爆炸 |
| 「IDE 會自動重命名、不用想清楚」                        | IDE 改不到 doc / commit / chat 引用                     |
| 用 `data` `value` `type` `info` `obj` 含糊命名          | grep 失敗率高、自帶 false-match                         |
| 用語言不一致的 `處理 handler`                           | 中英混雜、grep 兩邊都失敗                               |
| `tempVar1` `tempVar2` 流水號                            | 看不出是什麼、純佔位                                    |
| `getUserById` 名字洩漏 query strategy                   | 換成 cache hit 後名字錯了                               |
| 複數同義詞並存（`fetch` / `get` / `load` / `retrieve`） | caller 不知選哪個                                       |
| 介面命名洩漏 impl（`HashMapUserStore`）                 | impl 換 RedisStore 後 caller 跟著改                     |

---

## 何時可以跳輪

| 情境                             | 可跳輪                   |
| -------------------------------- | ------------------------ |
| Loop counter / 即時 close-up var | 只跑輪 1                 |
| Test code 內部 helper            | 跑輪 1 + 4               |
| Temporary script / one-off       | 1 + 2                    |
| 跨 team API / DB schema          | **每輪都跑、跑兩遍**     |
| Public library / SDK             | **每輪都跑、跑兩遍**     |
| Production-facing URL / endpoint | **不可跳、改名成本極高** |

兩極：作用域越窄越可省、跨邊界 / public 越要 multi-pass。

---

## 跟其他抽象層原則的關係

| 原則                                                                                                | 關係                                                                                               |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [writing-multi-pass-review](./writing-multi-pass-review.md)                                         | 本卡是該卡輪 4（Grep-ability / 命名）在 naming 場景的特化                                          |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | 命名 lint（max length、case style）只擋字面、grep-ability / 一致性 / impl 洩漏靠 multi-pass review |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 第一版命名是「容易寫」、不是「對齊意圖」、需要重命名                                               |
| [methodology-multi-pass-embedding](./methodology-multi-pass-embedding.md)                           | 命名的多輪設計同樣要結構性嵌入、不是「最後檢查一下命名」                                           |

同概念跨 layer 用同名 = naming SSOT、不該允許多版本同義。

---

## 判讀徵兆

| 訊號                                    | 該做的事                                             |
| --------------------------------------- | ---------------------------------------------------- |
| 第一次想到的名字直接用了                | 跑輪 2-4、預期會改                                   |
| `data` `type` `value` `info` `obj` 出現 | 含糊命名、強制重新命                                 |
| `utils` / `helpers` / `common` module   | 「不知該叫什麼」訊號、重新分類                       |
| Grep 命中太多無關結果                   | 名字太短 / 太泛、重命名加 prefix                     |
| Caller code 看 callsite 不知契約        | 介面名字洩漏不夠、補強或改名                         |
| 重構後類型 / impl 換了名字沒換          | 命名洩漏 impl、重命名                                |
| 同概念出現 ≥ 2 個名字                   | 違反 SSOT、選一個改另一個                            |
| 重命名 PR 被 reject「沒必要」           | 文化沒接受 naming 是 iterated、補 reviewer education |

**核心**：命名是 **iterated artifact**、不是 single-shot 動作。第一版基於狹窄 context 幾乎必錯。**接受 N 輪 review 跟 K 次重命名是常態**、命名品質會提升一個量級。試圖一次寫對 = 第一版 ship 出去 = 後續長期付 cognitive 成本。
