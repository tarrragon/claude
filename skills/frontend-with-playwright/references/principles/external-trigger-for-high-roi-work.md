# 高 ROI 無外部觸發的工作會被結構性跳過

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段（#72）引用、是說明「為什麼 layout test / RED phase / Checkpoint 1 / a11y review 等動作需要協議結構強制、不能靠紀律」的 meta 原則。
>
> **何時讀**：當你寫到「下次記得 X」「之後我會 X」「等下回頭做 Y」這類紀律承諾、或發現某類重要工作（refactor / doc / monitor / RED phase）長期沒人做、需要判斷該補哪個層級的觸發機制時。

---

## 核心原則

**工作有兩個獨立維度：ROI 高低 × 是否有外部觸發。**

| ROI / 觸發 | 有外部觸發           | 沒外部觸發                   |
| ---------- | -------------------- | ---------------------------- |
| **高 ROI** | 順利做（happy path） | **被結構性跳過**（本卡焦點） |
| **低 ROI** | 該砍掉、不該做       | 自然不做（也對）             |

「**高 ROI + 沒外部觸發**」是個結構性陷阱 — 知道該做、做了有大回報、但永遠不做。靠「我下次記得」不可行。修法是**結構性對策**：把外部觸發補上。

---

## 為什麼靠紀律不可行

### 「之後做」是個謊言（共同結構）

相關概念：寫作便利度跟意圖對齊反相關 已經點到一個面向。把它推廣：

「之後做 X」這個 plan 在 X 屬於「高 ROI + 無觸發」時、預期完成率接近 0。不是個人意志問題、是結構問題：

| 工作觸發來源      | 「之後做」的執行率 |
| ----------------- | ------------------ |
| 客戶來信催        | ~95%               |
| Bug 卡死流程      | ~95%               |
| Calendar reminder | ~70%               |
| Sprint planning   | ~60%               |
| 自己記下的 TODO   | ~30%               |
| 「下次有空我做」  | ~5%                |

往下走、外部觸發越弱、執行率越低。最弱的「下次有空我做」≈ 0% — 因為「下次」永遠是「現在」、「現在」永遠有更急的事。

### 為什麼結構性、不是動機問題

「沒外部觸發」 = 沒人催、沒 deadline、沒 alarm、沒 PR review 提醒。腦中有 working memory 限制、優先處理「正在叫」的事。**「叫」這個動作只有外部能做** — 自己對自己叫沒用（因為「自己叫自己時」跟「自己接受自己叫時」是同個 context）。

這跟意志力、自律、責任感無關 — 即使最自律的人、面對「沒人催的高 ROI 工作」，執行率也大幅下降。靠紀律 = 預期失敗、然後責怪自己。

---

## 多面向：高 ROI + 無觸發的工作清單

每一條都是常見展現：

### 寫程式類

- **Refactor（沒功能壓力）**
- **Test-first 的 RED 階段（修完才補測試）**
- **Checkpoint 1（列使用者意圖完整集）**
- **Ship 前 E2E case 設計**
- **Code review feedback 的 follow-up**（reviewer 留 comment、作者回「之後改」）

### 維護類

- **Migration cleanup（feature flag 拔除、舊 path 砍掉）**
- **Deprecated 程式碼移除**
- **Dependency upgrade（沒 breaking 但該升）**
- **Performance regression 修復（測量上有但使用者沒抱怨）**

### 文件類

- **API doc / README 更新**
- **事後檢討卡片寫入**（卡片系統本身就是 case — 沒 user 提醒就不會做）
- **Decision log / ADR**

### 監控類

- **Setup observability / log monitor**
- **Alert 規則 review**
- **Dashboard 維護**

### 知識類

- **Onboarding doc 更新**
- **Post-mortem 寫完發出去**
- **跨團隊 share session**

**共通結構**：每一項都「知道該做、做了有大回報、沒人催就不做」。即使是寫過卡片教自己原則的人（meta-level dogfooding 失敗）也一樣會跳過。

---

## 修法：結構性對策的五個層級

從弱到強：

### L1：個人紀律（最弱、不可行）

「我下次記得」「我會自律」 — 已經證明 ≈ 0% 執行率。不該寫進 plan。

### L2：自我排程（弱）

「每週五下午 refactor 1 小時」「每個月初 review TODO」。比 L1 強、但仍依賴自己當下不分心、不被「更急」的事拉走。執行率約 30-50%。

### L3：外部工具觸發（中-強）

把觸發外化到工具：

- **CI / pre-commit hook**：commit test file 自動提醒「跑過 RED 嗎」
- **Scheduled scripts**：cron job 跑 lint / dep audit / migration cleanup detector
- **Calendar event**：固定時間、有 alarm
- **PR template**：強制填「Checkpoint 1 列了哪些 case」

工具不會忘、不會拖、不會選擇性執行。執行率 80-95%。

### L4：團隊流程（強）

把觸發外化到別人：

- **Pair programming**：另一個人在旁邊、會問「為什麼跳過 X」
- **Code review block**：reviewer 不通過 PR 直到 X 完成
- **Standup commitment**：公開講出「我這週要修 X」、隔天會被問
- **Retro action items**：團隊紀錄 + 追蹤、不個人擁有

