# Claude Code Hooks - 專案 Hook 系統

## 概述

本目錄包含專案使用的 Claude Code Hooks 腳本和相關工具。Hook 的註冊以 `.claude/settings.json` 為準；經 `hook-dispatcher.py` 分派的 Bash 類 hook 見 `hook-dispatch-registry.json`。

## 檔案結構

### Hook 腳本

#### `task-dispatch-readiness-check.py`
**功能**：PreToolUse Hook（Agent/Task 工具）－派發前置檢查

**檢查項目**：
1. 派發缺少 prompt 時擋下（deny）
2. prompt 引用 handoff 指向的票時輸出可見訊號（不影響放行）

代理人分派對應比對（任務類型 → 代理人）已移除：設定檔 `known_agents` 全數列在 `agent_to_task_map` 內，比對永遠判定為正確、deny 分支實際走不到。Strict/Warning 模式切換與 `agent-dispatch-warnings.jsonl` 記錄隨之移除。

### 工具模組

#### `archived/agent_dispatch_recovery.py`（已歸檔）
**功能**：代理人分派錯誤恢復工具

**提供功能**：
- 錯誤訊息解析
- 自動重試邏輯
- 糾正歷史記錄
- 統計分析

**使用方式**：
```bash
# 查看糾正歷史
python .claude/hooks/archived/agent_dispatch_recovery.py history 10

# 查看統計資訊
python .claude/hooks/archived/agent_dispatch_recovery.py stats
```

### 測試套件

測試執行規則（一般 pytest 檔與 PEP 723 檔）見 `.claude/hooks/tests/README.md`。

#### `tests/test_task_dispatch_readiness_check.py`
**功能**：`task-dispatch-readiness-check.py` 的測試（檔名依 hooks-test-gate 的 stem 慣例）

**測試覆蓋**：空 stdin／畸形 JSON 放行、非 Agent/Task 工具放行、缺 prompt 擋下、有 prompt 不依代理人判定、liveness 記錄。

#### `tests/test_error_recovery.py`
**功能**：錯誤恢復工具模組測試套件

**測試覆蓋**：
- 錯誤訊息解析測試（5 個）
- 重試判斷邏輯測試（3 個）
- 自動重試機制測試（3 個）
- 無限循環防護測試（2 個）
- 實際場景模擬測試（2 個）

**執行方式**：
```bash
.claude/hooks/tests/test_error_recovery.py
```

## Hook 系統文件

- **方法論**：`.claude/methodologies/hook-system-methodology.md`
- **Hook 規格**：`.claude/hook-specs/agile-refactor-hooks-specification.md`
- **官方標準**：`.claude/hook-specs/claude-code-hooks-official-standards.md`
- **技術參考**：`.claude/references/hook-architect-technical-reference.md`

## 故障排除

### Hook 未執行

**檢查項目**：
1. `.claude/settings.json` 配置是否正確
2. Hook 腳本是否有執行權限（`chmod +x`）
3. Python 環境是否可用（`python3 --version`）

### 測試失敗

**處理步驟**：
1. 查看錯誤訊息
2. 檢查 Hook 日誌（`.claude/hook-logs/`）
3. 執行語法檢查（`python3 -m py_compile hook.py`）
4. 單獨執行失敗的測試

---

**最後更新**: 2026-11-12
