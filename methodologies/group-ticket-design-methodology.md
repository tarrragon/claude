# Group Ticket 設計方法論

> 30 秒核心：當父 ANA/IMP 已 complete 卻發現未追蹤的 N 項衍生修復時，用 Group ticket（`--source-ticket` 接原父 + `--parent` group 接 children）保留層次感且不違 PC-073。CLI 操作與六欄位語意見 ticket skill，本檔只留設計判斷。

## 適用情境

滿足以下任一條件時考慮 Group Ticket 模式：

| 情境 | 細節 |
|------|------|
| 父 ANA/IMP 已 complete，卻發現有未追蹤的 N 項衍生修復 | 直接用 `--parent` 會拉回父狀態為 pending（違 PC-073）|
| 有 3+ 項子任務語意上屬於同一修復專案 | 散為兄弟會失去「屬於某專案」的層次感 |
| 需要「全部子項完成才算收尾」的硬性阻擋語意 | children 阻擋父 complete 正是此需求 |
| 要保留 ANA 分析結論的獨立完成狀態 | 避免衍生追蹤干擾分析本身的 completed 狀態 |

## 三選項對照（地圖型，本表即核心）

| 選項 | 關係欄位 | 阻擋語意 | 對父狀態影響 | 語意合適度 |
|------|---------|---------|-------------|-----------|
| A. `--parent` 直接 children | parent_id + children[] | 硬阻擋（父等所有 children）| **違反 PC-073**——若父已 complete，會被拉回 pending | 不可用於已 complete 父 |
| B. `--source-ticket` 直接 spawned | source_ticket + spawned_tickets[] | 無阻擋（獨立排程）| 無影響 | 語意「兄弟衍生」，失去層次 |
| C. **Group ticket**（本方法論）| group 用 `--source-ticket`；children 用 `--parent` group | children 阻擋 group | 父完全不受影響 | **兩全——保留層次 + 合 PC-073** |

## Group Ticket 模式結構

```
原分析父 ticket（已 complete）
    |
    | --source-ticket
    v
Group ticket（新建，pending）
    |
    | --parent（硬阻擋語意）
    +---> children.1 / .2 / .N（待實作）
```

關鍵性質：原父不受干擾（用 `--source-ticket`，不影響已 complete）；層次感保留（children 明確屬於 group 專案）；硬阻擋正確（children 全完成才觸發 group complete）；雙向追溯（group.source_ticket → 原分析，group.children → 具體子項）。

> CLI 建立步驟（`ticket create --parent` / `--source-ticket` 各欄位）與六欄位語意 SSOT 見 `.claude/skills/ticket/SKILL.md` 與 `.claude/skills/ticket/references/field-semantics.md`，本檔不複述。

## 設計判斷（三衍生規範）

| 規範 | 要求 | 違反後果 |
|------|------|---------|
| Group 不得有實作內容 | `how.strategy` 為「建 children → 協調 → 驗收整合」；統一修復步驟建為 children 之一 | 與 children 職責重疊，難驗收 |
| Children 立即補 Context Bundle | 建完同一輪 append-log 寫入 PCB（原父落差編號 + 實作範圍 + 驗證方式） | 觸發 PC-100（PCB 未繼承 source）|
| Group acceptance 枚舉 children 完成 | 逐項列 children + 「所有 N children complete」+「linux 最終審查」 | group 完成判斷無法機械化檢查 |

**Group complete 時機**：所有 children complete 後 acceptance 自動滿足才 complete；禁止 children 未完成前手動 complete；complete 前派 linux 視角最終審查確認原父修復清單無遺漏。

## 反模式警示

| 反模式 | 後果 | 正確做法 |
|--------|------|---------|
| 實作內容寫 group 自己 | 與 children 職責重疊；難驗收 | Group 只協調，實作推到 children |
| Children 用 `--source-ticket group` 而非 `--parent` | 失去硬阻擋語意，group 可能被誤 complete | Children 必用 `--parent` |
| Group 建好就放著，children 慢慢補 | Group 缺 PCB（PC-100）；children 欄位稀疏 | Build 當輪即完成 group + 全部 children 框架 |
| 「隱形 group」口頭說「這幾個是一組」不建 ticket | 沒有追蹤錨點；父 complete 後無主 | 明確建 group ticket |

## 何時**不**用 Group Ticket

| 情境 | 建議 |
|------|------|
| 只有 1-2 項衍生且父尚未 complete | 直接 `--parent` 父即可 |
| 衍生項互相獨立無語意關聯 | 各自 spawned 即可，不必 group |
| 衍生項全是 backlog 低優先 | 可列 todolist.yaml 不必建 group |
| 父 ticket 尚未 complete 就想建衍生 | 可直接 `--parent` 父（無 PC-073 風險）|

## 相關 Pattern

| 關聯 | 關係 |
|------|------|
| PC-073 | Group 模式存在動機——ANA 衍生 IMP 應用 spawned 而非 parent |
| PC-100 | Children 必須立即補 Context Bundle |
| PC-102 | ROI 表未逐項轉 ticket；Group 模式是轉化的建議結構 |

> 首次實踐案例：W17-008（W17-004 介面基線清理，group + 11 children，混合 5 IMP / 3 DOC / 3 ANA）。

---

**Last Updated**: 2026-06-14
**Version**: 2.0.0 — W8-019.3 整併瘦身：156→約 95 行，CLI 建立步驟路由 ticket skill + field-semantics SSOT（原 line 50-75 命令塊去重），三選項地圖表 + 反模式 + 何時不用保留為 30 秒核心
**Version**: 1.0.0 — 從 W17-008 group ticket 首次實踐提煉
