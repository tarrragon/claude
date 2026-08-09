---
id: ARCH-BAL-015
title: 補救機制的掃描軸超出真實需求，把原問題轉化為另一類問題
category: architecture
severity: medium
created: 2026-08-06
---

# ARCH-BAL-015: 補救機制的掃描軸超出真實需求，把原問題轉化為另一類問題

## 摘要

**為修復原問題而建立的自動補救機制，若其掃描軸以「目錄」而非「真實需求條件」界定，就會對不具備該需求的檔案施加副作用，把原問題轉化成另一類問題。**（本案例：為 hook 補執行權限的機制波及不需要執行權限的測試檔，把啟動失敗問題轉化為版本控制雜訊。）原問題確實消失了，於是審查者判定機制有效；轉化後的問題出現在另一個維度（版本控制、建置產物、快取狀態），與原問題不共用症狀，因而不會被歸因回這個機制。

危險之處在於補救機制的正當性來自一份真實的事故記錄，使其免於被質疑。審查焦點集中在「原問題有沒有再發生」，而不是「這個機制對不需要它的對象做了什麼」。掃描軸過寬的成本被記在別的帳上。

## 症狀

- 某個自動修復機制長期運作、原問題確實不再發生
- 另一個維度出現反覆的低階雜訊：無主的版本控制變更、週期性的 chore commit、pull/merge 被非預期地阻擋
- 這些雜訊每次都被當作獨立的偶發事件手動處理，累積多筆同質 commit 而無人歸因
- 檢視掃描軸後發現，受影響對象中有相當比例從一開始就不需要這個修復
- 補救機制自身的「跳過」分支在真實環境從未執行，但其單元測試恆為綠

## 根因

| 環節 | 事實 | 後果 |
|------|------|------|
| 需求條件與目錄結構不重合 | 真正需要修復的是「符合條件 X 的檔案」，但條件 X 難以直接查詢 | 實作者以目錄作為條件 X 的代理指標 |
| 代理指標比真實條件寬 | 目錄下同時存在需要與不需要的對象 | 機制對不需要者施加副作用 |
| 副作用落在另一維度 | 原問題在執行期，副作用在版本控制 | 兩者不共用症狀，不會被歸因為同一機制 |
| 補救機制有事故背書 | 機制源於真實事故記錄 | 正當性不受質疑，審查只問「原問題有無再發」 |
| 副作用被逐次手動吸收 | 每次雜訊都能在數分鐘內手動處理掉 | 單次成本低到不觸發根因追查，長期累積無人負責 |

**與一般過度工程的差別**：過度工程是做了不需要的功能，成本止於開發；本 pattern 是需要的功能作用到不需要的對象，成本持續產生於運行期，且記在另一個維度的帳上。

**與 ARCH-BAL-014 的關係**：ARCH-BAL-014 是修復使下游既有缺陷的暴露面擴大，本 pattern 是修復機制自身的作用面超出需求。兩者都表現為「修復通過驗證但別處變糟」，區別在於前者暴露的是既有缺陷，後者製造的是新的副作用。本案例的修復自身即產生一次 ARCH-BAL-014 情形——解除 commit 的前置限制後，rebase 進行中的狀態首次進入該路徑，詳見下方「修復後的追加發現」。

## 案例：hook 執行權限自動修正波及測試檔（2026-08-06）

**背景**：`IMP-054` / `PC-086` 記錄了「hook 檔案缺少 exec bit 導致 session 啟動失敗」。補救方式是在 SessionStart 掃描 hook 目錄，對缺少 exec bit 的 `.py` 自動 `chmod +x`，並在工作區乾淨時自動 commit。

**掃描軸過寬**：實作使用 `hooks_dir.rglob("*.py")` 遞迴掃描，涵蓋 `tests/`、`acceptance_checkers/`、`archived/` 三個子目錄。但 hook 是以 `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>.py` 的形式被直接執行——實測 `settings.json` 中指向 `.claude/hooks/` 的 122 個註冊全部落在頂層，帶子目錄者 0 個。測試檔由 pytest import、`acceptance_checkers/` 由 `from acceptance_checkers import ...` 匯入，都不被 shell 執行，不需要 exec bit。

實測掃描面：頂層 98 個 `.py` 為真正需要 exec bit 的對象，三個子目錄合計 184 個屬誤掃，佔舊掃描軸 282 個 `.py` 的 65%。

**轉化後的問題**：每當新增 hook 測試檔（建立時為 644），下次 SessionStart 便對其 `chmod +x`，在 git 產生一筆 mode-only 變更。該變更不屬於任何 ticket，跨 session 留在工作區，最終以兩種形式暴露：

- 累積至少 7 筆「補上執行權限」的 chore commit
- 某次 `git pull` 被本地未提交的 mode 變更阻擋，而遠端待合併的 commit 正是內容等價的權限修正

