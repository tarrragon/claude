# CLAUDE.md

本文件為 Claude Code 在此專案中的開發指導規範。

---

## 1. 專案配置

**專案類型**: Flutter 移動應用程式（Startup Hook 自動識別）

| 專案類型 | 識別特徵 | 語言配置 | 執行代理人 |
|---------|---------|---------|-----------|
| **Flutter** | `pubspec.yaml` | [`FLUTTER.md`](./FLUTTER.md) | parsley-flutter-developer |

**通用規範**（本文件）：TDD 流程、5W1H 決策、敏捷重構、文件管理、測試設計哲學

**語言特定規範**：[`FLUTTER.md`](./FLUTTER.md)

---

## 2. 卓越開發的核心價值

> 理論依據：Will Guidara《Unreasonable Hospitality》

### 我們的價值觀

**品質承諾**
100% 測試通過是我們對品質的承諾。每一個綠燈都是團隊的驕傲。

**成長心態**
每個挑戰都是成長的機會。我們選擇面對而非迴避，透過分解問題找到解決方案。

**架構優先**
優秀的架構是長期成功的基石。發現設計問題時，我們選擇立即改進。

**完整體驗**
TDD 四階段是完整的開發體驗。Phase 4 重構是提升程式碼品質的寶貴機會。

**學習導向**
測試失敗是發現問題的珍貴時刻。我們記錄學習，讓經驗成為團隊的資產。

### 快速檢查

- [ ] 測試全綠？
- [ ] 面對挑戰？
- [ ] 架構健康？
- [ ] Phase 4 完成？
- [ ] 學習記錄？

### 底線要求

- 測試通過率必須 100%
- Phase 4 不可跳過
- 設計問題立即修正

---

## 3. 5W1H 決策框架

**核心精神**：每個開發決策必須經過系統化思考，確保決策品質和職責分離。

### 必要格式

```text
5W1H-{TOKEN}

Who: {agent} (executor) | rosemary-project-manager (dispatcher)
What: {單一職責功能}
When: {觸發時機}
Where: {架構層級}
Why: {需求依據}
How: [Task Type: {TYPE}] {TDD 策略}
```

### Task Types

| 類型 | 執行者 | 禁止執行者 |
|-----|-------|----------|
| Implementation | parsley, sage, pepper | rosemary |
| Dispatch | rosemary | agents |
| Review | rosemary | agents |
| Documentation | thyme, rosemary | - |

### 快速檢查

- [ ] Who 有 (executor) | (dispatcher)
- [ ] What 單一職責
- [ ] How 有 [Task Type: XXX]

**深入學習**：`/5w1h-decision` | [5W1H 方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/5w1h-self-awareness-methodology.md)

---

## 4. 敏捷重構開發流程

### 主線程職責

**rosemary-project-manager**：
- 依照工作日誌分派任務
- 維持敏捷節奏和品質標準
- 處理升級請求和任務重新分派

**專注於**：分派和驗收，不親自實作程式碼。

### 五重文件協作

| 文件 | 核心問題 |
|------|---------|
| **CHANGELOG.md** | 這個版本做了什麼改變？ |
| **todo.md** | 還有哪些問題需要處理？ |
| **worklog** | 這個版本要達成什麼目標？ |
| **ticket** | 這個任務的執行細節是什麼？ |
| **error-patterns** | 之前遇過類似問題嗎？ |

**深入學習**：[五重文件系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/five-document-system-methodology.md)

### 代理人分工

**TDD 四階段**：
| Phase | 代理人 | 產出 |
|-------|-------|------|
| 1. 功能設計 | lavender-interface-designer | 規格和介面 |
| 2. 測試設計 | sage-test-architect | 測試案例 |
| 3a. 策略規劃 | pepper-test-implementer | 虛擬碼 |
| 3b. 實作 | parsley-flutter-developer | 可執行程式碼 |
| 4. 重構 | cinnamon-refactor-owl | 優化後程式碼 |

**專業任務**：
| 任務類型 | 代理人 |
|---------|-------|
| Hook 開發 | basil-hook-architect |
| 文件整合 | thyme-documentation-integrator |
| 格式化 | mint-format-specialist |
| MCP 工具 | general-purpose |

**任務類型優先於專案類型**：Hook 開發 → basil，不是 parsley。

### TDD 四階段流程

