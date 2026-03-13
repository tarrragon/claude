# Ticket ID 命名規範

本文件定義 Ticket 檔案的標準命名規則，包括標準格式和允許的描述性後綴。

> **來源**：W44-003 — ID 解析包容性擴充和命名字典實作

---

## 1. 標準 Ticket ID 格式（主要格式）

### 格式定義

```
{version}-W{wave}-{sequence}[-description]
```

### 組件說明

| 組件 | 規則 | 範例 | 說明 |
|------|------|------|------|
| `{version}` | 三位數版本號（數字.數字.數字） | `0.31.0`, `0.1.0` | 專案發布版本號 |
| `W{wave}` | 波次號（1-999） | `W3`, `W44` | 一個版本內的執行批次 |
| `{sequence}` | 序號序列（整數.整數...） | `001`, `001.1`, `001.1.2` | 同 Wave 內的任務序號，支援無限深度子任務 |
| `[-description]` | **可選**描述性後綴 | `-phase1-design`, `-analysis` | 檔案內容描述（見 2.1-2.3 節） |

### 正則表達式

```python
# 正式定義於 .claude/skills/ticket/ticket_system/lib/constants.py
TICKET_ID_PATTERN = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"
```

### 標準格式範例

| 檔案名 | 說明 |
|--------|------|
| `0.31.0-W3-001.md` | 根任務 |
| `0.31.0-W3-001.1.md` | 子任務 |
| `0.31.0-W3-001.1.2.md` | 孫任務 |
| `0.1.0-W44-003.md` | v0.1.0 版本，W44 Wave，第 3 個任務 |

---

## 2. TDD 階段文件命名規範（允許的後綴模式）

### 2.1 TDD Phase 輔助文件後綴

TDD 流程（Phase 0-4）中各代理人產出的設計、測試、策略、執行報告文件應使用以下後綴：

| 後綴 | Phase | 用途 | 範例 | 使用代理人 |
|------|-------|------|------|-----------|
| `-phase1-design` | Phase 1 | 功能規格設計文件 | `0.1.0-W44-003-phase1-design.md` | lavender-interface-designer |
| `-phase1-feature-spec` | Phase 1 | 功能規格（Phase 1 前綴變體） | `0.1.0-W41-002-phase1-feature-spec.md` | lavender-interface-designer |
| `-feature-spec` | Phase 1 | 功能規格（別名） | `0.1.0-W44-003-feature-spec.md` | lavender-interface-designer |
| `-feature-design` | Phase 1 | 功能設計（別名） | `0.1.0-W44-003-feature-design.md` | lavender-interface-designer |
| `-phase2-test-design` | Phase 2 | 測試設計文件 | `0.1.0-W44-003-phase2-test-design.md` | sage-test-architect |
| `-test-design` | Phase 2 | 測試設計（縮寫） | `0.1.0-W43-006-test-design.md` | sage-test-architect |
| `-test-case-design` | Phase 2 | 測試案例設計 | `0.1.0-W37-002-test-case-design.md` | sage-test-architect |
| `-phase3a-strategy` | Phase 3a | 實作策略規劃文件 | `0.1.0-W44-003-phase3a-strategy.md` | pepper-test-implementer |
| `-phase3b-execution-report` | Phase 3b | 實作執行報告 | `0.1.0-W44-003-phase3b-execution-report.md` | parsley-flutter-developer |
| `-phase3b-test-report` | Phase 3b | Phase 3b 測試報告 | `0.1.0-W39-001-phase3b-test-report.md` | parsley-flutter-developer |
| `-phase3b-execution-log` | Phase 3b | Phase 3b 執行日誌 | `0.1.0-W44-003-phase3b-execution-log.md` | parsley-flutter-developer |
| `-phase4-evaluation` | Phase 4 | Phase 4 評估報告 | `0.1.0-W39-001-phase4-evaluation.md` | /parallel-evaluation |
| `-refactor` | Phase 4b | 重構相關檔案 | `0.1.0-W39-refactor.md` | cinnamon-refactor-owl |
| `-refactoring-report` | Phase 4b | 重構報告 | `0.1.0-W2-014-refactoring-report.md` | cinnamon-refactor-owl |

**命名決策樹**：

