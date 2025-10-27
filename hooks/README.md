# Claude Code Hooks - 專案 Hook 系統

## 📖 概述

本目錄包含專案使用的 Claude Code Hooks 腳本和相關工具。

## 📁 檔案結構

### Hook 腳本

#### `task-dispatch-readiness-check.py`
**功能**：PreToolUse Hook - 任務分派準備度檢查

**檢查項目**：
1. 必要參考文件檢查（UseCase、Event、架構層級）
2. 代理人分派正確性檢查（任務類型優先原則）

**模式支援**（v0.12.N.10+）：
- **Strict 模式**（預設）：偵測到錯誤 → 阻擋執行
- **Warning 模式**：偵測到錯誤 → 記錄警告 + 允許執行

**配置方式**：
```bash
# 環境變數（臨時）
export HOOK_MODE=warning

# 配置檔案（持久）
# 參考 .claude/hook-config.json.example
```

### 工具模組

#### `agent_dispatch_recovery.py`
**功能**：代理人分派錯誤恢復工具

**提供功能**：
- 錯誤訊息解析
- 自動重試邏輯
- 糾正歷史記錄
- 統計分析

**使用方式**：
```bash
# 查看糾正歷史
python .claude/hooks/agent_dispatch_recovery.py history 10

# 查看統計資訊
python .claude/hooks/agent_dispatch_recovery.py stats
```

### 測試套件

#### `tests/test_agent_dispatch_check.py`
**功能**：代理人分派檢查 Hook 完整測試套件

**測試覆蓋**：
- 9 個正確分派測試
- 9 個錯誤分派測試
- 8 個邊界測試（包含 Phase 4 誤判改進）
- 4 個整合測試
- 4 個關鍵字檢測測試
- 1 個效能測試
- 4 個模式切換測試

**總計**：56 個測試，100% 通過率

**執行方式**：
```bash
.claude/hooks/tests/test_agent_dispatch_check.py
```

#### `tests/test_error_recovery.py`
**功能**：錯誤恢復工具模組測試套件

**測試覆蓋**：
- 錯誤訊息解析測試（5 個）
- 重試判斷邏輯測試（3 個）
- 自動重試機制測試（3 個）
- 無限循環防護測試（2 個）
- 實際場景模擬測試（2 個）

**總計**：15 個測試

**執行方式**：
```bash
.claude/hooks/tests/test_error_recovery.py
```

### 示範腳本

#### `demo-mode-switching.sh`
**功能**：Hook 模式切換功能示範

**示範內容**：
1. Strict 模式行為（阻擋錯誤分派）
2. Warning 模式行為（警告 + 允許執行）
3. 警告記錄查看
4. 正確分派測試

**執行方式**：
```bash
.claude/hooks/demo-mode-switching.sh
```

### 配置檔案

#### `.claude/hook-config.json.example`
**功能**：Hook 配置檔案範例

**內容**：
```json
{
  "agent_dispatch_check": {
    "mode": "strict",
    "description": "代理人分派檢查 Hook 運作模式",
    "options": {
      "strict": "嚴格模式 - 偵測到錯誤時阻擋執行（預設）",
      "warning": "警告模式 - 偵測到錯誤時記錄警告但允許執行"
    }
  }
}
```

**使用方式**：
```bash
# 複製範例檔案
cp .claude/hook-config.json.example .claude/hook-config.json

# 編輯配置
vi .claude/hook-config.json
```

## 📊 Hook 系統架構

```text
PreToolUse Hook (Task 工具)
    ↓
┌─────────────────────────────────────────┐
│ task-dispatch-readiness-check.py        │
├─────────────────────────────────────────┤
│ 1. 讀取 Hook 模式（環境變數/配置檔案）    │
│ 2. 檢查必要參考文件                      │
│ 3. 檢查代理人分派正確性                  │
│                                         │
│ 模式判斷：                               │
│   ├─ Strict: deny + 錯誤訊息            │
│   └─ Warning: 警告 + 記錄 + 允許        │
└─────────────────────────────────────────┘
    ↓
警告記錄（Warning 模式）
    ↓
.claude/hook-logs/agent-dispatch-warnings.jsonl
```

## 🔧 快速開始

### 1. 基本使用（Strict 模式）

**預設行為**：錯誤分派會被阻擋

```bash
# 無需配置，預設使用 Strict 模式
# 錯誤分派會返回錯誤訊息並阻擋執行
```

### 2. 切換到 Warning 模式

**臨時切換**：
```bash
export HOOK_MODE=warning
```

**持久配置**：
```bash
# 建立配置檔案
cat > .claude/hook-config.json << EOF
{
  "agent_dispatch_check": {
    "mode": "warning"
  }
}
EOF
```

### 3. 查看警告記錄

