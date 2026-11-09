---
description: 推送 .claude 配置到獨立 repo (https://github.com/tarrragon/claude.git)
---

# 同步推送 .claude 配置到獨立 Repo

請執行以下流程，將本地 .claude 配置推送到獨立 repo 供其他專案使用。

## 推送內容

- `.claude/` 目錄所有檔案（Hook、Agent、方法論、規則、project-templates）

## 不推送內容

- 根目錄 `CLAUDE.md`（專案特定，不同步）

## 檢查清單

1. **發版前置：更新版號與變更紀錄**
   - 更新 `.claude/CHANGELOG.md`（腳本不產生條目，遠端內容即本地檔）
   - 更新 `.claude/VERSION` 為新版號，須數值上高於遠端 VERSION，且遠端不得已有 `v<版號>` tag；否則腳本 exit 1 拒絕推送

2. **確認變更已提交到主專案**
   - 檢查 `.claude` 是否已提交（含上一步的 VERSION 與 CHANGELOG）
   - 確保提交訊息清楚描述變更內容

3. **執行推送腳本**（推送版號 = 本地 `.claude/VERSION`，腳本不遞增、不回寫）
   - 自動分析模式（推薦）：腳本自動分析 .claude/ 相關 commit 生成 commit 訊息（僅作訊息，與版號無關）
     ```bash
     python3 ./.claude/scripts/sync-claude-push.py
     ```
   - 手動訊息模式：用戶指定 commit 訊息（覆蓋自動生成）
     ```bash
     python3 ./.claude/scripts/sync-claude-push.py "提交訊息"
     ```

4. **驗證推送結果**
   - 確認腳本輸出最後出現「成功推送 .claude 到獨立 repo！」訊息
   - 確認輸出含「已打並推送版本 tag v<版號>」（tag 失敗時腳本 exit 非 0，須補推 tag）
   - 確認腳本輸出包含 `To https://github.com/tarrragon/claude.git` 推送記錄
   - 注意：腳本使用臨時目錄操作，主專案沒有 `claude-shared` remote，**禁止**執行 `git fetch claude-shared`

## 自動 commit 訊息生成

腳本在無參數時會自動：
1. 取得遠端 repo 上次推送的時間戳
2. 收集主專案中該時間之後所有涉及 `.claude/` 的 commit
3. 按 conventional commit 類型分類（feat/fix/refactor/docs 等）
4. 過濾專案特定資訊（Ticket ID、版本號、Wave 編號）
5. 生成結構化摘要作為 commit 訊息（版號不由此推算）

## commit 訊息規範

獨立 repo 是跨專案通用框架，commit 訊息必須聚焦框架功能性變化：

| 正確 | 錯誤 |
|------|------|
| 新增 Hook 完整性檢查 | 完成 W5-012 Hook 重構 |
| 修正規則檔案路徑偵測 | v0.2.0 修復 |
| 重構規則系統為分層架構 | Wave 5 重構成果 |

## skill / hook 遷移後須跑 --clean 傳播刪除（防復發）

**Why**：`clean_stale_files`（刪除傳播）是 `--clean` opt-in 模式（預設不啟用）。將扁平 `hooks/*.py` 重組為 skill 自包含 `skills/*/hooks/`、或刪除任何 tracked 檔後，若後續 push 未帶 `--clean`，遠端會殘留舊路徑的孤兒，與新結構分叉，每次 full overlay sync 都複製孤兒（W1-003 議題二根因）。

**Consequence**：孤兒長期累積（W1-009 實測遠端殘留 755 孤兒，含 632 MagicMock 測試垃圾 + 28 遷移 hooks），且 full overlay 路徑的下游專案會反覆收到應已刪除的檔。

**Action**：

| 觸發情境 | 必要動作 |
|---------|---------|
| skill 遷移（扁平 hooks → skills/*/hooks/） | 遷移 commit 後跑一次 `sync-push --clean` 傳播刪除 |
| 刪除任何 tracked `.claude/` 檔 | 該批刪除 push 時帶 `--clean` |
| runtime state / worktree gitlink 殘留（should_exclude 保護範圍外） | `--clean` 不涵蓋，需手動 clone + `git rm` + push（見 W1-009 階段 1） |

## 無實質變更時自動跳過推送

腳本在無 `--force`／`--clean`／手動 commit 訊息時，會先比對「當前 `.claude/` 內容指紋」與「上次推送時的內容指紋」，並檢查上次推送後是否有新的 `.claude/` commit：

- 兩者皆無變化（含僅有 `VERSION` 記帳 commit）→ 印出「無實質變更可推送」並 `exit 0`，不推送、不打 tag。
- 有其他實質變更 → 進入發版閘門（版號遞增、tag 不存在檢查），通過後推送並打 tag。
- 帶 `--force`、`--clean` 或手動指定 commit 訊息時，一律跳過此檢查直接進入推送流程。

## 注意事項

- 確保變更已在本專案充分測試
- 根目錄 CLAUDE.md 不會被推送（專案特定配置）
- 版號由本地 `.claude/VERSION` 決定，腳本不推算也不回寫；發版流程見 `docs/roadmap.md` §5
