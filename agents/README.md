# Agents 索引與職責邊界

本文件為 `.claude/agents/` 目錄的導引，包含代理人完整清單與「文件品質」職責邊界對照表。

---

## 文件品質職責邊界（basil / thyme / mint / bay）

四個代理人的「文件品質」職責在概念上容易混淆。本表以 PM 派發角度明示邊界，避免「該派 thyme 還是 basil」的決策摩擦。

**Why**：thyme 的 v2.0 以前 description 含「文件品質檢查」，與 basil-writing-critic 的「文字品質審查」概念交集；W17-066 linux L-W2 審查將此列為 Warning，要求 IMP 階段重寫（W17-069 執行）。

**Consequence**：邊界不明確時 PM 面臨「要派誰」的模糊決策，實測（W17-048）顯示 PM 在壓力情境下傾向略過審查或重複派發，兩者都造成品質下滑或 token 浪費。

**Action**：PM 派發前對照下表，確認任務歸屬後直接派發對應代理人；若任務跨越兩欄，拆分為獨立任務分別派發。

| 代理人 | 核心定位 | 負責維度 | 不負責 | 產出類型 |
|--------|---------|---------|-------|---------|
| basil-writing-critic | 文字品質常駐審查委員 | 三明示結構（Why/Consequence/Action）/ 資訊優先序（原則先於示例）/ 正面陳述（禁止 X 後附正向錨點）/ 禁用字 / 字元集污染（兜底 fallback，L1 Hook 主責） | 文件結構 / 連結有效性 / 版本一致性 / 格式修正（不修改任何文件，只出具審查報告） | 審查報告（唯讀）|
| thyme-documentation-integrator | 文件結構整合與衝突解決 | 文件結構完整性 / 連結有效性 / 版本一致性 / 工作日誌轉方法論 / 方法論整合到核心文件 / 跨文件衝突解決（引用/定義/版本衝突） | 文字明示性審查（三明示/資訊優先序/隱含表達）—— 發現此類問題時轉發 basil | 修改後的 Markdown 文件 |
| mint-format-specialist | 批量格式化執行者 | Lint 批量修復 / Markdown 格式標準化 / 路徑語意化（大規模執行層修正）| 違規偵測決策（由 basil / Hook 報告後才執行修正）/ 文字品質判斷 | 格式化後的檔案 |
| bay-quality-auditor | 技術品質審計 | 整體技術債務評估 / 安全性 / 穩定性 / 程式碼品質審計（跨 TDD 四階段）| 文字品質 / 文件整合 / 格式修正 | 審計報告（docs/audit-reports/）|

### 快速派發判斷

| 任務描述 | 派發代理人 |
|---------|----------|
| 「這段規則的三明示是否完整？」「有無隱含表達？」 | basil-writing-critic |
| 「這個方法論的引用路徑是否有效？」「版本號是否一致？」 | thyme-documentation-integrator |
| 「工作日誌需要轉化為方法論」 | thyme-documentation-integrator |
| 「新方法論需要整合到 CLAUDE.md」 | thyme-documentation-integrator |
| 「兩個文件對同一概念有矛盾定義」 | thyme-documentation-integrator（確認後修正）|
| 「大量 Markdown 文件需要批量格式化」 | mint-format-specialist |
| 「整體程式碼技術債評估」 | bay-quality-auditor |
| 「文件需要文字審查 + 引用驗證」 | 拆分：basil（文字）+ thyme（引用），分別派發 |

---

## 常駐委員架構（parallel-evaluation）

parallel-evaluation 情境的常駐委員分兩類，詳見 `.claude/skills/parallel-evaluation/SKILL.md`：

| 類型 | 代理人 | 情境覆蓋 | opt-out |
|------|--------|---------|---------|
| `universal_lens` | linux | 所有情境（A-G） | 否，無條件加入 |
| `default_lens_per_scenario` | basil-writing-critic | 情境 C / D / F / G（書面文字產出量高的場景） | 是，`--skip-basil` 可宣告（需說明原因）|