```
寫一份 TDD Phase 的產出文件
    |
    v
是 Phase 1 功能規格？ → 是 → 使用 "-phase1-design" 或 "-feature-spec"
    |
    v
是 Phase 2 測試設計？ → 是 → 使用 "-phase2-test-design"
    |
    v
是 Phase 3a 實作策略？ → 是 → 使用 "-phase3a-strategy"
    |
    v
是 Phase 3b 執行報告？ → 是 → 使用 "-phase3b-execution-report"
    |
    v
皆非 → 不使用 TDD Phase 後綴
```

### 2.2 分析/報告類後綴

各類分析和研究的產出文件使用以下後綴：

| 後綴 | Ticket Type | 用途 | 範例 |
|------|-------------|------|------|
| `-analysis` | ANA | 分析報告 | `0.1.0-W25-005-analysis.md` |
| `-uc-analysis` | ANA | Use Case 分析 | `0.1.1-W1-004-uc-analysis.md` |
| `-evaluation-report` | ANA | 評估報告 | `0.1.0-Wx-xxx-evaluation-report.md` |
| `-test-cases` | TST | 測試案例清單 | `0.1.0-W1-005-test-cases.md` |
| `-test-cases-quick-reference` | TST | 測試案例快速參考 | `0.1.0-W1-005-test-cases-quick-reference.md` |

### 2.3 3b 拆分子任務後綴（進階用法）

Phase 3b 拆分為多個並行子任務時，可選用描述性後綴標記模組名稱：

| 模式 | 用途 | 範例 |
|------|------|------|
| `-{module-name}` | 模組或功能名稱 | `0.1.0-W44-003.1-ui.md`, `0.1.0-W44-003.2-logic.md` |

**規則**：只含小寫字母、數字、連字號，長度 1-60 字元。

---

## 3. 禁止的命名模式

以下模式**禁止使用**，違規檔案會被 Hook 提示：

| 禁止模式 | 原因 | 建議 |
|---------|------|------|
| 大寫字母（如 `-Phase1`） | 與小寫規範不一致 | 改為 `-phase1` |
| 空格（如 `-phase 1`） | 檔名規範禁止空格 | 改為 `-phase-1` |
| 下劃線（如 `-phase_1`） | 保持連字號統一 | 改為 `-phase-1` |
| 超過 60 字元後綴 | 過長後綴增加識別難度 | 縮短描述 |
| 自由描述後綴（如 `-my-notes`） | 非預定義模式，系統無法識別 | 使用標準後綴 |
| 多個後綴（如 `-phase1-design-v2`） | 規範不支援，容易歧義 | 只使用一個後綴 |

---

## 4. Ticket 檔案命名清單（現存後綴清單）

本清單列出專案實際使用的所有後綴檔案，已被系統識別為有效。

### TDD Phase 文件 - Phase 1（設計）
1. `0.1.0-W11-004-phase1-design.md`
2. `0.1.0-W22-007-phase1-design.md`
3. `0.1.0-W39-001-phase1-design.md`
4. `0.1.0-W41-002-phase1-feature-spec.md`
5. `v0.1.0-W44-003-feature-design.md`

### TDD Phase 文件 - Phase 2（測試設計）
6. `0.1.0-W1-005-phase2-test-design.md`
7. `0.1.0-W11-004-phase2-tests.md`（變體：`-tests` 代替 `-test-design`）
8. `0.1.0-W22-007-phase2-tests.md`（變體：`-tests` 代替 `-test-design`）
9. `0.1.0-W39-001-phase2-test-design.md`
10. `0.1.0-W41-001-phase2-test-design.md`
11. `0.1.0-W41-002-phase2-test-design.md`
12. `0.1.0-W43-006-test-design.md`（縮寫：`-test-design` 代替 `-phase2-test-design`）
13. `v0.1.0-W44-003-phase2-test-design.md`

### TDD Phase 文件 - Phase 3a（策略）
14. `0.1.0-W11-004-phase3a-strategy.md`
15. `0.1.0-W22-007-phase3a-strategy.md`
16. `0.1.0-W39-001-phase3a-strategy.md`
17. `0.1.0-W41-001-phase3a-strategy.md`
18. `0.1.0-W41-002-phase3a-strategy.md`
19. `v0.1.0-W44-003-phase3a-strategy.md`

