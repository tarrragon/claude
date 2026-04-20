# Claude Code Plugin 管理準則

本文件定義 Claude Code plugin（marketplaces 安裝）的安裝前評估、審查週期、卸載流程，防止誤裝或重疊 plugin 膨脹 session context。

> **載入方式**：按需讀取（安裝、評估、定期審查 plugin 時）。非 auto-load，避免本檔本身佔用 context。
>
> **為何需要本準則（Why）**：每個 plugin 可能注入 skills、commands、agents、hooks、MCP tools 至 CC runtime。其中 skill description 會進 SessionStart system-reminder，每個 skill 佔 ~110 tokens/session，170 個 skills 約 ~7-10K tokens 啟動固定開銷。誤裝或功能重疊的 plugin 會造成無謂 token 消耗，並稀釋 LLM attention。
>
> **後果（Consequence）**：配額異常消耗、LLM 決策時將注意力分散到無關 skills、相同功能重複注入（如 document-skills 與 example-skills 的 14+ 重複 skill）。
>
> **下一步（Action）**：新 plugin 安裝前走第 1 章評估清單；每版本完成時走第 3 章審查週期；發現不用的 plugin 依第 4 章卸載。

---

## 1. 安裝前評估清單

安裝任何 plugin 前，逐項回答以下 6 題，**任一項答否即應暫緩安裝**，改採替代方案。

| # | 評估項 | 判定標準 | 如果答否 |
|---|-------|---------|---------|
| 1 | 功能對齊 | 是否解決當前專案的具體需求？ | 暫緩安裝，等需求明確 |
| 2 | 重複性檢查 | 是否已有同名或同類 skill/命令/工具？（查 `.claude/skills/` 與已安裝 plugin） | 不裝；使用現有工具 |
| 3 | 本專案使用頻率預估 | 預期每週使用 >= 1 次？ | 改為 local scope 或不裝 |
| 4 | Token 成本評估 | 注入的 skill 數量與平均描述長度是否可接受？（skills 多 = context 成本高） | 改用 command 或 hook 形式的 plugin |
| 5 | 可逆性 | 卸載流程是否單純（一行指令）？ | 確認後再裝 |
| 6 | 逃生路線 | 卸載後是否有替代手段完成原任務？ | 先準備替代，再決定是否安裝 |

**評估執行指令**：

```bash
# 查已安裝 plugin
cat ~/.claude/plugins/installed_plugins.json | jq 'keys'

# 查專案內建 skills，對照是否重複
ls .claude/skills/

# 查 plugin 原始 marketplace 描述（安裝前）
claude plugin info <plugin-name>@<marketplace>
```

---

## 2. Plugin 注入類型與 context 成本對照

不同 plugin 內容對 session context 的影響差異大。理解各類型成本有助於第 1 章第 4 題的判定。

| 注入類型 | 位置 | Session context 成本 | 代表例 |
|---------|------|--------------------|-------|
| Skills | SessionStart system-reminder | **高**（每 skill ~110 tokens） | document-skills, example-skills |
| Commands（slash commands） | UserPromptSubmit 時解析 | 低（名稱清單） | commit-commands, code-review |
| Agents | 按需載入（派發時） | 低（名稱 + description） | feature-dev, serena |
| Hooks | Runtime 執行，無 prompt 注入 | **無**（但有執行時間成本） | hookify |
| MCP tools | deferred（ToolSearch 發現） | 低（延遲載入） | context7, serena, linear |
| LSP | IDE/編輯器層，非 prompt | **無** | dart-analyzer, marksman-lsp |
| Output styles | CLAUDE.md 級別注入 | 低-中（依 style 設定） | learning-output-style |

**判讀準則**：

- Skills 型 plugin 最昂貴，必須通過第 1 章全部 6 題
- MCP 型 plugin 成本低但需考慮工具發現摩擦（ToolSearch 步驟）
- Hook 型 plugin 無注入成本，主要考慮是否與專案既有 hook 衝突

---

## 3. 已安裝 Plugin 審查週期

