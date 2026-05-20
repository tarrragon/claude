---
id: PC-151
title: Stale 測試 exit code 期望未隨 CLI exit code 規範演進同步
category: process-compliance
severity: low
source_case: 0.18.0-W14-046 / 0.18.0-W14-046.1
created: 2026-05-18
---

# PC-151: Stale 測試 exit code 期望飄移

## 症狀

CLI 工具的測試（特別是錯誤路徑與業務拒絕路徑）出現持續性 stale 紅燈，pattern：

```
assert result == 1
E   assert 2 == 1
```

或反向（期望 2，實際 1）。失敗訊息單純為數字不符，無錯誤類別差異。被 PM 或代理人遇到時容易被誤判為：

- 「實作 bug：exit code 回錯了」
- 「代理人虛構：報告中提及的測試名稱不存在於 repo」（W14-045 ↔ W14-046 案例）
- 「pre-existing failure 與本 ticket 無關」（baseline 接受，沒人追查）

**Why**：失敗訊息不指向真因（規範演進 vs stale 期望），第一直覺往程式碼動向走。

**Consequence**：可能誤改正確的實作（將 return 2 改回 return 1）、開不必要的 ANA ticket 追查「agent 虛構」、或將真實的 stale test 永久標記為「pre-existing failure baseline」不再追查。

**Action**：看到「assert result == X」+「assert Y == X」型錯誤時，先讀對應 production code 註解（常見會引用 `cli-exit-code-rules.md`），確認規範方向，再決定改測試或改實作。

## 觸發條件

以下三條件同時成立：

1. **CLI 工具有正式的 exit code 規範**（本專案：`.claude/references/cli-exit-code-rules.md`，將 exit code 分為 0=success / 1=internal error / 2=user input business reject）
2. **規範後期演進過**（如從「所有錯誤都回 1」演進到「業務拒絕回 2，內部錯誤才回 1」）
3. **測試以早期語意撰寫，後續未隨規範同步更新**

## 根因

測試 exit code 期望本質上是 CLI 規範的副本（duplicate of canonical rule），但沒有自動同步機制：

| 規範變更時的同步路徑 | 實際發生狀況 |
|--------------------|-------------|
| 規範文件 → 實作程式碼 | 通常同步（程式碼會註明「依 cli-exit-code-rules 規則 X」） |
| 規範文件 → 測試期望值 | 容易遺漏（測試本身不會 import 規範，期望值是 hard-coded 數字） |
| 實作 → 測試 | 通常會跑測試發現失敗，但若實作變更那次該測試被忽略（如標 baseline）就永久落後 |

當 PM/agent 後續遇到 stale test，因為失敗訊息只是數字不符，沒有「規範條款編號」線索，第一反應傾向懷疑實作或 agent 報告。

## 案例

### 案例 1: W14-045 → W14-046 → W14-046.1（2026-05-18）

完整鏈：

1. thyme-python-developer 在 W14-045 完成報告寫「預存失敗 `test_check_acceptance_no_criteria` 已 stash-baseline 驗證與本 ticket 無關」
2. PM 驗證時用 `grep test_check_acceptance_no_criteria` 但範圍漏掃 `.claude/skills/ticket/tests/`，誤判 thyme 虛構，開 W14-046 ANA 派 saffron
3. saffron grep 全 repo 確認測試存在於 `.claude/skills/ticket/tests/test_track_acceptance.py:81`，pytest 確認失敗為 `assert 2 == 1`
4. PM 推進 W14-046.1 時讀 `track_acceptance.py:292` 註解「用戶輸入錯誤路徑均為業務拒絕（return 2），詳見 cli-exit-code-rules.md 規則 2」，判定實作正確、測試 stale
5. 同 file 內共 4 個測試同根因 stale（no_criteria / nonexistent_ticket / all_and_index_mutually_exclusive / missing_index_and_all），一次修完
6. 同 commit 後跑 `pytest tests/`（全套）發現 `test_track_batch.py` 另有 3 個失敗，疑同根因待追查

雙線根因：

- PM 端：grep 範圍不完整 → 已寫 feedback memory（pm-grep-scope-includes-skill-tests）
- 測試端：規範演進後測試期望未同步 → 本 PC

## 防護措施

防護分自律層與規範層兩線：自律層處理「已發生的 stale test 如何正確診斷」，規範層處理「規範演進時如何防止測試期望落後」。兩者互補，缺一會在不同時間點重新產生本模式。

### 自律層（PM + 代理人）

1. **看到「assert N == M」型 stale 紅燈時，先讀對應 production 程式碼註解**
   - 多數會引用規範文件（如 `cli-exit-code-rules.md`），可立即判定方向
   - 禁止直覺改實作或標 baseline 跳過

2. **將 stale test 視為「規範同步缺口」而非 agent 虛構或實作 bug**
   - thyme 報告測試名稱時應信任至少存在性（先 grep 全 repo 驗證），再評估期望值合理性
   - PM 驗證 agent 報告的測試名稱時 grep 範圍須含 `.claude/skills/**/tests/`（PC-151 配套）

3. **修 stale test 時順手掃同檔同模式**
   - 同 file 內常多個測試同根因，一次掃清避免反覆 ticket（W14-046.1 案例：1 個 → 4 個）

### 規範層（CLI 設計者）

| 預防動作 | 觸發時機 |
|---------|---------|
| 規範變更 commit 加 checklist「已掃所有測試 exit code 期望」 | 規範條款新增 / 修改時 |
| 測試以常數引用規範（`from cli_exit_codes import BUSINESS_REJECT`）取代裸數字 `2` | 規範引入或測試重構時 |
| pytest 失敗訊息註解附「請對照 cli-exit-code-rules.md 規則 X」 | 規範首次落地時 |

## 升級條件

- 若 stale test 期望飄移在後續 3 個月再出現 2+ 次，升 medium severity 並補強防護措施。
- 若 stale test 導致 agent 報告被誤判虛構超過 2 次，與 PM 驗證範圍類 PC 合併升格 methodology。

## 相關文件

- `.claude/references/cli-exit-code-rules.md` — exit code 規範（規則 2：業務拒絕 = 2）
- `feedback_pm_grep_scope_includes_skill_tests.md` — PM grep 範圍 memory（雙線根因之一）
- W14-046 ticket / W14-046.1 ticket — 完整案例脈絡
