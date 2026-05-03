# 規則層 SSOT 先於 Hook 層收斂 方法論

當發現規則文件、方法論或 error-pattern 與 hook 行為層出現語意分裂時，本方法論規範修訂順序：**先 DOC 規則層落地新決議（含建 SSOT）→ 再 IMP hook 層收斂**。

---

## 適用場景

| 觸發訊號 | 範例 |
|---------|------|
| Hook 行為與規則文件描述不一致 | acceptance-gate-hook 的阻擋邏輯與 ticket-lifecycle.md 描述衝突 |
| 一份概念散落在多個文件且互相矛盾 | 五欄位語意散落於 SKILL.md / methodologies / error-patterns 且結論對立 |
| 行為層存在「過渡狀態補丁」未對齊規則 | W15-003 升級 hook 阻擋邏輯但 create-command.md 文字未同步 |
| 多視角審查發現規則 vs 實作分歧 | linux/saffron/basil 對 PM 的 ANA 結論補強指出「實作已選邊但規則未統一」 |

---

## 核心原則

### 為什麼是 DOC 先於 IMP？

| 順序 | 結果 |
|------|------|
| **DOC 先**（推薦） | IMP 派發時 prompt 引用「規則 X 已在 DOC ticket 落地」作為決策依據；agent 無需做設計決策；hook 重構基於 SSOT 描述執行驗收 |
| IMP 先（反模式） | IMP 必須隱式選邊（用哪個規則版本）；後人讀 hook 變更會困惑「規則文件還寫舊版，hook 為何用新版？」；DOC 修訂被迫追隨 hook 既成事實 |

### 三層落地保證

DOC ticket 落地時必須包含：

1. **概念層 SSOT**：建立 `references/<concept>.md` 作為單一定義來源（六欄位語意 SSOT 示範）
2. **規則層**：error-pattern / pm-rules / methodologies 修訂指向 SSOT，不重複定義
3. **行為描述層**：CLI / Hook 文件 / SKILL 描述同步引用 SSOT，並標註「過渡狀態」段落（如「W15-003 升級為過渡狀態，IMP 收斂後將回到設計意圖」）

---

## 實施步驟

### Step 1：識別語意分裂

| 線索 | 確認方法 |
|------|---------|
| 文件規則互相矛盾 | grep 跨多個文件的相關概念，列出每處主張 |
| Hook 行為違反某文件描述 | 讀 hook 對應段落程式碼，比對文件描述 |
| 多視角審查（linux + 領域 expert）共識指出分歧 | parallel-evaluation 結論 |

### Step 2：決定主導路線

| 決策依據 | 範例 |
|---------|------|
| 較新規則的設計意圖 | PC-091（2026-04-18）取代 PC-073（2026-04-17） |
| 行為層已選邊的事實 | acceptance-gate hook 已用 children 路線（PC-091） |
| 多視角審查共識 | linux/saffron/basil 全選 PC-091 |

### Step 3：建立 DOC ticket（規則層先行）

| 內容項 | 動作 |
|--------|------|
| 建立 SSOT 文件 | `references/<concept>.md` 含定義 / 對照表 / 決策樹 / 反模式速查 |
| 修訂衝突 PC / 規則 | 加 deprecated 標註 + 範圍縮限（PC-122）+ 引用 SSOT |
| 同步引用文件 | SKILL.md / methodologies / pm-rules 改為引用 SSOT，不重複定義 |
| 標註過渡狀態 | 在 CLI / Hook 描述段落明示「行為過渡，IMP-X 收斂後恢復」 |

### Step 4：建立 IMP ticket（行為層後續），blockedBy=DOC

| 設計要點 | 說明 |
|---------|------|
| `blockedBy` 強制 | IMP ticket frontmatter 必須 `blockedBy: [<DOC-ticket-id>]`，避免並行造成決策不對齊 |
| Context 引用 SSOT | IMP prompt 引用 SSOT 作為驗收標準；agent 無需做規則決策 |
| 回歸測試覆蓋 | 必加「行為翻轉核心 case」測試（驗證新行為與舊行為的差異） |
| 跨 hook 影響面驗證 | grep 受影響 hook，逐一確認改動無回歸 |

