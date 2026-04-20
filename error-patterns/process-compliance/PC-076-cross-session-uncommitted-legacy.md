# PC-076: Session 間未 commit 變更在後續 session 執行中意外浮現

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-076 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-17（W13-003 commit 後 git status 清點發現 W12-005 遺留） |
| 姊妹模式 | **PC-078（並行 session 狀態變化）**——PC-076 處理靜態遺留，PC-078 處理動態並行；與 Git index.lock Prevention（memory feedback_git_index_lock_prevention）同屬 git 流程紀律 |

---

## 症狀

1. Session-start 的 `branch-status-reminder` Hook 顯示 `M test_ana_spawned_checker.py` 一條，給出「主 repo 有未提交變更」警告
2. PM 依 session 任務（W12-001 完結）推進工作
3. 工作中某個 `git status` 呼叫（通常是 Checkpoint 1 commit 準備階段）才揭露：除了本 session 成果，還有 4+ 個前 session 未 commit 的實作檔案（例：`.claude/skills/ticket/ticket_system/commands/lifecycle.py`、`test_track_lifecycle.py`、`command_lifecycle_messages.py`、`track.py`、對應 Ticket 的 where.files 與 Problem Analysis）
4. 這些檔案屬於另一個 Ticket（例 W12-005），非本 session 任務範疇
5. PM 需臨時決定：合併 commit、拆分 commit、或擱置不 commit

## 實例（2026-04-17 W12-001 完結 session）

- Session-start git status 僅顯示 `M test_ana_spawned_checker.py`
- W12-001 complete 後 git status 突然出現：
  - `M .claude/skills/ticket/tests/test_track_lifecycle.py`
  - `M .claude/skills/ticket/ticket_system/commands/lifecycle.py`（實為新增 145 行）
  - `M .claude/skills/ticket/ticket_system/commands/track.py`
  - `M .claude/skills/ticket/ticket_system/lib/command_lifecycle_messages.py`
  - `M docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W12-005.md`（+237 行 Problem Analysis）
- 屬前 session 對 W12-005 / PC-075 Phase 2 的實作遺留，未 commit 即結束 session
- 本 session 拆出獨立 commit B 處理

## 實例（2026-04-17 W14-013 session）

- Session-start `branch-status-reminder` 僅顯示 1 個變更：`M docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W14-016.md`
- PM 認領並執行 W14-013（與 W14-016 主題完全無關）
- W14-013 修復檔 + check-acceptance 完成、準備 commit 時跑 `git status` 才浮現額外 4 個檔案：
  - `M .claude/hooks/acceptance_checkers/children_checker.py`（W14-016 H 方案 import 路徑改造）
  - `M .claude/skills/ticket/ticket_system/lib/constants.py`（改為 shim）
  - `?? .claude/skills/ticket/ticket_system/constants.py`（W14-016 新建 canonical 常數）
  - W14-016.md 又被改（前 session 勾了 AC1/AC3 + 補實作摘要）
- 屬前 session 對 W14-016 H 方案實作遺留，AC1/AC3 已勾但未 commit 即中斷
- 本 session 隔離 commit：(a) 先單獨 commit W14-016.md status 元資料 (b) 再 commit W14-013 修復；W14-016 程式碼變更暫留待後續處理

### 本案例新觀察

1. **遺留檔案中可能含 untracked 新檔**：W14-016 案例新增了 `constants.py`，需用 `git status` 而非 `git diff` 才看得到
2. **遺留 ticket md 同時被多 session 修改**：W14-013 session 當下 commit 過 W14-016.md 一次（status: in_progress + 5W1H 細節），但前 session 還做了 AC 勾選與實作摘要追加，必須再分離 commit
3. **使用者用 /ticket 預設流程選擇新 pending 時，並未提示「另一 in_progress ticket 含未 commit 程式碼變更」**：建議 /ticket 流程在列出 pending 前先做 git status 全量檢查並警告

---

## 根本原因

### 真根因

1. **Session-start git status 輸出不完整**
   - branch-status-reminder Hook 的 git status 檢測僅列首行變更（實例中只列 test_ana_spawned_checker.py），未列出全部
   - 或 Hook 僅偵測 untracked；tracked-modified 部分被壓縮到「未提交變更：N 項」等彙整

