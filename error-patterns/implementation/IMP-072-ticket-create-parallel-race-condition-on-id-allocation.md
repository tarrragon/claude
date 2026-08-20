# IMP-072: ticket create 並行執行時 ID 分配 race condition

## 基本資訊

- **Pattern ID**: IMP-072
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-12
- **風險等級**: 中
- **影響範圍**: `.claude/skills/ticket/ticket_system/commands/create.py`

---

## 問題描述

### 症狀

PM 在單一 session 中並行執行 2+ 個 `ticket create` 命令（如 background bash），兩個命令同時讀取「最新 ticket 編號」並各自 +1，最終分配到**同一個 ID**。後執行的 commit 會 overwrite 先執行的 commit 內容。

### 表現形式

| 階段 | 行為 |
|------|------|
| t=0 | 兩個 bash 同時讀取最大編號為 N |
| t=1 | 兩個 bash 各自寫入 N+1.md（無 file lock）|
| t=2 | 後完成的 process overwrite 前一個的內容 |
| 通知 | 兩個 bash 都通知 `completed exit 0` |
| 結果 | 檔案系統只剩 1 個 N+1.md（內容是後者）|

---

## W10-105 ANA 收尾案例

### 時序

1. PM W10-105 ANA 結論需建 2 個 spawned IMP（hook accessibility + CLI/schema 對齊）
2. PM 並行派發 2 個 background bash `ticket create`：
   - bash bi43cud13: hook accessibility IMP
   - bash b6uyaczhp: CLI/schema 對齊 IMP
3. 兩個 bash 都通知 completed exit 0
4. ls 只看到 `W10-107.md`，內容為「CLI/schema 對齊」（後執行的 b6uyaczhp 內容）
5. 第一個 bash 的「hook accessibility」內容被 overwrite 遺失
6. PM 重新 serial 執行第一個 ticket create，建出 `W10-108.md`

### 證據

- `cat b6uyaczhp.output` 顯示 Context Bundle 抽取成功訊息
- `cat bi43cud13.output` 顯示同樣 Context Bundle 抽取訊息
- `ls` 只有 W10-107.md（內容對應 b6uyaczhp）
- 重新 serial 執行才建出 W10-108.md

---

## 根因分析

### 直接原因

`ticket create` 分配 ID 流程：

```
1. 掃描 docs/work-logs/.../tickets/ 找最大編號 N
2. 設定新 ticket 為 N+1
3. 寫入 N+1.md
```

步驟 1-2 與步驟 3 之間無 atomic lock，並行執行時：

- Process A: 讀 N=106 → 設定 ID=107 → 寫 107.md
- Process B: 讀 N=106（同時）→ 設定 ID=107 → 寫 107.md（overwrite A）

### 深層原因

| 動機類型 | 表面說法 | 深層動機 |
|---------|---------|---------|
| A 設計假設 | 「ticket create 是低頻操作」 | 未考慮並行 PM 派發場景 |
| B 缺乏並行測試 | 「單機開發無 race condition」 | 測試覆蓋不涵蓋並行 create |
| C 缺 file lock | 「Python file lock 跨平台不一致」 | 避難式設計而非正面解決 |

---

## 防護機制

### 修補方向

| 方案 | 描述 | 成本 |
|------|------|------|
| A. fcntl/lockfile 原子化 | 在 ID 分配 + 寫入之間加 file lock | 中（跨平台處理 fcntl vs msvcrt）|
| B. ID 預留 + retry | 寫入前 atomic test-and-set；衝突則 retry 下一 ID | 中-高 |
| C. PM 規則禁止並行 create | 規則層約束 PM 序列化 create | 低（但靠自律）|
| D. 編號改為 UUID | 完全消除 race | 高（破壞性變更，影響 ID 可讀性）|

推薦：**A**（fcntl-based file lock）+ **C**（規則層補強）雙層防護。

### PM 層 workaround

當前 v0.18.0 在修補前，PM 應：

- **禁止並行 `ticket create`**：多 ticket 一次只能序列建立
- **驗證新建 ticket 存在性**：每次 create 後 `ls -t .../tickets/*.md | head -1` 確認新檔
- **避免 background bash 並行 ticket create**：用 foreground bash 序列執行

### 頻率升級案例：跨 session 同日二度撞號（2026-06-11）

原始案例為「同 session 並行派發」撞號；本案例為**跨 session**（兩個獨立 terminal 各自 create）撞號，且同日二度發生：

| 撞號 | 雙方 ticket | 處置 |
|------|------------|------|
| 第一次 | telemetry IMP（並行 session，源 W1-049）vs bookkeeping IMP（主 session） | 主 session 的票遷移為 W1-058 |
| 第二次 | auto-commit-hook ANA（並行 session）vs hook 注入污染 ANA（主 session） | 主 session 的票遷移為 W1-060 |

