# Agent Definition 結構標準

本文件規範 `.claude/agents/*.md` 的主文（YAML frontmatter 之後）必須具備的結構，使 PM 派發前可查表確認職責邊界，並為 Hook 解析職責提供穩定錨點。

> **背景**：W5-001 Phase 2 派發 sage 越界事件根因 A——agent 職責邊界模糊，外部派發者難以在 prompt 之外推論 agent 可做/不可做的範圍。標準化結構讓「可做」「不可做」「何時派發」三件事顯性化。

---

## 適用範圍

| 對象 | 是否需符合本標準 |
|------|----------------|
| `.claude/agents/*.md`（實質 agent） | 是 |
| 元文件（如 `AGENT_PRELOAD.md`） | 否（豁免） |
| 已 DEPRECATED 的 agent | 否（須在檔案開頭明示 `DEPRECATED` 標記與重定向目標） |

---

## 強制區塊

每個實質 agent 的主文必須包含以下三個區塊（標題層級為 `##`）：

### 區塊 1：允許產出

明列此 agent 可產生的產出類型。

| 必含元素 | 說明 |
|---------|------|
| 檔案類別 | 例如 `.py` / `.md` / `tests/` 下測試檔 |
| 操作類型 | 例如 Edit / Write / 執行測試 / 產出分析報告 |
| 路徑範圍 | 與 frontmatter 的 Tools / permissions 對應 |

### 區塊 2：禁止行為

明列此 agent 不可做的事。

| 必含元素 | 說明 |
|---------|------|
| 禁止檔案類別 | 例如「禁止修改 `src/` 下產品程式碼」 |
| 禁止操作類型 | 例如「禁止 git commit」「禁止跨 ticket 範圍編輯」 |
| 禁止職責越界 | 例如「禁止替代 PM 進行派發決策」 |

### 區塊 3：適用情境

明列何時應派發此 agent。

| 必含元素 | 說明 |
|---------|------|
| TDD Phase 標註 | Phase 0 / 1 / 2 / 3a / 3b / 4 之一或多個；獨立任務類型可標 N/A |
| 觸發條件 | 描述任務特徵（如「測試紅燈時」「需要多視角分析時」） |
| 排除情境 | 何時不該派發此 agent，建議改派發誰 |

---

## 豁免類別

以下檔案不需符合本標準：

| 類別 | 範例 | 說明 |
|------|------|------|
| 元文件 | `AGENT_PRELOAD.md` | 共享 preamble，非 agent 定義 |
| 已 DEPRECATED | `john-carmack.md`、`memory-network-builder.md` | 須在檔案開頭明示 DEPRECATED 與重定向目標 |
| 範本 | `language-agent-template.md` | 範本檔（如有），用途為新 agent 樣板 |

---

## 驗證方式

```bash
# 確認某 agent 含三區塊
grep -E "^## (允許產出|禁止行為|適用情境)" .claude/agents/<agent>.md | wc -l
# 預期輸出：3
```

---

## 與 frontmatter 的關係

| 欄位 | 用途 | 與三區塊關係 |
|------|------|------------|
| `description` | 一句話說明 agent 用途 | 區塊 3「適用情境」的精簡版 |
| `tools` / Tools | runtime 可用工具清單 | 區塊 1「允許產出」的能力上界 |
| `permissionMode` | runtime 寫入權限 | 區塊 1/2 的執行邊界 |

**重要**：本標準只規範主文區塊，不修改 frontmatter。frontmatter 的 description 應保持原樣，三區塊在主文補充細節。

---

## 執行責任：Ticket body 填寫

實作類 agent（thyme-python-developer / parsley-flutter-developer / fennel-go-developer 及其他執行代理人）完成任務前必須依 ticket type schema 填寫 body 章節。**Why**: Hook 擋是安全網，agent 主動填才是主責；agent 定義若不寫入此責任，agent 不會自律。**Consequence**: body 空白或佔位符未替換會造成後人（審查者、後續承接者）無法理解任務脈絡，ticket 失去歷史價值。**Action**: 本章節必須在實作類 agent 的區塊 1「允許產出」或 agent 通用責任段落中引用。

### 必填章節（依 ticket type）

