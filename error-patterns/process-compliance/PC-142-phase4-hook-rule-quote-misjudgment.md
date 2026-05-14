# PC-142: Phase 4 Hook 字面抓觸發詞誤判規則引用為延後話術

## 分類

- **類別**：process-compliance
- **嚴重度**：中（false positive 阻擋合法 complete，PM 需手動改寫或加 exempt marker 繞過）
- **狀態**：reproducible（W10-113 / cinnamon Phase 4 / W10-114 / W10-115 共重現 4 次達反模式門檻，跨 session 持續觸發）

## 症狀

執行 `ticket track complete <ticket-id>` 被 `phase4-decision-enforcement-hook` 阻擋，hook 報告偵測到「Phase 4 評估」「Phase 5 再決定」等延後話術，要求二選一執行/移除/豁免。但實際上這些文字屬於：

1. **規則名稱引用**：如 acceptance 「Phase 4 結論禁止 Phase 5 再決定」是引用 `decision-trigger-binding` 規則 1.5 的禁止描述
2. **歷史脈絡記述**：Phase 1/2/3a 規劃章節記錄「Phase 4 評估」階段名稱
3. **frontmatter 合法欄位**：`how.strategy` 欄位含「Phase 4 評估」描述當前 ticket 的階段規劃

PM 被迫採用 workaround：

- 改寫關鍵字（「Phase 5 再決定」→「無 trigger 延後」「Phase4-RefactorReview」）
- 加 `<!-- PC-093-exempt: cat:reason -->` 標記
- 局部重寫整個段落迴避

## 根因

`.claude/hooks/phase4-decision-enforcement-hook.py` 採字面匹配 + 合法 exempt category 白名單（`tdd-transition` / `baseline-gated` / `ticket-tracked` / `user-override`）。

**設計缺口**：

1. **無「規則引用」豁免類別**：規則文件名稱本身含「Phase 4 評估」「Phase 5 再決定」等字眼，當 PM 在 acceptance / Problem Analysis / Solution 章節**引用規則名稱**時 hook 無法區分「真正延後話術」vs「規則引用」
2. **無語意 negation 偵測**：前後文若有「禁止」「不應」「反模式」等 negation 詞，邏輯上是禁止延後而非提倡延後，hook 仍會抓
3. **無欄位類型感知**：frontmatter 的 `how.strategy` 含階段名稱屬規格元資料，與 body 內延後話術語意不同
4. **無歷史章節豁免**：Phase 1/2/3a 章節記錄 Phase 4 階段規劃是合法歷史脈絡，不應觸發

## 案例重現紀錄

| 案例 | Session | Ticket | 觸發位置 | 處理方式 |
|------|---------|--------|---------|---------|
| 1 | session 2026-05-12 上半 | W10-113 ANA complete | 5 處（acceptance + Problem Analysis + Solution） | 改寫 + frontmatter acceptance 字面替換 |
| 2 | session 2026-05-12 上半 | W10-114 Phase 4 cinnamon | frontmatter `how.strategy` + acceptance 描述 + Phase 1/2/3a 規劃章節 | 局部改寫「Phase4-RefactorReview」+ 加 PC-093-exempt 標記 |
| 3 | session 2026-05-12 上半 | W10-114 complete 自身 | 多處規則引用 | PC-093-exempt 標記 |
| 4 | session 2026-05-12 下半（resume W10-115） | W10-115 complete | 10 處（frontmatter `how.strategy` + AC + Phase 1 spec + Phase 3a TD 表 + Phase 3b 報告 + Context Bundle） | YAML 區 2 處改寫「Phase 4」→「P4」；markdown 區 6 處加 `<!-- PC-093-exempt: tdd-transition / ticket-tracked -->` 標記 |

## 防護

### 立即（PM 工作流）

1. **acceptance 字面避免關鍵字**：寫 acceptance 時避免「禁止 Phase 5 再決定」之類直接引用，改用「結論狀態明確並含落地路徑」等正向描述
2. **加 PC-093-exempt 標記**：在規則引用位置加 `<!-- PC-093-exempt: user-override:引用 decision-trigger-binding 規則 1.5 -->`
3. **Phase 規劃章節用代號**：Phase 1/2/3a 引用 Phase 4 階段時，使用代號（如「下一階段重構評估」）

### 中期（hook 邏輯改善 / W10-118 ANA 追蹤）

W10-118 ANA 已建並含完整 4 個 hook 限制收斂方向，包含本案：

- 新增 exempt category `rule-reference`（reason 需含規則路徑引用）
- 加入語意 negation 偵測（前後 50 字含「禁止」「不應」「反模式」豁免）
- frontmatter `how.strategy` 欄位排除字面匹配
- 歷史章節（Phase 1/2/3a）標頭範圍排除

## 相關文件

- `.claude/error-patterns/process-compliance/PC-093-yagni-deferred-decision-accumulation.md`（hook 設計原意，本 PC 是其 false positive 子模式）
- `.claude/rules/core/decision-trigger-binding.md` 規則 1.5（被誤判的規則）
- `0.18.0-W10-118`（ANA 追蹤 4 個 hook 限制的修復策略）
- `.claude/hooks/phase4-decision-enforcement-hook.py`（待改善 hook）

## 學習要點

| 教訓 | 應用 |
|------|------|
| 字面匹配 hook 必須有「引用 / 歷史 / 元資料」豁免機制 | 設計新 hook 時預留 exempt category 擴展點 |
| Hook 重現 4 次達反模式門檻 = 應升級至 framework 改善 | 不再延後 W10-118 ANA 推進 |
| PM workaround（改寫字面）是訊號不是解法 | 看到反覆 workaround 即時建 PC 並升級 hook |
| 跨 session 持續再現 = 修復優先級應上調 | W10-118 從 P2 評估上調為 P1（hook false positive 阻擋合法 complete 已成穩定模式） |

---

**Created**: 2026-05-12
**Updated**: 2026-05-12（W10-115 complete 案例 4 補入，跨 session 再實證）
**Source**: 案例 1-3（W10-113 ANA → W10-114 Phase 4 cinnamon → W10-114 complete）+ 案例 4（W10-115 complete，跨 session resume 後再觸發）
**Related**: PC-093 (parent), W10-118 (improvement ANA, 優先級建議上調 P2→P1)
