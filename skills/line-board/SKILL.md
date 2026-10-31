---
name: line-board
description: "多線開發看板 plugin：在 Pane 顯示用戶待辦、每條線的現行佇列、各 session 狀態與合併閘門最近紀錄，並註冊模型可呼叫的 line_status 工具（各線接續狀態與過期項）。Use when: 查看多線並行進度、啟用或關閉看板、設定協調票、看板或 line_status 顯示異常。"
metadata:
  version: 0.11.0
---

# line-board

多線開發看板（Claude Code plugin，同目錄 `.claude-plugin/` 與 `hooks/`）。在終端機內開一個 Pane，顯示多 session 並行開發的現況：要用戶處理的事項（用戶待辦）、每條線的現行佇列與票狀態、派發中的代理人、本 repo 各 session 的狀態、合併閘門最近紀錄。另外註冊模型可呼叫的唯讀工具 `mcp__line-board__line_status`，回報各線接續狀態與過期項（讀法見 `multi-session-orchestration` 的 `references/line-continuity.md` §3，實作面見 `references/board-screens.md`〈line_status 工具〉）。只讀本機檔案，並執行 `git worktree list` 與 `ps -p <pid> -o lstart=`；不改任何設定、不連網。

## 啟用與關閉

| 項目 | 做法 |
|------|------|
| 啟用 | 預設開啟：plugin 隨 skills 目錄自動載入（`defaultEnabled: true`），不需 `--plugin-dir`。首次載入須接受該專案的 workspace trust |
| 關閉 | 在 `settings.json`（專案或使用者層）的 `enabledPlugins` 加 `"line-board@skills-dir": false` |
| 手動開 Pane | 輸入 `/board`；Pane 關掉後也用它重開 |

```json
{ "enabledPlugins": { "line-board@skills-dir": false } }
```

## 設定檔

看板從專案設定檔讀協調票：`.claude/project-integration/multi-session.json`（主 checkout 內，隨專案提交）。

```json
{ "coordinationTicket": "<完整票號>" }
```

- `coordinationTicket` 為字串，必須是完整票號（含版本與 Wave 前綴，如 `<版本>-W<波次>-<序號>`）；看板由它推導票檔位置與短票號前綴
- 協調票的 `## Solution` 段落放各線的現行佇列行與目標行，格式見 `references/board-screens.md`〈協調票現行佇列行的格式〉；寫入時機與責任屬 `multi-session-orchestration`（路由見下節）

## 沒有設定時的行為

設定檔不存在、不是合法 JSON、缺 `coordinationTicket` 或值不是完整票號，都視為設定不成立：

- session 啟動時不自動開 Pane，也不定時讀取，沒有使用多 session 協調的專案不受影響
- 輸入 `/board` 開啟後，Pane 顯示設定提示：未成立的原因、設定檔的絕對路徑與格式
- 補上設定檔後，下次 session 啟動即自動開 Pane；同一 session 內補上後，再輸入 `/board` 開始讀取

## 合併閘門套件

合併閘門的套件宣告在專案的 `.claude/project-integration/merge-gate.yaml`。要讓改動 line-board 時自動跑它的測試，consumer 加一個套件：

```yaml
suites:
  line-board:
    prefixes: [.claude/skills/line-board/]
    command: [claude, plugin, test, .claude/skills/line-board]
    summary: '^Ran \d+ tests across \d+ files'
    failure: '^\(fail\)'
```

宣告會取代內建預設套件，所以專案原有的套件（如 flutter）要一併寫在 `suites:` 下。

### 合併前型別檢查（手動）

閘門不跑 `tsc`：平台型別（`.claude-plugin/types/`）只在以互動方式 `claude --plugin-dir .claude/skills/line-board` 啟動時產生，skills 目錄載入、headless 啟動與 `claude plugin test` 都不產生，閘門快照與 worktree 因此沒有型別。改到 `.claude/skills/line-board/` 的分支，由 PM 在合併前以主 checkout 的型別檢查 worktree 的程式：

```bash
MAIN=<主 checkout 絕對路徑>   # 須已以互動式 --plugin-dir 啟動過一次
WT=<worktree 絕對路徑>
CFG="$(mktemp -d)/tsconfig.json"
cat > "$CFG" <<EOF
{
  "extends": "$MAIN/.claude/skills/line-board/.claude-plugin/types/tsconfig.json",
  "compilerOptions": { "noEmit": true, "typeRoots": ["$MAIN/.claude/skills/line-board/.claude-plugin/types"] },
  "include": ["$WT/.claude/skills/line-board/hooks/**/*", "$WT/.claude/skills/line-board/types/**/*"]
}
EOF
out=$(npx --no-install tsc -p "$CFG" --listFiles 2>&1); rc=$?
echo "rc=$rc errors=$(printf '%s\n' "$out" | grep -c 'error TS') hooks=$(printf '%s\n' "$out" | grep -c "$WT/.claude/skills/line-board/hooks/")"
```

判準：`rc=0`、`errors=0`，且 `hooks` 大於 0（確認檢查的是 worktree 的檔案）。主 checkout 沒有型別時 `extends` 解析失敗、rc 非 0，屬未執行，不算通過；先以互動式 `--plugin-dir` 啟動一次再跑。產生型別時 Claude Code 會在 `types/` 內寫出內容為 `*` 的 `.gitignore`，型別不會進版控。

## 佇列行格式與多 session 協調

現行佇列行、線目標行的寫法與寫入時機（排定、改派、開新線、結線時同一步寫）屬 `multi-session-orchestration` skill。看板與狀態列（`scripts/statusline_lane.py`）共用同一套解析規則。協調各線時改讀該 skill。

## 畫面規格與調整

| 情境 | 讀 |
|------|---|
| 看板各區塊的資料來源、版面、五色狀態、派發階段判定、合併閘門顯示 | `references/board-screens.md` |
| 調整看板程式的檔案分工與職責 | `references/board-screens.md`〈結構〉 |
| Claude Code 升版後驗證 | `references/board-screens.md`〈驗證〉；指令為 `claude plugin validate`、`tsc -p`、`claude plugin test`（皆對 `.claude/skills/line-board`） |
| 在既有 session 實測 plugin 改動（`/clear` 不重新載入 plugin、檔案變動可能熱重載） | `references/board-screens.md`〈實機驗證時的載入時機〉 |

版本紀錄見同目錄 `CHANGELOG.md`。
