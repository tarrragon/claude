# PC-V1-013: acceptance 用 lenient build 路徑驗證，遮蔽 production-only gate 失敗

## 基本資訊

- **Pattern ID**: PC-V1-013
- **分類**: process-compliance（驗證路徑與出貨路徑不一致）
- **風險等級**: 中
- **關聯**: PC-165（測試綠燈不等於 runtime 正確）、[[feedback-version-bump-worklog-and-prod-build-verify]]（同事件 memory）

## 錯誤症狀

修改通過某 ticket 的 acceptance 驗證並標記完成，但相同邏輯在實際出貨流程（CI / 正式建置）失敗。典型表現：

- acceptance 寫「跑 `build:dev` 確認版本顯示正確」並通過，但出貨用的 `build:prod` / `package:release` 在同一改動上失敗。
- 失敗點是只在 production 模式啟用的守衛（version-check、minify-only 斷言、prod-only 環境變數），dev 模式整段跳過，故 dev 驗證 false-pass。
- 升 package.json / manifest version 後，build:prod 因缺對應 worklog 結構（version-check gate）中止，但 dev 驗證看不到。

## 根因分析

### 根因 1：驗證路徑 ≠ 出貨路徑

acceptance 選了「最方便、最快、最常用」的 build 變體（dev）作驗證，而非實際會送到使用者 / CI 的變體（prod）。當兩條路徑行為不對稱（prod 多一道守衛），dev 綠燈不蘊含 prod 綠燈。這是 PC-165「測試綠燈不等於 runtime 正確」在 build 層的同型變體：lenient 驗證路徑與嚴格出貨路徑的落差。

### 根因 2：production-only 守衛的存在未被納入 acceptance 設計

`scripts/build.js` 的版號守衛只在 `MODE === 'production' && !SKIP_VERSION_CHECK` 啟用（build.js:532）。設計 acceptance 的人未意識到「版本相關改動的真正 gate 在 prod-only 分支」，故驗證指令選了不觸發該 gate 的 dev 模式，gate 失效對 acceptance 不可見。

### 根因 3：升版的隱藏前置依賴未顯性化

升 version 隱含「該版 worklog 結構必須存在」這條前置依賴（build.js version-check 要求 patchDir + mainFile）。此依賴未寫入 ticket 的 where / strategy，執行者只改版號字串，CI 在 build:prod 才暴露缺口。

## 解決方案

### 步驟 1：acceptance 的驗證路徑對齊出貨路徑

涉及 build / 打包 / 發布的 ticket，acceptance 必須用實際出貨指令驗證（`build:prod` / `package:release` / CI dry-run），禁止只用 `build:dev` 等 lenient 變體。dev 僅供開發迭代，不作完成判據。

### 步驟 2：列出 production-only 守衛清單，納入 acceptance

設計 build 相關 ticket 前，先盤點哪些檢查是 prod-only（version-check、log 移除斷言、env gate），acceptance 逐項覆蓋。對照 PC-165：修復鏈 acceptance 必含 runtime / 出貨層級驗證。

### 步驟 3：升版顯性化前置依賴

version bump 的 where / strategy 明列「建 v{ver} worklog 結構」（或先跑 version-release skill 的 start），使隱藏依賴成為可勾選步驟而非執行期才發現。

## 預防措施

- **acceptance 模板**：build / release 類 ticket 的 acceptance 預設填 `npm run package:release` / `build:prod` 通過 + 產出物驗證，PM 派發前在 Context Bundle 明示此前置依賴。
- **派發 prompt**：升版 / 打包類派發明示「驗證用 prod 路徑，dev 不作完成判據」。
- **memory 雙通道**：[[feedback-version-bump-worklog-and-prod-build-verify]] 已固化操作面；本 PC 為流程面 canonical 記錄。

## 實證

v1.4.3 版本：升版 ticket acceptance 寫「build:dev 確認版本 1.4.3」並 false-pass 完成；首次 v1.4.3 tag 觸發 CI 在 `Package production release`（build:prod）失敗於 version-check gate（缺 v1.4.3 worklog 結構）；後續修復 ticket 建 worklog + 本機 package:release 驗證後重建 tag，CI 才全綠並發布 release zip。
