# PC-V1-003: 聯想式檔案參照寫入後個案修補，跳過模式分析

## 基本資訊

| 項目 | 內容 |
|------|------|
| 類別 | Process Compliance |
| 嚴重度 | 中（單例成本低，但消音機制讓同型錯誤無上限累積） |
| 觸發角色 | PM 主線程（撰寫 ticket 欄位 / 規格 / 文件中的檔案參照時） |
| 家族 | PC-166（confabulation）檔案參照變體 + PC-111 Layer B（淺層歸因）同構 + PC-143（未驗證假設寫入規格）同家族 |

---

## 症狀

兩段式模式，缺一不構成本 PC：

1. **聯想式參照寫入**：PM 在 ticket 欄位（`where.files`、引用路徑）、規格或派發 prompt 中寫入檔案參照，其內容由記憶聯想生成（memory slug、慣用命名模式、相似檔名），未經 `ls` / `grep` 固定值驗證即當事實寫入。
2. **個案修補消音**：防護機制（claim 檢查清單、派發前驗證）抓到參照錯誤後，PM 以「筆誤」歸因，`set-where` 修正該例即繼續推進——不掃描同 session 是否有同型錯誤、不建學習記錄。錯誤情報被消音而非被學習。

**判別準則**：發現參照錯誤時，若修正動作後的下一步是「繼續原任務」而沒有「同型掃描」或「記錄」，即命中第 2 段。

## 根因分析

### Layer A：參照生成無 grounding（PC-166 變體）

檔案參照是自回歸生成的高風險點：記憶條目 slug（如 `feedback_batch_script_over_edit_loop`）、規則慣用命名（`pm-role-details.md`）與真實檔名（`PC-069-batch-mechanical-edit-when-subagent-blocked.md`、`behavior-loop-details.md`）在語意空間中相鄰，生成時無法自我區分「回憶」與「重構」。PC-166 處理的是「工具結果幻覺」，本 PC 是其靜態變體——**參照幻覺**：不需要工具呼叫場景，任何「憑印象寫路徑」的瞬間都會發生。

### Layer B：淺層歸因消音（PC-111 Layer B 同構）

防護機制抓到錯誤 = 系統送來高價值訊號（quality-baseline 規則 6：失敗直指特定瓶頸）。「筆誤」歸因把結構性訊號降級為隨機雜訊，跳過三個本應觸發的動作：(a) 問「為什麼會生成這個錯誤參照」；(b) 掃描同 session 同型錯誤；(c) 二度發生時建學習記錄。**Consequence**：消音機制讓同型錯誤的發現成本永遠由防護機制承擔，PM 的生成行為不被修正；防護未覆蓋的參照（如寫入規格文件、未被 hook 檢查的欄位）成為靜默錯誤直接流入下游。

## 觸發案例（2026-06-11 同 session 二度發生）

| # | 寫入位置 | 錯誤參照 | 實際檔名 | 聯想來源 | 抓到的防護 | PM 處置 |
|---|---------|---------|---------|---------|-----------|---------|
| 1 | ticket `where.files` | `.claude/pm-rules/pm-role-details.md` | `behavior-loop-details.md` | pm-role.md 的「詳細版」慣用命名模式 | claim 檢查清單（驗證 where.files 存在） | set-where 修正後繼續，無模式分析 <!-- broken-link-exempt: documented-error --> |
| 2 | ticket `where` | `PC-069-batch-script-over-edit-loop.md` | `PC-069-batch-mechanical-edit-when-subagent-blocked.md` | memory slug `feedback_batch_script_over_edit_loop` 直譯 | 派發前 `ls` 驗證 | 同上——二度發生仍未觸發學習記錄，由用戶指出 |

## 防護措施

| 層 | 措施 | 可執行檢查 |
|----|------|-----------|
| 寫入前（Layer A 阻斷） | 任何檔案參照寫入 ticket 欄位 / 規格 / prompt 前，先以固定值驗證存在性 | `ls <path>` 或 `ls <dir> \| grep <關鍵字>`；批量參照用一次 `ls` 對照全表。**正向錨點**：驗證成本一條命令，遠低於下游修正 |
| 發現時（Layer B 阻斷） | 防護機制抓到參照錯誤時，修正前強制自問兩題 | (1)「這個錯誤參照從哪個聯想來源生成？」（記下來源）；(2)「同 session 還有哪些參照出自同一生成方式？」（grep 本 session 建立的 ticket 欄位掃描） |
| 二度即記錄 | 同 session 同型錯誤第二次出現 = 模式門檻，當下建學習記錄（本 PC 的存在即此規則的產物） | 依 quality-baseline 規則 5/6 建 ticket + error-pattern，不等用戶指出 |

## 與其他 PC 的邊界

| PC | 聚焦 | 與本 PC 差異 |
|----|------|------------|
| PC-166 | 工具呼叫後的結果幻覺（動態，需 tool-call 場景） | 本 PC 為靜態參照幻覺，無工具呼叫也會發生；防護同源（固定值驗證） |
| PC-111 | 論述編造（Layer A）+ 淺層歸因（Layer B） | 本 PC 的 Layer B 與其同構；差異在對象——PC-111 是「被糾正時」，本 PC 是「防護機制抓到時」（更早、無人際壓力，理應更容易做對） |
| PC-143 | agent 在規格中寫未驗證的 CLI flag 假設值 | 同家族（未驗證假設寫入產出物）；本 PC 補「發現後的處置」第二段，PC-143 只覆蓋寫入段 |

---

**Last Updated**: 2026-06-11
**Version**: 1.0.0
**Source**: 2026-06-11 session 二度發生（W1-056 where.files 不存在檔名 + W1-065 PC-069 錯誤檔名 = memory slug 直譯），均個案修補後繼續，由用戶指出「發現錯誤情報未深入系統錯誤直接略過」後固化（W1-067）
