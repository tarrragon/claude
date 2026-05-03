# PC-122: 新建 error-pattern 推翻既有 PC 但未同步舊 PC，留下並存衝突源

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-122 |
| 類別 | process-compliance |
| 風險等級 | 中（並存期間任何 PM 觸發都是潛在 bug 來源） |
| 首發時間 | 2026-04-17 / 2026-04-18（PC-073 vs PC-091 並存）；2026-05-03 識別並修訂 |
| 姊妹模式 | PC-093（無 trigger 延後決策）、PC-061（memory 升級盲視） |

---

## 症狀

PM 或 framework 維護者建立新 error-pattern 推翻既有 PC 的指引，但未同步處理既有 PC：

1. 既有 PC 仍宣稱舊指引有效，無 deprecated 標註，無「被取代」線索
2. 新 PC 不引用既有 PC 為 sister pattern
3. 兩 PC 並存進入 framework 流通；不同 session 的 PM 讀到不同 PC，做出**正面對立**的操作
4. 衝突可能延遲數週至數月才被發現（多視角審查 / 跨情境讀規則時）

---

## 觸發案例

**事件**（2026-04-17 至 2026-05-03，0.18.0-W17-120 ANA 識別）：

| 日期 | 事件 |
|------|------|
| 2026-04-17 | PC-073 建立：「ANA Ticket 的 Solution 建議『後續 IMP 實作』→ 衍生關係（spawned）」 |
| 2026-04-18 | PC-091 建立：「ANA 結論的執行延伸（IMP/DOC 落地）必為 children（不可用 spawned）」一日內覆蓋 PC-073 |
| 2026-04-19 至 2026-05-03 | 約 16 天並存期間。PC-073 未加 deprecated 標註，PC-091 未引用 PC-073；PM 在不同情境讀到不同規則 |
| 2026-05-03 | W17-120 ANA 多視角審查（linux + saffron + basil）才識別衝突，需執行修訂 |

---

## 與 PC-093 / PC-061 的區別

| 維度 | PC-093 (deferred decision) | PC-061 (memory upgrade blindness) | PC-122 (本模式) |
|------|---------------------------|----------------------------------|----------------|
| 對象 | 個別 ticket 內的決策延後 | memory 寫入後未升級 framework | error-pattern 之間的覆蓋未同步 |
| 觸發 | 「之後再改」「以後再說」 | memory 寫完直接結束 | 新 PC 建立時不處理舊 PC |
| 後果 | 死議題累積 | 跨專案原則被困在單一專案 | 兩 PC 並存產生對立指引 |

---

## 根本原因

### 表層原因
建立新 PC 時專注於描述新發現的反模式，忘記檢查既有 PC 是否有重疊範圍。

### 深層原因
1. **規則撰寫者的「新規則焦點」偏誤**：撰寫者心思集中在「我要記錄這個新發現」，舊規則屬「已知資產」自動退入背景
2. **缺乏「衝突檢查」步驟**：PC 建立流程未強制 grep 既有 PC 索引確認範圍重疊
3. **缺乏並存衝突的偵測機制**：framework 沒有 hook 自動偵測「多個 PC 對同一情境給出對立指引」

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 規則 | rules/core/quality-baseline.md 規則 5「所有發現必須追蹤」延伸：新建 PC 時必須 grep 既有 PC 索引並說明衝突處理 | 建議實施 |
| Hook | 新建 PC commit 觸發掃描，若新 PC 未引用既有 PC（grep 既有 PC 名稱）且新 PC 內含「取代 / 推翻 / deprecated / 不可用」等關鍵字，提示確認衝突處理 | 建議實施（複雜度中） |
| 自檢 | PC 建立 PR / commit 前自問：「這個 PC 是否與既有 PC 範圍重疊？是 → 同步在既有 PC 加 deprecated 標註並交叉引用」 | 行為準則 |
| Memory | 原則保留 memory 作跨 session 索引（feedback_error_pattern_conflict_sync.md） | 已實施（配對本檔） |

---

## 檢查清單（建立新 PC 前）

- [ ] grep 既有 PC 是否有範圍重疊？（依 keyword / 概念）
- [ ] 若有重疊，是「補充」「延伸」「取代」哪一種關係？
- [ ] 若是「取代」全部範圍 → 既有 PC 加 deprecated 標註指向新 PC
- [ ] 若是「取代」部分範圍 → 既有 PC 在重疊段落加 deprecated 標註 + 範圍縮限說明
- [ ] 若是「補充」「延伸」 → 互相引用為 sister pattern，不需 deprecated
- [ ] 同 commit 一併修訂既有 PC（或先後 commit，禁止口頭記錄「之後再改」）

---

## 緊急修復步驟（已遇到此問題時）

1. 識別衝突的兩個（或多個）PC
2. 決定主導 PC（通常較新且更完整的版本）
3. 既有 PC 加 deprecated 標註 + 範圍縮限說明（保留有效範圍如有）
4. 主導 PC 加 sister pattern 引用 + 取代日期
5. 評估是否需建立 SSOT 文件統一概念（如 W17-120 建立 field-semantics.md）
6. 跨文件 grep 修正所有引用舊 PC 的下游文件

---

## 教訓

1. **建立規則時的「破壞影響檢查」必須與規則內容並重**：新規則的價值不只在「它說什麼」，還在「它如何與既有規則協同」
2. **acceptance-gate / commit hook 是規則完整性的最後防線**：人工自檢失效時，hook 是兜底
3. **多視角審查在規則層的價值**：W17-120 的衝突若只用 PM 單視角審查不易識別，三 reviewer 並行才能交叉驗證

---

## 象限歸類

本模式的防護屬 **摩擦力管理 A 象限（自動護欄）**：commit hook 偵測新 PC 引用既有 PC 衝突關鍵字，提示確認。代價（單次 hook 開發）遠低於收益（避免每次新 PC 建立後數週至數月的並存衝突期）。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-091-ana-followup-as-siblings-not-children.md` — 觸發案例之一（已升格為 ANA 落地唯一指引）
- `.claude/error-patterns/process-compliance/PC-073-ana-spawned-misused-as-children.md` — 觸發案例之二（已加 deprecated 標註，範圍縮限）
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` — 姊妹模式（memory 升級盲視）
- `.claude/error-patterns/process-compliance/PC-093-yagni-deferred-decision-accumulation.md` — 「之後再改」反模式
- `.claude/skills/ticket/references/field-semantics.md` — W17-120 建立的 SSOT 範例

---

**Last Updated**: 2026-05-03
**Version**: 1.0.0 — 從 W17-120 ANA 識別 PC-073 vs PC-091 並存衝突提煉。Source memory: `feedback_error_pattern_conflict_sync.md`
