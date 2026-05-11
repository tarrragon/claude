# Handoff 純指針設計原則

本方法論定義 handoff 機制的核心設計原則：handoff 是**純指針（pure pointer）**，承擔「下 session 該對焦哪個 ticket」的指向責任，禁止重複 ticket md 已承擔的任務內容。

---

## 核心原則

handoff = 純指針 + 必要 metadata。內容明示如下：

| 必含 | 禁含 |
|------|------|
| `target_ticket_id`（絕對指向，W17-164） | 任務描述 / what / 動詞 + 受詞 |
| `from_ticket` + `direction`（相對指向，W17-162） | acceptance criteria |
| `created_at`（建立時間） | 5W1H 任一欄位（who/what/when/where/why/how） |
| `source_ticket`（任務鏈來源 ticket，可選） | 實作策略 / Solution 草稿 |
| `auto_generated`（旗標，True/False） | Problem Analysis |

**Why**：handoff 與 ticket md 是兩個獨立的儲存單位，職責切分明確：

- ticket md = 任務細節權威（5W1H / acceptance / Solution / Test Results）
- handoff = 跨 session 對焦指針（讓下 session 一秒知道「該做哪個」）

若 handoff 重複承載任務細節，會出現雙重來源（dual source of truth）：handoff 與 ticket md 隨開發推進產生漂移，後人不知該信哪邊。

**Consequence**：違反原則會讓 handoff 從「指針」退化為「迷你 ticket」，導致：

1. handoff 內容過時（ticket md 更新但 handoff 不變）
2. 下 session 接手者讀 handoff 後不需再讀 ticket md，錯過最新狀態
3. 多個 handoff 累積後形成「ticket md 之外的平行任務追蹤系統」，違反五重文件系統 SSOT

**Action**：

| 場景 | 應做 |
|------|------|
| 寫新 handoff | 只填上方「必含」欄位；若想補充，把內容寫入對應 ticket md 的 Problem Analysis / Solution / Context Bundle |
| 讀 handoff | 取得 `target_ticket_id` 後立即 `ticket track full <id>` 讀完整 ticket md，handoff 不取代 ticket md |
| 審查 handoff | 檢查 JSON 內是否含禁含欄位；發現即移到 ticket md，handoff 只保留指針 |

---

## Schema 落地（W17-164 機制連結）

W17-164 引入的 `target_ticket_id` 欄位是本原則的 schema 表達：

| 機制元素 | 原則對應 |
|---------|---------|
| `target_ticket_id` 欄位（絕對指向） | 「指針」概念的具體欄位化 |
| `--next <target-ticket-id>` CLI | 顯式指向，禁止間接推導 |
| `resolve_target(record)` 優先序 | target > direction fallback，本質是「指針」優於「相對方位」 |
| `direction="context-refresh"` 固定 | direction 退為描述符，不再承擔指向責任 |

**詮釋**：W17-164 之前 handoff 用 `from_ticket + direction` 間接表達指向（如 `direction=to-child:X`），讀取端需從 direction 後綴解析；W17-164 後新生 handoff 統一以 `target_ticket_id` 直接寫入，舊 JSON 由 fallback 路徑相容讀取。schema 演進的內在動機，正是本方法論定義的「純指針」原則。

---

## 與 ticket md 職責切分

| 內容類型 | 落點 | 載體 |
|---------|------|------|
| 任務動詞 + 受詞（what） | ticket md frontmatter `what` | YAML 欄位 |
| 完成定義 | ticket md `acceptance` | YAML list |
| 解決方案策略 | ticket md `## Solution` | Markdown 章節 |
| 跨 ticket 脈絡 | ticket md `## Context Bundle` | Markdown 章節（auto-extracted） |
| **下 session 該做哪個 ticket** | **handoff JSON `target_ticket_id`** | **JSON 欄位** |
| **任務鏈方向（父子兄弟）** | **handoff JSON `direction`** | **JSON 欄位** |

切分原則：handoff 只回答「指向哪個 ticket」，所有「該 ticket 是什麼」的細節由 ticket md 承擔。

---

## 違反案例

### 案例 1：W17-162 ANA 觀察的設計偏離

W17-162 ANA `why` 欄位記載：

> 設計初衷：handoff = 對焦指針讓下 session 快速指向「該執行的 ticket」（target），任務細節在 ticket md。
> 實際運作：handoff JSON 以「剛完成 ticket（source）+ 相對方向 direction」為主，缺絕對 target 指向。
> 具體偏離：completed ticket 不應被 handoff 指定卻仍出現在 SessionStart「待恢復任務」提示；W10-047.4 案例 direction=to-source 但 sources_declared=0 變孤兒 JSON。

**偏離本質**：缺乏顯式「指針」欄位，導致讀取端反向從 source + direction 推導，schema 一致性 bug 連環（W17-161 / W10-047.4）。W17-164 引入 `target_ticket_id` 是 schema 修補，本方法論是原則層說明「為何要修」。

### 案例 2：本 session（2026-05-09）PM 收尾選項違反

W17-175 ticket why 記載：

> 本 session 收尾時 PM 自己寫「handoff JSON 記錄 W17-174 為下 session 首選接手項」違反此原則被用戶察覺。

**違反本質**：PM 在向用戶提議 handoff 時，於 AskUserQuestion 選項描述中放入「W17-174 為下 session 首選接手項」這種任務優先級判斷——優先級判斷屬 scheduler / runqueue 職責（priority 排序），不屬 handoff 內容。handoff 只該寫「指向 W17-174」，不該寫「為什麼指向它」。

**修正方向**：PM 寫 handoff 時，自問「這句話是指針還是任務說明？」若是後者，移到 ticket md 對應章節；handoff 只留純指針 + 必要 metadata。

---

## 自檢清單

寫 handoff 前自問：

- [ ] 我寫的內容能用 `target_ticket_id` 一個欄位表達嗎？若不能，多餘部分是否應移到 ticket md？
- [ ] 我寫的內容含「為什麼指向這個 ticket」（理由）嗎？理由屬 ticket md why 或 source_ticket 鏈，不屬 handoff
- [ ] 我寫的內容含「這個 ticket 該怎麼做」（策略）嗎？策略屬 ticket md Solution，不屬 handoff
- [ ] 我寫的內容含 acceptance / 5W1H 任一欄位的草稿嗎？草稿屬 ticket md frontmatter，不屬 handoff
- [ ] handoff JSON 是否只含上方「必含」欄位？多餘欄位是否有正當理由？

---

## 相關文件

- `.claude/skills/ticket/references/handoff-command.md` — handoff CLI 機制層說明（W17-164 落地細節）
- `.claude/skills/ticket/SKILL.md`「handoff - 任務鏈管理與 Context 交接」章節 — 命令層使用指引
- `.claude/methodologies/atomic-ticket-methodology.md`「任務鏈核心哲學」章節 — handoff 在任務鏈中的位置
- `.claude/rules/core/document-format-rules.md` — handoff JSON 格式規範（檔案命名、frontmatter）

---

**Last Updated**: 2026-05-10
**Version**: 1.0.0 — 從 W17-175 落地（升級 W17-162 ANA why 內文 + W17-164 schema 落地的原則層說明），與機制層（references）+ 命令層（SKILL）形成三層分離：原則層回答「為何如此設計」、機制層回答「schema 如何表達」、命令層回答「如何使用」。

**Source**: W17-162 ANA why 欄位（設計初衷觀察）+ W17-164 target_ticket_id schema 落地（機制實證）+ W17-175 升級需求（PM 反覆違反原則案例）
