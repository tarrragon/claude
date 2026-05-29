# PC-142: Phase 4 Hook 字面抓觸發詞誤判規則引用為延後話術

## 分類

- **類別**：process-compliance
- **嚴重度**：中（false positive 阻擋合法 complete，PM 需手動改寫或加 exempt marker 繞過）
- **狀態**：reproducible（W10-113 / cinnamon Phase 4 / W10-114 / W10-115 共重現 4 次達反模式門檻，跨 session 持續觸發）；case 5（frontmatter YAML 區塊誤判）已由 W1-092 方案 b 結構性修復（commit `de2f82c3`），body 內文規則引用誤判仍依 W10-118 規劃追蹤

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
3. **無欄位類型感知**：frontmatter 的 `how.strategy` / `why` 欄位屬規格元資料，與 body 內延後話術語意層級不同。這些欄位常含階段名稱，包括對 source ticket 歷史脈絡的引用（case 5 即此類，詳見下方「案例 5 詳述」）
4. **無歷史章節豁免**：Phase 1/2/3a 章節記錄 Phase 4 階段規劃是合法歷史脈絡，不應觸發

## 案例重現紀錄

| 案例 | Session | Ticket | 觸發位置 | 處理方式 |
|------|---------|--------|---------|---------|
| 1 | session 2026-05-12 上半 | W10-113 ANA complete | 5 處（acceptance + Problem Analysis + Solution） | 改寫 + frontmatter acceptance 字面替換 |
| 2 | session 2026-05-12 上半 | W10-114 Phase 4 cinnamon | frontmatter `how.strategy` + acceptance 描述 + Phase 1/2/3a 規劃章節 | 局部改寫「Phase4-RefactorReview」+ 加 PC-093-exempt 標記 |
| 3 | session 2026-05-12 上半 | W10-114 complete 自身 | 多處規則引用 | PC-093-exempt 標記 |
| 4 | session 2026-05-12 下半（resume W10-115） | W10-115 complete | 10 處（frontmatter `how.strategy` + AC + Phase 1 spec + Phase 3a TD 表 + Phase 3b 報告 + Context Bundle） | YAML 區 2 處改寫「Phase 4」→「P4」；markdown 區 6 處加 `<!-- PC-093-exempt: tdd-transition / ticket-tracked -->` 標記 |
| 5 | session 2026-05-25（W1-039 complete） | W1-039 complete | frontmatter `why` 欄位引用 source ticket W1-029.1 的「Phase 4 評估發現」歷史脈絡 | 臨時加 `<!-- PC-093-exempt: history -->` marker 通過，complete 後 `git restore` 還原；後續由 W1-092 方案 b 結構性修復 |

### 案例 5 詳述：frontmatter source ticket history 引用（已修復）

**事件**：W1-039（thyme 完成 commit `b7956e14`）執行 `ticket track complete` 時觸發 `phase4-decision-enforcement-hook` 的 PreToolUse 二次掃描。hook 掃描 W1-039.md 的 frontmatter `why` 欄位，命中「Phase 4 評估發現」字面並判為延後話術。該文字實際語意為「W1-029.1（source ticket）在其 Phase 4 階段中發現的問題」，屬 source ticket 歷史脈絡引用，非本 ticket 的延後決策。代理人臨時在 main repo 的 W1-039.md 加 `<!-- PC-093-exempt: history:... -->` marker 通過 hook，complete 後再 `git restore` 還原。

**根因**：frontmatter 是 YAML 結構化元資料，非人類撰寫的決策論述。其 `why` / `title` / `how.strategy` 等欄位可能引用 source ticket 的歷史階段名稱。當時 hook 對 frontmatter 區塊無整段豁免機制：既有 `history` exempt category 雖語意吻合，但需手動插入 HTML comment marker，而 YAML 區塊不支援 HTML comment（插入會破壞 frontmatter 結構）。

**Why**：frontmatter 字面與 body 決策論述的語意層級不同。frontmatter 記錄「這張 ticket 是什麼、源自哪裡」的元資料，引用 source ticket 階段名稱是事實陳述；body 才是「本 ticket 要不要延後」的決策載體。對兩者套用同一字面規則必然產生 false positive。

**Consequence**：任何 ticket 的 frontmatter `why` 含「Phase N 評估 / 決定」等 source ticket 歷史引用都會被攔截，且無法用 marker 合法豁免（YAML 不支援 comment），PM 被迫採「臨時加 marker → complete → git restore」的脆弱 workaround，違反「不修改既成正確產出」原則。

**Action（修復）**：W1-092（commit `de2f82c3`）採方案 b — 新增 `compute_frontmatter_lines()`，在 `scan_lines_for_phrases` 與 `collect_exempt_markers` 內整段跳過 frontmatter YAML 區塊，與 W10-130 Schema placeholder、W11-018 fenced code block 同精神。邊界限「行首僅 `---` 三字元」避免內文水平分隔符誤判結束；未閉合 frontmatter 視為無 frontmatter（容錯，回傳空集合，避免整檔被跳過）。新增 7 個測試覆蓋跳過、內文 regression、`---` 分隔符誤判防護、容錯與 frontmatter 內 marker 不蒐集；W1-039.md 經 PreToolUse simulate 確認 exit 0。

