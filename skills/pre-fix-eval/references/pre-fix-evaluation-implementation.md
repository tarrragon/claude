# 修復前強制評估 Hook + Skill 實作說明

## 📋 概述

本文件記錄「修復前強制評估」Hook + Skill 系統的完整實作。該系統自動偵測測試失敗和編譯錯誤，根據錯誤類型自動分類，並強制執行評估流程。

**版本**: v1.0
**建立日期**: 2025-01-12
**狀態**: ✅ 實作完成，測試通過

## 🎯 核心功能

### 自動錯誤分類

Hook 腳本能自動識別四種錯誤類型：

| 錯誤類型 | 識別模式 | 開 Ticket | 流程 | 代理人 |
|---------|---------|----------|------|--------|
| **SYNTAX_ERROR** | 括號、分號、拼字 | ❌ 不需 | 簡化(直接修) | mint-format-specialist |
| **COMPILATION_ERROR** | 類型、引用、導入 | ✅ 必須 | 完整評估 | parsley-flutter-developer |
| **TEST_FAILURE** | 斷言失敗、失敗計數 | ✅ 必須 | 完整評估 | parsley-flutter-developer |
| **ANALYZER_WARNING** | lint 警告、棄用 API | ✅ 必須 | 評估+延遲 | mint-format-specialist |

### 強制評估流程

非語法錯誤強制進入六階段評估流程：

```
Stage 1: 錯誤分類 (Hook 自動)
    ↓
Stage 2: BDD 意圖分析 (Skill 引導)
    ↓
Stage 3: 設計文件查詢 (用戶或 Skill 協助)
    ↓
Stage 4: 根因定位 (用戶分析)
    ↓
Stage 5: 開 Ticket 記錄 (強制, /ticket create)
    ↓
Stage 6: 分派執行 (根據根因分派代理人)
```

## 📁 實作檔案

### 1. Hook 腳本

**檔案**: `.claude/hooks/pre-fix-evaluation-hook.py`
**類型**: PostToolUse Hook
**大小**: ~300 行
**語言**: Python 3.11+ (UV single-file)

**核心功能**:
- 從 stdin 讀取 JSON 輸入
- 使用正則表達式分類錯誤
- 生成對應的 Hook 輸出
- 記錄評估結果到日誌檔案

**關鍵演算法**:
```python
優先級: SYNTAX_ERROR > COMPILATION_ERROR > TEST_FAILURE > ANALYZER_WARNING

分類流程:
1. 檢查語法錯誤模式 → 若匹配，返回 SYNTAX_ERROR
2. 檢查編譯錯誤模式 → 若匹配，返回 COMPILATION_ERROR
3. 檢查測試失敗模式 → 若匹配，返回 TEST_FAILURE
4. 檢查 Analyzer 警告模式 → 若匹配，返回 ANALYZER_WARNING
5. 否則返回 UNKNOWN
```

### 2. Skill 檔案

**檔案**: `.claude/commands/pre-fix-eval.md`
**類型**: Claude Skill 定義
**大小**: ~500 行
**語言**: Markdown (Claude 指令格式)

**核心內容**:
- 六階段評估流程詳細說明
- 修復決策矩陣
- Ticket 建立提示模板
- 常見情況處理指南
- 禁止行為清單

### 3. 配置更新

**檔案**: `.claude/settings.json`
**修改內容**: 在 PostToolUse Hook 中新增兩個配置項

```json
{
  "matcher": "Bash",
  "hooks": [
    {"type": "command", "command": ".claude/hooks/test-timeout-post.py"},
    {"type": "command", "command": ".claude/hooks/pre-fix-evaluation-hook.py", "timeout": 10000}
  ]
},
{
  "matcher": "mcp__dart__run_tests",
  "hooks": [
    {"type": "command", "command": ".claude/hooks/test-timeout-post.py"},
    {"type": "command", "command": ".claude/hooks/pre-fix-evaluation-hook.py", "timeout": 10000}
  ]
}
```

## 🧪 驗證結果

### 測試 1: 語法錯誤分類

**輸入**:
```json
{
  "tool_response": "error: Expected '}' but found 'void'\n  at lib/main.dart:42:10"
}
```

**預期結果**:
- ✅ 識別為 SYNTAX_ERROR
- ✅ 輸出簡化流程提示
- ✅ 推薦 mint-format-specialist
- ✅ 不要求開 Ticket

**實際結果**: ✅ PASS

**輸出片段**:
```
🔧 語法錯誤 - 簡化修復流程

錯誤數量: 1
推薦代理人: mint-format-specialist

識別的語法錯誤：
1. 缺少括號或分號: }
```

