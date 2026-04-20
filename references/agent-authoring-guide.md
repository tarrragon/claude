# Agent Authoring Guide

本文件定義撰寫 Claude Code subagent（`.claude/agents/*.md`）時的規範，特別聚焦 `permissionMode` 的選擇原則。

> **核心教訓來源**：PC-059（retry5 模式）與 worktree 絕對路徑權限教訓

---

## permissionMode 為何重要

`frontmatter.tools` 宣告的是**代理人可使用的工具清單**，不是**runtime 實際授權**。兩者語義不同：

| 層級 | 作用 |
|------|------|
| `tools` frontmatter | 限制代理人能呼叫哪些工具（工具白名單） |
| `permissionMode` frontmatter | 決定被呼叫的工具如何通過權限檢查（runtime 授權模式） |
| `settings.local.json` `permissions.allow` | **對 subagent 無效**，僅控制主線程權限 |

派發背景代理人時若無正確的 `permissionMode`，工具權限提示無人互動批准，自動拒絕，代理人降級為規劃模式。

---

## permissionMode 合法值

| 值 | 行為 | 適用場景 |
|----|------|---------|
| `default`（預設） | 標準檢查含提示；背景派發自動拒 | 避免用於實作類代理人 |
| `acceptEdits` | 自動接受 **cwd 或 `additionalDirectories`** 內的 Edit/Write | 主 repo cwd 內編輯的代理人 |
| `auto` | 由分類器評估批准與否 | 中等信任度 |
| `dontAsk` | 自動拒（`permissions.allow` 仍有效） | 僅讀取類代理人 |
| `bypassPermissions` | 跳過大部分提示；`.claude/commands`、`.claude/agents`、`.claude/skills` 在此模式下允許；`.git`、其他 `.claude/` 子目錄仍提示 | 實作類代理人的慣例值（但見下方 worktree 陷阱） |
| `plan` | 唯讀探索模式 | Phase 1/3a 規劃類代理人 |

官方參考：https://code.claude.com/docs/en/sub-agents#permission-modes

---

## 選擇矩陣

| 代理人類型 | 典型工具 | 建議 permissionMode |
|-----------|---------|---------------------|
| 實作代理人（thyme/parsley/fennel/cinnamon 等） | Edit、Write、Bash | `bypassPermissions` |
| 策略規劃代理人（pepper/sage） | Edit、Write、Read | `bypassPermissions`（會寫策略 `.md`） |
| 規格設計代理人（lavender） | Write、Edit、Read | `bypassPermissions`（會寫 spec `.md`） |
| Hook 開發代理人（basil-hook-architect） | Write、Edit | `bypassPermissions` |
| 審查／稽核代理人（linux、bay-quality-auditor、clove-security-reviewer） | Read、Grep、Bash | 不設定（預設 default），純讀取不需寫權限 |
| 派發／分析代理人（rosemary、incident-responder、saffron） | Read、Grep、Bash | 不設定（預設 default） |

**判斷原則**：代理人 `tools` 清單含 `Edit` 或 `Write` 時，**必須**加 `permissionMode: bypassPermissions`。純讀取代理人不需要。

---

## 標準 Frontmatter 範例

實作代理人：

```yaml
---
name: thyme-python-developer
description: Python 開發專家...
tools: Edit, Write, Read, Bash, Grep, LS, Glob
permissionMode: bypassPermissions
color: green
model: opus
effort: low
---
```

插入位置：`tools:` 之後、`color:` 之前。

---

## Worktree 陷阱（歷史教訓）

`permissionMode` 不是萬靈丹，它受 **subagent cwd** 限制：

### 根因

- subagent 繼承主 session 的 cwd（通常是主 repo）
- 若 PM 派發時指定 **worktree 的絕對路徑**（例如 `/Users/xxx/project-feature-branch/.claude/agents/`），subagent 視這個路徑為「cwd 外部」
- `acceptEdits` 只認 cwd 或 `additionalDirectories`，worktree 外部編輯被拒
- `bypassPermissions` 的「`.claude/agents` 允許」判斷也可能基於 cwd 相對路徑識別，worktree 絕對路徑可能無法觸發例外

### 症狀

代理人回報 `Permission to use Edit has been denied.`，即使 frontmatter 已有 `permissionMode: bypassPermissions`。

### 解法（依優先序）

1. **PM 在主 repo 的 feature branch 直接執行框架配置修改**（`.claude/agents/`、`.claude/rules/` 等屬於框架層，不是產品程式碼）。
2. **將 worktree 路徑加入 `settings.local.json` 的 `permissions.additionalDirectories`**，配合 `acceptEdits`。缺點是每個 worktree 都要手動維護。
3. **派發代理人時避免使用 worktree 絕對路徑**——讓代理人在主 repo cwd 下操作，完成後由 PM checkout 到 feature branch 合併。

### 禁止

