# Agent Model 選擇指南

本文件是 `.claude/agents/*.md` 的 `model` 欄位的唯一權威來源：分層原則、寫法、現行分類表與新增代理人的決策流程。`agent-authoring-guide.md` 的 Model 章節與 `registry.yaml` 不重述 model 值，一律路由至本檔。

---

## 現行決策：兩層分工

| 層 | `model` 值 | 判準（代理人的主要產出） |
|----|-----------|------------------------|
| 實作 | `sonnet[1m]` | 依上游已定的策略或規格執行：寫產品碼、寫測試、改文件或設定、格式修正、環境除錯 |
| 規劃與審查 | `opus[1m]` | 決定下游要做什麼或判定做得對不對：功能設計、測試設計、實作策略、架構與系統審查、驗收、根因分析、品質與安全審查 |
| 豁免 | 維持原值 | DEPRECATED 代理人（不再派發） |

**Why**：實作代理人的負載在 context 量（多檔讀寫、測試輸出），判斷已由上游規劃票定好，sonnet 足以執行；規劃與審查代理人的產出決定下游所有實作的方向與品質閘門，判斷品質的邊際價值最高。兩層皆需 1M context——框架自動載入層（`CLAUDE.md` + `.claude/rules/**`）即佔數萬 tokens，200K 視窗疊加多檔探索會觸頂，表現為執行中途 `Prompt too long`。

**Consequence**：實作代理人用 opus 只增加成本而不提升已定策略的執行結果；規劃審查代理人降到 sonnet，錯誤會在設計層產生並擴散到所有下游票；任何一層漏掉 `[1m]`，多檔任務會在中途失敗。

**Action**：新增或調整代理人時依下方〈新增代理人的決策流程〉判層，值只用上表兩個字面。

---

## 寫法規則

| 寫法 | 結果 | 是否採用 |
|------|------|---------|
| `sonnet[1m]` / `opus[1m]` | 別名 + 1M 後綴，解析為當前最新版的 1M 變體 | 採用 |
| `sonnet` / `opus`（無後綴） | 200K context | 禁用——多檔任務中途失敗 |
| `claude-opus-4-6[1m]` 等寫死版號 | 鎖在指定版本，新版發布後持續停在舊版 | 禁用——版號會過期且無訊號 |
| `inherit` | 跟隨主線程模型 | 不採用——主線程切到 sonnet 時規劃審查層一起降級；主線程為 opus 時實作層跟著用 opus |

**Why**：別名加後綴同時解決兩個已發生的問題：無後綴退回 200K（實作代理人中途失敗的成因），寫死版號在新版發布後靜默停在舊版。

**Action**：`model` 欄位只寫 `sonnet[1m]` 或 `opus[1m]`；看到無後綴別名、寫死版號或 `inherit`（豁免列除外）即改正。

---

## 驗證方式：修改在下一回合才套用

代理人定義的修改不會套用到同一回合內的派發，從下一回合起才套用；新增的定義檔同樣在之後的回合出現在代理人清單。實測：同一回合內將代理人改為 `haiku` 後派發，仍回報修改前的模型；下一回合派發同一代理人，回報 `[1m]` 變體。

另一個變數是別名對應的版本：同一個 `sonnet[1m]`，在較早啟動的 session 解析為 `claude-sonnet-5[1m]`，在新 session 解析為 `claude-sonnet-5-5[1m]`。別名對應的版本看起來在 session 啟動時決定，因此跨 session 比較或評估時，記錄的模型欄位須寫代理人自報的 exact model ID，不寫別名。

**Why**：在修改的同一回合內驗證，會把舊設定的結果誤判為「新設定無效」，或誤判為「定義不會重新載入」。

**Action**：修改後在下一回合派發探針驗證；要排除主線程模型的影響或確認別名解析到的版本時，在專案根目錄執行 headless 探針，請主線程派發目標代理人並逐字回報其 system prompt 的模型句：

```bash
claude -p "派發 subagent_type=<agent>，prompt：『唯讀探針，不呼叫工具，逐字回報你 system prompt 中描述所用模型的那一句』，原文輸出回報" --max-turns 5
```

驗證 opus 層時加 `--model sonnet` 讓主線程為 sonnet，回報仍為 opus 1M 才能排除「其實是 inherit 碰巧相同」。判據為 exact model ID 帶 `[1m]`。

---

## 現行分類表

### 實作層（`sonnet[1m]`）