**升級訊號**：並行 session 工作模式（PC-078）常態化後，跨 session create 的撞號機率與 session 活躍度成正比，不再是低頻事件。**Consequence**：撞號後的遷移處置會遺失 frontmatter 關聯欄位（relatedTo / spawned_tickets，IMP-061 已知），且後建方的內容存在被靜默覆寫的時間窗。**Action**：方案 A（fcntl file lock）優先級由「修補方向」升為「待排程」——已超過單日 2 次的頻率門檻；排程前 PM workaround 增加一條：跨 session 並行期間，create 後立即以 `grep -c "<自己的 title>" <新檔>` 確認內容歸屬，不只確認檔案存在。

### 頻率升級案例二：跨 worktree 結構性盲區（方案 A 落地後仍撞號）

前兩案例（同 session 並行派發、跨 session 同日二度撞號）皆發生在**同一份** tickets_dir 內——即便撞號，兩張票的檔案最終落在同一個目錄，後續可用 `ls` 直接發現重複並手動遷移。git worktree 工作模式常態化後出現第三種樣態：兩個 session 分別在**不同 worktree**（各自擁有獨立的 docs/work-logs 副本）呼叫 create。各自的 get_next_seq 掃描範圍（本地工作樹 glob ∪ main/master git ref，即「B3 方案」）皆看不到對方的 worktree 目錄；即使方案 A 的 `create_id_allocation_lock` 在各自 worktree 內都正確取鎖，兩把鎖本身落在不同的 tickets_dir 裡、互不阻擋——鎖存在但保護的臨界區從未真正重疊，屬「鎖粒度未涵蓋實際並行範圍」的結構性缺口，而非鎖機制本身失效。

實測驗證（`git worktree add` 建立兩個獨立 worktree 重現）：一方本地建立並 commit 一張 ticket 到自己的分支（未 merge 進 main），另一方**序列**（非並行）呼叫 get_next_seq，仍算出與前者相同的序號——證明問題不是臨界區未序列化，而是掃描範圍本身缺少「同 repo 下其他 worktree」這個資料來源；即使有鎖，只要掃描看不到對方的檔案，兩次呼叫依然會各自算出相同的下一個可用序號。

**升級訊號**：worktree 工作模式下，即使方案 A（目錄級鎖）與 B3 方案（main ref 聯集）皆已落地，跨 worktree create 仍完全無保護。**Consequence**：本案例的碰撞後果比前兩案例更隱蔽——兩張票分別落在兩個實體不同的目錄，彼此互不可見，不會出現在同一次 `ls` 結果裡，需要人工比對 commit 歷史才能發現，且其中一方的內容需要從對方的 commit 物件（`git show <hash>:<path>`）手動取回，而非簡單的檔名去重。

**Action（已落地）**：
1. 新增第三掃描來源 `list_ticket_files_from_sibling_worktrees`：列舉 `git worktree list --porcelain` 回報的所有 worktree 路徑，各自 glob 其 tickets_dir，與本地 glob / main ref 三方取聯集（`get_next_seq` 與 `get_next_child_seq` 皆已納入）。
2. `create_id_allocation_lock` 的鎖檔位置由「各 worktree 自己的 tickets_dir 內」改為「git-common-dir 下（所有 linked worktree 共用同一份物理路徑）」，使鎖真正跨 worktree 互斥；非 git 環境降級為原本的本地落鎖，不影響既有非 worktree 場景行為。
3. graceful degradation（取鎖失敗 warn 後無鎖續行）維持不變：結構性缺口已由掃描範圍擴大＋鎖位置改為共用位置解決，取鎖失敗仍是罕見的環境異常（lock file 無法建立），阻斷單 process create 的代價高於保留降級。

---

## 與其他 race condition 的差異

| 場景 | 鎖機制 |
|------|--------|
| git index.lock（PC-139）| git 自帶 lock 但跨 process 競爭 |
| sqlite WAL | DB 層原子化 |
| ticket create | **無 lock**（本 IMP）|

---

**Last Updated**: 2026-08-19
**Version**: 1.2.0 — 新增「頻率升級案例二：跨 worktree 結構性盲區」：方案 A（目錄級鎖）與 B3 方案（main ref 聯集）皆落地後，git worktree 常態化仍暴露結構性缺口——鎖粒度未涵蓋跨 worktree 範圍、掃描來源看不到 sibling worktree 本地已建立的 ticket。已落地修復：新增 sibling worktree 掃描第三來源、鎖檔改落 git-common-dir 跨 worktree 共用；graceful degradation 維持不變（結構性缺口已由前兩者解決）

**Version**: 1.1.0 — 新增「頻率升級案例：跨 session 同日二度撞號」；方案 A 升為待排程（trigger 綁修補 ticket）；PM workaround 增加 create 後內容歸屬確認

**Version**: 1.0.0
**Source**: W10-105 ANA 收尾時並行派發 2 個 ticket create 撞 ID（bi43cud13 vs b6uyaczhp），實際只建出 W10-107（後者內容），前者內容遺失需 serial 重建為 W10-108
