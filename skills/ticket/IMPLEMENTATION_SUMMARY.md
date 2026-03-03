# Ticket Generator + Generate Command 實現總結

## 實現範圍

完成了 Ticket 0.31.0-W5-001.6 的核心需求：

### 1. ticket_generator.py（新建）
位置：`ticket_system/lib/ticket_generator.py`

**主要功能**：
- `GeneratedTicket` 資料類：代表生成的單一 Ticket
- `GenerationResult` 資料類：代表生成結果（包含成功/失敗狀態）
- `generate()` 函式：主要生成邏輯
  - 接收 PlanParseResult 和版本、Wave 資訊
  - 應用 TDD 階段映射規則（IMP → Phase 1-4, ADJ → Phase 3b-4, DOC → 無 TDD）
  - 執行 Wave 分配算法（根據複雜度自動分組）
  - 應用並行分組優化
  - 呼叫 ticket_builder 建構 Ticket 內容
  - 支援 dry-run 預演模式

**內部函式**：
- `_get_tdd_stages()`: 根據任務類型和複雜度取得 TDD 階段
- `_map_tdd_stages()`: 映射每個任務的 TDD 階段
- `_assign_wave()`: 分配 Wave 編號
- `_format_ticket_content()`: 格式化 Ticket 內容

### 2. commands/generate.py（新建）
位置：`ticket_system/commands/generate.py`

**主要功能**：
- `register()` 函式：註冊 generate 子命令到 argparse
- `execute()` 函式：主執行邏輯
  1. 驗證 Plan 檔案存在
  2. 驗證版本號和 Wave 號
  3. 呼叫 plan_parser.parse_plan() 解析
  4. 呼叫 ticket_generator.generate() 產生
  5. 預演模式：顯示預覽不寫入
  6. 正常模式：寫入 Ticket 檔案

**CLI 介面**：
```bash
ticket generate <plan_file> --version <ver> --wave <wave> [--dry-run]
```

**內部函式**：
- `_print_generation_summary()`: 顯示生成摘要
- `_save_tickets()`: 保存生成的 Tickets 到檔案

### 3. 命令註冊
- 更新 `commands/__init__.py`: 新增 generate 的 register 導出
- 更新 `scripts/ticket.py`: 註冊 generate 子命令到主 argparse

### 4. messages.py 擴展
- 新增 `GenerateMessages` 類別，包含：
  - `GENERATION_SUMMARY`: 生成摘要訊息
  - `TICKETS_PREVIEW`: Tickets 預覽訊息
  - `TICKETS_SAVED`: 保存成功訊息
  - 錯誤訊息（計畫解析失敗、無任務等）

### 5. 測試
- 新建 `tests/test_ticket_generator.py`: 完整單元測試套件
  - 17 個測試，100% 通過
  - 覆蓋所有核心功能和邊界情況

## 技術特色

### TDD 階段映射規則
實作了根據任務類型的智能 TDD 階段選擇：
- **IMP（實作）**：完整 TDD → Phase 1-4（高複雜度加 Phase 0）
- **ADJ（調整）**：簡化 TDD → Phase 3b-4
- **DOC（文件）**：無 TDD

### Wave 分配算法
自動根據複雜度分配 Wave：
- 低複雜度（< 6）：同一 Wave
- 中複雜度（6-10）：同一 Wave
- 高複雜度（> 10）：增加 Wave 分隔

### 內容生成
完整的 YAML Frontmatter + Markdown Body 生成：
- 使用 `create_ticket_frontmatter()` 產生 frontmatter
- 使用 `create_ticket_body()` 產生 body
- 自動格式化為完整 Markdown 文檔

## 驗證結果

### 測試結果
- **新增測試**：17 個（全部通過）
- **現有測試**：339 個（全部通過）
- **總計**：356 個測試，100% 通過

### CLI 測試
```bash
$ uv run ticket generate --help
usage: ticket generate [-h] --version VERSION --wave WAVE [--dry-run]
                       plan_file

positional arguments:
  plan_file          Plan 檔案路徑（Markdown 格式）

options:
  -h, --help         show this help message and exit
  --version VERSION  版本號（如 0.31.0）
  --wave WAVE        基礎 Wave 編號
  --dry-run          預演模式（不實際建立檔案）
```

## 驗收條件檢查

✅ **1. ticket_generator.py 建立完成**
- GeneratedTicket 資料類：✅
- GenerationResult 資料類：✅
- 完整的生成邏輯：✅

✅ **2. 支援 TDD 階段映射和 Wave 分配**
- TDD 階段映射規則實作：✅
- Wave 分配算法實作：✅
- 認知負擔高時加 Phase 0：✅

✅ **3. commands/generate.py 建立完成**
- register() 函式：✅
- execute() 函式：✅
- CLI 介面完整：✅

✅ **4. 命令已註冊**
- __init__.py 更新：✅
- ticket.py 更新：✅

✅ **5. messages.py 新增 GenerateMessages 類別**
- 訊息類別：✅
- 格式化函式：✅

✅ **6. dry-run 模式正常運作**
- 預演模式實作：✅
- 不建立實際檔案：✅

✅ **7. 所有新增和現有測試通過**
- 新增 17 個測試：✅ 全部通過
- 現有 339 個測試：✅ 全部通過

## 程式碼品質

### 認知負擔評估
- `generate()` 函式：認知負擔 6（中等，可接受）
- `execute()` 函式：認知負擔 7（中等，可接受）
- 平均函式長度：< 30 行
- 無重複程式碼：✅（使用現有 ticket_builder）
- 完整型別標註：✅

### 遵循現有架構
- 遵循 ticket_builder 的設計模式：✅
- 使用 TicketConfig TypedDict：✅
- 遵循 messages.py 的訊息結構：✅
- 遵循命令註冊模式：✅

## 後續使用

### 基本用法
```bash
# 預演模式（查看會產生哪些 Tickets）
uv run ticket generate plans/my-plan.md --version 0.31.0 --wave 5 --dry-run

# 正常模式（實際建立 Tickets）
uv run ticket generate plans/my-plan.md --version 0.31.0 --wave 5
```

### 全局安裝
```bash
cd .claude/skills/ticket
uv tool install . --force
# 之後可以在任何目錄使用：
ticket generate plans/my-plan.md --version 0.31.0 --wave 5
```

## 已知限制

1. Wave 分配算法採用簡單策略（基於複雜度）
   - 未來可考慮基於文件重疊的更複雜算法

2. 並行分組優化在生成階段未實現
   - 目前在 generate 命令產出報告時建議
   - 實際的並行檢查由 create 命令的 ParallelAnalyzer 執行

3. TDD Phase 0（SA 前置審查）僅在 IMP 類型且複雜度 > 10 時自動加入
   - 可考慮在 generate 命令新增參數手動控制

## 相關檔案

- 主要實作：
  - `ticket_system/lib/ticket_generator.py`
  - `ticket_system/commands/generate.py`
  - `ticket_system/lib/messages.py`
  - `ticket_system/commands/__init__.py`
  - `ticket_system/scripts/ticket.py`

- 測試：
  - `tests/test_ticket_generator.py`

- 參考規格：
  - `.claude/rules/flows/plan-to-ticket-flow.md`（Plan-to-Ticket 轉換流程）
  - `.claude/rules/core/cognitive-load.md`（認知負擔設計原則）

## 符合要求

✅ 所有 7 個驗收條件都已滿足
✅ 339 個現有測試未受影響（全部通過）
✅ 新增 17 個測試（全部通過）
✅ 認知負擔指數 < 10
✅ 完整型別標註
✅ 遵循現有架構和風格
✅ CLI 命令已正確註冊