定期審查避免歷史遺留的 plugin 長期佔用 context。

| 時機 | 頻率 | 檢查動作 |
|------|------|---------|
| 每 session 啟動 | 自動 | file-size-guardian / session 啟動 log 若顯示 skills 總數異常，觸發第 5 章查詢 |
| 每版本完成時 | 每版本 1 次 | `cat ~/.claude/plugins/installed_plugins.json` 對照第 1 章清單 |
| 每季 | 每季 1 次 | 全面審視：逐 plugin 回顧過去 90 天使用頻率 |
| 配額異常 / context 吃緊 | 即時 | 觸發全面盤點，優先卸載 skills 型重複 plugin |

**提前審查的觸發訊號**：

| 訊號 | 行動 |
|------|------|
| Skills 清單 > 150 個 | 立即走第 3 章每季審查流程 |
| 發現 plugin 在過去 30 天從未被提及或使用 | 標註待觀察，下個版本完成時若仍未用，卸載 |
| 兩個 plugin 功能描述高度重疊 | 擇一保留，另一卸載 |
| CC runtime 升級後出現新版 plugin | 對比舊版差異，決定是否替換 |

---

## 4. 卸載流程

### 基本卸載指令

```bash
# 列出已安裝清單
claude plugin list

# 卸載指定 plugin（名稱@marketplace 格式）
claude plugin uninstall <plugin-name>@<marketplace>

# 範例
claude plugin uninstall example-skills@anthropic-agent-skills
```

### 卸載後驗證步驟

1. 確認 `installed_plugins.json` 不再列出該 plugin：

   ```bash
   cat ~/.claude/plugins/installed_plugins.json | jq 'keys | contains(["<plugin-name>@<marketplace>"])'
   # 應回傳 false
   ```

2. 開新 session，觀察 SessionStart system-reminder 中 skills 清單是否已縮短。

3. 確認原本依賴該 plugin 的工作流是否有替代手段（第 1 章第 6 題已備）。

### 卸載前留痕

卸載前建議記錄理由，避免未來重複評估：

- 在該版本的 worklog 註記卸載理由（如「document-skills 與 example-skills 重複，擇一保留」）
- 若為框架級決策，記至錯誤模式或方法論

---

## 5. 查詢當前已安裝 Plugin 清單

每個專案的使用者環境可能不同，本節提供通用查詢方式，**不硬編碼特定清單**。

### 快速查詢

```bash
# 方法 A：CC CLI
claude plugin list

# 方法 B：直接讀 manifest
cat ~/.claude/plugins/installed_plugins.json | jq 'keys'

# 方法 C：按 scope 過濾
cat ~/.claude/plugins/installed_plugins.json | jq 'to_entries | map(select(.value[0].scope == "user")) | map(.key)'
```

### 交叉比對與分類

```bash
# 比對專案內建 skills 與 plugin 注入 skills 是否重複
ls .claude/skills/ > /tmp/local-skills.txt
# 對照 SessionStart system-reminder 中的 skill 清單，標出同名項目
```

### 分類框架（套用於任一專案）

讀者可用以下分類框架套用到自己的 `installed_plugins.json` 清單：

| 類別 | 判定準則 | 處理方向 |
|------|---------|---------|
| **核心使用中** | 過去 30 天多次觸發 | 保留 |
| **輔助使用** | 偶爾使用，替代成本高 | 保留 |
| **語言/平台工具** | LSP、MCP 等運行時依賴 | 依當前語言需求保留 |
| **可考慮卸載** | 30+ 天未使用或功能重複 | 下個版本完成時卸載 |
| **誤裝** | 安裝後發現與需求不符 | 立即卸載 |

---

## 6. 範例快照（非規範，僅示範分類方法）

以下為某 Chrome Extension 專案於 2026-04-20 的快照示例，**示範如何套用第 5 章分類框架**，非跨專案通用規範。讀者應以自己的 `installed_plugins.json` 實測結果為準。

