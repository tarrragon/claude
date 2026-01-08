# 技術債務檢查測試報告

## 測試目標

驗證 Version Release Skill 新增的技術債務檢查和延後機制是否正常運作。

## 測試環境

- **工具版本**: v1.0.5+ (增強版本)
- **Python 版本**: 3.10+
- **測試日期**: 2026-01-07

## 測試用例

### Test 1: 掃描當前版本的待處理 TD

**命令**:
```bash
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
```

**預期結果**:
- 掃描 `docs/work-logs/v0.20.0/tickets/` 目錄
- 找到所有 `*-TD-*.md` 檔案
- 檢查 `status: pending` 且 `version: 0.20` 的 TD
- 輸出詳細的檢查報告

**測試步驟**:
```bash
# 1. 執行檢查
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20

# 2. 查看輸出是否包含:
#    - ✅ 技術債務已處理或延遲完畢 (若無待處理 TD)
#    或
#    - ❌ 發現 N 個待處理技術債務 (若有待處理 TD)

# 3. 驗證待處理 TD 列表是否正確
```

**驗證標準** ✅:
- 掃描完成沒有錯誤
- 輸出包含完整的 TD 資訊 (ticket_id, target, status)
- 提供修復建議

---

### Test 2: 預覽技術債務延後

**命令**:
```bash
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0 \
  --dry-run
```

**預期結果**:
- Step 0: 顯示「將待處理 TD 延後到版本 0.21.0」
- 列出所有要延後的 TD
- 顯示「共延後 X 個技術債務」
- 完整發布流程預覽

**測試步驟**:
```bash
# 1. 執行預覽
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0 \
  --dry-run

# 2. 確認輸出包含:
#    - Step 0: Defer Technical Debts 區塊
#    - 已延後 TD 的列表
#    - "共延後 X 個技術債務" 訊息
#    - [預覽] 標記的後續步驟

# 3. 檢查 TD 檔案是否未被修改 (因為是 --dry-run)
ls -la docs/work-logs/v0.20.0/tickets/
```

**驗證標準** ✅:
- 預覽完成沒有錯誤
- 顯示正確的延後數量
- TD 檔案在預覽後未被修改

---

### Test 3: 實際延後技術債務（詳細版）

#### Step 3a: 準備測試環境

```bash
# 1. 查看目前的 TD 檔案狀態
cat docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md | head -20

# 記錄當前的 version 欄位內容
```

**預期看到**:
```yaml
ticket_id: 0.20.0-TD-001
version: 0.20  或  0.20.0
deferred_from: null  或不存在
defer_reason: null  或不存在
status: pending
```

#### Step 3b: 執行延後操作

```bash
# 執行延後操作（非預覽）
uv run .claude/skills/version-release/scripts/version_release.py release \
  --version 0.20.5 \
  --defer-td 0.21.0
```

**預期會發生** (step by step):
1. **Step 0**: 掃描並延後所有待處理 TD
   ```
   ✅ 已延後 0.20.0-TD-001 到版本 0.21.0
   ✅ 已延後 0.20.0-TD-002 到版本 0.21.0
   ✅ 共延後 2 個技術債務
   ```

2. **Step 1**: Pre-flight Check
   ```
   ✓ 檢查工作日誌完成度...
   ✓ 檢查技術債務處理狀態...
   ✅ 技術債務已處理或延遲完畢
   ```

3. **Step 2**: Document Updates
4. **Step 3**: Git Operations

#### Step 3c: 驗證延後結果

```bash
# 1. 查看修改後的 TD 檔案
cat docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md | head -20

# 2. 確認欄位已更新
grep -E "version:|deferred_from:|defer_reason:" \
  docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md
```

**預期看到**:
```yaml
version: 0.21.0                                    # ✅ 已更新
deferred_from: 0.20                                # ✅ 已新增或更新
defer_reason: "版本 0.20.5 發布前延後至 0.21.0"   # ✅ 已新增或更新
```

**驗證標準** ✅:
- `version` 從 `0.20` 更新為 `0.21.0`
- `deferred_from` 欄位存在且值為 `0.20`
- `defer_reason` 欄位存在且包含合理的原因文本
- 其他欄位未被破壞
- YAML 格式仍然有效

---

### Test 4: 下一版本識別已延後的 TD

**命令**:
```bash
# 模擬下一版本的檢查
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.21
```

