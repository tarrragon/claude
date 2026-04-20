# ARCH-015: subagent .claude/ 寫入 hardcoded 保護

## 基本資訊

- **Pattern ID**: ARCH-015
- **分類**: 架構設計（Claude Code runtime 行為）
- **來源版本**: v0.18.0
- **發現日期**: 2026-04-13
- **更新日期**:
  - 2026-04-15（W10-049.4）修正：主 repo 內 subagent 也被擋（本結論 **2026-04-18 驗證後部分推翻**，見下方 v2.1.114 實證章節）
  - 2026-04-18（W5-050.1/2/3）重新實證：**真正分界線是 target 是否在主 repo 樹內，非「.claude/ 一律被擋」**
- **風險等級**: 中（影響範圍收斂到「外部 worktree 內 .claude/」，主 repo 內 .claude/ 實測 subagent Write/Edit 通行）
- **CC 版本基準**: v2.1.114（W5-050 實證）

## 問題描述

### 症狀

PM 主線程派發 subagent 嘗試 Edit worktree 路徑內的 `.claude/` 檔案時，無論 subagent 的 `permissionMode` 設為 `bypassPermissions`、`acceptEdits`，或 settings.json 加入 `additionalDirectories`（含 worktree 絕對路徑或 glob pattern），Edit 操作均被 CC runtime 拒絕，回傳：

```
Permission to use Edit has been denied. IMPORTANT: You *may* attempt to accomplish
this action using other tools that might naturally be used to accomplish this goal...
```

