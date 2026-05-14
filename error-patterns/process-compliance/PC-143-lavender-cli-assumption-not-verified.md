# PC-143: Lavender Phase 1 Spec 對既有 CLI 行為假設未驗證

## 分類

- **類別**：process-compliance
- **嚴重度**：低（pepper Phase 3a 通常會抓出，但若 sage Phase 2 已基於錯誤 spec 寫測試案例，回頭修正成本上升）
- **狀態**：reproducible（W10-115 Phase 1 出現 1 次）

## 症狀

lavender-interface-designer 在 Phase 1 撰寫 spec 時，描述既有 CLI 命令的 flag / format / 行為時使用了**未經驗證的假設值**。

具體案例（W10-115）：

- lavender Phase 1 spec 寫「`--format table/json/list`」
- pepper Phase 3a 實際 grep `commands/track.py` 後發現實際既有 format 為「`table/ids/yaml`」
- 偏差來源不明：可能是 lavender 從常見 CLI 慣例推測、或從其他命令類比
- 修正成本：pepper Phase 3a 在 8 個 Phase 3b 接手點第 1 點明示「**Spec 偏差**：Phase 1 spec 寫 `--format table/json/list`，**實際既有為 `table/ids/yaml`**——Phase 2 TC F1-F5 須對齊既有 format 名」

## 根因

lavender 預設工作流偏向「閱讀 Context Bundle 內既有設計目標 + 推測合理 CLI 行為」，未強制 grep / Read 既有 CLI 程式碼驗證假設。

當 ticket 修改範圍是「擴展既有命令行為」（非「新增命令」）時，spec 中的「既有行為描述」應為事實陳述而非設計選擇，必須以 source code 驗證。

## 案例重現紀錄

| 案例 | Ticket | 偏差項目 | 發現者 |
|------|--------|---------|--------|
| 1 | W10-115 | `--format` 可選值（table/json/list vs 實際 table/ids/yaml） | pepper Phase 3a |

## 防護

### 立即（lavender 工作流）

當 ticket type=IMP 且修改範圍包含「既有命令 / 既有模組 / 既有 flag」時，lavender 在 Phase 1 撰寫前**必須**：

1. **grep / Read 既有實作**：找到既有 CLI 的 parser 定義、flag choices、help 文字
2. **將事實陳述標為已驗證**：spec 中描述既有行為時，標註來源 line 號（如「依 `commands/track.py:430-439` 既有定義」）
3. **與設計新增區分**：spec 章節內「既有行為（事實）」 vs 「本 ticket 新增（設計）」必須明確分離

### 中期（lavender prompt template / SKILL.md）

- lavender 派發 prompt 加入強制 grep 提示：「修改既有命令時，先 grep `<file_path>` 驗證 flag/format 既有值再寫 spec」
- SKILL.md 加入「既有行為事實陳述必須附 source 引用」規範

### 跨 Phase 防護

- pepper Phase 3a 接手時應例行驗證 Phase 1 spec 對既有 CLI 的描述（本案例已自然發生）
- sage Phase 2 若基於既有 flag 寫測試 fixture，亦應驗證 fixture 值與既有 CLI 一致

## 相關文件

- `.claude/agents/lavender-interface-designer.md`（待補強既有行為驗證規範）
- `.claude/error-patterns/process-compliance/PC-068-phase3a-existing-utility-scan.md`（pepper Phase 3a 既有 utility 掃描，本 PC 是其姊妹模式對 lavender Phase 1 的要求）

## 學習要點

| 教訓 | 應用 |
|------|------|
| 修改既有命令時 spec 含事實陳述（不只設計選擇） | lavender 必須 grep 驗證才寫 spec |
| 「既有行為描述」與「新增設計」應分離標註 | spec 模板加入區分章節 |
| pepper Phase 3a 是 Phase 1 偏差的最後安全網 | pepper prompt 應提示交叉驗證 Phase 1 spec |

---

**Created**: 2026-05-12
**Source**: 本 session W10-115 Phase 3a pepper 回報的 Spec 偏差
**Related**: PC-068（姊妹模式：pepper Phase 3a 既有 utility 掃描）