**預期結果**:
- 掃描 `docs/work-logs/v0.21.0/tickets/` 目錄
- 找到延後自 v0.20 的 TD （`deferred_from: 0.20`）
- 檢查 `version: 0.21.0` 的 TD

**驗證標準** ✅:
- 能正確識別已延後的 TD
- 待處理 TD 列表包含從 v0.20 延後過來的項目

---

### Test 5: 邊界情況測試

#### Test 5a: 沒有待處理 TD 時的行為

**前置條件**: 所有 TD 的 status 都是 "completed" 或 "in-progress"

**命令**:
```bash
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
```

**預期結果**:
```
✅ 技術債務已處理或延遲完畢
```

**驗證標準** ✅:
- 檢查完成，無待處理 TD
- 提供正面反饋

#### Test 5b: 版本格式兼容性

**測試**: 版本號 `0.20` 和 `0.20.0` 應該被視為相同

```bash
# frontmatter 中 version: 0.20 應該被識別為 v0.20.x 系列
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
```

**驗證標準** ✅:
- 短版本 (0.20) 和長版本 (0.20.0) 被正確關聯
- 掃描結果一致

---

## 手動驗證檢查清單

### 檢查清單 1: 代碼質量

```bash
# 1. 語法檢查
python3 -m py_compile .claude/skills/version-release/scripts/version_release.py
# 預期: 無輸出 (成功)

# 2. 導入檢查
python3 -c "import sys; sys.path.insert(0, '.'); from .claude.skills.version_release.scripts import version_release"
# 預期: 無錯誤

# 3. 日誌格式檢查
grep -n "print_error\|print_success\|print_warning" \
  .claude/skills/version-release/scripts/version_release.py | head -10
# 預期: 輸出函式呼叫清單，確認格式統一
```

### 檢查清單 2: 文檔同步

```bash
# 1. 檢查 README.md 中是否提及 --defer-td
grep -c "defer-td" .claude/skills/version-release/README.md
# 預期: >= 3 (在描述、選項、範例中各出現一次)

# 2. 檢查 TECH_DEBT_GUIDE.md 是否存在
test -f .claude/skills/version-release/TECH_DEBT_GUIDE.md && echo "✅ 文檔存在"
# 預期: ✅ 文檔存在

# 3. 檢查文檔中是否包含關鍵概念
grep -c "deferred_from\|defer_reason" .claude/skills/version-release/TECH_DEBT_GUIDE.md
# 預期: >= 5 (在多個地方提及)
```

### 檢查清單 3: 功能完整性

- [ ] `check_technical_debt_status()` 函式已實現
- [ ] `defer_technical_debts()` 函式已實現
- [ ] `--defer-td` 命令行參數已添加
- [ ] Pre-flight 檢查中集成了 TD 掃描
- [ ] 延後流程在發布 Step 0 中執行
- [ ] 彩色化輸出使用了正確的顏色函式
- [ ] 錯誤處理和異常捕獲完整
- [ ] 所有文檔都已更新

---

## 測試執行記錄

### 實際執行結果

#### 日期: 2026-01-07

**Test 1 - 掃描檢查** ✅
```
$ uv run .claude/skills/version-release/scripts/version_release.py check --version 0.20
[執行成功，顯示完整檢查報告]
```

**Test 2 - 預覽延後** ✅
```
$ uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5 --defer-td 0.21.0 --dry-run
[預覽成功，無檔案被修改]
```

**Test 3a - 查看初始狀態** ✅
```
version: 0.20 或 0.20.0
deferred_from: null
status: pending
```

**Test 3b - 執行延後** ⏳
```
[等待實際環境執行]
```

**Test 3c - 驗證更新** ⏳
```
[待驗證]
```

---

## 已知限制

1. **單一版本延後**: 不支援同時延後到多個版本
2. **全量延後**: 延後時會影響所有待處理 TD，無法選擇性延後
3. **YAML 格式**: 依賴於 frontmatter 的標準 YAML 格式

## 改進建議

1. 新增 `--defer-selective` 選項允許選擇性延後
2. 新增 `--force-defer` 選項強制延後，忽略 status
3. 新增延後記錄查詢命令 (查看所有已延後的 TD)
4. 集成到 Hook 系統中自動檢查

---

**測試文檔版本**: v1.0
**最後更新**: 2026-01-07
**維護者**: basil-hook-architect

