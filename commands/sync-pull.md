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

2. **覆蓋確認（強制使用 AskUserQuestion）**
   - 在執行腳本前，必須使用 AskUserQuestion 工具詢問用戶確認
   - 顯示即將被覆蓋的內容，讓用戶知情同意
   - AskUserQuestion 問題格式：
     ```
     question: "即將從 tarrragon/claude.git 拉取更新。以下內容將被覆蓋：
     - .claude/ 目錄所有內容（包含 hooks、agents、methodologies、rules、project-templates 等）

     根目錄 CLAUDE.md 不受影響。腳本會自動備份到 /tmp 臨時目錄。
     確認繼續？"

     options:
     - 確認拉取（腳本自動備份到 /tmp）
     - 先建立穩定備份再拉取（備份到 .claude-backup-{date}）
     - 取消
     ```

3. **根據用戶選擇執行**
   - **確認拉取**：直接執行 `python3 ./.claude/scripts/sync-claude-pull.py`
   - **先備份再拉取**：先執行以下備份指令，再執行拉取腳本
     ```bash
     BACKUP_DIR=".claude-backup-$(date +%Y%m%d-%H%M%S)"
     cp -r .claude "$BACKUP_DIR/"
     echo "備份已建立：$BACKUP_DIR"
     ```
     然後執行：`python3 ./.claude/scripts/sync-claude-pull.py`
   - **取消**：中止操作，不執行任何動作

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
   - sync-pull 可能引入新的 hook 檔案，但尚未在 `settings.json` 中登記
   - 建議執行以下指令確認未登記的 hook：
     ```
     提示用戶：「建議執行 project-init onboard 或在 SessionStart 時檢查 hook 完整性報告，
     確認 .claude/hooks/ 下所有 hook 都已在 settings.json 登記，
     若有未登記的 hook 請補充到 settings.json 或加入 exclude list」
     ```
   - 或等待下次 session 啟動，SessionStart hook `hook-registration-coverage-check.py` 會自動報告

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

**Action**：每次 pull 成功後依序執行以下六步。

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

非版本檔衝突的三選項：

| 選項 | 適用情境 | 操作 |
|------|---------|------|
| 採 local（保留現狀） | 本地修改是本專案特化（如專案專屬防護） | 以 `.sync-conflicts/` 對照副本為準，將工作區本檔還原為衝突前的本地內容（移除標記） |
| 採 upstream | 本地修改已過時或上游版本更完整 | 從 `.sync-conflicts/` 對照後，以上游內容覆蓋本地檔（移除標記） |
| 手動合併 | 雙方修改都有價值 | 對照工作區本檔內的衝突標記與 `.sync-conflicts/` 副本，手動整合後移除標記並寫回本地檔 |

### 3. 衝突標記歸零驗證（自動）

pull 收尾會自動掃描 `.claude/` 正式檔（排除 `.sync-conflicts/`）是否殘留未解衝突標記；命中時 stderr 輸出命中清單並以非零狀態碼結束，須依上表逐一處理後重新確認再繼續。若需自行複查，可執行與掃描邏輯同樣式的手動指令：

```bash
grep -rn "^<<<<<<< \|^>>>>>>> " .claude/ --include="*.md" --include="*.py" --include="*.json" --include="*.yaml" | grep -v ".sync-conflicts/"
```

預期輸出為空。任何命中代表手動合併時把衝突標記寫進了正式檔案，必須立即清除。

### 4. Commit 規範

- 一次 pull 的 delta 集中為單一 commit，訊息格式：`chore(sync): pull .claude 更新（上游 <short-sha>）`
- 衝突解決若涉及本地檔修改，與 delta 同 commit（同一次 pull 的完整結果）
- 禁止與其他任務的變更混入同一 commit（變更邊界清晰，便於回溯）

### 5. 清理 .sync-conflicts/

完成步驟 2 的所有衝突決策後清空暫存：

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

`--fix` 只作用於 `settings.local.json`，且只移除 command 指向不存在檔案的項目。指向的檔案仍存在的註冊不是幽靈，`--fix` 不會動它，這種要自己搬到 `settings.json`：框架 hook 的註冊來源只應有 `settings.json` 一處。`settings.json` 內的幽靈由 sync overlay 自癒，不在 `--fix` 範圍。

**當前 session 的註冊不回溯**：以上處理的都是磁碟上的設定檔。已啟動的 session 在啟動當下就把 hook 註冊讀進記憶體，pull 改了設定檔不會回頭改它。在 session 中途執行 pull 之後，該 session 剩餘時間內 hook 仍以舊路徑執行，直到重啟為止。

實際出現過的樣態：一次 pull 把兩支 hook 從一個 skill 遷到另外兩個 skill，`settings.json` 的四行指向由三方合併正確更新，磁碟狀態無誤，但同一個 session 內 PostToolUse 仍以舊路徑觸發，Agent 派發與 Stop 事件在該 session 剩餘時間內持續報錯。設定檔查過沒問題而錯誤仍在時，先確認 session 是否尚未重啟，不要回頭改一份已經正確的設定檔。

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

如果是新專案，需要手動建立 CLAUDE.md：

1. 複製 `.claude/templates/CLAUDE-template.md` 到根目錄
2. 重命名為 `CLAUDE.md`
3. 填入專案特定資訊（專案目標、技術選型、MCP 配置）
4. 驗證所有連結有效

## 還原方式

如果拉取後發現問題，可使用備份還原：

```bash
# 備份位置會在拉取時顯示
cp -r /tmp/備份目錄/.claude .
```

## 注意事項

- 自動備份當前 .claude 配置到臨時目錄
- 拉取會完全替換本地 .claude 檔案
- 不會覆蓋根目錄 CLAUDE.md（專案特定配置）
- 不再需要 `.claude/installed-packages.json` 靜態追蹤檔案（已刪除）
- 套件版本變更由 `git diff` 自動偵測，重新安裝由 Hook 自動處理
- 無需手動執行套件安裝命令，下次 SessionStart 時 Hook 會自動同步
- 拉取後建議執行 `project-init onboard` 完成框架定制
- 拉取後建議檢查 settings.local.json 是否需要調整
- 拉取後建議重啟 Claude Code Session 確保 Hook 正確執行
