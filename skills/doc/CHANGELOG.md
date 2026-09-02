# doc 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.11.0 — 新增 `validate <SPEC-ID>` 子命令：依 frontmatter subdomain 分派章節 schema 驗證（data-contract 驗可攜性邊界原則/A.1-A.6/B.1-B.3/適用判準兩旗標非空；非 data-contract 明確路由 `/spec validate`，exit 0/1/2），對應 `doc_system/commands/validate.py`

**Version**: 1.10.0 — Domain 列表改為指引 `doc domain` 動態查詢，移除他專案（book_overview_app）的 extraction/platform/messaging 等固定清單（違反 framework-asset-separation）

**Version**: 1.9.0 — Domain Map 模板列補 §3 bundle 實作狀態驗證要求（`ls`/`grep` 驗證存在才標「已實作」，PC-APP-012 防護收編自 book_overview_app）

**Version**: 1.8.0 — data-contract 接線 doc create CLI（取代 cp 手動流程，取得自動編號/日期/tracking）+ 新增 `doc next-id` 唯讀查詢子命令

**Version**: 1.7.0 — data contract 升為 first-class 文件類型（五種→六種）：新增 DataContract 列 + data-contract-template 模板 + 使用方式 cp 命令

**Version**: 1.6.0 — domain map 升為 first-class 文件類型（四種→五種）：新增 DomainMap 列 + domain-map-template 模板 + 使用方式 cp 命令；saas 銜接節補「domain map 不因無 saas 而略過」調和說明——非 saas 起手由 version-bootstrap Step 2.5 從 domain-map-template 新建

**Version**: 1.5.0
**Last Updated**: 2026-07-26
