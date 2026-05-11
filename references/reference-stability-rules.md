# 引用穩定性規則

> **本檔承載原 `.claude/rules/core/document-format-rules.md` 規則 7-8**。規則 1-6、YAML frontmatter、檢查清單骨架仍保留在 document-format-rules.md 自動載入。

本文件定義「引用穩定性」相關規範：規格文件的引用穩定性（規則 7）和框架文件對專案層級識別符的引用禁制（規則 8）。兩者共享「哪些來源可信、哪些引用會在時間或跨專案 sync 中失效」的核心主題。

---

## 適用情境（何時需要讀取本檔）

| 情境 | 涉及規則 |
|------|---------|
| 編輯 `docs/spec/`、`docs/use-cases.md`、`docs/proposals/` 等規格文件 | 規則 7 |
| 編輯 `.claude/` 框架檔案（rules / pm-rules / references / methodologies / agents / skills / hooks / error-patterns / best-practices） | 規則 8 |
| Code review 時檢查跨檔案引用是否指向穩定來源 | 規則 7、規則 8 |
| 升級 memory 或 ticket 內容至框架層時評估引用穩定度 | 規則 7、規則 8 |

---

## 規則 7：規格文件引用穩定性

**規格文件（docs/spec/、docs/use-cases.md）禁止引用臨時性文件**

| 文件類型 | 穩定性 | 可被規格引用 |
|---------|--------|------------|
| 規格文件（docs/spec/） | 穩定 | 是 |
| Use Cases（docs/use-cases.md） | 穩定 | 是 |
| 提案文件（docs/proposals/） | 穩定 | 是 |
| CLAUDE.md | 穩定 | 是 |
| Worklog（docs/work-logs/） | 臨時 | **否** |
| Ticket 檔案 | 臨時 | **否** |
| Plan 檔案 | 臨時 | **否** |

**允許的例外**：
- 變更歷史中記錄 Ticket ID 作為「來源標注」（如：「本次變更由 0.17.0-W1-002 執行」）
- 這是記錄歷史事實，不是建立依賴

**禁止的模式**：

| 禁止 | 原因 | 正確做法 |
|------|------|---------|
| `詳見 v0.17.1 W1-001` | Ticket 可能被遷移、刪除、重新編號 | `待定義於匯出規格章節` 或直接在此定義 |
| `參考 docs/work-logs/v0.17/...` | Worklog 會被歸檔，路徑可能失效 | 引用對應的 spec 文件 |
| `依 0.18.0-W2-001 的分析結論` | 結論應提煉為規格，而非依賴分析過程 | 將結論寫入規格文件 |

**理由**：
- 規格文件是開發的**唯一穩定依據**，worklog 和 ticket 是**過程記錄**
- 過程記錄可能遺失、修改、遷移，規格文件不應依賴不穩定來源
- 如果規格需要引用的資訊尚未定義，標記為「待定義」而非指向臨時文件

---

## 規則 8：框架文件禁止引用專案層級識別符

**`.claude/` 框架文件禁止引用專案特定的 ticket ID、commit hash、worklog 路徑等專案層級識別符**

`.claude/` 是**跨專案共用框架**，透過 sync 機制同步到多個專案（如 `.claude/skills/sync-push`、`sync-pull`）。專案層級識別符只存在於當前專案，sync 到其他專案後會變成死連結和誤導性資訊。

| 識別符類型 | 範例 | 可在框架文件引用？ |
|---------|------|-----------------|
| 專案 ticket ID | `0.18.0-W5-001`、`W2-007` | **否** |
| 專案 commit hash | `8f74d08`、`abc1234` | **否** |
| 專案 worklog 路徑 | `docs/work-logs/v0.17/...` | **否** |
| 專案 proposals ID | `PROP-007` | **否**（除非已提煉為方法論） |
| 框架 error-pattern ID | `PC-050`、`IMP-003`、`ARCH-002` | **是**（框架內部分類） |
| Claude Code 版本號 | `CC 2.1.97` | **是**（外部平台識別） |
| 框架檔案路徑 | `.claude/rules/core/pm-role.md` | **是**（框架內部結構） |

