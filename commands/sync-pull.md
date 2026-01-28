---
description: 從獨立 repo 拉取最新 .claude 配置和專案模板 (https://github.com/tarrragon/claude.git)
---

# 從獨立 Repo 拉取最新 .claude 配置

請執行以下流程，從獨立 repo 拉取最新的 .claude 配置和專案模板到本專案。

## 拉取內容

- `.claude/` 目錄所有檔案（Hook、Agent、方法論、規則）
- `FLUTTER.md` Flutter 特定規範（更新到專案根目錄）

## 不覆蓋內容

- 根目錄 `CLAUDE.md`（保留專案特定配置）

## 檢查清單

1. **確認本地無未提交變更**
   - 檢查 `.claude`、`FLUTTER.md` 是否有未提交的變更
   - 如有變更，詢問用戶是否先提交或暫存

2. **執行拉取腳本**
   - 執行：
     ```bash
     ./scripts/sync-claude-pull.sh
     ```
   - 腳本會自動備份當前配置

3. **顯示備份位置**
   - 腳本會輸出備份目錄位置
   - 告知用戶如需還原可使用備份

4. **建議測試 Hook 系統**
   - 提醒用戶測試 Hook 系統是否正常運作
   - 建議重啟 Claude Code Session 驗證

## 新專案初始化

如果是新專案，需要手動建立 CLAUDE.md：

1. 複製 `.claude/templates/CLAUDE-template.md` 到根目錄
2. 重命名為 `CLAUDE.md`
3. 填入專案特定資訊（專案目標、技術選型、MCP 配置）
4. 驗證所有連結有效

## 還原方式

如果拉取後發現問題，可使用備份還原：

```bash
# 備份位置會在拉取時顯示
cp -r /tmp/備份目錄/.claude .
cp /tmp/備份目錄/FLUTTER.md .
```

## 注意事項

- 自動備份當前配置和專案模板到臨時目錄
- 拉取會完全替換本地 .claude 和 FLUTTER.md 檔案
- 不會覆蓋根目錄 CLAUDE.md（專案特定配置）
- 拉取後建議檢查 settings.local.json 是否需要調整
- 拉取後建議重啟 Claude Code Session
