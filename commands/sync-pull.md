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
   - 或等待下次 session 啟動，SessionStart hook `hook-completeness-check.py` 會自動報告

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

**Action**：每次 pull 成功後依序執行以下五步。

### 1. Delta 檢視

```bash
git status --porcelain -- .claude/
git diff --stat -- .claude/
```

逐項確認變更符合預期：來源是上游 delta（合理）還是意外覆蓋本地特化檔（需還原）。

### 2. 衝突解決決策表

腳本對衝突的處理分兩類（stdout 已註記）：

| 衝突檔案 | 腳本行為 | 人工後續 |
|---------|---------|---------|
| `VERSION` / `CHANGELOG.md`（版本檔） | 自動採 upstream，`.sync-conflicts/` 留對照副本 | 無需動作（本地版本檔必 stale，屬系統性衝突）；如對照副本顯示本地有應保留的內容，屬異常需人工檢視 |
| 其他檔案 | 本地原檔保留，衝突合併結果存 `.sync-conflicts/` | 依下表三選項逐檔決策 |

非版本檔衝突的三選項：

| 選項 | 適用情境 | 操作 |
|------|---------|------|
| 採 local（保留現狀） | 本地修改是本專案特化（如專案專屬防護） | 不動本地檔；考慮將該檔加入 `sync-preserve.yaml` 避免下次再衝突 |
| 採 upstream | 本地修改已過時或上游版本更完整 | 從 `.sync-conflicts/` 對照後，以上游內容覆蓋本地檔 |
| 手動合併 | 雙方修改都有價值 | 開啟 `.sync-conflicts/` 中含衝突標記的合併結果，手動整合後寫回本地檔 |

### 3. 衝突標記歸零驗證

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
