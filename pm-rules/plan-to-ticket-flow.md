# Plan-to-Ticket 轉換流程

Plan Mode 產出到 Atomic Ticket 的轉換流程。

---

## 8 步驟流程

1. **解析 Plan 檔案** - 提取功能名稱、步驟、修改檔案
2. **識別任務項目** - 原子性檢查、分類（IMP/ADJ/ANA/DOC）
3. **評估複雜度** - 認知負擔指數，決定是否拆分
4. **映射 TDD 階段** - 新功能→完整 TDD，小修改→簡化，純文件→DOC
5. **識別依賴關係** - 資料、架構、TDD 依賴，標記 blockedBy
6. **並行分組** - 無依賴同階段任務分組到同一 Wave
7. **產生 Tickets** - `/ticket create` 建立符合格式的 Atomic Ticket
8. **驗證輸出** - 確認所有 Ticket 符合規範

---

## 觸發條件

| 條件 | 強制性 |
|------|--------|
| `.claude/plans/` 下有已核准 Plan | 必須 |
| 用戶已確認（Plan Mode 退出） | 必須 |
| 目標版本和 Wave 已確定 | 必須 |

**不觸發**：Plan 未核准、純研究型 Plan、已有對應 Ticket

---

## 執行中額外發現（強制流程）

> **核心原則**：執行 Ticket 過程中發現任何需要追蹤的問題（技術債/bug/回歸/超範圍需求），必須立即建立 Ticket，**不需要詢問用戶確認**，不可忽視，不可中斷主線。

### 什麼算「額外發現」

| 情況 | 是否觸發 |
|------|---------|
| 執行中發現技術債務 | 是 |
| 執行中發現 bug 或回歸 | 是 |
| 執行 Ticket 時發現相關模組需同步更新 | 是 |
| Agent 分析時識別出計畫未涵蓋的需求 | 是 |
| 實作中發現設計缺口（規則/流程/文件） | 是 |
| 超出當前 Ticket scope 的延伸工作 | 是 |
| 計畫內的子步驟細分 | 否 |
| 已在原計畫 Ticket 驗收條件中的工作 | 否 |

### 強制處理流程

```
執行中發現技術債/問題/超範圍需求
    |
    v
[強制] 立即執行 /ticket create 建立 pending Ticket
（不需要詢問用戶是否要建立）
    |
    v
新 Ticket 歸入當前版本（Wave 依複雜度決定）
    |
    v
繼續執行當前計畫主線（不中斷）
    |
    v
當前 Ticket 完成後 → 處理新建的 pending Ticket
```

**子任務 vs 獨立 Ticket 判斷**：

```
發現額外需求
    |
    v
因執行當前 Ticket 而產生? ─是→ /ticket create --parent {current_id}
    |
    └─否→ /ticket create（獨立 Ticket）
```

判斷依據：「如果當前 Ticket 不存在，這個問題還會被發現嗎？」
- 不會 → 子任務（因果關係）
- 會 → 獨立 Ticket（獨立問題）

### 禁止行為

| 禁止 | 說明 |
|------|------|
| 詢問用戶「要不要建 Ticket？」 | 發現是確定性事件，建立是強制動作 |
| 忽視不建立 Ticket | 額外發現必須立即追蹤 |
| 中斷主線去處理額外發現 | 先建 Ticket，完成當前任務後再執行 |
| 僅口頭回報不建 Ticket | 必須有可追蹤的 Ticket 記錄 |
| 等計畫完成後再補建 Ticket | 必須**立即**建立 |

---

## Ticket 創建位置決策樹（W17-008.15）

> **背景**：W17-004 / W17-008 系列暴露的問題 — ANA 結論的多項修復條目散落為兄弟 ticket 失去層次感；但若硬用 `--parent {ANA_id}` 又會違反 PC-073（ANA complete 不該被 spawned 拉回）。決策樹協助 PM 在「兄弟」「子任務」「衍生」三種關係間快速定位。

```
新發現需要建立 ticket
    │
    ▼
是 ANA 結論的修復條目？──是──▶ 建為 group ticket 的 children
    │                              （--parent {group_id}；保留層次感、阻擋語意）
    │                              禁止：建為已知 group ticket 的「父任務的兄弟」
    │                              禁止：建為 ANA 自身的 child（PC-073 衝突）
    │
    └─否──▶ 是當前 in_progress ticket 執行中發現？
                │
                是──▶ 因果關係（不執行此 ticket 不會發現）？
                │       │
                │       是──▶ --parent {current_ticket_id}（子任務）
                │       │
                │       否──▶ --source-ticket {current_ticket_id}（衍生 / spawned）
                │              （ANA 衍生 IMP 走此路；遵循 PC-073）
                │
                否──▶ 獨立 ticket（不帶 --parent / --source-ticket）
```

### 三種關係速查

| 關係 | CLI 旗標 | 適用情境 | 違反成本 |
|------|---------|---------|---------|
| 子任務（children） | `--parent {id}` | 因果衍生、需阻擋父 complete | 漏層次 → group 看不出 11 項目；錯掛 ANA → PC-073 |
| 衍生（spawned） | `--source-ticket {id}` | ANA / 大 IMP 衍生獨立 ticket | 漏掛 → 失去追溯；錯用 --parent → PC-073 |
| 兄弟（siblings） | 不帶 flag | 完全獨立的問題 | 應屬子卻建兄弟 → 失層次；ARCH-017 兄弟應無依賴 |

### 創建後輔助提示

- `ticket create` 不帶 `--parent` 時若偵測到當前 wave 內 in_progress group，會自動印出提示行（W17-008.15 第 3 項）
- `ticket track stuck-anas` 列出「in_progress 但 spawned 全 completed」的 ANA，協助識別卡住情境（W17-008.15 第 1 項）
- IMP complete 後若 source ANA 的 spawned 全 completed，會自動印出 complete 建議（W17-008.15 第 2 項）

### 禁止項

| 禁止 | 替代 |
|------|------|
| 建為已知 group ticket 的「父任務的兄弟」（破壞層次感） | `--parent {group_id}` |
| ANA 結論修復條目用 `--parent {ANA_id}`（PC-073） | 建 group ticket 後 `--parent {group_id}` |
| 用 `--parent` 串接無因果的 ticket | 改用 `blockedBy` 或保持兄弟 |

---

## 相關文件

- .claude/references/plan-to-ticket-mapping-details.md - 映射規則、依賴分析、並行分組
- .claude/references/plan-to-ticket-details.md - 驗證清單、報告格式
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/pm-rules/tdd-flow.md - TDD 流程
- .claude/rules/core/cognitive-load.md - 認知負擔評估

---

**Last Updated**: 2026-04-28
**Version**: 3.4.0 — 新增「Ticket 創建位置決策樹」（W17-008.15 方案 D）：三種關係（children / spawned / siblings）速查、CLI 輔助提示、禁止項
**Version**: 3.3.0 - 執行中額外發現流程新增子任務 vs 獨立 Ticket 判斷標準
