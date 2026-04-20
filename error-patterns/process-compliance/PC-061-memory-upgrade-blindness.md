# PC-061: Memory 寫入後未評估升級為框架規則

## 錯誤症狀

PM 在 session 中發現重要原則時，反覆出現以下模式：

1. 將原則以 `feedback_*.md` 形式寫入 auto-memory（`~/.claude/projects/<project>/memory/`）
2. 未評估此原則是否**跨專案適用**
3. 未升級到 `.claude/` 框架層（rules / pm-rules / references / methodologies / error-patterns / skills）
4. 原則停留在專案層級 memory，其他專案 sync `.claude/` 後**無法繼承此原則**
5. 其他專案重複踩同樣的雷，PM 才在事後意識到「這條原則本應該升級」

## 根因分析

### 成因 1：認知摩擦差（Friction Imbalance）

| 動作 | 步驟數 | 心智負擔 |
|------|-------|---------|
| 寫入 memory | 1（Write 單一檔案 + 更新 MEMORY.md 索引） | 低 |
| 升級為框架規則 | 5+（判斷跨專案性 → 找 rules/methodologies 位置 → 寫內容 → 更新索引 → 回填 memory 標記「已升級」） | 高 |

PM 在 session 高壓下選擇低摩擦路徑（先寫 memory 保留資訊），但「之後再升級」的第二步永遠沒到。

### 成因 2：邊界判斷缺失（Scope Misjudgment）

Memory 和 Ticket **都是專案層級儲存**，但 PM 的心智模型誤將 memory 視為「跨 session 持久層」而非「專案層級儲存」。寫 memory 當下未評估「此原則是否跨專案適用」，預設行為變成「先寫 memory」→ 等用戶指正才升級。

### 成因 3：工具提示偏向（Tool Guidance Bias）

| 提示來源 | 偏向 |
|---------|------|
| CLAUDE.md auto-memory 章節 | 詳述「如何寫」，未述「何時升級」 |
| continuous-learning skill | 聚焦「捕獲」，未強制「升級路徑」 |
| Memory tool description | 鼓勵多寫，未提示「跨專案原則應寫到框架」 |

工具設計潛在假設是「寫 memory 是終點」，而非「寫 memory 是評估起點」。

### 成因 4：依賴用戶介入作為唯一校正機制（Reliance on User Correction）

Memory 升級案例中，相當比例是「用戶指正後 PM 才升級」。PM 自身**無主動 memory audit 流程**，依賴用戶巡檢，失敗率顯著。

## 實際案例

### 案例 1：「框架不引用專案 ticket」原則升級延遲

**背景**：PM 在某次 session 識別出「.claude/ 框架文件禁止引用專案特定 ticket ID / commit hash / worklog 路徑」的原則。

**錯誤路徑**：
1. PM 將此原則寫入 feedback memory
2. 未即時升級為 `.claude/references/reference-stability-rules.md` 規則
3. 經用戶指正 memory 不會跨專案 sync，才補上規則 8 與 DOC-010 error-pattern

**代價**：在升級發生前，新專案若 sync `.claude/` 後無法繼承此原則，框架文件內的專案識別符可能繼續被寫入。

### 案例 2：memory 盤點中的升級缺失

某次盤點（W9-003）對 13 個 feedback/project memory 進行跨專案性檢視，發現約 38%（5/13）屬於「跨專案適用但僅存 memory 未升級」：

| 主題 | 跨專案性 | 應升級位置（示意） |
|------|---------|-----------------|
| 框架/產物分離 | 高 | `references/framework-asset-separation.md` 或新 `rules/core/*.md` |
| /clear 前必須持久化 | 高 | `pm-rules/session-switching-sop.md` 或 `skills/strategic-compact/` |
| Ticket 引導優先於 Hook | 高 | `methodologies/ticket-lifecycle-management-methodology.md` |
| 核心修改前先搜社群 | 高 | `pm-rules/incident-response.md` |
| worktree 代理人 scope | 高 | `pm-rules/agent-failure-sop.md` 重試守則 |

這些 memory 的共同特徵：原則識別正確、寫入即時，但**後續升級步驟未發生**。

## 防護措施

### 措施 1：quality-baseline 新增規則 7

新增 `.claude/rules/core/quality-baseline.md` 規則 7「Memory 寫入必須評估跨專案升級」：

- 定義四問檢查（跨專案適用？屬於哪類原則？應升級至哪個位置？）
- 明確升級目的地對照表（rules / pm-rules / error-patterns / methodologies / skills）
- 禁止「之後再升級」的延後理由
- 納入品質檢查清單與底線要求總結

### 措施 2：continuous-learning skill 升級評估決策樹

`.claude/skills/continuous-learning/` 新增升級評估步驟（由後續 ticket 實施）：

- Step「儲存到 memory」後強制 Step「升級評估」
- 提供升級決策樹 references，引導至對應框架位置
- 降低升級摩擦，讓評估成為 skill 流程內建環節

### 措施 3：自動提示 Hook

`.claude/hooks/` 新增 `memory-upgrade-reminder-hook.py`（由後續 ticket 實施）：

- 觸發：PostToolUse:Write，偵測 `feedback_*.md` 新增或修改
- 輸出：stderr 提示（符合觀測性規則 4）列出四問檢查 + 升級目的地選項
- 節流：同檔案 30 分鐘內只提示一次

### 措施 4：歷史債務清理

一次性升級既有僅存 memory 的跨專案原則案例（由後續 ticket 執行），並在 memory 檔案頂部註明升級目的地路徑。

### 措施 5：升級後回填

升級完成後必須在原 memory 檔案頂部註明：

```markdown
---
已升級: <框架路徑>
升級日期: <YYYY-MM-DD>
---
```

保留 memory 作為本專案的 context 索引，但顯式標示「原則已落地框架」。

## 自我檢查清單

寫入 feedback memory 時，依序自問：

- [ ] 這個原則對**其他專案**也適用嗎？（若否，加 `project_` 前綴明示）
- [ ] 這個原則屬於哪類？（通用品質 / PM 行為 / 錯誤學習 / 流程方法論 / Skill 引導）
- [ ] 對應的框架升級位置是什麼？
- [ ] 我是否已在當前 session 完成升級，而非留給「下次」？
- [ ] 升級完成後，原 memory 是否已回填「已升級」標註？

任一答「否」都不可結案，必須補完後才能視為「原則已落地」。

## 關聯

- **相關規則**：`.claude/pm-rules/pm-quality-baseline.md` 規則 7（Memory 寫入必須評估跨專案升級，原 quality-baseline v1.9.0 規則 7，2026-04-16 外移）
- **相關模式**：PC-010（待辦應建 Ticket 不寫 memory，聚焦任務追蹤；本模式聚焦原則類 memory）
- **相關模式**：PC-060（Meta-tool 發現盲點，同類「原則建立當下未擴充檢查清單」結構）
- **相關 Skill**：`.claude/skills/continuous-learning/`（後續新增升級評估決策樹）
- **相關 Hook**：`memory-upgrade-reminder-hook.py`（後續新增自動提示）

---

**Created**: 2026-04-13
**Last Updated**: 2026-04-13
**Category**: process-compliance
**Severity**: P2（跨專案原則流失累積成本高，但非立即錯誤；與 PC-060 同結構）
**Key Lesson**: Memory 是專案層級儲存，不是跨 session 知識庫。寫 feedback memory 不是知識管理的終點，而是評估升級的起點；跨專案原則必須同步升級到 `.claude/` 框架層才算落地。