**basil 不加入情境 A / B / E**：標的為程式碼，文字品質審查無法施作，basil 在場無事可做。

---

## 代理人完整清單

### basil 前綴群組命名說明

**Why（共用前綴的理由）**：basil 在香料命名慣例中對應「語言藝術守護者」的次要聯想，適合同時承載「建造複雜結構」（architect）和「審查書面表達」（critic）兩種需要對語言/系統施加紀律的角色。採用共用前綴而非拆分為不同香料，是為了明示這兩類角色同屬「對規則的主動執行者」這一更大族群，便於 PM 在同族代理人間做精確路由。

**architect 與 critic 的角色差異**：

| 角色類型 | 代表代理人 | 核心職責 | 操作方向 |
|---------|-----------|---------|---------|
| architect（建造者） | basil-event-architect, basil-hook-architect | 設計並建造系統結構（事件驅動架構、Hook 系統架構）| 創造：從無到有定義架構邊界、介面、流程 |
| critic（審查者） | basil-writing-critic | 審查書面文字的明示性品質（三明示 / 資訊優先序 / 正面陳述）| 把關：對已存在的文字出具審查報告，不修改文件 |

兩者共同點在於「對複雜結構施加紀律」——architect 是在建造時施加，critic 是在完成後施加。兩者都不負責實作程式碼或格式修正（前者屬 parsley / fennel / thyme-extension-engineer，後者屬 mint-format-specialist）。

**Consequence（不說明差異的後果）**：PM 在需要文字審查時誤派 basil-event-architect，或在需要架構設計時誤派 basil-writing-critic，兩者都會因職責不符而回報空產出，造成 token 浪費與進度停滯。

**未來新增 basil-* 代理人的命名指引**：

1. 先評估新代理人屬 architect（創造結構）還是 critic（把關品質）哪一類
2. 若屬 architect 類：命名為 `basil-{領域}-architect`（例：`basil-api-architect`）
3. 若屬 critic 類：命名為 `basil-{審查對象}-critic`（例：`basil-schema-critic`）
4. 若兩者皆不符：重新評估是否應使用不同香料前綴，避免強行歸入 basil 群組造成語意污染

| 代理人 | 定位摘要 |
|--------|---------|
| basil-event-architect | 事件驅動架構設計 |
| basil-hook-architect | Hook 系統架構設計 |
| basil-writing-critic | 文字品質常駐審查（三明示 / 資訊優先序 / 正面陳述） |
| bay-quality-auditor | 技術品質審計（程式碼 + 測試，獨立於 TDD） |
| cinnamon-refactor-owl | 邏輯重構 |
| clove-security-reviewer | 安全性審查 |
| coriander-integration-tester | 整合測試設計 |
| fennel-go-developer | Go 語言開發 |
| ginger-performance-tuner | 效能調校 |
| incident-responder | 事件回應 / 根因分析 |
| lavender-interface-designer | 介面設計（UI/UX） |
| linux | Good Taste 架構品質審查（universal_lens 常駐委員） |
| mint-format-specialist | 批量格式化 + Lint 修復 |
| oregano-data-miner | 資料挖掘 / 外部搜尋 |
| parsley-flutter-developer | Flutter / Dart 開發 |
| pepper-test-implementer | 測試實作 |
| rosemary-project-manager | PM 主線程（任務拆分 / 派發 / 驗收）|
| saffron-system-analyst | 系統分析 |
| sage-test-architect | 測試架構設計 |
| star-anise-system-designer | 系統設計 |
| sumac-system-engineer | 系統工程 |
| thyme-documentation-integrator | 文件結構整合 / 衝突解決 |
| thyme-extension-engineer | Chrome Extension 開發 |
| thyme-python-developer | Python 開發 |

> DEPRECATED 代理人（john-carmack, memory-network-builder）已在各自檔案開頭標注，不列入上表。

---

**Last Updated**: 2026-04-28
**Version**: 1.1.0 - 新增「basil 前綴群組命名說明」子章節：共用前綴理由、architect vs critic 角色差異表、未來命名指引四步驟（W17-059 / W17-066 saffron warning 1）
