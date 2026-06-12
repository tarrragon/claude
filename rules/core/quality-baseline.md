# 品質基線規則

本文件定義專案的品質底線要求（所有角色通用，不可協商）。
> **範圍**：規則 1-6 為通用品質底線（PM 和代理人皆 auto-load）。PM 情境專屬規則（框架修改優先、Memory 升級評估）見 `.claude/pm-rules/pm-quality-baseline.md` 按需讀取。

## 核心價值

> 理論依據：Will Guidara《Unreasonable Hospitality》

- **品質承諾** — 100% 測試通過是我們對品質的承諾。
- **成長心態** — 每個挑戰都是成長的機會。
- **架構優先** — 優秀的架構是長期成功的基石。
- **完整體驗** — 完整 TDD 流程（含 SA 前置審查、Phase 1-4）是完整的開發體驗。
- **學習導向** — 測試失敗是發現問題的珍貴時刻。
- **文件即知識** — 所有角色嚴格依文件規則做事。文件遵循開放封閉原則：**開放內容**（通用規則）放自動載入 `rules/`；**封閉內容**（情境細節）放按需讀取 `references/`。

## 強制規則

### 規則 1：測試通過率 100%

**測試通過率必須維持 100%**：提交前所有測試通過、PR 合併 CI 全綠、版本發布完整套件通過。違規處理：測試失敗禁止直接修復，必須派發 incident-responder 分析，遵循 Skip-gate 防護機制。

- **邊界：測試綠燈不等於 Runtime 正確**：100% 通過是必要非充分條件。修復「訊息系統 / 日誌系統 / 跨模組整合」類 bug 時 unit test 綠燈可能遮蔽 runtime 失效（mock 替代真實依賴 + 斷言不檢查訊息文字 + 動態語言靜默忽略多餘參數三層共振）；此類修復 acceptance 必含 runtime 層級驗證。詳見 `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md`。
- **邊界：少量綠燈不等於 always 綠燈**：race / 異步 / 環境敏感類問題 baseline 取樣 N < 5 時連續 GREEN 可能是 flaky 環境的幸運連勝，基於假 baseline 的決策鏈會連鎖崩塌；此類任務派發前 prompt 必須強制 N >= 5 取樣 + 紀錄 GREEN/RED 分佈。詳見 `.claude/error-patterns/process-compliance/PC-168-flaky-baseline-lucky-streak.md`。

### 規則 2：Phase 4 不可跳過

**即使程式碼品質 A+，也必須完成 Phase 4 重構評估**：品質優良仍需評估（可產出「無需重構」結論）；時間緊迫不可跳過；小型修改仍需評估（可能發現周圍技術債務）。**最小產出**：重構需要（是/否）、技術債務（發現/無）、程式碼品質（A+/A/B/C）、結論說明。

### 規則 3：設計問題立即修正

**發現架構或設計問題時，不可延後處理**：架構違規→立即修正或建高優先級 Ticket；命名不一致→當下修正；依賴方向錯誤→停止開發先修架構；測試設計問題→建 Ticket 本版本修復。

### 規則 4：Hook 失敗必須可見

**Hook 失敗不可靜默吞掉，必須對用戶可見**（來源：IMP-003）：Hook 異常必須寫入 stderr（用戶端可見）+ 同時寫檔案日誌（保留完整 traceback）；禁止只記錄日誌檔而不通知用戶。

**擴充：一般程式碼異常可觀測性**（來源：IMP-013）——雙通道要求亦適用所有程式碼異常處理。每個 `except` 區塊必須滿足以下至少一項，否則需在註解說明原因：寫入 stderr（`sys.stderr.write` / `logger.error`）、寫入日誌檔（`logger.info/warning/error`）、只做 `return`/`pass` 時在註解說明。Hook 異常 stderr+日誌皆必須；業務邏輯拒絕日誌必須、stderr 建議。Go/Dart 具體要求見 `.claude/references/observability-rules.md`。

### 規則 5：所有發現必須追蹤

**發現任何問題，無論優先級，都必須建立 Ticket 追蹤。發現即建立，不詢問確認。** 執行期間發現（Ticket 執行中）直接 `/ticket create`，不需詢問用戶確認。高→當前版本（IMP Ticket）；中→pending Ticket 排後續 Wave/版本；低→pending Ticket 排技術債務清理。**禁止行為**：以「進階」「非急需」「後續再說」省略 Ticket；分析結論只追蹤高優先級忽略中低；口頭記錄取代正式 Ticket。

**適用場景**：Ticket 執行中發現技術債/bug/回歸、多視角分析結論、Phase 4 技術債務、incident 分析、SA 審查發現、任何代理人分析報告。完整識別條件見 `.claude/pm-rules/plan-to-ticket-flow.md`。

