# 字面攔截 vs 行為精煉：驗證手段跟錯誤層次的對齊

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段（#82）引用、是說明「playwright 測試是字面驗證、抓不到 selector 設計錯這類行為錯誤、需要 multi-pass review 配合」的根據。
>
> **何時讀**：想加 hook / lint 防某個重複出現的問題時、先檢查那是字面錯誤還是行為錯誤；或察覺規則一直補例外、想理解 ceiling 訊號何時改用 multi-pass review。

---

## 結論

驗證手段（hook / lint / CI / review / spiral / test / production observation）有不同的「錯誤偵測粒度」、必須跟**錯誤的層次**對齊：

| 錯誤層次 | 例子                                               | 適合手段                                    | 不適合手段                     |
| -------- | -------------------------------------------------- | ------------------------------------------- | ------------------------------ |
| 字面     | typo、缺 field、syntax 錯、檔案沒 frontmatter      | hook、lint、type checker、schema validation | multi-pass review（過殺）      |
| 行為     | 推薦騎牆、yes/no collapse、思考偏差、judgment 錯位 | multi-pass spiral、review、dogfood          | hook（catch 不到、假裝有保護） |

「攔截」這個動作預設**已經知道錯誤的形狀**（hook 寫死規則 = 已知錯誤）。**真正會出錯的是「不知道形狀」的錯誤** — 那需要多輪 review / spiral 收斂、不是即時攔截。

---

## 為什麼 hook 對行為錯誤無能為力

Hook / lint / type checker 的本質是 **字串匹配 / structural check** — 看得到形狀、看不到意圖。所以：

- ✅ 抓得到「commit message 沒含 issue 號」 — 字面 pattern
- ✅ 抓得到「test file 沒對應 source file」 — 結構檢查
- ✅ 抓得到「YAML frontmatter 缺欄位」 — schema check
- ❌ 抓不到「這個推薦不夠明確、騎牆」 — 需要理解語意
- ❌ 抓不到「決策 collapse 到 yes/no、漏五維」 — 需要判斷意圖
- ❌ 抓不到「思考路徑跳過 RED phase」 — 需要追溯 reasoning
- ❌ 抓不到「過度疊加策略、超過必要」 — 需要 judgment

**Hook 試圖用字串規則模擬語意檢查 = 規則永遠 over-fit 或 under-fit**：寫太嚴 → 大量 false positive 把好的也擋掉、寫太鬆 → 行為錯誤照樣通過。

---

## 反模式：用 hook 蓋行為錯誤的代價

### False confidence 比沒保護更危險

寫了 hook 之後、心理上會覺得「有保護」。實際上 hook 只擋字面、行為錯誤照常發生 — 但作者不再警覺、因為「CI 通過了應該沒事」。

對比沒 hook 的情境：作者知道沒保護、會主動多看一次。

| 狀態                          | 警覺度           | 實際漏接率             |
| ----------------------------- | ---------------- | ---------------------- |
| 沒 hook                       | 高（知道沒保護） | 中                     |
| Hook 抓不到的範圍誤以為有保護 | 低(誤以為有)     | **高**（行為錯誤通過） |
| Hook 真的夠（純字面領域）     | 適中             | 低                     |

**第二行是最危險的組合** — 加 hook 卻不知道 hook 範圍、會比沒 hook 更糟。

### 規則膨脹：嘗試「再寫一條 hook」永遠補不完

每次行為錯誤通過、直覺反應是「再加一條 hook 規則」。但行為錯誤的形狀是無限的、規則永遠補不完。最終結果：

- 規則越來越多、越來越複雜
- 維護成本爆炸
- 仍然漏接行為錯誤
- 還產生越來越多 false positive 把好的擋掉

→ 規則膨脹是「用錯工具」的訊號、不是「規則寫得不夠細」的訊號。

---

## 多輪精煉的設計：spiral 取代攔截

行為錯誤的正確驗證手段是 **multi-pass spiral**：

```text
第 1 輪：先做、看結果
   ↓ 發現 N 個問題
第 2 輪：依結果調整 / 補強
   ↓ 發現 N-k 個問題
第 3 輪：dogfood / 實際使用 / 反向自查
   ↓ 收斂
（沒新問題 → 結束、有新問題 → 繼續迭代）
```

關鍵設計：**不是「攔截錯誤」、是「設計每輪能 catch 不同層的錯誤」**。

### 各輪的職責分工

| 輪次                          | 適合 catch 什麼      | 怎麼設計                                                                                                     |
| ----------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------ |
| 第 1 輪：實作                 | 純執行、預期會有錯   | 不要追求 perfect、跑起來看結果                                                                               |
| 第 2 輪：自查 / 對比需求      | 邏輯偏差、漏 case    | 對比原始需求、列 Checkpoint 1（[verification-timeline-checkpoints](./verification-timeline-checkpoints.md)） |
| 第 3 輪：dogfood / production | 實際使用才浮現的問題 | 真實 user / 真實流量、看回饋                                                                                 |
| 第 N 輪：反向自查             | 上幾輪沒看到的盲點   | 改換 frame（例如「假裝是另一個人 review」）                                                                  |

