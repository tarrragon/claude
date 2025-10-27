# 🧹 resume-mission-complete

## 描述
清理上下文恢復相關記憶檔案，標記恢復任務完成，避免重複執行和檔案累積。

## 使用方式
```text
/resume-mission-complete
```

## 功能說明
此指令會執行以下清理操作：
1. **清理恢復提示詞檔案** - 移除 `.claude/hook-logs/context-resume-*.md` 檔案
2. **記錄完成狀態** - 建立完成標記檔案，防止重複恢復
3. **整理Hook日誌** - 清理過期的Hook執行日誌
4. **重置恢復計數** - 重置恢復相關的計數器和狀態
5. **生成清理報告** - 輸出清理作業的詳細報告

## 清理目標檔案
### 🗂 恢復提示詞檔案
- `$CLAUDE_PROJECT_DIR/.claude/hook-logs/context-resume-*.md`
- `$CLAUDE_PROJECT_DIR/.claude/hook-logs/pre-compact-*.log`

### 📋 Hook執行日誌 (保留最近5個)
- `$CLAUDE_PROJECT_DIR/.claude/hook-logs/startup-*.log`
- `$CLAUDE_PROJECT_DIR/.claude/hook-logs/prompt-submit-*.log`
- `$CLAUDE_PROJECT_DIR/.claude/hook-logs/stop-*.log`

### 🔄 狀態重置
- 清除恢復相關的臨時狀態檔案
- 重置Hook日誌輪轉計數器

## 使用時機
- **成功恢復工作狀態後** - 清理恢復過程中產生的檔案
- **切換開發階段時** - 清理上一階段的恢復記錄
- **定期維護時** - 避免hook-logs目錄檔案累積
- **儲存空間清理時** - 移除不再需要的恢復檔案

## 安全機制
- **保留最新檔案** - 保留最近的Hook日誌以供除錯
- **備份重要記錄** - 關鍵工作狀態會備份到memory/
- **確認機制** - 清理前顯示將被移除的檔案清單
- **恢復功能** - 提供撤銷清理的選項

## 實際執行
```bash
$CLAUDE_PROJECT_DIR/.claude/scripts/resume-mission-complete.sh
```

## 輸出範例
```text
🧹 上下文恢復任務完成清理
📁 專案目錄: /Users/tarragon/Projects/book_overview_app

🗑️ 清理檔案:
- context-resume-20250929_102316.md (已移除)
- context-resume-20250929_104944.md (已移除)
- pre-compact-20250929_102248.log (已移除)

📊 清理統計:
- 恢復提示詞檔案: 2個 (3.2KB)
- Hook日誌檔案: 1個 (0.8KB)
- 總計釋放空間: 4.0KB

✅ 清理完成，系統已準備好進行新的開發工作
```

## 注意事項
- 執行前會列出要清理的檔案，確認後再執行
- 重要的工作狀態記錄會保存到memory/目錄
- 清理操作不可逆，建議在確認恢復成功後執行
- 不會影響正在進行的Hook系統運作

## 相關指令
- `/generate-context-resume` - 生成上下文恢復提示詞
- Hook系統會自動在適當時機建議執行此清理指令