```text
Phase 1 → Phase 2 → Phase 3a → Phase 3b → Phase 4 → Commit
  設計      測試       策略        實作       重構      存檔
```

**Phase 4 必須執行**：即使程式碼品質 A+，也要完成重構評估。

**深入學習**：[TDD 協作開發流程]($CLAUDE_PROJECT_DIR/.claude/tdd-collaboration-flow.md) | [敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)

---

## 5. Ticket 服務精神

> 理論依據：Will Guidara《Unreasonable Hospitality》

### 核心理念

**Ticket 不只是解決問題的工具，而是為專案品質提供服務的載體。**

| 舊思維 | 新思維 |
|--------|--------|
| Ticket = 解決問題的工具 | Ticket = 提供服務的載體 |
| 測試失敗 = 需要修復的錯誤 | 測試失敗 = 寶貴的學習機會 |
| 追求在單一 Ticket 完成所有任務 | 積極派發新 Ticket |

### Atomic Ticket 原則

**一個 Action + 一個 Target = 單一職責**

**四大檢查**：
| 檢查項目 | 通過標準 |
|---------|---------|
| 語義檢查 | 能用「動詞 + 單一目標」表達 |
| 修改原因 | 只有一個修改原因 |
| 驗收一致 | 所有驗收條件指向同一目標 |
| 依賴獨立 | 無循環依賴 |

### 95/5 規則

- **95% 結構化執行**：遵循流程、格式、驗收條件
- **5% 創意探索**：研究性 Ticket、深入分析、學習記錄

### Ticket 類型

| 類型 | 代碼 | 用途 |
|------|------|------|
| Research | RES | 探索未知領域 |
| Analysis | ANA | 理解現狀和問題 |
| Implementation | IMP | 執行具體任務 |
| Investigation | INV | 深入追蹤問題根因 |
| Documentation | DOC | 記錄和傳承經驗 |

**可用指令**：`/ticket-create` | `/ticket-track`

**深入學習**：[Atomic Ticket 方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/atomic-ticket-methodology.md) | [Ticket 生命週期]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-lifecycle-management-methodology.md)

---

## 6. 開發工具快速參考

### LSP 優先策略

**LSP 能解決的問題必須優先使用 LSP**（~50ms vs ~45秒）

| 操作 | 用途 |
|------|------|
| `goToDefinition` | 追蹤符號來源 |
| `findReferences` | 重構影響分析 |
| `hover` | 查看型別和文件 |
| `callHierarchy` | 呼叫分析 |

**工具優先順序**：LSP → Skill → MCP（委派給 general-purpose）

**深入學習**：`/lsp-first`

### 測試失敗處理

**核心理念**：測試失敗是珍貴的改進機會，不要急於修復。

**流程**：
1. 暫停修復衝動
2. 建立 Ticket（`/ticket-create`）
3. 六階段評估（`/pre-fix-eval`）
4. 分派執行
5. 經驗記錄（error-patterns）

**深入學習**：`/pre-fix-eval`

### 版本發布

**Phase 4 完成 = 立即提交存底**

```bash
# 檢查發布準備度
uv run .claude/skills/version-release/scripts/version_release.py check

# 預覽發布
uv run .claude/skills/version-release/scripts/version_release.py release --dry-run

# 執行發布
uv run .claude/skills/version-release/scripts/version_release.py release
```

**深入學習**：`/version-release` | `/commit-as-prompt`

### 技術債務處理

**Phase 4 發現技術債務的標準流程**：

```text
發現技術債務 → 記錄到工作日誌 → /tech-debt-capture → 建立 Ticket → 提交
```

**工作日誌記錄格式**：
```markdown
| ID | 描述 | 風險等級 | 建議處理時機 |
|----|------|---------|------------|
| TD-001 | [描述] | 高/中/低 | [時機] |
```

**深入學習**：`/tech-debt-capture` | [TDD 協作流程 - Phase 4 技術債務規範]($CLAUDE_PROJECT_DIR/.claude/tdd-collaboration-flow.md)

---

## 7. 程式碼品質原則

### 測試行為非結構

> "Tests should be coupled to the behavior of the code and decoupled from the structure of code."
> — Kent Beck

**Sociable Unit Tests**（推薦）：
- Unit = Module
- 只 Mock 外部依賴（Database, File System, External Services）
- 測試 Module API（黑盒測試）

**驗證**：重構時測試無需修改 = 測試耦合到行為。

