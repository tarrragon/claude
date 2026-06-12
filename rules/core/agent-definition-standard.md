# Agent Definition 結構標準（速查 stub）

> **完整規則**：`.claude/references/agent-definition-standard-details.md`（按需讀取，含各區塊必含元素細節、跨 ticket 物件操作禁令論證、執行責任兩大章、違規偵測表）。本檔僅保留三區塊速查與驗證指令。

`.claude/agents/*.md` 的主文（YAML frontmatter 之後）必須具備固定結構，使 PM 派發前可查表確認職責邊界，並為 Hook 解析職責提供穩定錨點。

> **背景**：W5-001 Phase 2 派發 sage 越界事件根因 A——agent 職責邊界模糊。標準化結構讓「可做」「不可做」「何時派發」三件事顯性化。

## 三強制區塊

每個實質 agent 主文必須含以下三個 `##` 層級區塊：

| 區塊 | 內容 | 必含元素 |
|------|------|---------|
| 允許產出 | agent 可產生的產出類型 | 檔案類別 / 操作類型 / 路徑範圍 |
| 禁止行為 | agent 不可做的事 | 禁止檔案類別 / 禁止操作 / 禁止職責越界 / 禁止跨 ticket 物件操作 |
| 適用情境 | 何時應派發此 agent | TDD Phase 標註 / 觸發條件 / 排除情境 |

> 跨 ticket 物件操作禁令：subagent 不得對非派發範圍 ticket 執行 `close` / `set-status` / 編輯他人 ticket md（即使發現衝突），應透過審查報告上報 PM。完整論證見 references 詳細版。

## 豁免類別

| 類別 | 範例 |
|------|------|
| 元文件 | `AGENT_PRELOAD.md` |
| 已 DEPRECATED | `john-carmack.md`（須開頭明示 DEPRECATED + 重定向目標） |
| 範本 | `language-agent-template.md` |

## 驗證方式

```bash
grep -E "^## (允許產出|禁止行為|適用情境)" .claude/agents/<agent>.md | wc -l
# 預期輸出：3
```

## 何時讀完整規則

| 情境 | 必讀章節（references 詳細版） |
|------|------------------------------|
| 撰寫/審查 agent 三區塊的必含元素 | 強制區塊各區塊明細 |
| 判斷內容該不該裝（偏好 / 知識庫 vs 流程 / 案例全文） | `.claude/methodologies/knowledge-carrier-allocation-methodology.md`「代理人定義內容規範」節 |
| 釐清跨 ticket close 禁令依據 | 區塊 2 跨 ticket 物件操作禁令論證 |
| 實作類 agent 的 ticket body 填寫責任 | 執行責任：Ticket body 填寫（必填章節 / 時機 / 章節結構規則 W17-072） |
| 實作類 agent 的 ticket 收尾責任 | 執行責任：Ticket 完成（收尾步驟 / 安全網 / 違規偵測） |

---

**Last Updated**: 2026-06-12 | **Version**: 1.6.0 — 觸發表補內容規範路由（結構權威與內容權威互通，W8 multi-round-review R3）。**Version**: 1.5.0 — 主文 substance 外移至 `.claude/references/agent-definition-standard-details.md`，本檔保留速查 stub（W7-004.2）。**Source**: W5-001 派發越界根因 A + PC-110 + W17-033。