```bash
# 查看所有警告
cat .claude/hook-logs/agent-dispatch-warnings.jsonl

# 查看最近 10 筆
tail -n 10 .claude/hook-logs/agent-dispatch-warnings.jsonl

# 使用 jq 美化輸出
cat .claude/hook-logs/agent-dispatch-warnings.jsonl | jq '.'
```

### 4. 執行測試

```bash
# 執行所有測試
.claude/hooks/tests/test_agent_dispatch_check.py

# 執行錯誤恢復測試
.claude/hooks/tests/test_error_recovery.py

# 執行模式切換示範
.claude/hooks/demo-mode-switching.sh
```

## 📚 文件參考

### 使用指南

- **完整指南**：`/Users/tarragon/Projects/book_overview_app/docs/agent-dispatch-auto-retry-guide.md`
- **快速參考**：`/Users/tarragon/Projects/book_overview_app/.claude/quick-ref-agent-dispatch-recovery.md`

### 實作報告

- **v0.12.N.1**：Phase 1 - 功能規格
- **v0.12.N.2**：Phase 2 - 測試設計
- **v0.12.N.3**：Phase 3a - 實作策略
- **v0.12.N.4**：Phase 3b - 實作報告
- **v0.12.N.5**：Phase 4 - 重構評估
- **v0.12.N.6**：Phase 4a - 測試修正
- **v0.12.N.7**：錯誤恢復實作
- **v0.12.N.8**：關鍵字檢測改進
- **v0.12.N.9**：自動重試指南
- **v0.12.N.10**：模式切換功能（本版本）

### Hook 系統文件

- **方法論**：`.claude/methodologies/hook-system-methodology.md`
- **Hook 規格**：`.claude/hook-specs/agile-refactor-hooks-specification.md`
- **官方標準**：`.claude/hook-specs/claude-code-hooks-official-standards.md`

## ⚙️ 代理人分派規則

### 任務類型優先原則

**決策樹**：
```text
1. 首先判斷任務類型：
   ├─ Hook 開發 → basil-hook-architect
   ├─ 文件整合 → thyme-documentation-integrator
   ├─ 程式碼格式化 → mint-format-specialist
   ├─ Phase 1 設計 → lavender-interface-designer
   ├─ Phase 2 測試設計 → sage-test-architect
   ├─ Phase 3a 策略規劃 → pepper-test-implementer
   ├─ Phase 4 重構 → cinnamon-refactor-owl
   ├─ 應用程式開發 → 進入步驟 2
   └─ 其他專業任務 → 對應專業代理人

2. 如果任務類型是「應用程式開發」，才判斷專案類型：
   ├─ Flutter 應用程式 → parsley-flutter-developer
   ├─ React 應用程式 → react-developer（未來）
   └─ 其他語言應用程式 → 對應語言代理人
```

### 關鍵字權重機制

**權重定義**：
- **高權重**（3 分）：明確的任務類型關鍵字
- **中權重**（2 分）：相關的技術關鍵字
- **低權重**（1 分）：輔助性關鍵字

**閾值**：3 分（達到閾值立即返回，實現優先級機制）

**範例**：
```text
"開發 Hook 腳本" → Hook 開發（高權重 3 分）
".claude/hooks/ 修改" → Hook 開發（中權重 2 分 + 其他）
"Phase 4 重構評估" → Phase 4 重構（高權重 3 分，優先於 Hook）
```

## 🐛 故障排除

### Hook 未執行

**檢查項目**：
1. `.claude/settings.local.json` 配置是否正確
2. Hook 腳本是否有執行權限（`chmod +x`）
3. Python 環境是否可用（`python3 --version`）

### 模式切換無效

**檢查項目**：
1. 環境變數是否正確設定（`echo $HOOK_MODE`）
2. 配置檔案格式是否正確（JSON 語法）
3. 優先級順序：環境變數 > 配置檔案 > 預設值

### 測試失敗

**處理步驟**：
1. 查看錯誤訊息
2. 檢查 Hook 日誌（`.claude/hook-logs/`）
3. 執行語法檢查（`python3 -m py_compile hook.py`）
4. 單獨執行失敗的測試

## 📈 效能指標

**Hook 執行時間**：
- 環境變數模式：< 1ms
- 配置檔案模式：< 5ms
- 代理人檢查邏輯：< 10ms
- **總計**：< 15ms（對使用者無感）

**測試執行時間**：
- 56 個測試：0.03-0.04 秒

## 🚀 版本歷史

- **v0.12.N.1-9**：代理人分派檢查 Hook 開發和改進
- **v0.12.N.10**：模式切換功能（Strict/Warning）
- **v0.13.x**（計劃）：關鍵字檢測改進、學習模式
- **v0.14.x**（計劃）：主線程自動重試、統計分析

---

**維護者**: basil-hook-architect
**最後更新**: 2025-10-18
**版本**: v0.12.N.10+
