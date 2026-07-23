---
name: doc
description: "需求追蹤文件系統（proposals/spec/usecases）的查詢、建立、導航和管理。Use for: (1) 查詢提案、規格、用例文件, (2) 建立新提案/規格/用例（從模板）, (3) 跨文件導航（從 UC 找 spec/ticket）, (4) Domain 地圖查詢, (5) 追蹤索引管理, (6) UC 測試對應驗證, (7) 提案評估與審查, (8) 測試追溯矩陣查詢（UC↔測試覆蓋狀態）, (9) UC 編號治理（uc list 列合法 UC / uc verify 白名單驗證可掛 CI / uc trace 引用追溯 / uc context 派發 UC 定位）。Use when: user mentions PROP-, UC-, SPEC-, 功能, 需求, feature, issue, 提案, 用例, 規格, 需求文件, 需求追蹤, 測試覆蓋, 追溯, traceability, test-map, UC 編號, 編號驗證, uc verify, 偽 UC, 合法 UC 清單"
---

# Doc SKILL

需求追蹤文件系統 — 管理 proposals/spec/usecases 三種需求文件。

> 與 doc-flow（管理 CHANGELOG/worklog/ticket/todolist）互補，不重疊。

---

## 五種文件類型

| 類型 | 目錄 | 核心問題 | 詳細規範 |
|------|------|---------|---------|
| Proposal | `docs/proposals/` | 為什麼要做？做什麼不做什麼？ | Read `references/proposals.md` |
| Spec | `docs/spec/{domain}/` | 功能規格是什麼？ | Read `references/spec.md` |
| DomainMap | `docs/spec/{domain}/domain-map.md`（單 domain 退化 `docs/domain-map.md`） | domain bundle 邊界、依賴方向、層測試策略？（DDD 水平視角，正交 UC）| `templates/domain-map-template.md` |
| UseCase | `docs/usecases/` | 使用場景和驗收標準？ | Read `references/usecases.md` |
| Tracking | `docs/proposals-tracking.yaml` | 提案進度如何？ | Read `references/tracking.md` |

---

## 命令格式

```bash
/doc <subcommand> [options]
```

> **CLI 狀態**：已實作 Python CLI，使用 `doc <subcommand>` 執行。首次使用需安裝：`(cd .claude/skills/doc && uv tool install .)`

## 子命令

| 子命令 | 用途 | 範例 |
|--------|------|------|
| `query` | 查詢文件 | `/doc query PROP-001` 或 `/doc query UC-01` |
| `list` | 列出文件 | `/doc list proposals` 或 `/doc list specs` |
| `nav` | 跨文件導航 | `/doc nav UC-01` → 相關 spec/proposal/ticket |
| `domain` | Domain 地圖 | `/doc domain extraction` |
| `status` | 追蹤狀態 | `/doc status` |
| `test-map` | UC 測試對應 | `/doc test-map UC-01` |
| `batch-init` | 批量建置骨架 | `/doc batch-init --proposals PROP-007,PROP-008 --domain collector` |
| `uc list` | 列出合法 UC 編號+標題（SSOT 動態解析） | `/doc uc list` |
| `uc verify [path]` | 驗證路徑內 UC token 白名單合規（可掛 CI） | `/doc uc verify lib`（exit 0=pass / 1=violation） |
| `uc trace <UC-XX>` | 列出指定 UC 的 code 引用位置 | `/doc uc trace UC-01` |
| `uc context <UC-XX\|ticket-id>` | 輸出 UC 標題+spec 位置+code 引用 top-N，供派發 Context Bundle 引用 | `/doc uc context UC-01` 或 `/doc uc context <ticket-id>` |

---

> **uc 子命令群組**：UC 編號治理（格式規範、SSOT 解析、豁免範圍）定義於 `docs/spec/uc-numbering-convention.md`，四個 uc 子命令是該規範的唯一 CLI 實作；`uc-reference-validation-hook.py`（PreToolUse WARNING 層）已複用 `doc_system/core/uc_registry.py`——修改解析/豁免邏輯只改 uc_registry 單點，禁止在 hook 或其他消費端複製規則（防漂移）。