| Plugin 名稱 | 類別 | 用途說明（示例） |
|------------|------|----------------|
| `context7@claude-plugins-official` | 核心使用中 | 第三方文件查詢 MCP |
| `serena@claude-plugins-official` | 核心使用中 | 語意程式碼操作 MCP |
| `github@claude-plugins-official` | 核心使用中 | GitHub MCP tools |
| `linear@claude-plugins-official` | 核心使用中 | Linear MCP tools |
| `feature-dev@claude-plugins-official` | 輔助使用 | 提供 code-architect/explorer/reviewer 代理人 |
| `code-review@claude-plugins-official` | 輔助使用 | PR 審查 slash command |
| `code-simplifier@claude-plugins-official` | 輔助使用 | 程式碼精簡 skill |
| `commit-commands@claude-plugins-official` | 輔助使用 | commit/PR 輔助 commands |
| `security-guidance@claude-plugins-official` | 輔助使用 | 安全審查 skill |
| `frontend-design@claude-plugins-official` | 輔助使用 | 前端設計 skills |
| `greptile@claude-plugins-official` | 輔助使用 | Greptile MCP |
| `dart-analyzer@claude-code-lsps` | 語言/平台工具 | Dart LSP（若本專案用 Flutter） |
| `explanatory-output-style@claude-plugins-official` | 語言/平台工具 | 輸出風格 |
| `learning-output-style@claude-plugins-official` | 語言/平台工具 | 輸出風格 |
| `document-skills@anthropic-agent-skills` | 可考慮卸載 | PDF/Office skills 注入 ~18 個，若專案不處理 Office 檔案可卸載 |
| `example-skills@anthropic-agent-skills` | 可考慮卸載 | 與 document-skills 重複 ~14 個，擇一保留 |

**重要提醒**：

- 上述分類來自特定專案的使用模式，換一個專案需要重新判定
- 「核心使用中 vs 可考慮卸載」的邊界會隨專案演進移動
- 跨專案共通的判定只有「第 1 章評估清單」和「第 5 章分類框架」

---

## 7. 常見反模式

| 反模式 | 後果 | 正確做法 |
|-------|------|---------|
| 安裝前未走第 1 章評估清單，直接 install | 累積冗餘 plugin，context 膨脹 | 每次 install 前逐題回答 |
| 「以後可能用到」心態保留 plugin | 佔 context 且無實際效益 | 不用即卸，需要時重裝成本低 |
| 兩個功能重疊的 plugin 並存 | 重複注入 skills | 擇一保留，另一卸載 |
| 卸載後未更新 worklog 記錄理由 | 未來重複評估同樣的 plugin | 卸載前在 worklog 記一行理由 |
| 在 session 裡直接抱怨「skills 太多」卻不審查 | 問題未落地 | 觸發第 3 章提前審查流程 |

---

## 8. 與相關工具的關係

| 工具/文件 | 關係 |
|----------|------|
| `.claude/skills/` 專案內建 skills | 本專案的 skill，**不受 plugin 管理**；用於實作專案流程 |
| `.claude/settings.json` | 無 plugin 過濾 API；plugin 管理只能在 CLI 層進行 |
| `installed_plugins.json` | CC runtime 記錄已安裝 plugin 的唯一權威來源 |
| SessionStart system-reminder | 每 session 啟動時顯示當前載入的 skills 清單，是成本監測入口 |

---

## 相關文件

- `.claude/references/framework-asset-separation.md` — 框架資產與專案產物職責分離原則（說明為何 plugin 清單屬於用戶環境而非框架資產）
- `.claude/references/reference-stability-rules.md` — 規則 8：框架文件禁止引用專案層級識別符（本檔採範例快照而非硬清單的理由）
- `.claude/rules/core/document-writing-style.md` — 文件撰寫明示性原則（本檔遵循三明示架構）
- `.claude/skills/search-tools-guide/SKILL.md` — CC Meta-Tools 與 deferred tools 發現機制（影響 MCP plugin 的 context 成本判定）

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 初始建立。從 skills 注入成本分析報告提煉跨專案通用的 plugin 管理準則。
