---
id: PC-059
title: 代理人 frontmatter Tools 宣告 ≠ 實際 runtime 權限
category: process-compliance
severity: high
retries:
 - retry3: 確認 permissionMode 是 subagent Edit 的控制欄位
 - retry4: 聲稱 bypassPermissions 為 worktree 場景標準值（後被 retry5 推翻）
 - retry5: 確認 permissionMode 受 subagent cwd 限制，worktree 絕對路徑不可靠
 - retry6: 主 repo cwd 內 `.claude/` 檔案 + thyme `permissionMode: acceptEdits` 仍被拒（W17-088）
related:
 - PC-058
 - IMP-056
---

# PC-059: 代理人 frontmatter Tools 宣告 ≠ 實際 runtime 權限

## 現象

派發代理人執行需要 Edit/Write/Grep 的任務時，代理人回報「工具權限被拒」，即使：
- 代理人 frontmatter 明確宣告 `Tools: Edit, Write, Read, Bash, Grep, LS, Glob`
- 代理人身分對應該能使用這些工具（如 thyme-python-developer）

背景派發時尤其嚴重，因為無人互動批准，工具呼叫直接被拒。

## 觸發情境

1. PM 派發代理人（背景或前台）執行需要修改檔案的任務
2. 代理人嘗試 Edit/Write → 被 Claude Code permission system 攔截
3. 權限提示無人互動 → 自動拒絕
4. 代理人回報「工具權限被拒」，回退至「僅能讀取和規劃」模式

## 根因（修訂版 — 2026-04-12 retry3 確認）

Claude Code 權限層級：

```
Layer 1: 代理人 frontmatter tools         ← 代理人可用工具清單
Layer 2: 代理人 frontmatter permissionMode ← 權限提示處理模式（關鍵）
Layer 3: settings.local.json permissions.allow ← 全域允許清單
Layer 4: 互動式權限提示                    ← 即時批准
```

**關鍵誤解 #1**：`tools` frontmatter 是**可用工具清單**，不是 runtime 授權。
**關鍵誤解 #2**：`permissions.allow` 的 `Edit` 對 subagent **無效**，真正控制權在 `permissionMode`。

**正確機制**（參考 https://code.claude.com/docs/en/sub-agents#permission-modes）：

| permissionMode | 行為 | 適用場景 |
|----------------|------|---------|
| `default`（預設） | 標準檢查含提示 | 前台互動（背景會自動拒） |
| `acceptEdits` | 自動接受 Edit + FS 命令 | **實作類 subagent** |
| `auto` | 分類器評估 | 中等信任度 |
| `dontAsk` | 自動拒（allow 清單仍有效） | 僅讀取類 |
| `bypassPermissions` | 跳過所有提示 | 高風險、需謹慎 |
| `plan` | 唯讀探索 | 規劃類 |

**本案鍵結**：thyme-python-developer 無 `permissionMode` 欄位 → 預設 `default` → 背景模式下 Edit 提示無人批准 → 自動拒。

## 本案實例

- thyme frontmatter：`Tools: Edit, Write, Read, Bash, Grep, LS, Glob`
- settings.local.json permissions.allow：沒有 Edit / Write / Grep
- 結果：背景代理人無法修改 `lifecycle.py` 或 `test_track_lifecycle.py`
- 代理人回報：「工具權限被拒。Edit/Grep 拒絕，但計畫已擬定完畢」

## 影響

| 情境 | 後果 |
|------|------|
| 背景代理人遇到未授權工具 | 直接拒絕 → 代理人降級為規劃角色，實作無法完成 |
| 前台代理人遇到未授權工具 | 觸發互動提示 → 打斷對話節奏，用戶必須手動批准 |
| 每次新設備/新 session | 權限狀態可能不同，代理人行為不一致 |

## 防護措施

### 正確修正（已驗證 — retry4 確認）

在**代理人 frontmatter** 加入 `permissionMode: bypassPermissions`（若代理人會在 worktree 編輯）：

```yaml
---
name: thyme-python-developer
tools: Edit, Write, Read, Bash, Grep, LS, Glob
permissionMode: bypassPermissions
---
```

