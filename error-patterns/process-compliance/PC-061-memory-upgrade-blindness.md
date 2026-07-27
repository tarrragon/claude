# PC-061: Memory 寫入後未評估升級為框架規則

## 現況說明（2026-07-27 起）

`.claude/` 已改採 hook 層執法（`memory-write-guard-hook.py`，PreToolUse deny）取代規則層自律期望——寫入 memory 目錄的操作在寫入**當下**即被攔截並改道分流，不再是本檔原描述的「先寫入、事後評估升級」模式。下方「錯誤症狀 / 根因分析 / 實際案例」記錄的是舊機制下的失敗模式，保留作為 hook 層執法設計依據的歷史記錄；「防護措施 / 自我檢查清單」已更新為現行機制，見該二節。

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

## 防護措施（現行機制）

原措施 1-5（規則層期望 PM 自律升級、PostToolUse 事後提醒 hook、回填「已升級」標註）已由下列兩層取代：

### 規則層：知識捕獲時分流

`.claude/pm-rules/pm-quality-baseline.md` 規則 7「知識捕獲時分流」——記錄經驗教訓前，先依判別問句「另一個專案的 session 讀到這段，能用嗎」分流至三個目的地之一：

| 學習成果性質 | 目的地 |
|------------|--------|
| 框架相關（替換專案名稱與路徑後仍成立） | `.claude/error-patterns/` 或 `rules/` `methodologies/` `references/`（依內容性質細分） |
| 專案相關（僅本專案成立） | `docs/` 或 `CLAUDE.md` |
| 兩者皆非（僅本次 session 成立） | 不記錄，ticket md 已承載執行脈絡 |

memory 不在三個目的地內；三分流已窮盡所有情境，不留「先寫 memory 保底」的第四選項。

### 執法層：寫入攔截

`.claude/hooks/memory-write-guard-hook.py`（PreToolUse deny，取代已刪除的 `memory-upgrade-reminder-hook.py`）在寫入 memory 目錄的**當下**即攔截，deny 訊息直接引導至上述三分流判準，而非等寫入發生後才事後提醒。此設計呼應成因 1（認知摩擦差）——規則層的自律期望對抗不了低摩擦路徑的傾向，須由 hook 層在寫入當下攔截才有效。

## 自我檢查清單

準備記錄經驗教訓時，依序自問（完整判準見 `pm-quality-baseline.md` 規則 7）：

- [ ] 這段內容替換專案名稱與檔案路徑後，另一個專案的 session 讀到還能用嗎？（能 → 框架相關，進入下一問；否則進專案相關）
- [ ] 屬框架相關時，這是通用品質原則 / PM 行為規範 / 錯誤學習 / 流程方法論 / Skill 引導的哪一類？依此選定升級目的地
- [ ] 屬專案相關時，落 `docs/` 或 `CLAUDE.md`
- [ ] 兩者皆非、僅本次 session 成立？→ 不記錄

任一步驟拿不定，不代表可退回「先寫 memory」——代表資訊尚不成熟，留在 ticket 執行紀錄內待同主題再現時累積判斷。

## 關聯

- **相關規則**：`.claude/pm-rules/pm-quality-baseline.md` 規則 7「知識捕獲時分流」（現行機制，memory 排除，三分流取代原「Memory 寫入必須評估跨專案升級」）
- **相關模式**：PC-010（待辦應建 Ticket 不寫 memory，聚焦任務追蹤；本模式聚焦原則類 memory）
- **相關模式**：PC-060（Meta-tool 發現盲點，同類「原則建立當下未擴充檢查清單」結構）
- **相關模式**：[PC-160](PC-160-pm-skip-upgrade-gate-direct-memory-write.md)（本 PC 的 v2 實證案例 + session 內浮現洞察情境的補充案例；兩者記錄同一錯誤模式的不同切片，cross-reference 而非合併）
- **相關 Skill**：`.claude/skills/continuous-learning/`（知識捕獲時分流已內建於 skill 流程，memory 不再列為目的地）
- **相關 Hook**：`.claude/hooks/memory-write-guard-hook.py`（PreToolUse deny，取代已刪除的 `memory-upgrade-reminder-hook.py`）
- **相關方法論**：[`.claude/methodologies/hook-system-methodology.md`](../../methodologies/hook-system-methodology.md) § 6「觀察類工具的雙重身份設計」

### v2 案例延伸（PC-160）

PC-160 補充 PC-061 未涵蓋的情境差異：本 PC 案例 1-2 聚焦「原則類 memory 識別正確但升級延遲」，PC-160 聚焦「session 內浮現洞察的第一動作即跳過評估閘門直接寫 memory」。W3-058 ANA 評估結論：兩者為同一錯誤模式的不同切片，PC-160 保留為 PC-061 v2 實證案例 + session 浮現洞察的 specific 五步驟防護，不合併以避免更新 PC-061 既有多處引用點。

---

**Created**: 2026-04-13
**Last Updated**: 2026-07-27（防護章節與自我檢查清單改寫：memory 已從合法目的地排除，規則層改為知識捕獲時三分流、執法層改為 PreToolUse 寫入攔截；症狀/根因/案例章節保留為 hook 層執法設計依據的歷史記錄）
**Category**: process-compliance
**Severity**: P2（跨專案原則流失累積成本高，但非立即錯誤；與 PC-060 同結構）
**Key Lesson**: Memory 是專案層級儲存，不是跨 session 知識庫，本框架已排除其作為知識目的地。歷史教訓（規則層自律期望對抗不了低摩擦路徑）是現行 hook 層執法設計的直接依據；跨專案原則一律直接落 `.claude/` 框架層，不經 memory 中繼。