| Type | 必填章節 |
|------|---------|
| IMP | Problem Analysis / Solution / Test Results |
| ANA | Problem Analysis / Analysis Result |
| DOC | Solution（文件變更摘要） |

> 具體章節清單以 type-aware body schema（W17-016.2）為權威來源。

### 填寫時機

| 時機 | 對應章節 |
|------|---------|
| claim 後 | Problem Analysis（ticket md 若為空需補完） |
| 實作中 | Solution（遞增式 append-log） |
| complete 前 | Test Results（含測試指令與摘要輸出） |

### 填寫方式

使用 `ticket track append-log <id> --section "<章節名>"` 搭配 heredoc 傳長文字（參考 `.claude/rules/core/bash-tool-usage-rules.md` 規則五）。

**禁止行為**：

| 反模式 | 原因 |
|-------|------|
| 佔位符「（待填寫：...）」未替換就 complete | 等同空白 body |
| 以「見 commit message」「略」「同上」迴避填寫 | ticket body 與 commit 各自承擔不同讀者 |
| 寫 `/tmp/*.md` 作 CLI 中介（PC-087） | heredoc 容量足夠，無需繞路 |
| 寫自定義 H2（`## 實作摘要` / `## 驗證指令與結果` 等非 Schema 章節） | 自定義 H2 會切斷 Schema section 擷取範圍，與 PC-110 false negative 共振造成空殼 ticket 漏擋 |

### 章節結構規則（W17-072）

**Why**：PC-110 事件暴露 agent 寫自定義 H2（`## 實作摘要` / `## 驗證指令與結果`）繞過 Schema section，與 validator 漏判分隔符共振導致空殼 complete 放行。W17-071 已修 validator 側，本條款堵住源頭（agent 行為層）。

**Consequence**：違反此條款會讓 ticket body 被切斷成多個 H2 章節，後人審查時難以定位 Schema 章節邊界，且各語言 CLI 工具（如 `ticket track validate`）的 section 擷取邏輯會失準。

**Action**：

| 規則 | 允許 | 禁止 |
|------|------|------|
| H2 章節（`## 標題`） | 僅使用 Schema 定義章節名（Problem Analysis / Solution / Test Results / Context Bundle 等） | 自創 H2 標題（`## 實作摘要` / `## 驗證指令與結果` / `## 修復摘要` 等） |
| H3 子章節（`### 標題`） | 在 Schema 章節內自由組織（例：`## Solution` 下可用 `### 修復摘要` / `### 設計決策` / `### 不在本 ticket 範圍`） | — |
| 更深層標題（`#### / #####`） | 按需使用 | — |

**Schema 章節清單**（來源 `.claude/pm-rules/ticket-body-schema.md`）：`Task Summary` / `Problem Analysis` / `重現實驗結果` / `Solution` / `Test Results` / `Context Bundle` / `NeedsContext` / `Exit Status` / `Completion Info`

### 違規偵測

| 違規類型 | 偵測時機 | 行為 |
|---------|---------|------|
| 必填 Schema 章節缺失或佔位符未替換 | complete 前 | 阻擋 complete（`--force` / `--skip-body-check` 可豁免，使用會被追蹤） |
| 自定義 H2 章節（W17-072） | complete 前 | 輸出 warning（不阻擋，提示 agent / PM 修正） |

### 不適用範圍

| 類別 | 說明 |
|------|------|
| 純分析型 agent（如 bay-quality-auditor、saffron-system-analyst） | 產出即 body 內容，由 PM 派發時明確指示寫入章節 |
| DEPRECATED agent | 豁免 |
| ANA 類 ticket 的子任務分派者 | 本體職責已明確，不加此段 |

---

**Last Updated**: 2026-04-24
**Version**: 1.2.0 — 新增「章節結構規則」：禁止自定義 H2，實作內容必須寫在 Schema 章節下可用 H3 子章節組織；違規偵測表分層（阻擋 vs 警告）
**Version**: 1.1.0 — 新增「執行責任：Ticket body 填寫」章節，明示實作類 agent 的 body 填寫時機、方式、違規偵測
**Source**: W5-001 派發越界根因 A + body 空白系統性缺口 + PC-110 根因 B（agent 自定義 H2 切斷 Schema section）
