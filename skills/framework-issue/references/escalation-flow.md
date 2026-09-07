# 框架問題升級流程

處理 ticket 過程中，若問題本質屬於 Claude 框架而非本專案，正確路徑是提 framework issue，不在本地當下修復。四個環節：介入判斷、兩條後續路徑、issue 關閉協定、回報前查重 SOP。

- [介入判斷：框架問題 vs 專案問題](#介入判斷框架問題-vs-專案問題)
- [兩條路徑](#兩條路徑)
- [Issue 關閉協定](#issue-關閉協定)
- [回報前查重 SOP](#回報前查重-sop)

## 介入判斷：框架問題 vs 專案問題

**判準**（同時符合視為框架問題）：

| 判準 | 說明 |
|------|------|
| 抽象可攜性 | 敘述替換掉本專案名稱與檔案路徑後依然成立（「Hook X 對某類副檔名誤判」而非「本專案的 Y 檔案有 bug」） |
| 資產範圍 | 根源在 `.claude/` 下的通用資產（hooks／skills／rules／methodologies／agents），非 `lib/`、`docs/` 等專案專屬產物 |

**Why**：框架資產由 sync-push／sync-pull 在多個 consumer 間共享，本地直接修復只解決當前專案的徵狀，其他 consumer 仍帶著同一缺陷；貼著單一 consumer 特例的修法，日後 sync-pull 覆蓋時復發。

**Consequence**：略過判斷直接在當下 ticket 內修 `.claude/` 通用資產，修復困在本地 commit 歷史不會傳播；下次 `sync-pull` 可能用上游未修的舊版覆蓋掉本地修復，且無 canonical 記錄可查。

**Action**：識別為框架問題時走查重 SOP，再依兩條路徑擇一銜接，不在當前 ticket 直接編輯 `.claude/` 檔案了事。

## 兩條路徑

| 路徑 | 適用情境 | 動作 |
|------|---------|------|
| A：先記錄，不接手 | 當下 ticket 的主要目標不是修這個框架問題（順手發現） | 建立或附加 framework issue 記錄徵狀；本地相關 ticket 若因此阻塞則以收束配方的 close 命令關閉（reason-note 寫「已遷至 tarrragon/claude#N」），並**當下**建一張驗證 ticket（pending，`why` 引用該 issue，`when` 寫「sync-pull 帶回含 fix-version 的版本後」），承擔者是執行 `sync-pull` 的 PM，在 runqueue 看到它即接手 |
| B：當下接手 | 框架問題本身就是當前任務目標，或不修復無法繼續 | 直接在框架 canonical repo 修復，修復後走下方關閉協定 |

**Why**：框架問題的修復地點是 canonical repo；本地 ticket 若卡在框架缺陷上又不切割，專案層任務的驗收會綁死在框架修復進度上。

**Consequence**：路徑 A 若省略 close 與驗證票、直接放著，違反品質基線規則 5（發現必須追蹤）與決策 trigger 綁定規則。issue ref 與「sync-pull 帶回修復」都不是合法 trigger，合法 trigger 只有 ticket，所以驗證票要在路徑 A 當下建立，不等修復發生。

**Action**：路徑 A 的 close 命令與 reason-note 禁詞見 `references/ticket-intake.md` 的〈步驟五：ticket 處置〉；路徑名不可抄進 reason-note。路徑 B 修復完成後立即執行關閉協定。

## Issue 關閉協定

修復完成到正式 close 之間，必須依序完成版本號回註，讓其他 consumer 能追溯此修復落在框架的哪個版本：

```
修復完成 → sync-push（取得框架版本號）→ fix-version 回註 issue → close
```

| 步驟 | 命令 | 說明 |
|------|------|------|
| 1. 推送修復 | `/sync-push` | 推送後本地 `.claude/VERSION` 即為此次推送後的框架版本號 |
| 2. 版本號回註 | `python3 .claude/skills/framework-issue/scripts/fix_version.py <issue-ref> --summary "徵狀摘要"` | `--version` 省略時自動讀本地 `.claude/VERSION`，寫入 body 的 fix-versions 表格 |
| 3. 關閉 issue | `python3 .claude/skills/framework-issue/scripts/close_issue.py <issue-ref> [--reason completed]` | 前置檢查 fix-versions 非空，缺少即 exit 3 拒關 |

close 後在其他情境發現同一 issue 的新徵狀，不重開新 issue：對同一 issue 再跑一次「修復 → sync-push → fix-version」，版本號表格可累積多筆。

**Why**：版本號前置檢查是防止「各專案各自關閉造成同步狀態不一致」的機械閘門。**Consequence**：跳過 `fix-version` 直接 `close` 被 exit 3 拒絕；繞過閘門在網頁關閉，其他 consumer 執行查重 SOP 時誤判此 issue 已有版本可追溯。**Action**：路徑 B 或舊 issue 新徵狀，一律走三步不省略。「當下接手」與「先記錄」兩條路徑的分流見上節，本協定只管修復完成之後。

## 回報前查重 SOP

建立新 framework issue 前，先查既有 issue：

```bash
python3 .claude/skills/framework-issue/scripts/section_comment.py dedup --keywords "詞一" "詞二"
```

| 查詢結果 | 判讀 | 動作 |
|---------|------|------|
| 命中 issue，closed 且已有 fix-versions 版本號 | 該問題可能已在框架修復，只是本專案尚未同步 | `/sync-pull` 拉取該版本後驗證徵狀是否消失；仍存在則視為新徵狀，對同一 issue 追加 `fix-version` |
| 命中 issue，open 或查無版本號 | 已被記錄但尚未修復，或修復未完整回註 | 帶著既有 issue 的脈絡接續排查，以 `observe` 附加新徵狀；判定為全新獨立問題才建新 issue |
| 查無命中 | 尚未有人記錄 | 依介入判斷與兩條路徑建立新 issue |

命中清單的關係判定（重複／切分／引用）見 `references/comment-as-section-protocol.md` 的〈init 前查重：三種關係處置〉。

**Why**：`dedup` 成本遠低於重複建立後才發現。**Consequence**：略過查重使同一徵狀在框架 repo 產生多筆記錄，稀釋 canonical 追蹤的價值。一個已發生的形態：來源專案已在 canonical 修好的問題，移交線索只寫在該專案 closed 票的備註，下游 session 踩到同一誤判時查 runqueue 看不到，依流程正確地建了新票並準備升級到 canonical，目的地正是已修好的地方；每一步都正確，但「已修好」對下游不可達。`dedup` 涵蓋 comment 內文，是唯一能碰到這類事實的入口。
