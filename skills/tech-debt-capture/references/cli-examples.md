# Tech Debt Capture CLI 範例

> 本文件提供 tech-debt-capture 腳本的詳細 CLI 使用範例。

---

## 批量模式

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md
```

**輸出**:

```
解析工作日誌
  找到 4 個技術債務項目

版本對應決策
  TD-001 (低) -> 0.20.0
  TD-002 (低) -> 0.20.0
  TD-003 (極低) -> 0.20.0 (可選)
  TD-004 (中) -> 0.20.0

建立 Ticket 檔案
  docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md
  docs/work-logs/v0.20.0/tickets/0.20.0-TD-002.md
  docs/work-logs/v0.20.0/tickets/0.20.0-TD-003.md
  docs/work-logs/v0.20.0/tickets/0.20.0-TD-004.md

更新 todolist.yaml
  技術債務追蹤區塊已更新

完成！共建立 4 個技術債務 Ticket
```

## 指定目標版本

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md \
    --target-version 0.20.0
```

## 預覽模式

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md \
    --dry-run
```

**輸出**:

```
預覽模式 - 不會建立實際檔案

將建立以下 Ticket:
  1. 0.20.0-TD-001 - 新增 book_tags.book_id 索引 (低)
  2. 0.20.0-TD-002 - 抽取共用錯誤處理邏輯 (低)
  3. 0.20.0-TD-003 - 清理 linter 警告 (極低)
  4. 0.20.0-TD-004 - 整合 BackgroundProcessingService (中)

預覽完成。執行不含 --dry-run 參數建立 Ticket
```

## 初始化版本目錄

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py init 0.20.0
```

建立版本目錄和 tickets 子目錄：

```
docs/work-logs/v0.20.0/
├── tickets/
├── v0.20.0-phase1-design.md
├── v0.20.0-phase2-test-design.md
├── v0.20.0-phase3a-strategy.md
└── (其他 Phase 工作日誌)
```

## 列出技術債務

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py list \
    --version 0.20.0
```

**輸出**:

```
v0.20.0 技術債務清單

Ticket ID         | 描述                      | 風險  | 來源版本 | 狀態
------------------|-------------------------|-------|---------|-------
0.20.0-TD-001     | 新增 book_tags 索引       | 低   | v0.19.8 | pending
0.20.0-TD-002     | 抽取錯誤處理邏輯          | 低   | v0.19.8 | pending
0.20.0-TD-003     | 清理 linter 警告          | 極低 | v0.19.8 | pending
0.20.0-TD-004     | 整合 Service              | 中   | v0.19.8 | pending
```

## 錯誤處理

### 常見問題

| 問題               | 原因                  | 解決方式                    |
| ------------------ | --------------------- | --------------------------- |
| 找不到工作日誌檔案 | 檔案路徑錯誤          | 確認檔案路徑和名稱          |
| 表格格式不符       | 日誌編輯後格式變化    | 檢查表格欄位名稱            |
| 版本目錄已存在     | 多次執行              | 使用 --force-overwrite 覆蓋 |
| Ticket 檔案衝突    | 已有相同 ID 的 Ticket | 查看現有 Ticket 或變更版本  |

### 修復指引

**問題**: `FileNotFoundError: docs/work-logs/v0.19.8-phase4.md`

```bash
# 1. 確認工作日誌檔案路徑
ls docs/work-logs/v0.19.8*

# 2. 使用正確的檔案名稱
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md
```

**問題**: `ValueError: 無法解析技術債務表格`

```bash
# 1. 檢查表格格式（應包含 ID, 描述, 風險等級, 建議處理時機 欄位）
# 2. 若表格名稱不同，檢查工作日誌內容
# 3. 使用 --dry-run 預覽解析結果
```
