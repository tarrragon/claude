# session 命名與換 session 時機

各線以自動產生的衍生名稱（例如 `<repo>-3e`）互稱時，用戶切換終端機無法分辨哪一個 session 是哪條線。本檔規定：一個 session 只持有一條線、以線主題命名、線完結或轉階段時換 session，以及改名後必須同步的位置。

**用語**：「協調票」指主控記錄各線目標與佇列的那張票；「現行佇列行」指協調票中 `**L<n> 現行佇列**（<session 名稱>）：<票序>` 格式的行，每條線以最後一行為準。看板與狀態列從現行佇列行取得線號與 session 名稱的對應。

**量測版本**（2026-10-20，macOS）：行為實測在 Claude Code 2.1.303 的行程上進行，依據是 sessions 檔的 `version` 欄位；CLI 說明與 binary 字串來自 2.1.304。改名與定址行為屬 Claude Code 內部實作，沒有相容承諾；升版後依本檔末的確認方式重新核對。

---

## 1. 規則

| 規則 | 做法 | 不這樣做的後果 |
|------|------|---------------|
| 一個 session 一條線 | 主控分線時，每條線配一個 session；某 session 的線結束後，不把另一條線接進同一個 session | 一個 session 持有多條線時，名稱只能對應其中一條，狀態列與看板無法以名稱判斷它在做哪條線 |
| 以線主題命名 | 名稱要讓人一看就知道是哪條線的主題，格式只守下方的命名底線；要不要放線號、用中文或英文，由命名者自定 | 衍生名稱與線無關，用戶與各線只能靠記憶對照代號與線號 |
| 線完結或轉階段就換 session | 線的佇列寫上結束，或線從一個階段轉入下一個階段（例如分析定案後轉實作）時，舊 session 收尾，另開一個以新主題命名的 session 接手 | 舊 session 的 context 會繼續累積，裝的多是前一階段的內容；名稱也不再反映目前在做的事 |

**命名底線**（用戶裁定，2026-10-20）：

| 底線 | 理由 |
|------|------|
| 以線主題命名 | 名稱的用途就是讓用戶與各線不必對照代號就知道是哪條線 |
| 本機唯一 | `ListAgents` 列出本機所有專案的 session，其他專案可能已有同名的 session。改名後以 `ListAgents` 的自稱為準。撞名時的行為尚未實測，依 2.1.304 的 binary 字串：`/rename` 回應改為 `Session renamed to: <實際名稱> ("<要求的名稱>" is held by another live session on this machine)`，`nameSource` 記為 `collision` |
| 不含全形右括號「）」與換行 | 現行佇列行以全形括號包住 session 名稱，看板解析時遇到第一個「）」就截斷；換行會讓佇列行斷成兩行 |

**實作限制**：名稱不要以「[6 到 12 位十六進位]」結尾（例如 `xxx [3fa9c1]`）。SendMessage 以 `<名稱> [<ref>]` 表示消歧義，這種名稱會被誤讀成 ref（依 2.1.304 binary 字串，未實測）。

**平台對字元的處理**：

- 實測（2026-10-20）：
  - 中文名稱可以設定。`/rename` 改成「看板」「看板設計」「主控」後，`ListAgents` 都以原字面顯示。
  - 含中文與空白的名稱可以用原字面定址。以「修復 合併閘門對 Flutter 資產目錄免跑 flutter 測試」為 `to` 呼叫 SendMessage，回傳 success。
  - 舊名失效另有一例：改名後以舊的衍生名稱傳訊，回 `No agent named ... reachable`。
- 依 2.1.304 binary 字串，未實測：
  - `/rename` 只在去掉不可見字元後名稱為空時拒絕。
  - 比對名稱時會先正規化（NFKC、去控制字元、轉小寫、空白換成連字號），所以只差在大小寫或空白的兩個名稱，推測會被視為撞名。

---

## 2. 命名的方法

| 時機 | 方法 | 說明 |
|------|------|------|
| 開新 session | `claude -n <名稱>`（或 `--name`） | 首選。啟動就定名，不會先以衍生名稱對外一段時間 |
| 已開啟的 session | 用戶在該 session 輸入 `/rename <名稱>`（別名 `/name`） | 這是內建 CLI 命令，模型無法自行觸發；需要時請用戶輸入 |