### TDD Phase 文件 - Phase 3b（執行和測試）
20. `0.1.0-W37-002-test-case-design.md`（Phase 2 變體：`-test-case-design`）
21. `0.1.0-W39-001-phase3b-test-report.md`
22. `0.1.0-W44-003-phase3b-execution-log.md`
23. `0.1.0-W41-001-phase3b-execution-report.md`
24. `v0.1.0-W44-003-phase3b-execution-report.md`

### TDD Phase 文件 - Phase 4（重構）
25. `0.1.0-W2-014-refactoring-report.md`
26. `0.1.0-W39-refactor.md`
27. `v0.1.0-W44-003-refactor.md`
28. `v0.2.0-W3-001-refactor.md`

### 分析和報告
29. `0.1.0-W1-005-test-cases.md`
30. `0.1.0-W1-005-test-cases-quick-reference.md`
31. `0.1.0-W25-005-analysis.md`
32. `0.1.1-W1-004-uc-analysis.md`

### 邊界情況（具體描述性後綴）
33. `v0.1.0-refactor-ticket-cli-set-relations.md`（非常具體的模組名稱後綴：`-refactor-ticket-cli-set-relations`，**不納入白名單**）
34. `v0.2.0-onboarding-framework.md`（內容描述後綴：`-onboarding-framework`，**不納入白名單**）

### 非規範檔案（需更正）
35. `W41-refactor-worklog.md`（**非規範格式**：缺少版本號前綴，應改為 `0.1.0-W41-xxx-refactor-worklog.md`）

**現狀**：清單中 32 個正規檔案均可被 `extract_core_ticket_id()` 函式正確解析，並在 `list_tickets()` 中進行去重載入。2 個邊界檔案因其過度具體的描述後綴**故意不納入白名單**（目的是讓這類"一次性"後綴受到 Hook 警告，提醒檔案命名是否合適），1 個非規範檔案需修正。

---

## 5. Hook 驗證規則

### 標準 ID 驗證（嚴格）

檔案名符合標準格式（無後綴）時，Hook 執行：
- 格式驗證（正則匹配）
- 波次範圍驗證（1-999）
- 版本一致性驗證（目錄版本 = ID 版本）

**不符合時**：輸出 WARNING，不阻止操作（exit 0）。

### 帶後綴 ID 驗證（寬鬆）

檔案名帶描述性後綴時，Hook 執行：
- 格式驗證（正則匹配）
- **不執行波次和版本檢查**（寬鬆驗證）
- 後綴識別：
  - 後綴在已知清單 → 輸出 INFO（已識別）
  - 後綴不在清單 → 輸出 WARNING（建議檢查）

**結果**：無論何種情況，都不阻止操作（exit 0），只提示。

---

## 6. 操作指南

### 情景 1：建立新 TDD Phase 文件

```
Step 1: 識別你正在完成的 Phase（例如 Phase 1）
Step 2: 從上方表格選擇對應後綴（例如 "-phase1-design"）
Step 3: 組建檔名
        核心 ID: 0.1.0-W44-003
        後綴: -phase1-design
        檔名: 0.1.0-W44-003-phase1-design.md
Step 4: 建立檔案（Hook 會自動提示並驗證）
```

### 情景 2：建立分析報告

```
Step 1: 確認 Ticket Type 為 ANA
Step 2: 選擇合適的分析後綴（例如 "-analysis"）
Step 3: 建立檔案（例如 0.1.0-W25-005-analysis.md）
```

### 情景 3：建立標準 Ticket 檔案

```
Step 1: 不需要添加後綴
Step 2: 使用標準格式（例如 0.31.0-W3-001.md）
Step 3: Hook 執行完整驗證（格式、波次、版本一致性）
```

---

## 7. 後綴設計原則

### 為什麼限制小寫？

全系統採用小寫字母開頭的後綴，確保：
1. **一致性**：所有後綴遵循統一風格
2. **可搜尋性**：避免大小寫變體（如 `-Phase1` vs `-phase1`）
3. **系統識別**：正則表達式簡化，減少誤判

### 為什麼限制 60 字元？

