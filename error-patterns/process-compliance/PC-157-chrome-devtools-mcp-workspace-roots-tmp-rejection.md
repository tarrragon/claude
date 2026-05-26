---
id: PC-157
title: chrome-devtools-mcp install_extension 拒絕非 workspace roots 內路徑（含 /tmp）
category: process-compliance
severity: low
source_case: 0.19.0-W1-002.2
created: 2026-05-25
---

# PC-157: chrome-devtools-mcp install_extension 拒絕非 workspace roots 內路徑（含 /tmp）

## 症狀

執行 `mcp__chrome-devtools__install_extension` 載入解壓後 unpacked extension 時，傳入 `/tmp/<dir>` 等慣常臨時目錄被拒絕，錯誤訊息：

```
Error: Access denied: path /tmp/readmoo-ext-w1-002-2 is not within any of the
workspace roots [{"uri":"file:///Users/<user>/project/<proj>"},{"uri":"file:///var/folders/.../T","name":"temp"}].
```

可觀察訊號：

- 解壓 ZIP 到 `/tmp/<dir>` 後嘗試安裝，被拒
- 錯誤訊息明示 workspace roots 清單，含「專案目錄」與「temp」兩個 URI
- macOS 的 `temp` 對應 `/var/folders/.../T`（系統 temp），非 Unix 通用 `/tmp`

**Why**：chrome-devtools-mcp server 啟動時依 host（如 Claude Code）提供的 workspace roots 建立路徑白名單。Claude Code macOS 預設 workspace roots 含「專案根目錄」與「`$TMPDIR`（macOS 系統 temp）」，但**不含** `/tmp`（Unix 慣用但與 macOS sandbox 政策不一致）。

**Consequence**：PM 與代理人若沿用 Linux/Docker 慣例先解壓到 `/tmp/<dir>` 再 install_extension 會撞牆，第一次嘗試必失敗；若未仔細讀錯誤訊息上的 workspace roots 清單，可能誤以為 mcp 損壞或權限問題，浪費 tool call 與認知資源。

**Action**：

| 場景 | 正確做法 |
|------|---------|
| 解壓 extension ZIP 給 mcp install | 用 `$TMPDIR/<dir>`（macOS = `/var/folders/.../T/`），或專案內路徑（如 `dist/extracted/`） |
| 取得正確 TMPDIR 路徑 | Bash `echo "$TMPDIR"` 取得絕對路徑；mkdir 與後續操作用 absolute path（zsh 的 globbing 對相對路徑變數展開有時失敗） |
| 撞到 access denied 錯誤 | 第一步讀錯誤訊息的 `workspace roots [...]` 清單，從中挑路徑，不要重試 /tmp 變體 |

## 觸發條件

以下三條件同時成立：

1. **使用 `mcp__chrome-devtools__install_extension`（或其他需要本地路徑參數的 mcp 工具）**
2. **傳入路徑不在 host 提供的 workspace roots 內**
3. **常見誤入：`/tmp/...`、`/var/tmp/...`、`~/.cache/...` 等 mcp host 未授權的路徑**

## 根因

### L1（環境差異未文件化）

`chrome-extension-mcp-debug` SKILL 未明示 install_extension 的路徑限制；範例多寫「解壓到任意目錄」未強調必須在 workspace roots 內。新使用者沿用 Linux/Docker 慣例先嘗試 `/tmp`。

### L2（macOS sandbox 政策）

macOS 的 `$TMPDIR` 是 per-user sandboxed temp（`/var/folders/g?/.../T/`），與 `/tmp`（系統共用）不同。Claude Code workspace roots 預設加入 `$TMPDIR` 而非 `/tmp`，符合 sandbox 慣例但對使用者不直觀。

## 防護機制

| 層級 | 防護動作 |
|------|---------|
| 文件層 | `.claude/skills/chrome-extension-mcp-debug/SKILL.md` 加入「路徑限制」章節（待補） |
| 預設層 | mcp host 錯誤訊息已含 workspace roots 清單（足夠資訊，但需 PM 主動讀） |
| 工具選擇 | 解壓 extension 預設使用 `$TMPDIR/<dir>` 或專案內 `dist/extracted/`，避開 `/tmp` |

## 案例

### Case 1: 2026-05-25 W1-002.2

PM 執行 W1-002.2 實機驗證，第一次嘗試：

```bash
unzip -q dist/readmoo-book-extractor-v0.18.0.zip -d /tmp/readmoo-ext-w1-002-2/
mcp__chrome-devtools__install_extension(path: /tmp/readmoo-ext-w1-002-2)
→ Error: Access denied: path /tmp/... is not within any of the workspace roots
```

修正：改用 `$TMPDIR`（解析為 `/var/folders/g3/.../T/`），install_extension 成功，extension ID `phhicihcocdiopiaimejpapbkdammnjn`。

## 相關文件

- `.claude/skills/chrome-extension-mcp-debug/SKILL.md`
- chrome-devtools-mcp 工具定義（list_pages, install_extension, evaluate_script）
- macOS sandbox / `$TMPDIR` 文件：`man tmpdir`

---

**Last Updated**: 2026-05-25
