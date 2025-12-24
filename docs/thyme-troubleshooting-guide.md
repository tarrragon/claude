# thyme-documentation-integrator 疑難排解指南

> 常見問題快速解決參考
> Version: 1.0.0
> Last Updated: 2025-10-16

## 🎯 核心定位

本文件提供 **thyme-documentation-integrator** 使用過程中常見問題的快速診斷和解決方案。

**適用對象**:
- 主線程 (rosemary-project-manager)
- thyme-documentation-integrator 代理人
- 其他需要文件整合支援的代理人

---

## 🚨 常見錯誤和解決方案

### 錯誤 1: Serena MCP 查詢結果不精確

#### 症狀
- `find_symbol` 找到多個匹配結果
- 插入位置不是預期的位置
- 替換操作影響到錯誤的內容

#### 可能原因
1. **符號名稱太短或太通用**
   - 範例：`"## 核心"` 可能匹配多個章節
2. **檔案中有重複的符號**
   - 範例：多個章節都使用 `### 範例`
3. **符號格式不完整**
   - 範例：缺少 emoji 或標點符號

#### 解決方案

**方案 1: 使用更具體的符號名稱**
```json
// ❌ 不精確的符號
{
  "symbol": "## 核心"
}

// ✅ 精確的符號
{
  "symbol": "## 🎯 核心定位（thyme-documentation-integrator）"
}
```

**方案 2: 增加上下文過濾**
```json
// 使用 get_symbols_overview 先取得結構
{
  "file_path": "CLAUDE.md"
}

// 根據結構選擇唯一的符號
// 範例：line 123 的 "## 🎯 核心定位"
```

**方案 3: 手動確認位置後使用 Edit 工具**
```bash
# Step 1: 使用 grep 確認精確位置
grep -n "## 🎯 核心定位" CLAUDE.md

# 輸出：123:## 🎯 核心定位

# Step 2: 使用 Edit 工具在 line 123 後插入
```

#### 預防措施
- ✅ 使用完整的標題格式（包含 emoji 和標點符號）
- ✅ 優先使用唯一性高的符號（如包含專案特定名稱）
- ✅ 使用 `get_symbols_overview` 先確認檔案結構

---

### 錯誤 2: 引用路徑無法點擊跳轉

#### 症狀
- Markdown 連結無法跳轉
- 路徑顯示為紅色（找不到檔案）
- IDE 或編輯器提示「檔案不存在」

#### 可能原因
1. **相對路徑計算錯誤**
   - 範例：`../methodologies/file.md` 從不同位置讀取會有不同結果
2. **檔案實際路徑不存在**
   - 範例：檔案已移動或刪除
3. **路徑格式不符合專案規範**
   - 範例：應該使用 `$CLAUDE_PROJECT_DIR/` 格式

#### 解決方案

**方案 1: 統一使用絕對路徑格式**
```markdown
<!-- ❌ 不推薦：相對路徑 -->
[方法論](../methodologies/agile-refactor-methodology.md)

<!-- ✅ 推薦：絕對路徑格式 -->
[方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)
```

**方案 2: 驗證檔案是否存在**
```bash
# 使用 ls 驗證檔案存在
ls -la /Users/mac-eric/project/book_overview_app/.claude/methodologies/agile-refactor-methodology.md

# 如果不存在，檢查是否在其他位置
find /Users/mac-eric/project/book_overview_app -name "agile-refactor-methodology.md"
```

**方案 3: 使用 Serena MCP 確認路徑**
```json
// 使用 find_symbol 確認檔案可讀取
{
  "symbol": "# 敏捷重構方法論",
  "file_path": "/Users/mac-eric/project/book_overview_app/.claude/methodologies/agile-refactor-methodology.md"
}

// 如果成功，表示路徑正確
```

#### 預防措施
- ✅ 統一使用 `$CLAUDE_PROJECT_DIR/` 格式
- ✅ 整合任務前驗證檔案存在
- ✅ 使用 Serena MCP 測試路徑可讀性

---

### 錯誤 3: 衝突檢測誤報

#### 症狀
- 報告不存在的衝突
- 正常的變體被誤判為衝突
- 不同層級的描述被認為衝突

#### 可能原因
1. **檢測邏輯過於嚴格**
   - 範例：要求完全相同才算不衝突
