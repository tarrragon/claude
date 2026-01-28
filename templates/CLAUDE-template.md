# CLAUDE.md

本文件為 Claude Code 在此專案中的開發指導規範。

---

## 1. 專案身份

<!-- 填入專案特定資訊 -->

**專案名稱**: <!-- 例如：Book Overview App -->

**專案目標**: <!-- 簡述專案目的和願景 -->

**專案類型**: <!-- Flutter / Python / Node.js 等 -->

| 專案類型 | 識別特徵 | 語言配置 | 執行代理人 |
|---------|---------|---------|-----------|
| <!-- Flutter --> | `pubspec.yaml` | [`FLUTTER.md`](./FLUTTER.md) | parsley-flutter-developer |

**啟用的 MCP/Plugin**:
<!-- 列出專案使用的 MCP 伺服器 -->
- dart - Dart/Flutter 開發工具
- serena - 語意程式碼操作
- context7 - 文檔查詢
- greptile - PR 審查（如適用）

---

## 2. 核心價值

> 理論依據：Will Guidara《Unreasonable Hospitality》

**品質承諾** - 100% 測試通過是我們對品質的承諾。

**成長心態** - 每個挑戰都是成長的機會。

**架構優先** - 優秀的架構是長期成功的基石。

**完整體驗** - TDD 四階段是完整的開發體驗。

**學習導向** - 測試失敗是發現問題的珍貴時刻。

### 底線要求（不可協商）

- 測試通過率必須 100%
- Phase 4 不可跳過
- 設計問題立即修正

詳細規則：[品質基線](.claude/rules/core/quality-baseline.md)

---

## 3. 規則系統

> 入口文件：[rules/README](.claude/rules/README.md)

### core/ - 核心決策與約束

| 規則 | 用途 |
|------|------|
| [decision-tree](.claude/rules/core/decision-tree.md) | 主線程決策樹（核心，含 Mermaid 圖表） |
| [cognitive-load](.claude/rules/core/cognitive-load.md) | 認知負擔設計原則 |
| [document-system](.claude/rules/core/document-system.md) | 五重文件系統 |
| [quality-baseline](.claude/rules/core/quality-baseline.md) | 品質基線 |
| [language-constraints](.claude/rules/core/language-constraints.md) | 語言約束 |
| [document-format-rules](.claude/rules/core/document-format-rules.md) | 文件格式 |

### agents/ - 代理人系統

| 規則 | 用途 |
|------|------|
| [overview](.claude/rules/agents/overview.md) | 職責矩陣、升級規則 |
| [incident-responder](.claude/rules/agents/incident-responder.md) | 錯誤回應（Level 1） |
| [system-analyst](.claude/rules/agents/system-analyst.md) | 系統分析（Level 2） |
| [security-reviewer](.claude/rules/agents/security-reviewer.md) | 安全審查（Level 3） |
| TDD 代理人 | lavender, sage, pepper, parsley, cinnamon |

### flows/ - 執行流程

| 規則 | 用途 |
|------|------|
| [tdd-flow](.claude/rules/flows/tdd-flow.md) | TDD 開發流程 |
| [incident-response](.claude/rules/flows/incident-response.md) | 事件回應流程 |
| [ticket-lifecycle](.claude/rules/flows/ticket-lifecycle.md) | Ticket 生命週期 |
| [tech-debt](.claude/rules/flows/tech-debt.md) | 技術債務流程 |

### guides/ - 操作指南

| 規則 | 用途 |
|------|------|
| [task-splitting](.claude/rules/guides/task-splitting.md) | 任務拆分指南 |
| [parallel-dispatch](.claude/rules/guides/parallel-dispatch.md) | 並行派發指南 |

### forbidden/ - 禁止行為

| 規則 | 用途 |
|------|------|
| [skip-gate](.claude/rules/forbidden/skip-gate.md) | Skip-gate 防護 |

---

## 4. Skill 指令

### 常用指令

| 指令 | 用途 |
|------|------|
| `/5w1h-decision` | 5W1H 決策格式 |
| `/pre-fix-eval` | 修復前評估 |
| `/ticket-create` | 建立 Ticket |
| `/ticket-track` | 追蹤 Ticket |
| `/version-release` | 版本發布 |
| `/tech-debt-capture` | 技術債務捕獲 |

### 開發輔助

| 指令 | 用途 |
|------|------|
| `/lsp-first` | LSP 使用指南 |
| `/cognitive-load` | 認知負擔評估 |
| `/decision-helper` | 決策樹助手 |

完整列表：`.claude/skills/` 目錄

---

## 5. 方法論參考

| 方法論 | 用途 |
|-------|------|
| [5W1H 決策](.claude/methodologies/5w1h-self-awareness-methodology.md) | 決策框架 |
| [Atomic Ticket](.claude/methodologies/atomic-ticket-methodology.md) | Ticket 設計 |
| [行為優先 TDD](.claude/methodologies/behavior-first-tdd-methodology.md) | 測試設計 |
| [敏捷重構](.claude/methodologies/agile-refactor-methodology.md) | 開發流程 |
| [認知負擔設計](.claude/methodologies/cognitive-load-design-methodology.md) | 程式碼設計 |

完整列表：`.claude/methodologies/` 目錄

---

## 6. 語言特定規範

<!-- 根據專案類型引用對應的語言規範 -->

**Flutter 專案**：[`FLUTTER.md`](./FLUTTER.md)

---

## 7. 專案文件

### 任務追蹤

| 文件 | 用途 |
|------|------|
| `docs/todolist.md` | 開發任務追蹤 |
| `docs/work-logs/` | 版本工作日誌 |
| `CHANGELOG.md` | 版本變更記錄 |
| `.claude/tickets/` | Ticket 文件 |

### 專案文件

<!-- 根據專案需要填入 -->

| 文件 | 用途 |
|------|------|
| `docs/app-requirements-spec.md` | 需求規格 |
| `docs/app-use-cases.md` | 用例說明 |
| `docs/test-pyramid-design.md` | 測試設計 |

---

## 8. 里程碑

<!-- 根據專案規劃填入 -->

- v0.0.x: 基礎架構與測試框架
- v0.x.x: 開發階段，逐步實現功能
- v1.0.0: 完整功能，準備上架

---

## 重要提醒

本專案所有品質控制、流程檢查、問題追蹤都由 Hook 系統執行。

請信任並配合 Hook 系統的運作，專注於解決技術問題而非繞過檢查機制。

---

*專案入口文件 - 詳細規則請參考 `.claude/rules/` 目錄*

<!--
使用說明：
1. 將此範本複製到專案根目錄
2. 重命名為 CLAUDE.md
3. 填入專案特定資訊（標記 <!-- --> 的區塊）
4. 移除不需要的章節
5. 驗證所有連結有效
-->
