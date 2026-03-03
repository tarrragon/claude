# 技術債務檢查與延後指南

## 概述

Version Release Skill 新增了**自動技術債務檢查**和**延後機制**，確保發布時不會遺漏待處理的技術債務。

## 功能說明

### 1. 自動技術債務掃描

在發布流程中，工具會自動掃描當前版本目錄下的所有技術債務票（`*-TD-*.md` 檔案）。

**掃描條件**:
- 文件位置: `docs/work-logs/vX.Y.0/tickets/*-TD-*.md`
- 檢查欄位: `status: pending` 且 `version` 欄位等於當前版本號

**輸出結果**:
```
✓ 檢查技術債務處理狀態...
✅ 技術債務已處理或延遲完畢

或者

❌ 發現 4 個待處理技術債務（目標版本 v0.20.x）

待處理技術債務:
  - 0.20.0-TD-001: `book_tags.book_id` 缺少資料庫索引 (pending)
  - 0.20.0-TD-002: 錯誤處理邏輯抽取 (pending)
  - 0.20.0-TD-003: linter 警告 (pending)
  - 0.20.0-TD-004: BackgroundProcessingService 整合 (pending)

解決方式:
  1. 處理這些技術債務後再發布
  2. 使用 --defer-td 0.21.0 明確延後到下一版本
```

### 2. 延後技術債務機制

如果無法在當前版本處理所有 TD，可使用 `--defer-td` 選項延後到下一版本。

#### 命令格式

```bash
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0 \
  [--dry-run]
```

#### 執行流程

**Step 0: Defer Technical Debts**
1. 掃描版本目錄的所有 TD 票
2. 找到所有 `status: pending` 且 `version: 0.20` 的 TD
3. 更新欄位:
   - `version`: `0.20` → `0.21.0`
   - `deferred_from`: 新增/更新為 `0.20`
   - `defer_reason`: 新增/更新為 `"版本 0.20.5 發布前延後至 0.21.0"`
4. 輸出延後結果

**Step 1-3**: 正常的發布流程

### 3. 技術債務檔案結構

```yaml
---
# === Identification ===
ticket_id: 0.20.0-TD-001
ticket_type: "tech-debt"
version: 0.21.0              # 目標版本（會被更新）
deferred_from: 0.20          # 延後自哪個版本（會被更新）
defer_reason: "..."          # 延後原因（會被更新）

# === Technical Debt Specific ===
source_version: v0.19.8      # 原始版本
source_uc: UC-08             # 原始 UC
risk_level: low              # 風險等級
original_id: TD-001

# === Single Responsibility ===
action: Fix                  # 動作類型
target: "描述"               # 目標描述

# === Status Tracking ===
status: pending              # pending / in-progress / completed
assigned: false              # 是否已分派
started_at: null
completed_at: null
---
```

## 使用範例

### 範例 1: 檢查待處理 TD

```bash
# 只執行檢查，不做任何修改
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
```

**輸出**:
```
✓ 檢查技術債務處理狀態...
✅ 技術債務已處理或延遲完畢

# 或者

❌ 發現 2 個待處理技術債務（目標版本 v0.20.x）

待處理技術債務:
  - 0.20.0-TD-001: `book_tags.book_id` 缺少資料庫索引 (pending)
  - 0.20.0-TD-003: linter 警告 (pending)

解決方式:
  1. 處理這些技術債務後再發布
  2. 使用 --defer-td 0.21.0 明確延後到下一版本
```

### 範例 2: 預覽延後結果

```bash
# 預覽 TD 延後
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0 \
  --dry-run
```

**輸出**:
```
╔══════════════════════════════════════════════════════════╗
║ Version Release Tool - 0.20.0 (DRY RUN)                  ║
╚══════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 0: Defer Technical Debts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 將待處理 TD 延後到版本 0.21.0...
✅ 已延後 0.20.0-TD-001 到版本 0.21.0
✅ 已延後 0.20.0-TD-003 到版本 0.21.0

✅ 共延後 2 個技術債務

[預覽模式：不會執行實際的 git 操作]
```

### 範例 3: 實際執行延後和發布

```bash
# 實際執行 TD 延後和發布
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0
```

此命令會：
1. ✅ 更新所有待處理 TD 的版本和延後信息
2. ✅ 執行完整的發布流程（文件更新、Git 操作等）
3. ✅ 完成版本發布

