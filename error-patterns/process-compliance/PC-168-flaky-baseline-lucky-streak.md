---
id: PC-168
title: Flaky Baseline 少量 sample 推導 stable 錯覺
type: process-compliance
severity: high
status: active
source: 0.19.0-W4-005.1 二分定位實證
related:
  - PC-165
  - test-assertion-design-rules
  - pre-fix-eval
  - wrap-decision
---

# PC-168: Flaky Baseline 少量 sample 推導 stable 錯覺

## 摘要

對 race condition / 異步 / 環境敏感類問題，**少量 sample（N < 5）連續 GREEN 不能推導 stable baseline**。PM 派發前未強制 N >= 5 取樣 + 分佈紀錄時，agent 觀察的「N 次 GREEN」可能是 30-40% flaky 環境下的幸運連勝，據此推導的後續決策鏈會連鎖崩塌。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| Agent 回報「N 次 baseline GREEN，pristine 確認 stable」且 N < 5 | task-notification result |
| 後續基於該 baseline 做的決策（修 AC、建 follow-up、判 root cause）在另一次 baseline 觀察被推翻 | PM 連續 session 對比 |
| 同一檔案多次 baseline 結果不一致（例如某次 8/9、另次 9/9） | PM 跨 session 記憶 / git log |
| 修復「不會有效」但被誤判為「修復生效」 | runtime / 後續 ticket 驗證 |

## 根因（三層共振）

| 層 | 機制 |
|---|------|
| 環境層 | race condition（SW launch timing / chrome.storage init / 網路 / 檔案 I/O timing / 跨 process 通訊）導致 30-40% flaky |
| 取樣層 | 少量 sample（N=2, 3, 4）的觀察分佈無法代表母體；連續 GREEN 的條件機率仍可達 60-80% |
| 心理層 | PM / agent 把「連續 N 次 GREEN」直觀推為 stable，未做統計判斷；越早的 GREEN 越強化「stable」信念 |

三層共振讓 baseline 假設成為決策鏈的隱性前提，後續每一步推導都建在沙地上。

## 案例：W4-005.1 二分定位推翻三次 PM 決策

**情境**：W4-005「E2E timeout 常數化 + reExtract helper 抽取」純可讀性重構 ticket。

**前次 thyme 觀察**：

| Run | 工作區狀態 | 結果 |
|-----|----------|------|
| 1 | pristine baseline | 9/9 GREEN |
| 2 | 重構後 | 1/9 GREEN |
| 3 | 重構後（確認非 transient） | 1/9 GREEN |
| 4 | stash 還原後 pristine 再驗 | 9/9 GREEN |

**前次 thyme 結論**：「pristine 兩次驗證皆 9/9 GREEN（run 1 + run 4），baseline stable」→「重構引入穩定 regression（兩次 1/9 重現）」。

**PM 基於此假設做了三次決策**：

| 決策序 | 內容 | 假設基礎 |
|------|------|---------|
| 1 | 放寬 W4-005 AC#3 為「8/9 等價」 | 前次 thyme 觀察 baseline 8/9 為 pre-existing |
| 2 | 建立 W4-021 ANA ticket 追蹤「G4-1 pre-existing fail」 | 同上 |
| 3 | 後續再校正為「baseline 9/9 stable, 重構引入 regression」 | 本次 thyme 觀察 pristine 4 次 9/9 |

**W4-005.1 二分定位實證（N = 10 取樣）**：

| 階段 | 結果 |
|-----|------|
| pristine baseline（未含 W4-005 重構） | 33-40% flaky（同樣狀態既有 9/9 也有 1/9） |
| W4-005 重構後 | 33-40% flaky（同樣分佈） |
| W4-005.1 三層修復後 | 100% GREEN（10/10，其中 2 次觸發 retry 自動恢復） |

**反轉結論**：
- pristine 「兩次 9/9」是幸運連勝，**非** stable baseline
- W4-005 重構**不是** regression 元兇，與 race condition 無關
- 真實根因：SW launch timing 10s hardcoded 不足 + chrome.storage.local 初始化 race（兩個 pre-existing race）

**PM 三次決策成本**：
- 建 W4-021 ANA（基於錯前提）→ 撤回（rm 未進 git）
- 改 AC#3 為 8/9 等價 → 還原為 9/9
- 額外 1 輪 thyme 派發（重派確認 regression）

