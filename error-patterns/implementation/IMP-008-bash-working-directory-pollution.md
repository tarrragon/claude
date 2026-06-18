# IMP-008：Bash 工作目錄污染

**錯誤碼**: IMP-008
**分類**: Implementation / Tool Usage
**風險等級**: 中（影響操作正確性，不影響資料安全）
**發現日期**: 2026-03-03
**狀態**: 已記錄，已加入防護規則

---

## 症狀

同一 session 內先執行含 `cd` 的命令：
```bash
cd .claude/skills/ticket && uv run ticket track list
```

後續命令找不到預期路徑：
```
Exit code 127: No such file or directory: ./scripts/sync-claude-push.sh
Exit code 1:   ls: scripts/sync-claude-push.sh: No such file or directory
```

即使檔案確實存在，相對路徑也失效。

---

## 根本原因

Claude Code 的 Bash 工具在同一 session 內保持**持久 shell 狀態**。

- `cd` 執行後，工作目錄永久改變（直到 session 結束）
- 後續所有 Bash 命令相對路徑都基於新工作目錄計算
- 與一般 terminal 的行為完全一致，但跨越多個工具呼叫時容易被忽視

---

## 防護方案

### 立即修復（發現污染後）

```bash
# 確認當前目錄
pwd

# 切回專案根目錄
cd /path/to/project
```

### 預防措施（避免污染）

```bash
# 方法 1：子 shell（推薦）
(cd .claude/skills/ticket && uv run ticket track list)

# 方法 2：uv -d 參數
uv -d .claude/skills/ticket run ticket track list

# 方法 3：每次命令前明確指定絕對路徑
cd /project/root && ./scripts/sync-push.sh
```

---

## 觸發案例（復發紀錄）

| 日期 | 情境 | 復發細節 | 教訓 |
|------|------|---------|------|
| 2026-06-15（W8-049 session） | PM 跑 skill 測試 + 還原 cwd | 兩次裸 cd 違反規則一：(1) `cd .../broken-link-check && python3 -m pytest`（跑測試）；(2) `cd /project/root && grep ...`（還原兼驗證）。PreToolUse `[Bash Edit Guard]` hook 兩次皆 WARN 但屬非阻擋層，cd 仍執行 → cwd 汙染使後續相對路徑 grep 假性 No such file、第二次觸發 chpwd ls 淹沒（IMP-056）干擾 git status 判讀。 | warning-only 提示不足以阻止復發——在場 WARNING 仍被忽略。連「跑測試」「還原 cwd」這類看似無害操作也須一律用子 shell `(cd ... && cmd)` 或 `uv run --project <dir>`；裸 cd 無例外豁免。 |
| 2026-06-18（app_tunnel v1.2.0） | PM 跑診斷散落多次裸 cd（`cd .../skills/ticket`、`cd /project/app_tunnel; ...`） | cwd 停在 `.claude/skills/ticket` 後，**安裝版 `ticket` CLI 的 `get_project_root()` 從錯誤 cwd 解析**，`ticket track list/complete` 回「沒有 Tickets / 找不到 Ticket」——但 ticket md 與索引皆正常。PM 未先察覺 cwd 汙染，**連環提出三個錯誤假設**（sync-pull 的 track.py 回歸、frontmatter 損壞、.version-release.yaml config 破壞）並逐一查證，耗費多輪。最終 `cd /project/app_tunnel` 還原 cwd 後一切正常。多次 `[Bash Edit Guard]` WARN 全程在場被忽略。 | 新症狀類：cwd 汙染不只使相對路徑失敗，更使**下游工具 `get_project_root()` 解析到錯誤 root → 假性「找不到資源」false negative → 連環錯誤假設瀑布**。「工具回報找不到」時，**第一順位排查 cwd**（`pwd`）而非懷疑工具/資料損壞（對齊 tool-output-trust 規則 5：記錄/工具回報非 ground truth，世界平面以 cwd-correct 重查為準）。warning-only 已三度被忽略 → 升級為 DENY（見下）。 |

> **Why warning-only 不夠（已三度復發）**：hook 每次都在 context 印出明確 WARN，PM 仍重複裸 cd。提示層對「順手 cd」攔截力不足。**根治升級**：既然依設計（子 shell / `git -C` / `uv -d` / 絕對路徑）從不需要持久 cd，bare cd 永遠是錯誤 → `bash-edit-guard-hook` 由 WARN 升級為 **DENY**（在命令送出當下擋下，cwd 永不被汙染），並補 heredoc/quoted 內字面 cd 的 FP 抑制（上游 PR，framework hook）。預防 > 事後提示。

---

## 相關規則

- @.claude/rules/core/bash-tool-usage-rules.md - 完整防護規範

---

## 發現背景

**版本**: 0.31.1
**操作**: 執行 ticket 查詢後接著執行 sync-push
**根因鏈**: `cd .claude/skills/ticket` → 工作目錄污染 → `./scripts/sync-claude-push.sh` 找不到
**修復**: 改用絕對路徑 `cd /path/to/project && bash scripts/...`
