# Agent Dispatch Template — 職責邊界聲明骨架

> **用途**：PM 派發代理人時，prompt 必含「職責邊界聲明」開場結構，讓代理人在執行前確認任務符合其定義的允許產出範圍，阻擋越界行為。
>
> **實證來源**：
> - W5-001 session（pepper / thyme-A / thyme-B）：派發 prompt 含職責邊界聲明，無越界案例
> - W5-001 sage 越界案例：派發 prompt 缺職責邊界聲明，sage 寫了禁止範圍的 .py 測試
>
> **設計依據**：quality-baseline 規則 6（失敗案例學習原則）— 從實證有效的派發模式固化為強制骨架。

---

## 骨架

派發 prompt 必含以下開場結構：

```
Ticket: {ticket_id}

## 職責邊界聲明

{agent-name} 的 agent 定義為「{agent-description 引文，來自 .claude/agents/{agent}.md frontmatter}」。

**允許的產出**:
- {列出本 ticket 範圍內允許的檔案/動作}

**禁止的產出**:
- {列出本 ticket 範圍外或代理人定義禁止的檔案/動作}

本 prompt 符合職責邊界，請繼續執行。

## 執行

{具體執行步驟、Ticket 指令、引用 Context Bundle}

## 禁止
- {與其他並行 Ticket 衝突的修改範圍}
- {本 Ticket 不應涉及的副作用}
```

---

## 填寫要點

| 欄位 | 內容要求 |
|------|---------|
| `{agent-name}` | 代理人名稱（如 `thyme-python-developer`） |
| `{agent-description 引文}` | 從 `.claude/agents/{agent}.md` frontmatter `description` 直接引用 |
| 允許的產出 | 對照代理人可編輯路徑表 + 本 Ticket `where.files` 交集 |
| 禁止的產出 | 並行 Ticket 範圍、代理人定義外的檔案類型、跨 Ticket 動作 |

---

## 適用範圍

| 場景 | 是否強制引用骨架 |
|------|----------------|
| 所有 TDD Phase 派發（Phase 1-4） | 強制 |
| 所有背景代理人派發（`run_in_background: true`） | 強制 |
| ANA / DOC / IMP 各類 Ticket 派發 | 強制 |
| 並行派發（多代理人同時） | 強制（尤其重要，範圍劃分清楚） |
| 探索類代理人（Explore、查詢類） | 選用（無寫入風險時可省略） |

---

## 為何不直接依賴代理人定義？

代理人 frontmatter 已定義職責，但實務證明僅靠代理人端檢查不足夠：

| 防護層 | 失效模式 |
|-------|---------|
| 代理人端 agent 定義 | 代理人可能為滿足 prompt 具體要求而越界 |
| Hook 預檢（branch-verify-hook） | 僅檢查路徑白名單，無法判斷 Ticket 範圍 |
| **Prompt 端職責邊界聲明** | **派發時即明示邊界，代理人執行前有自檢依據** |

三層防護並存，prompt 端聲明是派發時的最後防線。

---

## 相關文件

- `.claude/pm-rules/parallel-dispatch.md` — 引用本模板為強制骨架
- `.claude/pm-rules/decision-tree.md` — 代理人可編輯路徑對照表
- `.claude/rules/core/quality-baseline.md` — 規則 6 失敗案例學習原則

---

**Last Updated**: 2026-04-18
**Version**: 1.0.0 — 從 W5-009 方案 2 落地（Ticket 0.18.0-W5-044）