2. **未區分「變體」和「衝突」**
   - 範例：CLAUDE.md 的摘要 vs 方法論的詳細說明
3. **語意相同但表達不同**
   - 範例：「主線程不執行程式碼」vs「主線程禁止修改程式碼」

#### 解決方案

**方案 1: 人工複查衝突報告**
```markdown
## 衝突複查清單

對每個報告的衝突，檢查：
- [ ] 兩個版本是否真的矛盾？
- [ ] 是否只是詳細程度不同？
- [ ] 是否只是表達方式不同？
- [ ] 是否可以共存（摘要 + 詳細）？
```

**方案 2: 區分「正常變體」vs「真實衝突」**

| 類型 | 定義 | 範例 | 處理方式 |
|------|------|------|---------|
| **正常變體** | 不同層級的描述 | CLAUDE.md 摘要 vs 方法論詳細 | 保持兩者，建立引用 |
| **真實衝突** | 相互矛盾的描述 | 「必須使用 A」vs「禁止使用 A」 | 確認保留版本，統一修改 |

**方案 3: 調整檢測閾值**
```markdown
## 衝突檢測標準調整

**嚴格模式**（當前）:
- 任何差異都報告為衝突

**推薦模式**:
- 只報告相互矛盾的內容
- 忽略詳細程度差異
- 忽略表達方式差異
```

#### 預防措施
- ✅ 人工複查所有衝突報告
- ✅ 明確區分變體和衝突
- ✅ 提供衝突嚴重程度評級（高/中/低）

---

### 錯誤 4: 方法論轉化內容不完整

#### 症狀
- 轉化後的方法論缺少關鍵章節
- 流程說明不完整
- 範例或檢查清單遺漏

#### 可能原因
1. **工作日誌章節識別錯誤**
   - 範例：只提取了主章節，忽略了子章節
2. **提取邏輯未覆蓋所有相關章節**
   - 範例：相關內容分散在多個章節
3. **重點提取說明不明確**
   - 範例：分派時未明確指出需要提取哪些內容

#### 解決方案

**方案 1: 重新分派轉化任務（擴大範圍）**
```markdown
請重新將 `docs/work-logs/vX.Y.Z-main.md` 轉化為方法論。

**修正內容**:
- **原始範圍**: Phase 3a 策略規劃 (line 300-450)
- **擴大範圍**: Phase 3a 策略規劃 + Phase 3b 實作細節 (line 300-600)
- **特別注意**: 包含所有範例、檢查清單、決策記錄

**補充重點提取**:
- 完整的執行流程（包含每個步驟的詳細說明）
- 所有實際範例（至少 3 個）
- 完整的檢查清單（包含驗收標準）
```

**方案 2: 補充更新現有方法論**
```markdown
請補充更新方法論 `.claude/methodologies/[名稱].md`。

**補充內容來源**:
- 檔案：`docs/work-logs/vX.Y.Z-main.md`
- 章節：Phase 4 重構總結 (line 600-700)

**補充位置**:
- 章節：## 最佳實踐

**補充內容**:
- 重構經驗總結
- 避免的陷阱清單
- 效能優化技巧
```

**方案 3: 手動補充遺漏內容**
```markdown
檢查工作日誌完整性：
- [ ] 所有主要章節都已提取
- [ ] 所有子章節都已包含
- [ ] 所有範例都已轉化
- [ ] 所有檢查清單都已整理
- [ ] 所有決策記錄都已記錄
```

#### 預防措施
- ✅ 分派時明確指定章節範圍（使用行數）
- ✅ 詳細說明重點提取內容（包含範例、檢查清單）
- ✅ 提供關鍵字清單幫助定位內容
- ✅ 驗收時使用檢查清單逐項確認

---

### 錯誤 5: 整合後文件結構混亂

#### 症狀
- 章節順序不合理
- 內容重複出現
- 文件結構層級錯亂

#### 可能原因
1. **整合位置選擇不當**
   - 範例：應該整合到 A 章節，卻整合到 B 章節
2. **未檢測到重複內容**
   - 範例：相同內容在多個位置出現
3. **整合策略選擇錯誤**
   - 範例：應該使用引用，卻使用完整複製

#### 解決方案

