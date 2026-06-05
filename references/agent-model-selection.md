# Agent Model 選擇指南

本文件記錄 `.claude/agents/*.md` 的 `model` 欄位選擇原則與背景，供後人新增 / 調整代理人 model 時參考。

> **觸發背景**：0.31.1-W8-031（盤點並提升過載代理人 model）。source: W8-029 實證 coriander 整合測試任務在 sonnet 下 3 連敗（Prompt too long）。

---

## 核心背景：sonnet 1m 訂閱模式已停用

**Why**：Claude Code 較新版本的訂閱模式已不再提供 sonnet 的 1M context 變體。過去設 `model: sonnet` 的寫碼 / 多檔讀取代理人能跑在 sonnet 1m 上，故未過載；訂閱政策變更後，sonnet 退回 200K context。

**Consequence**：本專案 auto-loaded rules（`CLAUDE.md` + `.claude/rules/**`）約佔 55K tokens，已吃掉 sonnet 200K 的約 1/4。任何「多檔讀取」或「寫碼探索」任務的 context 疊加會觸頂，表現為 `Prompt too long`。W8-029 實證：coriander（整合測試）3 連敗，而同任務的 saffron（已是 opus 1m）不過載——差異主導因子為任務探索成本 + agent preload 疊加。

**Action**：過載風險代理人（寫碼 / 多檔讀取 / 深度探索）的 model 不可設 `sonnet`；改用能取得 1M context 的方案（見下節）。

---

## model 寫法：inherit vs 硬編碼 1m

| 寫法 | 語意 | 適用 | 風險 |
|------|------|------|------|
| `inherit`（或省略 model 欄位） | 繼承當前主 session 模型 | 過載風險代理人（W8-031 採用） | session 切到非-1m 模型時，agent 也降級（與 PM 一致，非單一 agent 失誤） |
| `claude-opus-4-X[1m]`（硬編碼） | 不論 session 一律強制 1m opus | 需強制保證 1m 的代理人（bay / saffron） | 版本字串會過期，需手動更新（4-6 → 4-8 → ...） |
| `opus`（普通 alias） | 繼承 session 的 opus，但**不保證** 1m | 不建議用於防過載 | 訂閱模式下可能退回 200K，無法解決過載 |
| `sonnet` / `haiku` | 強制小模型 | 純輕量任務、範本、DEPRECATED 豁免 | 多檔 / 寫碼任務會過載 |

**關鍵區別**：`inherit` 是「跟隨」（model 隨 session 變動），硬編碼 `[1m]` 是「強制」（鎖定）。兩者在 1m session 下都能拿到 1M context；差異只在未來切換 session 時的行為。

**W8-031 決策**：7 個過載風險代理人採 `inherit`。理由：(1) 與 `rosemary`(PM) 同模式；(2) 零版本維護（不會隨 Opus 版號過期）；(3) 唯一風險（切非-1m session）下 PM 自身也降級，是全局一致選擇。

> **`[1m]` 後綴的必要性**：要真正取得 1M context window，model ID 必須帶 `[1m]` 變體標記（如 `claude-opus-4-8[1m]`）。`inherit` 繼承的是主 session 的完整 model ID——若 session 是 `claude-opus-4-8[1m]`，agent 同步取得 1m。

---

## 盤點分類表（W8-031）

### 升級至 1m（model: inherit）

| Agent | tools | 負載特性 |
|-------|-------|---------|
| acceptance-auditor | All tools | 驗證跑測試 + 多檔一致性檢查 |
| coriander-integration-tester | Grep, Read, Glob, Bash | 整合測試多檔探索（已實證 3 連敗） |
| project-compliance-agent | Edit, Write, Read, Bash, Grep, Glob, LS | 寫碼 + 跨文件一致性檢查 |
| thyme-documentation-integrator | All tools | 文件整合（寫）+ 多檔讀取整合 |
| sassafras-data-administrator | Read, Grep, Glob, LS, Bash, serena | DBA 唯讀設計，多檔深度分析 |
| sumac-system-engineer | Read, Bash, Grep, Glob, LS | 環境除錯，唯讀但探索成本高 |
| oregano-data-miner | Grep, LS, Read | 純策略規劃，最輕量；保守全面防過載一併升級 |

### 豁免維持小模型

| Agent | model | 豁免理由 |
|-------|-------|---------|
| john-carmack | sonnet | DEPRECATED，已併入 ginger-performance-tuner，不再派發 |
| memory-network-builder | haiku | DEPRECATED，已併入 continuous-learning Skill |
| language-agent-template | haiku | 範本檔，非實質代理人 |
| impeccable-manual-edit-applier | inherit | 已是 inherit |
| rosemary-project-manager | inherit | PM，已是 inherit |

### 既有硬編碼 1m（未在本次範圍，保留現狀）

| Agent | model | 說明 |
|-------|-------|------|
| bay-quality-auditor | claude-opus-4-6[1m] | 強制 1m 保證；版本字串較舊但功能正常 |
| saffron-system-analyst | claude-opus-4-6[1m] | 同上 |

> **後續可選**：若要統一格式，可評估將 bay / saffron 的硬編碼 4-6 改為 `inherit`，與本次決策一致。屬獨立調整，需另開 ticket（避免本 ticket 範圍蔓延）。

---

## 新增代理人時的 model 決策流程

1. 此代理人會**寫碼**或**讀取多個檔案**或**深度探索**（除錯 / 設計 / 驗證）嗎？
   - 是 → 用 `inherit`（跟隨 session 取 1m）
   - 否（純輕量單檔 / 範本 / DEPRECATED）→ 可用 `haiku` / `sonnet`
2. 需**不論 session 一律強制 1m**（如核心審計角色）嗎？
   - 是 → 硬編碼 `claude-opus-4-X[1m]`（X 取當時最新版號）
   - 否 → `inherit` 即可

---

## 相關文件

- `.claude/agents/AGENT_PRELOAD.md` — 代理人共享 preamble（auto-loaded rules 的主要來源之一）
- `.claude/rules/core/cognitive-load.md` — Context Bundle token 閾值與過載判準
- `docs/work-logs/v0/v0.31/v0.31.1/tickets/0.31.1-W8-029.md` — coriander 過載根因分析
- `docs/work-logs/v0/v0.31/v0.31.1/tickets/0.31.1-W8-031.md` — 本次盤點與提升

---

**Last Updated**: 2026-06-05 | **Version**: 1.0.0 — 初版，W8-031 落地（sonnet 1m 訂閱停用背景 + inherit/硬編碼決策原則 + 盤點分類表）
