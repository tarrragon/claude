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

1. **確認變更已提交到主專案**
   - 檢查 `.claude` 是否已提交
   - 確保提交訊息清楚描述變更內容

2. **執行推送腳本**
   - 自動分析模式（推薦）：腳本自動分析 .claude/ 相關 commit 生成結構化摘要
     ```bash
     python3 ./.claude/scripts/sync-claude-push.py
     ```
   - 手動訊息模式：用戶指定 commit 訊息（覆蓋自動生成）
     ```bash
     python3 ./.claude/scripts/sync-claude-push.py "提交訊息"
     ```

3. **驗證推送結果**
   - 確認腳本輸出最後出現「成功推送 .claude 到獨立 repo！」訊息
   - 確認腳本輸出包含 `To https://github.com/tarrragon/claude.git` 推送記錄
   - 注意：腳本使用臨時目錄操作，主專案沒有 `claude-shared` remote，**禁止**執行 `git fetch claude-shared`

## 自動 commit 訊息生成

腳本在無參數時會自動：
1. 取得遠端 repo 上次推送的時間戳
2. 收集主專案中該時間之後所有涉及 `.claude/` 的 commit
3. 按 conventional commit 類型分類（feat/fix/refactor/docs 等）
4. 過濾專案特定資訊（Ticket ID、版本號、Wave 編號）
5. 根據 commit 類型建議版本遞增幅度（patch/minor/major）
6. 生成結構化摘要作為 commit 訊息

## commit 訊息規範

獨立 repo 是跨專案通用框架，commit 訊息必須聚焦框架功能性變化：

| 正確 | 錯誤 |
|------|------|
| 新增 Hook 完整性檢查 | 完成 W5-012 Hook 重構 |
| 修正規則檔案路徑偵測 | v0.2.0 修復 |
| 重構規則系統為分層架構 | Wave 5 重構成果 |

## 注意事項

- 確保變更已在本專案充分測試
- 根目錄 CLAUDE.md 不會被推送（專案特定配置）
- 版本遞增由腳本根據 commit 類型自動決定
