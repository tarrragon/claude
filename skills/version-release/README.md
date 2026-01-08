# Version Release Skill

完整的版本發布流程自動化工具。

## 快速開始

### 檢查版本是否準備好發布

```bash
uv run .claude/skills/version-release/scripts/version_release.py check
```

### 預覽發布流程（推薦先執行）

```bash
uv run .claude/skills/version-release/scripts/version_release.py release --dry-run
```

### 執行完整發布

```bash
uv run .claude/skills/version-release/scripts/version_release.py release
```

## 檔案結構

```
version-release/
├── SKILL.md                          # Skill 詳細文件（完整功能說明）
├── README.md                         # 此檔案（快速參考）
├── scripts/
│   └── version_release.py            # 主要腳本（~650 行）
└── templates/
    └── release-checklist.md          # 發布檢查清單範本
```

## 核心功能

### Step 1: Pre-flight 檢查
- ✅ 驗證工作日誌完成度（Phase 0-4）
- ✅ 檢查技術債務處理狀態（詳細掃描 pending TD）
- ✅ 驗證技術債務分類
- ✅ 驗證版本號同步（pubspec.yaml、git、工作日誌）
- ✅ 檢查 git 分支和工作目錄狀態

### Step 2: 文件更新
- ✅ 清理 todolist.md（標記版本為已完成）
- ✅ 更新 CHANGELOG.md（新增版本區塊）
- ✅ 驗證 pubspec.yaml 版本號

### Step 3: Git 操作
- ✅ 提交檔案變更
- ✅ 切換到 main 分支
- ✅ 拉取最新 main
- ✅ 合併 feature 分支（--no-ff）
- ✅ 建立 Tag（v{VERSION}-final）
- ✅ 推送到遠端
- ✅ 清理 feature 分支

## 子命令

### `release` - 完整發布流程

```bash
uv run .claude/skills/version-release/scripts/version_release.py release [options]

Options:
  --version TEXT    版本號 (X.Y 或 X.Y.Z)
  --dry-run        預覽模式，不執行實際 git 操作
  --force          強制執行，跳過某些檢查
  --defer-td TEXT  將待處理 TD 延後到指定版本 (例如 0.21.0)
```

**範例**:
```bash
# 自動偵測並發布
uv run .claude/skills/version-release/scripts/version_release.py release

# 預覽發布流程
uv run .claude/skills/version-release/scripts/version_release.py release --dry-run

# 指定版本並發布
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.19.8

# 延後待處理 TD 並發布
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5 --defer-td 0.21.0

# 預覽 TD 延後結果
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5 --defer-td 0.21.0 --dry-run
```

### `check` - 只執行檢查

```bash
uv run .claude/skills/version-release/scripts/version_release.py check [--version X.Y]

# 檢查當前版本
uv run .claude/skills/version-release/scripts/version_release.py check

# 檢查特定版本
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.19
```

### `update-docs` - 只更新文件

```bash
uv run .claude/skills/version-release/scripts/version_release.py update-docs [options]

Options:
  --version TEXT    版本號
  --dry-run        預覽模式
```

## 版本偵測

工具自動偵測版本號順序：

1. `--version` 命令行參數
2. Git 分支名稱 (`feature/vX.Y`)
3. `pubspec.yaml` 中的 `version` 字段
4. 最新 Git tag

## 前置條件

- 完成 Phase 4 重構評估
- 所有工作日誌已記錄
- 技術債務已分類和標記版本
- 在 `feature/v{VERSION}` 分支上
- 所有變更已提交

## 技術債務檢查機制

### 自動掃描流程

發布時，工具會自動掃描版本目錄下的所有技術債務票（`*-TD-*.md` 檔案），檢查：

1. **待處理狀態**: `status: pending` 且 `version` 欄位等於當前版本系列
2. **詳細報告**: 列出所有待處理 TD 的 ticket_id、目標描述和狀態
3. **修復建議**: 提供兩種解決方式

### 兩種解決方式

#### 方式 1: 立即處理 TD
```bash
# 1. 處理所有待處理的技術債務
#    根據提示在 TD 票中填充實作日誌

# 2. 執行發布
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5
```

