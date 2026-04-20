# PC-079: Bash CLI 參數含 backtick 被解析為 command substitution

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-079 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-17（W13-007 Context Bundle append-log 時 shell 誤執行 backtick 內路徑） |
| 姊妹模式 | `.claude/rules/core/bash-tool-usage-rules.md` 規則一（cd 污染）/ 規則三（git 串接）同屬 Bash 工具使用紀律 |

---

## 症狀

PM 執行 `ticket track append-log <id> --section "..." "..."` 或其他含長文字參數的 Bash 命令時，若文字內含 markdown 樣式的 backtick（例如 `` `.claude/hooks/file.py` ``），Bash 會：

1. 將 backtick 內容解析為 command substitution
2. 嘗試把 `` `file.py` `` 當命令執行
3. 失敗輸出錯誤（例如 `command not found`、`permission denied`、`ModuleNotFoundError`）
4. 最終傳給 CLI 的字串**被替換後的空白取代 backtick 範圍**

後果：append-log 仍可寫入但內容缺失路徑識別符，讓 Ticket Context Bundle 的檔案參考變成空白或錯誤。

---

## 實例（2026-04-17 W13-007 Context Bundle）

PM 執行：

```bash
ticket track append-log 0.18.0-W13-007 --section "Problem Analysis" "...Hook 實作：`.claude/hooks/askuserquestion-charset-guard-hook.py` ..."
```

Bash 將 `` `.claude/hooks/...py` `` 當 command 執行：
- 第一個 backtick 路徑檔案存在 → Bash 嘗試執行該 Python 檔 → `ModuleNotFoundError: No module named 'pytest'`（Hook 測試執行）
- 其他 backtick 路徑：`permission denied` / `command not found`

CLI 實際收到的參數：backtick 內容被 substitution 結果取代（多為空字串），Context Bundle 中：
- `- Hook 實作：`（後面空白）
- `- Hook 測試：（W13-003 新建 14 測試）`（路徑消失）

---

## 根本原因

### 真根因

1. **Bash backtick 語法歷史包袱**
   - `` `command` `` 與 `$(command)` 同義，皆為 command substitution
   - 即使在雙引號 `"..."` 內，backtick 仍被解析（單引號 `'...'` 才可抑制）

2. **Markdown 與 shell 衝突**
   - Markdown 用 `` ` `` 表示 inline code
   - PM 寫技術文件時習慣 `` `path/to/file.py` `` 或 `` `function_name()` ``
   - 這些內容直接塞進 Bash double-quoted 參數會觸發 substitution

3. **CLI 工具無感知**
   - `ticket track append-log` 把 `--section` 後的字串當純文字
   - 但 shell 在傳入 CLI 前已完成 substitution，CLI 收到的是替換後結果

---

## 常見陷阱模式

| 陷阱 | 為何錯誤 |
|------|--------|
| 「雙引號應該會保護 backtick」 | 雙引號保護 space / special chars 但**不保護 backtick** |
| 「CLI 收到完整字串」 | Shell 先替換 backtick，CLI 收到的已是替換後 |
| 「backtick 執行失敗會整個中止」 | 不會，Bash 會繼續用「錯誤輸出 / 空字串」當替換結果塞回字串 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 流程 | 長文字參數用 **單引號** 或 **heredoc** 包住（如 `$(cat <<'EOF' ... EOF)`） | 行為準則（已在 bash-tool-usage-rules.md 類似） |
| 流程 | 含 backtick 的 Markdown 內容改用 Edit/Write 直接編輯 Ticket 檔案，繞開 Bash 參數層 | 行為準則 |
| 工具 | `ticket append-log` 評估支援從 `--from-file` 讀入內容，避免命令列轉義 | 建議實施 |
| 規則 | bash-tool-usage-rules.md 新增「第四規則：文字參數含 backtick 改用單引號或檔案讀入」 | 建議實施 |

---

## 檢查清單（PM 寫長文字 CLI 參數時）

- [ ] 文字內含 `` ` `` 嗎？
- [ ] 是 → 以下至少一項：
  - [ ] 整個字串改用 single quote（`'text with `backtick`'`），但注意 single quote 內無法直接含 single quote
  - [ ] 改用 heredoc：`-c "$(cat <<'EOF'\n...\nEOF\n)"`
  - [ ] 改用 Edit/Write 工具直接寫 Ticket 檔，繞開 shell
- [ ] 否 → 雙引號可接受

---

## 教訓

1. **shell 先於 CLI 解析**：任何 `"..."` 內的特殊 shell 字元（backtick / `$` / `!`）都會在 CLI 收到前被 shell 處理
2. **Markdown 寫技術文件會踩 shell 包袱**：PM 寫 Context Bundle 自然用 inline code，反而觸發污染
3. **Edit/Write 比 ticket append-log 更安全**：檔案編輯工具不經過 shell 解析，適合含特殊字元長文字
4. **事後可識別受害範圍**：`wc -l` 對照 Ticket 檔案可快速確認內容缺失

---

## 相關文件

- `.claude/rules/core/bash-tool-usage-rules.md` — Bash 工具使用規則（規則一/三/**四 已升級**）
- `.claude/references/bash-tool-usage-details.md` — 詳細案例
- `ticket_system/commands/lifecycle.py`（W12-005 實作）— append-log 實作可考慮 `--from-file` 參數

---

**Last Updated**: 2026-04-17
**Version**: 1.1.0 — 防護升級至 bash-tool-usage-rules.md 規則四（W13-010 完成）
**v1.0.0**: 首發記錄（W13-007 Context Bundle shell backtick substitution）
**Source**: 2026-04-17 W13-003 完結 session 中，PM append-log W13-007 Context Bundle 含 markdown inline code 的檔案路徑 backtick，被 shell 執行為 command substitution 導致路徑被替換為空白
