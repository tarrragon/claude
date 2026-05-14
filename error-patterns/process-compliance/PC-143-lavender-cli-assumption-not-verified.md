# PC-143: Spec / ANA 規劃引用既有資源（CLI flag / Hook 名稱）未驗證存在性

> **Why**：spec 和 ANA 規劃中對既有資源（CLI flag、hook 名稱、模組路徑）的描述屬於「事實陳述」而非「設計選擇」。若未 grep / Read 驗證即寫入，實作者會以錯誤名稱開發，直到 Phase 3a 或 commit 才發現偏差，回頭修正成本隨階段推進而上升。

> **Consequence**：兩個已記錄案例顯示此模式在不同角色（lavender Phase 1 spec、basil ANA spawn IMP）和不同資源類型（CLI flag、hook 名稱）下均可重現；未驗證假設的修正成本最早在 Phase 3a 顯現，最晚可到 Phase 3b 實作時才發現 hook 名稱不存在。

> **Action**：任何 agent 在 spec / ANA 規劃中描述「既有資源名稱」前，必須先 grep / ls / Read 驗證其存在性，然後將驗證結果（來源路徑:行號 或 ls 輸出）作為 spec/Solution 的一部分附上。

## 分類

- **類別**：process-compliance
- **嚴重度**：中（修正成本隨 TDD Phase 推進而上升；hook 名稱錯誤會導致 Phase 3b 實作直接失敗）
- **狀態**：reproducible（W10-115 首例；W14-036 二度重現，不同 agent、不同資源類型）

## 症狀

spec 或 ANA 規劃文件中出現「既有資源名稱」（CLI flag / hook 檔案名稱 / 模組路徑），但實際資源不存在或名稱不同。

觸發條件：

- 「修改既有命令 / 擴充既有 hook」類 ticket，spec 含事實陳述而非設計選擇
- ANA spawn IMP 規劃，`where.files` 列出的 hook/模組名稱從「常識推測」而非 ls/grep

## 根因

spec / ANA 規劃者的預設工作流是「閱讀 Context Bundle 設計目標 + 推測合理名稱」，未建立「既有資源名稱必須 grep/ls 驗證」的強制節點。

**Why 此模式容易跨角色重現**：「推測合理名稱」在認知上費力度極低（從語意推名稱直覺合理），而 grep 驗證需要額外 tool call；若 spec/規劃框架未明確要求驗證步驟，角色會自然略過。

**Consequence**：規劃文件含錯誤名稱時，後續 IMP ticket 會繼承錯誤的 `where.files`，直到 Phase 3b 實作者嘗試讀取或測試才發現，此時已消耗多個 Phase 的推進成本。

**Action**：防護措施設計為「規劃階段強制驗證 + 文件標註來源」雙層，使偏差在最低成本的時機（spec 撰寫時）被發現，不傳遞到後續 Phase。

## 案例重現紀錄

| 案例 | Ticket | 規劃者 | 偏差資源類型 | 假設值 | 實際值 | 發現者 / 時機 |
|------|--------|--------|------------|--------|--------|-------------|
| 1 | W10-115 | lavender（Phase 1 spec） | CLI `--format` 可選值 | `table/json/list` | `table/ids/yaml` | pepper Phase 3a |
| 2 | W14-036 | basil（W14-032 ANA spawn IMP 規劃） | hook 檔名 | `decision-quality-guard-hook.py` | `wrap-decision-tripwire-hook.py` | basil 執行 W14-036 時（Phase 3b 實作前 agent 自律對齊） |

### W14-036 案例細節

**時間**：2026-05-14（W14 Wave）

**規劃 ticket**：W14-032（ANA，basil 執行）— 分析 `.claude/hooks/` 全部 hook 的 effort 感知遷移範圍與優先級，產出 spawn IMP 規劃表。

**實際情境**：basil 在 W14-032 Solution 類別 A 清單中列入 `decision-quality-guard-hook.py`，並在 spawn IMP W14-036 的 `where.files` 繼承此名稱。W14-036 執行時（basil 實作），實際對 `.claude/hooks/` 執行 ls 後確認 `decision-quality-guard-hook.py` 不存在，對應 hook 為 `wrap-decision-tripwire-hook.py`（以 `wrap-decision-tripwire` 語意命名，職責為 WRAP 決策框架觸發偵測）。

**Agent 自律對齊行為**：basil 在 Phase 3b 實作前自行 ls 確認，主動修正 hook 名稱後繼續實作，未造成 commit 阻擋。但錯誤名稱已傳入 W14-036 `where.files` 且 W14-032 Solution 表格仍含誤記名稱（未回填修正）。

**根因分析**：basil ANA 分析時「依檔名語意 + 既有 hook 知識（agent prompt 已內化所有 hook 名稱與職責）分類」（引自 W14-032 Solution「實驗執行」段落）。此描述揭示問題：ANA 規劃者依賴「內化知識」（訓練時習得的名稱）而非實時 ls 驗證，兩者可以不一致。`decision-quality-guard` 是功能語意，`wrap-decision-tripwire` 是實際命名，從功能推名稱在語意上「合理」卻實際不存在。

