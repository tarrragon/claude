# 規則系統

> **平台機制**：Claude Code 啟動時自動載入 `CLAUDE.md` + `.claude/rules/**/*.md`。其他 `.claude/` 子目錄不會自動載入，必須主動 Read。

本目錄只放**所有角色通用**的品質規則（集中於 `core/`，現為 17 檔）。PM 流程規則在 `pm-rules/`，技術參考在 `references/`。

**自動載入預算原則**：`core/` 每回合注入 PM 與所有代理人的 context，故只放「每回合都需遵守的行為禁令」；情境性內容（特定流程細節、語言品質規範、按需查表資料）放 `references/` 按需讀取。新增 `core/` 規則前先自問「這是否每回合都需要？」否則放 `references/`。stub 構成標準與外移 SOP（hook 錨點保全、引用鏈同步、預算驗證）→ `.claude/references/auto-load-stub-conventions.md`。

| 目錄 | 載入方式 | 內容 |
|------|---------|------|
| `rules/core/` | 自動載入 | 通用品質基線、Bash 規則、認知負擔、文件格式、語言約束、AI 對話品質 |
| `pm-rules/` | PM 按需讀取 | 決策樹、TDD、Ticket、事件回應、Skip-gate |
| `references/` | PM 與代理人按需讀取 | 語言品質（dart/go/python）、Ticket ID 規範、職責分離原則 |
| `agents/` | 派發時讀取 | 代理人定義（身份、三區塊、偏好、多方案技術知識庫；內容邊界見 knowledge-carrier-allocation） |

**職責分離原則**（設計新規則 / Skill / 文件系統前請讀）：

- 知識該寫進哪個載體（受眾 x 形態地圖、代理人定義內容邊界）→ `.claude/methodologies/knowledge-carrier-allocation-methodology.md`
- 專案設定 vs 代理人知識分離、框架資產 vs 專案產物分離 → `.claude/references/framework-asset-separation.md`

**環境管理原則**（安裝 / 審查 / 卸載 Claude Code plugin 前請讀）：

- Plugin 注入成本、安裝前評估清單、審查週期、卸載流程 → `.claude/references/plugin-management.md`

---

**Last Updated**: 2026-06-12
**Version**: 10.5.0 — 職責分離導航補知識載體地圖路由（入口讀者原僅得二分法拿不到十載體地圖）；agents 列補內容邊界路由（W8 multi-round-review R3）
**Version**: 10.4.1 — references/ 列受眾修正為「PM 與代理人按需讀取」（PM 亦按需讀 references，原描述過窄）
**Version**: 10.4.0 — 預算原則補 stub 規範路由（`references/auto-load-stub-conventions.md`，W7-007）
**Version**: 10.3.0 — 新增「自動載入預算原則」（core/ 僅放每回合行為禁令，情境性內容放 references/）；確認 `core/` 檔數 17 與實際一致
**Version**: 10.2.0 — 更正 `core/` 檔數（原「7 檔」stale，現 17 檔）（文件交叉引用稽核）
**Version**: 10.1.0 — 新增「環境管理原則」導航，指向 `references/plugin-management.md`（避免 plugin 誤裝膨脹 context）