## 無子命令時的預設行為

1. 執行 `/doc status` 顯示追蹤索引摘要
2. 列出近期更新的文件

---

## 快速參考

### 文件關係圖

```
Proposal ──spec_refs──→ Spec
    │                      │
    │                 related_usecases
    │                      │
    └──usecase_refs──→ UseCase
    │                      │
    └──ticket_refs──→ Ticket（doc-flow 管理）

DomainMap ──source_specs──→ Spec
    │
    └──related_usecases──→ UseCase
    │
    └──不變式軸──→ Phase 2 測試設計（sage 消費）
    │
    └──依賴方向 DAG──→ Phase 0 一致性審查（saffron 消費）
```

> DomainMap 與 Spec/UC 正交：Spec 是功能需求（FR）的垂直切面，DomainMap 是 domain bundle 邊界的水平切面。方法論：`.claude/methodologies/domain-bundle-mapping-methodology.md`。

### Domain 列表

| Domain | 目錄 | 說明 |
|--------|------|------|
| core | `spec/core/` | 資料模型、錯誤處理、事件系統 |
| extraction | `spec/extraction/` | 資料提取 |
| platform | `spec/platform/` | 平台管理 |
| data-management | `spec/data-management/` | 儲存、匯出、同步 |
| messaging | `spec/messaging/` | 跨 context 通訊 |
| page | `spec/page/` | 頁面偵測 |
| system | `spec/system/` | 生命週期管理 |
| user-experience | `spec/user-experience/` | UI、搜尋 |

---

## 模板

模板是框架資產，放在 Skill 內。`docs/` 只放產物，不放模板。

| 模板 | 位置 | 用途 |
|------|------|------|
| 提案模板 | `templates/proposal-template.md` | 建立新提案 |
| 規格模板 | `templates/spec-template.md` | 建立新功能規格 |
| Domain Map 模板 | `templates/domain-map-template.md` | 建立 domain bundle 邊界地圖（DDD 水平視角） |
| Design System 規格模板 | `templates/design-system-spec-template.md` | 建立 UI 設計系統規格 |
| 用例模板 | `templates/usecase-template.md` | 建立新用例 |

### 使用方式

```bash
# 建立提案
cp .claude/skills/doc/templates/proposal-template.md docs/proposals/PROP-{NNN}-{desc}.md

# 建立功能規格
cp .claude/skills/doc/templates/spec-template.md docs/spec/{domain}/{name}.md

# 建立 Domain Map（多 domain 專案放 domain 子目錄；單 domain 專案放 docs/ 根層）
cp .claude/skills/doc/templates/domain-map-template.md docs/spec/{domain}/domain-map.md

# 建立 Design System 規格
cp .claude/skills/doc/templates/design-system-spec-template.md docs/spec/design-system-spec.md

# 建立用例
cp .claude/skills/doc/templates/usecase-template.md docs/usecases/UC-{XX}-{desc}.md
```

---

## 參考資料

| 資料 | 說明 |
|------|------|
| `references/proposals.md` | 提案文件規範、流程、範圍界定原則 |
| `references/spec.md` | 規格文件規範、Domain 組織、FR/NFR 格式 |
| `references/usecases.md` | 用例規範、UC 測試對應要求、資訊鏈驗證 |
| `references/tracking.md` | 追蹤索引格式、跨文件導航機制 |
| `references/proposal-evaluation-guide.md` | 提案評估指南（跨專案通用的三關式審查） |
| `references/legacy-code-workflow.md` | Legacy Code 接手處理標準化流程（前置 + 步驟 0~6） |

---

## 與現有系統的整合

### 與 saas-tech-selection 的銜接（需求上游）

