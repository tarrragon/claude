# ARCH-018: Hook 單維度強制與架構規則的交集衝突

## 錯誤症狀

Hook 以「單一維度」（如代理人類型）強制派發行為（如必用 worktree），但架構層另有規則（如 ARCH-015 禁用 worktree 修改 `.claude/`）要求**反向行為**。兩條規則各自合理，交集處卻產生**硬衝突**——任一決策都違反其中一條。

典型表現：
- Hook 規則：「代理人 X 必用 worktree」（保護 .git/HEAD）
- 架構規則：「X 修改 `.claude/` 不能用 worktree」（CC runtime hardcoded）
- 交集情境：X 修改 `.claude/` → 兩條規則直接衝突
- PM 唯一繞路：自己前台做（破壞 PM 職責）

## 根因分析

### 根因 1：Hook 設計時未考慮其他規則的後置約束

Hook 作者專注於自身目的（如 worktree 保護 .git/HEAD），不熟悉 runtime 對 `.claude/` 的 hardcoded 保護（ARCH-015 是後來才被發現和記錄的）。Hook 規則本身無誤，但規則**組合**在特定交集產生矛盾。

### 根因 2：單維度檢查錯失情境豐富度

Hook 檢查只看「代理人類型」，忽略「prompt 內容」所隱含的路徑意圖。同一代理人修改不同路徑應有不同處理：
- 代理人改 `src/` → worktree 有意義
- 代理人改 `.claude/` → worktree 適得其反

單維度檢查無法表達此差異。

### 根因 3：衝突訊號依賴人工發現

兩條規則第一次碰撞前，沒有自動檢測機制。PM 首次踩雷時才發現矛盾，此前所有派發都沉默地被迫走 PM 前台繞路。

## 防護措施

### 規則層：Hook 強制要求需對齊其他架構規則

新增 Hook 強制行為前（尤其派發類 Hook），必須回答：
- 此強制是否與 `.claude/error-patterns/architecture/` 中其他規則衝突？
- 是否有特定 prompt 內容會讓強制失效？
- 最小檢查維度是否足夠？（單維度 vs prompt 內容檢查）

### 設計準則：情境感知優於一律強制

| 設計方式 | 優缺點 |
|---------|--------|
| 一律強制（單維度） | 簡單但易與其他規則衝突 |
| **情境感知（多維度）** | 複雜但能對齊其他約束 |

範例：agent-dispatch-validation-hook 從「代理人類型一律要 worktree」升級為「代理人類型 + prompt 路徑分類」，豁免 `.claude/` 情境（落實 ARCH-015）。

### 交集驗證：跨 Hook/規則一致性檢查

- 新增/修改 Hook 時，對照 `.claude/error-patterns/architecture/` 中既有規則
- 對每條已知 runtime 約束（如 ARCH-015 .claude/ 寫入保護）確認 Hook 行為不矛盾
- 若有矛盾，優先調整 Hook（情境豁免）而非代理人定義或規則

### 檢測手段：PM 前台繞路即訊號

PM 被迫前台執行實作代理人任務（非 RED 測試規格定義）時，應質疑：
- 是否某 Hook × 某架構規則衝突？
- 若是，建 ANA Ticket 分析，後續 IMP 修正 Hook

本 pattern 即透過此手段被發現（W10-039.3 觸發 → W10-041 ANA → W10-042 IMP）。

## 實戰案例

### 2026-04-14：agent-dispatch-validation-hook × ARCH-015

**衝突**：
- Hook：`IMPLEMENTATION_AGENTS`（含 thyme/parsley/cinnamon 等 6 個）一律強制 `isolation: "worktree"`
- ARCH-015：`.claude/` 修改不能用 worktree subagent（CC runtime hardcoded 拒絕 Edit）
- 本專案 Chrome Extension，thyme 幾乎 100% 派發涉及 `.claude/hooks/`，每次派發都撞牆

**觸發**：PM 派發 thyme 處理 W10-039.3（`.claude/hooks/tests/` 測試擴充）時被 Hook 阻擋，改 PM 前台執行。

**解決**：W10-041 ANA 分析三方案，選方案 A（Hook 路徑檢測豁免）。W10-042 實作 `_classify_prompt_paths()` 函式，加入三分類決策：
- 僅 `.claude/` → 放行（ARCH-015 豁免）
- 跨路徑 → 阻擋（要求拆分）
- 僅非 `.claude/` → 原強制 worktree

## 相關規則

- `.claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md` — 衝突的另一方
- `.claude/pm-rules/worktree-operations.md` — `.claude/` 路徑限制章節
- `.claude/rules/core/quality-baseline.md` — 規則 5（發現必追蹤）
- `.claude/pm-rules/pm-quality-baseline.md` — 規則 6（框架優先）

---

**Last Updated**: 2026-04-14
**Version**: 1.0.0 — 初始建立