**深入學習**：[行為優先 TDD 方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/behavior-first-tdd-methodology.md)

### 導入路徑語意化

- 100% 使用 `package:book_overview_app/` 格式
- 0% 相對路徑
- 禁用別名（`as`）和隱藏機制（`hide`）

**深入學習**：[Package 導入路徑方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/package-import-methodology.md)

### 自然語言化撰寫

- 函式控制在 5-10 行
- 變數只承載單一類型資料
- 程式碼如同閱讀自然語言

**深入學習**：[自然語言化撰寫方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/natural-language-programming-methodology.md)

### 錯誤處理

```dart
// 統一導入
import 'package:book_overview_app/core/errors/errors.dart';

// 優先使用預編譯錯誤
throw CommonErrors.titleRequired;
throw CommonErrors.networkTimeout;
```

**深入學習**：[錯誤修復和重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/error-fix-refactor-methodology.md)

---

## 8. 重要文件索引

### 核心規範

| 文件 | 用途 |
|------|------|
| [TDD 協作開發流程]($CLAUDE_PROJECT_DIR/.claude/tdd-collaboration-flow.md) | 四階段開發 |
| [Agent 協作規範]($CLAUDE_PROJECT_DIR/.claude/agent-collaboration.md) | Sub-agent 使用 |
| [敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md) | 分工協作 |
| [五重文件系統]($CLAUDE_PROJECT_DIR/.claude/methodologies/five-document-system-methodology.md) | 文件管理 |

### 方法論

| 方法論 | 用途 |
|-------|------|
| [5W1H 決策]($CLAUDE_PROJECT_DIR/.claude/methodologies/5w1h-self-awareness-methodology.md) | 決策框架 |
| [Atomic Ticket]($CLAUDE_PROJECT_DIR/.claude/methodologies/atomic-ticket-methodology.md) | Ticket 設計 |
| [行為優先 TDD]($CLAUDE_PROJECT_DIR/.claude/methodologies/behavior-first-tdd-methodology.md) | 測試設計 |
| [系統化除錯]($CLAUDE_PROJECT_DIR/.claude/methodologies/systematic-debugging-methodology.md) | 除錯流程 |

### Skill 指令

| 指令 | 用途 |
|------|------|
| `/5w1h-decision` | 5W1H 決策格式 |
| `/pre-fix-eval` | 修復前評估 |
| `/ticket-create` | 建立 Ticket |
| `/ticket-track` | 追蹤 Ticket |
| `/version-release` | 版本發布 |
| `/tech-debt-capture` | 技術債務捕獲 |
| `/lsp-first` | LSP 使用指南 |
| `/commit-as-prompt` | 提交流程 |

### Hook 系統

**完整參考**：[Hook 系統快速參考]($CLAUDE_PROJECT_DIR/.claude/hook-system-reference.md) | [Hook 系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hook-system-methodology.md)

### 專案文檔

| 文件 | 用途 |
|------|------|
| `docs/app-requirements-spec.md` | 需求規格 |
| `docs/app-use-cases.md` | 用例說明 |
| `docs/test-pyramid-design.md` | 測試金字塔 |
| `docs/event-driven-architecture-design.md` | 事件驅動架構 |

---

## 9. 語言規範

**所有回應必須使用繁體中文 (zh-TW)**

**禁用詞彙**：
| 禁用 | 使用 |
|------|------|
| 智能 | Hook 系統、規則比對 |
| 文檔 | 文件 |
| 數據 | 資料 |
| 默認 | 預設 |

**參考**：[專案用語規範字典]($CLAUDE_PROJECT_DIR/.claude/terminology-dictionary.md)

---

## 10. 任務追蹤

### 任務管理檔案

- `docs/todolist.md` - 開發任務追蹤
- `docs/work-logs/` - 詳細開發工作日誌
- `CHANGELOG.md` - 版本變更記錄

### 里程碑

- v0.0.x: 基礎架構與測試框架
- v0.x.x: 開發階段，逐步實現功能
- v1.0.0: 完整功能，準備上架

---

## 重要提醒

**本專案所有品質控制、流程檢查、問題追蹤都由 Hook 系統執行。**

請信任並配合 Hook 系統的運作，專注於解決技術問題而非繞過檢查機制。

---

*精簡版 CLAUDE.md - 專注核心精神，詳細流程請參考對應的 Skill 和方法論*
