# version-bootstrap 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.5.0 — Step 2 的 L3 元件庫章節檢查項對齊方法論 1.9.0（明示本步驟得先只到清單，契約於地基波補齊，並指名 doc 範本）；Step 4.5 四塊表插入 3.5「元件契約」（程序見 `component-contract-design` skill，checkpoint 為契約齊全），PM 工作補元件契約 DOC 票與依賴。動因：多輪審查發現本 skill 對「第四塊之前的契約產出」無承接段落
**Version**: 1.4.0 — 新增 Step 2.6「資料契約產出」於 Step 2.5 與 Step 3 間：依兩旗標判準（引用 `data-layer-contract-methodology.md` 第 2 節，不複寫）決定是否 cp 模板產出資料契約文件；契約條目登錄 traceability 第三軸 `data_contract_tests` 供 Step 5 測試設計盤點缺口
**Version**: 1.3.0 — 新增 Step 2.5「Domain 規劃」於 Step 2 與 Step 3 間：spec FR 填完後、測試設計前產出/更新 domain map（doc domain-map-template），含 saas / standalone 調和語意（domain 規劃是所有規劃波通用步驟，非 saas 專屬）；Step 5 補「消費 domain map 逐 bundle 定測試層」、Step 6 建票來源補「domain map bundle 分層 → domain/data/presentation 切分」（落地 ANA domain 規劃整合結論）
**Version**: 1.2.0 — 新增 Step 4.5「地基波（僅含 UI 提案版本）」於 Step 4 與 Step 5 間：測試設計前依 component-library 方法論〈地基波 build 順序〉編排 i18n / design-system / UX 審查 / 元件庫四塊實作（Why：測試需驗 zh/en overflow 與元件反應，依賴 i18n/元件先存在；實證地基波經指正後手動插入）；Step 2 UI 前置檢查補「design-system spec（用 design-system-spec-template）」檢查項。非 UI 版本略過
**Version**: 1.1.0 — Step 2 新增「UI 類提案元件庫前置檢查」小節：判別提案是否涉及 UI/頁面/元件，涉及則須先確認 design token 層與 L3 元件庫章節存在（缺則先補齊），才可繼續 UI 實作票規劃，落地元件庫雙向約束方法論流程整合點 1
**Last Updated**: 2026-07-21
