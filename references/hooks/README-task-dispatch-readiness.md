# 任務分派準備度檢查 Hook - 快速參考

## 🎯 功能說明

在使用 Task 工具分派任務前，自動檢查任務描述是否包含必要的參考文件，確保符合敏捷重構方法論。

## ✅ 必須包含的參考文件

### 1. UseCase 參考
**格式**: `UC-XX`（例如：UC-01、UC-02）
**說明**: 指明任務對應的使用案例編號
**參考文件**: `docs/app-use-cases.md`

### 2. 流程圖 Event 參考
**格式**: `Event N` 或 `事件 N`（例如：Event 3、事件 5）
**說明**: 標明任務處理哪些事件
**參考文件**: `docs/event-driven-architecture-design.md`

### 3. 架構規範引用
**關鍵字**:
- `Clean Architecture`
- `Domain 層`
- `Application 層`
- `Presentation 層`
- `Infrastructure 層`

**說明**: 明確指出任務屬於哪個架構層級

### 4. 依賴類別說明
**關鍵字**:
- `Repository`
- `Service`
- `Entity`
- `ValueObject`
- `UseCase`

**說明**: 說明任務需要依賴哪些類別或介面

## 📝 正確範例

### ✅ 完整的任務描述

```text
請實作 UC-01 書籍新增功能，處理 Event 3 使用者觸發新增，屬於 Application 層，依賴 BookRepository 和 Book Entity
```

**包含**:
- ✅ UseCase: `UC-01`
- ✅ Event: `Event 3`
- ✅ 架構層級: `Application 層`
- ✅ 依賴類別: `BookRepository` 和 `Book Entity`

### ✅ 另一個正確範例

```text
請實作 UC-05 書籍搜尋功能，對應 Event 12 使用者輸入搜尋關鍵字，按照 Clean Architecture 原則設計，使用 SearchService 和 BookRepository
```

**包含**:
- ✅ UseCase: `UC-05`
- ✅ Event: `Event 12`
- ✅ 架構規範: `Clean Architecture`
- ✅ 依賴類別: `SearchService` 和 `BookRepository`

## ❌ 錯誤範例

### ❌ 缺少所有參考文件

```text
請實作一個書籍新增功能
```

**缺失**:
- ❌ 沒有 UseCase 參考
- ❌ 沒有 Event 參考
- ❌ 沒有架構規範
- ❌ 沒有依賴類別說明

**結果**: 任務被拒絕

### ❌ 只有部分參考文件

```text
請實作 UC-01 書籍新增功能
```

**缺失**:
- ✅ 有 UseCase 參考
- ❌ 沒有 Event 參考
- ❌ 沒有架構規範
- ❌ 沒有依賴類別說明

**結果**: 任務被拒絕

## 🔍 Hook 行為

### 允許執行
- 所有 4 項檢查都通過
- Exit Code: 0
- 日誌記錄在 `.claude/hook-logs/task-dispatch-{timestamp}.log`

### 拒絕執行
- 任一項檢查失敗
- 顯示缺失的項目清單
- 提供具體的補充建議
- permissionDecision: "deny"

### 跳過檢查
- 不是 Task 工具（例如：Write、Edit、Bash）
- 直接允許執行

## 🧪 測試方式

### 執行完整測試套件

```bash
./.claude/hooks/test-task-dispatch-readiness.sh
```

### 手動測試特定輸入

```bash
cat <<'EOF' | python3 ./.claude/hooks/task-dispatch-readiness-check.py
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "你的任務描述"
  }
}
EOF
```

## 📊 日誌位置

- **通過檢查日誌**: `.claude/hook-logs/task-dispatch-{timestamp}.log`
- **Hook 執行日誌**: `~/.claude/debug.log`（需啟用 `claude --debug`）

## 🔧 故障排除

### 問題：Hook 沒有執行

**檢查項目**:
1. 確認 `.claude/settings.local.json` 包含 Hook 配置
2. 確認腳本有執行權限：`ls -l .claude/hooks/task-dispatch-readiness-check.py`
3. 確認 Python 3 可用：`python3 --version`

### 問題：總是被拒絕

**檢查項目**:
1. 確認任務描述包含所有 4 項必要參考文件
2. 使用測試套件驗證：`./.claude/hooks/test-task-dispatch-readiness.sh`
3. 手動測試並查看詳細錯誤訊息

### 問題：JSON 格式錯誤

**檢查項目**:
1. 驗證 JSON 格式：`python3 -m json.tool .claude/settings.local.json`
2. 確認沒有遺漏逗號或括號

## 📚 相關文件

- **實作報告**: `.claude/hook-specs/hook-2-implementation-report.md`
- **官方規範**: `.claude/hook-specs/claude-code-hooks-official-standards.md`
- **敏捷重構方法論**: `.claude/methodologies/agile-refactor-methodology.md`
- **測試腳本**: `.claude/hooks/test-task-dispatch-readiness.sh`

## 💡 最佳實踐

1. **任務描述模板**:
   ```text
   請實作 UC-XX [功能名稱]，處理 Event N [事件描述]，
   屬於 [架構層級]，依賴 [類別1] 和 [類別2]
   ```

2. **檢查清單**:
   - [ ] 包含 UseCase 編號（UC-XX）
   - [ ] 包含 Event 編號（Event N）
   - [ ] 明確架構層級
   - [ ] 列出依賴類別

3. **參考文件優先**:
   - 先查閱 `docs/app-use-cases.md` 確認 UseCase
   - 先查閱事件驅動架構設計確認 Event
   - 確保任務對應明確的需求

---

**版本**: v1.0
**建立日期**: 2025-10-09
**維護者**: rosemary-project-manager
