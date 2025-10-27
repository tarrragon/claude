# thyme-documentation-integrator MCP 工具整合指南

> Serena MCP 和 Context7 MCP 使用細節
> Version: 1.0.0
> Last Updated: 2025-10-16

## 🎯 核心定位

**thyme-documentation-integrator** 使用兩個主要的 MCP 工具系統：

1. **Serena MCP** - 程式碼符號檢索和精準編輯
2. **Context7 MCP** - 技術文檔查詢和規範驗證

本文件提供詳細的工具使用指南、降級策略和最佳實踐。

---

## 🔧 Serena MCP 工具詳解

### 工具概覽

Serena MCP 提供類似 IDE 的語意程式碼檢索和編輯功能，專門用於：
- 查找 Markdown 文件中的特定章節和符號
- 在精確位置插入或替換內容
- 追蹤引用關係和依賴

### 工具清單

| 工具名稱 | 用途 | 使用頻率 |
|---------|------|---------|
| `find_symbol` | 查找特定符號位置 | 高 (70%) |
| `find_referencing_symbols` | 查找引用特定符號的位置 | 中 (20%) |
| `insert_after_symbol` | 在符號後插入內容 | 高 (60%) |
| `insert_before_symbol` | 在符號前插入內容 | 中 (30%) |
| `replace_symbol` | 替換符號內容 | 中 (40%) |
| `get_symbols_overview` | 取得檔案結構概覽 | 低 (10%) |

---

### 工具 1: mcp__serena__find_symbol

#### 功能描述
查找 Markdown 文件中的特定符號（章節標題、函式名稱、類別名稱等）。

#### 使用場景
- ✅ 需要在特定章節後插入內容
- ✅ 需要替換特定章節的內容
- ✅ 需要確認某個章節是否存在

#### 使用範例

