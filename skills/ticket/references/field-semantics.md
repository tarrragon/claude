# Ticket 欄位語意對照（六欄位 SSOT）

本文件為 ticket frontmatter 中六個血緣/依賴/關聯欄位的權威語意定義。其他規則、方法論、error-pattern、SKILL 文件涉及這些欄位時應引用本檔，不重複定義。

---

## 適用範圍

本檔涵蓋 **六個血緣/依賴/關聯欄位**：

| 類別 | 欄位 | 雙向欄位 |
|------|------|---------|
| 血緣 | `parent_id` ↔ `children` | 是（CLI 自動維護） |
| 衍生 | `source_ticket` ↔ `spawned_tickets` | 是（CLI 自動維護） |
| 阻擋 | `blockedBy` | 否（單向） |
| 關聯 | `relatedTo` | 否（單向） |

**不涵蓋**：

| 欄位 | 角色 | 應另查 |
|------|------|------|
| `dispatch_reason` | 派發原因記錄（決策溯源） | 本檔不討論；參考 `agent-dispatch-template.md` |
| `decision_tree_path` | 決策樹路徑記錄（決策溯源） | 本檔不討論；參考 `pm-rules/decision-tree.md` |
| `chain` | 任務鏈聚合視圖（衍生欄位） | 本檔不討論；參考 `atomic-ticket-methodology.md`「子任務建立指引」 |

> **判別準則**：本檔聚焦「ticket 之間的關係欄位」（影響阻擋/排程/驗收 hook 行為）；決策溯源欄位（記錄為何建立此 ticket）不在本檔範圍。

---

## 六欄位定義

### parent_id（單值，string）

**語意**：直系父任務（血緣關係）。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | `parent.children[]`（CLI 自動維護） |
| 阻擋語意 | 父 ticket 被未完成 children 阻擋 complete |
| Runqueue 影響 | 子 ticket 受 blockedBy 機制間接影響（本欄位本身不直接過濾） |
| 序號規則 | 自動子序號（如 `W17-001.1`） |
| CLI 寫入 | `--parent <PARENT-ID>` |
| CLI 互斥 | 與 `--source-ticket` 互斥 |

### children（陣列，array of IDs）

**語意**：`parent_id` 的反向欄位，所有以本 ticket 為 parent 的子任務 ID 清單。

| 屬性 | 值 |
|------|---|
| 維護方式 | CLI 自動維護（建立子 ticket 時自動追加） |
| 阻擋語意 | 父端被阻：父 complete 須等所有 children 進入 terminal 狀態（completed/closed） |
| 業務語意 | 「必須一起交付完整功能」 |

### source_ticket（單值，string）

**語意**：衍生來源（非血緣）。本 ticket 因哪個來源 ticket 的執行而衍生。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | `source.spawned_tickets[]`（CLI 自動維護） |
| 阻擋語意 | 視 source ticket type 而定（見「阻擋語意對照表」） |
| Runqueue 影響 | 無 |
| 序號規則 | 獨立 ID（不繼承序號） |
| CLI 寫入 | `--source-ticket <SOURCE-ID>` |
| CLI 互斥 | 與 `--parent` 互斥 |

### spawned_tickets（陣列，array of IDs）

**語意**：`source_ticket` 的反向欄位，本 ticket 衍生出的後續 ticket ID 清單。

| 屬性 | 值 |
|------|---|
| 維護方式 | CLI 自動維護（建立衍生 ticket 時自動追加） |
| 阻擋語意 | 視本 ticket type 而定（見「阻擋語意對照表」） |
| 業務語意 | 「衍生副產品，獨立排程」 |

### blockedBy（陣列，array of IDs）

**語意**：阻擋依賴（單向時序）。本 ticket 必須等清單內的 ticket 全部進入 terminal 狀態才能執行。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | 無（純單向） |
| 阻擋語意 | 不阻擋 complete；影響 runqueue 排程過濾 |
| Runqueue 影響 | `blockedBy` 非空 → 不在 runqueue 列表 |
| CLI 寫入 | `--blocked-by`、`set-blocked-by --add/--remove` |

### relatedTo（陣列，array of IDs）

**語意**：相關引用（弱關聯 metadata）。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | 無（純單向） |
| 阻擋語意 | 不阻擋任何流程 |
| Runqueue 影響 | 無 |
| 業務語意 | 純 metadata 引用（類似 markdown 的 see-also） |
| CLI 寫入 | `--related-to`、`set-related-to --add/--remove` |

> **重要**：`relatedTo` 是弱關聯，**不**作為任何流程訊號。「兄弟 A 的 relatedTo 引用兄弟 B → B 應為 A 的父」這種「升格訊號」推論已棄用——弱關聯就是弱關聯，不從中推論結構意圖。

---

## 阻擋語意對照表

| 欄位組合 | 阻擋父 / source complete? | 阻擋 runqueue? |
|---------|------------------------|--------------|
| `children`（任意 parent type） | 是（永遠） | 子 ticket 受 blockedBy 影響，不直接受本欄位影響 |
| `spawned_tickets`（ANA 類型 source） | 是（W15-003 升級後）— **過渡狀態，IMP 收斂後將移除** | 否 |
| `spawned_tickets`（非 ANA 類型 source） | 否（獨立排程） | 否 |
| `blockedBy` | 否（不影響 complete） | 是（過濾本 ticket） |
| `relatedTo` | 否 | 否 |

