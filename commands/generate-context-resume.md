# 🔄 generate-context-resume

## 描述
生成包含當前工作狀態和所有相關需求文件的上下文恢復提示詞，用於在上下文清除後恢復工作記憶。

## 使用方式
```text
/generate-context-resume
```

## 功能說明
此指令會執行以下操作：
1. **分析當前工作狀態** - 檢查最近的工作日誌和todolist狀態
2. **收集Git狀態** - 記錄未提交變更和最近提交記錄
3. **列出關鍵文件** - 提供核心規範文件清單和最近修改檔案
4. **生成恢復指引** - 提供具體的恢復執行步驟
5. **輸出提示詞檔案** - 儲存至 `$CLAUDE_PROJECT_DIR/.claude/hook-logs/context-resume-{timestamp}.md`

## 輸出內容包含
- 📋 當前工作狀態摘要
- ✅ TodoList 當前狀態
- 📝 最近工作日誌路徑
- 🔧 Git 狀態和最近提交
- 📚 核心規範文件引用
- 📝 最近修改的重要檔案
- 🛠 開發環境狀態
- 🚀 恢復執行指引

## 使用時機
- **上下文容量接近上限時** - 主動生成恢復提示詞
- **長時間暫停開發前** - 保存工作狀態便於後續恢復
- **切換開發環境時** - 確保工作狀態完整轉移
- **團隊交接時** - 提供完整的工作狀態說明

## 實際執行
```bash
$CLAUDE_PROJECT_DIR/.claude/hooks/generate-context-resume.sh
```

## 輸出範例位置
```text
$CLAUDE_PROJECT_DIR/.claude/hook-logs/context-resume-20250929_102316.md
```

## 注意事項
- 生成的恢復提示詞包含所有必要的文件路徑和執行指引
- 可直接複製提示詞內容作為新對話的起始輸入
- Hook系統也會在PreCompact時自動執行此功能
- 建議定期生成以確保工作狀態不遺失

## 相關Hook系統
此command與以下Hook系統整合：
- **PreCompact Hook** - 自動在上下文壓縮前執行
- **SessionStart Hook** - 啟動時檢查是否需要恢復
- **Stop Hook** - 結束時提醒是否需要生成恢復提示詞
