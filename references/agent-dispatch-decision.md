# 代理人派發決策表

本文件提供 PM 派發代理人前的決策依據：根據**目標檔案位置**和**隔離需求**選擇正確的派發策略，避開 permissionMode / worktree cwd 的已知陷阱。

> **目的**：讓 PM 派發前有明確決策表可查，不需在派發失敗後才事後學習。解決 permissionMode 受 subagent cwd 限制（經多次 retry 確認）帶來的重複踩雷問題。

---

## 核心決策表

| 目標檔案位置 | 派發策略 | 理由 |
|------------|---------|------|
| `.claude/rules/**` / `.claude/pm-rules/**` / `.claude/references/**` / `.claude/methodologies/**` | **PM 前台執行** | 框架層文件，pm-role 允許 PM 直接修改；避開 subagent permissionMode 陷阱 |
| `.claude/agents/**` / `.claude/skills/**` / `.claude/commands/**` | **PM 前台** 或 **代理人 + 主 repo feat 分支** | 框架配置；若需大量修改可派發但必須在主 repo（非 worktree）進行 |
| `.claude/hooks/**/*.py` | **代理人 + 主 repo feat 分支** + `permissionMode: acceptEdits` | Python 程式碼建議派發；主 repo cwd 確保 acceptEdits 生效 |
| `src/**`（產品程式碼，無隔離需求） | **代理人背景派發** + `permissionMode: acceptEdits` + 主 repo feat 分支 | 標準 TDD 實作流程 |
| `src/**`（產品程式碼，需隔離 / 並行多代理人） | **代理人 + worktree** + `permissionMode: acceptEdits` + **worktree path 加入 `additionalDirectories`** | 並行派發需要 worktree；必須在 settings.local.json 補 additionalDirectories 才能讓 acceptEdits 涵蓋 worktree 絕對路徑 |
| `tests/**` | 同 `src/**` 規則 | 測試程式碼視同產品碼 |
| `docs/**`（worklog / ticket） | **PM 前台** 或 **代理人**（視工作量） | docs/ 通常在主 repo，派發較簡單 |
| `CLAUDE.md` / `README.md` / `CHANGELOG.md` | **PM 前台執行** | 頂層文件 pm-role 明確豁免 |

---

## permissionMode 選擇指南

| permissionMode | 適用場景 | 限制 |
|----------------|---------|------|
| `default` | 前台互動（有人批准） | 背景模式會自動拒（PC-059） |
| `acceptEdits` | **實作類代理人標準值** | 只涵蓋 cwd 和 `additionalDirectories`；worktree 絕對路徑需加 additionalDirectories |
| `bypassPermissions` | 高風險、或 worktree 場景（但已驗證**不可靠**） | PC-059 retry5：受 cwd 限制，worktree 絕對路徑仍會被拒 |
| `plan` | 純分析、規劃類代理人 | 唯讀，無法實作 |
| `dontAsk` | 僅讀取類代理人 | allow 清單仍有效 |
| `auto` | 中等信任度 | 分類器評估 |

**關鍵規則**：
- **永不假設** `bypassPermissions` 在 worktree 可靠（PC-059 retry5 推翻此假設）
- **優先**讓目標路徑對齊 subagent cwd（主 repo feat 分支），而非靠 permissionMode 放寬
- 若必須用 worktree，**必須**在 `settings.local.json` 的 `permissions.additionalDirectories` 加入 worktree 絕對路徑

---

## 派發前 Preflight 檢查清單

派發代理人前，PM 必須確認：

| 檢查項 | 命令 / 動作 | 失敗時處理 |
|-------|-----------|----------|
| 目標檔案位置分類 | 查上表決定策略 | 若跨多類檔案 → 拆成多個子任務 |
| 代理人 frontmatter 有無 permissionMode | `head -30 .claude/agents/<agent>.md` | 若無、預設 `default` 不適合背景派發 → 用 PM 前台或修 frontmatter |
| 若用 worktree 方案 | 確認 worktree 路徑在 `settings.local.json` `additionalDirectories` | 未加 → 加入後才派發（否則 acceptEdits 無效） |
| 分支狀態 | `git branch --show-current` + `git worktree list` | 不在預期分支 → 先切換 |
| dispatch-active.json 計數 | `cat .claude/dispatch-active.json` | 已有活躍派發 → 評估並行是否安全 |

---

## 已知失敗模式速查

| 症狀 | 可能原因 | 解方 |
|------|---------|------|
| 代理人回報「Permission to use Edit has been denied」 | cwd 不對齊目標路徑 | 切換到方案：PM 前台執行，或改用主 repo feat 分支 |
| 代理人背景派發無修改但 git 無變更 | permissionMode 為 default，背景無人批准 | frontmatter 加 `permissionMode: acceptEdits` |
| worktree 中代理人編輯 .claude/ 被拒絕 | **CC runtime hardcoded 保護**（非 hook 攔截），additionalDirectories 無法繞過（ARCH-015） | **必須**改用主 repo cwd（PM 前台或主 repo subagent），不要繼續嘗試 additionalDirectories / --add-dir |
| 代理人修改了 Ticket scope 外的檔案 | 重試 prompt 擴大 scope（PC-050 延伸） | 重試時嚴守原 Ticket 驗收條件 |
| Worktree 建立後缺依賴 | worktree 不自動合併 blockedBy 分支 | prompt 加 `git merge feat/{dep}` 前置步驟 |
| isolation:worktree 代理人無法自行 `ticket track complete` 收尾 | CC runtime 的 worktree 隔離守衛判定命令字串含 `complete` token 即「透過 shell builtin complete 執行一段字串，無法驗證留在 worktree 內」而拒絕（PC-SCLK-002，1.4.0-W1-023 探針取得逐字證據證實），非本 repo 可修正 | 見下方「isolation:worktree 派發的 complete 收尾限制」專節 |

