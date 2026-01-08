# 技術債務檢查 - 快速開始指南

## 🚀 3 分鐘快速開始

### 基本用法

#### 1. 檢查待處理 TD

```bash
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
```

**結果**:
- ✅ `技術債務已處理或延遲完畢` - 無待處理 TD，可發布
- ❌ `發現 N 個待處理技術債務` - 有待處理 TD，需處理或延後

#### 2. 延後 TD 並發布（推薦）

```bash
# 預覽
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0 \
  --dry-run

# 實際執行
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0
```

**效果**:
1. 掃描所有 pending TD
2. 更新 version 為 0.21.0
3. 設定 deferred_from 為 0.20
4. 記錄延後原因
5. 完成發布流程

#### 3. 標準發布（優先選擇）

```bash
# 檢查是否有待處理 TD
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20

# 如果有 TD，先處理它們（更新 status 為 completed）
# 然後發布
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5
```

## 📋 常用命令速查

| 命令 | 用途 | 何時使用 |
|------|------|--------|
| `check` | 檢查是否有待處理 TD | 發布前快速檢查 |
| `release` | 標準發布流程 | 沒有待處理 TD 時 |
| `release --defer-td 0.21.0` | 延後 TD 並發布 | 無法在當前版本完成 TD |
| `release --dry-run` | 預覽發布流程 | 發布前確認無誤 |

## ✅ 發布前檢查清單

- [ ] 執行 `check --version 0.20` 確認 TD 狀態
- [ ] 若有待處理 TD：
  - [ ] 選擇：優先處理 TD 或使用 `--defer-td` 延後
- [ ] 執行 `release --dry-run` 預覽
- [ ] 執行 `release` 完成發布

## 🎯 選擇你的發布策略

### 策略 A: 優先處理 TD（推薦）

**優點**: 保持版本清晰，無遺留問題
**流程**:
```bash
1. 檢查
   uv run version_release.py check --version 0.20

2. 處理 TD
   更新每個 TD 的 status 為 completed

3. 再次檢查
   uv run version_release.py check --version 0.20

4. 發布
   uv run version_release.py release --version 0.20.5
```

### 策略 B: 延後 TD（時間緊迫）

**優點**: 快速發布，TD 記錄在案
**流程**:
```bash
1. 檢查
   uv run version_release.py check --version 0.20

2. 預覽延後
   uv run version_release.py release --version 0.20.5 --defer-td 0.21.0 --dry-run

3. 執行延後和發布
   uv run version_release.py release --version 0.20.5 --defer-td 0.21.0
```

## 🔍 理解輸出

### 檢查成功

```
✅ 技術債務已處理或延遲完畢
```
→ 沒有待處理 TD，可以發布

### 發現待處理 TD

```
❌ 發現 2 個待處理技術債務（目標版本 v0.20.x）

待處理技術債務:
  - 0.20.0-TD-001: `book_tags.book_id` 缺少資料庫索引 (pending)
  - 0.20.0-TD-003: linter 警告 (pending)

解決方式:
  1. 處理這些技術債務後再發布
  2. 使用 --defer-td 0.21.0 明確延後到下一版本
```

→ 選擇一種解決方式

### 延後成功

```
Step 0: Defer Technical Debts
📋 將待處理 TD 延後到版本 0.21.0...
✅ 已延後 0.20.0-TD-001 到版本 0.21.0
✅ 已延後 0.20.0-TD-003 到版本 0.21.0

✅ 共延後 2 個技術債務
```

→ TD 已延後，繼續發布流程

## 🆘 常見問題

**Q: 提示有待處理 TD，該怎麼辦？**
A: 二選一：
1. 優先選擇：在 TD 票中更新 status 為 completed，再發布
2. 備選：使用 `--defer-td 0.21.0` 延後並發布

**Q: 使用 --defer-td 後，TD 去哪裡了？**
A: TD 的 version 欄位從 0.20 改為 0.21.0，下一版本發布時會檢查

**Q: 可以只延後某個 TD 嗎？**
A: 目前延後所有 pending TD。若需選擇性延後，發布前手動更新特定 TD 的 status

**Q: 延後後如何追蹤 TD？**
A: 查看 TD 檔案的 `deferred_from` 和 `defer_reason` 欄位，了解延後歷史

## 📚 深入了解

需要詳細說明？查看完整文檔：

- **詳細指南**: `TECH_DEBT_GUIDE.md`
- **測試用例**: `tests/test_tech_debt_check.md`
- **完整更新**: `ENHANCEMENT_SUMMARY.md`
- **一般說明**: `README.md`

## 💡 最佳實踐

1. **定期檢查**: 發布前總是執行 `check` 命令
2. **優先處理**: 盡量優先處理 TD，而不是延後
3. **清晰記錄**: 延後 TD 時自動記錄原因
4. **定期追蹤**: 下一版本開發時優先處理已延後的 TD

---

**提示**: 在 `.claude/skills/version-release/` 目錄執行命令，或使用完整路徑

```bash
# 快速別名（可選）
alias vr='uv run .claude/skills/version-release/scripts/version_release.py'

# 之後可以使用
vr check --version 0.20
vr release --version 0.20.5 --defer-td 0.21.0 --dry-run
```

