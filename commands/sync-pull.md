---
description: 從獨立 repo 拉取最新 .claude 配置 (https://github.com/tarrragon/claude.git)
---

# 從獨立 Repo 拉取最新 .claude 配置

請執行以下流程，從獨立 repo 拉取最新的 .claude 配置到本專案。

## 拉取內容

- `.claude/` 目錄所有檔案（Hook、Agent、方法論、規則、project-templates）

## 不覆蓋內容

- 根目錄 `CLAUDE.md`（保留專案特定配置）

## 執行流程

1. **確認本地無未提交變更**
   - 檢查 `.claude` 是否有未提交的變更
   - 如有變更，詢問用戶是否先提交或暫存

2. **先不帶旗標執行一次**
   - 執行 `python3 ./.claude/scripts/sync-claude-pull.py`（不帶 `--confirm-overlay`），保留完整 stdout
   - 依輸出分流：

     | 輸出特徵 | 意義 | 下一步 |
     |---------|------|--------|
     | 結束碼 0，且有「成功拉取 .claude 更新」 | 三方合併，或全量 overlay 但沒有覆蓋或刪除；已跑完 | 跳到步驟 4，不詢問 |
     | 結束碼 1，且 stdout 有一行以 `拉取已中止：全量 overlay 需要確認，但 stdin 不是互動終端機` 開頭 | 全量 overlay 等待確認；`.claude/` 未改動、未寫基準點 | 進入步驟 3 |
     | 其他非 0 結束碼，或結束碼 1 但沒有上一列的那一行 | 其他原因中止（未提交變更、clone 失敗、衝突殘留等） | 依輸出處理，不進入步驟 3，不帶旗標重跑 |

   - 只看結束碼 1 不夠：其他中止原因的結束碼也是 1。判斷依據是上表第二列的那一行，腳本只在「需要確認但無法詢問」時印出這句（輸出帶 ANSI 顏色碼，比對時以子字串比對）

3. **附清單確認（強制使用 AskUserQuestion）**
   - 從步驟 2 的 stdout 取出 `[dry-run]` 開頭的各段與其下的條目（`~` 將覆蓋、`-> conflict:` 轉存 `.sync-conflicts/`、`- delete:` 直接刪除、`x skip-resurrection:` 跳過復活），放進問題
   - 每段最多列 50 條；段落標題的數字大於列出的條目數時，在問題中註明「另有 N 條未列出」
   - AskUserQuestion 問題格式：
     ```
     question: "本次拉取走全量 overlay（沒有基準點，或基準點不可達），會以上游內容整份覆蓋 .claude/。
     將覆蓋：<~ 條目>
     將轉存 .sync-conflicts/：<-> conflict 條目>
     將刪除：<- delete 條目>
     根目錄 CLAUDE.md 與 sync-preserve.yaml 列出的檔案不受影響。腳本會自動備份到 /tmp 臨時目錄。
     清單中有自己建的檔時，選取消，把該檔列進 .claude/sync-preserve.yaml 後重跑 /sync-pull。確認套用？"

     options:
     - 確認套用（腳本自動備份到 /tmp）
     - 先建立穩定備份再套用（備份到 .claude-backup-{date}）
     - 取消
     ```
   - 根據用戶選擇執行：
     - **確認套用**：執行 `python3 ./.claude/scripts/sync-claude-pull.py --confirm-overlay`
     - **先建立穩定備份再套用**：先執行以下備份指令，再執行 `python3 ./.claude/scripts/sync-claude-pull.py --confirm-overlay`
       ```bash
       BACKUP_DIR=".claude-backup-$(date +%Y%m%d-%H%M%S)"
       cp -r .claude "$BACKUP_DIR/"
       echo "備份已建立：$BACKUP_DIR"
       ```
     - **取消**：不再執行腳本。步驟 2 那次執行沒有改動 `.claude/`
   - 帶旗標重跑會重新 clone，印出 dry-run 清單後直接套用。重跑印出的清單和用戶確認的清單不同時（上游在兩次執行之間有新提交），套用已經發生：把多出的條目和備份位置告知用戶

4. **顯示備份位置**
   - 腳本會輸出備份目錄位置
   - 告知用戶如需還原可使用備份

5. **自動偵測需要重新安裝的套件**
   - 使用 `git diff` 自動掃描 `.claude/skills/*/pyproject.toml` 的版本變更
   - 偵測到變更的套件會在日誌中列出
   - 實際的套件重新安裝由 `package-version-sync-hook` 在下次 SessionStart 自動執行
   - Hook 會自動比對 pyproject.toml 版本 vs uv tool list 實際安裝版本
   - 版本不符時自動執行 `uv tool uninstall + cache clean + tool install --reinstall`

6. **建議測試 Hook 系統**
   - 提醒用戶測試 Hook 系統是否正常運作
   - 建議重啟 Claude Code Session 驗證

7. **Hook 完整性驗證（重要）**
   - sync-pull 可能引入新的 hook 檔案。框架 hook 的註冊由上游 `settings.json` 提供，隨這次 pull 一併更新，consumer 不修改 `settings.json`
   - 下次 session 啟動時，SessionStart hook `hook-registration-coverage-check.py` 會報告未註冊的 hook；也可以直接執行它
   - 報告列出框架 hook 未註冊時，回報 framework issue（README〈回報框架問題〉），由主控方在上游補註冊或列入 exclude list；不在 consumer 端補進 `settings.json`
   - 報告列出 `settings.local.json` 內的 hook 註冊時，依〈pull 後檢查清單〉〈6. 幽靈註冊處置〉的表格處理

8. **Post-pull 框架定制引導**
   - 提示用戶執行 `project-init onboard` 完成框架定制：
     ```
     拉取完成。建議執行以下步驟完成框架定制：

     1. 執行 `project-init onboard` — 偵測專案語言、建議停用不適用的 Hook、檢查配置完整性
     2. 如果是全新專案且根目錄無 CLAUDE.md：
        - 複製 `.claude/templates/CLAUDE-template.md` 到專案根目錄
        - 重命名為 `CLAUDE.md`
        - 填入專案特定資訊
     3. 執行 `project-init check` 驗證環境
     ```
   - 如果偵測到根目錄無 CLAUDE.md，額外提醒從模板建立

## pull 後檢查清單（強制）

**Why**：pull 的 delta 檢視、衝突解決、commit 過去全靠 ad-hoc 判斷無 SOP，實證曾發生衝突殘留 `.sync-conflicts/` 多日無人處理。本清單將 pull 後的人工收尾步驟標準化。

**Consequence**：跳過清單會讓未解決衝突與衝突標記殘留靜默累積——下次 pull 的新衝突與舊殘留混雜無法分辨、含 `<<<<<<<` 標記的檔案被當正常內容使用、未 commit 的 delta 汙染後續任務的變更邊界。

**Action**：每次 pull 成功後依序執行以下七步。

### 1. Delta 檢視

```bash
git status --porcelain -- .claude/
git diff --stat -- .claude/
```

逐項確認變更符合預期：來源是上游 delta（合理）還是意外覆蓋本地特化檔（需還原）。

### 2. 衝突解決決策表

腳本對衝突的處理分三類（stdout 已註記）：

| 衝突檔案 | 腳本行為 | 人工後續 |
|---------|---------|---------|
| `VERSION` / `CHANGELOG.md`（版本檔） | 自動採 upstream，`.sync-conflicts/` 留對照副本 | 無需動作（本地版本檔必 stale，屬系統性衝突）；如對照副本顯示本地有應保留的內容，屬異常需人工檢視 |
| `SKILL.md` 的 `metadata.version` 欄位（僅版號差異，無其他內容衝突） | 自動取本地/上游中較大版號並寫回，不留衝突標記 | 無需動作（skill 版號由 skill-sync 通道管轄，git pull 的 canonical 只是快照，兩側各自合法 bump 屬正常情境） |
| 其他檔案（含 `SKILL.md` 內版號以外的真實內容衝突） | 衝突區塊以標記寫回工作區本檔，upstream 非重疊變更已套用；`.sync-conflicts/` 留對照副本 | 依下表三選項逐檔決策，處理完成前工作區該檔含 `<<<<<<<` 標記 |
| 轉 `.sync-conflicts/` 的本地檔（拉取輸出「轉 .sync-conflicts」清單；全量 overlay 把 git 追蹤、上游沒有的本地檔移到此處，不是衝突） | 本地檔從原位移走，轉存於 `.sync-conflicts/` | 逐檔決定：專案自建要保留 → 放回原位；確認不要 → 留待步驟 5 清理 |

非版本檔衝突的三選項：

| 選項 | 適用情境 | 操作 |
|------|---------|------|
| 採 local（保留現狀） | 本地修改是本專案特化（如專案專屬防護） | 以 `.sync-conflicts/` 對照副本為準，將工作區本檔還原為衝突前的本地內容（移除標記） |
| 採 upstream | 本地修改已過時或上游版本更完整 | 從 `.sync-conflicts/` 對照後，以上游內容覆蓋本地檔（移除標記） |
| 手動合併 | 雙方修改都有價值 | 對照工作區本檔內的衝突標記與 `.sync-conflicts/` 副本，手動整合後移除標記並寫回本地檔 |

### 3. 衝突標記歸零驗證（自動）

pull 收尾會自動掃描 `.claude/` 同步範圍內的正式檔是否殘留未解衝突標記（`hook-logs/`、`.sync-conflicts/` 等 pull 不寫入的位置不掃）；命中時 stderr 輸出命中清單並以非零狀態碼結束，須依上表逐一處理後重新確認再繼續。若需自行複查，可執行與掃描邏輯同樣式的手動指令：

```bash
grep -rn "^<<<<<<< \|^>>>>>>> " .claude/ --include="*.md" --include="*.py" --include="*.json" --include="*.yaml" | grep -v ".sync-conflicts/"
```

預期輸出為空。任何命中代表手動合併時把衝突標記寫進了正式檔案，必須立即清除。

**有衝突的那一輪，解完後執行 `--resolve-done` 推進 base**：

```bash
python3 ./.claude/scripts/sync-claude-pull.py --resolve-done
```

| 結果 | 意義 | 下一步 |
|------|------|--------|
| exit 0「已將 pending base 升為 base SHA」 | 同步範圍內無殘留標記，base 已推進到衝突輪的上游 HEAD | 繼續步驟 4 |
| exit 1，stderr 列出檔名 | 仍有檔案殘留標記，base 與 pending base 都未變動 | 處理列出的檔案後重跑 |
| exit 0「沒有待確認的 pending base」 | 上一輪 pull 沒有衝突，無需推進 | 繼續步驟 4 |

**Why**：有衝突的那一輪 pull 不推進 `.sync-state.json` 的 base，而是把本輪上游 HEAD 記成 pending base。**Consequence**：不推進 base 時，下一輪 pull 仍以舊 base 做三方合併，已經解完的衝突會再被標記一次。**Action**：解完衝突就執行 `--resolve-done`，不要手改 `.sync-state.json`（手改不會檢查是否真的解完）。pending base 還沒確認時，下一次一般 pull 開頭會提示先執行 `--resolve-done`。

### 4. Commit 規範

- 一次 pull 的 delta 集中為單一 commit，訊息格式：`chore(sync): pull .claude 更新（上游 <short-sha>）`
- 衝突解決若涉及本地檔修改，與 delta 同 commit（同一次 pull 的完整結果）
- 禁止與其他任務的變更混入同一 commit（變更邊界清晰，便於回溯）

### 5. 清理 .sync-conflicts/

完成步驟 2 的所有衝突決策，且轉存的本地檔都已處理後清空暫存。刪除前先核對：

- 對照拉取輸出的「轉 .sync-conflicts」清單，每個檔已放回原位，或確認不要。
- 以 `git status` 確認清單中的專案自建檔已回到原位（顯示為未變更，而非已刪除）。

```bash
ls -la .claude/.sync-conflicts/ 2>/dev/null   # 先確認內容已處理完
rm -rf .claude/.sync-conflicts/
```

清理是步驟 2 完成的訊號：下次 pull 開始時腳本會偵測 `.sync-conflicts/` 既有殘留並警告列出（殘留 = 前次清單未走完）。

### 6. 幽靈註冊處置

**Why**：`settings.local.json` 是 sync 排除檔，pull 不覆蓋它。上游把一支 hook 從某個目錄搬到另一個目錄時，`settings.json` 的指向由這次 pull 一併更新，`settings.local.json` 內指向舊路徑的那份註冊卻不會被動到，於是成為指向不存在檔案的幽靈註冊。

**Consequence**：幽靈註冊不讓 pull 失敗，pull 收尾的警告也只是警告。成本落在之後——該事件每次觸發都指向一個不存在的腳本，而故障點與這次 pull 已相隔一段時間，排查時不容易聯想回來。

**Action**：pull 收尾若出現下列警告，當場處理，不要留到下次 session 啟動再說：

```
[sync-pull] 警告：settings.local.json 含 hook 註冊（事件: ...）
```

```bash
./.claude/hooks/hook-registration-coverage-check.py         # 先看命中哪幾筆
./.claude/hooks/hook-registration-coverage-check.py --fix   # 移除 command 指向不存在檔的註冊
```

`--fix` 只作用於 `settings.local.json`，且只移除 command 指向不存在檔案的項目。指向的檔案仍存在的註冊不是幽靈，`--fix` 不會動它，依註冊對象處理。`settings.json` 屬框架，consumer 不修改它（README〈設定檔分工〉）：

| 註冊對象 | 判別 | 動作 |
|---------|------|------|
| 框架 hook，上游 `settings.json` 已註冊 | 同一個 command 也出現在 `settings.json` | 從 `settings.local.json` 刪除這筆重複註冊 |
| 框架 hook，上游 `settings.json` 沒有註冊 | 檔案在框架的 `.claude/hooks/` 或 skill 的 `hooks/` 下，`settings.json` 找不到 | 回報 framework issue（README〈回報框架問題〉），由主控方在上游補註冊；`settings.local.json` 的這筆暫時保留，上游補上後依上一列刪除 |
| 專案自有 hook | 檔案是專案自建的，不在上游框架內 | 寫進 `.claude/project-integration/hook-registry.yaml`（格式見 [references/project-hook-registry-format.md](../references/project-hook-registry-format.md)），不手寫進 `settings.local.json`。下一個 session 啟動時，框架依清冊重建 `settings.local.json` 的 hooks 區段；清冊內的條目，coverage check 與本命令都不再示警。清冊外但檔案存在的手寫條目會保留，每次 session 啟動時提示加入清冊 |

`settings.json` 內的舊註冊不在 `--fix` 範圍，依來源分兩種：

| 來源 | pull 時的處理 |
|------|-------------|
| 上游 `settings.json` 本身就有的註冊 | 三方合併套用上游的改名或刪除，自動消失；合併衝突時依〈2. 衝突解決決策表〉處理 |
| hook 自動登記（依 `config/hook-registry.yaml`）寫進來的註冊 | 每次寫入都記在 `.claude/.sync-state.json`。之後 pull 時，若清冊已不列該腳本，或已改由 `hook-dispatch-registry.json`、`settings.json` 其他項目註冊，就收回並在 stdout 列出。沒有紀錄的項目不收回 |

沒有紀錄、但與 `hook-dispatch-registry.json` 重複的項目，pull 收尾會警告，並列出 `settings.json` 的事件、matcher 與 command。這類項目常見於早期版本自動登記時還沒有紀錄。確認不是刻意保留後，從該區段的 hooks 陣列刪除這一筆；該 hook 仍由 hook-dispatcher 執行。

**當前 session 的註冊不回溯**：以上處理的都是磁碟上的設定檔。已啟動的 session 在啟動當下就把 hook 註冊讀進記憶體，pull 改了設定檔不會回頭改它。在 session 中途執行 pull 之後，該 session 剩餘時間內 hook 仍以舊路徑執行，直到重啟為止。

實際出現過的樣態：一次 pull 把兩支 hook 從一個 skill 遷到另外兩個 skill，`settings.json` 的四行指向由三方合併正確更新，磁碟狀態無誤，但同一個 session 內 PostToolUse 仍以舊路徑觸發，Agent 派發與 Stop 事件在該 session 剩餘時間內持續報錯。設定檔查過沒問題而錯誤仍在時，先確認 session 是否尚未重啟，不要回頭改一份已經正確的設定檔。

### 7. 交給框架更新適應

前六步只確認合併正確。這次 delta 對本專案要做哪些對齊（重驗產物、復原被覆寫的本地特化、處理廢除與改名、配合新守衛或啟用設定），不在本清單範圍：commit 完成後執行 `framework-update-adaptation` skill。

## 孤兒稽核（--audit）

**Why**：久未 pull 或長期本地演化，會在 `.claude/` 累積「上游 HEAD 已無、本地仍殘留」的孤兒檔。常規 pull 的 delta 通報只看 `base..HEAD` 這段窗口，早於 base、不落在此窗的舊孤兒不會被列出，形成盲區。

**Consequence**：孤兒長期累積會膨脹 `.claude/` 並讓配置狀態模糊——某檔究竟是刻意保留的本地特化、還是上游早已刪除而該清理的殘留，難以辨別；更糟的是這類殘留可能在後續 `sync-push` 時被傳播到其他專案。

**Action**：執行下列指令做一次主動全量稽核（不限 `base..HEAD` 窗），補上常規 delta 通報的盲區：

```bash
python3 ./.claude/scripts/sync-claude-pull.py --audit
```

稽核行為與後續處理：

| 項目 | 說明 |
|------|------|
| 唯讀性質 | 純唯讀稽核——clone 上游後計算「本地 .claude/ 有、上游 HEAD 無」的全量差集，僅在 stdout 列出候選；不寫任何本地檔、不更新 base SHA、不進入同步主流程 |
| 排除範圍 | preserve 清單、LOCAL_ONLY 標記檔、憑證等不列入孤兒候選 |
| 非阻擋 | 列出的檔可能是該清理的孤兒，也可能是刻意的本地特化；腳本不自動刪除、不阻擋、不視為失敗，由人工逐項判別 |
| 無孤兒時 | 印出「無孤兒候選（本地 .claude/ 皆存在於上游 HEAD）」 |

逐項判別原則：確認為上游已刪除的殘留則手動移除；確認為刻意的本地特化則忽略（並可考慮加入 `sync-preserve.yaml` 標示為應保留）。

## 新專案初始化

如果是新專案，依 `.claude/README.md` 〈首次安裝〉進行；步驟只在該處維護，本檔不重列。

## 還原方式

如果拉取後發現問題，可使用備份還原：

```bash
# 備份位置會在拉取時顯示
cp -r /tmp/備份目錄/.claude .
```

## 注意事項

- 全量 overlay（無基準點或基準點不可達）且預覽有覆蓋或刪除時需要確認，確認來源依序為：
  - 帶 `--confirm-overlay`：不詢問，直接套用（本 command 只在步驟 3 用戶看過清單並同意後才帶）
  - 未帶旗標、stdin 不是互動終端機（如 Claude Code Bash 工具內）：印出 dry-run 清單後不詢問，直接中止，訊息指出應加 `--confirm-overlay`（本 command 步驟 2 即利用這一點取得清單）
  - 未帶旗標、在互動終端機：印出 dry-run 清單後以 `input()` 詢問 `Apply full overlay? [y/N]`，回答非 y 即中止

  中止時一律印出中止原因、結束碼 1、不印「成功拉取」、不更新 `.claude/`、不寫基準點、不執行 hook 自動登記
- 自動備份當前 .claude 配置到臨時目錄
- 拉取會完全替換本地 .claude 檔案
- 不會覆蓋根目錄 CLAUDE.md（專案特定配置）
- 不再需要 `.claude/installed-packages.json` 靜態追蹤檔案（已刪除）
- 套件版本變更由 `git diff` 自動偵測，重新安裝由 Hook 自動處理
- 無需手動執行套件安裝命令，下次 SessionStart 時 Hook 會自動同步
- 拉取後建議執行 `project-init onboard` 完成框架定制
- 拉取後建議檢查 settings.local.json 是否需要調整
- 拉取後建議重啟 Claude Code Session 確保 Hook 正確執行