---

## isolation:worktree 派發的 complete 收尾限制（PC-SCLK-002，1.4.0-W1-023 探針證實）

**現象**：以 `isolation: worktree` 派發的代理人，在其收尾階段自行執行 `ticket track complete <id> --as <agent>` 時會被拒絕，逐字阻擋原文：

```
This agent is isolated in the worktree <worktree-path>,
but this command runs a string through complete, which can't be verified to stay inside the worktree;
run the command directly instead. Refusing to run it — a worktree-isolated agent's git operations
must target its own worktree.
```

**根因**：Claude Code runtime 的 worktree 隔離守衛偵測到命令字串含 `complete` 這個 token，判定為「透過 shell builtin `complete` 執行一段字串」而無法驗證其執行後是否仍留在 worktree 範圍內，因而拒絕。此判斷發生在 CLI 啟動之前（不存在的 ticket ID 與真實 ID 得到逐字相同的拒絕訊息即為證據），屬 runtime 層機制，**本 repo 無法修改**（`.claude/hooks/`、`.claude/skills/ticket/` 皆不涉及此邏輯）。

**派發前提（必須告知代理人或於 Context Bundle 註明）**：

- 以 `isolation: worktree` 派發、且任務結尾需呼叫 `ticket track complete` 的代理人，**該收尾動作必然失敗**，非代理人操作錯誤
- 代理人應依 PC-SCLK-002 指引：**禁止**改寫命令形式規避阻擋（base64 / eval / 變數拼接等）；於 Exit Status 記錄「complete 被 worktree 隔離守衛拒絕（已知限制，非任務失敗）」並交還 PM
- PM 收到此類回報後，於主 repo（非 worktree）執行 `ticket track complete <id> --as <agent>` 代為收尾，這是合規的標準流程，不需視為異常
- 同樣邏輯適用其他子命令字面恰為 shell builtin 名稱的 CLI 呼叫（不限 `ticket`，`doc`/`worktree` 等 skill CLI 若有同名子命令亦會觸發）

---

## 派發模式決策流程

```
開始派發前
  |
  v
目標檔案在 .claude/ 或 docs/ 或 頂層文件?
  +-- 是 → PM 前台執行（不派發）
  |
  +-- 否 ↓
  v
需要並行派發多個代理人?
  +-- 是 ↓                      +-- 否 ↓
  v                              v
需要隔離（避免衝突）?          代理人 + 主 repo feat 分支 + acceptEdits
  +-- 是 → 方案 A：worktree
  |         + additionalDirectories
  |         + acceptEdits
  +-- 否 → 方案 B：同分支並行
          （風險：PC-050 模式 C 共用分支）
```

---

## 方案 A：Worktree + additionalDirectories（並行+隔離）

**設定 settings.local.json**（派發前）：

```json
{
  "permissions": {
    "additionalDirectories": [
      "/absolute/path/to/worktree-ticket-1/",
      "/absolute/path/to/worktree-ticket-2/"
    ]
  }
}
```

**代理人 frontmatter**：

```yaml
---
name: <agent-name>
tools: Edit, Write, Read, Bash, Grep, LS, Glob
permissionMode: acceptEdits
---
```

**派發 prompt 附註**：

```
Worktree: /absolute/path/to/worktree-ticket-N
工作分支: feat/ticket-N
```

---

## 方案 B：主 repo feat 分支（不隔離）

適用單一代理人或已知不會衝突的場景。

**PM 準備**（派發前）：

```bash
cd /main/repo
git checkout -b feat/ticket-N
# 直接派發代理人到此分支
```

代理人 frontmatter 同方案 A（`acceptEdits`）。

---

## 相關錯誤模式

- PC-059 — 代理人 frontmatter Tools 宣告 ≠ 實際 runtime 權限
- PC-050 — 過早代理人完成判斷（含模式 C：共用分支）
- PC-045 — PM 代理人失敗時自行撰寫產品程式碼

---

## 後續工作（長期根因修復）

| 項目 | 說明 | 狀態 |
|------|------|------|
| Hook `is_subagent_environment` 實證 | 確認 CC 派發時 agent_id 是否一致注入 | 未開 Ticket |
| `worktree create` 自動合併 blockedBy | 解決依賴分支未自動合併問題 | 未開 Ticket |
| 派發 preflight 自動化 Hook | 派發前自動檢查 additionalDirectories / permissionMode | 未開 Ticket |

---

**Last Updated**: 2026-07-31
**Version**: 1.1.0 - 新增「isolation:worktree 派發的 complete 收尾限制」專節與失敗模式速查列（PC-SCLK-002，1.4.0-W1-023 探針取得逐字證據證實：CC runtime worktree 隔離守衛判定 `complete` token 為 shell builtin 呼叫而拒絕，本 repo 無法修正，需 PM 代跑收尾）
**Version**: 1.0.0 - 初版，整合 PC-059 retry5 結論建立決策表
