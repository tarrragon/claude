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

**Last Updated**: 2026-04-18
**Version**: 1.0.0 — 從 W5-009 方案 1 落地（W5-043.1）
**Source**: W5-001 派發越界根因 A
