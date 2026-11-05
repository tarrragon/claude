---
id: IMP-GPD-025
title: zsh 下未加大括號的變數後接冒號（如 "$B:assets/x"）被解讀為歷史修飾詞，git show 的 <rev>:<path> 被改寫成絕對路徑
status: active
severity: 低
---

# IMP-GPD-025: zsh 把 `$var:` 後的字母當修飾詞，`git show "$B:path"` 靜默變成另一個參數

## 基本資訊

- **Pattern ID**: IMP-GPD-025
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.6.0
- **發現日期**: 2026-11-05
- **風險等級**: 低
- **影響範圍**: 在 zsh 中以變數存分支名或 commit，再組成 `<rev>:<path>` 傳給 `git show`／`git cat-file` 等命令的 Bash 呼叫

---

## 問題描述

### 症狀

PM 用 `B=worktree-agent-<id>` 存分支名，接著執行 `git show "$B:assets/schema/builtin_tracking_schema.json"`，得到以下錯誤：

```
fatal: ambiguous argument '<repo 絕對路徑>/worktree-agent-<id>ssets/schema/builtin_tracking_schema.json': unknown revision or path not in the working tree.
```

後面接著的 `cmp` 讀到空的 stdin，回報 `EOF on stdin`，`grep -c` 回報 0。如果只看計數或 cmp 的結果，會誤以為「副本不含新邊」或「兩檔不一致」。

### 根因

zsh 的參數展開支援 csh 風格的修飾詞：`$B:a` 會把 `$B` 轉成絕對路徑，`:h`、`:t`、`:r`、`:e` 等也是同類修飾詞。即使放在雙引號內，`$B:` 後面緊接的字母仍會被當成修飾詞。在 `$B:assets/...` 裡，`:a` 被吃掉當作「轉絕對路徑」，剩下的 `ssets/...` 直接接在後面，`<rev>:<path>` 語法因此被拆壞。bash 沒有這個行為，所以從 bash 習慣搬過來的寫法會在 zsh 靜默變質。

失效形態是「命令失敗，下游命令讀到空輸入卻照樣產出看似合法的結果」。如果過濾輸出只看最後的計數，這次失敗就和「真的不一致」長得一模一樣（與 `bash-tool-usage-rules` 規則二的過濾方向問題同屬一類）。

---

## 解決方案

變數名一律加大括號：`git show "${B}:assets/schema/x.json"`。大括號會在 `}` 結束參數名稱，後面的 `:` 就不會被當成修飾詞。

## 預防措施

- 在 zsh 中，變數後面緊接 `:` 時一律寫成 `${var}`，不只限於 git 的 `<rev>:<path>`（`scp`、`host:port`、`${var}:suffix` 都適用）。
- 用 `cmp`、`grep -c` 下判斷前，先確認上游命令的 stderr 是否有 `fatal:`，或分開讀上游命令的 rc，不要只看最後的計數。

## 發現情境

2026-11-05，PM 在合併前以固定值核對 App 內建型別表副本時發現；改寫成 `${B}` 後 cmp rc=0，新邊型命中 2 次。