## 防護（三層）

### 防護 A：PM 派發前 prompt 強制取樣要求

對下列觸發條件，prompt 必須明示「baseline 取樣 N >= 5，紀錄 GREEN/RED 分佈，禁推導 stable」：

| 觸發條件 | 說明 |
|---------|------|
| 任務涉及 race condition | SW / 網路 / 檔案 I/O / 跨 process 通訊 |
| 任務涉及異步 | Promise / setTimeout / event loop 競爭 |
| 任務涉及環境敏感 | cold-start / 機器負載 / GC 觸發時機 |
| Flaky 修復類 ticket | acceptance 必含「N >= 10 連跑全 GREEN 或 retry 機制覆蓋下全恢復」|

### 防護 B：Agent 觀察驗證閘門

PM 接 task-notification 時，若 agent 回報「N 次 baseline GREEN 確認 stable」且 N < 5：

| 動作 | 說明 |
|------|------|
| 不採信為 stable | 標記為「未驗證」狀態 |
| 退回派發 | 要求補到 N >= 5 取樣後重新回報 |
| 禁止基於該觀察推導後續決策 | 包括修改 AC、建 follow-up ticket、判定 root cause |

### 防護 C：跨 session 不一致升級

同一檔案 / 測試 baseline 結果在不同 session 觀察不一致時：

| 訊號 | 防護動作 |
|------|---------|
| Session A 觀察 N/M，Session B 觀察 N'/M（N != N'） | 立即升級為 flaky 嫌疑，**不視為 transient** |
| 多 session 累積失敗 case 形成 pattern | 建 ANA ticket 找根因（race condition / 環境因素） |
| pattern 確認後 | 加 retry 機制 + 升級為 ticket 系列修復 |

## 識別訊號表

| 訊號 | 反模式句型 | 正確反應 |
|------|---------|---------|
| 「pristine baseline 兩次 GREEN，stable」 | 任何 N < 5 的 stable 推斷 | 問 N 多少；要求補到 N >= 5 |
| 「N 次 baseline 確認 stable」 | 同上 | 要求紀錄完整 GREEN/RED 分佈 |
| 「重構後 N 次都 RED，regression 穩定」 | N < 5 的 regression 穩定推斷 | 同樣要求 N >= 5 + flaky 排除 |
| 「同一狀態為何時 GREEN 時 RED」 | 把 flaky 視為環境 transient | 升級為 race condition ANA |
| 「乾淨環境驗證」「兩次驗證」「二次確認」 | 強化 stable 信念的語言 | 反問取樣次數 + 分佈 |

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| `.claude/rules/core/quality-baseline.md` 規則 1 邊界 | PC-168 與 PC-165 並列為「測試綠燈不充分」的姐妹反模式：PC-165 處理「綠燈不代表 runtime 正確」，PC-168 處理「少量綠燈不代表 always 綠燈」 |
| `.claude/rules/core/test-assertion-design-rules.md` 規則 1 | 同源（race condition 環境取樣失真），規則 1 處理斷言設計層（禁絕對計時門檻），PC-168 處理 PM 派發決策層（baseline 取樣方法） |
| `.claude/skills/pre-fix-eval` | 修復前評估，PC-168 補上「N >= 5 取樣」前置條件 |
| `.claude/skills/wrap-decision` P 階段 | 「12 小時後失敗最可能原因」候選列表必含「baseline 是幸運連勝」 |
| `.claude/skills/test-assertion-design` | 斷言設計判斷框架，與 PC-168 互補（前者 design-time, 後者 runtime baseline 驗證） |

## 案例文件來源

- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W4-005.md` — Problem Analysis 段落含三次 PM 決策誤判記錄
- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W4-005.1.md` — Solution + Test Results 段含 10/10 取樣實證
- `/Users/tarragon/.claude/projects/-Users-tarragon-Projects-book-overview-v1/memory/feedback_flaky_baseline_lucky_streak.md` — 短期 memory 雙向 cross-ref

---

**Last Updated**: 2026-05-31
**Version**: 1.0.0 — 從 0.19.0-W4-005.1 二分定位實證 + W4-021 升級流程落地
**Source**: W4-005.1 二分定位推翻三次 PM 決策（W4-021 / pm-quality-baseline-rule-7 四問升級）
