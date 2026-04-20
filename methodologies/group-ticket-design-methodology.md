# Group Ticket 設計方法論

> 正面案例方法論——從 W17 介面基線清理實踐提煉。用於解決「父 ticket 已 complete 後仍需追蹤衍生子項」的 parent-source 語意衝突。

## 適用情境

當滿足以下任一條件時，考慮 Group Ticket 模式：

| 情境 | 細節 |
|------|------|
| 父 ANA/IMP 已 complete，卻發現有未追蹤的 N 項衍生修復 | 直接用 `--parent` 會拉回父狀態為 pending（違 PC-073）|
| 有 3+ 項子任務語意上屬於同一修復專案 | 散為兄弟會失去「屬於某專案」的層次感 |
| 需要「全部子項完成才算收尾」的硬性阻擋語意 | children 阻擋父 complete 正是此需求 |
| 要保留 ANA 分析結論的獨立完成狀態 | 避免衍生追蹤干擾分析本身的 completed 狀態 |

## 三選項對照

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
    +---> children.1（待實作）
    +---> children.2（待實作）
    +---> children.N（待實作）
```

關鍵性質：

- **原父不受干擾**：Group 用 `--source-ticket`，不影響已 complete 狀態
- **層次感保留**：Children 清楚屬於「group 修復專案」非散落
- **硬阻擋正確**：Children 全完成才觸發 Group complete，符合 children 語意
- **雙向追溯**：Group.source_ticket → 原分析；Group.children → 具體子項

## 實踐清單

### 建 Group ticket

```bash
ticket create \
  --action "清理" \
  --target "<原父 ID> <主題> batch（N 項 group 協調）" \
  --type IMP  # 或 ANA/ADJ 視內容
  --wave <N> \
  --priority <最高 children 優先級> \
  --who rosemary \
  --what "作為 group ticket 協調 <原父> 修復清單中 N 項未建 ticket 的遺漏項；逐項由 children 執行；本 group 於所有 children 完成後 complete" \
  --source-ticket "<原父 ID>" \  # 注意：source 非 parent
  --acceptance "children <group>.1 ...|...|所有 N children complete|linux 最終審查" \
  --decision-tree-*
```

### 建 Children ticket

```bash
ticket create \
  --action "..." \
  --target "..." \
  --type <IMP/DOC/ANA> \
  --parent "<group ID>" \  # 注意：parent 非 source
  --priority <Px> \
  --who <agent> \
  # 其餘欄位充分
```

### Group ticket 完成時機

- **禁止**：所有 children 未完成前，不可手動 complete group
- **正確**：children 全部 complete 後，group 的 acceptance 自動滿足，才 complete
- **驗收**：group complete 前派 linux 視角最終審查，確認原父分析的修復清單已無遺漏

## 衍生規範

### 1. Group 本身不得有實作內容

Group ticket 的 `how.strategy` 應為「step 1: 建 children；step 2: 協調；step 3: 驗收整合」，不可混入自身實作。若需要統一修復步驟，建為 children 之一。

### 2. Children 必須立即補 Context Bundle（PC-100 防護）

建完 children 後**同一輪** append-log 寫入 Context Bundle，引用：
- 原父的具體落差/優先級編號
- 實作範圍（具體檔案 + 函式/常數）
- 驗證方式（grep / pytest / 手動）

缺此步會觸發 PC-100（PCB 未繼承 source）。

### 3. Group 的 acceptance 必須枚舉 children 完成

```yaml
acceptance:
- '[ ] children X.1 (類型): 短標題'
- '[ ] children X.2 (類型): 短標題'
- ...
- '[ ] 所有 N children complete'
- '[ ] linux 最終審查 reviewed'
```

這讓 group 完成判斷可機械化檢查。

## 觸發案例

### W17-008：W17-004 介面基線清理 group（首次實踐）

**情境**：W17-004 ANA 完成後，Solution 修復清單 P0 已建（W17-005/006），但 P1/P2/中型歧義共 11 項未轉 ticket（PC-102 首案）。用戶要求子任務語意而非兄弟。

**應用**：
- Group: W17-008（source=W17-004）
- Children: W17-008.1-.11（11 項，parent=W17-008）
- 類型混合：5 IMP / 3 DOC / 3 ANA

**效果**：
- W17-004 completed 狀態維持
- 11 項明確屬於「W17-004 介面清理專案」
- W17-008 collect 11 children 完成才 complete，有序推進

## 反模式警示

| 反模式 | 後果 | 正確做法 |
|--------|------|---------|
| 把 group 當「虛擬聚合」，實作內容寫 group 自己 | 與 children 職責重疊；難驗收 | Group 只協調，實作推到 children |
| Children 用 `--source-ticket group` 而非 `--parent` | 失去硬阻擋語意，group 可能在 children 未完成前被誤 complete | Children 必用 `--parent` |
| Group 建好就放著，children 慢慢補 | Group 缺 Context Bundle（PC-100）；children 欄位稀疏 | Build 當輪即完成 group + 全部 children 框架 |
| 「隱形 group」——口頭說「這幾個是一組」不建 group ticket | 沒有追蹤錨點；父 complete 後無主 | 明確建 group ticket |

## 相關 Pattern 與方法論

| 關聯 | 類型 | 關係 |
|------|------|------|
| PC-073 | error-pattern | Group 模式的存在動機——ANA 衍生 IMP 應用 spawned 而非 parent |
| PC-100 | error-pattern | Children 必須立即補 Context Bundle |
| PC-102 | error-pattern | ROI 表未逐項轉 ticket；Group 模式是轉化的建議結構 |

## 何時**不**用 Group Ticket

| 情境 | 建議 |
|------|------|
| 只有 1-2 項衍生且父尚未 complete | 直接 `--parent` 父即可 |
| 衍生項互相獨立無語意關聯 | 各自 spawned 即可，不必 group |
| 衍生項全是 backlog 低優先 | 可列 todolist.yaml 不必建 group |
| 父 ticket 尚未 complete 就想建衍生 | 可直接 `--parent` 父（無 PC-073 風險）|

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17-008 group ticket 首次實踐提煉