## 防護

### 立即（PM 工作流）

1. **acceptance 字面避免關鍵字**：寫 acceptance 時避免「禁止 Phase 5 再決定」之類直接引用，改用「結論狀態明確並含落地路徑」等正向描述
2. **加 PC-093-exempt 標記**：在規則引用位置加 `<!-- PC-093-exempt: user-override:引用 decision-trigger-binding 規則 1.5 -->`
3. **Phase 規劃章節用代號**：Phase 1/2/3a 引用 Phase 4 階段時，使用代號（如「下一階段重構評估」）

### 已落地（W1-092，frontmatter 維度）

case 5（frontmatter YAML 區塊誤判）已由 W1-092 結構性修復，commit `de2f82c3`。方案 b 以 `compute_frontmatter_lines()` 整段跳過 frontmatter，使 `scan_lines_for_phrases`（phrase 掃描）與 `collect_exempt_markers`（marker 蒐集）對 frontmatter 行一律 short-circuit。此方向對應原 W10-118 規劃的「frontmatter 欄位排除字面匹配」項目，且涵蓋範圍從 `how.strategy` 擴大至整個 frontmatter（含 `why` / `title` 等所有欄位）。

**對 PM 工作流的影響**：frontmatter `why` / `title` / `how.strategy` 含 source ticket 歷史階段名稱引用時，complete 不再被攔截，無須再手動加 marker 後 `git restore`。

### 中期（body 內文維度 / W10-118 ANA 追蹤）

W10-118 ANA（已完成）規劃 4 個 hook 限制收斂方向；frontmatter 面向已如上落地，body 內文層面的其餘方向（落地狀態見 W10-118 spawned tickets）：

- 新增 exempt category `rule-reference`（reason 需含規則路徑引用）
- 加入語意 negation 偵測（前後 50 字含「禁止」「不應」「反模式」豁免）
- 歷史章節（Phase 1/2/3a）標頭範圍排除

## 相關文件

- `.claude/error-patterns/process-compliance/PC-093-yagni-deferred-decision-accumulation.md`（hook 設計原意，本 PC 是其 false positive 子模式）
- `.claude/rules/core/decision-trigger-binding.md` 規則 1.5（被誤判的規則）
- `0.18.0-W10-118`（ANA 追蹤 4 個 hook 限制的修復策略）
- `.claude/hooks/phase4-decision-enforcement-hook.py`（frontmatter 維度已修復，body 內文維度待改善）
- `0.19.0-W1-039`（case 5 事件來源：frontmatter `why` 引用 source ticket 歷史脈絡被誤判）
- `0.19.0-W1-089`（ANA：PC-142 與 PC-077 共振分析，規劃 case 5 落地 DOC-1）
- `0.19.0-W1-092`（IMP：方案 b frontmatter 跳過修復，commit `de2f82c3`）

## 學習要點

| 教訓 | 應用 |
|------|------|
| 字面匹配 hook 必須有「引用 / 歷史 / 元資料」豁免機制 | 設計新 hook 時預留 exempt category 擴展點 |
| Hook 重現 4 次達反模式門檻 = 應升級至 framework 改善 | 不再延後 W10-118 ANA 推進 |
| PM workaround（改寫字面）是訊號不是解法 | 看到反覆 workaround 即時建 PC 並升級 hook |
| 跨 session 持續再現 = 修復優先級應上調 | W10-118 從 P2 評估上調為 P1（hook false positive 阻擋合法 complete 已成穩定模式） |
| frontmatter 是 YAML 結構化元資料，與 body 決策論述語意層級不同 | 字面規則對 YAML 區塊整段豁免（與 Schema placeholder / fenced code block 共用同一抽象），不可與 body 套同規則 |
| 無法用既有豁免機制（marker）合法繞過的 false positive = 結構性缺口 | YAML 不支援 HTML comment marker，迫使 case 5 從 workaround 升級為 hook 整段跳過修復 |

---

**Created**: 2026-05-12
**Updated**: 2026-05-29（W1-093：新增 case 5「frontmatter source ticket history 引用」+ 防護同步 W1-092 方案 b 落地，commit `de2f82c3`）
**Source**: 案例 1-3（W10-113 ANA → W10-114 Phase 4 cinnamon → W10-114 complete）+ 案例 4（W10-115 complete，跨 session resume 後再觸發）+ 案例 5（W1-039 complete，frontmatter `why` 誤判 → W1-089 ANA → W1-092 IMP 修復）
**Related**: PC-093 (parent), W10-118 (improvement ANA, 優先級建議上調 P2→P1, 已完成), W1-039 / W1-089 / W1-092 (case 5 事件 → 分析 → 修復鏈)
