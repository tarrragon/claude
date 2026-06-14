# Hook 降級觀察追蹤

> **用途**：本檔為 `.claude/methodologies/hook-system-methodology.md` 的衛星參考檔，存放 8 Hook 降級觀察期完整追蹤表、Rollback 觸發條件、快速恢復 SOP 與歷史觀察期評估結果。需要查特定 Wave 的觸發數據、執行 Hook rollback、評估觀察期收斂/延長時按需讀取。
>
> **核心方法論（生命週期階段 + 降級機制定義 + 觀察期啟動/結束標準）**：`.claude/methodologies/hook-system-methodology.md`「Hook 生命週期與降級觀察」章節。
> **operations 詳解（Hook 設計決策樹 + 反模式 + 降級檢查清單）**：`.claude/references/hook-system-operations.md`。

---

## 背景

Phase 3b 候選 hook 量化分析（11 hook，3 天觸發頻率：4915 觸發 / 36 Action，< 1%），降級計畫拆 4 子 ticket 執行；P1 + P3 兩階段已完成 8 hook 降級，預估累計削減 Phase 3b Hook 摩擦約 85%。本文件提供觀察期追蹤數據，確保降級後若有未察覺風險可快速 rollback。

---

## 觀察期啟動點

| 階段 | Commit SHA | Git Tag | 涵蓋 Hook | 預估削減 |
|------|-----------|---------|----------|---------|
| P1 baseline | `05f328b7` | `hook-downgrade-p1-baseline` | parallel-dispatch-verification / bash-edit-guard / acceptance-gate | ~50% |
| P3 baseline | `4a225bcf` | `hook-downgrade-p3-baseline` | worklog-format-check / utf8-integrity-check / language-guard / comment-qa / file-type-permission | 加權至 ~85% |

**觀察期長度**：2 Wave（自 P3 baseline 起算；P1 與 P3 可獨立 rollback）。

---

## 降級機制驗證樣本

> 降級機制定義（觸發消除 vs 處理降級）與修正預估公式見核心方法論「降級機制」章節。本節記錄本案驗證樣本。

**驗證樣本**：本案 1 hook 觸發消除（parallel-dispatch, 佔 25.6%）+ 7 hook 處理降級（佔 74.4%）-> 預估 = 25.6% × 100% + 74.4% × 75% = **81.4%**。vs 實測 **81.9%**，偏差 0.5 ppt。

---

## 8 Hook 觸發頻率與 Action 比追蹤表

每 Wave 結尾（PM 在版本回顧 / Wave 收斂時）更新本表。資料來源：

| 來源 | 路徑 | 用途 |
|------|------|------|
| Hook log | `.claude/hook-logs/<hook-name>/` | 觸發次數（按日期 grep INFO 入口行） |
| Sampling counter | `.claude/hook-logs/_sampling/<hook>.count` | 候選 3 抽樣 hook 的累計觸發 |
| Action 紀錄 | hook log 中的 deny / warning 輸出 | Action 比分子 |

### 追蹤表（每 Wave 更新一列）

