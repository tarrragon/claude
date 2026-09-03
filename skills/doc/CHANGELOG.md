# doc 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.12.0 — 元件庫規格模板升為 first-class 文件類型：模板表新增「元件庫規格模板」列（逐元件契約、容器元件排列不變式、禁用對照、豁免清單），使用方式補其 cp 命令，Design System 規格模板列註明其涵蓋範圍為 token 層。模板本身擴為十一欄位契約（語意與內容角色、變體、狀態集、操作機制、尺寸契約、內容政策、slot 契約、組合規則、無障礙、測試契約、反例），形態因素矩陣改為操作方式驅動並補回饋通道、最小命中區、禁放區與安全區。

**Version**: 1.11.0 — 新增 `validate <SPEC-ID>` 子命令：依 frontmatter subdomain 分派章節 schema 驗證（data-contract 驗可攜性邊界原則/A.1-A.6/B.1-B.3/適用判準兩旗標非空；非 data-contract 明確路由 `/spec validate`，exit 0/1/2），對應 `doc_system/commands/validate.py`

**Version**: 1.10.0 — Domain 列表改為指引 `doc domain` 動態查詢，移除他專案（book_overview_app）的 extraction/platform/messaging 等固定清單（違反 framework-asset-separation）

**Version**: 1.9.0 — Domain Map 模板列補 §3 bundle 實作狀態驗證要求（`ls`/`grep` 驗證存在才標「已實作」，PC-APP-012 防護收編自 book_overview_app）

**Version**: 1.8.0 — data-contract 接線 doc create CLI（取代 cp 手動流程，取得自動編號/日期/tracking）+ 新增 `doc next-id` 唯讀查詢子命令

**Version**: 1.7.0 — data contract 升為 first-class 文件類型（五種→六種）：新增 DataContract 列 + data-contract-template 模板 + 使用方式 cp 命令

**Version**: 1.6.0 — domain map 升為 first-class 文件類型（四種→五種）：新增 DomainMap 列 + domain-map-template 模板 + 使用方式 cp 命令；saas 銜接節補「domain map 不因無 saas 而略過」調和說明——非 saas 起手由 version-bootstrap Step 2.5 從 domain-map-template 新建

**Version**: 1.5.0
**Last Updated**: 2026-07-26