**為何不用 acceptEdits**（retry3 失敗教訓）：
- `acceptEdits` 只自動接受 **working directory 或 additionalDirectories** 內的編輯
- subagent 繼承主 session 的 cwd = 主倉庫路徑
- worktree 位於主倉庫 **外部**（`../book_overview_v1-<ticket>`）→ 不在 acceptEdits 範圍
- 背景 subagent 仍會收到權限提示 → 無人批准 → 自動拒

**bypassPermissions 的安全保證**：
- 官方文件：`.git` / `.claude` / `.vscode` / `.idea` / `.husky` 仍會提示
- **例外**：`.claude/commands` / `.claude/agents` / `.claude/skills` 在 bypass 下允許
- 實作代理人修改 `.claude/skills/` + `docs/` 都在允許範圍內

### 錯誤嘗試（已驗證無效）

- settings.local.json `permissions.allow` 加 `Edit` / `Write` / `Grep`：對 subagent **無效**
- settings.local.json `permissions.allow` 加 `Edit(**)` / `Edit(/path/**)`：對 subagent **無效**

**為何：** 這些設定適用於**主線程**權限。Subagent 的 Edit 權限獨立由 `permissionMode` 控制。

### retry5 新發現（2026-04-13）

**retry4 聲稱被推翻**：`bypassPermissions` 不是 worktree 場景的萬能解方。

**事件**：某 Ticket 派發 thyme-python-developer（frontmatter 已有 `permissionMode: bypassPermissions`）執行 Edit worktree 絕對路徑（`/path/to/worktree-ticket/.claude/agents/*.md`），首次 Edit 操作即被拒。

**真正根因**：`permissionMode` 受 **subagent cwd** 限制。

- subagent 繼承主 session 的 cwd（通常是主 repo）
- PM 派發時若指定 worktree 的**絕對路徑**（cwd 外部），對 subagent 視角是「cwd 外部路徑」
- `acceptEdits` 只認 cwd 或 `additionalDirectories`（retry3 已知）
- `bypassPermissions` 的「`.claude/agents` 允許」判斷**也可能基於 cwd 相對路徑識別**（新發現）
- 結果：兩種 mode 在「cwd 外的 worktree 絕對路徑」皆不可靠

**關鍵證據**（saffron 調查）：

某 Ticket Phase 3b-A/B（2026-04-12 17:28）commit `56521697` / `2632c0c7` 由 thyme 並行執行 Python Edit，當時：
- thyme frontmatter **無** `permissionMode`
- settings.local.json **無** Edit/Write allow（19:34 才加入）

但 thyme 成功。這**推翻「permissionMode 是 subagent Edit 的必要條件」**。最可能解釋：**主 session 的互動模式（accept-edits）透過某種機制影響 subagent 的工具批准行為**，frontmatter permissionMode 僅能放寬不能覆蓋主 session 限制。

**正確修復策略（retry5 更新）**：

優先序：

1. **PM 在主 repo feat 分支直接執行框架配置修改**（推薦）
 - 適用：`.claude/agents/`、`.claude/rules/`、`.claude/references/` 等框架層檔案
 - 為何：PM cwd 對齊主 repo，具 acceptEdits 權限；這些屬於框架配置非產品程式碼，pm-role 允許

2. **設定 `additionalDirectories` + `acceptEdits`**
 - 在 `settings.local.json` 將 worktree 絕對路徑加入 `permissions.additionalDirectories`
 - 代理人 frontmatter 用 `acceptEdits`
 - 缺點：每個 worktree 要手動維護

3. **禁止：prompt 要求代理人 `cd` 到 worktree**
 - 環境的 zsh `chpwd` hook 會觸發 `ls` 淹沒代理人輸出（IMP-056）

**檢測訊號**：代理人具 `permissionMode: bypassPermissions` 但仍回報 `Permission to use Edit has been denied` → 立即懷疑是 worktree cwd 不對齊，切換方案 1。

### retry6 新案例（2026-04-28，W17-088）

