---
description: 推送 .claude 配置和專案模板到獨立 repo (https://github.com/tarrragon/claude.git)
---

# 同步推送 .claude 配置到獨立 Repo

請執行以下流程，將本地 .claude 配置和專案模板推送到獨立 repo 供其他專案使用。

## 推送內容

- ✅ `.claude/` 目錄所有檔案（Hook、Agent、方法論）
- ✅ `CLAUDE.md` 通用開發規範
- ✅ `FLUTTER.md` Flutter 特定規範

## 檢查清單

1. **確認變更已提交到主專案**
   - 檢查 `.claude`、`CLAUDE.md`、`FLUTTER.md` 是否已提交
   - 確保提交訊息清楚描述變更內容

2. **詢問用戶提交訊息**
   - 如果尚未提交，先詢問用戶提交訊息
   - 使用 `git add .claude CLAUDE.md FLUTTER.md` 和 `git commit -m "訊息"` 提交

3. **執行推送腳本**
   - 使用用戶提供的提交訊息執行：
     ```bash
     ./scripts/sync-claude-push.sh "提交訊息"
     ```

4. **驗證推送結果**
   - 執行 `git fetch claude-shared`
   - 執行 `git log --oneline claude-shared/main | head -1` 查看最新 commit
   - 確認推送成功

## 提交訊息範例

建議用戶使用清楚的提交訊息格式：

```text
feat: 新增 XXX Hook 腳本
docs: 更新 YYY 方法論
refactor: 優化 ZZZ 檢查邏輯
fix: 修正 AAA 問題
```

## 注意事項

- ⚠️ 推送會使用 force push 覆蓋遠端歷史
- ✅ 確保變更已在本專案充分測試
- 📝 提交訊息要清楚說明變更內容