saas-tech-selection skill 做完技術選型訪談後產出「決策記錄」，doc 是它的下游 — 把決策記錄長成 proposal / spec / usecase。偵測到 saas 決策記錄（`docs/tech-decisions.md` 或訪談產出）時，依下表接手：

| saas 決策記錄段落 | doc 文件 | 接手動作 |
|------|------|---------|
| 1 操作風險表（BDD） | usecase | 每個操作主體生成一個 UC：操作轉用例、主 / 失敗情境轉主 / 例外場景、風險 + 防護轉驗收 |
| 2 Domain Map | spec（domain 邊界） | 每個自建 domain 一份 spec：責任轉概述、command 轉 FR（與 3 雙源） |
| 2 介面契約段 | spec（資料模型 + 介面規格） | payload schema / 子協議 / 資料模型轉 spec 介面規格章節。介面具體細節（endpoint 路徑、參數、DDL）來源優先序見 `references/spec.md`「介面規格章節指引」 |
| 3 技術維度決策 | spec（FR / NFR）+ proposal（決策依據） | 需求判讀轉 FR、選型 / 防護轉 NFR + proposal 技術決策 |
| 0 定錨 + gate + 4-5 決策 | proposal | 範圍界定 + 決策依據 + 驗收，spec_refs / usecase_refs 指向上面生成的 |

**前置檢查**：1 操作風險表、2 Domain Map 任一為空 = saas 訪談沒走完 Stage 1 / 2，doc 無源可長 usecase / spec — 回頭請 saas 補完盤點，不可硬生半成品。

接手順序：proposal（綁範圍） -> spec（依 domain map） -> usecase（依操作表） -> 補雙向交叉引用 -> **CLAUDE.md 瘦身**。saas 側的移交規格見 saas skill 的 `references/decision-record-template.md`「銜接 doc 系統」節。doc 單獨使用（無 saas）時此 saas 接手表不觸發、照常從模板建立。

> **domain map 不因無 saas 而略過**（saas / standalone 調和）：saas 起手時 domain map 由 saas Stage 1/2 的 DDD 切分餵入產出端；非 saas 起手（提案 / handoff 起手）時，domain map 改由 version-bootstrap Step 2.5 從 `templates/domain-map-template.md` 新建。domain 規劃是所有規劃波的通用步驟，非 saas 專屬——上方「2 Domain Map -> spec」的 saas 接手不觸發，不等於 domain map 步驟被跳過。

**Spec→ticket 轉換與三方比對（需求文件完成後）**：需求文件（proposal + spec + usecase）完成後，進入 ticket 拆分前，必須執行三方交叉比對驗證——每個 Spec FR 至少被一個 ticket 覆蓋、每個 UC 場景有 ticket 對應、每項 Proposal 驗收條件有 ticket 對應。比對規範見 `references/spec.md`「Spec → Ticket 轉換指引」。

**CLAUDE.md 瘦身（移交最後一步）**：需求文件結構化落地到 docs/ 後，CLAUDE.md 中的完整技術規格（理由 / 防護 / tripwire 全文）替換為路由索引表——只留決策編號、維度、選型一行摘要 + 指向 `docs/tech-decisions.md` 的路徑。需求文件同理：只留文件類型 + 位置 + 一行說明的索引表，不在 CLAUDE.md 重述內容。移交是 CLAUDE.md 的代謝機制——規格搬進 docs/ 按需讀取，auto-load 的 CLAUDE.md 只保留路由，token 預算隨之下降。

### 與 doc-flow 的分工

| 系統 | 管理範圍 | 追蹤層級 |
|------|---------|---------|
| /doc | proposals, spec, usecases | 需求生命週期（提案 → 確認 → 實作） |
| doc-flow | CHANGELOG, worklog, ticket, todolist | 任務生命週期（建立 → 執行 → 完成） |

**協作觸發點**：