執行率 90-99%。

### L5：結構性不可能（最強）

讓不做 X 變成 ship 不出去：

- **Tests required**：CI fail 不能 merge
- **Build fails on stale doc**：lint 規則檢查 doc 跟 code 同步
- **Feature flag 自動 expire**：超過某時間、flag 被自動移除
- **Linter 禁用 deprecated API**：用了就 build 錯

100% 執行率（系統強制）。代價：建立成本高、要團隊認可。

選擇法則：**先看哪個層級剛好夠**、不要用 L5 解 L3 能解的問題（過度工程）、也不要用 L1 解 L4 才能解的問題（會失敗）。

---

## 「想到就動手」是次優、不是最優

直覺反應是「想到該做就立刻做」、避免拖延。這在「想到時剛好沒手邊事」可行、但實際多半「想到時手邊有事」 — 變成中斷當前工作、context switch 高昂。

更穩定的策略：**把想到的東西塞進已存在的觸發機制**：

- 想到「這個重複了該抽 helper」 → 開 issue / TODO 給下次 refactor session
- 想到「這個 case 沒測」 → 加進 PR template 的 Checkpoint 1 list
- 想到「這個 doc 過時了」 → 打開 doc 在 commit 寫 `// TODO: 更新 X`

「動手」的時機由觸發決定、不由「想到」決定。**想到 = 觸發機制的 input、不是執行的 trigger**。

---

## 不該套用本原則的情境

「高 ROI + 無觸發 = 結構性跳過」原則在多數情境成立、但有合理例外：

| 情境              | 為什麼不該套用                            |
| ----------------- | ----------------------------------------- |
| 純探索 / 興趣專案 | 沒 ROI 概念、做了爽就好、不需要結構性對策 |
| 一次性極小工作    | 5 分鐘內完成、加 trigger 反而成本高       |
| 緊急 incident     | 已有最強觸發（系統壞了）、不需額外結構    |
| 還沒穩定的探索期  | 規則還在演化、結構性對策可能會卡死探索    |
| 學習新技術 / 練習 | 自己選、沒外部 ROI 衡量、跳過也不損失     |

四類共同特徵：**「外部觸發」這個變數已經有解或不存在** — 本原則建立在「沒觸發 = 跳過」上、有觸發或不需要時自然不適用。

---

## 判讀徵兆

| 訊號                                             | 該做的事                                   |
| ------------------------------------------------ | ------------------------------------------ |
| Plan 含「之後我會 X」                            | 是 L1 紀律、預期失敗、改成 L3+ 觸發        |
| TODO list 累積 30+ 項、半年沒減少                | 觸發機制壞了、不是「太忙」                 |
| 某類重要工作（refactor / doc / monitor）長期沒做 | 沒外部觸發、補 L3-L5                       |
| 自己責怪「我又拖延了」                           | 結構問題不是個人問題、停止責怪、改機制     |
| 同團隊不同人做同類工作的執行率差很多             | 個別人差是表象、機制設計問題（流程不一致） |
| 某個 lint / CI rule 改完所有人都自動跟上         | L5 對策成功、適合複用到其他類似工作        |
| 「想到就立刻做」打斷正在做的事                   | 動作該由觸發排程、不由 thoughts 觸發       |

**核心原則**：高 ROI 但無外部觸發的工作 = 結構性跳過、不是個人問題。修法是把觸發外化（工具 / 流程 / 結構）、不是「我下次記得」。「之後我會 X」是 plan-level 警訊、應該轉成「X 會被 Y 觸發」的具體機制。

---

## 與其他原則的串連

- 寫作便利度跟意圖對齊反相關：是本卡在「寫程式當下選哪條路」面向的展現 — 對齊 = 高 ROI 但無觸發 — 詳見 [`ease-of-writing-vs-intent-alignment.md`](./ease-of-writing-vs-intent-alignment.md)
- 驗收的時間軸：四個 checkpoint 中「Ship 前 / Checkpoint 1 結構性偏差」是本卡在驗收動作的展現 — 詳見 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md)
- Test-First：RED 階段被跳過 = 本卡在測試協議的展現 — 詳見 [`test-first-red-before-green.md`](./test-first-red-before-green.md)
- 2 次門檻：失敗訊號需要被「外部承認」才能觸發轉折 — 跟本卡共骨 — 詳見 [`two-occurrence-threshold.md`](./two-occurrence-threshold.md)
- 字面攔截 vs 行為精煉：本卡的 ceiling — L5 hook 只擋字面、行為錯誤需要 L4 review / multi-pass spiral、不是「再寫一條 hook 規則」 — 詳見 [`literal-interception-vs-behavioral-refinement.md`](./literal-interception-vs-behavioral-refinement.md)

本卡是 meta- 寫作便利反相關 / 驗收時間軸 / Test-First — 把「為什麼這些動作會被跳過」抽出來、答案是「沒外部觸發 + 靠紀律失敗 = 結構性跳過」。三張卡的修法都是「補外部觸發」、不是「自己更努力」。