**事件**：派發 thyme-documentation-integrator（frontmatter `permissionMode: acceptEdits`）執行 Edit `.claude/agents/basil-writing-critic.md`，cwd 為主 repo（**非 worktree**）。Edit 與 `mcp__serena__replace_content` 兩者皆被拒，agent 回報「Both Edit and mcp__serena__replace_content have been denied」並停止執行。

**新發現**：retry5 強調「worktree 絕對路徑」失敗，但本案件 target 在主 repo cwd 內部、且為 `.claude/` 框架檔案，理論上應在 acceptEdits 範圍。仍失敗代表 **subagent permissionMode 在某些 session 狀態下完全不生效**，不限於 worktree 場景。

**最可能根因**（待後續調查確認）：

1. **主 session 模式繼承問題**：subagent 的 Edit 批准行為可能繼承自主 session 當下的互動模式快照（retry5 已假設）。若主 session 啟動時不在 acceptEdits 模式，subagent 即使宣告 acceptEdits 也無法覆蓋。
2. **`.claude/` 路徑的特殊保護**：CC runtime 對 `.claude/` 有 hardcoded 保護（ARCH-015 已指出 worktree 內 `.claude/` 被擋），可能擴展至 subagent 在主 repo 內 `.claude/` 也需互動批准。
3. **Hook 攔截**：某 PreToolUse hook 在 subagent 環境下將 Edit/Write 改為 deny。

**修復策略（更新優先序）**：

優先序：

1. **PM 在前台直接執行框架配置修改**（最高優先，retry5 即為此結論）
   - 適用：`.claude/agents/`、`.claude/rules/`、`.claude/references/`、`.claude/error-patterns/` 等框架層檔案
   - 為何：PM cwd 對齊主 repo，具完整 Edit 權限，避開 subagent permissionMode 黑箱

2. **派發前測試 subagent 是否能 Edit 該路徑**
   - 派發 thyme/mint 等代理人前，先派一個極小測試任務（Edit 一個無關緊要的檔案 + revert）確認 permissionMode 生效
   - 不生效則切換方案 1

3. **避免 subagent Edit `.claude/` 內檔案（保守規則）**
   - W17-088 證據：即使主 repo cwd + acceptEdits 仍可能被拒
   - 實務作法：`.claude/` 內所有 Edit 一律 PM 前台執行；subagent 限定處理 `src/`、`tests/`、`docs/` 等非框架檔案

**檢測訊號（追加）**：subagent 派發後立即回報「Edit/Write 被拒」+ target 在 `.claude/` 內 → 不必嘗試任何修復，直接 PM 前台 Edit。

### 長期（框架級）

1. **派發前 preflight check**：PM 派發代理人前，掃描 prompt 中提及的工具（Edit/Write 等），對照 settings.local.json 的 allow list，若缺失則警告或自動補加
2. **代理人啟動 self-check**：代理人啟動時先測試自己宣告的 Tools 能否實際呼叫，缺失則 early fail 而非進入規劃模式
3. **全域預設 allow list**：專案初始化時，自動在 settings.local.json 配置一份標準 allow list，包含所有常用代理人工具

### PM 派發前檢查

PM 派發需要編輯的代理人前，確認：

- [ ] Edit / Write / Grep 在 permissions.allow 中？
- [ ] 代理人會用到的 Bash 子命令（uv run、pytest 等）是否在 allow 中？
- [ ] 若背景派發，所有必要工具都已預先授權？

## 與其他 pattern 的關係

- **PC-058**（ANA Ticket metadata 漂移）：在 Ticket 層級缺少設定；本 pattern 在工具權限層級缺少設定。都是「宣告 vs 實際」落差。
- **IMP-050**（hook_utils 是 Package 非檔案）：相似概念——代理人 prompt 提及的資源（import path / tool name）與實際環境不一致。

## 檢測方式

代理人回報包含以下字串時：
- "工具權限被拒"
- "Edit 被拒絕"
- "Permission denied for tool"
- "tool permission denied"

→ 立即檢查 `settings.local.json` 的 `permissions.allow` 是否包含該工具

## 記錄於 Memory

對應 memory 項目：`feedback_agent_tools_runtime_permission.md`
