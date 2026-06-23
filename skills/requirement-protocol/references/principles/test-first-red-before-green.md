# Test-First：先看到 RED 才相信 GREEN

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被相關抽象層原則段引用、是 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md) 中 Checkpoint 2 / 3 的具體協議。
>
> **何時讀**：寫測試前後想確認「測試本身有沒有 catch 能力」、或修完 bug 才補測試（test-after）想 retrospectively 補驗證時、用本卡的 RED-GREEN 兩訊號協議。

---

## 核心原則

**測試本身需要被驗證。** 一個從沒看過 RED 的測試 = 未驗證的訊號、不是「會抓回歸的測試」。

驗證一個測試真的有用、需要看到兩個訊號：

1. **RED**：測試在「該失敗的版本」上失敗（buggy code → 紅）
2. **GREEN**：測試在「該通過的版本」上通過（fixed code → 綠）

只看過 GREEN = 不知道測試有沒有 catch 能力；只看過 RED = 不知道修復有沒有真的解問題。**兩個都看到 = 測試 + 修復都被驗證**。

跳過 RED 把驗收標準降到「測試跑得通」、漏掉「測試自己有沒有 bug」這層。

---

## 為什麼測試需要被驗證

### 測試是程式 about 程式、會有 bug

測試本身是程式碼、跟其他程式碼一樣會有 bug：

| 測試 bug 類型           | 症狀                                            | 為什麼跳過 RED 看不到             |
| ----------------------- | ----------------------------------------------- | --------------------------------- |
| Selector 寫錯           | 永遠抓不到目標元素、assertion always 過         | GREEN（因為沒 assert 到任何東西） |
| Assertion 太寬          | `expect(x).toBeDefined()` 對 buggy / fixed 都過 | GREEN（assertion 通過範圍太大）   |
| Setup / fixture 錯      | 測試根本沒跑、報告假性綠                        | GREEN（測試被 skip 但沒人注意）   |
| Race condition / 時機錯 | Buggy 時剛好在 race window 過、fixed 時也過     | GREEN（取決於非常規 case）        |
| 測試對象選錯            | 測 happy path、bug 在邊界                       | GREEN（沒覆蓋 bug 所在的範圍）    |

這五種都會讓「跑測試一次就 GREEN」是個假訊號 — 測試 pass 不代表測試 catch 到該 catch 的東西。

### RED 是測試的「使用者驗收」

對使用者代碼、我們會用「驗收訊號」（功能跑得對）證明它有用。測試也需要驗收訊號。

「測試 catch 到 bug」這個能力的驗收訊號 = **「在有 bug 的代碼上失敗」**。沒看過這個訊號就相信測試 = 跳過驗收。

對應 [`two-occurrence-threshold.md`](./two-occurrence-threshold.md)：一次 GREEN 是低資訊量訊號、RED → GREEN 是 2 次跑（一次 fail 一次 pass）的高資訊量訊號。

---

## 多面向：四種情境的 RED-GREEN 應用

### 情境 1：修 bug

```text
1. 先寫一個 test 重現 bug 為失敗 — 例：「filter 後 0 筆但 source 還有未載入時、應該顯示 explicit empty 而非 silent」
2. 跑測試 → RED ✓（證明測試抓到 bug、bug 真的存在）
3. 修 code
4. 跑測試 → GREEN ✓（證明修對了 + 測試會抓回歸）
```

跳過第 2 步 = 不知道測試會不會抓到、不知道 bug 真的有沒有。

### 情境 2：加 feature

```text
1. 寫 acceptance test 描述新 feature 該有的行為
2. 跑測試 → RED ✓（feature 還沒實作、應該 fail；如果 GREEN 就表示 feature 已經存在或測試太寬）
3. 實作 feature
4. 跑測試 → GREEN ✓
```

加 feature 時跳過 RED 風險：feature 被誤以為實作但實際是 stub、或測試根本沒驗到 feature。

### 情境 3：Refactor

```text
1. 確認當前測試 GREEN（baseline）
2. Refactor（不改 behavior）
3. 跑測試 → 仍 GREEN ✓
```

Refactor **不需要** RED — 因為 behavior 沒變。如果 refactor 後變 RED、表示 refactor 改到了 behavior（變成隱性 bug）、要回頭看。

### 情境 4：偵錯（不確定 bug 是什麼）

```text
1. 寫一個 test 嘗試重現問題
2. 跑測試 → 看是 RED 還是 GREEN：
   - RED → 重現成功、現在可以著手修
   - GREEN → 沒重現到 / 測試寫錯 / bug 在別處 → 重新理解 bug
3. 修
4. 跑測試 → GREEN
```

「看是 RED 還是 GREEN」這個動作本身是 debug 訊號 — 比單純猜根因有用。

---

## 「只看 GREEN 不看 RED」是反模式

### 反模式 1：修完才補測試（Test-after）

```text
1. 修 bug code
2. 寫測試
3. 跑測試 → GREEN
4. ship
```

問題：測試從沒跑過 buggy code、不知道它能不能抓到 bug。未來 regression 進來、測試可能仍然 GREEN（測試本身有 bug）。