**適用範圍**：

| 目錄 | 適用規則 8？ |
|------|-------------|
| `.claude/rules/` | 是 |
| `.claude/pm-rules/` | 是 |
| `.claude/references/` | 是 |
| `.claude/methodologies/` | 是 |
| `.claude/error-patterns/` 內容（檔名除外） | 是 |
| `.claude/agents/` | 是 |
| `.claude/skills/` | 是 |
| `.claude/hooks/` Python docstring/comment | 是 |
| `.claude/best-practices/` | 是 |
| `.claude/handoff/archive/` | **否**（歷史紀錄，合理保留） |
| 專案 `docs/` | **否**（專案內部，可引用） |
| `CLAUDE.md` | **否**（專案入口，可引用） |

**Memory 和 ticket 也是專案層級**：

用戶/專案 auto-memory（`~/.claude/projects/<project>/memory/`）和 ticket（`docs/work-logs/`）**都不會跨專案 sync**，所以「把原則寫到 memory」不能取代框架規則。需要跨專案落實的原則必須寫入：
- `.claude/rules/`（自動載入規則）
- `.claude/error-patterns/`（錯誤學習經驗）
- `.claude/methodologies/`（方法論）

**禁止的模式**：

| 禁止 | 改為 |
|------|------|
| `（來源：0.18.0-W4-002）` | `（防範 Hook error 干擾代理人判斷）` |
| `（W5-021 教訓）` | `（多代理人 permissionMode 批次修復教訓）` |
| `**Ticket**: 0.17.3-W12-001`（在 error-pattern 內） | 移除整行（檔名 PC-XXX 已是足夠識別） |
| `來源：PROP-007` | 以提案內容的抽象描述取代 |

**允許的例外**：

| 例外 | 說明 |
|------|------|
| error-pattern 檔名本身 | `PC-050-premature-agent-completion-judgment.md` 是框架內部分類 |
| 觸發日期 | 「2026-04-12 新增」可保留，日期不是專案識別符 |
| 通用 CC 能力版本號 | 「CC 2.1.97 新增 /agents 分頁」屬外部平台能力 |

**理由**：
- `.claude/` 經 sync 跨專案共用，專案識別符在其他專案是死連結
- 框架文件的價值在於**抽象原則**，專案引用是耦合而非依賴
- Memory/ticket 也是專案內部，不能承擔跨專案原則的傳遞責任

---

## CLAUDE.md 章節外移決策樹

**Why**：縮減 `CLAUDE.md` 體量時，章節外移目標必須依「內容是否含專案層級識別符」決定，誤將專案內容外移到 `.claude/references/`（跨專案 sync 範圍）會觸發規則 8 違反；誤將通用內容外移到 `docs/`（專案內部）則喪失跨專案知識複用。

**Consequence**：外移目標選錯會讓 `.claude/` sync 機制把專案專屬內容（如 `src/` 路徑、產品名稱）擴散到其他專案，造成跨專案誤導；或讓跨專案通用知識被困在單一專案 `docs/` 失去複用機會。

**Action**：執行 `CLAUDE.md` 章節外移前依下方決策樹判定目標，外移後執行檢查清單驗證合規。

### 觸發條件

| 訊號 | 處理 |
|------|------|
| `CLAUDE.md` 單檔行數 > 200（或某章節 > 50 行） | 評估外移 |
| 章節內容只在特定情境（如寫程式碼前）才需要 | 評估外移為 lazy-load reference |
| 章節含具體實作細節（命名清單、檔案位置表） | 評估外移以保持 `CLAUDE.md` 抽象層級 |

### 外移目標選擇決策樹

依序回答以下問題：

