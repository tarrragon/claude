# PC-040: Context 存於 Prompt 而非 Ticket

## 錯誤症狀

PM 派發 agent 時，將大量 context（規格摘要、實作策略、檔案位置、程式碼範例）寫在 Agent prompt 中，而非存在 Ticket 文件裡。

典型症狀：
- Agent prompt 超過 200 行，包含完整規格摘要和實作策略
- Agent 失敗後重新派發，PM 需要重新手動組裝相同的 prompt
- 下一個 session 的 PM 看不到上次派發的 context

## 根因分析

**直接原因**：PM 為了讓 agent 「一次到位」，把所有研究成果直接寫進 prompt。

**深層原因**：缺乏「Ticket 作為 Context 載體」的流程引導。現有的 Context Bundle 規範（W2-021）定義了 agent 需要什麼 context，但沒有明確規定 context 應**存放在 Ticket 中**，而非 prompt 中。

**行為模式**：PM 在當前 session 有完整認知（讀過規格、看過原始碼），自然傾向把這些知識「傾倒」到 prompt。但這本質上是把 session-local 的知識寫到 ephemeral 的載體（prompt），而非 persistent 的載體（Ticket）。

## 影響

| 影響 | 說明 |
|------|------|
| Context 不可重用 | Agent 失敗後，prompt 中的 context 需要手動重組 |
| Context 不可追溯 | Session 結束後，prompt 內容消失，無法審查或改善 |
| 違反 Ticket 中心化 | W2-019/W2-020 設計的 Ticket 中心化工作流被繞過 |
| Agent 回合浪費 | 即使 prompt 含 context，agent 仍可能花回合 Read 驗證 |

## 正確做法

### Context 應存入 Ticket 的 How.strategy 和 Problem Analysis

| Context 類型 | 存放位置 | 範例 |
|-------------|---------|------|
| 規格摘要 | Ticket How.strategy | 「v2 JSON 根結構含 metadata/tagCategories/tags/books」 |
| 實作策略 | Ticket How.strategy | 「修改 exportToJSON 新增 v2 路徑，透過 options.formatVersion 控制」 |
| 關鍵檔案和行號 | Ticket Where.files | 「src/export/book-data-exporter.js:269（exportToJSON 方法）」 |
| 現有程式碼狀態 | Ticket Problem Analysis | 「現有 exportToJSON 無 v2 結構，FIELDS.V2 常數已存在（L59-67）」|
| 程式碼範例 | Ticket Solution（預填） | 完整的實作程式碼或虛擬碼 |

### Agent Prompt 只需包含

```
Ticket ID: 0.17.2-W2-006.1
請 Read Ticket 文件取得完整 context 和實作策略。
驗收條件見 Ticket acceptance 欄位。
完成後更新 Ticket execution log。
```

### 流程修正

1. PM 研究完成後，把發現寫入 Ticket（How.strategy + Problem Analysis）
2. Ticket 的 Solution 區段可預填實作策略或虛擬碼
3. Agent prompt 只引用 Ticket ID，agent 自行讀取 Ticket
4. Agent 失敗後，Ticket 中的 context 仍在，重新派發零成本

## 預防措施

| 措施 | 類型 | 說明 |
|------|------|------|
| 修改 Context Bundle 規範 | 規則更新 | 明確規定 context 存 Ticket 不存 prompt |
| 修改派發指南 | 規則更新 | Agent prompt 模板只含 Ticket ID 引用 |
| PreToolUse Agent Hook | 自動化 | 偵測 prompt 超過 N 行時警告 |

## 發現來源

- Ticket: 0.17.2-W2-006.1 執行過程
- 場景：PM 把完整規格摘要和實作策略寫在 Agent prompt（超過 100 行），agent 仍用完回合在 Read 上，未產出任何程式碼變更
- 日期：2026-04-06

## 相關錯誤模式

- PC-034: workflow output 未持久化
- IMP-047: Subagent 實作需提供完整程式碼（此模式的前身，方向正確但載體錯誤）

---

**Created**: 2026-04-06
**Version**: 1.0.0
