# Claude AI 開發規範配置標準庫

> 跨專案共享的 Claude Code 開發規範配置。
> 包含 Hook 系統、代理人配置、方法論文件，支援 TDD 四階段開發流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 目錄

- [關於本專案](#關於本專案)
- [快速開始](#快速開始)
- [新專案配置指南](#新專案配置指南)
- [目錄結構](#目錄結構)
- [同步機制](#同步機制)
- [代理人職責說明](#代理人職責說明)
- [核心文件索引](#核心文件索引)
- [授權](#授權)

---

## 關於本專案

本專案維護一套完整的 Claude Code 開發流程：先設計方法論，再基於方法論轉換成實際執行的代理人，並用 Hook 機制確保執行結果符合方法論的要求。

| 內容 | 說明 |
|------|------|
| TDD 驅動 | 完整的 SA 前置審查 + TDD 四階段流程 |
| 代理人協作 | 28 個專業代理人自動分工 |
| Hook 自動化 | 49 個 Python Hook 持續品質監控 |
| 方法論完整 | 40+ 份方法論文件 |
| Skill 工具 | 33 個 Skill 指令 |

---

## 快速開始

將本框架配置到新專案的標準流程：

```bash
# 1. Clone 框架到專案的 .claude 目錄
cd your-project
git clone https://github.com/tarrragon/claude.git .claude

# 2. 移除框架的 .git 目錄（避免 submodule 衝突）
rm -rf .claude/.git

# 3. 設定 Hook 執行權限
chmod +x .claude/hooks/*.py

# 4. 執行 project-init onboard（互動式配置）
#    會引導你更新 settings.local.json、調整語言特定配置
/project-init onboard

# 5. 建立 CLAUDE.md（詳見「新專案配置指南 > 建立 CLAUDE.md」）
#    填入專案類型、語言、框架版本、實作代理人

# 6. 提交到專案 Git
git add .claude CLAUDE.md
git commit -m "feat: 添加 Claude AI 開發規範配置"
```

---

## 新專案配置指南

將框架 clone 到新專案後，需要完成以下配置才能正常運作。

### settings.local.json 更新指南

`settings.local.json` 包含 permission 和 Hook 配置。依照以下分類逐項處理：

| 分類 | 項目 | 操作 |
|------|------|------|
| 必須更新 | 含硬編碼路徑的 permission（如 `/Users/xxx/project/xxx`） | 搜尋替換為新專案路徑，或改用相對路徑 |
| 按需調整 | `enabledMcpjsonServers`（如 `["dart"]`） | 非 Flutter 專案移除或替換為對應語言的 MCP server |
| 按需調整 | Flutter/Dart 特定 permission（`flutter test`、`dart analyze` 等） | 非 Flutter 專案移除，替換為對應語言的工具指令 |
| 按需調整 | `WebFetch` domain 白名單 | 根據需要增減 |
| 安全保留 | 使用 `$CLAUDE_PROJECT_DIR` 的 hooks 配置 | 運行時自動解析路徑，無需修改 |
| 安全保留 | 通用工具 permission（`git`、`python3`、`uv run`、`chmod` 等） | 跨專案通用 |
| 安全保留 | Skill permission（`Skill(ticket)`、`Skill(tech-debt-capture)` 等） | 框架內建功能 |
| 建議移除 | 舊專案特定的 shell 迴圈 permission | 一次性操作產生的殘留，新專案不需要 |

快速搜尋硬編碼路徑：

```bash
grep -n '/Users/' .claude/settings.local.json
```

### 環境檢查清單

逐項驗證框架能正常運作：

```bash
# 1. Python 版本（Hook 系統需要 3.9+）
python3 --version

# 2. Hook 執行權限
chmod +x .claude/hooks/*.py

# 3. 驗證 Hook 可編譯（挑選一個核心 Hook 測試）
python3 -m py_compile .claude/hooks/prompt-submit-hook.py

# 4. 驗證 settings.local.json 格式正確
python3 -c "import json; json.load(open('.claude/settings.local.json'))"

# 5. 確認無殘留的硬編碼路徑
grep -c '/Users/' .claude/settings.local.json
# 預期輸出：0
```

### 常見問題排除

| 問題 | 原因 | 解法 |
|------|------|------|
| Hook 執行失敗 `Permission denied` | 缺少執行權限 | `chmod +x .claude/hooks/*.py` |
| Hook 報錯 `SyntaxError` | Python 版本低於 3.9 | 升級 Python 或安裝 3.9+ |
| `settings.local.json` 解析錯誤 | JSON 格式損壞 | `python3 -c "import json; json.load(open('.claude/settings.local.json'))"` 定位錯誤行 |
| Session 啟動時大量 Hook 失敗 | 硬編碼路徑指向不存在的目錄 | `grep '/Users/' .claude/settings.local.json` 找出並修正 |
| MCP server 連線失敗 | `enabledMcpjsonServers` 配置了未安裝的 server | 移除不適用的 server 或安裝對應工具 |
| `.claude` 出現 Git 衝突 | 未移除框架的 `.git` 目錄 | `rm -rf .claude/.git` |

### 建立 CLAUDE.md

新專案需要在專案根目錄建立 `CLAUDE.md`，作為 Claude Code 讀取專案資訊的入口。

**CLAUDE.md 必須包含的資訊**：

| 項目 | 說明 | 範例 |
|------|------|------|
| 專案類型 | 應用程式類型 | Flutter 移動應用程式、Node.js Web API |
| 開發語言 | 主要程式語言 | Dart、TypeScript、Python |
| 框架版本 | 使用的框架和版本 | Flutter 3.41、Next.js 14 |
| 實作代理人 | Phase 3b 使用的語言特定代理人 | parsley-flutter-developer |
| 語言特定規範 | 指向語言規範檔案 | FLUTTER.md |

**建立步驟**：

1. 從模板複製（`.claude/templates/CLAUDE-template.md`）或手動建立 `CLAUDE.md`
2. 填入專案基本資訊（類型、語言、框架版本）
3. 指定實作代理人（決定 Phase 3b 由誰執行）
4. 如有語言特定規範檔案（如 `FLUTTER.md`），在 CLAUDE.md 中引用

**實作代理人對照表**：

| 語言/框架 | 實作代理人 | 語言規範檔 |
|-----------|-----------|-----------|
| Flutter/Dart | parsley-flutter-developer | `.claude/project-templates/FLUTTER.md` |
| Python | thyme-python-developer | 依專案建立 |

> 其餘 TDD 階段代理人（Phase 1/2/3a/4）為語言無關，跨專案通用，不需調整。

**範例**（Flutter 專案）：

```markdown
# CLAUDE.md - 專案開發規範

## 專案資訊

| 項目 | 說明 |
|------|------|
| **專案類型** | Flutter 移動應用程式 |
| **開發語言** | Dart |
| **框架版本** | Flutter 3.41 |
| **實作代理人** | parsley-flutter-developer |
| **語言特定規範** | [FLUTTER.md](./.claude/project-templates/FLUTTER.md) |
```

---

## 目錄結構

```text
.claude/
├── README.md                          # 本文件
├── README-subtree-sync.md             # 同步機制詳細說明
├── settings.local.json                # Claude Code 權限配置
├── installed-packages.json            # 已安裝套件記錄
│
├── project-templates/                 # 專案模板檔案
│   └── FLUTTER.md                     # Flutter 特定規範
│
├── templates/                         # 通用模板
│   ├── CLAUDE-template.md             # CLAUDE.md 模板
│   ├── work-log-template.md           # 工作日誌模板
│   ├── ticket-log-template.md         # Ticket 模板
│   ├── ticket.md.template             # Ticket Markdown 模板
│   ├── ticket.yaml.template           # Ticket YAML 模板
│   ├── agent-template.md              # 代理人模板
│   └── ...                            # 其他模板
│
├── config/                            # 配置檔案
│   ├── agents.yaml                    # 代理人配置
│   └── quality_rules.yaml             # 品質規則配置
│
├── hooks/                             # Hook 系統（49 個 Python 檔案）
│   ├── hook_utils.py                  # 共用工具模組
│   ├── command-entrance-gate-hook.py  # 命令入口驗證
│   ├── prompt-submit-hook.py          # 用戶輸入檢查
│   ├── phase-completion-gate-hook.py  # 階段完成驗證
│   ├── acceptance-gate-hook.py        # 驗收閘門
│   ├── process-skip-guard-hook.py     # 流程省略防護
│   ├── commit-handoff-hook.py         # Commit 後 Handoff
│   └── ...                            # 其他 Hook
│
├── agents/                            # 代理人定義（28 個）
│   ├── AGENT_PRELOAD.md               # 代理人預載設定
│   ├── rosemary-project-manager.md    # 主線程 PM
│   ├── lavender-interface-designer.md # Phase 1 功能設計
│   ├── sage-test-architect.md         # Phase 2 測試設計
│   ├── pepper-test-implementer.md     # Phase 3a 策略規劃
│   ├── parsley-flutter-developer.md   # Phase 3b Flutter 實作
│   ├── cinnamon-refactor-owl.md       # Phase 4 重構評估
│   ├── saffron-system-analyst.md      # SA 前置審查
│   ├── incident-responder.md          # 事件回應
│   ├── thyme-documentation-integrator.md  # 文件整合
│   └── ...                            # 其他專業代理人
│
├── rules/                             # 規則系統
│   ├── core/                          # 核心決策 + 基本約束
│   │   ├── decision-tree.md           # 主線程決策樹
│   │   ├── askuserquestion-rules.md   # AskUserQuestion 規則
│   │   ├── quality-baseline.md        # 品質基線
│   │   ├── implementation-quality.md  # 實作品質標準
│   │   └── ...                        # 其他核心規則
│   ├── flows/                         # 執行流程
│   │   ├── tdd-flow.md                # TDD 流程
│   │   ├── incident-response.md       # 事件回應流程
│   │   ├── ticket-lifecycle.md        # Ticket 生命週期
│   │   └── ...                        # 其他流程
│   ├── guides/                        # 操作指南
│   │   ├── parallel-dispatch.md       # 並行派發指南
│   │   ├── methodology-index.md       # 方法論索引
│   │   ├── skill-index.md             # Skill 指令索引
│   │   └── ...                        # 其他指南
│   └── forbidden/                     # 禁止行為
│       └── skip-gate.md               # Skip-gate 防護
│
├── skills/                            # Skill 工具（33 個）
│   ├── ticket/                        # Ticket 系統
│   ├── project-init/                  # 專案初始化
│   ├── pre-fix-eval/                  # 修復前評估
│   ├── version-release/               # 版本發布
│   ├── tech-debt-capture/             # 技術債務捕獲
│   ├── parallel-evaluation/           # 並行評估
│   └── ...                            # 其他 Skill
│
├── methodologies/                     # 方法論文件（40+ 份）
│   ├── README.md                      # 方法論索引
│   ├── agile-refactor-methodology.md
│   ├── 5w1h-self-awareness-methodology.md
│   ├── behavior-first-tdd-methodology.md
│   ├── hook-system-methodology.md
│   └── ...                            # 其他方法論
│
├── references/                        # 參考文件（22 份）
│   ├── decision-tree-diagrams.md
│   ├── ticket-lifecycle-phases.md
│   └── ...                            # 其他參考
│
├── error-patterns/                    # 錯誤模式知識庫
│   ├── README.md
│   ├── architecture/                  # 架構類錯誤（ARCH-xxx）
│   ├── implementation/                # 實作類錯誤（IMP-xxx）
│   ├── test/                          # 測試類錯誤（TEST-xxx）
│   └── documentation/                 # 文件類錯誤（DOC-xxx）
│
├── commands/                          # Slash 命令定義
│   ├── commit-as-prompt.md
│   ├── sync-push.md
│   ├── sync-pull.md
│   └── ...                            # 其他命令
│
├── scripts/                           # 工具腳本（Python）
│   ├── cleanup-hook-logs.py
│   ├── pm-status-check.py
│   └── ...                            # 其他腳本
│
└── hook-logs/                         # Hook 執行日誌（自動生成）
    ├── acceptance-gate/
    ├── agent-dispatch-check/
    └── ...
```

---

## 同步機制

本框架支援跨專案同步，使用雙向同步腳本管理 `.claude` 資料夾。

| 操作 | Slash 命令 | 腳本 |
|------|-----------|------|
| 推送變更到獨立 Repo | `/sync-push` | `scripts/sync-claude-push.py` |
| 拉取最新配置 | `/sync-pull` | `scripts/sync-claude-pull.py` |

**獨立 Repo**：https://github.com/tarrragon/claude.git

> 完整的同步機制說明（設計原理、方案比較、衝突處理、最佳實踐）請參考 [README-subtree-sync.md](./README-subtree-sync.md)。

---

## 代理人職責說明

代理人定義檔案統一存放於 `.claude/agents/` 目錄。

### TDD 四階段代理人

| 階段 | 代理人 | 職責 |
|------|-------|------|
| Phase 0 | [saffron-system-analyst.md](./agents/saffron-system-analyst.md) | SA 前置審查 |
| Phase 1 | [lavender-interface-designer.md](./agents/lavender-interface-designer.md) | 功能設計、API 介面定義 |
| Phase 2 | [sage-test-architect.md](./agents/sage-test-architect.md) | 測試案例設計 |
| Phase 3a | [pepper-test-implementer.md](./agents/pepper-test-implementer.md) | 策略規劃、虛擬碼設計 |
| Phase 3b | [parsley-flutter-developer.md](./agents/parsley-flutter-developer.md) | 語言特定實作（Flutter） |
| Phase 4 | [cinnamon-refactor-owl.md](./agents/cinnamon-refactor-owl.md) | 重構評估、技術債務識別 |

### 專案管理與品質

| 代理人 | 職責 |
|-------|------|
| [rosemary-project-manager.md](./agents/rosemary-project-manager.md) | 主線程 PM、任務派發、決策 |
| [acceptance-auditor.md](./agents/acceptance-auditor.md) | 驗收審查 |
| [bay-quality-auditor.md](./agents/bay-quality-auditor.md) | 品質稽核 |
| [incident-responder.md](./agents/incident-responder.md) | 事件回應、錯誤分析 |

### 專業領域

| 代理人 | 職責 |
|-------|------|
| [thyme-documentation-integrator.md](./agents/thyme-documentation-integrator.md) | 文件整合、方法論轉化 |
| [thyme-python-developer.md](./agents/thyme-python-developer.md) | Python 實作（Hook、腳本） |
| [basil-hook-architect.md](./agents/basil-hook-architect.md) | Hook 系統架構設計 |
| [sumac-system-engineer.md](./agents/sumac-system-engineer.md) | 環境配置、系統工程 |
| [clove-security-reviewer.md](./agents/clove-security-reviewer.md) | 安全審查 |
| [ginger-performance-tuner.md](./agents/ginger-performance-tuner.md) | 效能調優 |
| [oregano-data-miner.md](./agents/oregano-data-miner.md) | 外部資源研究 |
| [star-anise-system-designer.md](./agents/star-anise-system-designer.md) | 系統設計 |

> 完整代理人清單共 28 個，詳見 `.claude/agents/` 目錄。

---

## 核心文件索引

### 規則系統（建議閱讀順序）

| 文件 | 說明 |
|------|------|
| [rules/core/decision-tree.md](./rules/core/decision-tree.md) | 主線程決策樹（核心入口） |
| [rules/core/quality-baseline.md](./rules/core/quality-baseline.md) | 品質基線（不可協商） |
| [rules/core/implementation-quality.md](./rules/core/implementation-quality.md) | 實作品質標準 |
| [rules/flows/tdd-flow.md](./rules/flows/tdd-flow.md) | TDD 含 SA 前置審查流程 |
| [rules/flows/ticket-lifecycle.md](./rules/flows/ticket-lifecycle.md) | Ticket 生命週期 |
| [rules/forbidden/skip-gate.md](./rules/forbidden/skip-gate.md) | Skip-gate 防護機制 |

> 完整規則索引：[rules/README.md](./rules/README.md)

### 方法論文件（核心）

| 文件 | 說明 |
|------|------|
| [agile-refactor-methodology.md](./methodologies/agile-refactor-methodology.md) | 敏捷重構方法論 |
| [5w1h-self-awareness-methodology.md](./methodologies/5w1h-self-awareness-methodology.md) | 5W1H 決策框架 |
| [hook-system-methodology.md](./methodologies/hook-system-methodology.md) | Hook 系統設計 |
| [behavior-first-tdd-methodology.md](./methodologies/behavior-first-tdd-methodology.md) | 行為優先 TDD |
| [natural-language-programming-methodology.md](./methodologies/natural-language-programming-methodology.md) | 命名方法論 |
| [comment-writing-methodology.md](./methodologies/comment-writing-methodology.md) | 註解撰寫規範 |

> 完整方法論索引：[methodologies/README.md](./methodologies/README.md) 或 [rules/guides/methodology-index.md](./rules/guides/methodology-index.md)

### Hook 系統

所有 Hook 以 Python 實作，透過 `settings.local.json` 配置觸發時機。

| 觸發事件 | 代表性 Hook | 功能 |
|---------|------------|------|
| UserPromptSubmit | `prompt-submit-hook.py` | 用戶輸入檢查、5W1H 合規 |
| UserPromptSubmit | `command-entrance-gate-hook.py` | 開發命令 Ticket 驗證 |
| PreToolUse | `file-type-permission-hook.py` | 檔案編輯權限檢查 |
| PreToolUse | `main-thread-edit-restriction-hook.py` | 主線程編輯限制 |
| PostToolUse | `phase-completion-gate-hook.py` | 階段完成驗證 |
| PostToolUse | `commit-handoff-hook.py` | Commit 後 Handoff 引導 |

> Hook 設計方法論：[methodologies/hook-system-methodology.md](./methodologies/hook-system-methodology.md)

### Skill 指令

| 指令 | 用途 |
|------|------|
| `/ticket` | Ticket 系統（create/track/handoff/resume） |
| `/pre-fix-eval` | 修復前評估（錯誤發生時強制） |
| `/version-release` | 版本發布流程 |
| `/tech-debt-capture` | 技術債務捕獲 |
| `/project-init` | 新專案初始化 |

> 完整 Skill 索引：[rules/guides/skill-index.md](./rules/guides/skill-index.md)

---

## 配置說明

### settings.local.json

Claude Code 的權限與 Hook 配置文件，包含以下區塊：

| 區塊 | 用途 | 新專案是否需調整 |
|------|------|----------------|
| `permissions.allow` | 自動允許的工具和指令 | 是 -- 移除不適用的語言特定 permission，修正硬編碼路徑 |
| `permissions.ask` | 需確認才執行的指令（如 `git push`） | 通常保留 |
| `enabledMcpjsonServers` | 啟用的 MCP server | 是 -- 根據專案語言調整 |
| `hooks` | Hook 觸發配置 | 通常保留（使用 `$CLAUDE_PROJECT_DIR` 自動解析） |
| `outputStyle` | 回應格式 | 可保留 |

詳細的新專案配置步驟請參考[新專案配置指南](#新專案配置指南)。

---

## 授權

本專案採用 MIT 授權條款。

---

**最後更新**: 2026-03-04
**版本**: 2.0.0 - 全面重寫：更新目錄結構、移除 Emoji、統一快速開始流程、修正死連結
**維護者**: [@tarrragon](https://github.com/tarrragon)