| 步驟 | 問題 | 是 → 目標 | 否 → 下一步 |
|------|------|----------|------------|
| 1 | 章節是否含**專案層級識別符**（`src/` 路徑、產品名稱、專案 ticket ID、專案 commit hash、專案 worklog 路徑）？ | `docs/<descriptive-name>.md` | 進入步驟 2 |
| 2 | 章節是否含**跨專案可複用的通用知識**（如 Chrome Extension 限制、Manifest V3 行為、Python 通用規範）？ | `.claude/references/<descriptive-name>.md` | 進入步驟 3 |
| 3 | 章節是否為**混合內容**（部分專案、部分通用）？ | 拆檔：專案部分放 `docs/`、通用部分泛化後放 `.claude/references/` | 留在 `CLAUDE.md`（無法外移） |

### 目錄性質對照表

| 目錄 | sync 範圍 | 可含專案識別符？ | 適用情境 |
|------|----------|---------------|---------|
| `docs/` | 專案內部，不 sync | 是 | 專案專屬規範、架構說明、需求/規格 |
| `.claude/references/` | 跨專案 sync | 否（規則 8） | 跨專案技術速查、通用 lazy-load 參考 |
| `CLAUDE.md` | 專案入口，不 sync | 是 | 高層概覽 + lazy-load 指引 |

### 外移後檢查清單

- [ ] 新檔目標目錄符合決策樹結論（`docs/` vs `.claude/references/`）
- [ ] `CLAUDE.md` 引用路徑已更新（`@docs/<檔名>.md` 或 `@.claude/references/<檔名>.md`）
- [ ] 原檔案已刪除（外移而非複製）
- [ ] 若放 `.claude/references/`，內容已通過規則 8 自檢（無 `src/` 路徑、無產品名稱、無專案 ticket ID）
- [ ] 若放 `docs/`，已在新檔頂部說明「存放位置原因」（避免後續誤搬回 `.claude/`）
- [ ] 執行 `grep -rn "<新檔關鍵字>" .claude/ docs/` 確認無殘留舊路徑引用

### 範例對照

| 章節性質 | 外移目標 | 範例 |
|---------|---------|------|
| 專案錯誤處理體系（含 `src/core/errors/` 路徑） | `docs/project-conventions.md` | 含 `src/` 路徑與專案 enum 清單，屬步驟 1 命中 |
| Chrome Extension Manifest V3 通用限制 | `.claude/references/chrome-extension-quickref.md` | 通用限制速查表（require/global/Storage API），泛化後保留 |
| Flutter 專案的命名規範 + 通用 Dart 風格 | 拆檔：專案命名放 `docs/flutter-naming-conventions.md`、通用 Dart 風格放 `.claude/references/dart-style-quickref.md` | 混合內容拆檔範例 |

---

## 補充檢查清單（搭配 document-format-rules.md 主檢查清單使用）

編輯規格文件或 `.claude/` 框架檔案時，額外確認：

- [ ] 規格文件未引用 worklog/ticket/plan 等臨時性文件（規則 7）
- [ ] 框架文件（`.claude/`）未引用專案 ticket ID / commit hash / worklog 路徑（規則 8）
- [ ] 引用的來源屬於穩定類別（規格/提案/CLAUDE.md/框架檔案路徑/error-pattern 分類）
- [ ] 若需記錄歷史來源（如變更由某 ticket 執行），採「來源標注」模式而非依賴引用

---

## 相關文件

- `.claude/rules/core/document-format-rules.md` — 文件格式規則主檔（規則 1-6 + YAML frontmatter + 檢查清單骨架）
- `.claude/rules/README.md` — 規則系統導引
- `.claude/references/framework-asset-separation.md` — 框架資產與專案產物職責分離原則
- `.claude/error-patterns/documentation/DOC-010-framework-references-project-tickets.md` — 框架誤引用專案 ticket 的錯誤模式

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 從 document-format-rules.md 遷移規則 7、規則 8