| Wave | 日期 | Hook | 觸發次數 | Action 次數 | Action 比 | 變化 vs baseline | 備註 |
|------|------|------|---------|------------|----------|----------------|------|
| baseline | 2026-05-06 | parallel-dispatch-verification | 1586 | 0 | 0% | — | 量化分析 3d 統計 |
| baseline | 2026-05-06 | bash-edit-guard | 1662 | ~0 | <1% | — | 同上 |
| baseline | 2026-05-06 | acceptance-gate | 1667 | 36 | 2.2% | — | 同上 |
| baseline | 2026-05-06 | worklog-format-check | — | — | — | — | 候選 3 抽樣 N=10 |
| baseline | 2026-05-06 | utf8-integrity-check | — | — | — | — | 候選 3 抽樣 N=10 |
| baseline | 2026-05-06 | language-guard | — | — | — | — | 候選 3 抽樣 N=10 |
| baseline | 2026-05-06 | comment-qa | — | — | — | — | 候選 4 matcher 限定 |
| baseline | 2026-05-06 | file-type-permission | 285 (3d) / 95 日均 | 2 | 0.7% | — | 候選 1 提醒級別降級；降級執行後補錄 pre-baseline 數據 |
| Wave +1 (2026-05-07) | 2026-05-07 | parallel-dispatch-verification | 132 (1.5d) / 88 日均 | 0 | 0% | -83.2% | 完全從 settings.json 移除 |
| Wave +1 (2026-05-07) | 2026-05-07 | bash-edit-guard | 439 (1.5d) / 293 日均 | 0 | 0% | -46.2% | 邏輯簡化但 matcher 未縮減；削減幅度低於預期 |
| Wave +1 (2026-05-07) | 2026-05-07 | acceptance-gate | 440 (1.5d) / 293 日均 | 10 | 2.3% | -46.2% | Fast-path 65% 命中但仍 spawn Python；削減幅度低於預期 |
| Wave +1 (2026-05-07) | 2026-05-07 | worklog-format-check | 68 (1.5d) / 45 日均 | 0 | 0% | -57.2% | 抽樣 counter=20；fast-path 已減 |
| Wave +1 (2026-05-07) | 2026-05-07 | utf8-integrity-check | 68 (1.5d) / 45 日均 | 0 | 0% | -57.2% | 抽樣 counter=44 |
| Wave +1 (2026-05-07) | 2026-05-07 | language-guard | 22 (1.5d) / 15 日均 | 0 | 0% | -34.3% | 抽樣 counter=4；觸發基數小，誤差較大 |
| Wave +1 (2026-05-07) | 2026-05-07 | comment-qa | 68 (1.5d) / 45 日均 | 0 | 0% | -57.2% | matcher 限定生效 |
| Wave +1 (2026-05-07) | 2026-05-07 | file-type-permission | 61 (1.5d) / 41 日均 | 5 | 5.5% | -57.2% 但 Action 比 ×7.8 | rollback 條件命中（Action 比 > baseline×2 且 > 1%）；延長觀察期評估 |
| Wave +1 結論 | 2026-05-07 | 加權合計 | 1298 (1.5d) / 865 日均 | 15 | — | -57.8% (vs 預估 -85%, 差距 27.2 ppt) | bay-quality-auditor 審計，信心度 0.75（觀察期 1.5d < 1 Wave）；觸發 acceptance #4 -> 延長觀察期 |
| Extended | 2026-05-11 | parallel-dispatch | 0 (5.5d) / 0 日均 | 0 | 0% | -100% | 完全移除，觸發消除 |
| Extended | 2026-05-11 | bash-edit-guard | 1163 (5.5d) / 211.5 日均 | 0 | 0% | -74.1% | 處理降級，削減收斂 |
| Extended | 2026-05-11 | acceptance-gate | 1167 (5.5d) / 212.2 日均 | — | — | -74.0% | 處理降級，削減收斂 |
| Extended | 2026-05-11 | worklog-format-check | 172 (5.5d) / 31.3 日均 | 0 | 0% | -80.3% | 處理降級（抽樣） |
| Extended | 2026-05-11 | utf8-integrity-check | 172 (5.5d) / 31.3 日均 | 0 | 0% | -80.3% | 處理降級（抽樣） |
| Extended | 2026-05-11 | language-guard | 49 (5.5d) / 8.9 日均 | 0 | 0% | -73.4% | 處理降級（抽樣），基數小 |
| Extended | 2026-05-11 | comment-qa | 172 (5.5d) / 31.3 日均 | 0 | 0% | -80.3% | 處理降級（matcher 限定） |
| Extended | 2026-05-11 | file-type-permission | 159 (5.5d) / 28.9 日均 | — | — | -79.7% | 處理降級；Action 比異常消退（May 8-11 TICKET/WORKLOG 命中比 6.2%） |
| Extended 結論 | 2026-05-11 | 加權合計 | 3054 (5.5d) / 555 日均 | — | — | -81.9% (vs 修正預估 -81.4%, 偏差 0.5 ppt) | Extended 觀察期 ANA 落地；信心度 0.95；短期樣本偏差為主因（+24.1 ppt 修正）；file-type-permission rollback 不再命中 |

> **使用方式**：每 Wave 收斂時新增資料列；超過 2 Wave 後依「觀察期結束評估標準」決定收斂或延長。

---

## Rollback 觸發條件

任一條件成立即啟動 rollback SOP。

| 條件 | 訊號 | 嚴重度 |
|------|------|-------|
| False-negative 出現 | 降級後遇到該 hook 原本應擋的反模式案例（PC 新增或既有 PC 案例增量） | 高（立即 rollback 對應 hook） |
| Action 比異常上升 | 觀察期 Action 比相對 baseline > 2x（且絕對值 > 1%） | 中（評估後 rollback 或調整抽樣 N） |
| 觸發頻率異常上升 | 降級後觸發頻率反而高於 baseline 50%+ | 中（檢查降級邏輯是否破損） |
| 用戶體感劣化回報 | 連續 2+ 案例反映「該擋的沒擋」 | 高（立即 rollback） |
| Sampling counter 異常 | counter 檔不增長 / 暴衝 | 低（先檢查實作再判斷 rollback） |

---

## 快速恢復 SOP

### 場景 A：完全 rollback 一個降級階段