1. **檔案系統相容**：大多數檔案系統對完整路徑有限制
2. **可讀性**：過長後綴難以辨識
3. **命令列友善**：縮短檔名便於 shell 操作

### 可否自訂後綴？

**禁止**。為確保系統一致性和可維護性，只允許上方列表中的後綴。

若需要新的後綴模式，請：
1. 評估需求合理性
2. 建立 Ticket 提出新後綴建議
3. 納入 KNOWN_TICKET_SUFFIXES 常數後統一使用

---

## 8. 與 Ticket ID 系統的整合

### 核心模組

| 模組 | 位置 | 職責 |
|------|------|------|
| `TICKET_ID_PATTERN` | `ticket_system/lib/constants.py` | 標準正則表達式 |
| `KNOWN_TICKET_SUFFIXES` | `ticket_system/lib/constants.py` | 已知後綴清單 |
| `extract_core_ticket_id()` | `ticket_system/lib/id_parser.py` | 提取核心 ID（去後綴） |
| `has_description_suffix()` | `ticket_system/lib/id_parser.py` | 判斷是否帶後綴 |
| `list_tickets()` | `ticket_system/lib/ticket_loader.py` | 掃描載入，支援去重 |
| `ticket-id-validator-hook.py` | `.claude/hooks/` | Hook 驗證，寬鬆模式 |

### 工作流程

```
檔案建立
    ↓
PostToolUse Hook 觸發
    ↓
ticket-id-validator-hook.py 執行
    ├─ 提取檔名 → 判斷是否為 Ticket 檔案
    ├─ 使用 TICKET_ID_REGEX（含後綴支援）匹配
    ├─ 如帶後綴 → 寬鬆驗證（只提示，不阻止）
    └─ 如標準 → 完整驗證（格式+波次+版本）
    ↓
Hook 提示或警告（不阻止操作，exit 0）
    ↓
list_tickets() 掃描載入
    ├─ 使用 extract_core_ticket_id() 提取核心 ID
    ├─ 使用 loaded_core_ids 集合去重
    └─ 只載入一次（優先標準檔，跳過後綴檔）
```

---

## 9. 常見問題

### Q: 為什麼我的檔案被認為是 Ticket？

A: 檔案名符合正則表達式 `^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$`
且存放在 `docs/work-logs/v{version}/tickets/` 目錄下。

### Q: 後綴是否區分大小寫？

A: 是。後綴必須全小寫。例如 `-phase1-design` 有效，`-Phase1-Design` 無效。

### Q: 能否自訂後綴？

A: 不能。只允許本文件列出的已知後綴。新需求應建立 Ticket 提出建議。

### Q: 同一 Ticket 能否有多個檔案（標準檔 + 後綴檔）？

A: 可以，但只會載入一次。系統使用核心 ID 去重，優先載入標準檔案。

**範例**：
- 存在 `0.1.0-W11-004.md` 和 `0.1.0-W11-004-phase1-design.md`
- 結果：只載入 `0.1.0-W11-004.md`

### Q: 為什麼有些現存檔案不符合規範？

A: W43-005 分析發現 22 個非標準檔案。W44-003 實作的擴充正是為了支援這些檔案，同時維持向後相容。

---

## 10. 相關檔案

| 檔案 | 說明 |
|------|------|
| `.claude/skills/ticket/ticket_system/lib/constants.py` | TICKET_ID_PATTERN + KNOWN_TICKET_SUFFIXES 定義 |
| `.claude/skills/ticket/ticket_system/lib/id_parser.py` | ID 解析函式 |
| `.claude/skills/ticket/ticket_system/lib/ticket_loader.py` | Ticket 載入與去重 |
| `.claude/hooks/ticket-id-validator-hook.py` | Hook 驗證邏輯（寬鬆模式） |
| `.claude/rules/core/quality-python.md` | Python 常數管理規範 |
| `.claude/references/ticket-id-existing-suffixes.md` | 現存後綴範例清單（第 4 節外放） |

---

**Last Updated**: 2026-03-13
**Status**: Published (Phase 3b 實作完成)
**Related Ticket**: 0.1.0-W44-003 (ID 解析包容性擴充)
**Version**: 1.1.0 - 第 4 節例外清單外放至 references/（0.1.0-W48-004）
