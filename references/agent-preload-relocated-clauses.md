# AGENT_PRELOAD 已重分配條款的完整 substance

本檔承接 `.claude/agents/AGENT_PRELOAD.md` 中已重分配至各 agent 定義檔的條款正文。

> **為何分開存放**：條款寫入 agent 定義檔時經過壓縮——定義檔只放可執行的 Action 與一句 Why，完整的判準表、範例與邊界說明留在本檔按需讀取。若不分開，定義檔會因逐字貼入而膨脹（最小者將翻倍）。
>
> **載體歸屬**：見 `.claude/references/agent-rule-carrier-map.md`。

---

## 條款 5：實作代理人查詢範圍限制（Phase 3b 強制）

> **來源**：PC-047 — PM prompt 誘導代理人大量讀取，回合耗盡未進入寫入。
> **壓縮版所在**：各實作類 agent 定義檔的「查詢範圍限制」章節（受眾為編輯產品碼者）。

### 核心原則

**實作基於測試，不基於探索。** 代理人收到任務後，查詢範圍嚴格限縮在以下四類：

| 允許查詢 | 目的 | 範例 |
|---------|------|------|
| 測試程式碼 | 了解要通過什麼 | Read 測試檔案中的 TC 案例 |
| 目標 model/DTO | 了解資料結構 | Read 要修改的 class/struct 定義 |
| Domain 邏輯 | 了解業務規則 | Read 相關 domain service |
| 介面定義 | 了解呼叫契約 | Read interface/abstract class |

### 禁止查詢

| 禁止 | 原因 | 正確做法 |
|------|------|---------|
| 「參考 X 檔案的模式」式的大範圍讀取 | 這是探索，不是實作 | PM 應在 Context Bundle 中 inline 必要資訊 |
| grep 搜尋「其他地方怎麼做」 | 消耗 tool call 預算 | PM 應預先提取模式並寫入 Ticket |
| 讀取完整設計文件（Phase 1/2/3a） | context 浪費 | PM 已提取摘要到 Context Bundle |
| 讀取與任務無直接關係的程式碼 | 超出實作範圍 | 聚焦測試要求的最小修改集 |

### 資訊不足時的處理

如果 Ticket 的 Context Bundle 不足以完成實作（缺少 API 簽名、常數定義、介面資訊等），代理人**不應自行大量查詢**，而應：

1. 在 Ticket 記錄缺少什麼：`ticket track append-log <id> --section "NeedsContext" "資訊不足：缺少 X 介面定義和 Y 常數"`
2. 回報 PM 補充資訊後再繼續

**判斷標準**：如果實作需要超過 5 次 Read/Grep 才能開始寫入，代表 Context Bundle 不完整，應停止查詢並回報。

---

## 條款 11：最小變更紀律（Surgical Changes，編輯既有碼時強制）

> **壓縮版所在**：各實作類 agent 定義檔的「最小變更紀律」章節（受眾為編輯既有碼者）。
> **完整條款另見**：`.claude/references/quality-common.md` 第 1.7 節。

**核心規則**：只改被派發任務要求改的碼。diff 每行須能對應需求；禁止四類越界——順手改鄰近無關碼（命名 / typo / 風格）、重新格式化未被要求格式化的檔案（reformat / 改縮排 / 重排 import）、清理非自己造成的既有死碼、用個人偏好改既有風格。新增碼須匹配所在檔案既有風格。

**Why/Consequence**：越界改動與任務無因果關係，會擴大回歸面積、淹沒真實 diff、破壞檔案風格一致性，使 PM review 無法分辨任務改動與順手改動。

**Action**：修改時發現鄰近其他問題（可重構點 / typo / 死碼），不當下順手改，回報 PM 由其建 Ticket 追蹤（quality-baseline 規則 5）；若修復開始級聯（改 A 觸發 B 觸發 C），停手回報 PM 這是範圍失控訊號。

---

## 相關文件

- `.claude/references/agent-rule-carrier-map.md` — 12 條規則的載體對應表
- `.claude/agents/AGENT_PRELOAD.md` — 條款原文所在，其 header 記載送達現況
- `.claude/references/quality-common.md` — 條款 11 的完整版

---

**Last Updated**: 2026-08-18
**Version**: 1.0.0 — 初始建立：承接條款 5 與條款 11 的完整 substance（判準表、禁止清單、資訊不足處理流程、5 次 Read 門檻）。建立原因為條款寫入 agent 定義檔時經壓縮，細節需有按需層去處而非隨壓縮消失。
