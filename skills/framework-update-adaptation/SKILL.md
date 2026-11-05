---
name: framework-update-adaptation
description: "Aligns a consumer project after a framework sync-pull: reads the last-adapted version, lists the delta, classifies each item with judgment questions, files tickets per class. Triggers: 框架更新適應, sync-pull 後, 框架 delta, 本地特化被覆寫, 上游廢除."
metadata:
  version: 1.0.0
---

# 框架更新適應

`sync-pull` 只保證合併正確套上。合併之後還有第二件事：這次 canonical 的 delta 對本專案代表什麼、要做哪些對齊。本 skill 把這件事固定成五步：讀狀態檔 → 列 delta → 逐項分類 → 各類建票 → 更新狀態檔。

**首要原則：每一項都要有分類，「不需動作」也要寫理由。** 框架 delta 是必須對齊的義務，不是可以挑選的機會。沒寫理由的項目，下一個讀者分不出「看過、判定不用動」和「沒看到」。

**與 `cc-release-impact-review` 的分別**：骨架相同，語意相反。那個 skill 評估 Claude Code 更新，對每一項可以判「不採用」；本 skill 處理框架更新，每一項都要判定本專案受不受影響，判「不需動作」也要有理由。

---

## 狀態檔

位置：`.claude/project-integration/framework-update-adaptation/last-adapted.md`（每個 consumer 各一份）。

`project-integration/` 底下的檔案進 git，但 sync-push 與 sync-pull 都不碰（sync 排除規範稱為類型 E），所以狀態檔不會被推到 canonical，也不會被下次 pull 覆寫。不要把狀態檔放進本 skill 目錄：那裡的內容會隨 sync 擴散，變成所有 consumer 共用同一份「上次適應到哪一版」。

格式：

```markdown
# 框架更新適應 — 狀態記錄

## last-adapted

**2.87.0**

## 適應歷史

| 版本區間 | 紀錄票 | 結論摘要 |
|---------|-------|---------|
| 2.86.0 → 2.87.0 | <紀錄票 ID 或「無需建票」> | 各類項數與建出的票 |
```

---

## 流程

### Step 1：讀狀態檔，定起點

讀狀態檔的 last-adapted 版本，再讀 `.claude/VERSION` 取得目前版本。兩者相同時，本次沒有 delta，結束。

**狀態檔不存在**（第一次使用）：列出 VERSION 的寫入歷史：

```bash
git log --format='%h %ad %s' --date=short -- .claude/VERSION | head -5
```

第一列是寫入目前版本的 commit，第二列是前一次寫入，它寫入的版本是起點的候選。用 `git show <第二列 hash>:.claude/VERSION` 讀出版號，向用戶確認「這個版本之前的 delta 是否都已對齊過」；確認後，連同目錄一起建立狀態檔。

只有一列（框架剛導入），或用戶表示第二列不是上一次對齊完成的版本時，起點由用戶指定，不自行推定。

### Step 2：列 delta

delta 有兩個來源，兩個都要取。canonical 的 tag 格式為 `v<版號>`，先確認起點與新版的 tag 都存在：`gh api repos/tarrragon/claude/git/ref/tags/v<版號> --jq .ref`，結束碼非 0 即不存在。

| 來源 | 指令 | 用途 |
|------|------|------|
| canonical 的版本紀錄 | `gh api "repos/tarrragon/claude/contents/CHANGELOG.md?ref=v<新版>" --jq .content \| base64 -d` | 取起點之後到新版之間的條目，作為分類的單位 |
| canonical 的檔案變更 | `gh api "repos/tarrragon/claude/compare/v<起點>...v<新版>" --jq '.files[] \| .status+" "+(.changes\|tostring)+" "+.filename'` | 檔案清單，含每個檔案的 status 與變更行數 |

版本紀錄以 `## [<版號>] - <日期>` 為各版標題，取版號大於起點、小於等於新版的各段。跨越多個版本時，每個版本的條目都要列。檔案清單裡的每個檔案都要歸到某個條目之下；歸不進任何條目的檔案，自成一項，不得略過。

檔案清單有兩種狀況要先標記，再進 Step 3：

| 狀況 | 處理 |
|------|------|
| status 為 `modified`、變更行數為 0 | 只改了權限位，內容不變。這是唯一可以省略 Step 3 四問的例外：直接歸「不需動作」，理由寫「僅權限位」 |
| status 為 `removed` 或 `renamed` | 問句 2 必定命中；其餘三問照常判（被刪的檔案也可能是本專案改過的，會同時命中問句 1） |

**改走本地 git 的條件**：tag 不存在、無法連上 GitHub，或檔案清單剛好 300 筆（compare API 的上限，清單會被截斷且不報錯）。做法：

