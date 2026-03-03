# Claude AI 開發規範配置標準庫

> **跨專案共享的 Claude Code 開發規範配置**
> 包含 Hook 系統、Agent 配置、方法論文件，支援 TDD 四階段開發流程

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue.svg)](https://claude.com/claude-code)

---

## 📋 目錄

- [關於本 Repo](#關於本-repo)
- [快速開始](#快速開始)
- [目錄結構](#目錄結構)
- [同步機制](#同步機制)
- [配置說明](#配置說明)
- [核心文件索引](#核心文件索引)
- [貢獻指南](#貢獻指南)

---

## 🎯 關於本專案

這個專案是為了維護一套開發流程，先設計方法論，然後基於方法論轉換成實際執行的 agent ，並且用 hook 機制確保執行的結果符合我們方法論的要求

### 核心內容

| 內容 | 說明 |
|-----|------|
| **TDD 驅動** | 完整的 TDD 四階段流程支援 |
| **Agent 協作** | 代理人自動分工 |
| **Hook 自動化** | Hook 腳本持續品質監控 |
| **方法論完整** | 方法論文件 |

---

## 🚀 快速開始

### 方案 A：新專案首次設置

```bash
# 1. Clone 本 repo 到專案的 .claude 目錄
cd your-project
git clone https://github.com/tarrragon/claude.git .claude

# 2. 複製 CLAUDE.md 和 FLUTTER.md（根據專案類型調整）
cp .claude/CLAUDE.md .
# 如果是 Flutter 專案
cp .claude/FLUTTER.md .

# 3. 調整專案特定配置
vim .claude/settings.local.json

# 4. 複製同步腳本到專案（可選）
mkdir -p scripts
cp .claude/../scripts/sync-claude-*.sh scripts/
chmod +x scripts/sync-claude-*.sh

# 5. 提交到專案 Git
git add .claude CLAUDE.md
git commit -m "feat: 添加 Claude AI 開發規範配置"
```

### 方案 B：從現有專案推送變更

如果你在某個專案中修改了 `.claude` 配置，想推送到本 repo：

```bash
# 使用推送腳本
./scripts/sync-claude-push.sh "描述你的變更"
```

### 方案 C：拉取最新配置

從本 repo 拉取最新配置到你的專案：

```bash
# 使用拉取腳本（自動備份）
./scripts/sync-claude-pull.sh
```

---

## 代理人目錄職責說明

代理人定義檔案統一存放於 `.claude/agents/` 目錄：

| 目錄 | 用途 | 格式 |
|------|------|------|
| `.claude/agents/` | 代理人定義和派發規則 | 完整指令 + YAML frontmatter |

---

## 📁 目錄結構

```text
.claude/
├── README.md                          # 本文件
├── README-subtree-sync.md             # 同步機制詳細說明
├── settings.local.json                # Claude Code 權限配置
│
├── project-templates/                 # 專案模板檔案
│   ├── CLAUDE.md                      # 通用開發規範模板
│   └── FLUTTER.md                     # Flutter 特定規範模板
│
├── hooks/                             # Hook 系統腳本
│   ├── startup-check-hook.sh         # Session 啟動檢查
│   ├── prompt-submit-hook.sh         # 用戶輸入檢查
│   ├── post-edit-hook.sh             # 程式碼變更後檢查
│   ├── tdd-phase-check-hook.sh       # TDD 階段完整性檢查
│   ├── task-avoidance-detection-hook.sh  # 任務逃避偵測
│   └── ...                            # 其他 Hook 腳本
│
├── agents/                            # Agent 配置
│   ├── rosemary-project-manager.md   # 主線程 PM
│   ├── lavender-interface-designer.md # Phase 1 設計師
│   ├── sage-test-architect.md        # Phase 2 測試架構師
│   ├── pepper-test-implementer.md    # Phase 3a 策略規劃
│   ├── parsley-flutter-developer.md  # Phase 3b Flutter 開發
│   ├── cinnamon-refactor-owl.md      # Phase 4 重構專家
│   └── ...                            # 其他專業代理人
│
├── methodologies/                     # 方法論文件
│   ├── agile-refactor-methodology.md # 敏捷重構流程
│   ├── 5w1h-self-awareness-methodology.md  # 決策框架
│   ├── behavior-first-tdd-methodology.md   # 行為優先 TDD
│   ├── hook-system-methodology.md    # Hook 系統設計
│   └── ...                            # 25+ 方法論文件
│
├── commands/                          # Claude Code Slash 命令
│   ├── startup-check.md              # /startup-check 命令
│   ├── commit-as-prompt.md           # /commit-as-prompt 命令
│   └── ...                            # 其他命令
│
├── docs/                              # 文件整合專家支援文件
│   ├── thyme-documentation-integrator-usage-guide.md
│   ├── thyme-mcp-integration-guide.md
│   └── thyme-troubleshooting-guide.md
│
├── scripts/                           # 工具腳本
│   ├── cleanup-hook-logs.sh         # 清理 Hook 日誌
│   ├── pm-status-check.sh            # PM 狀態檢查
│   └── ...                            # 其他工具
│
├── templates/                         # 模板文件
│   ├── work-log-template.md         # 工作日誌模板
│   └── ticket-log-template.md       # Ticket 模板
│
└── hook-logs/                        # Hook 執行日誌（自動生成）
    ├── startup-*.log
    ├── prompt-submit-*.log
    └── ...
```

---

## 🔄 同步機制

### 方式 A：使用 Slash Commands（推薦）

**在 Claude Code 中直接使用 Slash Commands 進行同步**：

#### `/sync-push` - 推送配置到獨立 Repo

在專案中改進了 `.claude` 配置後，可以直接推送到本 repo：

```bash
# 在 Claude Code 中執行
/sync-push
```

**執行流程**：

1. 自動檢查 `.claude` 相關變更是否已提交
2. 詢問提交訊息（或提供預設選項）
3. 執行推送腳本將變更推送到本 repo
4. 驗證推送結果並顯示確認訊息

**使用時機**：

- 新增或修改 Hook 腳本
- 更新方法論文件
- 改進 Agent 配置
- 任何值得跨專案共享的配置改進

#### `/sync-pull` - 拉取最新配置

從本 repo 拉取最新配置到你的專案：

```bash
# 在 Claude Code 中執行
/sync-pull
```

**執行流程**：

1. 自動備份當前 `.claude` 配置
2. 從本 repo 拉取最新配置
3. 驗證拉取結果
4. 提供衝突解決指引（如有需要）

**使用時機**：

- 啟動新專案，想使用最新配置
- 定期同步其他專案的改進
- 修復配置問題時回到已知良好狀態

### 方式 B：使用同步腳本

**適合需要更多控制的場景**：

#### 推送變更到本 Repo

當你在專案中改進了 `.claude` 配置或專案模板，可以推送回本 repo 供其他專案使用：

```bash
# 1. 確保變更已提交到專案 Git
git add .claude CLAUDE.md FLUTTER.md
git commit -m "feat: 改進 Hook 系統配置"

# 2. 推送到本 repo
./scripts/sync-claude-push.sh "feat: 改進 Hook 系統配置"
```

**推送內容**：

- `.claude/` 目錄所有檔案（Hook、Agent、方法論）
- `CLAUDE.md` 通用開發規範
- `FLUTTER.md` Flutter 特定規範

**推送機制說明**：

- 使用臨時 repo + force push 避免複雜的 Git 歷史
- 會覆蓋遠端歷史（單一來源原則）
- 推送前請確保配置已在專案中測試通過

#### 拉取最新配置

從本 repo 拉取最新配置和專案模板到你的專案：

```bash
# 拉取並自動備份
./scripts/sync-claude-pull.sh
```

**拉取內容**：

- `.claude/` 目錄所有檔案（Hook、Agent、方法論）
- `CLAUDE.md` 通用開發規範（更新到專案根目錄）
- `FLUTTER.md` Flutter 特定規範（更新到專案根目錄）

**拉取機制說明**：

- 自動備份當前配置和專案模板到臨時目錄
- Clone 本 repo 並替換專案的 `.claude` 和模板檔案
- 拉取失敗可使用備份還原

### 詳細同步說明

完整的同步機制說明請參考：[README-subtree-sync.md](./README-subtree-sync.md)

---

## ⚙️ 配置說明

### settings.local.json

這是 Claude Code 的權限配置文件，定義哪些命令可以自動執行：

```json
{
  "permissions": {
    "allow": [
      "Bash(flutter clean:*)",
      "Bash(dart test:*)",
      "mcp__serena__find_symbol",
      "mcp__context7__get-library-docs",
      ...
    ]
  }
}
```

**重要**：每個專案可能需要調整權限列表，根據專案需求添加或移除權限。

### Hook 系統配置

Hook 系統會自動執行品質檢查，主要包括：

| Hook | 觸發時機 | 功能 |
|------|---------|------|
| **SessionStart** | Session 啟動 | 環境檢查、文件同步確認 |
| **UserPromptSubmit** | 用戶輸入 | 5W1H 合規、TDD 階段檢查 |
| **PostEdit** | 程式碼變更 | 程式異味偵測、文件更新提醒 |
| **TaskAvoidance** | 持續監控 | 偵測任務逃避行為 |

詳細說明請參考：[hook-system-methodology.md](./methodologies/hook-system-methodology.md)

---

## 核心文件索引

### 必讀文件（建議閱讀順序）

1. **[tdd-collaboration-flow.md](./tdd-collaboration-flow.md)** - TDD 四階段開發流程
2. **[document-responsibilities.md](./document-responsibilities.md)** - 文件寫作規範
3. **[agent-collaboration.md](./agent-collaboration.md)** - Agent 協作模式
4. **[code-quality-examples.md](./code-quality-examples.md)** - 程式碼品質範例

### 方法論文件

**核心流程**：

- [agile-refactor-methodology.md](./methodologies/agile-refactor-methodology.md) - 敏捷重構方法論
- [5w1h-self-awareness-methodology.md](./methodologies/5w1h-self-awareness-methodology.md) - 5W1H 決策框架
- [hook-system-methodology.md](./methodologies/hook-system-methodology.md) - Hook 系統設計

**測試策略**：

- [behavior-first-tdd-methodology.md](./methodologies/behavior-first-tdd-methodology.md) - 行為優先 TDD
- [bdd-testing-methodology.md](./methodologies/bdd-testing-methodology.md) - BDD 測試
- [hybrid-testing-strategy-methodology.md](./methodologies/hybrid-testing-strategy-methodology.md) - 混合測試策略

**程式碼品質**：

- [natural-language-programming-methodology.md](./methodologies/natural-language-programming-methodology.md) - 自然語言化撰寫
- [comment-writing-methodology.md](./methodologies/comment-writing-methodology.md) - 註解撰寫規範
- [package-import-methodology.md](./methodologies/package-import-methodology.md) - 導入路徑語意化

**完整列表**：[methodologies/README.md](./methodologies/README.md)

### Agent 配置

**TDD 四階段專業代理人**：

- **Phase 1**: [lavender-interface-designer.md](./agents/lavender-interface-designer.md) - 功能設計
- **Phase 2**: [sage-test-architect.md](./agents/sage-test-architect.md) - 測試設計
- **Phase 3a**: [pepper-test-implementer.md](./agents/pepper-test-implementer.md) - 虛擬碼以及 模擬流程圖
- **Phase 3b**: [parsley-flutter-developer.md](./agents/parsley-flutter-developer.md) -  針對不同語言設計的實作代理人，比如flutter代理人會要求透過 dart mcp 去輔助開發 
- **Phase 4**: [cinnamon-refactor-owl.md](./agents/cinnamon-refactor-owl.md) - 重構執行

**專案管理**：

- [rosemary-project-manager.md](./agents/rosemary-project-manager.md) - 主線程 PM

**文件整合**：

- [thyme-documentation-integrator.md](./agents/thyme-documentation-integrator.md) - 文件整合專家

**完整列表**：20+ 專業代理人配置

---

## 📖 延伸閱讀

### 官方文件

- [Claude Code 官方文件](https://docs.claude.com/claude-code)
- [Hook 系統開發指南](./docs/hooks/README.md)

### 相關專案

- 本配置基於實戰專案 [book_overview_app](https://github.com/tarrragon/book_overview_V1) 開發和驗證

---

## 📄 授權

本專案採用 MIT 授權條款。

---

**最後更新**: 2025-10-17
**維護者**: [@tarrragon](https://github.com/tarrragon)
**問題回報**: 在使用本配置的專案中建立 Issue
