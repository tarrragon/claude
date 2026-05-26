---
id: PC-154
title: 派發 worktree agent 前未驗證兩項前置條件（worktree base 完整性 + ticket 已 claim）
category: process-compliance
severity: medium
source_case: 0.19.0-W1-043
created: 2026-05-23
---

# PC-154: 派發 worktree agent 前未驗證兩項前置條件

## 症狀

PM commit 後立即派發 worktree-isolation subagent，agent 在起步階段即受阻，已配置的 context 與 token 遭浪費。可觀察訊號：

- subagent 回報「找不到 Ticket `<id>`」或「Ticket does not exist」
- subagent 回報被「Ticket 必須被認領後才能開始工作」hook 擋下
- subagent 在 worktree 內 `ticket track full / claim / append-log` 全部失敗
- PM 從 task-notification 才發現失敗，整輪派發作廢

**Why**：worktree base 是否含所需檔案、ticket 是否已 claim，是兩個獨立前提；任一不滿足都讓 agent 起步即卡死。

**Consequence**：agent 無法 claim、無法填 body、無法執行任務，整輪派發需重派；嚴重時 agent 在受阻狀態下困惑地消耗大半 context 才回報（W1-040/W1-041 實測其中一個 agent 浪費大半工作）。

**Action**：派發 worktree agent 前，PM 逐一驗證下節「兩項前置條件」，任一不滿足先處理再派發。

## 兩項前置條件

### 前置 1：worktree base 含所需檔案

CC `isolation: "worktree"` 建立的 worktree 並非從當前本機 HEAD checkout，而是從較早的 checkpoint 或 `origin/main`。若 agent 依賴剛 commit 但未 push 的檔案（如新建 ticket md），worktree 看不到。技術根因見 IMP-066。

合法處理（擇一）：

| 方式 | 適用情境 |
|------|---------|
| 派發前 `git push` 同步 origin | agent 依賴的 commit 可公開推送 |
| 改用非 worktree 派發（agent 於主 repo cwd 工作） | agent 需看到本機未 push commit，或需 Edit `.claude/` |
| prompt 內以絕對路徑直接 Read 主 repo 檔案 | agent 只需讀取檔案內容，不需 worktree 隔離 |

### 前置 2：ticket 已 claim（派發 ≠ 認領）

dispatch agent 不會自動 claim ticket。ticket 停在 pending 時，agent 一動工即被「Ticket 必須被認領後才能開始工作」hook 擋下。

合法處理（擇一）：

| 方式 | 適用情境 |
|------|---------|
| PM 派發前先 `ticket track claim <id>` | 預設做法 |
| prompt 第一步明確要求 agent「先 claim ticket」 | agent 在可見該 ticket 的環境下執行 |

## 根因

### L1（流程層缺口）

PM 派發流程原無「派發前驗證前置條件」的強制檢查點。PM 直覺假設「commit 完成 = agent 看得到」與「dispatch = ticket 進入執行狀態」，兩個假設皆不成立。缺少檢查點使錯誤假設無從攔截。

### L2（訊號不可見性）

worktree base 落後、ticket 未 claim 在派發當下沒有任何警示。失敗訊號延遲到 agent 執行後的 task-notification 才出現，PM 無法在派發前自我糾正，只能事後重派。

### L3（worktree base 直覺落差）

「worktree 從哪個 commit 分支」不直觀。PM 直覺認為 worktree 反映當前本機狀態，實際上 CC `isolation:worktree` 以較早 checkpoint 或 `origin/main` 為 base（設計意圖為固定 baseline 避免並行 agent 互相干擾，詳見 IMP-066）。直覺與機制的落差是錯誤假設的來源。

## 案例

### 案例 1: 0.19.0-W1-040 / W1-041（2026-05-22）

**情境**：PM commit 4 個 ticket md 到本機 main（`76b0d070`）後，立即並行派發兩個 worktree-isolation agent。

**失敗**：兩 worktree 均基於 stale `origin/main`（merge commit `818a7de2`，本機 commit 尚未 push），agent 在 worktree 內找不到 ticket 檔，無法 claim 與填 body，被 hook 阻擋並困惑，其中一個 agent 浪費大半工作。

**修正**：改用非 worktree 派發（agent 於主 repo cwd 工作，直接看到本機 commit）+ 派發前先 `ticket track claim`。

## 防護

| 層級 | 機制 | 狀態 |
|------|------|------|
| 教訓層 | 本 PC-154 + memory `feedback_worktree_dispatch_prerequisites` | 已落地（0.19.0-W1-043） |
| 規則層 | `.claude/rules/core/pm-role.md` 派發前檢查清單補入兩項前置驗證 | 待後續 ticket 評估 |
| 並行派發層 | 並行派發多個 worktree agent 時，逐一驗證兩項前置條件，不可整批假設一致 | 自律 |

## 與 IMP-066 的關係

| 項目 | IMP-066 | PC-154 |
|------|---------|--------|
| 視角 | 實作層：解釋 worktree base 為何落後主 repo | 流程層：PM 派發前應驗證的前置條件 |
| 範圍 | 前置 1（worktree base 完整性）的技術根因 | 前置 1 + 前置 2（ticket 已 claim）的派發流程防護 |
| 關係 | 被 PC-154 前置 1 引用為技術根因 | IMP-066 的派發流程層對應 |

PC-154 前置 1 是 IMP-066 所述現象的派發流程防護；PC-154 另涵蓋 IMP-066 不含的前置 2（dispatch ≠ claim）。

## 相關 Pattern

- IMP-066: subagent isolation:worktree 看不到主 repo 新建 ticket —— 前置 1 的實作層根因
- ARCH-015: subagent `.claude/` 寫入保護 —— 「改用非 worktree 派發」的另一動機
- PC-019: worktree-merge-state-loss —— 派發前必須 commit 主 repo 變更

---

**Last Updated**: 2026-05-23 | **Source**: 0.19.0-W1-043（DOC：固化 worktree agent 派發失敗為 PC error-pattern）