**自動 commit 的失效**：補救機制原設計以「工作區恰好只有本次 chmod 的變更」為 commit 條件（集合全等比較）。SessionStart 時工作區通常已有開發中變更，條件幾乎不成立——實測連續 4 次 chmod 全數跳過，觸發成功率 0%。對應單元測試在 tmp repo 中構造乾淨工作區，恆為綠燈，因而未暴露此失效（參 quality-baseline 規則 1「測試綠燈不等於 Runtime 正確」）。

**修復**（0.2.1-W3-319）：

| 缺陷 | 修法 |
|------|------|
| 掃描軸過寬 | 改為僅掃描 `hooks_dir` 頂層（非遞迴）；三個子目錄自然排除 |
| commit 條件永不成立 | 廢除集合全等，改以 `git diff HEAD --numstat --no-renames` 取得「已追蹤、相對 HEAD 有變更、且零增刪行」的精確集合 |
| commit 可能吸收他人變更 | 改用 `git commit --only -- <paths>`，不吸收其他 session 已 stage 的內容（PC-BAL-008） |
| mode-only 判定基準過窄 | 判定基準由 index 改為 HEAD，涵蓋內容變更已被 stage 的情形 |

**修復後的追加發現**：多視角審查在上述修法上又找出兩個缺陷，兩者性質不同：

| 追加缺陷 | 性質 | 修法 |
|---------|------|------|
| rebase 暫停期間仍會 commit，該 commit 被 `rebase --continue` 收進 replay 序列成為分支永久祖先，其後所有 commit 的 SHA 都改變，全程無警告 | 暴露面擴大（ARCH-BAL-014 形態）：舊條件使 commit 路徑幾乎不執行，解除後 rebase 狀態才首次進入判定 | 以 `git symbolic-ref -q HEAD` 判斷 HEAD 是否掛在分支上；不逐一檢查 `.git/` 狀態檔，因 linked worktree 的 `.git` 是 gitfile，路徑存在性檢查在 worktree 中必然失效 |
| 全新未追蹤的 hook 檔無法提交（`--only` 要求路徑已被 git 追蹤） | 本次修復自身的迴歸：`git add` 改 `--only` 使 untracked 從可提交變為不可提交 | 改用 numstat 後未追蹤檔案不會出現在輸出中，特例自然消失。此類檔案本就不該由本機制提交——其整份內容都是新的，以「auto-fix executable permissions」為訊息提交會使 commit 訊息與內容不符 |

**未採取**：既有 154 個已提交為 755 的測試檔維持原狀。回改會產生一次大量 mode-only commit，成本高於收益，且 755 對測試檔無害。

## 防護

**設計補救機制時**：

- 先寫下真實需求條件（「什麼樣的檔案需要這個修復」），再檢查掃描軸是否恰好等於該條件。以目錄作代理指標時，逐一記錄目錄內不符合條件卻承受副作用的對象及其理由；誤掃比例過半即應改以條件判定取代目錄判定（本案例為 184/282，65%）
- 補救機制的副作用若落在版本控制、建置產物或快取等其他維度，在該維度也要留下可歸因的訊號（log 或 commit message 標明來源機制）
- 修好一個「從未觸發」的前置條件時，該條件下游的程式碼首次獲得執行機會。這些路徑同樣沒有真實環境驗證，須在同一次修復中一併稽核，並確認修法本身未改變下游的輸入假設（本案例：解除工作區乾淨限制後，rebase 進行中與未追蹤新檔兩種狀態首次進入 commit 路徑；同時 `git add` 改 `--only` 使未追蹤檔案從可提交變為不可提交）

**審查既有補救機制時**：

- 除了問「原問題有無再發生」，另問「這個機制每次執行對系統做了什麼，其中多少是必要的」
- 檢查機制的「跳過」「降級」分支在真實環境的實際觸發率。若某分支從未執行，其前置條件可能與真實環境不符，而非該情境不存在
- 反覆出現的同質低階雜訊（週期性 chore commit、每次都手動處理掉的小衝突）視為歸因訊號，追查是否有自動機制在持續產生它

## 相關

- `.claude/error-patterns/implementation/IMP-054-hook-missing-execute-permission.md` — 本補救機制的起源事故
- `.claude/error-patterns/process-compliance/PC-086-subagent-hook-script-missing-exec-bit.md` — 同主題事故
- `.claude/error-patterns/architecture/ARCH-BAL-014-upstream-filter-fix-widens-downstream-exposure.md` — 同族：修復使別處變糟；本案例的追加發現之一即為其實例
- `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md` — 共用 index 吸收他人變更
- `.claude/rules/core/quality-baseline.md` 規則 1 — 測試綠燈不等於 Runtime 正確
- `.claude/rules/core/opinionated-default-design.md` — 預設行為應引導正確做法
- Ticket `0.2.1-W3-319`