**方案 1: 重新整合到正確位置**
```markdown
請重新整合方法論到核心文件。

**步驟**:
1. **移除錯誤的整合內容**:
   - 檔案：CLAUDE.md
   - 章節：## 🔧 開發工具 (line 500-550)
   - 原因：此位置不適合整合方法論引用

2. **重新整合到正確位置**:
   - 檔案：CLAUDE.md
   - 新位置：## 📚 重要文件參考 → 核心規範文件
   - 整合策略：引用

3. **驗證結構**:
   - 使用 get_symbols_overview 確認文件結構
   - 確認無重複內容
```

**方案 2: 重組核心文件結構**
```markdown
請重組 CLAUDE.md 的 [章節名稱]。

**重組目標**:
- 合併重複章節：
  - 「開發規範」章節出現在 line 200 和 line 600
  - 合併為單一章節並建立內部引用

- 調整章節順序：
  - 將「核心原則」移到文件前段
  - 將「參考文件」移到文件末段

- 建立清晰的結構層級：
  - Level 1: 核心概念
  - Level 2: 開發流程
  - Level 3: 參考資源

**重組原則**:
- 保持邏輯一致性
- 避免內容重複
- 引用優於複製
```

**方案 3: 執行去重處理**
```markdown
請檢查並移除 CLAUDE.md 的重複內容。

**檢查範圍**:
- 檔案：CLAUDE.md
- 重複類型：
  - 相同章節在多個位置
  - 相同方法論引用出現多次
  - 相同規範描述重複

**處理原則**:
- 保留最完整的版本
- 移除其他重複版本
- 建立內部引用（如需要）
```

#### 預防措施
- ✅ 整合前使用 Serena MCP 查詢現有章節結構
- ✅ 選擇最合適的整合位置（符合邏輯層級）
- ✅ 優先使用引用策略保持核心文件簡潔
- ✅ 驗收時檢查文件整體結構和完整性

---

### 錯誤 6: Context7 MCP 查詢超時或失敗

#### 症狀
- 查詢無回應或超時（> 30 秒）
- 返回錯誤訊息「Service unavailable」
- 查詢結果不相關或空白

#### 可能原因
1. **網路連線問題**
   - Context7 服務無法訪問
2. **查詢主題過於廣泛**
   - 範例：`topic: "flutter"` 太廣泛
3. **庫 ID 解析失敗**
   - 未使用 `resolve-library-id` 先解析

#### 解決方案

**方案 1: 縮小查詢範圍**
```json
// ❌ 過於廣泛
{
  "context7CompatibleLibraryID": "/flutter/flutter",
  "topic": "flutter"
}

// ✅ 具體明確
{
  "context7CompatibleLibraryID": "/flutter/flutter",
  "topic": "flutter widget testing best practices"
}
```

**方案 2: 使用降級方案（手動查詢官方文檔）**
```markdown
## 手動查詢流程

1. **Flutter 官方文檔**:
   - URL: https://flutter.dev/docs
   - 搜尋：widget testing
   - 複製相關章節連結

2. **Dart 官方文檔**:
   - URL: https://dart.dev/guides
   - 搜尋：null safety
   - 複製最新語法說明

3. **整合到方法論**:
   - 在方法論中新增「參考資源」章節
   - 列出官方文檔連結
```

**方案 3: 跳過技術驗證（如果非必要）**
```markdown
## 決策流程

**問題**: Context7 MCP 無法使用

**決策**:
- 方法論涉及關鍵技術規範？
  - 是 → 使用手動查詢（方案 2）
  - 否 → 跳過技術驗證，繼續轉化

**範例**:
- 「Widget 測試方法論」→ 需要技術驗證 → 手動查詢
- 「敏捷重構流程」→ 不需要技術驗證 → 跳過
```

#### 預防措施
- ✅ 使用 `resolve-library-id` 先驗證庫 ID
- ✅ 查詢主題具體明確
- ✅ 設定超時後的降級方案
- ✅ 手動查詢作為備用方案

---

## 📋 除錯檢查清單

### 轉化任務除錯清單

