---
id: PC-GPD-022
title: 跨間接層的驗證錯誤指向被檢查層而非損壞層
category: process-compliance
severity: medium
created: 2026-09-10
updated: 2026-09-10
---
# PC-GPD-022: 跨間接層的驗證錯誤指向被檢查層而非損壞層

## 狀態：git worktree 形態已由最小重現確立；跨載體泛化仍為假說

本檔原記錄為待驗證假說（原始物證已刪除、事後重現產出不同訊息）。**2026-09-10 以最小重現實驗確立了 git worktree 形態**：原始訊息可被穩定重現，且可證偽條件四項全部滿足（見「最小重現」節）。

仍為假說的部分是**跨載體的泛化**——本檔列舉的其他間接層（CLI shim 與解析目標、hook 註冊表與被註冊檔案、error-pattern canonical issue 欄位與 issue 本體、skill 路由表與被路由檔案）尚無任一經查證的實例。引用本檔套用到 git worktree 以外的載體時，須連同本節一起引用。

## 基本資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-GPD-022 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 提出日期 | 2026-09-10 |
| 證據強度 | git worktree 形態：確定性最小重現（git 2.50.1）。其他載體：無實例 |

## 模式內容

當一個驗證動作跨越間接層——命名對象 A 內含指向 B 的指標，而驗證需要 A 與 B 兩側都成立——失敗訊息可能只指出 A，因為 A 是驗證器直接持有的參數。若實際損壞在 B，則：

1. 訊息指名 A
2. 操作者依訊息檢視 A，發現 A 形式完好
3. 操作者的結論落向「損壞無法理解」，而非「訊息指的不是損壞的那一層」
4. 正確的下一步（沿指標檢視 B）不會被想到，因為訊息從未提及 B 存在

**Consequence**：操作者停在「壞到看不懂」，處置退化為整個刪掉重來。刪除同時銷毀了唯一的物證，使該次失效無法被歸因，下一次撞到的人仍從零開始。

**Action**：驗證錯誤指名一個對象、而該對象逐項比對後確實完好時，在下「無法理解」的結論之前，**先沿該對象持有的指標檢視一層**。成本是一次 `cat` 或 `ls`，收益是把「不可理解」與「指標另一端損壞」區分開。

## 最小重現（git worktree 形態，git 2.50.1 / Apple Git-155）

`worktree create` 被逾時中止時，殘骸的形狀取決於中止時點。全程**不改動** worktree 側的 `.git` gitfile（內容為形式完好的 `gitdir:` 指向存在的 admin 路徑），僅移除 admin 側（`<repo>/.git/worktrees/<name>/`）的單一檔案：

| admin 側殘缺 | `git worktree remove` 訊息 | `git worktree prune -v` |
|---|---|---|
| 目錄整個不存在 | `is not a working tree` | 靜默 |
| 缺 `gitdir` | `is not a working tree` | `Removing worktrees/<name>: gitdir file does not exist` |
| 缺 `commondir` | `validation failed ... '<worktree>/.git' is not a .git file, error code 7` | 靜默 |
| 缺 `HEAD` | `validation failed ... '<worktree>/.git' is not a .git file, error code 7` | 靜默 |

`error code 7` 是 git `read_gitfile_gently()` 的 `READ_GITFILE_ERR_NOT_A_REPO`：gitfile 讀得到、格式合法、目標路徑存在，但目標不被認可為 repo。**錯誤碼本身就編碼了「壞在指標另一端」，訊息文字未將其翻出**。

**可證偽條件的滿足情形**：

| 條件 | 滿足 |
|------|------|
| 1. 訊息指名一個具體對象 A | 指名 `<worktree>/.git` |
| 2. A 經檢視確實形式完好 | A 全程未被改動，與健康樣本逐位元組相同 |
| 3. 實際損壞在 B 且可獨立確認 | admin 側缺 `commondir` / `HEAD`，`ls` 與健康樣本比對即見 |
| 4. 訊息完全未提及 B 或指標關係 | 訊息無 admin 路徑、無 `gitdir:` 字樣 |

## 反直覺點：prune 不是這個形態的診斷手段

**`prune` 會說話的形狀，正好是不會產生原始訊息的形狀。**產生 `error code 7` 時，`git worktree prune -v` 與 `prune -v --dry-run` 皆為 0 行輸出、rc=0，且 prune 之後 `remove` 仍以同一訊息失敗；只有「缺 `gitdir`」那一種形狀 prune 才有輸出，而該形狀的 `remove` 訊息並非 `error code 7`。

**Why 值得單獨記**：事後回述容易把「後來清掉了」壓縮成「prune 說出了原因」。這兩件事在此形態下互斥——本節即為該回述的實測反例（`tool-output-trust-rules` 規則 5：對話記憶屬記錄平面，不是 ground truth）。

**真正自動指名 B 的診斷**，從 worktree 內部問：

```
$ git -C <worktree> rev-parse --git-dir
fatal: not a git repository: <repo>/.git/worktrees/<name>
```

此訊息直接印出 admin 路徑。次級訊號：`git worktree list` 中損壞的那一列 commit 欄顯示 `0000000`。

**處置**：確認 admin 側殘缺後，刪除 worktree 目錄與 admin 目錄兩側，再 `prune`。刪除前先 `ls` admin 側並記錄缺哪些檔案——那是唯一的物證。

## 相關

- `PC-GPD-021`——本檔原假說的提出過程即該模式的實例（機制解釋未經查證而以已查證語氣呈現）；本次以最小重現取代推測，是該模式預防措施的正向實作
- `PC-GPD-019`——形狀相符終止查證；本模式為其特化情境：訊息指名的對象形狀相符（是個真的 gitfile），因而終止了往下的查證
- `.claude/rules/core/tool-output-trust-rules.md` 規則 5——記錄平面（含自己的對話記憶）不是 ground truth；「反直覺點」節為其實例
- `.claude/rules/core/tool-output-trust-rules.md` 規則 6——驗證器警告與工具自動產出衝突時先查建立端；與本模式同屬「驗證輸出本身需要被判讀」的家族，斷點不同（規則 6 是判準過期，本模式是指向錯層）