**ANA Solution 內 spawn 規劃**：Solution 含 IMP/DOC/ANA spawn 規劃表格時，規劃項目即屬「發現」，必須 complete 前轉為實際 ticket（寫入 `spawned_tickets` 或 `children`）或顯性標註豁免理由。

| 情境 | 必要動作 |
|------|---------|
| Solution 含 spawn 規劃表格 | complete 前建對應 ticket，回填 `spawned_tickets` 或 `children` |
| 規劃項目經評估不需建 ticket | Solution 顯性標註「無需建 ticket：[具體理由]」 |
| ANA 由無 create 權限代理人執行（saffron 等） | complete 後 PM 立即驗收 spawn 一致性，缺漏立即補建 |

> **強制層**：acceptance-gate-hook Step 2.5.2 自動偵測 Solution spawn 規劃 vs `spawned_tickets + children` 數量一致性，缺漏阻擋 complete。**Schema 層**：`ticket-body-schema.md` ANA Solution「Spawn 落地確認」子節。背景與案例（W17-162 / W17-167 / PC-093）見 ticket-body-schema.md。

### 規則 6：失敗案例學習原則

**發現疏失時，對流程瑕疵不回退既成工作；提煉教訓、建 Ticket、固化為規則。產出有害者另依規則 3 / skip-gate 處理。** 核心主張：失敗案例暴露系統邊界，資訊密度高於成功案例；發現疏失第一反應是「提煉可學習經驗」而非「回退到正確狀態」；改善計畫與修復架構是正向產物應主動建立。

| 場景 | 禁止行為 | 鼓勵行為 |
|------|---------|---------|
| 派發越界或職責違反（流程瑕疵） | 自動中止並丟棄既成工作（產出無害時） | 工作品質可用則保留，教訓建 ANA + memory |
| 設計錯誤被多視角審查發現 | 歸咎個案、不系統性追蹤 | 升級為 error-pattern 或 methodology |
| 決策失誤事後回顧 | 以「避免犯錯」為由過度保守 | 在相關規則加註觸發案例 |

**豁免邊界**：產出本身有害（資料損壞、架構違規、測試紅燈）時走規則 3 或 skip-gate。**落地通道**：規則 5（ANA/IMP Ticket）+ memory feedback 雙通道；必要時升級為 framework 規則。

## 品質檢查清單

每次提交前確認：測試通過率 100%？Phase 4 評估已完成？無已知設計問題被忽略？技術債務已記錄（如有）？所有分析發現都有對應 Ticket？工作日誌已更新？新功能可觀測性已確認（啟動/異常/狀態 log）？引用一致性已確認（`grep -rl "修改的概念" .claude/`）？修改有對應 Ticket（rules/pm-rules/skills 修改必須有 Ticket，PC-053）？claim 前已處理 AC 漂移偵測輸出（PC-055 / PROP-010）？寫 feedback memory 已執行四問升級檢查（PM 專屬 PC-061 / PC-160，完整四問見 `pm-quality-baseline.md` 規則 7）？

## 底線要求總結

| 要求 | 說明 | 可協商 |
|------|------|--------|
| 測試通過率 100% | 所有測試必須通過 | 否 |
| Phase 4 必須執行 | 不可跳過重構評估 | 否 |
| 設計問題立即修正 | 不可延後處理 | 否 |
| Hook 失敗必須可見 | 禁止靜默失敗 | 否 |
| 所有發現必須追蹤 | 禁止省略任何優先級的問題 | 否 |
| 失敗案例學習原則 | 流程瑕疵不回退、提煉教訓、固化規則 | 否 |

> PM 情境的額外底線要求詳見 `.claude/pm-rules/pm-quality-baseline.md`。本專案所有品質控制、流程檢查、問題追蹤都由 Hook 系統執行，請信任並配合 Hook 系統。

## 相關規則

- `.claude/pm-rules/pm-quality-baseline.md` - PM 情境專屬品質基線
- `.claude/pm-rules/skip-gate.md`、`.claude/pm-rules/tdd-flow.md`、`.claude/pm-rules/incident-response.md`
- `.claude/references/observability-rules.md` - 規則 4 except 區塊 Go/Dart 要求
- `.claude/pm-rules/ticket-body-schema.md` - 規則 5 ANA spawn 落地確認

---
**Last Updated**: 2026-06-12 | **Version**: 3.0.0 — token 收斂：規則 1 兩個邊界段保留主張句 + PC 路由（事件鏈敘事移至 PC-165/168）；規則 4 IMP-013 except 要求濃縮保留；規則 5 ANA spawn 章濃縮為情境動作表 + 路由 ticket-body-schema/acceptance-gate-hook。規則編號與名稱不變（hooks 引用錨點）（1.0.0-W7-004.3）。歷史 2.0–2.5.x 版見 git log。