**同一行程內換 session（例如 `/clear`）不換名**：名稱記在 `~/.claude/sessions/<pid>.json`，跟著行程走。實測：一個衍生名稱的行程在同一行程內換成新 session（sessionId 改變）後，名稱仍是原本的衍生名稱；當時換 session 的操作是否為 `/clear` 沒有記錄，`/clear` 的行為由 §5 第 3 步確認。用 `/rename` 改過名的行程換 session 後名稱是否保留，也尚未量測。所以換線時要開新行程（`claude -n`），或請用戶 `/rename`；只在原行程換 session 的話，新 session 可能頂著前一條線的名稱。

---

## 3. 改名後必須同步的位置

**舊名在改名當下就失效**：以舊名 SendMessage 會回錯誤（`No agent named '<舊名>' is reachable`），錯誤附的建議名稱清單也不含新名，送訊方無法從錯誤訊息找到改名後的 session。所以改名後要依下表同步：

| 步驟 | 誰做 | 做法 | 不這樣做的後果 |
|------|------|------|---------------|
| 告知新名 | 改名的 session | 改名後立刻以新名身分傳訊主控，寫明舊名與新名 | 主控仍以舊名傳訊，訊息送不到 |
| 更新現行佇列行 | 主控 | 在協調票追加一行該線的現行佇列行，括號內填新名；格式不變 | 以名稱比對線與 session 的看板和狀態列找不到對應，該線顯示為無 session |
| 轉知有往來的線 | 主控 | 只轉知最近與該線直接互傳事實的線 | 那些線仍以舊名直接傳訊，送訊失敗後要回頭問主控 |

---

## 4. 換 session 的步驟

1. 舊 session 依 `wrap-up-and-handoff.md` §1 收尾：寫票面〈階段收尾狀態〉，把發現建成票，推送票面 commit。
2. 用戶開新終端機，以 `claude -n <新主題>` 啟動。
3. 主控在協調票寫該線新的目標行與現行佇列行（括號內填新名），再傳訊給新 session 指派線。
4. 新 session 只讀票面接手，不依賴舊 session 的對話。

舊 session 收尾後就可以關閉。不要讓它繼續持有線，否則兩個 session 都在 `ListAgents` 裡，主控和各線傳訊時可能選錯對象。

---

## 5. 升版後的確認方式

1. 在一個測試用 session 輸入 `/rename <名稱>`，讀它的 `~/.claude/sessions/<pid>.json`，確認 `name` 已改、`nameSource` 為 `user`。
2. 從另一個 session 以新名 SendMessage，確認送達；以舊名送訊，確認錯誤字面與本檔 §3 相符。
3. 在同一行程內 `/clear`，確認名稱維持不變。

任一項不符，表示行為已變，先修正本檔再沿用。

---

## 6. 狀態列

`scripts/statusline_lane.py` 在內層狀態列輸出前加一行 `L<n> │ <名稱>`，讓用戶切換終端機時辨認 session 所屬的線。名稱取 statusLine stdin 的 `session_name`（`/rename` 或 `-n` 設定後才出現），缺席時以 `session_id` 對 `~/.claude/sessions/*.json` 的 `sessionId` 取 `name`。線號從協調票 `## Solution` 段的現行佇列行取得（規則同看板：每線取最後一行、票序為 `（結束）` 或 `（無）` 的線視為結束、名稱精確比對；一個名稱對到多條線時列 `L6·L13`）。對不到線時只印名稱，名稱也沒有時不印前綴。任何解析失敗只省略前綴，內層狀態列照常輸出。

**啟用方式**：在專案 `.claude/settings.local.json` 設定（只影響本專案 session，不動全域設定）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 .claude/skills/multi-session-orchestration/scripts/statusline_lane.py --coord-ticket <協調票路徑>"
  }
}
```

| 參數 | 說明 |
|------|------|
| `--coord-ticket` | 協調票路徑；相對路徑以 stdin 的 `workspace.project_dir` 為基準。未給或檔案缺席時不顯示線號 |
| `--inner` | 內層狀態列命令；未給時讀 `~/.claude/settings.json` 的 `statusLine.command`。該命令指回本腳本時不執行內層（避免遞迴） |

寫入 settings.local.json 屬用戶授權範圍，由主控向用戶確認後才寫。