### 反模式 2：「快速跑一下測試」沒看訊號

```text
1. 寫測試
2. 跑「應該 pass 吧」、不仔細看輸出
3. 看到 PASS → 安心
```

問題：可能測試 skip 了、可能測試 zero assertions、可能環境錯了。需要看「具體 catch 到什麼」、不只是「是否 PASS」。

### 反模式 3：測試 PASS 但 coverage 是 0

```text
1. 寫測試 file
2. CI 跑、看到「all green」
3. 沒看 coverage report
```

問題：測試文件存在但實際沒 import / 沒執行、CI 報告 GREEN 是因為「沒 fail」不是「有 catch」。

---

## 不該套用本原則的情境

「先看 RED 再看 GREEN」原則在大多數情境成立、但有合理例外：

| 情境                      | 為什麼不該套用                                          |
| ------------------------- | ------------------------------------------------------- |
| Pure refactor             | 沒 behavior 變更、本來就 GREEN、RED 反而表示出問題      |
| 純探索 / spike            | 不寫測試、用 console / 手動驗證、不在「測試驗收」範圍   |
| Build / config 改動沒邏輯 | 沒 testable behavior、沒測試可言                        |
| 顯眼的 syntax 錯誤修復    | 改一個 typo、測試會在 build 階段就 fail、不需要刻意 RED |

四類共同特徵：**沒有「行為差異」可被測試 catch** — 本原則建立在「測試該 catch 的事」上、沒事可 catch 時自然不適用。

---

## 跟其他抽象層原則的關係

| 原則                                                                                 | 跟本卡的關係                                                                    |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| [`two-occurrence-threshold.md`](./two-occurrence-threshold.md)                       | 一次 GREEN 是低資訊量訊號、RED → GREEN 是 2 次跑（一次 fail 一次 pass）的真訊號 |
| 「視覺完成 ≠ 功能完成」                                                              | 測試 PASS ≠ 測試 verified；同個「訊號需要驗證」結構                             |
| [`ease-of-writing-vs-intent-alignment.md`](./ease-of-writing-vs-intent-alignment.md) | 跳過 RED 是便利（不用切 branch / 不重 build）、走 RED-GREEN 是對齊              |
| [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md)     | 本卡是 Checkpoint 2「開發中」+ Checkpoint 3「Ship 前」內部的具體協議            |

本卡是把「測試這個動作本身」放進驗收體系：寫測試是動作、跑測試的訊號才是驗收。動作完成 ≠ 驗收完成。

---

## Retrospective 補驗證的協議

如果已經修完才寫測試（test-after）、可以 retrospectively 補 RED-GREEN 驗證：

```bash
# 1. Stash 現有變動 / 切到修前 commit
git stash
git checkout <pre-fix-commit>

# 2. Cherry-pick 測試 commit（或手動複製 test files）
git cherry-pick <test-commit>
# 或：cp ../tests/foo.spec.ts tests/  # 複製測試檔過來

# 3. Build + 跑測試
make build && npm test
# 預期：RED ✓（測試抓到 bug）

# 4. 切回 main / 修後版本
git checkout main
git stash pop

# 5. 跑測試
npm test
# 預期：GREEN ✓
```

兩次跑 + 兩個訊號（RED + GREEN）都對、測試才被驗證。**Retrospective 補驗證 ≠ 不能補** — 比完全跳過 RED 好、比 test-first 弱。

協議可 codify 為類似 `make verify-red-green PRE_FIX=<commit-sha>` 的工具 — 五步驟自動化、不需要每次手動 stash / checkout / build / restore。

跳過 RED 是相關概念「高 ROI 無外部觸發的工作會被結構性跳過」在測試協議的展現 — 修法不是「下次記得」（L1 紀律會失敗）、是 verify-red-green 工具（L3 工具觸發）+ pre-commit hook 提醒（L3 結構觸發）。

---

## 判讀徵兆

| 訊號                             | 該做的事                                                     |
| -------------------------------- | ------------------------------------------------------------ |
| 寫完測試第一次跑就 GREEN         | 警訊 — 確認測試是不是真的有 catch 能力（覆蓋 bug case 嗎？） |
| 修了 bug 但沒看過該測試 RED 過   | 補 retrospective 驗證、或下次採 test-first                   |
| 「我等下會跑一下」但沒實際跑     | 跟「我等下會 refactor」同類謊言、補不回來                    |
| CI 永遠 GREEN、沒有人改過測試    | 看 coverage、可能測試沒在跑                                  |
| 加了 feature、測試一寫就 GREEN   | feature 可能已經存在、或測試太寬                             |
| 測試環境跟 production 環境差太多 | RED 在 dev 但 prod 仍 fail = 測試環境沒 catch 真實 case      |

**核心原則**：測試不是「跑得通就有用」、是「跑出該有的訊號才有用」。RED 是測試的驗收訊號、跳過 = 接受測試本身可能是壞的。RED → GREEN 兩次跑、才證明「測試真的會 catch + 修復真的解掉 bug」。
