# .claude 資料夾同步機制

## 概述

本文件是同步機制技術文件，說明 `.claude` 資料夾的同步設計原理、操作方式和衝突處理。新專案首次設置請參考 [README.md](./README.md)。

> **檔名與實作說明**：本檔名含 `subtree` 字樣為歷史命名，**實際實作並非標準 Git Subtree**，而是「clone 遠端 + 檔案複製（`shutil.copytree`/`copy2`）」。標準 Git Subtree 的優劣對照見下方[「與其他方案的比較」](#與其他方案的比較)。

本專案使用同步腳本管理 `.claude` 資料夾，實現跨專案配置共享。

- **本地管理**: `.claude` 是實體目錄，納入主專案 Git 版本控制
- **獨立 Repo**: https://github.com/tarrragon/claude.git
- **同步方式**: 雙向同步（推送和拉取），透過 `shutil` 檔案複製（非 rsync、非 git subtree）
- **同步範圍**: `.claude/` 目錄（排除暫存檔與各專案本地設定，詳見[「同步範圍與排除」](#同步範圍與排除)）

## 設計原理

### 為什麼使用這個同步方案？

1. **實體目錄** - `.claude` 在專案中是真實的目錄，Hook 系統可正常運作
2. **獨立版本控制** - `.claude` 可推送到獨立 repo 供多專案共享
3. **歷史保留推送** - Clone 遠端後基於歷史建立新 commit，保留完整演進記錄
4. **安全拉取** - 自動備份當前配置，拉取失敗可輕鬆還原

### 與其他方案的比較

| 特性 | 當前方案 | Git Submodule | 標準 Git Subtree |
|-----|---------|---------------|-----------------|
| 目錄類型 | 實體目錄 | 符號連結 | 實體目錄 |
| Hook 系統 | 正常運作 | 需特殊配置 | 正常運作 |
| 推送方式 | clone + push | 自動追蹤 | subtree push |
| 拉取方式 | clone + 複製 | 自動追蹤 | subtree pull |
| 歷史處理 | 保留歷史 | 完整歷史 | 可能失敗 |
| 管理複雜度 | 低 | 高 | 中 |

> **「當前方案」非標準 Git Subtree**：本機制檔名雖含 `subtree`，實際推送為 `clone + push`、拉取為 `clone + 檔案複製`，並未使用 `git subtree` 指令。表格最右欄「標準 Git Subtree」僅供對照，非本機制行為。

## 同步範圍與排除

push 以 `git archive HEAD -- .claude` 取 git tracked 樹，再依 `should_exclude` 過濾後複製到遠端 staging；pull 以三方合併處理 `.claude/` 內容。排除分類的 SSOT 為 `.claude/hooks/lib/sync_exclude_manifest.py`（`should_exclude` / `LOCAL_ONLY_PATTERNS` / `CREDENTIAL_PATTERNS` 等），push/pull/status 三腳本與 hook 共用，避免漂移（ARCH-020）。

| 項目 | Push（本地 → 遠端） | Pull（遠端 → 本地） | 說明 |
|-----|------|------|------|
| `.claude/` 一般檔案 | 推送 | 拉取覆蓋 | 跨專案共用框架資產 |
| `settings.local.json` | **排除**（`EXCLUDE_PATTERNS`） | **不覆蓋**（`LOCAL_ONLY`） | 各專案個別權限設定，自行管理 |
| `sync-preserve.yaml`、`.sync-state.json` | 排除 | 不覆蓋 | 各專案本地同步狀態 |
| Runtime state（`dispatch-active.json`、`hook-state/` 等） | 排除 | 不覆蓋 | 本 session 狀態，跨專案會污染 |
| Session log（`hook-logs/`、`handoff/` 等） | 排除 | 不覆蓋 | 僅本機有意義 |
| 敏感憑證（`.env*`、`secrets.*`、`.keys` 等） | 排除 | — | 嚴禁推送至公開 repo |
| `project-templates/` | 隨 `.claude/` 推送（含 `FLUTTER.md`） | **主同步迴圈跳過**（`REMOTE_ONLY`），改由特例函式單獨複製 `FLUTTER.md` 到專案根目錄 | 見下方 FLUTTER.md 說明 |

### FLUTTER.md 的特殊處理

`FLUTTER.md` 位於遠端 `project-templates/` 中，**並非「隨主同步自動包含」**：

- **Push**：`project-templates/FLUTTER.md` 作為 `.claude/` 內容一併推送至遠端。
- **Pull**：`project-templates` 列於 `REMOTE_ONLY`，主同步迴圈會**跳過**整個目錄；`FLUTTER.md` 由 `_update_project_templates()` 特例函式單獨從遠端 `project-templates/FLUTTER.md` 複製到專案根目錄，且**不覆蓋根目錄 `CLAUDE.md`**。

## Base Snapshot 三方合併模型

**背景**：早期同步無「base / 共同祖先」概念，push 與 pull 皆為**無狀態全量 overlay**——pull 直接以遠端內容覆蓋本地，push 直接以本地內容覆蓋遠端。此模型無法區分「對方新增」與「我方刪除」，導致跨專案 / 並行修改互相覆蓋（0.19.1-W1-014 統一根因）。

**現行模型**：引入 **base snapshot** 後，push / pull 收斂為帶共同祖先的**三方合併**（base / local / upstream）。

### Base 錨點：`last_synced_base_sha`

| 項目 | 說明 |
|------|------|
| 儲存位置 | 各專案本地 `.sync-state.json` 的 `last_synced_base_sha` 欄位（W1-025 schema） |
| 語意 | 上次成功同步時的上游（遠端 `.claude` repo）HEAD commit SHA，作為下次三方合併的共同祖先（base） |
| 單一欄位約束 | push / pull / status 三腳本共用**單一** `last_synced_base_sha`，**禁雙欄位**（不分 push/pull 各記一個），**禁對 commit SHA 用 `max()`**（commit SHA 非單調可比較）。多視角審查 H1 防護 |
| 同步範圍 | 此欄位列於本地同步狀態，**不推送、不被覆蓋**（屬各專案本地狀態，見上方排除表） |

### Pull 三方合併流程（W1-028）

1. clone 上游（partial clone，見下方）取得完整 commit graph。
2. 驗證本地記錄的 `last_synced_base_sha` 在上游 clone 中**可達為 commit 物件**（H4）；不可達時退回較保守流程。
3. 計算上游 `base → HEAD` 的檔案 delta（`git diff --name-status --no-renames base HEAD`），只處理 A（新增）/ M（修改）/ D（刪除）三種狀態。
4. 對每個變更檔執行三方合併（`git merge-file`，base / local / upstream 三方）：
   - upstream 新增、本地無 → 直接採 upstream。
   - 本地已刪除 → 保留本地刪除（不寫回）。
   - 三方齊備 → 標準三方合併，衝突寫入本地暫存目錄（local-only，不推送）供人工解決。
5. 經 `should_exclude` 過濾 `LOCAL_ONLY` / 憑證檔，避免本地 runtime / 特化檔被遠端覆蓋。
6. 合併結果**原子套用**；成功後將上游 HEAD SHA 寫回 `last_synced_base_sha`。

### Push（git archive，commit-first）（W1-029 / W1-030）

push 端不再 walk 磁碟，改以 `git archive HEAD -- .claude` 取 **git tracked 樹**作為推送來源（C1）。commit-first 行為見下方[「推送本地變更」](#推送本地變更到獨立-repo)的說明區塊。push 成功後將遠端 HEAD SHA 寫回 `last_synced_base_sha`，作為下次同步的 base 錨點。

### Partial Clone（L1：完整 commit graph + 按需 blob）

三方合併需要 base commit 可達（`git diff base HEAD`、`git show base:path`）。**shallow clone 取不到歷史的 base commit**，故 pull / push 改用 **partial clone（`--filter=blob:none`）**：保留完整 commit graph（base commit 可達），blob 按需 lazy fetch。

| 取捨 | 說明 |
|------|------|
| 為何不用 shallow | shallow clone 截斷歷史，base commit 不可達 → 三方合併失效 |
| 為何用 blob:none | 完整 commit graph 保證 base 可達，blob 延遲抓取兼顧速度 |
| timeout | 為容納 full / blob:none clone 的網路時間，clone timeout 放寬至 300s |

## 使用方式

### 推送本地變更到獨立 Repo

當你在本專案修改了 `.claude` 資料夾的內容，想同步到獨立 repo：

```bash
# 1. 先提交變更到主專案
git add .claude
git commit -m "feat: 更新 .claude 配置"

# 2. 推送到獨立 repo
python3 ./.claude/scripts/sync-claude-push.py "更新說明"
```

> **commit-first 強制（必讀）**：push 取的是 git **tracked 樹**（`git archive HEAD -- .claude`），
> **不**從磁碟讀取工作區。因此步驟 1 的 commit 是必要前置——若 `.claude/` 有未 commit
> 或僅 staged 未 commit 的變更，push 會 abort 並要求先 commit（避免推上去的內容與工作區不一致）。
>
> 此設計同時帶來兩個保證：
> - **安全**：untracked / gitignored 檔（含機密檔）不在 tracked 樹中，不可能被推上公開 repo。
> - **刪除傳播**：本地 `git rm` 的檔自然不在 archive，遠端會對應刪除（需搭配 `--clean` 清理遠端殘留）。

### 從獨立 Repo 拉取更新

當獨立 repo 有新的變更，想同步到本專案：

```bash
# 拉取最新配置
python3 ./.claude/scripts/sync-claude-pull.py
```

**注意**：拉取會自動備份當前配置，如有問題可輕鬆還原。

## 其他專案如何使用

新專案的首次設置和定期更新配置，請參考 [README.md](./README.md) 的「其他專案如何使用」章節。

## 目錄結構

```text
project/
├── .claude/                  # 實體目錄（同步管理）
│   ├── hooks/               # Hook 腳本
│   ├── agents/              # Agent 配置
│   ├── methodologies/       # 方法論文件
│   ├── project-templates/   # 專案模板（含 FLUTTER.md）
│   ├── scripts/             # 同步腳本
│   │   ├── sync-claude-push.py   # 推送腳本
│   │   └── sync-claude-pull.py   # 拉取腳本
│   └── settings.local.json  # 專案特定配置
├── CLAUDE.md                # 主配置文件（專案特定，不同步）
```

## 注意事項

### Windows 使用者特別注意

Windows 執行 sync-push 時 git 對新增檔案的 mode 處理與 macOS/Linux 不同（NTFS 無 executable bit 概念）。未遵循建議操作可能導致遠端 repo 的 hook 檔案 mode 損壞，下游 pull 後 hook 無法執行。

詳見：[WINDOWS-NOTES.md](./WINDOWS-NOTES.md)

### settings.local.json 管理

- **不同步** - `settings.local.json` 列於 push 端 `EXCLUDE_PATTERNS` 與 pull 端 `LOCAL_ONLY`，**不會被推送，也不會被遠端覆蓋**。
- **各專案自管** - 屬各專案個別的權限/覆蓋設定，由各專案自行維護，依專案需求調整。

### 衝突處理

如果推送或拉取時出現衝突：

1. **備份本地變更**
2. **手動解決衝突**
3. **測試 Hook 系統**
4. **再次推送/拉取**

## 相關連結

- 獨立 Repo: https://github.com/tarrragon/claude.git
- 排除分類 SSOT: `.claude/hooks/lib/sync_exclude_manifest.py`
- Error-pattern 編號區段約定（影響 `error-patterns/` 跨專案傳播）: `.claude/references/error-pattern-numbering-policy.md`

## 最佳實踐

1. **定期同步** - 有重大變更時推送到獨立 repo
2. **測試驗證** - 同步後測試 Hook 系統是否正常
3. **文件更新** - 同步配置變更時更新此 README
4. **版本管理** - 獨立 repo 使用語意化版本號（自動遞增）

---

**Last Updated**: 2026-06-03
**Version**: 2.1.0 - 新增「Base Snapshot 三方合併模型」章節（base 錨點 last_synced_base_sha、pull 三方合併、push git-archive、partial clone blob:none）；補相關連結指向 sync_exclude_manifest.py 與 error-pattern 編號區段 policy（0.19.1-W1-026，源 W1-018/025/028/029/030）
**Version**: 2.0.0 - 定位為同步機制技術文件，首次設置引導移至 README.md
