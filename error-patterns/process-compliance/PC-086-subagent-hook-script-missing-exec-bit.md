---
id: PC-086
title: Subagent 建 Hook 腳本缺執行權限（exec bit）
category: process-compliance
severity: high
first_observed: 2026-04-18
status: active
related:
  - PC-064
  - W14-024
  - W14-028
---

# PC-086: Subagent 建 Hook 腳本缺執行權限（exec bit）

## 問題描述

subagent（如 basil-hook-architect）執行 Write 工具建立 `.py` Hook 腳本時，檔案預設為 `.rw-r--r--`（644），缺少執行權限（`x` bit）。Claude Code Hook 系統將腳本作為 executable 呼叫，觸發時回報 `Permission denied`。

## 重現情境

**W14-028 實測**（commit 6945319c → dea1939e 修復）：

1. basil-hook-architect 執行 `Write .claude/hooks/ticket-frontmatter-validator-hook.py`
2. 檔案 mode: `100644`（無 exec bit）
3. settings.json 已正確註冊 PostToolUse
4. 後續任一 Edit ticket .md 觸發 Hook → `/bin/sh: ...ticket-frontmatter-validator-hook.py: Permission denied`
5. `chmod +x` 修復後 Hook 正常運作

## 根因分析

與 PC-064（PM 列純文字選項繞過 AUQ）和 W14-024（subagent 手寫 frontmatter 繞過 CLI）**同類根因**：

**subagent 寫檔缺系統約束**。具體表現：

| 類型 | 範例 | 缺失約束 |
|------|------|---------|
| 檔案權限 | Hook .py 無 +x | Write 工具不主動設 exec bit |
| Frontmatter 格式 | AC 單行合併、status 非標準值 | Edit 不驗證 YAML schema |
| Shebang 缺失 | 未來風險 | Write 不檢查 shebang 與可執行性匹配 |

Subagent 訓練傾向於「完成主任務」，不自動處理周邊系統約束（權限、格式、註冊）。

## 預防措施

### 短期（本 session 已執行）
- `chmod +x` 手動修復
- commit message 紀錄根因 + 防護方向

### 中期（W14-024 分析範圍延伸）
- **擴充 ticket-frontmatter-validator 偵測範圍**：新 Hook 腳本建立時檢查：
  - Shebang 存在（`#!/usr/bin/env python3` 或類似）
  - Exec bit 正確（`0o755`）
  - settings.json 註冊對應 matcher
- 派發 Hook 建立任務的 prompt 必須明列：「建檔後執行 `chmod +x`」

### 長期
- W14-024 Phase B IMP-3（CLI 強化）可延伸為 `ticket track register-hook` 命令，統一處理權限 + 註冊
- 或新增 `basil-hook-architect` 代理人後置 hook：自動 `chmod +x` 新建的 `.claude/hooks/*.py`

## 檢測信號

- commit 後 Hook 首次觸發：`Permission denied`
- `ls -la .claude/hooks/*.py` 檢查是否有 `.rw-r--r--`（應為 `.rwxr-xr-x`）

## 相關規則 / Ticket

- W14-024 ANA：subagent frontmatter bypass（同類根因分析）
- W14-028 IMP：ticket-frontmatter-validator-hook（本 ticket 建 hook 時發生）
- PC-064：PM 無意識繞過 AUQ（同類「系統約束缺失」）
- 建議後續：擴充 W14-024 Phase A IMP 範圍涵蓋 Hook 腳本驗證