#### 方式 2: 延後 TD 到下一版本
```bash
# 使用 --defer-td 選項明確延後 TD
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.20.5 --defer-td 0.21.0

# 此命令會：
# 1. 更新所有 pending TD 的 version 欄位為 0.21.0
# 2. 設定 deferred_from 欄位為 0.20.0
# 3. 記錄 defer_reason（延後原因）
# 4. 繼續完整發布流程
```

### 技術債務檔案結構

```yaml
---
ticket_id: 0.20.0-TD-001
version: 0.21.0              # 目標版本
deferred_from: 0.20.0        # 延後自哪個版本
defer_reason: "說明延後原因"   # 延後原因
status: pending              # pending / in-progress / completed
---
```

### 最佳實踐

1. **優先處理**: 盡量在發布前處理待處理的 TD
2. **必要延後**: 若無法在當前版本處理，使用 `--defer-td` 明確標記
3. **定期追蹤**: 利用 defer_reason 記錄延後原因，定期檢查已延後的 TD

## 使用流程

1. **確認所有 Phase 完成**
   ```bash
   # 確認工作日誌中所有 Phase 都標記為 ✅
   cat docs/work-logs/v0.XX.0-main.md
   ```

2. **檢查發布準備度**
   ```bash
   uv run .claude/skills/version-release/scripts/version_release.py check
   ```

3. **預覽發布流程**
   ```bash
   uv run .claude/skills/version-release/scripts/version_release.py release --dry-run
   ```

4. **執行發布**
   ```bash
   uv run .claude/skills/version-release/scripts/version_release.py release
   ```

5. **驗證發布結果**
   ```bash
   # 檢查 Git 狀態
   git log --oneline -5
   git tag -l | tail -5
   ```

## 常見問題

### Q: 如何查看完整的功能說明？
A: 查看 `SKILL.md` 文件，包含所有功能詳細描述、輸出範例、錯誤處理等。

### Q: 如何使用發布檢查清單？
A: 複製 `templates/release-checklist.md`，填入版本號後按照步驟執行。

### Q: 版本號格式是什麼？
A: 支援 `X.Y` (轉換為 `X.Y.0`) 或 `X.Y.Z` 格式，例如 `0.19` 或 `0.19.8`。

### Q: 如何修復版本檢查失敗？
A: 詳見 SKILL.md 的「錯誤處理和恢復」章節。

## 腳本實作

**語言**: Python 3.10+
**模式**: UV Single-File (PEP 723)
**依賴**: pyyaml

**主要類別/函式**:
- `detect_version()` - 自動版本偵測
- `normalize_version()` - 版本號規範化
- `preflight_check()` - Pre-flight 檢查
- `update_documents()` - 文件更新
- `git_merge_and_push()` - Git 操作
- `print_*()` - 彩色化輸出

**大小**: ~650 行代碼

## 相關檔案

- `docs/todolist.md` - 版本狀態和技術債務追蹤
- `CHANGELOG.md` - 版本變動記錄
- `pubspec.yaml` - 應用程式版本號
- `docs/work-logs/` - 所有 Phase 工作日誌

## 技術細節

### 三步驟發布流程

```
Step 1: Pre-flight Check
  ├─ 檢查 Worklog 完成度
  ├─ 檢查技術債務狀態
  └─ 檢查版本同步

Step 2: Document Updates
  ├─ 更新 todolist.md
  ├─ 更新 CHANGELOG.md
  └─ 驗證 pubspec.yaml

Step 3: Git Operations
  ├─ 提交變更
  ├─ 切換到 main
  ├─ 拉取最新
  ├─ 合併 feature
  ├─ 建立 Tag
  ├─ 推送遠端
  └─ 清理分支
```

### 彩色化輸出

工具使用 ANSI 顏色碼提供清晰的執行狀態：
- 🟢 綠色: 成功
- 🔴 紅色: 錯誤
- 🟡 黃色: 警告
- 🔵 藍色: 資訊

## 版本 & 維護

**版本**: v1.0
**建立日期**: 2026-01-06
**維護責任**: basil-hook-architect
**所屬代理人**: basil-hook-architect

## 延伸閱讀

- [`SKILL.md`](./SKILL.md) - 完整功能文件
- [`templates/release-checklist.md`](./templates/release-checklist.md) - 發布檢查清單
- [`scripts/version_release.py`](./scripts/version_release.py) - 完整原始碼

---

**快速提示**: 先執行 `check` 檢查，再執行 `release --dry-run` 預覽，最後執行 `release` 完成發布。