```bash
# 最近一次把 VERSION 寫成指定版號的 commit（逐一比對內容，不用 -S 子字串比對，避免 2.8.0 命中 12.8.0）
version_commit() { for h in $(git log --format=%h -- .claude/VERSION); do [ "$(git show "$h:.claude/VERSION")" = "$1" ] && { echo "$h"; return; }; done; }
A=$(version_commit '<起點>'); B=$(version_commit '<新版>')
git diff --name-status "$A" "$B" -- .claude/
git log --format='%h %s' "$A..$B" -- .claude/ | grep -v '^[0-9a-f]* chore(sync)'   # 期間本專案自己的 commit
```

A 或 B 為空時，代表本地沒有寫入該版號的紀錄，改向用戶確認起點。最後一條列出的 commit 是本專案自己的變更，它們碰到的檔案要從清單剔除（`git show --name-only <hash>` 查）。這條過濾依賴 sync-pull 的 commit 規範：pull 的 commit 訊息以 `chore(sync)` 開頭。本專案若沒照這個規範寫，先用 `git log --format='%h %s' "$A..$B" -- .claude/VERSION` 找出 pull 的 commit，再人工剔除。本專案就是框架主控方時，期間的 commit 全是自己的，本地 git 分不出上游 delta，只能用 canonical 的兩個來源。

### Step 3：逐項分類

每一項依下表順序判問句 1 到 4，**命中即記下，但繼續往下判**：一項可以同時屬於多類，例如上游刪掉一支 hook，而這支 hook 本專案改過。前四類都沒命中，才歸第 5 類「不需動作」。

| 順序 | 分類 | 範圍 | 判別問句 | 動作 |
|------|------|------|---------|------|
| 1 | 本地特化被覆寫 | 只限本專案曾提交的內容，被這次 pull 改掉或刪掉 | 這個檔案在本次 pull 之前，有沒有本專案自己的 commit（不是 `chore(sync)`）？那些修改在 pull 之後還在嗎？ | 建復原票，或建改走容納機制（`project-integration/`、`settings.local.json`）的票 |
| 2 | 上游廢除或改名 | 上游刪除或改名的檔案、hook、skill、命令；改註冊歸這一類 | 被刪除或改名的舊名稱，本專案還有沒有引用、註冊或依賴（`settings.local.json`、本專案文件、票、程式碼）？上游的版本紀錄有沒有寫明職責由誰接手？ | 建去留或改註冊的票；版本紀錄沒寫接手者時，回報上游 |
| 3 | 新增守衛或啟用設定需要配合 | 上游新增或改動的內容，需要本專案做出回應 | 新的 hook、守衛或檢查，會不會擋住本專案既有的內容？新功能需要的啟用設定，是不是放在 sync 排除檔（上游不會帶來）？本專案的 sync 排除檔（如 `settings.local.json`）裡，有沒有同一個設定的舊值，優先序較高而遮住上游的新設定？ | 建配合票；啟用設定放在 sync 排除檔時，回報上游 |
| 4 | consumer 產物要重驗 | skill 判準、方法論、範本或 schema 有變更 | 本專案有沒有依舊版產出、至今仍在用的規格、守衛定義、基準或生成檔？ | 建重驗票，列出受影響的產物 |
| 5 | 不需動作 | 問句 1 到 4 都答「沒有」 | — | 寫一句理由，說明為什麼不觸及本專案 |

判別要讀本專案的產物，skill 只提供問句，不自動判定。每個問句的第一個查證動作：

| 問句 | 指令 |
|------|------|
| 1：本專案改過這個檔案嗎 | `git log --format='%h %s' -- <檔案> \| grep -v '^[0-9a-f]* chore(sync)' \| head`（依 Step 2 所述的 commit 規範過濾 pull 的 commit） |
| 2：舊名稱還有人用嗎 | `grep -rn '<舊名稱>' .claude/settings.local.json docs/ CLAUDE.md`，再加上本專案的程式碼目錄 |
| 3：新守衛會擋住既有內容嗎 | 讀新守衛的判定條件，用 grep 或它提供的 CLI 檢查模式掃一次本專案既有檔案；守衛只有 hook 形態、沒有掃描入口時，在分類表記下判讀依據（依哪條條件、查了哪些檔案） |
| 3：某個檔案在不在 sync 排除範圍 | `python3 -c "import sys; sys.path.insert(0,'.claude'); from pathlib import Path; from lib.sync_exclude_manifest import should_exclude; print(should_exclude(Path(sys.argv[1])))" <相對 .claude 的路徑>`，印出 `True` 即被排除 |
| 4：本專案有依舊版產出的東西嗎 | `grep -rln '<變更的 skill 名、範本名或 schema 檔名>' docs/ CLAUDE.md`，再加上本專案的程式碼、測試與資源目錄；找到副本時，以同一個新增鍵名在兩邊 `grep -c` 比對計數（範例第 2 列即此法） |