## 防護

### 立即（spec / ANA 規劃撰寫者通用）

任何 agent（lavender、basil、saffron 等）在 spec / ANA 規劃中描述「既有資源名稱」時，**必須**在撰寫前執行驗證：

**CLI flag / format 驗證**：
```bash
grep -n "choices\|add_argument\|format" <cli_source_file> | head -30
```

**Hook 名稱驗證**：
```bash
ls .claude/hooks/ | grep -i "<功能關鍵字>"
```

**模組路徑驗證**：
```bash
ls <目標目錄>/<預期檔名>
```

驗證後，spec / Solution 中的既有資源名稱必須標註來源：

| 陳述類型 | 標註格式 | 範例 |
|---------|---------|------|
| CLI flag 既有值 | `（依 <file>:<line> 既有定義）` | `--format table/ids/yaml（依 commands/track.py:430-435 既有定義）` |
| Hook 檔名 | `（依 ls .claude/hooks/ 確認）` | `wrap-decision-tripwire-hook.py（依 ls .claude/hooks/ 確認）` |
| 模組路徑 | `（依 ls <dir> 確認）` | `hook_utils/effort.py（依 ls .claude/hooks/hook_utils/ 確認）` |

### 中期（agent prompt template 層）

**lavender** 派發 prompt 加入強制 grep 提示：「修改既有命令時，先 grep `<file_path>` 驗證 flag/format 既有值再寫 spec」

**basil / saffron（ANA 規劃 spawn IMP 環節）** 派發 prompt 加入強制 ls 提示：「列入 `where.files` 的 hook/模組名稱，必須先 `ls .claude/hooks/ | grep <keyword>` 確認存在再寫入」

### 跨 Phase 安全網

- pepper Phase 3a 接手時應例行驗證 Phase 1 spec 對既有 CLI 的描述（W10-115 案例已自然發生）
- Phase 3b 實作者（或 ANA spawn IMP 執行者）接手時應驗證 `where.files` 中的路徑存在性，發現偏差時在 Problem Analysis 記錄並回填規劃 ticket Solution（W14-036 案例：agent 自律對齊成功，但漏回填規劃 ticket）

### AGENT_PRELOAD 通用層防護

在 AGENT_PRELOAD.md 加入「規劃 hook/CLI 名稱前必須 grep/ls 驗證存在性」條款（見「相關文件」連結）。

## 決策記錄：選 A（擴充 PC-143）vs 選 B（新建 PC）

**選 A 理由**：

W10-115（lavender CLI flag）與 W14-036（basil ANA hook 名稱）共享相同根因結構：

1. 規劃/spec 撰寫者以「語意推測」取代「grep/ls 驗證」
2. 偏差對象是「既有資源名稱」（事實陳述，非設計選擇）
3. 偏差在後續 Phase 實作時才顯現

差異僅是呼叫者角色（lavender vs basil）和資源類型（CLI flag vs hook 名稱）。若建立 PC-B 獨立模式，讀者需要知道「何時查 PC-143、何時查 PC-B」，邊界定義本身會增加認知負擔。合併在 PC-143 下並泛化標題，讀者看到「spec/ANA 規劃引用既有資源未驗證」即能快速定位，無需查兩個 PC。

**排除選 B 的理由**：兩個案例的防護措施（grep/ls 驗證 + 來源標註）完全相同，無需因角色或資源類型差異建立獨立 PC。

## 相關文件

- `.claude/agents/AGENT_PRELOAD.md`（通用層防護條款，規則 8）
- `.claude/agents/lavender-interface-designer.md`（待補強既有行為驗證規範）
- `.claude/error-patterns/process-compliance/PC-068-phase3a-existing-utility-scan.md`（pepper Phase 3a 既有 utility 掃描，本 PC 的姊妹模式）

## 學習要點

| 教訓 | 應用 |
|------|------|
| spec/規劃文件含「既有資源名稱」即屬事實陳述，必須 grep/ls 驗證 | 所有規劃類 agent（lavender/basil/saffron）在 spec/Solution 撰寫前強制驗證 |
| 「內化知識」（訓練習得的名稱）與「實際程式碼狀態」可以不一致 | 不可依賴 agent 內化知識，必須實時查詢 |
| agent 自律對齊（Phase 3b 前 ls 確認）是最後安全網，但代價是規劃文件含誤記名稱不回填 | 強制驗證在規劃階段完成，不應依賴 Phase 3b 自律對齊作為主要防護 |
| 「既有行為描述」與「新增設計」在 spec/Solution 中應分離標註 | 既有資源名稱附來源引用，新增設計不加引用 |

---

**Created**: 2026-05-12
**Updated**: 2026-05-14（W14-040：擴充標題涵蓋 ANA 規劃情境；加入 W14-036 案例；加入 AGENT_PRELOAD 通用層防護）
**Source**: W10-115 Phase 3a pepper 回報的 Spec 偏差（首例）；W14-036 basil ANA spawn IMP hook 名稱誤記（二度重現）
**Related**: PC-068（姊妹模式：pepper Phase 3a 既有 utility 掃描）
