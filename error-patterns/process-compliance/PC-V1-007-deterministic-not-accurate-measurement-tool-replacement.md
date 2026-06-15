---
id: PC-V1-007
title: 確定性 ≠ 準確性 — 量測工具確定化未驗證複現原始分析意圖
category: process-compliance
severity: high
status: active
created: 2026-06-15
related:
- PC-165
- PC-168
- PC-182
---

# PC-V1-007: 確定性 ≠ 準確性 — 量測工具確定化未驗證複現原始分析意圖

把一個非確定性量測 / 判定工具（如 LLM 手動判讀、啟發式掃描）改寫為確定性 CLI 時，達成「確定性」（同一輸入連續多次輸出逐字一致）不等於達成「準確性」（輸出複現了原始分析建立的權威結論）。若 acceptance 只要求確定性 + synthetic fixture 測試綠燈，工具可能從「不確定地錯」退化為「穩定地錯」——每次都給同一個錯誤數字，反而更難察覺偏差。

**Why**：確定性與準確性是兩個正交維度。確定性由「固定排除規則 + 穩定排序」保證，可用受控 fixture 完整驗證；準確性則取決於排除規則是否真的覆蓋原始分析（人工判讀）所涵蓋的所有類別，只能對 live 真實資料抽樣比對才能驗證。synthetic fixture 測試刻意用小型受控資料（避免依賴會變動的 live 樹），這個正確的測試設計決策恰恰使測試無法揭露「排除規則覆蓋面不足」——fixture 只含測試作者想到的類別，漏掉的 false positive 類別在 fixture 中根本不存在。

**Consequence**：

| 層級 | 影響 |
|------|------|
| Gate 可信度 | 確定化後的 gate 看似「可重現 = 可信」，實則系統性高估 / 低估；以此為 baseline 的下游決策（清理純度、delta 比較）建立在偏差值上 |
| 偵測難度 | 非確定性錯誤會因數字跳動引人警覺；確定性錯誤每次同值，反而被當成「穩定權威值」直接採信 |
| 測試承諾 | synthetic fixture 全綠營造「已驗證」假象，但覆蓋的是「確定性 + 已知類別」，未覆蓋「排除規則對 live 全類別的準確性」 |
| 追溯成本 | 偏差只在有人拿原始分析的權威值（如 ANA baseline 164）對照 live 輸出（237）時才暴露，缺此對照即靜默通過 |

**Action**：

1. 當 ticket 目標是「用確定性工具複現先前分析建立的權威計數 / 分類」時，acceptance 必須含**對 live 真實資料的準確性驗證**（抽樣比對 + 與原始分析的權威值對照），而非僅「連續 2 次一致」+ synthetic fixture 綠燈。確定性驗收與準確性驗收是兩條獨立 acceptance，缺一不可。
2. Phase 4（或驗收）必須明確問：「確定性工具的 live 輸出是否落入原始分析的權威區間？落差是合法的資料演化（樹成長）還是排除規則覆蓋不足？」對落差抽樣 triage，區分 false positive 與真實變化。
3. synthetic fixture 測試設計（為避免依賴變動 live 樹，屬正確決策）必須額外配一個「live smoke + 權威值對照」驗證，否則 fixture 的封閉性會遮蔽排除規則的覆蓋缺口。
4. 規則語言提醒：替換非確定性量測工具時，「確定性」是必要非充分條件。本 PC 與 [[PC-165]]「測試綠燈不等於 runtime 正確」、[[PC-168]]「flaky baseline 少量 sample 推導 stable 錯覺」、[[PC-182]]「UI 測試綠燈但 runtime 路徑不可達」同屬「驗證維度錯配」家族——綠燈 / 確定 / 穩定 / 可達都不蘊含「正確」。四者差異在錯配的具體維度：PC-165 是斷言覆蓋落差，PC-168 是 sample 不足，PC-182 是測試路徑與 runtime 路徑脫節，本 PC 是確定性取代準確性。

---

## 觸發案例

### W8-030.1 → W8-047：broken-link CLI 確定化但高估 42%（2026-06-15）

**背景**：broken-link-check 原為 LLM 手動執行的 SKILL（Glob + Grep + 逐條判讀），三個排除旋鈕（code block / migration-backups / placeholder 範例）的主觀判讀組合使計數浮動於 164~270（兩次執行報 258 vs 155）。ANA W8-030 透過確定性重現實驗確立權威 baseline = 164（curated + 排除 code block + 排除 placeholder），並 spawn W8-030.1 建確定性 CLI 取代之。

**事件鏈**：

1. **W8-030.1 Phase 1-3b**：完整 TDD 建 `scan_links.py`，30 個 synthetic fixture 測試全綠。acceptance 三條（確定性 / skill 路由 / 輸出 schema）全達成——確定性實證為「live 樹連續 2 次 `--format json` diff 為空」（md5 逐字一致）。
2. **確定性達成但數字異常**：live 預設執行回報 broken_count = **237**，而 ANA 權威 baseline 為 **164**。30 個測試全綠無法揭露此落差——fixture 斷言的是「已知 broken_count == 1」的受控小資料，不含 live 樹的 false positive 類別。
3. **W8-030.1 Phase 4 強制加任務 B（分類正確性驗證）**：cinnamon 對 237 條全量 token 掃描，發現約 99 筆（42%）為 false positive，根因為兩處排除規則覆蓋不足——(a) backup 排除單向不對稱（僅過濾 resolved target 端，未排除 source 檔在 `migration-backups/`，30 筆）；(b) placeholder 樣式集過窄（4 項 exact-match，漏 glob `*` 46 / 角括號 `<>` 8 / 模板 `{}` 13 / xxx-TEST token 9）。
4. **W8-047 修正**：backup 來源端對稱排除 + placeholder 改樣式偵測，live 預設計數 237 → **139**（落入 ANA「真實斷鏈約 140±」估計區間）。44 測試綠（既有 30 + 新增 14）。

**關鍵教訓**：若 W8-030.1 Phase 4 未強制「對 live 資料抽樣 + 對照 ANA 權威值 164」的準確性驗證，僅憑「30 測試綠 + 確定性 diff 為空」即 complete，會交付一個「穩定高估 42%」的 gate——下游 W8-034 清理會以 237 為斷鏈 baseline，污染清理純度。確定性把「LLM 不確定地錯」變成「CLI 確定地錯」，後者反而更隱蔽。

**防護落地**：本案 Phase 4 任務 B 即為 Action 2 的實踐（強制 live 抽樣 + 權威值對照），成功在 complete 前攔截。固化為本 PC，使「確定化量測工具須驗證準確性」成為此類 ticket 的 acceptance 設計預設。
