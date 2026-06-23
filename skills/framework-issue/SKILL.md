---
name: framework-issue
description: "Creates and lists framework issues on the canonical framework repo (tarrragon/claude) via gh CLI. Use when tracking a framework-level problem, error-pattern canonical reference, provenance anchor, or cross-consumer fix across projects. Triggers include: framework issue, canonical issue, 跨 consumer 修復追蹤, 框架 issue, error-pattern canonical. Do NOT use for project-local docs/work-logs tickets (use the ticket skill instead)."
---

# Framework Issue

於框架 canonical repo（`tarrragon/claude`）標準化建立與查詢 framework
issue。framework issue 三重用途：provenance 錨點、error-pattern canonical
去重 key、跨 consumer 修復追蹤。本 skill 僅包 `gh` CLI，所有不可用狀態優雅降級。

## Commands

| 命令 | 包裝 | 用途 |
|------|------|------|
| create | `gh issue create --repo tarrragon/claude` | 建立 framework issue |
| list | `gh issue list --repo tarrragon/claude` | 列出 / 去重查詢 framework issue |
| link | 寫本地 error-pattern 檔 | 把 canonical_issue stamp 進 error-pattern 分類資訊表格 |
| fix-status | `gh issue view/edit --repo tarrragon/claude` | 查 / 更新 issue body 內跨 consumer 修復矩陣（軸 C） |

> 範圍：本 skill 含 create / list / link / fix-status，四命令齊備。

## Usage

create：

```bash
python3 .claude/skills/framework-issue/scripts/create_issue.py \
  --title "標題" [--body "內文"] [--label bug] [--label canonical]
```

list：

```bash
python3 .claude/skills/framework-issue/scripts/list_issues.py \
  [--state open|closed|all] [--label X] [--limit 30] [--search "關鍵字"]
```

建 issue 前先用 `list --search "<關鍵字>"` 查既有 canonical issue 避免重複。

link：

```bash
python3 .claude/skills/framework-issue/scripts/link_issue.py \
  <error-pattern-id-或路徑> <issue-ref>
# 例：link PC-020 tarrragon/claude#42
```

link 把 `| canonical_issue | <issue-ref> |` 寫入該 error-pattern 的
「## 分類資訊」表格（落點為表格列，非 YAML frontmatter，與既有結構一致）。
pattern 可傳 id（如 `PC-020`，於 `error-patterns/` 下遞迴解析 `<id>-*.md`）或
直接傳 `.md` 路徑。重複 link 為**更新既有列**而非新增重複列；找不到 pattern
或缺分類資訊表格時降級報錯（exit 3）不寫檔。link 寫的是本地檔，不真打
GitHub API；issue ref 由呼叫端先以 create / list 取得。

升格時機：error-pattern 升格為 canonical 後，先 `create` / 找到對應 framework
issue，再以 `link` 把 issue ref stamp 回 error-pattern 作 canonical 錨點。詳見
`.claude/methodologies/error-pattern-numbering-methodology.md`「canonical 升格機制」。

fix-status（軸 C：跨 consumer 修復追蹤）：

```bash
# view：顯示哪些 consumer 修了該壞 change
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref>

# mark-fixed：把「本 consumer」標為 fixed 並回寫 issue body
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref> --mark-fixed
```

修復狀態 SSOT 為 framework issue body 內的標記區段
`<!-- fix-matrix -->...<!-- /fix-matrix -->`，內嵌 markdown 表格
`| consumer | status |`（flat-base 號無狀態無法追蹤，此為 framework issue
獨有價值）。read=`gh issue view --json body` 解析；write=更新區段後
`gh issue edit --body-file` 回寫；矩陣不存在時 `--mark-fixed` 自動初始化。

consumer 自我識別沿用 `.claude/error-patterns/_project-registry.yaml` + git
toplevel basename（同 error-pattern allocator 的 `identify_project_code`），
**不需也不接受手動傳 consumer 名**；basename 未登錄於 registry 時降級報錯
（防止靜默產生錯誤 consumer 前綴）。

## Graceful Degradation

`scripts/gh_common.py` 的 `preflight()` 與 `run_gh()` 將下列狀態轉為清楚的
stderr 提示與 exit code `3`（`EXIT_DEGRADED`），不拋 traceback：

| 狀態 | 偵測 | 提示方向 |
|------|------|---------|
| gh 未安裝 | `shutil.which("gh")` 為 None | 安裝 GitHub CLI |
| gh 未登入 | `gh auth status` exit != 0 | 執行 `gh auth login` |
| 目標 repo Issues 停用 | gh stderr 含 disabled + issue | 於 repo Settings 啟用 Issues |
| gh 執行例外 | OSError / SubprocessError | 確認安裝完整與網路可用 |

exit code：`0` 成功、`3` 降級、其餘為 gh 原始錯誤碼經 `run_gh` 轉為 `3`。

## Examples

| 情境 | 動作 | 結果 |
|------|------|------|
| 建 canonical issue | `create --title "X" --label canonical` | 成功印 issue URL，exit 0 |
| 去重查詢 | `list --search "PC-V1-009"` | 列出符合 issue，exit 0 |
| gh 未登入 | 任一命令 | stderr 提示 `gh auth login`，exit 3 |

## Testing

```bash
uv run --project .claude/hooks pytest \
  .claude/skills/framework-issue/tests/ -v
```

測試以 mock 攔截 gh subprocess，不真打 GitHub API；涵蓋正常路徑與三種降級路徑。

---

**Version**: 1.0.0
