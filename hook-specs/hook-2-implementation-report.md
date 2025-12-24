# Hook 2 實作報告 - 任務分派準備度檢查

## 📖 文件資訊

- **版本**: v1.0
- **實作日期**: 2025-10-09
- **Hook 類型**: PreToolUse
- **目標工具**: Task
- **責任人**: rosemary-project-manager

---

## 🎯 實作目標

實作 PreToolUse Hook，在使用 Task 工具前檢查任務描述是否包含必要的參考文件，確保符合敏捷重構方法論的任務分派原則。

---

## ✅ 完成項目

### 1. 核心腳本

**檔案**: `.claude/hooks/task-dispatch-readiness-check.py`

**功能**:
- 從 stdin 讀取 JSON 輸入（符合官方規範）
- 檢查 4 項必要參考文件：
  - UseCase 參考（格式：UC-XX）
  - 流程圖 Event 參考
  - 架構規範引用（Clean Architecture 層級）
  - 依賴類別說明（Repository/Service/Entity/ValueObject/UseCase）
- 提供詳細的建議訊息
- 記錄通過檢查的任務日誌

**檢查規則**:

```python
# UseCase 參考檢查
if not re.search(r'UC-\d{2}', prompt):
    missing_items.append("UseCase 參考 (格式: UC-XX)")

# Event 參考檢查（支援中英文）
if not re.search(r'Event \d+|事件 \d+', prompt, re.IGNORECASE):
    missing_items.append("流程圖 Event 參考")

# 架構規範檢查
architecture_patterns = [
    r'Clean Architecture',
    r'Domain 層',
    r'Application 層',
    r'Presentation 層',
    r'Infrastructure 層'
]
if not any(re.search(pattern, prompt, re.IGNORECASE) for pattern in architecture_patterns):
    missing_items.append("架構規範引用")

# 依賴類別檢查
dependency_patterns = [
    r'Repository',
    r'Service',
    r'Entity',
    r'ValueObject',
    r'UseCase'
]
if not any(re.search(pattern, prompt, re.IGNORECASE) for pattern in dependency_patterns):
    missing_items.append("依賴類別說明")
```

### 2. 配置更新

**檔案**: `.claude/settings.local.json`

#### Permissions 區段
```json
{
  "permissions": {
    "allow": [
      "Bash($CLAUDE_PROJECT_DIR/.claude/hooks/task-dispatch-readiness-check.py:*)"
    ]
  }
}
```

#### Hooks 區段
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/task-dispatch-readiness-check.py"
          }
        ]
      }
    ]
  }
}
```

### 3. 測試套件

**檔案**: `.claude/hooks/test-task-dispatch-readiness.sh`

**測試案例**:
1. ✅ 缺少所有參考文件 → 正確拒絕
2. ✅ 只缺少 UseCase → 正確拒絕
3. ✅ 完整參考文件 → 正確允許
4. ✅ 非 Task 工具 → 直接通過（不檢查）
5. ✅ 空 prompt → 正確拒絕
6. ✅ Clean Architecture 不同表達方式 → 正確允許

**測試結果**: 6/6 通過 ✅

---

## 📤 輸出格式

### 拒絕任務時

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "任務分派準備度不足，缺失: UseCase 參考 (格式: UC-XX), 流程圖 Event 參考, 架構規範引用, 依賴類別說明\n\n建議補充:\n- 請參考 docs/app-use-cases.md 並引用相關 UseCase 編號\n- 請參考事件驅動架構設計文件，標明處理哪些 Event\n- 請明確指出任務屬於哪個架構層級 (Domain/Application/Presentation/Infrastructure)\n- 請說明需要依賴哪些 Repository、Service、Entity 等類別"
  },
  "systemMessage": "⚠️ 請補充完整的參考文件後重新分派任務（符合敏捷重構方法論）"
}
```

### 允許任務時

- Exit Code: 0
- 日誌記錄在 `.claude/hook-logs/task-dispatch-{timestamp}.log`

**日誌範例**:
```text
[2025-10-09 15:54:38.555588] ✅ 任務分派準備度檢查通過
Task 類型: pepper-test-implementer
Prompt 長度: 84 字元

--- Prompt 摘要 ---
請實作 UC-01 書籍新增功能，處理 Event 3 使用者觸發新增，屬於 Application 層，依賴 BookRepository 和 Book Entity...
```

---

## 🎯 設計特點

### 1. 符合官方規範