每輪解上一輪沒看到的問題、不是重複同一檢查。

### 不同輪適合不同的「不對齊」

- 第 1 輪 vs 需求 → 看「做出來的跟要的對不對齊」
- 第 2 輪 vs 邊界 case → 看「漏哪些情境」
- 第 3 輪 vs 真實使用 → 看「用起來感覺對不對」
- 第 N 輪 vs 上層原則 → 看「有沒有違反某個 meta-原則」

每輪有不同的角度、新角度才能 catch 上一輪 miss 的東西。

---

## 何時 hook 真的足夠

某些情境純字面就夠、加 hook 是對的：

| 情境                                                                   | 為什麼 hook 夠                |
| ---------------------------------------------------------------------- | ----------------------------- |
| Schema validation（API、DB、config）                                   | 結構是 spec、字面對 = 行為對  |
| 已知的 anti-pattern 字串（`TODO:`、`FIXME:`、`console.log`）           | 字面就是 evidence             |
| 格式統一（換行、縮排、import 順序）                                    | 純美化、沒語意                |
| 不可破壞的 invariant（commit 訊息含 issue 號、test 名格式）            | 結構即正確                    |
| 安全 critical 的 surface check（沒 secret 在 code、license header 在） | 漏掉成本極高、字面檢查 ROI 高 |

五類共通：**錯誤形狀完全字面、且漏掉成本高 / 字面就是 evidence**。其他情境 hook 都會在某個時點走到 ceiling。

---

## 識別 ceiling：什麼時候該換手段

ceiling 訊號：

| 訊號                                   | 該換的手段                              |
| -------------------------------------- | --------------------------------------- |
| 「這個 lint 規則寫不出來、太多例外」   | 改 review checklist、不寫 lint          |
| 「hook pass 但 production 還是出錯」   | hook 已到 ceiling、補 multi-pass review |
| 「規則第 N 次補例外」                  | 規則膨脹、退回 review                   |
| 「false positive 比 true positive 多」 | hook 過殺、放寬 + 補 review             |
| 「需要 understand intent 才能判斷」    | 純字面不夠、要 LLM / human review       |
| 「加了 hook 後 review 變草率」         | False confidence 在發生、警覺度降低     |

看到任一訊號、不是「再寫一條 hook」、是**接受 hook 對這個錯誤層次無能為力、改設計 multi-pass review**。

---

## 跟其他抽象層原則的關係

| 原則                                                                          | 關係                                                                                      |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| [two-occurrence-threshold](./two-occurrence-threshold.md)                     | 第 2 輪是 multi-pass 的最小單位、跟本卡的「多輪設計」同骨                                 |
| [verification-timeline-checkpoints](./verification-timeline-checkpoints.md)   | 四個 checkpoint = 多輪 review 的時間軸實現                                                |
| [test-first-red-before-green](./test-first-red-before-green.md)               | RED phase 是「testing the test」的多輪設計 — 純 hook 看不到                               |
| [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md) | 該卡提倡 L3-L5 結構性對策、本卡是 ceiling — L5 hook 抓不到行為錯誤、需要 L4 review / pair |
| [decision-dialogue-dimensions](./decision-dialogue-dimensions.md)             | 「五維 collapse」是行為錯誤、hook 抓不到、要靠 reference dogfood + multi-pass review      |

本卡是 [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md) 的 sibling / 補強 — 該卡推 L3-L5 結構性對策最強、本卡指出 L5 也有 ceiling、不是萬能。組合解：**字面用 L5 hook、行為用 L4 pair + multi-pass**。

---

## 判讀徵兆

| 訊號                                     | 該做的事                                                                                                     |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 想加 hook 防某個重複出現的問題           | 先問「是字面還是行為？」、行為的話別寫 hook                                                                  |
| 寫了 hook 規則但例外越來越多             | ceiling 到了、改 review                                                                                      |
| 「CI 通過 = 沒事」這個信念               | 檢查 CI 範圍、行為錯誤可能漏接                                                                               |
| 同類錯誤不斷以新形狀出現                 | 行為錯誤、hook 無解、補 multi-pass                                                                           |
| 第 1 輪做完就 ship、沒第 2 輪            | 假設一次寫對、多半會漏行為錯誤                                                                               |
| 多輪 review 每輪用同樣 frame             | 角度沒換、後續輪 = 重跑前輪、不會新發現                                                                      |
| 「下次注意」當作驗證                     | L1 紀律、不是 L4 結構、跟 [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md) 同病 |
| 行為錯誤反覆出現、但「再加條 hook 規則」 | 換工具、不是換規則                                                                                           |

**核心**：驗證手段的 ROI = 跟錯誤層次對齊 × 不超出 ceiling。**Hook 不會思考、所以只能擋字面**；**行為錯誤需要 multi-pass spiral、用每輪不同角度收斂、不靠單次攔截**。試圖用 hook 蓋 spiral 該做的工作 = 假裝有保護、實際比沒保護更危險。