### Step 5：驗證

| 項目 | 檢查方式 |
|------|---------|
| pytest 全綠 | hook 測試套件通過 |
| grep 殘留 | 確認舊 hook / 舊規則描述已全部移除或標註 deprecated |
| SSOT 引用一致 | grep 各引用文件對 SSOT 的描述一致無衝突 |

---

## 例外條件

| 例外 | 適用 |
|------|------|
| 純 hook bug fix（無規則層分歧） | 直接 IMP；規則本來就清楚，hook 只是 bug |
| Hot fix（線上事故，需立即止血） | 先 hot patch，事後補 DOC 整理（事後 DOC 仍必須執行） |

---

## 反模式

| 反模式 | 後果 |
|-------|------|
| 「先改 hook 看測試會不會通過」 | 繞過規則討論的 shortcut；hook 變更會 implicit 鎖死特定 rule 解讀 |
| DOC 與 IMP 並行（無 blockedBy） | 兩 ticket 各自做決策，可能對齊不一致 |
| DOC 只改 PC 不建 SSOT | 衝突在文件層解但概念仍散落，下次仍會分裂 |
| IMP 完成後才補 DOC | 既成事實鎖死規則層彈性；DOC 失去設計討論價值 |

---

## 案例：W17-120 五欄位語意收斂

| Wave | Ticket | 類型 | 動作 |
|------|--------|------|------|
| 父 ANA | W17-120 | ANA | 多視角審查 + 決議 PC-091 路線 |
| 17 | W17-120.1 | DOC | 建立 field-semantics.md SSOT + PC-073 deprecated + PC-091 升格 + 8 文件同步 |
| 17 | W17-120.2 | IMP（blockedBy=.1） | acceptance-gate-hook ana_spawned_checker 退場 + 4 case 回歸測試 |
| 17 | W17-120.3 | DOC（選配，已 close as duplicate） | relatedTo 純 metadata 定位（被 .1 順帶完成） |

實施結果：
- DOC 階段（W17-120.1）落地後，IMP 階段（W17-120.2）派發時 prompt 直接引用「PC-091 路線（W17-120.1 已落地）」作為決策依據，thyme-python-developer 無需做設計決策
- create-command.md:141 在 DOC 階段明示「W15-003 升級為過渡狀態，IMP-2 後將回到不阻擋」——IMP 收斂後自然兌現此承諾
- 4 case 回歸測試含「行為翻轉核心」case (d)，驗證 ANA 有 spawned 但無 children 不再阻擋

---

## 與其他方法論的邊界

| 方法論 | 聚焦 | 與本方法論差異 |
|--------|------|--------------|
| `agile-refactor-methodology.md` | TDD 重構流程 | 本方法論聚焦「規則 vs 實作」分歧的修訂順序，非單純重構 |
| `design-driven-refactoring-methodology.md` | Design-driven 重構 | 本方法論聚焦「規則層 SSOT 落地」作為 IMP 前提，design 是 SSOT 的一部分 |
| `framework-meta-methodology.md` | 框架資產設計通則 | 本方法論是 framework-meta 的子情境（行為-規則分歧時的修訂順序） |

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-122-error-pattern-conflict-not-synced.md` — 衝突未同步反模式
- `.claude/error-patterns/process-compliance/PC-091-ana-followup-as-siblings-not-children.md` — 案例之一
- `.claude/skills/ticket/references/field-semantics.md` — SSOT 範例
- `.claude/methodologies/atomic-ticket-methodology.md` — 父子 ticket 與 blockedBy 設計原則

---

**Last Updated**: 2026-05-03
**Version**: 1.0.0 — 從 W17-120 任務鏈實證提煉（DOC blockedBy 為空 → IMP blockedBy=.1 雙階段順序驗證有效）。Source memory: `feedback_rule_before_hook_refactor_order.md`