- ✅ 使用 `$CLAUDE_PROJECT_DIR` 環境變數
- ✅ 從 stdin 讀取 JSON 輸入
- ✅ 使用 `hookSpecificOutput.permissionDecision` 控制
- ✅ PreToolUse Hook 的標準 matcher 模式
- ✅ 正確的 Exit Code（0 = 允許，非 0 無特殊意義）

### 2. 敏捷重構方法論對齊

確保任務分派時包含：
- **需求依據**: UseCase 編號（對應需求規格）
- **事件上下文**: Event 編號（對應流程圖）
- **架構位置**: Clean Architecture 層級（確保責任歸屬）
- **依賴資訊**: 需要的類別和介面（確保上下文完整）

### 3. 使用者友善

- 清晰的錯誤訊息
- 具體的補充建議
- 提供參考文件路徑
- 中英文混合支援

### 4. 可維護性

- Python 實作（比 Bash 更適合 JSON 處理）
- 清晰的檢查邏輯
- 完整的測試覆蓋
- 詳細的日誌記錄

---

## 📊 實測範例

### 範例 1: 缺少參考文件（被拒絕）

**輸入**:
```json
{
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作一個書籍新增功能"
  }
}
```

**輸出**:
```text
⚠️ 請補充完整的參考文件後重新分派任務（符合敏捷重構方法論）

任務分派準備度不足，缺失: UseCase 參考 (格式: UC-XX), 流程圖 Event 參考, 架構規範引用, 依賴類別說明

建議補充:
- 請參考 docs/app-use-cases.md 並引用相關 UseCase 編號
- 請參考事件驅動架構設計文件，標明處理哪些 Event
- 請明確指出任務屬於哪個架構層級 (Domain/Application/Presentation/Infrastructure)
- 請說明需要依賴哪些 Repository、Service、Entity 等類別
```

### 範例 2: 完整參考文件（允許）

**輸入**:
```json
{
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作 UC-01 書籍新增功能，處理 Event 3 使用者觸發新增，屬於 Application 層，依賴 BookRepository 和 Book Entity"
  }
}
```

**輸出**:
- 任務允許執行
- 日誌記錄在 `.claude/hook-logs/task-dispatch-20251009_HHMMSS.log`

---

## 🔧 使用方式

### 自動觸發

當使用 Task 工具時，Hook 會自動執行檢查：

```python
# Claude Code 內部會自動觸發
Task(
    prompt="請實作 UC-01 書籍新增功能，處理 Event 3...",
    subagent_type="pepper-test-implementer"
)
```

### 手動測試

```bash
# 執行完整測試套件
./.claude/hooks/test-task-dispatch-readiness.sh

# 測試特定輸入
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

### Debug 模式

```bash
# 啟用 Claude Code Debug 模式
claude --debug

# 查看 Hook 執行日誌
tail -f ~/.claude/debug.log
```

---

## 📚 相關文件

- **官方規範**: `.claude/hook-specs/claude-code-hooks-official-standards.md`
- **調整建議**: `.claude/hook-specs/implementation-adjustments.md`
- **方法論**: `.claude/methodologies/agile-refactor-methodology.md`
- **Hook 系統**: `.claude/methodologies/hook-system-methodology.md`

---

## 🎉 實作總結

### 成功指標

- ✅ 腳本建立完成：`task-dispatch-readiness-check.py`
- ✅ 執行權限設定：`chmod +x`
- ✅ settings.local.json 配置更新（permissions + hooks）
- ✅ 測試套件建立：`test-task-dispatch-readiness.sh`
- ✅ 所有測試通過：6/6 ✅
- ✅ 日誌記錄正常運作
- ✅ JSON 輸出格式正確

### 符合規範

- ✅ 使用官方 JSON 輸入處理
- ✅ 使用 `$CLAUDE_PROJECT_DIR` 環境變數
- ✅ 使用 `hookSpecificOutput.permissionDecision` 控制
- ✅ 提供詳細的拒絕原因
- ✅ 符合 PreToolUse Hook 行為規範

### 實際效益

- **提升任務品質**: 強制要求完整的參考文件
- **加速代理人執行**: 提供完整上下文，減少返工
- **符合方法論**: 實踐敏捷重構的任務分派原則
- **可追溯性**: 所有任務都有明確的需求依據

---

**版本**: v1.0
**狀態**: ✅ 實作完成並測試通過
**下一步**: 可整合到實際工作流程中，持續監控效果