關鍵特徵：
- Read 操作不受影響（讀寫權限不對稱）
- 同 subagent 對 worktree 內**非 .claude/** 路徑（docs/、src/）Edit **可成功**
- 同 subagent 對主 session cwd 內 `.claude/` Edit **也被擋**（W10-049.4 案例修正：thyme-documentation-integrator 在主 repo 嘗試 Edit `.claude/README.md` 仍被 CC runtime 拒絕，hook log 顯示 hook 已正確跳過 subagent，但 CC runtime 在 hook 之前就擋了）
- 拒絕來源不是任何 hook（hook-logs 顯示 ALLOW），是 CC runtime 層

### 根本原因（5 Why 分析）

1. Why 1: subagent Edit worktree 內 `.claude/` 被拒
2. Why 2: subagent 看到的 `.claude/` 寫入 scope 不包含 worktree 路徑
3. Why 3: settings.json 的 `additionalDirectories` 設定（無論絕對路徑或 glob）對 `.claude/` 路徑無效
4. Why 4: CC runtime 對 `.claude/` 目錄施加比一般路徑更嚴格的保護策略
5. Why 5（根本原因）: **CC runtime 將 `.claude/` 視為框架配置目錄，僅允許主 session cwd 內的那一份 `.claude/` 被 subagent 寫入**。此保護**繞過** `additionalDirectories` 機制（推測為硬編碼安全策略，防止 subagent 修改非預期的 framework 配置）。

### 受影響配置矩陣（2026-04-13 實證）

| 主 session cwd | 目標路徑 | 路徑類型 | additionalDirectories | 結果 |
|---------------|--------|--------|--------|------|
| 主 repo | 主 repo 內 `.claude/` | .claude/ | 無 | 成功 |
| 主 repo | 主 repo 內非 `.claude/`（docs/） | 非 .claude/ | 無 | 成功 |
| 主 repo | worktree 內 `.claude/` | .claude/ | 無 | 拒絕 |
| 主 repo | worktree 內 `.claude/` | .claude/ | 絕對路徑 | 拒絕 |
| 主 repo | worktree 內 `.claude/` | .claude/ | glob pattern | 拒絕 |
| 主 repo | worktree 內非 `.claude/`（docs/） | 非 .claude/ | glob pattern | 成功 |

### 2026-04-18 驗證結果（CC v2.1.114）

**觸發背景**：Anthropic 官方 Permissions 文件宣稱 `.claude/commands`, `.claude/agents`, `.claude/skills` 為 bypassPermissions 豁免路徑；CHANGELOG v2.1.98 修復 agent team permission 繼承 bug。W5-050.1/2/3 三實驗重新驗證 ARCH-015 是否仍成立。

**實測矩陣**（subagent cwd 為 CC isolation:worktree 建立的 agent worktree，位於主 repo 樹內 `.claude/worktrees/agent-xxx`）：

| 實驗 | target 路徑 | 工具 | 結果 |
|------|-----------|------|------|
| 050.2 A | 主 repo `/.claude/agents/TEST.md`（豁免清單） | Write + Edit | **成功** |
| 050.2 B | 主 repo `/.claude/rules/TEST.md`（非豁免清單） | Write + Edit | **成功** |
| 050.1 / 050.2 C / 050.3 | `/tmp/arch015-verify-*/`（外部 worktree）`/.claude/agents/` | Write + Edit | **被拒** |
| 050.2 D | `/tmp/arch015-verify-2/.claude/rules/` | Write + Edit | **被拒** |
| 050.1 / 050.2 / 050.3 | 外部 worktree 內 `docs/`, 根目錄 | Write + Edit | **成功** |
| 050.2 E | 主 repo 或 worktree 內 `.claude/` 的 Bash rm/printf | Bash | **被拒** |

**核心洞察**：

1. **真正分界線是「target 是否在主 session repo 樹內」**，不是：
   - 不是 `.claude/` vs 非 `.claude/`
   - 不是 subagent cwd 位置
   - 不是 permissionMode
   - 不是 `additionalDirectories` 設定
   - 不是豁免清單（agents/commands/skills）vs 非豁免子目錄

2. **推翻 2026-04-15 W10-049.4 的結論**：「同 subagent 對主 session cwd 內 `.claude/` Edit 也被擋」在 v2.1.114 實測下**並不成立**。W10-049.4 測試當時的 `.claude/README.md` 被擋，可能是：
   - 當時 CC 版本早於 v2.1.98（agent team permission 繼承 bug 期間）
   - 或 `.claude/` 根檔案（README.md）與子目錄檔案（agents/TEST.md）有不同處理（本次未直接測）

3. **Bash 側通道獨立規則**：Bash 對任何 `.claude/` 路徑（含主 repo）的寫入類命令被拒，與 Write/Edit 的規則不同。Bash 有獨立 sandbox。

4. **官方文件 vs 實測**：官方說 `.claude/agents/commands/skills` 是豁免，但 `.claude/rules` 在主 repo 內也成功。豁免清單在 acceptEdits 模式下可能不是決定性因素。

### 更新後的實用邊界

| 情境 | v2.1.114 實測行為 | 實用建議 |
|------|----------------|---------|
| Subagent 修改主 repo 內 `.claude/*`（任何子目錄） | Write/Edit 成功 | **可從任何 cwd 派發**，不限主 repo cwd |
| Subagent 修改外部 worktree `/tmp/*/.claude/*` | Write/Edit 被拒 | 不可派發；如需改該 worktree 的 `.claude/` 改用檔案搬回主 repo |
| Subagent 修改主 repo 或 worktree 內非 `.claude/` 路徑 | 成功 | 正常派發 |
| Subagent 用 Bash 寫入任何 `.claude/` 路徑 | 被拒 | 改用 Write/Edit 工具（主 repo 內）或不要在 Bash 做 `.claude/` 寫入 |

### 觸發條件（2026-04-18 修正後）

以下**三條件同時成立**時必然觸發：

1. 派發 subagent 嘗試 Write/Edit 目標 `.claude/` 路徑
2. 目標 `.claude/` 路徑**不在主 session 啟動目錄的檔案樹內**（典型情境：`/tmp/` 下的獨立 worktree）
3. 即使目標路徑是官方豁免清單子目錄（agents/commands/skills）

以下條件**不是觸發關鍵**（與原認知不同）：

- `permissionMode` 設定（default/acceptEdits/bypassPermissions 皆無法繞過外部路徑保護）
- `additionalDirectories` 設定（無效）
- subagent 自身 cwd 位置（可在主 repo 樹內或任何位置）
- 豁免清單子目錄（agents/commands/skills 也會被擋，**若在外部 worktree**）

## 正確做法（2026-04-18 修正版）

### 規則：`.claude/` 修改目標路徑**必須在主 repo 樹內**

| 路徑類型 | 目標在哪 | 可派發 |
|---------|---------|--------|
| `.claude/` 框架檔案 | 主 repo 內 `.claude/` | **可**（不限 subagent cwd） |
| `.claude/` 框架檔案 | 外部 worktree（`/tmp/` 或主 repo 樹外） | 不可（Write/Edit 被拒） |
| `src/` `tests/` `docs/` 等產品檔案 | worktree | 可（worktree subagent 正常運作） |

### 派發決策（修正版）

| 條件 | 派發位置 | 備註 |
|------|---------|-----|
| Prompt 目標含主 repo 內 `.claude/` 修改 | 任何 cwd 可（含 worktree） | 以往認為必須主 repo cwd，**2026-04-18 實測顯示非必要** |
| Prompt 目標含**外部** `.claude/`（worktree / 其他路徑）修改 | 無法派發 subagent；改由 PM 前台處理或搬檔到主 repo | 硬編碼保護，無法繞過 |
| Prompt 僅含非 `.claude/` 路徑 | 可在 worktree 或主 repo 派發 | 無限制 |

### Read 操作不受限制

subagent 在任何 cwd 都可 Read 任何路徑的 `.claude/` 檔案（含外部 worktree）。僅 Write/Edit 被限制於「主 repo 樹內」。

### Bash 側通道另有規則

Bash 對**任何** `.claude/` 路徑（含主 repo）的寫入類命令（rm/printf/mkdir 等）在 subagent 下被拒，與 Write/Edit 規則不同。若需對主 repo `.claude/` 做檔案操作，改用 Write/Edit 工具。

## 防護措施

### 開發時

- PM 派發前檢查 prompt 提及的路徑：含 `.claude/` 路徑且 cwd 為 worktree 時，改為主 repo 派發
- worktree skill 文件明確標示「`.claude/` 變更不在 worktree 進行」
- 跨 `.claude/` 與其他路徑的 ticket，拆分子任務分別派發

### 偵測時（Hook 候選）

`agent-dispatch-validation-hook` 可擴充：偵測 prompt 含 `.claude/` 路徑且當前 cwd 為 worktree 時，警告 PM 重新評估派發位置。

### 為何 `additionalDirectories` 無法解決

實證：絕對路徑與 glob pattern 均無效。CC runtime 對 `.claude/` 的保護優先於 `additionalDirectories`。**不要繼續嘗試此路徑**，浪費時間。

### 為何 `--add-dir` / `/add-dir` 對 PM workflow 不可行

- `/add-dir` 是用戶端 interactive slash command，AI 主線程無對應 deferred tool 可呼叫
- `--add-dir` 啟動參數需重啟 CC，每個 worktree 都要重啟一次
- 即使有效（推測仍受 hardcoded 保護），自動化程度低於 Option E

## 相關 Pattern

- ARCH-005: 代理人定義衝突（subagent 行為控制的另一面）
- 待補：subagent 權限與 cwd 互動細節（若未來有更深入研究）

---

**Last Updated**: 2026-04-18（W5-050.1/2/3 重驗後重大修正：分界線為「target 是否在主 repo 樹內」，非「.claude/ 一律被擋」。原 W10-049.4 認定的「主 repo 內 .claude/ 也被擋」被推翻）