### 測試 2: 編譯錯誤分類

**輸入**:
```json
{
  "tool_response": "Error: The variable 'book' can't be assigned to 'String' because 'Book' is not a subtype of 'String'."
}
```

**預期結果**:
- ✅ 識別為 COMPILATION_ERROR
- ✅ 輸出強制評估提示
- ✅ 強制要求開 Ticket
- ✅ Exit Code = 2 (阻塊)

**實際結果**: ✅ PASS

**輸出片段**:
```
🚨 修復前強制評估 - COMPILATION ERROR

⚠️ 此錯誤類型 **必須開 Ticket** 追蹤，禁止直接分派修復！

識別的錯誤：
1. 類型不匹配
2. 類型不匹配
```

### 測試 3: 測試失敗分類

**輸入**:
```json
{
  "tool_response": "test: Expected: true Actual: false\n\nFailed 2 tests in 1.5 seconds"
}
```

**預期結果**:
- ✅ 識別為 TEST_FAILURE
- ✅ 輸出強制評估提示
- ✅ 強制要求開 Ticket
- ✅ Exit Code = 2 (阻塊)

**實際結果**: ✅ PASS

### 測試 4: 成功情況

**輸入**:
```json
{
  "tool_response": "All tests passed! Completed in 2.5 seconds"
}
```

**預期結果**:
- ✅ 識別測試成功
- ✅ 無輸出，正常結束
- ✅ Exit Code = 0

**實際結果**: ✅ PASS

**日誌**:
```
[2026-01-12 13:03:27,660] INFO - 測試全部通過，無需評估
```

### 測試 5: 無錯誤輸出

**輸入**:
```json
{
  "tool_response": ""
}
```

**預期結果**:
- ✅ 無錯誤檢測
- ✅ 正常結束

**實際結果**: ✅ PASS

## 📊 正則表達式模式驗證

### 語法錯誤模式 (SYNTAX_PATTERNS)

```python
[
  r"Expected.*?['\"]([;})\]])['\"]",         # 缺少括號
  r"Unexpected\s+(?:end of|token)\b",       # 意外 token
  r"unterminated string literal",            # 字串未結束
  r"unexpected end of(?:\s+\w+)*\s*file",   # 檔案不完整
  r"missing comma",                          # 缺少逗號
  r"invalid number format",                  # 無效數字格式
]
```

**覆蓋範圍**: 6 種常見語法錯誤

### 編譯錯誤模式 (COMPILATION_PATTERNS)

```python
[
  r"(?:type|variable).*?can't be assigned",  # 類型不匹配
  r"is not a subtype of",                    # 子型檢查
  r"Undefined\s+(?:name|class|function)",    # 未定義
  r"Target of URI.*?doesn't exist",          # 導入不存在
  r"(?:Class|Function|Method).*?not found",  # 引用不存在
  r"cannot find symbol",                     # 符號未定義
  r"incompatible types",                     # 類型不相容
]
```

**覆蓋範圍**: 7 種編譯錯誤

### 測試失敗模式 (TEST_FAILURE_PATTERNS)

```python
[
  r"Expected:.*?Actual:",                    # 斷言失敗
  r"(\d+)\s+tests?\s+failed",                # 失敗計數
  r"FAILED",                                 # 失敗標記
  r"AssertionError",                         # 斷言例外
]
```

**覆蓋範圍**: 4 種測試失敗

### Analyzer 警告模式 (ANALYZER_WARNING_PATTERNS)

```python
[
  r"info\s*-.*?unused",                      # 未使用
  r"warning\s*-",                            # 警告標記
  r"deprecated\s+(?:function|class|method)", # 棄用 API
]
```

**覆蓋範圍**: 3 種 Analyzer 警告

## 🔧 配置詳情

### Hook 觸發條件

**PostToolUse Hook** 配置於兩個 Matcher:

#### 1. Bash 命令

```json
{
  "matcher": "Bash",
  "hooks": [
    {"type": "command", "command": ".claude/hooks/test-timeout-post.py"},
    {"type": "command", "command": ".claude/hooks/pre-fix-evaluation-hook.py", "timeout": 10000}
  ]
}
```

**觸發情況**:
- 執行 `flutter test` 完成
- 執行 `dart analyze` 完成
- 執行 `dart run` 完成
- 其他 Bash 命令輸出包含錯誤訊息

#### 2. MCP Dart 工具