## 最佳實踐

### 1. 優先處理待處理 TD

**推薦**:
```bash
# 優先在發布前處理 TD
1. 檢查待處理 TD
   uv run version_release.py check --version 0.20

2. 根據提示處理每個 TD
   - 更新 TD 票中的 status 為 in-progress / completed
   - 填充 Execution Log

3. 再次檢查確認 status 都是 completed
   uv run version_release.py check --version 0.20

4. 執行發布
   uv run version_release.py release --version 0.20.5
```

### 2. 必要延後時明確標記

**場景**: 某些 TD 無法在當前版本完成，但時間緊迫

```bash
# 使用 --defer-td 明確延後
uv run version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0

# 此時 defer_reason 會自動記錄延後原因
# 下一版本開發時可以查看並優先處理已延後的 TD
```

### 3. 定期追蹤已延後的 TD

```bash
# 在下一版本的 todolist.yaml 中查看已延後的 TD
cat docs/todolist.yaml | grep -A 5 "已延後 TD"

# 在新版本的發布流程中優先處理
uv run version_release.py check --version 0.21
```

## 技術細節

### 掃描邏輯

```python
# 檢查條件
is_current_version = (
    target_version == "0.20" or target_version == "0.20.0"
)
is_pending = status == "pending"

# 只掃描符合條件的 TD
if is_current_version and is_pending:
    result["pending_count"] += 1
    result["pending_tds"].append({...})
```

### 延後邏輯

```python
# 對每個待處理 TD 執行
1. 讀取 frontmatter
2. 更新 version 欄位
3. 更新/新增 deferred_from 欄位
4. 更新/新增 defer_reason 欄位
5. 寫回檔案
```

### 版本匹配策略

工具支援兩種版本格式的匹配：
- `version: 0.20` (短格式)
- `version: 0.20.0` (長格式)

均會被視為當前版本系列 v0.20.x

## 常見問題

### Q: 如果沒有待處理 TD，會發生什麼？

**A**: 掃描會正常完成，輸出：
```
✅ 技術債務已處理或延遲完畢
```
發布流程會繼續進行。

### Q: 可以延後到多個版本嗎？

**A**: 否。--defer-td 參數只接受一個版本號。如果需要在多個版本間移動，可在後續版本中再次使用 --defer-td。

### Q: 延後的 TD 會自動進入下一版本的檢查嗎？

**A**: 是的。下一版本發布時執行 `check` 或 `release` 時，工具會自動掃描所有 `version: 0.21.0` 的 TD。

### Q: 可以只延後特定的 TD 嗎？

**A**: 目前版本會延後所有待處理 TD。如果需要有選擇性地延後，可在發布前手動更新特定 TD 的 status 為 "completed" 或 "in-progress"。

### Q: 如何確認延後操作是否成功？

**A**:
1. 使用 `--dry-run` 預覽結果
2. 檢查輸出是否列出所有延後的 TD
3. 手動查看 TD 檔案確認欄位已更新

## 故障排除

### 問題: 掃描不到待處理 TD

**檢查清單**:
1. ✅ TD 檔案是否在正確位置: `docs/work-logs/vX.Y.0/tickets/*-TD-*.md`
2. ✅ frontmatter 格式是否正確 (必須以 `---` 開頭結尾)
3. ✅ `status` 欄位是否設為 `pending`
4. ✅ `version` 欄位是否匹配當前版本系列

### 問題: 延後操作失敗

**檢查清單**:
1. ✅ TD 檔案是否可讀寫
2. ✅ YAML 格式是否正確
3. ✅ --defer-td 參數格式是否正確 (例如 `0.21.0`)
4. ✅ 使用 --dry-run 預覽是否有錯誤提示

### 問題: defer_reason 未被更新

**解決方案**:
1. 如果 frontmatter 中 defer_reason 為 `null` 或 `""`，工具會正確更新
2. 如果為其他值，工具會嘗試用正則表達式替換
3. 若仍未更新，手動檢查檔案格式是否有特殊字符導致正則匹配失敗

## 相關文檔

- [Version Release README](./README.md) - 完整功能說明
- [SKILL.md](./SKILL.md) - 詳細技術文件
- 技術債務設計: `docs/work-logs/vX.Y.0/README.md`

---

**最後更新**: 2026-01-07
**維護者**: basil-hook-architect