| 階段 | 指令 | 說明 |
|------|------|------|
| P1 整批 rollback | `git revert 05f328b7` | parallel-dispatch / bash-edit-guard / acceptance-gate 全部恢復 |
| P3 整批 rollback | `git revert 4a225bcf` | worklog-format / utf8-integrity / language-guard / comment-qa / file-type-permission 全部恢復 |

P1 與 P3 commit 獨立，可分別 rollback 不互相干擾。

### 場景 B：單一 hook rollback（精準恢復）

1. `git show 05f328b7 -- .claude/hooks/<hook-name>.py .claude/settings.json` 取得降級前後 diff
2. 用 `git checkout <pre-baseline-sha> -- .claude/hooks/<hook-name>.py` 還原該檔
3. 若涉及 settings.json 區段（如 parallel-dispatch-verification 的註冊），手動 patch 對應 PostToolUse 區段
4. 新建 commit：`refactor(rollback): 還原 <hook-name> 降級（觀察期觸發 X 條件）`

### 場景 C：抽樣 N 值調整（不 rollback，僅微調）

候選 3 抽樣機制 hook（worklog-format / utf8-integrity / language-guard）若觀察到 false-negative 但不需完全 rollback：

1. 編輯對應 hook 的 `SAMPLE_N` 常數（從 N=10 降至 N=5 或 N=3）
2. 清除 counter：`rm .claude/hook-logs/_sampling/<hook>.count`（讓新 N 從 0 起算）
3. commit：`tune(<hook>): 抽樣 N 從 10 調整至 X（觀察期 Action 比 Y%）`

---

## 觀察期結束評估標準

> 收斂/延長三項判斷標準見核心方法論「觀察期啟動與結束標準」。本節記錄本案歷史評估結果。

### Wave +1 評估結果（2026-05-07）

| 判斷項 | 結果 | 評估 |
|--------|------|------|
| False-negative 案例 | 0 件 | 收斂 |
| Action 比變化 | file-type-permission: 0.7% -> 5.5%（× 7.8 倍且 > 1%） | 延長（rollback 條件命中 1 項） |
| 用戶體感 | 無劣化回報 | 收斂 |

**綜合判斷**：延長觀察期。已建立延長觀察期追蹤，涵蓋三項議題：（1）預估方法論偏差（57.8% vs 85%）；（2）bash-edit-guard / acceptance-gate 進一步降級評估；（3）file-type-permission Action 比異常評估（決定 rollback / 調整 / 偶發接受）。觀察期延長至追蹤 ticket 完成後重新評估。

### Extended 觀察期評估結果（2026-05-11）

| 判斷項 | 結果 | 評估 |
|--------|------|------|
| False-negative 案例 | 0 件 | 收斂 |
| Action 比變化 | file-type-permission 異常消退（Extended 期間 TICKET/WORKLOG 命中比 6.2%，部署日波動） | 收斂 |
| 用戶體感 | 無劣化回報 | 收斂 |
| 削減比 vs 修正預估 | 81.9% vs 81.4%（偏差 0.5 ppt） | 收斂（< 20% 門檻） |

**綜合判斷**：三項判斷皆收斂。Extended 觀察期 ANA 結論：（1）預估方法論已修正（核心方法論新增兩類機制定義與公式）；（2）bash-edit-guard / acceptance-gate 維持現狀，不進一步降級；（3）file-type-permission 不 rollback，偶發接受。降級為長期生效。

---

## 與降級驗證的銜接

降級驗證（驗證 85% 削減）依賴本觀察期數據：

| 啟動條件 | 說明 |
|---------|------|
| 至少 1 Wave 觀察期完成 | 追蹤表至少有 1 筆 Wave +1 資料 |
| 無 rollback 觸發條件命中 | 觀察期內未啟動任何 rollback SOP |
| Hook log 充足 | 8 hook 在觀察期內均有觸發紀錄（避免 zero-data 評估） |

降級驗證啟動時讀取本文件追蹤表，用觀察期數據驗證 ~85% 削減假設是否成立。

---

## 相關文件

- `.claude/methodologies/hook-system-methodology.md` — Hook 系統核心方法論（生命週期 + 降級機制定義 + 觀察期標準）
- `.claude/references/hook-system-operations.md` — Hook 設計決策樹、反模式、降級檢查清單
- `.claude/methodologies/friction-management-methodology.md` — Hook 降級的上位摩擦力管理理論

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 — 從 hook-downgrade-observation.md 外移（W8-020.6 hook 家族整併）：8 Hook 降級觀察期追蹤表、Rollback 觸發條件、快速恢復 SOP（場景 A/B/C）、歷史觀察期評估結果（Wave +1 + Extended）；機制定義與公式上移核心方法論，本檔保留追蹤數據與 SOP