| 禁止行為 | 原因 |
|---------|------|
| prompt 中要求代理人 `cd` 到 worktree | 環境的 `chpwd` shell hook 會觸發 `ls` 淹沒代理人輸出（IMP-056） |
| 相信「frontmatter 設了 `bypassPermissions` 就沒問題」 | 經驗證在 worktree 外部絕對路徑仍可能被拒 |

---

## 錯誤嘗試（已驗證無效）

| 嘗試 | 為何無效 |
|------|---------|
| `settings.local.json` 加 `permissions.allow: ["Edit"]` | 僅對主線程生效，subagent 獨立由 `permissionMode` 控制 |
| `settings.local.json` 加 `permissions.allow: ["Edit(**)"]` 或路徑 pattern | 同上，對 subagent 無效 |
| 僅依賴 `tools: Edit, Write` 宣告 | 只授予「工具可呼叫權」，不是 runtime 批准權 |

---

## 檢查清單（新增／修改代理人時）

- [ ] 代理人 `tools` 含 `Edit` 或 `Write`？→ 必須加 `permissionMode: bypassPermissions`
- [ ] 代理人會被背景派發？→ 必須有 `permissionMode`（避免預設 `default` 自動拒）
- [ ] 派發時目標路徑是否在主 repo cwd 內？→ 若否，改走 PM 直接執行或設 `additionalDirectories`
- [ ] `name`、`description`、`tools` 三欄必填？
- [ ] 引用 `AGENT_PRELOAD.md`？

---

## Model 選擇指南

### 歷史教訓（2026-04-16 更新）

早期誤以為代理人失敗主因是「context 不足」，將所有代理人 model 統一升級至 opus 1m。後來確認真正原因是**代理人的回合限制（tool call ~20）**，非 context。統一升級造成簡單任務也用 opus 1m，浪費成本與速度。

**提醒**：model 選擇解決的是「決策品質 / 成本」問題；回合限制問題需另行處理（任務拆分、cognitive load 降低等）。

### 4 維度評分

新增代理人時，先就以下 4 維度評估該代理人的典型任務：

| 維度 | 評估問題 | 等級 |
|------|---------|------|
| **閱讀量** | 每次呼叫需讀取的檔案規模 | S(單檔) / M(數檔) / L(整模組) / XL(跨模組或整 codebase) |
| **決策複雜度** | 任務本質是機械執行還是設計判斷 | 低(機械) / 中(規則推理) / 高(設計判斷) / 極高(架構決策) |
| **輸出量** | 典型輸出長度 | 短(摘要/清單) / 中(結構化分析) / 長(完整程式碼/規格) |
| **對話深度** | subagent 內部輪數 | 單輪 / 2-3 輪 / 多輪 |

### Model 分類標準

| 類別 | model 值 | 適用條件 |
|------|---------|---------|
| **D - 1M Context** | `claude-opus-4-6[1m]` | 閱讀量 = XL，系統級審查，需跨模組累積上下文 |
| **C - Opus** | `opus` | 決策複雜度 ≥ 高，或實作代理人（品質關鍵） |
| **B - Sonnet** | `sonnet` | 決策複雜度 = 中（規則推理），結構化任務 |
| **A - Haiku** | `haiku` | 決策複雜度 = 低（機械執行），單檔格式修復類 |
| **Main** | `inherit` | 主線程代理人（如 rosemary-project-manager） |

### Model 選擇 checklist

- [ ] 代理人是否需要讀取 > 200k tokens 的上下文？→ **D (opus 1m)**
- [ ] 代理人是否做架構/設計判斷或生產程式碼？→ **C (opus)**
- [ ] 代理人是否基於明確規則做結構化產出？→ **B (sonnet)**
- [ ] 代理人是否純機械執行（格式、重命名等）？→ **A (haiku)**
- [ ] 代理人是主線程 PM？→ **inherit**

### 當前代理人分類（2026-04-16 W9-005 執行結果）

| 類別 | 數量 | 代表代理人 |
|------|------|-----------|
| D (1m) | 2 | saffron-system-analyst, bay-quality-auditor |
| C (opus) | 15 | linux, cinnamon, parsley, fennel, thyme-extension 等實作/設計類 |
| B (sonnet) | 7 | acceptance-auditor, coriander, project-compliance 等規則驗證類 |
| A (haiku) | 1 | mint-format-specialist |
| inherit | 1 | rosemary-project-manager |

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-059-agent-tools-vs-runtime-permission.md` — 完整錯誤模式
- `.claude/agents/AGENT_PRELOAD.md` — 代理人共用前置知識
- `.claude/rules/core/pm-role.md` — PM 派發角色邊界
- permissionMode 與 worktree 路徑的歷史修復紀錄（詳見 PC-059）
- 代理人 model 重新評估歷史：W9-005（2026-04-16）

---

**Last Updated**: 2026-04-16
**Version**: 1.1.0 — 新增 Model 選擇指南（W9-005 落地）
**Source**: PC-059 retry5 模式調查結論 + W9-005 代理人 model 重新評估
