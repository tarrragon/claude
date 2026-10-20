---
id: IMP-GPD-007
title: 解析 git branch 給人看的輸出取分支名，漏掉 worktree 已 checkout 分支的「+ 」前綴
severity: 中
status: active
---

# IMP-GPD-007: 解析 git branch 給人看的輸出取分支名，漏掉 worktree 已 checkout 分支的「+ 」前綴

## 基本資訊

- **Pattern ID**: IMP-GPD-007
- **分類**: 實作（implementation）
- **風險等級**: 中（拿去比對時判定恆錯，且錯在 worktree 流程的必經狀態；只拿來顯示時僅影響可讀性）
- **來源版本**: 0.5.0
- **相關 Pattern**:
  - 守衛以實作路徑的副產物判定的同類模式：本模式同屬「判定依據取自不穩定的表層」，表層是輸出格式而非工作區狀態
  - 守衛以正則或子字串比對 git 命令本身的同類模式：本模式解析的是 git 給人看的輸出，該模式解析的是 git 命令字面
  - 兩者皆為本地分域編號，尚未推上共用通道，依 `.claude/references/reference-stability-rules.md` 規則 8 以描述代替編號

---

## 問題描述

### 症狀

- 以 `git branch --merged <base>` 或 `git branch --no-merged <base>` 的輸出逐行取分支名，清理方式為 `strip()` 或 `lstrip('* ')`
- 被另一個 worktree checkout 的分支，git 在行首加「+ 」（當前 checkout 的分支加「* 」）。清理只去空白與「*」，名稱帶著「+ 」留下
- 依用途有三種後果：
  - **全等比對**（`branch in merged_list`）：被 worktree checkout 的分支恆不相等，判為「未合併」。清理工具的對象正好都是 worktree 已 checkout 的分支，於是每次都誤報，安全警告淪為每次必帶 `--force`
  - **只顯示**：清單印出「+ feat/x」，可讀性受損，日後若有人把清單拿去比對就會落入上一種
  - **子字串比對**（`ticket_id in name`）：前綴不影響命中，但子字串本身會讓鄰近識別字互相命中（如 `X-36` 命中 `feat/X-363`）

### 根因

`git branch` 的預設輸出是給人看的格式（porcelain 指令的人類可讀輸出），行首標記會隨工作區狀態變化：

| 行首 | 意義 | 何時出現 |
|------|------|---------|
| `* ` | 當前 checkout 的分支 | 主工作樹所在分支 |
| `+ ` | 被其他 worktree checkout 的分支 | 有 linked worktree 時（本機實測 git 2.50.1 出現；引入版本未查證） |
| 兩個空白 | 其他分支 | 一般情況 |

清理邏輯在只有 `*` 標記的時期寫成，`+` 標記後來才出現，且只在有 linked worktree 時出現。解析給人看的輸出，等於把「目前見過的標記集合」當成格式契約。

### 缺陷為何長期未被發現

- 單元測試 mock 掉 git 呼叫，mock 回傳的是作者想像中的輸出（不含「+ 」），測試全綠
- 不在 worktree 流程裡的分支（沒有 linked worktree checkout）輸出無「+ 」，手動試也正常
- 只顯示的用途不影響判定結果，帶前綴的名稱被讀者略過

---

## 解決方案

不解析給人看的輸出，改用輸出格式穩定的 plumbing 或明確指定格式：

| 需求 | 改用 | 判讀 |
|------|------|------|
| 分支是否已合併到 base | `git merge-base --is-ancestor <branch> <base>` | 結束碼 0 為已合併；1 為未合併；128 為 ref 不存在 |
| 列出未合併／已合併分支名 | `git for-each-ref --no-merged=<base> --format='%(refname:short)' refs/heads` | 每行一個純分支名，無標記 |
| 依識別字找分支 | 對純分支名做邊界比對（全等，或識別字後接非識別字字元） | 不用子字串 `in` |

以結束碼判定時，非 0 一律視為未合併：含 1（未合併）、128（ref 不存在）、逾時、git 執行檔不存在。失敗方向是多報「未合併」，使清理停手而非誤刪，方向保守。

---

## 預防措施

1. **寫解析前自問**：這個指令的輸出是給人看的，還是有穩定格式？給人看的輸出改用 plumbing、`--format`、`--porcelain` 或結束碼
2. **測試用真實 git**：在暫存目錄 `git init`、建分支，並以 `git worktree add` 讓分支處於 checkout 狀態。mock 回傳值由作者撰寫，會遮住真實格式（`.claude/rules/core/quality-baseline.md` 規則 1 邊界：mock 替代真實依賴）
3. **正向對照涵蓋 checkout 狀態**：未合併的分支要在「一般」與「被 worktree checkout」兩種狀態下都判為未合併，另加分支不存在的情況（`.claude/rules/core/test-assertion-design-rules.md` E2）
4. **修一處時盤點同類**：以 `grep -rn -e '"--merged"' -e '"--no-merged"' -e 'branch --merged' -e 'branch --no-merged'` 掃描同庫其他解析點，同病因往往不只一處