```markdown
## 轉化任務問題診斷

### 基本檢查
- [ ] 工作日誌檔案路徑正確
- [ ] 檔案可讀取（使用 Read 工具測試）
- [ ] 目標章節明確（章節名稱或行數範圍）
- [ ] 輸出路徑可寫入（.claude/methodologies/）

### 章節識別檢查
- [ ] 章節名稱精確匹配
- [ ] 章節範圍完整（包含所有子章節）
- [ ] 相關內容未遺漏（檢查前後章節）

### 轉化邏輯檢查
- [ ] 重點提取說明明確
- [ ] 關鍵字清單完整
- [ ] 範例數量足夠（至少 2 個）
- [ ] 檢查清單完整

### 輸出品質檢查
- [ ] 方法論結構完整
- [ ] Markdown 格式正確
- [ ] 內容可獨立理解
- [ ] 無遺漏或錯誤
```

---

### 整合任務除錯清單

```markdown
## 整合任務問題診斷

### 基本檢查
- [ ] 方法論檔案存在且可讀取
- [ ] 核心文件可編輯
- [ ] 整合策略選擇正確（引用/摘要/完整）
- [ ] 整合位置明確

### 路徑格式檢查
- [ ] 使用 `$CLAUDE_PROJECT_DIR/` 格式
- [ ] 路徑正確無誤
- [ ] 相對路徑已全部替換

### 整合內容檢查
- [ ] 引用策略：連結正確可跳轉
- [ ] 摘要策略：摘要精確 + 連結
- [ ] 完整策略：內容完整複製
- [ ] 無內容重複

### 文件結構檢查
- [ ] 整合位置符合邏輯
- [ ] 章節順序合理
- [ ] 層級結構正確
- [ ] 無混亂或重複
```

---

### 衝突解決任務除錯清單

```markdown
## 衝突解決任務問題診斷

### 基本檢查
- [ ] 所有目標文件都可讀取
- [ ] 衝突類型正確識別
- [ ] 檢測範圍明確
- [ ] 優先級合理

### 衝突報告檢查
- [ ] 所有衝突都已列出
- [ ] 每個衝突都有具體位置（檔案 + 行數）
- [ ] 版本差異對比清晰
- [ ] 差異分析合理

### 解決方案檢查
- [ ] 提供多個可選方案
- [ ] 每個方案說明優缺點
- [ ] 有推薦方案和理由
- [ ] 方案可執行

### 確認流程檢查
- [ ] 已等待主線程確認
- [ ] 未擅自修改文件
- [ ] 確認格式清晰

### 執行後驗證
- [ ] 衝突已正確解決
- [ ] 無新衝突產生
- [ ] 檔案格式正確
- [ ] 引用路徑正確
```

---

## 🔧 進階除錯技巧

### 技巧 1: 使用 Hook 日誌診斷問題

```bash
# 查看最近的 Hook 執行記錄
ls -lt /Users/mac-eric/project/book_overview_app/.claude/hook-logs/ | head -5

# 查看特定 Hook 的詳細日誌
cat /Users/mac-eric/project/book_overview_app/.claude/hook-logs/document-sync-hook-20251016-153000.log

# 搜尋錯誤訊息
grep -i "error\|failed\|exception" /Users/mac-eric/project/book_overview_app/.claude/hook-logs/*.log
```

**常見日誌錯誤**:

| 錯誤訊息 | 可能原因 | 解決方案 |
|---------|---------|---------|
| `File not found` | 檔案路徑錯誤 | 驗證檔案是否存在 |
| `Permission denied` | 檔案權限問題 | 檢查檔案權限 |
| `Invalid JSON` | JSON 格式錯誤 | 驗證 JSON 語法 |
| `Symbol not found` | 符號名稱不匹配 | 使用 grep 確認精確名稱 |

---

### 技巧 2: 使用 Serena MCP 驗證

```bash
# 驗證符號是否存在
mcp__serena__find_symbol '{
  "symbol": "## 🎯 核心定位",
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}'

# 查看符號引用
mcp__serena__find_referencing_symbols '{
  "symbol": "agile-refactor-methodology.md",
  "project_root": "/Users/mac-eric/project/book_overview_app"
}'

# 取得檔案結構概覽
mcp__serena__get_symbols_overview '{
  "file_path": "/Users/mac-eric/project/book_overview_app/CLAUDE.md"
}'
```

**驗證流程**:
```text
Step 1: 使用 find_symbol 確認符號存在
    ├─ 成功 → 繼續
    └─ 失敗 → 使用 grep 手動查找

Step 2: 使用 get_symbols_overview 查看結構
    ├─ 符號在預期位置 → 繼續
    └─ 符號位置不對 → 調整整合位置

Step 3: 使用 find_referencing_symbols 檢查引用
    ├─ 無錯誤引用 → 通過驗證
    └─ 有錯誤引用 → 修正引用路徑
```