```json
{
  "matcher": "mcp__dart__run_tests",
  "hooks": [
    {"type": "command", "command": ".claude/hooks/test-timeout-post.py"},
    {"type": "command", "command": ".claude/hooks/pre-fix-evaluation-hook.py", "timeout": 10000}
  ]
}
```

**觸發情況**:
- 使用 `mcp__dart__run_tests` 執行測試完成

### 執行環境

- **Timeout**: 10000ms (10 秒)
- **Python 版本**: 3.11+
- **依賴**: 無外部依賴 (標準庫)
- **環境變數**: `CLAUDE_PROJECT_DIR` (自動設定), `HOOK_DEBUG` (可選)

## 📝 日誌系統

### 日誌檔案位置

所有評估結果記錄到: `.claude/hook-logs/pre-fix-evaluation-*.json`

### 日誌格式

```json
{
  "timestamp": "2025-01-12T13:00:00.000000",
  "error_type": "test_failure",
  "error_count": 2,
  "errors": [
    {
      "type": "test_failure",
      "description": "斷言失敗: Expected true",
      "pattern": "Expected.*?Actual:"
    }
  ],
  "requires_ticket": true
}
```

### 執行日誌位置

詳細執行日誌記錄到: `.claude/hook-logs/pre-fix-evaluation-hook.log`

## 🛠 故障排除

### 問題 1: Hook 未觸發

**檢查清單**:
- [ ] 確認 `.claude/settings.json` 已更新
- [ ] 確認 Hook 腳本有執行權限: `chmod +x .claude/hooks/pre-fix-evaluation-hook.py`
- [ ] 查看 Hook 日誌: `.claude/hook-logs/pre-fix-evaluation-hook.log`
- [ ] 確認 CLAUDE_PROJECT_DIR 環境變數已設定

### 問題 2: Hook 識別錯誤

**檢查清單**:
- [ ] 檢查工具輸出是否包含匹配的模式
- [ ] 查看記錄的日誌檔案: `.claude/hook-logs/pre-fix-evaluation-*.json`
- [ ] 確認是否需要新增或調整正則表達式模式
- [ ] 設定 `HOOK_DEBUG=true` 啟用詳細日誌

### 問題 3: JSON 解析失敗

**檢查清單**:
- [ ] 確認 Hook 輸入是有效的 JSON
- [ ] 確認 `tool_response` 欄位存在
- [ ] 查看 stderr 輸出的錯誤訊息
- [ ] 檢查 Python 版本是否 >= 3.11

## ✅ 驗收條件檢查清單

完整實作應滿足以下條件：

### 功能性驗收
- [x] Hook 腳本可正確分類錯誤類型
- [x] 語法錯誤可直接分派，無需 Ticket
- [x] 非語法錯誤強制提示開 Ticket
- [x] Skill 檔案包含完整六階段流程
- [x] settings.json 配置正確
- [x] Hook 在 PostToolUse 時自動觸發

### 測試驗收
- [x] 語法錯誤分類測試通過
- [x] 編譯錯誤分類測試通過
- [x] 測試失敗分類測試通過
- [x] 成功情況處理正確
- [x] 無錯誤情況處理正確
- [x] JSON 輸出格式正確

### 配置驗收
- [x] Hook 腳本有執行權限
- [x] settings.json JSON 格式有效
- [x] 所有路徑正確
- [x] Timeout 設定合理 (10 秒)

### 文件驗收
- [x] Hook 設計說明完整
- [x] Skill 六階段流程清晰
- [x] 修復決策矩陣完整
- [x] Ticket 建立提示模板提供
- [x] 常見情況處理指南清晰

## 🚀 後續改進方向

### 短期改進 (v1.1)
1. 新增更多語言的錯誤模式 (JavaScript, TypeScript)
2. 改進错误訊息的中文翻譯
3. 新增支援更多 Bash 命令輸出

### 中期改進 (v1.2)
1. 增進 Hook 輸出，包含自動的六階段分析開始提示
2. 與 ticket-tracker 整合，自動追蹤 Ticket 狀態
3. 建立修復效率統計 (Track time-to-fix 指標)

### 長期願景 (v2.0)
1. AI 輔助根因分析 (使用 Claude API)
2. 自動生成修復建議
3. 修復成功率統計和分析

## 📚 相關檔案

- Plan: `~/.claude/plans/iterative-swimming-feather.md`
- Hook 規格: `.claude/hook-specs/`
- Hook 系統方法論: `.claude/methodologies/hook-system-methodology.md`
- Ticket 方法論: `.claude/methodologies/ticket-lifecycle-management-methodology.md`
