# PC-100: ANA 衍生 IMP/ADJ 時 PCB 欄位未繼承 source ticket

## 基本資訊

- **Pattern ID**: PC-100
- **分類**: 流程合規（process-compliance）
- **風險等級**: 高（每次 ANA→IMP 衍生都可能踩）
- **相關 Pattern**: PC-040（context in prompt not ticket）、PC-047（prompt causes agent excessive reading）、PC-073（spawned vs children 語意）

---

## 問題描述

### 症狀

PM 建立 ANA 衍生的 IMP/ADJ/DOC spawned ticket 時，新 ticket 的 PCB 欄位呈現「空殼」狀態：

| 欄位 | 空殼表現 |
|------|---------|
| `where.files` | 只寫目錄如 `.claude/skills/ticket/`，不寫具體 Python 檔 |
| `how.strategy` | 高階四步驟（「盤點→設計→試點→評估」），未指向 source ticket 的具體結論 |
| `acceptance` | 含未量化詞彙（「合理性」「錯誤偵測機制」） |
| `Problem Analysis` | 完全空白（template placeholder 未替換） |
| Context Bundle | 無，子 agent 派發時必須自己 Read source ticket 補齊 |

### 根本矛盾

PM 在 source ticket（ANA）已完成充分分析（Linux 類比、WRAP 結論、落差清單），但衍生 IMP 時啟動「從零填表」思維而非「從 source 繼承」思維。subagent 啟動時 PCB 空→ 被迫 Read source → 耗掉 tool budget 於探索 → 失敗或回合不足。

---

## 根因分析

### 直接原因

`ticket create` CLI 沒有自動從 `--source-ticket` 抽取 Context Bundle 的機制（這正是 IMP 常見衍生任務要解決的問題，但現況仍需 PM 手填）。

### 深層原因

| 類型 | 說明 |
|------|------|
| A PM 思維切換失敗 | ANA 完成後建 IMP 啟動的是「新 ticket 建立表」腦中模板，忘記 source ticket 已有 80% 資訊 |
| B CLI 鼓勵簡短 | `--why / --how-strategy` 等參數適合短語，無法塞 Context Bundle；PM 預設簡短就夠 |
| C append-log 斷層 | create 完成後需**另一步** append-log 才能補 Context Bundle，PM 常直接跳下一動作 |
| D 文件斷層 | `context-bundle-spec.md` 要求用 `append-log --section "Context Bundle"`，但 CLI section 枚舉不含此值（見 PC-007 類衝突） |

---

## 防護措施

### 立即可行（PM 自律）

1. **建 spawned ticket 後立即 append-log**：
   ```bash
   ticket create --source-ticket <source_id> ... --acceptance ...
   ticket track append-log <new_id> --section "Problem Analysis" "$(cat <<'EOF'
   ## Context Bundle
   ### 背景（從 <source_id> 繼承）
   - 主要結論摘要（3-5 行）
   - 關聯檔案（具體到 .py / .md，含行號）
   - 驗收條件量化指標
   EOF
   )"
   ```
2. **where 欄位禁止僅目錄**：必須列至少 1 個具體檔案
3. **acceptance 禁止模糊詞**：「合理性」「錯誤偵測」必須替換為可量化指標（Tripwire）

### 系統性（待 W17-002 實作完成）

`ticket create --source-ticket` 自動抽取 source ticket 的 what/why/where.files/acceptance 填入新 ticket Context Bundle（對齊 Linux kernel ELF loader 自動載入依賴）。

---

## 觸發案例

### W17 Meta 循環（本 Pattern 發現案例）

PM 完成 W17-001 ANA（分析 subagent 派發 PCB 半填就 fork 反模式），建立 spawned IMP W17-002 / ADJ W17-003 時，首版 PCB 欄位全空（Problem Analysis placeholder、where 僅目錄、how 高階策略）。用戶審視後指出「正犯我們剛發現的毛病」，PM 被迫補欄位。

**Meta 觀察**：分析「PCB 未繼承」這個問題的 ticket，自己衍生的 IMP 就犯了同樣錯誤——證明沒有系統自動化，純靠 PM 自律難以維持一致性。

---

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-040 | 同主題（context in prompt not ticket）；PC-100 聚焦「衍生時 Context Bundle 應從 source 繼承」 |
| PC-047 | 下游後果：Context Bundle 空 → subagent 被迫探索 → tool budget 耗盡 |
| PC-073 | 關聯：spawned_tickets 語意被誤解後，更容易用 --parent 而非 --source-ticket，失去「來源」資訊 |

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17 meta 循環案例建立
