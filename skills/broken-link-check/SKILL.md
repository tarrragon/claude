---
name: broken-link-check
description: "broken-link 偵測工具。掃描 .claude/ 目錄所有 Markdown 文件中的路徑引用，偵測失效連結。Use for: (1) 一次性掃描所有 broken links, (2) 搭配 /loop 定期監控, (3) 修改規則/方法論/代理人文件後驗證路徑完整性。Use when: user runs /broken-link-check, 或搭配 /loop 定期執行, 或發現 broken link 錯誤後。"
---

# broken-link-check

掃描 `.claude/` 目錄下所有 Markdown 文件中的路徑引用，偵測失效連結。

## 背景

`.claude/` 目錄中的規則、方法論、代理人定義文件大量交叉引用彼此。
當文件被重命名或移動時，舊的引用路徑會變成 broken link（如 W14-002.1 發現的 4 個案例）。

此工具用於定期偵測此類問題，防止 broken links 長期未被發現。

---

## 執行方式

### 立即掃描

```
/broken-link-check
```

### 搭配 /loop 定期掃描

```
/loop 1h /broken-link-check
```

---

## 執行流程

執行 `/broken-link-check` 時，依序執行以下步驟：

### Step 1：收集所有 .md 文件

使用 Glob 工具找出 `.claude/` 目錄下所有 `.md` 文件：
- 掃描範圍：`.claude/**/*.md`
- 排除：`.claude/hook-logs/`（日誌目錄，非文件）

### Step 2：提取路徑引用

對每個文件，使用 Grep 找出所有路徑引用行。
偵測的路徑格式：

| 格式 | 範例 | 說明 |
|------|------|------|
| `@.claude/path/file.md` | `@.claude/rules/core/decision-tree.md` | @ 前綴的絕對引用 |
| `.claude/path/file.md` | `.claude/agents/incident-responder.md` | 裸路徑絕對引用 |
| `../path/file.md` | `../agents/lavender-interface-designer.md` | 相對路徑引用 |
| `./path/file.md` | `./references/detail.md` | 當前目錄相對引用 |

**排除以下不需要檢查的引用：**
- `http://` 或 `https://` 開頭（外部 URL）
- `#section` 開頭（錨點連結）
- 程式碼區塊內的範例路徑（以 ` ``` ` 包圍的區塊）
- 僅含目錄名（不含副檔名）的引用

### Step 3：解析實際路徑

將引用轉換為實際文件系統路徑：
- `@.claude/path/file.md` → 從專案根目錄的 `.claude/path/file.md`
- `.claude/path/file.md` → 從專案根目錄的 `.claude/path/file.md`
- `../path/file.md` → 相對於引用文件所在目錄向上一層解析
- `./path/file.md` → 相對於引用文件所在目錄解析

### Step 4：驗證路徑存在

對每個解析後的路徑使用 Glob 或 Read 工具確認是否存在。
- 路徑存在 → 正常
- 路徑不存在 → 記錄為 broken link（含文件名和行號）

### Step 5：輸出報告

```
broken-link-check 掃描結果
掃描範圍：.claude/ (N 個 .md 文件)
掃描時間：YYYY-MM-DD HH:MM

[有問題] N 個 broken links：
  .claude/rules/core/decision-tree.md:123
    → .claude/agents/system-analyst.md（不存在）
    → 建議：可能已重命名，搜尋相似文件

  .claude/pm-rules/tdd-flow.md:45
    → .claude/project-templates/FLUTTER.md（不存在）
    → 建議：確認正確路徑

[正常] 所有其他 N 個引用路徑均存在
```

**無問題時：**

```
broken-link-check 掃描結果
掃描範圍：.claude/ (N 個 .md 文件)
掃描時間：YYYY-MM-DD HH:MM

[正常] 所有 N 個引用路徑均存在，無 broken links
```

---

## 修復建議

發現 broken link 時，建議的修復步驟：

1. 搜尋相似文件名（文件可能被重命名）
2. 確認文件是否已移至其他目錄
3. 更新引用路徑（使用 Edit 工具）
4. 如文件確實已刪除，移除引用或更新為替代文件

---

## 注意事項

- 此工具只掃描 `.claude/` 目錄（不掃描 `docs/`、`ui/`、`server/` 等）
- 只偵測文件引用，不偵測 URL 有效性
- 相對路徑解析基於文件所在目錄，需正確計算層級
- 大型 `.claude/` 目錄（100+ 文件）掃描可能需要數分鐘

---

**Version**: 1.0.0
**Last Updated**: 2026-03-08
**Source**: 0.1.0-W14-003（W14-002.1 broken links 後置預防機制）