2. **前 session 結束流程缺口**
   - Session 結束時未執行完整 commit cycle（/commit-as-prompt）
   - 可能因：用戶中斷、/clear 未強制 commit、認為「後續再做」

3. **PM 工作邊界假設**
   - PM 認領 W12-001 任務時預設「git 工作區處於乾淨或僅含本任務相關變更」狀態
   - 未在 session 初期執行 `git status --porcelain | wc -l` 全量清點

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成違規 |
|---------|--------------|
| 「session-start Hook 顯示只有 1 個變更，應該沒事」 | Hook 輸出格式限制可能遮蔽其他 tracked-modified |
| 「前一任務 commit 已完成，現在主題乾淨」 | Ticket complete 不等於 git 工作區乾淨 |
| 「遺留檔案與我無關，commit 留給下次 session」 | 累積延後會混淆未來 session 的認知邊界 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Hook | branch-status-reminder 改為列出所有 tracked-modified 與 untracked（或給出「共 N 項」後附加詳細清單檔案路徑） | 建議實施 |
| 流程 | PM session-start 後主動執行 `git status --porcelain \| wc -l` 並與 Hook 訊息對照；若數字不符展開詳列 | 行為準則 |
| 流程 | Commit 前再次 `git status` 清點，將無關變更拆為獨立 commit 並標明「前 session 遺留」 | 行為準則 |
| 流程 | Session 結束前強制執行完整 commit cycle；未完成實作留在工作區必須於該 session 內整合處理 | 建議實施（W10-014 相關） |

---

## 檢查清單（PM session-start + commit 前）

### Session-start
- [ ] 讀完 Hook 的 branch-status-reminder 輸出後，額外執行 `git status` 確認完整變更清單
- [ ] 若看到非本任務檔案，先判定來源：前 session 遺留 / 其他 session 並行 / 自動化 Hook 產生
- [ ] 記錄遺留清單到 Ticket Problem Analysis 或工作日誌，明確標示處理計畫

### Commit 前
- [ ] `git status` 全量清點未提交變更
- [ ] 將主題不相關的變更拆為獨立 commit
- [ ] 每個獨立 commit 訊息標明：本 session 成果 vs 前 session 遺留
- [ ] 遺留檔案 commit 前跑對應測試確認未破壞（本案例跑 test_track_lifecycle.py 35 tests 全綠）

### Session 結束前
- [ ] 執行 `git status` 確認工作區乾淨（或僅含刻意保留給下 session 的 handoff）
- [ ] 未 commit 的實作進度寫入 Ticket handoff direction 或 worklog 「下個 Session 接手 Context」

---

## 教訓

1. **Hook 資訊密度有限**：session-start 提醒是摘要，非完整稽核；PM 仍須主動驗證
2. **Commit 不只是主題動作，也是清點動作**：commit 前全量 `git status` 暴露隱藏負擔
3. **Session 結束是集中責任的時刻**：不 commit 就是把負擔轉嫁給下一個 session 的人
4. **遺留檔案先跑測試再 commit**：本案例 test_track_lifecycle.py 35 測試驗證讓 commit B 有信心，若跳過可能把損壞的實作直接推入主線

---

## 重要區分

本模式僅處理**靜態遺留**（前 session 結束未 commit 的檔案變更）。遇到 Ticket **狀態變化**（status 欄位改變、started_at 填入新時間戳）時**不適用本模式**，需改用 PC-078（並行 session 狀態變化）判斷。詳見 PC-078 的「與 PC-076 的區別」對照表。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-078-parallel-session-ticket-state-misjudgment.md` — 姊妹模式（動態並行 vs 本檔的靜態遺留）
- `.claude/error-patterns/process-compliance/PC-075-spawned-children-status-check-asymmetric.md` — 本案例遺留檔案對應的 Ticket 主題
- `.claude/rules/core/bash-tool-usage-rules.md` — git 串接規則
- `.claude/error-patterns/implementation/IMP-XXX`（若升級） — 若 Hook 輸出改善落地

---

**Last Updated**: 2026-04-17
**Version**: 1.1.0 — 追加 W14-013 session 案例（含 untracked 新檔、ticket md 多 session 接力、/ticket 預設流程未檢查 in_progress 程式碼變更觀察）
**Source**: 2026-04-17 W12-001 完結 session 與 W14-013 session，連續兩次 commit 前 git status 揭露前 session 遺留實作