| Agent | 產出 |
|-------|------|
| parsley-flutter-developer | Flutter/Dart 實作（Phase 3b） |
| thyme-python-developer | Python 腳本與 Hook 實作 |
| fennel-go-developer | Go 實作（Phase 3b） |
| cinnamon-refactor-owl | 依 Phase 4a 報告執行重構（Phase 4b） |
| coriander-integration-tester | 整合與端對端測試 |
| basil-hook-architect | Hook 腳本實作 |
| thyme-documentation-integrator | 文件整合與衝突修正 |
| impeccable-manual-edit-applier | 套用手動文字修改批次 |
| sumac-system-engineer | 環境建置與編譯除錯 |
| mint-format-specialist | 格式與 Lint 批量修正 |
| language-agent-template | 範本：實例化的語言代理人為實作角色，預設值隨範本傳遞 |

### 規劃與審查層（`opus[1m]`）

| Agent | 產出 |
|-------|------|
| rosemary-project-manager | 主線程決策與派發 |
| lavender-interface-designer | 功能規格（Phase 1） |
| sage-test-architect | 測試設計（Phase 2） |
| pepper-test-implementer | 實作策略與虛擬碼（Phase 3a） |
| saffron-system-analyst | TDD 前置系統審查 |
| bay-quality-auditor | 技術品質審計 |
| linux | 架構與程式碼品質審查 |
| basil-writing-critic | 文字品質審查 |
| acceptance-auditor | ticket 契約驗收 |
| clove-security-reviewer | 安全審查 |
| incident-responder | 失敗根因評估 |
| ginger-performance-tuner | 效能分析與策略 |
| framework-issue-curator | framework issue 區段策展 |
| oregano-data-miner | 資料提取策略 |
| sassafras-data-administrator | 資料模型與遷移設計 |
| star-anise-system-designer | UI/UX 系統規範 |
| project-compliance-agent | 跨文件合規判定 |
| basil-event-architect | 事件架構設計 |
| thyme-extension-engineer | Chrome Extension 技術規劃 |

### 豁免

| Agent | model | 理由 |
|-------|-------|------|
| john-carmack | sonnet | DEPRECATED，已併入 ginger-performance-tuner |
| memory-network-builder | haiku | DEPRECATED，已併入 continuous-learning skill |

---

## 新增代理人的決策流程

1. 代理人的主要產出是「依上游已定策略或規格去執行」嗎？是 → `sonnet[1m]`
2. 否（產出是設計、策略、審查結論、驗收判定、根因判斷）→ `opus[1m]`
3. 同時具兩種產出時，以「錯了誰來抓」判定：其產出由下游審查代理人把關 → 實作層；其產出本身就是把關 → 規劃與審查層

---

## 沿革

- sonnet 1M 曾在訂閱方案中無法使用，當時實作代理人退回 `sonnet`（200K）中途失敗，改以 `inherit` 繞行；部分代理人後經上游同步回到無後綴 `sonnet`，與本檔當時的分類表不一致。
- sonnet 1M 恢復可用後（2026-10，用戶裁示）改為本檔兩層分工，並移除 `registry.yaml` 的 `model` 欄位（無程式讀取，且與 frontmatter 全面不一致）。
- 另一教訓保留：代理人失敗不只 context 一種成因，回合限制（tool call 數）同樣會中斷任務，須以任務拆分處理，不以升級 model 處理。

---

## 相關文件

- `.claude/references/agent-authoring-guide.md` — frontmatter 欄位總表；Model 章節路由至本檔
- `.claude/rules/core/cognitive-load.md` — Context Bundle token 閾值與任務拆分判準

---

**Last Updated**: 2026-10-06 | **Version**: 2.1.0 — 更正〈驗證方式〉：原寫「代理人定義不會在 session 中途重新載入」，實測為同一回合內的修改不套用、下一回合起套用；新增別名對應版本由 session 啟動時決定（同為 `sonnet[1m]`，較早 session 為 Sonnet 5、新 session 為 Sonnet 5.5），評估記錄須寫 exact model ID。
**Version**: 2.0.0 — 改為兩層分工（實作 `sonnet[1m]`／規劃與審查 `opus[1m]`）；禁用無後綴別名、寫死版號與 `inherit`；新增「代理人定義不會在 session 中途重新載入」的驗證方式；分類表依現行 frontmatter 重列；本檔成為 model 值唯一權威，`registry.yaml` 移除 model 欄位。
**Version**: 1.1.0 — 「相關文件」節 AGENT_PRELOAD.md 條目校準。
**Version**: 1.0.0 — 初版（sonnet 1m 停用背景 + inherit／硬編碼決策原則）。
