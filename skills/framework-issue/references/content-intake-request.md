# consumer 內容收錄請求格式

consumer 把本地新增的 error-pattern 送進框架 canonical 時，請求格式固定如下，主控方收錄時不必重組內容。本檔是格式的唯一定義處；產生草稿的工具與人工填寫都照本檔。

## 用途與前提

收錄通道是 `tarrragon/claude` 的 issue：主控方不讀 consumer repo，所以 consumer 必須把收錄所需的全部內容放進 issue。consumer 沒有送上 canonical 的推送通道（角色與理由見 `references/escalation-flow.md`〈角色：主控方與 consumer〉），不經 issue 的本地新增在下次 `sync-pull` 時沒有上游對應。

為何要固定格式：pattern 全文、索引列與 registry 列都是要逐字落進主控方檔案的內容。格式固定，主控方才能直接複製貼上；格式漂移，收錄時要重新判讀每一欄，且索引列與 registry 列的字面一旦與 consumer 本地不同，下次 `sync-pull` 帶回的列無法與本地列乾淨合併。

適用對象：位於 `.claude/error-patterns/` 內、替換專案名稱與檔案路徑後仍成立的 pattern。替換後不成立的內容屬專案知識，放 consumer 的 `docs/`，不送本格式（分流判準見 `.claude/references/sync-mechanism-guide.md`〈5.3 consumer 的 error-pattern：去處與等待收錄期間〉）。

## 請求本文格式

issue 本文依下列順序放置區塊。區塊界線是 `### <序號>. <區塊名>` 標題，標題文字與序號固定、不增刪、不調換順序；程式以標題行切分區塊。檔案與列的內容放在 fenced block 內，不在 block 外重複。

`<...>` 為待填欄位，其餘字面照抄。

~~~~~markdown
<!-- content-intake-request -->

### 0. 請求資訊

| 欄位 | 值 |
|------|-----|
| pattern_id | <ID，如 PC-XXX-001> |
| target_path | <相對 .claude/error-patterns/ 的路徑，如 process-compliance/PC-XXX-001-slug.md> |
| source_project | <專案目錄名，即 registry 的 dir 值> |
| framework_version | <consumer 的 .claude/VERSION 內容> |
| status | <待收錄 / 編號衝突> |

### 1. pattern 全文

````markdown
<含 frontmatter 的完整檔案內容，逐字>
````

### 2. 索引列

````markdown
<要加進 .claude/error-patterns/README.md 的那一列，逐字>
````

### 3. registry 列

````yaml
<要加進 .claude/error-patterns/_project-registry.yaml 的 projects 項目，逐字；代號已登錄時只寫「已登錄」>
````

### 4. 可攜性判定

| 欄位 | 值 |
|------|-----|
| 判定 | <可攜 / 不可攜> |
| 替換測試 | <替換專案名稱與檔案路徑後仍有意義的理由，一句> |
| carrier | <error-pattern frontmatter `carrier` 值：`rule`／`skill:<名稱>`／`lang-pack:<skill>/<語言>`／`agent:<名稱>`／`none`> |

### 5. 原樣收錄聲明

主控方依下列條件收錄；任一條不接受，於 issue 留言說明，不自行改寫後收錄。

- 檔名前綴與出處（`source_project`）保留。
- 區塊 1 至 3 的字面不改寫；格式或用語需調整時，退回 consumer 修改。
- 區塊 3 的列收錄後，下次 `sync-pull` 帶回的列須與 consumer 本地列字面相同。
~~~~~

## 各區塊填寫規則

| 區塊 | 填寫來源 | 規則 |
|------|---------|------|
| 0. 請求資訊 | 本地 pattern 檔 + `.claude/VERSION` | `status` 預設「待收錄」；上游已有同 ID 且內容不同時填「編號衝突」（處置見〈編號衝突〉） |
| 1. pattern 全文 | 本地 pattern 檔 | 含 frontmatter 的整檔逐字貼入，外層用比內容多一個反引號的 fence，避免內文的 code fence 提前結束區塊 |
| 2. 索引列 | 本地 `.claude/error-patterns/README.md` | 取 `ID | 標題 | 風險 | 來源版本` 那一列逐字複製，不重寫標題 |
| 3. registry 列 | 本地 `.claude/error-patterns/_project-registry.yaml` | 專案代號尚未登錄時填 `code`、`dir`、`note` 三欄的 yaml 項目；已登錄寫「已登錄」。接手者先查證 registry 實際指向哪個檔，不憑記憶填 |
| 4. 可攜性判定 | 本地判定 | 判準沿用 `.claude/rules/core/quality-baseline.md` 規則 6：替換專案名稱與檔案路徑後仍有意義才可攜；不可攜者不送本格式 |
| 5. 原樣收錄聲明 | 固定文字 | 逐字照抄，不改 |

**Why**：registry 列與索引列是共用檔中的單列，三方合併只在本地列與上游列字面相同時乾淨；逐字複製是讓合併成立的前提。**Consequence**：字面不同會在下次 `sync-pull` 產生衝突，或本地列被覆蓋後 allocator 以 `ValueError` 失敗。**Action**：區塊 2、3 一律從本地檔複製，不重新撰寫。

## 收錄方處置

| 步驟 | 動作 |
|------|------|
| 1 | 以區塊 3 登錄專案代號（優先處理：allocator 依賴它，缺列時新 consumer 無法配號） |
| 2 | 以區塊 1 在 `target_path` 建檔，保留檔名前綴與出處 |
| 3 | 以區塊 2 加入索引 |
| 4 | 發版推送；於 issue 留言標明收錄所在版本 |

收錄狀態分三種（已收錄、已回報、待回報）：已收錄指上游有同 ID 且內容相同；已回報指本地 pattern 的 frontmatter 有 `upstream_issue: <issue 號>`；待回報指本地獨有且無 `upstream_issue`。三種狀態的判定與摘要行為由 `error-pattern` skill 的比對功能實作，本檔只定義請求內容。

## 編號衝突

上游已有同 ID 而內容不同時，中央 repo 是編號權威：

1. consumer 將區塊 0 的 `status` 填「編號衝突」，其餘照常填寫。
2. 收錄方改配該前綴的下一個空號建檔，並在 issue 留言寫「舊號 → 新號」。
3. consumer 下次 `sync-pull` 取得新號檔案後，刪除本地舊號檔，並以 grep 更新本地引用。