| 場景 | /doc 動作 | doc-flow 動作 |
|------|----------|--------------|
| 提案確認 | status → confirmed | 開立 ticket（/ticket create） |
| 提案確認且 target_version 未註冊 | `doc update` 輸出 target_version 未在 todolist.yaml 註冊的提醒（不阻擋） | 於 docs/todolist.yaml 補建版本條目（status: planned） |
| Ticket 完成 | 更新 tracking.yaml checklist | ticket 標記 complete |
| 提案評估 | 提案 draft → discussing 時，執行 `references/proposal-evaluation-guide.md` 三關式審查 | - |
| 所有 checklist 完成 | 提案 status → implemented | 版本 worklog 記錄 |

**提案確認的 target_version 源頭引導（0.38.0-W1-004）**：`doc update <PROP-ID> confirmed` 時，若提案 target_version 已設定但未在 `docs/todolist.yaml` 註冊（不論 status），輸出提醒指引使用者補建版本條目。判定標準與 `version-tracking-consistency-guard-hook`（session-start 事後偵測層）一致，形成三層防護模型的第 1 層（源頭引導）；target_version 為 null 時不提示（不同關注點）。

### 與 /spec Skill 的關係

| 項目 | /doc 管理的 spec | /spec Skill 產物 |
|------|-----------------|-----------------|
| 性質 | Domain 知識資產（持久） | Ticket 執行工件（臨時） |
| 位置 | `docs/spec/{domain}/` | Ticket 目錄下的 feature-spec |
| 用途 | 擴充/重構時審視 domain 設計 | TDD Phase 1 功能設計 |
| 轉化時機 | Ticket 完成後，設計成果沉澱為 domain spec | - |

### 設計決策備註

以下設計決策經過多次審查確認，記錄理由以避免重複覆議：

| 決策 | 理由 |
|------|------|
| tracking.yaml 保留 checklist | 需求生命週期（提案確認/撤回/變更）!= 任務生命週期（ticket 建立/完成）。提案可能在 ticket 完成後仍需變更 |
| CLI 保留 6 個子命令 | 查詢精確性是長期需求。文件數量增長後 grep 會產生大量不相關結果。nav 是核心功能無法用 grep 替代 |
| proposal-evaluation-guide 保持完整 | .claude/ 是跨專案通用框架。資安/UX/效能維度對其他專案類型完全適用 |
| proposal frontmatter 保持 12 欄位 | outputs.* 是跨文件導航的核心欄位，source/priority 是分類排程必要欄位。砍掉會讓 /doc nav 無法運作 |

> 完整審查歷史見 `references/review-notes.md`

### 審查記錄

審查歷史和修復記錄見 `references/review-notes.md`。

---

**Version**: 1.6.0 — domain map 升為 first-class 文件類型（四種→五種）：新增 DomainMap 列 + domain-map-template 模板 + 使用方式 cp 命令（W2-016.1）；saas 銜接節補「domain map 不因無 saas 而略過」調和說明——非 saas 起手由 version-bootstrap Step 2.5 從 domain-map-template 新建（W2-016.2）
**Version**: 1.5.0
**Last Updated**: 2026-07-22

---

## 修改 source 後必須重新安裝

> **重要**：本 skill 透過 `uv tool install` 安裝為獨立 CLI，source（本目錄）與 installed（`~/.local/share/uv/tools/<package>/`）是兩份獨立 Python package。修改 source 後若未 reinstall，CLI 仍使用 stale installed 版本，新增的函式會 AttributeError 或被 hasattr 包裝靜默吞掉（W11-037 根因）。

**修復指令**：

```bash
cd .claude/skills/<本 skill 目錄> && uv tool install . --force --reinstall
```

**自動偵測**：每次 SessionStart 由 `uv-tool-staleness-check-hook` 比對 source vs installed SHA256，偵測 stale 時提示修復指令。對應 ticket-skill 本身另有 `ticket-reinstall-hook` 自動 reinstall。
