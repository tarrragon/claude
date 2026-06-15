---
name: broken-link-check
description: "broken-link 偵測工具。掃描 .claude/ 目錄所有 Markdown 文件中的路徑引用，偵測失效連結。Use for: (1) 一次性掃描所有 broken links, (2) 搭配 /loop 定期監控, (3) 修改規則/方法論/代理人文件後驗證路徑完整性。Use when: user runs /broken-link-check, 或搭配 /loop 定期執行, 或發現 broken link 錯誤後。"
---

# broken-link-check

掃描 `.claude/` 目錄下所有 Markdown 文件中的路徑引用，偵測失效連結。

## 背景

`.claude/` 目錄中的規則、方法論、代理人定義文件大量交叉引用彼此。
當文件被重命名或移動時，舊的引用路徑會變成 broken link。

此工具用於定期偵測此類問題，防止 broken links 長期未被發現。

---

## 權威 gate：scan_links.py CLI

broken-link 計數的唯一權威來源是 `scan_links.py` 確定性 CLI，不是 LLM 手動判讀。LLM 手動 Glob/Grep 流程對同一 repo 會產出浮動計數（W8-019 實測 258 vs 155），無法作為跨框架完成 gate。CLI 以固定排除規則與穩定排序保證同一 repo 連續執行 byte-for-byte 一致，因此作為權威 gate。

### 立即掃描（權威）

```
python3 .claude/skills/broken-link-check/scan_links.py .
```

- 位置參數為 repo root（預設 cwd），掃描 `<root>/.claude/**/*.md`
- exit code：`0`=零 broken（gate pass）/ `1`=偵測到 broken（gate fail）/ `2`=執行錯誤（root 不存在、I/O 失敗）
- gate 用途可直接接 `&&` 或 CI：broken>0 即非零 exit，與工具自身錯誤（exit 2）區隔

### 輸出格式

| flag | 用途 |
|------|------|
| `--format text`（預設） | 人類可讀：摘要 + 分組 broken 清單 |
| `--format json` | 穩定 schema，供下游清理工具消費（含 `source_file/line/raw_ref/resolved_path/category` + `categories` 分類計數） |

### 四排除旋鈕（預設皆排除，flag 顯式覆寫納入）

| 旋鈕 | 預設 | 覆寫 flag |
|------|------|-----------|
| 程式碼區塊內引用 | 排除 | `--include-code-block` |
| migration-backups / hook-logs 下路徑 | 排除（歸 `excluded_backup`） | `--include-migration-backups` |
| placeholder 範例路徑（如 `path/file.md`） | 排除（歸 `placeholder`） | `--include-placeholder` |
| documented-error 豁免 marker 行 | 排除（歸 `excluded_documented`） | `--include-documented` |

覆寫旋鈕用於 triage/debug，gate 預設一律不加 flag。

### documented-error 豁免 marker（W8-049）

error-pattern 案例表會刻意記錄不存在的路徑——例如 confabulation 案例的「錯誤參照」欄、或已遷移/刪除檔案的歷史軌跡。這些路徑的文獻價值正在於保留原貌，redirect/刪除會毀損案例資料。在含該引用的行尾（或同 table cell 內）加上行內 marker，scanner 即將該行所有引用歸 `excluded_documented` 不計 broken：

```
<!-- broken-link-exempt: documented-error -->
```

- 顯式 opt-in（per-occurrence），無 marker 的真實 broken 不受影響。
- marker 僅作用於所在行（PC-146 放置精確性），不會誤豁免他行。
- 僅取消「不存在」引用的 broken 計列；該行若有存在的引用仍歸 `ok`，不遮蔽存在事實。
- `--include-documented` 可在 triage 時顯式納入計數。

### 搭配 /loop 定期掃描

```
/loop 1h python3 .claude/skills/broken-link-check/scan_links.py .
```

---

## 偵測規則（CLI 內建，供理解輸出用）

CLI 已內建以下規則，本節僅供閱讀輸出時對照，非需手動執行的步驟。

偵測的路徑格式：

| 格式 | 範例 | 解析基準 |
|------|------|------|
| `@.claude/path/file.md` | `@.claude/pm-rules/decision-tree.md` | repo root |
| `.claude/path/file.md` | `.claude/agents/incident-responder.md` | repo root |
| `../path/file.md` | `../agents/lavender-interface-designer.md` | 引用文件所在目錄 |
| `./path/file.md` | `./references/detail.md` | 引用文件所在目錄 |

排除：`http(s)://`（外部 URL）、`#section`（錨點）、預設四旋鈕涵蓋的程式碼區塊 / 備份目錄 / placeholder 範例 / documented-error marker 行。

---

## Fallback：手動流程（非權威，僅 CLI 不可用時參考）

以下手動 Glob/Grep 流程為 `scan_links.py` 無法執行時（如環境缺 Python）的降級參考，計數可能浮動，不可作為完成 gate。權威結果一律以 CLI 輸出為準。

1. Glob 找出 `.claude/**/*.md`，排除 `.claude/hook-logs/`
2. Grep 找出上述四種前綴的路徑引用，排除 URL / 錨點 / 程式碼區塊
3. 依解析基準轉為實際路徑
4. Read/Glob 確認路徑存在，不存在者記為 broken link（含文件名與行號）
5. 輸出 broken 清單

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

**Version**: 2.1.0
**Last Updated**: 2026-06-15
**Source**: broken links 後置預防機制；1.0.0-W8-030.1 改路由至 scan_links.py 確定性 CLI 作權威 gate，手動流程降級為非權威 fallback；1.0.0-W8-049 新增 documented-error 豁免 marker（excluded_documented 類別 + `--include-documented` 旋鈕），case-study 內刻意記錄的不存在路徑顯式 opt-in 豁免
