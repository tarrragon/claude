---
id: PC-V1-008
title: lockfile 版本漂移修正被 auto-preserve worktree commit 孤立並險遭當噪音丟棄
category: process-compliance
severity: medium
status: active
created: 2026-06-15
related:
- PC-166
- PC-145
---

# PC-V1-008: lockfile 版本漂移修正被 auto-preserve worktree commit 孤立並險遭當噪音丟棄

版本 bump 只改了 `package.json`（如 0.20.0）卻未重生 `package-lock.json`（停在舊版 0.19.0），造成 lockfile 版本漂移；該漂移的修正後來被某個 worktree 自動產生、訊息為「auto: worktree agent work preserved」的 commit 捕獲，但此類 commit 訊息讀起來像系統噪音，在 worktree 清理後成為孤立未合併 commit，險遭當成無用 artifact 直接丟棄。

**Why**：兩個機制疊加。其一，版本 bump 是「改 `package.json` 版本欄位」與「重生 lockfile」兩個獨立步驟，後者極易遺漏——`package-lock.json` 是大型機器生成檔，人工 bump 時常只動 `package.json`；session-start 的 package-version-sync 類檢查若回報「cached, skip sync」會跳過實際比對，使漂移無人察覺。其二，worktree 隔離機制在清理前用「auto: worktree agent work preserved」自動提交未保存變更，這個泛用訊息不描述內容，與真正的暫存噪音在訊息層無法區分，誘使接手者「這只是 auto-preserve 殘留」一語帶過直接刪除。

**Consequence**：

| 層級 | 影響 |
|------|------|
| 可重現性 | `npm ci` / 鎖定安裝以 lockfile 版本為準，漂移使 lockfile 與 `package.json` 聲明不一致，潛在影響 CI / 發布產物版本標記 |
| 真實修正遺失 | 修正漂移的 commit 被當噪音刪除 → 漂移持續，且修正工作白做；若該 commit 含其他孤兒變更會一併遺失（[[PC-166]] 世界平面 ghost 副作用同類風險） |
| 偵測盲區 | 「cached, skip sync」式快取跳過讓版本檢查長期不實際執行，漂移可潛伏多個版本 |
| 雜訊疲勞 | worktree 清理後殘留的孤立分支持續觸發合併提醒 hook，但內容已 superseded，形成 false-positive nag |

**Action**：

1. 版本 bump 必須在同一變更內**重生並提交 `package-lock.json`**（`npm install` 後 commit lockfile），不可只改 `package.json`。發布流程的 acceptance 應含「lockfile 版本欄位 == package.json 版本」檢查。
2. 遇到「auto: worktree agent work preserved」或任何泛用訊息的孤立 commit，**先 `git show <sha>` 檢視 diff 內容再決定去留**，禁止僅憑訊息斷定為噪音直接刪除（[[PC-166]] 記錄平面非 ground truth：commit 訊息不等於 commit 內容）。
3. 刪除孤立分支 / worktree 前先確認其唯一內容是否已被其他 commit 取代（superseded 才可安全刪）；若內容必要，先套用（如 `npm install` 重生 lockfile）再清理孤立 ref。
4. 對「cached, skip sync」類快取跳過的版本檢查，發布前或定期強制一次真實比對（[[PC-145]] stale 安裝幻覺同類——快取狀態不等於真實狀態）。

---

## 觸發案例

### gen_test_data worktree 的 lockfile 漂移修正（2026-06-15）

**背景**：session 收尾推送時，worktree 合併提醒 hook 持續回報 `gen_test_data` 分支有 1 個未合併 commit `a706e3ace`「auto: worktree agent work preserved (1 files: package-lock.json)」。

**事件鏈**：

1. **初始框架風險**：commit 訊息「auto: worktree agent work preserved」讀起來像系統自動殘留，第一直覺易判為「無關噪音，直接刪分支」。
2. **檢視內容（正確動作）**：`git show a706e3ace` 顯示僅 `package-lock.json` 2 行變更——`version` 0.19.0 → 0.20.0。
3. **比對 main 真實狀態**：`package.json` = **0.20.0**，但 `package-lock.json` = **0.19.0**。確認是真實版本漂移——某次版本 bump 改了 `package.json` 未重生 lockfile，session-start 的「Package Version Sync - cached, skip sync」跳過未抓到。
4. **判定**：auto-preserve commit 的內容**有必要**，不是噪音——它正是修正此漂移。
5. **套用**：`npm install --legacy-peer-deps` 重生 lockfile，結果恰好就是 2 行版本同步（其餘內容本已一致），commit + push origin/main。
6. **清理**：`gen_test_data` worktree 與分支 ref 在本 repo 與 prowl clone 兩處皆已不存在（worktree 目錄移除、無 branch ref），僅剩 dangling commit `a706e3ace`，`git gc --prune=now` 回收。其內容已被新 commit superseded，刪除安全。

**關鍵教訓**：若依「auto-preserve 是噪音」的初始框架直接刪分支，會永久遺失唯一一份修正 lockfile 漂移的變更，漂移持續潛伏。`git show` 一步檢視內容即區分「真實孤兒修正」與「暫存噪音」，是 [[PC-166]]「記錄平面（commit 訊息）非 ground truth，重大去留決策以世界平面（commit 內容 / 檔案真實狀態）為準」的具體實踐。