---

### 技巧 3: 使用 Diff 工具比較版本

```bash
# 比較兩個版本的差異
diff -u CLAUDE.md.backup CLAUDE.md

# 只顯示新增的行
diff CLAUDE.md.backup CLAUDE.md | grep "^>"

# 只顯示刪除的行
diff CLAUDE.md.backup CLAUDE.md | grep "^<"

# 使用 git diff 比較
git diff CLAUDE.md
```

**Diff 分析**:
```text
# 範例輸出
--- CLAUDE.md.backup
+++ CLAUDE.md
@@ -456,0 +457,3 @@
+### 核心規範文件
+
+- [🚀 敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)

# 解讀：
# line 457 新增了 3 行（方法論引用）
```

---

### 技巧 4: 使用 Markdown Linter 檢查格式

```bash
# 使用 markdownlint 檢查格式
# （需要先安裝：npm install -g markdownlint-cli）
markdownlint CLAUDE.md

# 常見格式錯誤
# MD001: Heading levels should only increment by one level at a time
# MD009: Trailing spaces
# MD012: Multiple consecutive blank lines
# MD022: Headings should be surrounded by blank lines
```

**修正流程**:
```text
Step 1: 執行 markdownlint 檢查
Step 2: 記錄所有錯誤
Step 3: 逐項修正
Step 4: 重新執行驗證
```

---

## 📊 除錯效能優化

### 常見問題處理時間統計

| 問題類型 | 診斷時間 | 修復時間 | 總時間 |
|---------|---------|---------|--------|
| Serena MCP 查詢不精確 | 2-3 分鐘 | 3-5 分鐘 | 5-8 分鐘 |
| 引用路徑無法跳轉 | 1-2 分鐘 | 2-3 分鐘 | 3-5 分鐘 |
| 衝突檢測誤報 | 5-10 分鐘 | 10-15 分鐘 | 15-25 分鐘 |
| 方法論轉化不完整 | 3-5 分鐘 | 10-20 分鐘 | 13-25 分鐘 |
| 文件結構混亂 | 5-10 分鐘 | 15-30 分鐘 | 20-40 分鐘 |

### 效能優化建議

1. **預防優於修復**
   - 分派時提供完整資訊
   - 使用檢查清單驗證
   - 優先使用 Serena MCP 工具

2. **快速診斷**
   - 使用 Hook 日誌快速定位問題
   - 使用 Serena MCP 驗證工具
   - 建立常見問題快速索引

3. **批量修復**
   - 相似問題一次處理
   - 使用腳本自動化重複任務
   - 建立修復模板

---

## 📚 相關資源

### 支援文件
- [Agent 使用指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-documentation-integrator-usage-guide.md)
- [MCP 工具整合指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-mcp-integration-guide.md)

### Agent 配置
- [thyme-documentation-integrator Agent 配置]($CLAUDE_PROJECT_DIR/.claude/agents/thyme-documentation-integrator.md)

### 工作日誌
- [v0.12.J 文件整合代理人開發]($CLAUDE_PROJECT_DIR/docs/work-logs/v0.12.J.0-documentation-integrator-main.md)

### 方法論參考
- [敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md)

---

## 🆘 求助流程

### 何時尋求主線程協助

1. **問題無法自行解決**（嘗試 3 次以上）
2. **需要確認保留版本**（衝突解決）
3. **需要重新規劃任務**（任務範圍過大）
4. **發現設計缺陷**（需要架構調整）

### 求助格式

```markdown
## 求助請求

**問題類型**: [查詢/整合/衝突解決]
**嘗試次數**: 3 次
**失敗原因**:
1. 嘗試方案 A：[失敗原因]
2. 嘗試方案 B：[失敗原因]
3. 嘗試方案 C：[失敗原因]

**根本原因分析**:
- 技術限制：[具體說明]
- 任務範圍：[是否過大]
- 資訊不足：[缺少哪些資訊]

**建議行動**:
- 任務拆分建議：[如何拆分]
- 需要協助：[需要哪些協助]

**等待確認**: [請主線程確認下一步行動]
```

---

**最後更新**: 2025-10-16
**版本**: 1.0.0
**維護者**: thyme-documentation-integrator
**總行數**: 686
