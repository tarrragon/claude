---
id: PC-086
title: Subagent 建 Hook 腳本缺執行權限（exec bit）
category: process-compliance
severity: high
first_observed: 2026-04-18
status: active
related:
  - IMP-054
  - PC-064
---

# PC-086: Subagent 建 Hook 腳本缺執行權限（exec bit）

## 問題描述

subagent（如 basil-hook-architect）執行 Write 工具建立 `.py` Hook 腳本時，檔案預設為 `.rw-r--r--`（644），缺少執行權限（`x` bit）。Claude Code Hook 系統將腳本作為 executable 呼叫，觸發時回報 `Permission denied`。

## 重現情境

**實測**（commit 6945319c → dea1939e 修復）：

1. basil-hook-architect 執行 `Write .claude/hooks/ticket-frontmatter-validator-hook.py`（案例敘事：事發時路徑）<!-- broken-link-exempt: 本行為更正說明，案例本文保留原始路徑以忠實記錄事發當時狀態 -->
   （現搬遷至 `.claude/skills/ticket/hooks/ticket-frontmatter-validator-hook.py`，2026-08-22 文件複查更正）
2. 檔案 mode: `100644`（無 exec bit）
3. settings.json 已正確註冊 PostToolUse
4. 後續任一 Edit ticket .md 觸發 Hook → `/bin/sh: ...ticket-frontmatter-validator-hook.py: Permission denied`
5. `chmod +x` 修復後 Hook 正常運作

## 適用範圍註記（2026-11-20 重驗）

本節只更新適用範圍與現況結論；上方重現情境與以下根因保留事發當時（2026-04-18）的敘述，不改寫。

- **runtime 觸發路徑**：`.claude/settings.json` 的 hook 註冊已全數改為顯式解譯器形式（`uv run --quiet <path>` 或 `python3 <path>`），Bash 事件的 hook 經 `hook-dispatcher.py` 分派，兩者皆不讀檔案的可執行位。subagent 以 Write 建出 644 的 hook 檔案後，該 hook 由 runtime 觸發時不再出現上方重現情境第 4 步的 `Permission denied`；本 PC「hook 觸發即失敗」的 severity 前提對此路徑不成立。
- **殘留影響（非零）**：以路徑直接執行 hook 做手動驗證（依 shebang）仍需可執行位，缺位時仍得到 `Permission denied`；consumer 若仍有直接路徑形式的註冊，原症狀照樣重現。技術面的影響對照見 IMP-054〈適用範圍註記〉。
- **根因仍成立**：「subagent 寫檔缺系統約束」是本 PC 的主根因，與可執行位是否影響 runtime 無關；下方表格中 frontmatter 格式、shebang 兩列不受本次重驗影響。
- **預防措施現況**：可執行位的偵測已由 `hook-registration-coverage-check.py` 以純偵測方式承擔（2026-08-22 起不再自動 chmod）。下方「中期」「長期」兩節為撰寫當時的規劃，未依此重驗逐項更新。

## 根因分析

與 PC-064（PM 列純文字選項繞過 AUQ）和 subagent 手寫 frontmatter 繞過 CLI（另一 ANA 的分析對象）**同類根因**：

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

### 中期（frontmatter 繞過 ANA 的分析範圍延伸）
- **擴充 ticket-frontmatter-validator 偵測範圍**：新 Hook 腳本建立時檢查：
  - Shebang 存在（`#!/usr/bin/env python3` 或類似）
  - Exec bit 正確（`0o755`）
  - settings.json 註冊對應 matcher
- 派發 Hook 建立任務的 prompt 必須明列：「建檔後執行 `chmod +x`」

### 長期
- frontmatter 繞過 ANA 的 Phase B IMP-3（CLI 強化）可延伸為 `ticket track register-hook` 命令，統一處理權限 + 註冊
- 或新增 `basil-hook-architect` 代理人後置 hook：自動 `chmod +x` 新建的 `.claude/hooks/*.py`

## 檢測信號

- commit 後 Hook 首次觸發：`Permission denied`
- `ls -la .claude/hooks/*.py` 檢查是否有 `.rw-r--r--`（應為 `.rwxr-xr-x`）

## 相關規則 / Ticket

- IMP-054：exec bit 缺失的技術根因與機械修法（chmod +x）。本文件聚焦 subagent 寫檔行為模式；IMP-054 聚焦技術細節與通用防護措施，兩者互為交叉引用，非重複記錄
- subagent frontmatter bypass 的 ANA（同類根因分析）
- ticket-frontmatter-validator-hook 的 IMP（建 hook 時發生）
- PC-064：PM 無意識繞過 AUQ（同類「系統約束缺失」）
- ARCH-BAL-015：本 pattern 衍生的自動 chmod 補救機制掃描軸過寬，波及不需要 exec bit 的測試檔，把執行期問題轉化為版本控制問題
- 建議後續：擴充 frontmatter 繞過 ANA 的 Phase A IMP 範圍涵蓋 Hook 腳本驗證