**範例 1 - 查找 Markdown 章節標題**:
```json
{
  "symbol": "## 🎯 核心定位",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

**回應範例**:
```json
{
  "found": true,
  "location": {
    "file": "CLAUDE.md",
    "line": 123,
    "column": 0
  },
  "context": {
    "before": "## 🔧 專案類型配置\n\n本專案採用...",
    "match": "## 🎯 核心定位",
    "after": "\n\n**核心原則**: 測試先行..."
  }
}
```

**範例 2 - 查找方法論檔案中的章節**:
```json
{
  "symbol": "### 執行流程",
  "file_path": "/Users/mac-eric/project/book_overview_app/.claude/methodologies/agile-refactor-methodology.md"
}
```

#### 注意事項
- ⚠️ 符號名稱必須精確匹配（包含 emoji 和標點符號）
- ⚠️ 如果符號重複出現，會返回第一個匹配結果
- ⚠️ 建議使用完整的標題格式（包含 # 符號）

---

### 工具 2: mcp__serena__find_referencing_symbols

#### 功能描述
查找引用特定符號的所有位置，類似「查找所有引用」功能。

#### 使用場景
- ✅ 檢測引用路徑衝突（衝突檢測任務）
- ✅ 追蹤方法論被引用的位置
- ✅ 驗證整合後的引用關係

#### 使用範例

**範例 1 - 查找方法論被引用的位置**:
```json
{
  "symbol": "agile-refactor-methodology.md",
  "project_root": "/Users/mac-eric/project/book_overview_app"
}
```

**回應範例**:
```json
{
  "references": [
    {
      "file": "CLAUDE.md",
      "line": 456,
      "context": "[🚀 敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)"
    },
    {
      "file": ".claude/docs/thyme-documentation-integrator-usage-guide.md",
      "line": 89,
      "context": "完整的流程說明請參考 [敏捷重構方法論](../methodologies/agile-refactor-methodology.md)"
    }
  ],
  "total": 2
}
```

**範例 2 - 查找特定章節被引用的位置**:
```json
{
  "symbol": "## 🚀 敏捷重構開發流程",
  "project_root": "/Users/mac-eric/project/book_overview_app"
}
```

#### 注意事項
- ⚠️ 搜尋範圍為整個專案
- ⚠️ 可能返回大量結果，建議篩選
- ⚠️ 搜尋時間取決於專案大小

---

### 工具 3: mcp__serena__insert_after_symbol

#### 功能描述
在指定符號後插入內容，保持原有結構不變。

#### 使用場景
- ✅ 整合方法論到核心文件（引用策略）
- ✅ 新增章節到現有文件
- ✅ 補充內容到特定位置

#### 使用範例

**範例 1 - 在章節後插入方法論引用**:
```json
{
  "symbol": "## 📚 重要文件參考",
  "content": "\n\n### 核心規範文件\n\n- [🚀 敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md) - Agent 分工協作模式和三重文件原則\n",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

**範例 2 - 在清單後新增項目**:
```json
{
  "symbol": "### 方法論文件",
  "content": "\n- [📚 文件轉化方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/documentation-transformation-methodology.md) - 工作日誌轉化標準流程\n",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

#### 注意事項
- ⚠️ 插入內容前後建議加上空行（`\n\n`）
- ⚠️ 確認符號位置正確，避免插入到錯誤位置
- ⚠️ 插入後建議驗證檔案結構完整性

---

### 工具 4: mcp__serena__insert_before_symbol

#### 功能描述
在指定符號前插入內容，適合在章節開頭補充說明。

#### 使用場景
- ✅ 在章節開頭新增說明
- ✅ 在檔案開頭新增版本資訊
- ✅ 在特定位置插入警告或提示

#### 使用範例

**範例 1 - 在章節前新增說明**:
```json
{
  "symbol": "## 🚀 敏捷重構開發流程",
  "content": "> **注意**: 本章節說明主線程和執行代理人的協作流程。\n> 詳細方法論請參考 [敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)\n\n",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

#### 注意事項
- ⚠️ 插入內容後建議加上空行分隔
- ⚠️ 注意不要破壞 Markdown 結構

---

### 工具 5: mcp__serena__replace_symbol

#### 功能描述
替換特定符號的內容，適合內容更新或衝突解決。

#### 使用場景
- ✅ 解決內容衝突（衝突解決任務）
- ✅ 更新過時內容
- ✅ 重構文件結構

#### 使用範例

**範例 1 - 替換章節內容**:
```json
{
  "symbol": "### 主線程職責",
  "new_content": "### 主線程職責\n\n**主線程 (rosemary-project-manager) 職責**:\n- 📋 依照主版本工作日誌分派任務給相應的子代理人\n- 🎯 維持敏捷開發節奏和品質標準\n- 📊 監控整體進度和三重文件一致性\n- 🚨 處理升級請求和任務重新分派\n",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

**範例 2 - 修正引用路徑**:
```json
{
  "symbol": "[敏捷重構方法論](../methodologies/agile-refactor-methodology.md)",
  "new_content": "[敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

#### 注意事項
- ⚠️ 替換前建議備份原始內容
- ⚠️ 確認替換範圍正確（只替換目標符號）
- ⚠️ 替換後驗證檔案格式正確

---

### 工具 6: mcp__serena__get_symbols_overview

#### 功能描述
取得檔案的符號結構概覽，類似文件大綱視圖。

#### 使用場景
- ✅ 整合前分析核心文件結構
- ✅ 選擇最佳整合位置
- ✅ 驗證文件結構完整性

#### 使用範例

**範例 1 - 查看 CLAUDE.md 結構**:
```json
{
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}
```

**回應範例**:
```json
{
  "symbols": [
    {"type": "heading1", "name": "CLAUDE.md", "line": 1},
    {"type": "heading2", "name": "🔧 專案類型配置", "line": 5},
    {"type": "heading3", "name": "📋 當前專案配置", "line": 9},
    {"type": "heading2", "name": "🎯 核心定位", "line": 30},
    {"type": "heading2", "name": "🚀 敏捷重構開發流程", "line": 120}
  ]
}
```

#### 注意事項
- ⚠️ 只顯示標題層級符號
- ⚠️ 不包含內容詳情

---

## 🔄 Serena MCP 降級策略

### 降級觸發條件

- ❌ Serena MCP 服務無法連接
- ❌ 工具回應超時（> 30 秒）
- ❌ 工具回應錯誤或不準確

### 降級方案

#### 方案 1: 使用 Grep 工具替代查詢功能

**替代 find_symbol**:
```bash
# 查找章節標題
grep -n "## 🎯 核心定位" /Users/mac-eric/project/book_overview_app/CLAUDE.md

# 輸出範例：
# 123:## 🎯 核心定位
```

**替代 find_referencing_symbols**:
```bash
# 查找引用特定檔案的位置
grep -r "agile-refactor-methodology.md" /Users/mac-eric/project/book_overview_app/

# 輸出範例：
# CLAUDE.md:456:[🚀 敏捷重構方法論](...methodology.md)
```

#### 方案 2: 使用 Read + Edit 工具替代編輯功能

**替代 insert_after_symbol**:
```text
Step 1: 使用 Read 工具讀取檔案
Step 2: 使用 grep -n 定位符號行數
Step 3: 使用 Edit 工具在指定位置插入內容
```

**範例**:
```text
# Step 1: 讀取檔案
Read: CLAUDE.md

# Step 2: 定位行數
grep -n "## 📚 重要文件參考" CLAUDE.md
# 輸出: 456:## 📚 重要文件參考

# Step 3: 編輯檔案
Edit: 在 line 456 後插入方法論引用
```

**替代 replace_symbol**:
```text
Step 1: 使用 Read 工具讀取檔案
Step 2: 定位需要替換的內容
Step 3: 使用 Edit 工具精準替換
```

#### 方案 3: 手動執行（最後手段）

如果所有工具都無法使用：
1. 讀取原始檔案
2. 人工定位目標位置
3. 手動編輯內容
4. 驗證修改結果

---

## 🌐 Context7 MCP 工具詳解

### 工具概覽

Context7 MCP 提供最新技術文檔查詢功能，專門用於：
- 驗證方法論的技術規範正確性
- 查詢最新的 Flutter/Dart API 用法
- 確認第三方套件的最新版本

### 工具清單

| 工具名稱 | 用途 | 使用頻率 |
|---------|------|---------|
| `resolve-library-id` | 解析庫名稱為 Context7 ID | 中 (30%) |
| `get-library-docs` | 獲取庫的技術文檔 | 中 (40%) |

---

### 工具 1: mcp__context7__resolve-library-id

#### 功能描述
將常用的庫名稱（如 flutter, dart, dio）解析為 Context7 系統的標準 ID。

#### 使用場景
- ✅ 查詢技術文檔前的準備步驟
- ✅ 驗證庫名稱正確性
- ✅ 確認庫是否支援 Context7 查詢

#### 使用範例

**範例 1 - 解析 Flutter 庫**:
```json
{
  "libraryName": "flutter"
}
```

**回應範例**:
```json
{
  "libraryId": "/flutter/flutter",
  "displayName": "Flutter",
  "version": "stable",
  "description": "Flutter SDK for building cross-platform applications"
}
```

**範例 2 - 解析第三方套件**:
```json
{
  "libraryName": "dio"
}
```

**回應範例**:
```json
{
  "libraryId": "/dart/dio",
  "displayName": "Dio",
  "version": "5.4.0",
  "description": "A powerful HTTP client for Dart"
}
```

#### 注意事項
- ⚠️ 庫名稱必須是常見的公開庫
- ⚠️ 不支援私有庫或專案內部模組
- ⚠️ 如果庫不存在會返回錯誤

---

### 工具 2: mcp__context7__get-library-docs

#### 功能描述
獲取庫的最新技術文檔，可指定特定主題或 API。

#### 使用場景
- ✅ 驗證方法論的技術規範正確性
- ✅ 查詢最新的 API 用法
- ✅ 確認最佳實踐

#### 使用範例

**範例 1 - 查詢 Flutter Widget 文檔**:
```json
{
  "context7CompatibleLibraryID": "/flutter/flutter",
  "topic": "widget testing"
}
```

**回應範例**:
```json
{
  "docs": {
    "title": "Widget Testing in Flutter",
    "content": "Widget testing allows you to test individual widgets...",
    "examples": [
      {
        "title": "Basic Widget Test",
        "code": "testWidgets('MyWidget has a title', (tester) async { ... });"
      }
    ],
    "relatedTopics": ["integration testing", "unit testing"]
  }
}
```

**範例 2 - 查詢 Dart 語法文檔**:
```json
{
  "context7CompatibleLibraryID": "/dart/dart",
  "topic": "null safety"
}
```

**回應範例**:
```json
{
  "docs": {
    "title": "Sound Null Safety",
    "content": "Dart's null safety prevents null reference errors...",
    "examples": [
      {
        "title": "Non-nullable variables",
        "code": "String name; // Error: non-nullable variable must be initialized"
      }
    ]
  }
}
```

#### 注意事項
- ⚠️ 必須先使用 `resolve-library-id` 取得正確的 ID
- ⚠️ topic 必須是常見的技術主題
- ⚠️ 回應內容可能很長，需要篩選關鍵資訊

---

## 🎯 Context7 MCP 使用時機決策

### 何時使用 Context7 MCP

| 場景 | 是否使用 | 理由 |
|------|---------|------|
| 方法論涉及 Flutter/Dart 技術規範 | ✅ 是 | 需要驗證技術用法正確性 |
| 方法論涉及第三方套件用法 | ✅ 是 | 確認最新版本的 API 用法 |
| 工作日誌提到棄用語法 | ✅ 是 | 查詢最新的替代語法 |
| 方法論涉及 Widget 測試 | ✅ 是 | 驗證測試寫法符合最佳實踐 |
| 純流程規範（如敏捷重構） | ❌ 否 | 不涉及技術實作細節 |
| 專案特定規範（如 5W1H） | ❌ 否 | 專案內部規範，無需外部驗證 |
| 工作日誌轉化（無技術驗證需求） | ❌ 否 | 只需提取和格式化 |

### 使用流程

```text
Step 1: 判斷是否需要技術驗證
    ├─ 是 → 繼續
    └─ 否 → 跳過 Context7 MCP

Step 2: 使用 resolve-library-id 解析庫名稱
    ├─ 成功 → 繼續
    └─ 失敗 → 降級方案

Step 3: 使用 get-library-docs 查詢文檔
    ├─ 成功 → 提取關鍵資訊
    └─ 失敗 → 降級方案

Step 4: 整合技術驗證結果到方法論
```

---

## 📊 工具使用統計和最佳實踐

### 工具使用頻率（預估）

#### Serena MCP 工具使用分佈

```text
工作日誌轉化任務:
    ├─ find_symbol: 10%
    ├─ insert_after_symbol: 5%
    └─ 其他: 5%

方法論整合任務:
    ├─ find_symbol: 60%
    ├─ insert_after_symbol: 50%
    ├─ get_symbols_overview: 30%
    └─ find_referencing_symbols: 20%

衝突檢測解決任務:
    ├─ find_referencing_symbols: 80%
    ├─ find_symbol: 70%
    ├─ replace_symbol: 60%
    └─ 其他: 20%
```

#### Context7 MCP 工具使用分佈

```text
工作日誌轉化任務:
    ├─ resolve-library-id: 20%
    └─ get-library-docs: 30%

方法論整合任務:
    ├─ resolve-library-id: 5%
    └─ get-library-docs: 10%

衝突檢測解決任務:
    ├─ resolve-library-id: 0%
    └─ get-library-docs: 5%
```

### 效能優化技巧

#### 技巧 1: 批量查詢
```text
# ❌ 不佳實踐：逐個查詢符號
find_symbol("## 核心原則")
find_symbol("## 執行流程")
find_symbol("## 檢查清單")

# ✅ 最佳實踐：一次取得結構概覽
get_symbols_overview()
# 然後根據概覽選擇目標符號
```

#### 技巧 2: 快取結果
```text
# 第一次查詢
library_id = resolve-library-id("flutter")
# 快取結果，後續使用直接引用

# 後續查詢
get-library-docs(library_id, "widget testing")
get-library-docs(library_id, "state management")
```

#### 技巧 3: 增量編輯
```text
# ❌ 不佳實踐：替換整個章節
replace_symbol("## 核心規範", "[500 行的完整內容]")

# ✅ 最佳實踐：只編輯變更部分
insert_after_symbol("### 檢查清單", "[新增的檢查項目]")
```

---

## 🔧 疑難排解

### 問題 1: Serena MCP find_symbol 找不到符號

**可能原因**:
- 符號名稱不精確（缺少 emoji、標點符號）
- 符號在檔案中不存在
- 符號格式錯誤

**解決方案**:
```bash
# Step 1: 使用 grep 驗證符號是否存在
grep -n "核心定位" CLAUDE.md

# Step 2: 確認精確的符號格式（包含 emoji）
grep -n "🎯 核心定位" CLAUDE.md

# Step 3: 使用完整的標題格式
grep -n "## 🎯 核心定位" CLAUDE.md
```

---

### 問題 2: Context7 MCP 查詢超時

**可能原因**:
- 網路連線問題
- Context7 服務負載過高
- 查詢主題過於廣泛

**解決方案**:
```text
# 方案 1: 縮小查詢範圍
# ❌ 過於廣泛
topic: "flutter"

# ✅ 具體明確
topic: "flutter widget testing"

# 方案 2: 使用降級方案
# 手動查詢官方文檔
# Flutter: https://flutter.dev/docs
# Dart: https://dart.dev/guides
```

---

### 問題 3: 插入內容後文件結構混亂

**可能原因**:
- 插入位置選擇不當
- 插入內容缺少適當的空行分隔
- Markdown 格式錯誤

**解決方案**:
```json
// ❌ 不佳實踐
{
  "content": "### 新章節\n內容..."
}

// ✅ 最佳實踐
{
  "content": "\n\n### 新章節\n\n內容...\n"
}
```

---

## 📚 相關資源

### MCP 工具文檔
- [Serena MCP 官方文檔](https://github.com/serena-mcp/serena)
- [Context7 MCP 官方文檔](https://context7.ai/docs)

### 專案支援文件
- [Agent 使用指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-documentation-integrator-usage-guide.md)
- [疑難排解指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-troubleshooting-guide.md)

### Agent 配置
- [thyme-documentation-integrator Agent 配置]($CLAUDE_PROJECT_DIR/.claude/agents/thyme-documentation-integrator.md)

---

**最後更新**: 2025-10-16
**版本**: 1.0.0
**維護者**: thyme-documentation-integrator
**總行數**: 565