### Step 4：各類建票

命中某一類、但查證時發現對齊已經完成（例如變更在本專案提交時，同一批就已同步了內嵌副本），照樣記下分類，動作欄寫「已完成」和查證結果，不建票。本專案就是變更來源時，這種情況最常見。

分類結果只有「不需動作」與「已完成」時，不建票，跳到 Step 5。

有任何一類需要動作時：

1. 建一張 ANA 紀錄票，標題寫明版本區間（例：`框架更新適應 2.86.0 → 2.87.0`），Problem Analysis 貼完整分類表，每一項都要有分類，以及理由或動作。
2. 每個需要動作的類別建一張子票（`ticket create --parent <紀錄票 ID>`），列出該類命中的項目。子票型別：要改檔用 IMP，只需查證或判斷用 ANA。
3. 一項命中多類時，放進順序最前那一類的子票；其他類的子票不重複列。
4. 「回報上游」的項目記在所屬類別的子票裡，不另開子票。執行時依 `framework-issue` skill 的流程（先查重，再 observe 或開 issue），不在本專案直接修改框架檔案。

### Step 5：更新狀態檔

把 last-adapted 改成本次的新版本。在歷史表追加一列：版本區間、紀錄票 ID（沒建票就寫「無需建票」）、結論摘要（各類項數與建出的票）。

只有 Step 3 每一項都有分類之後，才可以更新狀態檔。

---

## 範例

取自一次實跑（2026-11-05 量測）：一個會消費 `tracking_schema.json` 的專案，delta 是 2.86.0 → 2.87.0。canonical 版本紀錄有 9 個條目，檔案清單 18 個。以下摘取其中四項：

| 項目 | 判別過程 | 分類 | 動作 |
|------|---------|------|------|
| feat：狀態列改為框架預設啟用（`settings.json` 新增 `statusLine`） | 問句 1：本專案沒改過上游這次改的設定行。問句 3：啟用設定這次放在 sync 範圍內，pull 後自動生效；查 `grep -c statusLine .claude/settings.local.json` 得 0，沒有舊值遮住新設定 | 不需動作 | 理由：啟用設定隨 pull 進來，本地沒有遮住它的舊值。若計數不是 0，就歸第 3 類並建配合票 |
| feat：GRAPH_EDGE_TYPES 新增 proposed 層 `closed_by` 邊 | 問句 4：本專案 App 消費這份型別表，另有一份 build 內嵌的副本；兩份的 `closed_by` 計數一致（皆為 2，等於上游） | consumer 產物要重驗 | 已完成：內嵌副本與上游一致，不建票 |
| `statusline_lane.py`（status 為 modified，變更行數 0） | 只改了權限位 | 不需動作 | 理由：僅權限位，內容不變 |
| docs：新增 error-pattern IMP-GPD-025 | 四問都沒有：純知識庫新增，不觸及本專案的產物、設定或註冊 | 不需動作 | 理由：純知識庫新增 |

---

## 反模式

| 反模式 | 後果 | 正確做法 |
|-------|------|---------|
| 只列需要動作的項目 | 讀者分不出「判定不用動」和「漏看」 | 每一項都分類，「不需動作」寫理由 |
| 只看 CHANGELOG 不看檔案清單 | 版本紀錄沒寫到的刪除或改名會被漏掉 | Step 2 兩個來源都取，每個檔案都要歸到某一項 |
| 判到第一個命中就停 | 同時屬於兩類的項目只處理一半 | Step 3 判完四問 |
| 狀態檔放進本 skill 目錄 | 隨 sync 擴散，各 consumer 讀到別人的進度 | 放 `project-integration/` |
| 分類沒完成就更新狀態檔 | 下次從新版本開始，沒判完的項目永遠不會再被看到 | Step 5 只在全部分類完成後執行 |
| 在本專案直接改框架檔案來配合 | 下次 pull 被上游舊版覆蓋 | 需要上游修的，走 `framework-issue` 回報 |

---

## 相關文件

- `sync-pull` 指令的〈pull 後檢查清單〉：最後一步導向本 skill；合併正確性仍由該清單負責
- `cc-release-impact-review` skill：骨架來源（狀態檔去重、逐項分類、不漏項）
- `framework-issue` skill：回報上游的查重與 observe 流程
- sync 排除規範（`sync-exclusion-guide`）的類型 E：狀態檔放 `project-integration/` 的依據

---

版本紀錄在同目錄的 `CHANGELOG.md`。