> **過渡狀態註記**：ANA spawned 阻擋（W15-003）是 children 路徑收斂前的補丁。後續 hook 重構（acceptance-gate-hook ana_spawned_checker 退場）完成後，ANA 落地將統一走 children 路徑，spawned 對 ANA 也回到「不阻擋」設計。

---

## 用戶情境對照表

| 情境 | 應用欄位 | CLI 命令 | 判別問題 |
|------|---------|---------|---------|
| 拆分功能成 atomic sub-tasks（必同時交付完整功能） | `parent_id` / `children` | `--parent <PARENT-ID>` | 「上游必須等子任務完成才能 complete？」是 → children |
| **ANA 結論的執行延伸（IMP/DOC 落地）** | **`parent_id` / `children`** | **`--parent <ANA-ID>`** | 「ANA 結論要求落地？」是 → children（PC-091 路線） |
| 執行過程中發現獨立 bug / 技術債（與當前 ticket 無因果） | `source_ticket` / `spawned_tickets` | `--source-ticket <SOURCE-ID>` | 「上游 ticket 結論要求？」否，但發現於執行中 → spawned |
| 兄弟單向時序依賴（規格→實作） | `blockedBy` | `set-blocked-by` 或建立時 `--blocked-by` | 「需要血緣？」否；「需要時序等待？」是 → blockedBy（須滿足串行 4 條件） |
| 同 wave 內彼此引用、無時序依賴 | `relatedTo` | `set-related-to` 或建立時 `--related-to` | 「需要等待？」否；「想記錄關聯？」是 → relatedTo |
| 完全獨立的新需求 | （無欄位）sibling | （三皆否，不指定上述任一） | 「上游觸發？時序依賴？關聯？」三皆否 → sibling |

---

## 欄位選擇決策樹

```
建立新 ticket 前自問：
    |
    v
Q1: 上游 ticket 的結論「要求」此 ticket 落地嗎？
   （含 ANA 衍生 IMP / DOC、功能拆分子任務）
    |
    +-- 是 → parent_id（--parent）
    |
    +-- 否 → Q2
         |
         v
    Q2: 此 ticket 是「執行上游 ticket 過程中發現」的獨立技術債 / bug 嗎？
        |
        +-- 是 → source_ticket（--source-ticket）
        |
        +-- 否 → Q3
             |
             v
        Q3: 此 ticket 需要等待其他 ticket 完成才能執行（單向時序）嗎？
            |
            +-- 是 → blockedBy（建立後或建立時 --blocked-by）
            |
            +-- 否 → Q4
                 |
                 v
            Q4: 此 ticket 與其他 ticket 有引用關係但無等待需求嗎？
                |
                +-- 是 → relatedTo（弱關聯 metadata）
                |
                +-- 否 → sibling（不指定上述任一）
```

---

## 反模式速查

| 反模式 | 為何錯誤 | 修正方向 |
|-------|---------|---------|
| ANA 衍生 IMP 用 `--source-ticket` 建為 spawned | 違反 PC-091（ANA 落地統一用 children） | 改用 `--parent <ANA-ID>` |
| 兄弟 A 的 `relatedTo` 引用 B → 推論「B 應為 A 的父」 | `relatedTo` 是弱關聯，不應反推結構 | 結構決策獨立評估，不從 relatedTo 反推 |
| 多個 spawned 但每個都阻擋 source（非 ANA） | `spawned_tickets` 對非 ANA 不阻擋（設計獨立排程） | 若需阻擋改用 children；若獨立排程 spawned 即可 |
| 執行 IMP 時發現獨立 bug，建為 children | children 用於「必同時交付」，獨立 bug 應為 spawned | 改用 `--source-ticket <CURRENT-TICKET>` |
| 兄弟 A 與 B 有依賴但 B 無 `blockedBy` | 隱式依賴難以追蹤（ARCH-017） | 顯式設定 `blockedBy`，或重組為父子（升格） |

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-091-ana-followup-as-siblings-not-children.md` — ANA 落地用 children 規則來源
- `.claude/error-patterns/process-compliance/PC-073-ana-spawned-misused-as-children.md` — 早期 spawned 使用情境（已 deprecated 部分內容，現定位於「執行中發現獨立技術債」）
- `.claude/pm-rules/ticket-lifecycle.md` — Ticket 生命週期完整規則（含「ANA Ticket 落地下游血緣選擇」章節）
- `.claude/methodologies/atomic-ticket-methodology.md` — 任務鏈方法論（兄弟協調模式、聚合父重組範式）
- `.claude/skills/ticket/references/create-command.md` —`--parent` vs `--source-ticket` CLI 副作用對比
- `.claude/skills/ticket/references/track-command.md` — `set-blocked-by` / `set-related-to` 操作說明
- `.claude/skills/ticket/SKILL.md` — `tree`/`chain`/`deps` 命令對血緣與衍生的視覺化分流
- `.claude/error-patterns/process-compliance/ARCH-017` — 兄弟任務隱藏依賴反模式

---

**Last Updated**: 2026-05-03
**Version**: 1.0.0 — 初版建立。提煉自 0.18.0-W17-120 ANA 多視角審查共識（linux + saffron-system-analyst + basil-hook-architect）：PC-091 路線（ANA 落地用 children）取代 PC-073，acceptance-gate hook 後續將收斂雙路徑。
**Source**: 0.18.0-W17-120 (ANA: 釐清五欄位語意邊界) → W17-120.1 (DOC: 建立 SSOT)
