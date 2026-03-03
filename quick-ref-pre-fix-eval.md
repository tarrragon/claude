# 修復前強制評估系統 - 快速參考

## 🚀 三步驟工作流

### Step 1: 自動偵測 (Hook 完成)

執行測試失敗時，Hook 自動分類錯誤：

```
flutter test → Hook 自動觸發
      ↓
錯誤分類
      ↓
語法錯誤? → 簡化流程（無需 Ticket）
      ↓
否 → 強制評估提示
```

### Step 2: 六階段評估 (使用 /pre-fix-eval)

按照 Skill 引導完成評估：

```
/pre-fix-eval

Stage 1: 錯誤分類 (Hook 已完成)
Stage 2: BDD 分析
Stage 3: 文件查詢
Stage 4: 根因定位
Stage 5: 開 Ticket ← 強制
Stage 6: 分派執行
```

### Step 3: 執行修復 (分派代理人)

根據根因分派，執行修復：

```
/ticket create → Ticket 建立
      ↓
代理人分派 (parsley 或 mint)
      ↓
修復執行
      ↓
測試驗證
```

## 🎯 錯誤分類速查表

| 錯誤類型 | 識別方式 | 流程 | 代理人 |
|---------|--------|------|--------|
| **語法** | `Expected '}' but...` | 簡化→直修 | mint |
| **編譯** | `can't be assigned` | 評估→Ticket→修 | parsley |
| **測試** | `Expected: ... Actual:` | 評估→Ticket→修 | parsley |
| **警告** | `info - unused` | 評估→Ticket | mint |

## ⚠️ 禁止行為

❌ 看到測試失敗就直接修改
❌ 跳過 Ticket 開設
❌ 修改測試（沒文件支持）
❌ 大規模重寫代碼

## ✅ 修復決策矩陣

| 情況 | 測試 | 代碼 | 決策 |
|------|------|------|------|
| 語法錯誤 | - | ❌ | 直接修 |
| 實作不完 | ❌ | ❌ | 補完 |
| 邏輯錯誤 | ❌ | ✅ | 修正邏輯 |
| 測試過時 | ❌ | ✅ | 更新測試 |
| 設計變更 | ❌ | ❌ | PM 審核 |

## 📋 Ticket 建立快速模板

```markdown
# Fix {ErrorType}: {簡短描述}

## 問題分析

**錯誤類型**: {SYNTAX/COMPILATION/TEST_FAILURE}
**位置**: {檔案:行}

## BDD 分析
Given: {前置條件}
When: {動作}
Then: {預期}

## 根因
{根因分析結果}

## 修復策略
{具體修復步驟}

## 驗收條件
- [ ] 測試通過
- [ ] 無新增失敗
- [ ] 代碼風格符合
```

## 🔗 常見情況快速跳轉

### 語法錯誤 (括號、分號)
→ **流程**: 直接分派 mint-format-specialist
→ **Ticket**: 不需要
→ **例子**: `Expected '}' but found 'void'`

### 編譯錯誤 (類型不匹配)
→ **流程**: Stage 1-5 → 開 Ticket → 分派
→ **代理人**: parsley-flutter-developer
→ **例子**: `type 'Book' is not a subtype of type 'String'`

### 測試失敗 (邏輯錯誤)
→ **流程**: Stage 1-5 → 開 Ticket → 分派
→ **代理人**: parsley-flutter-developer
→ **例子**: `Expected: true, Actual: false`

### Analyzer 警告 (未使用)
→ **流程**: 評估 → 開 Ticket → 延遲處理
→ **代理人**: mint-format-specialist
→ **例子**: `warning: unused import`

## 📊 Hook 自動輸出識別

### 簡化流程 (語法錯誤)
```
🔧 語法錯誤 - 簡化修復流程

錯誤數量: N
推薦代理人: mint-format-specialist

直接執行精確修復，無需開 Ticket。
```

### 強制評估流程 (其他錯誤)
```
🚨 修復前強制評估 - {ERROR_TYPE}

⚠️ 此錯誤類型 **必須開 Ticket** 追蹤

執行以下步驟：
1️⃣ 完成六階段評估 (使用 /pre-fix-eval)
2️⃣ 使用 /ticket create 建立修復 Ticket
3️⃣ Ticket 建立後分派給專業代理人執行
```

## 🧪 測試 Hook 功能

### 測試語法錯誤偵測

```bash
cat > /tmp/test.json << 'EOF'
{
  "tool_response": "Expected '}' but found 'void'\n  at lib/main.dart:42"
}
EOF

python3 .claude/hooks/pre-fix-evaluation-hook.py < /tmp/test.json
```

**預期**: 簡化流程輸出

### 測試編譯錯誤偵測

```bash
cat > /tmp/test.json << 'EOF'
{
  "tool_response": "type 'Book' is not a subtype of type 'String'"
}
EOF

python3 .claude/hooks/pre-fix-evaluation-hook.py < /tmp/test.json
```

**預期**: 強制評估輸出 (exit code 2)

### 測試成功情況

```bash
cat > /tmp/test.json << 'EOF'
{
  "tool_response": "All tests passed!"
}
EOF

python3 .claude/hooks/pre-fix-evaluation-hook.py < /tmp/test.json
```

**預期**: 無輸出 (exit code 0)

## 📁 重要檔案位置

| 用途 | 檔案 | 說明 |
|------|------|------|
| **Hook 腳本** | `.claude/hooks/pre-fix-evaluation-hook.py` | 自動分類錯誤 |
| **Skill** | `.claude/commands/pre-fix-eval.md` | 六階段評估流程 |
| **配置** | `.claude/settings.json` | PostToolUse Hook 配置 |
| **日誌** | `.claude/hook-logs/pre-fix-evaluation-*.json` | 評估結果記錄 |
| **實作說明** | `.claude/hook-specs/pre-fix-evaluation-implementation.md` | 完整技術文件 |

## 🆘 快速除錯

### 查看最新評估結果

```bash
ls -lt .claude/hook-logs/pre-fix-evaluation-*.json | head -1
cat .claude/hook-logs/pre-fix-evaluation-*.json | tail -1
```

### 啟用詳細日誌

```bash
HOOK_DEBUG=true python3 .claude/hooks/pre-fix-evaluation-hook.py < input.json
cat .claude/hook-logs/pre-fix-evaluation-hook.log | tail -20
```

### 驗證配置

```bash
python3 -m json.tool .claude/settings.json | grep -A 5 "pre-fix-evaluation"
```

## 💡 最佳實踐

### ✅ 做這些事

- ✅ 完成所有六階段評估再開始修復
- ✅ 使用 Ticket 記錄修復計劃
- ✅ 根據錯誤類型分派正確的代理人
- ✅ 修復後執行完整測試套件
- ✅ 檢查無新增失敗

### ❌ 不要做這些事

- ❌ 跳過評估流程
- ❌ 忽視「必須開 Ticket」的提示
- ❌ 修改測試作為修復方案
- ❌ 進行大規模重寫（應最小化修改）
- ❌ 直接分派非語法錯誤修復

## 📞 支援

遇到問題？

1. 查看完整技術文件: `.claude/hook-specs/pre-fix-evaluation-implementation.md`
2. 查看 Skill 詳細說明: `/pre-fix-eval`
3. 檢查日誌: `.claude/hook-logs/pre-fix-evaluation-hook.log`
4. 啟用 debug 模式: `HOOK_DEBUG=true`
