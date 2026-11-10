# Fix-Matrix 命令集

適用於「一個壞 change、多個 consumer 各自修復」的場景：修復狀態與版本號記在 issue body 的固定標記區段，各 consumer 以命令回寫。六命令：create／list／link／fix-status／fix-version／close。

- [create 與 list](#create-與-list)
- [link](#link)
- [fix-status](#fix-status)
- [fix-version](#fix-version)
- [close](#close)
- [Graceful Degradation](#graceful-degradation)

## create 與 list

```bash
python3 .claude/skills/framework-issue/scripts/create_issue.py \
  --title "標題" [--body "內文"] [--label bug] [--label canonical]

python3 .claude/skills/framework-issue/scripts/list_issues.py \
  [--state open|closed|all] [--label X] [--limit 30] [--search "關鍵字"]
```

`create` 的 body 一律自動附加環境資訊區段 `<!-- env-info -->`（OS／Claude Code 版本／Python 版本），供跨環境排查徵狀差異；任一項收集失敗降級為 `unknown`，不阻擋建立。建 issue 前先以 `list --search` 或 `section_comment.py dedup` 查既有 issue；`dedup` 涵蓋 comment 內文且拆詞聯集，`list --search` 只是粗篩。

## link

```bash
python3 .claude/skills/framework-issue/scripts/link_issue.py \
  <error-pattern-id-或路徑> <issue-ref>
# 例：link PC-020 tarrragon/claude#42
```

把 `| canonical_issue | <issue-ref> |` 寫入該 error-pattern 的「## 分類資訊」表格（落點為表格列，非 YAML frontmatter）。pattern 可傳 id（於 `error-patterns/` 下遞迴解析 `<id>-*.md`）或直接傳 `.md` 路徑。重複 link 為更新既有列；找不到 pattern 或缺分類資訊表格時 exit 3 不寫檔。link 只寫本地檔，不打 GitHub API。

升格時機：error-pattern 升格為 canonical 後，先 `create` 或找到對應 issue，再以 `link` 把 issue ref stamp 回 error-pattern 作 canonical 錨點。判準見 error-pattern 編號方法論的「canonical 升格機制」。

## fix-status

```bash
# view：顯示哪些 consumer 修了該壞 change
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref>
# mark-fixed：把「本 consumer」標為 fixed 並回寫 issue body
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref> --mark-fixed
```

修復狀態 SSOT 為 body 內 `<!-- fix-matrix -->...<!-- /fix-matrix -->` 區段，內嵌表格 `| consumer | status |`。read 以 `gh issue view --json body` 解析，write 更新區段後 `gh issue edit --body-file` 回寫；矩陣不存在時 `--mark-fixed` 自動初始化。

consumer 自我識別沿用 `.claude/error-patterns/_project-registry.yaml` 加 git toplevel basename（與 error-pattern 配號器同一函式），**不接受手動傳 consumer 名**；basename 未登錄時降級報錯，防止靜默產生錯誤前綴。

## fix-version

```bash
python3 .claude/skills/framework-issue/scripts/fix_version.py <issue-ref> \
  --summary "徵狀摘要" [--version X.Y.Z] [--date YYYY-MM-DD]
```

版本號註記 SSOT 為 body 內 `<!-- fix-versions -->...<!-- /fix-versions -->` 區段，內嵌表格 `| version | date | summary |`。`--version` 省略時讀本地 `.claude/VERSION`（sync-push 後已同步至框架 repo 的版本號）；`--date` 省略為今日。同版本號重複標記為更新既有列。多筆版本號可累積於同一 issue，close 後發現新徵狀仍可追加，`fix-version` 不要求 issue 為 open。

## close

```bash
python3 .claude/skills/framework-issue/scripts/close_issue.py <issue-ref> \
  [--reason completed|"not planned"] [--comment "說明"]
```

兩種關閉的前置條件不同，追溯載體也不同：

| 關閉原因 | 前置條件 | 追溯載體 | 不符時 |
|---------|---------|---------|-------|
| `completed`（或省略 `--reason`） | body 已有非空的 fix-versions 版本號註記 | 修復版本表（`fix-version` 寫入） | exit 3，提示先 `sync-push` 取得框架版本號並以 `fix-version` 註記 |
| `"not planned"`（過時、非框架、重複等不修關閉） | `--comment` 寫明判定理由；本地 `.claude/VERSION` 可讀 | 關閉留言：判定理由 + 工具自動附上的「不修關閉，判定依據框架版本：<版本>」 | exit 3，提示補 `--comment` 或確認 VERSION 可讀 |

**Why**：修復版本表回答「哪一版修好」，沒有版本號，其他 consumer 無從得知此 issue 對應框架的哪次同步；繞過閘門在網頁手動關閉，會讓查重 SOP 誤判此 issue 已有版本可追溯。不修關閉沒有「修好的版本」，若寫進修復版本表，讀者以表判斷修復版本時會誤讀；它要留下的是「依據哪一版的框架判定不修」，所以改記在關閉留言，版本由工具讀 `.claude/VERSION` 填入，不靠人工記得寫。

## Graceful Degradation

`scripts/gh_common.py` 的 `preflight()` 與 `run_gh()` 將下列狀態轉為 stderr 提示與 exit code `3`，不拋 traceback：

| 狀態 | 偵測 | 提示方向 |
|------|------|---------|
| gh 未安裝 | `shutil.which("gh")` 為 None | 安裝 GitHub CLI |
| gh 未登入 | `gh auth status` exit != 0 | 執行 `gh auth login` |
| 目標 repo Issues 停用 | gh stderr 含 disabled + issue | 於 repo Settings 啟用 Issues |
| gh 執行例外 | OSError / SubprocessError | 確認安裝完整與網路可用 |

exit code：`0` 成功、`3` 降級、其餘 gh 原始錯誤碼經 `run_gh` 轉為 `3`。

| 情境 | 動作 | 結果 |
|------|------|------|
| 建 canonical issue | `create --title "X" --label canonical` | 印 issue URL，exit 0 |
| gh 未登入 | 任一命令 | stderr 提示 `gh auth login`，exit 3 |
| 註記修復版本號 | `fix-version <ref> --summary "..."` | 版本號取自 `.claude/VERSION`，exit 0 |
| 關閉但未註記版本號 | `close <ref>` | stderr 提示先執行 fix-version，exit 3 |
| 不修關閉 | `close <ref> --reason "not planned" --comment "非框架問題"` | 不檢查修復版本表；關閉留言附判定依據的框架版本，exit 0 |
| 不修關閉但未給理由 | `close <ref> --reason "not planned"` | stderr 提示補 `--comment`，exit 3 |
