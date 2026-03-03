# Version Release 錯誤排除指引

## 常見問題

| 問題             | 原因            | 解決方式                                |
| ---------------- | --------------- | --------------------------------------- |
| 版本偵測失敗     | 分支名稱不符    | 確認在 `feature/vX.Y` 分支上            |
| Worklog 檢查失敗 | Phase 未完成    | 完成所有 Phase 工作日誌                 |
| 技術債務未分類   | TD 沒有版本標記 | 更新 todolist.yaml 技術債務表格         |
| Git 操作失敗     | 遠端衝突或權限  | 檢查 git status，解決衝突後重試         |
| 文件更新失敗     | 檔案格式變化    | 檢查 CHANGELOG.md 或 todolist.yaml 格式 |

## 恢復指引

### VersionDetectionError: Unable to detect version

```bash
# 1. 確認當前分支
git branch

# 2. 確保在 feature/vX.Y 分支
git checkout feature/v0.19

# 3. 或明確指定版本
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.19
```

### WorklogError: Phase X not completed

```bash
# 1. 檢查工作日誌檔案
cat docs/work-logs/v0.19.4-phase3b-implementation.md

# 2. 確認 Phase 標記為完成
# 3. 更新 Phase 狀態
# 4. 重新執行檢查

uv run .claude/skills/version-release/scripts/version_release.py check
```

### Git 合併失敗

```bash
# 1. 檢查 git 狀態
git status

# 2. 解決衝突
# 3. 繼續合併或中止
git merge --abort

# 4. 重新執行發布流程
uv run .claude/skills/version-release/scripts/version_release.py release
```

## 版本偵測邏輯

工具使用以下策略自動偵測版本號：

1. **命令行參數優先** - 如果指定 `--version`，使用該版本
2. **git 分支名稱** - 從 `feature/v{VERSION}` 提取版本
3. **pubspec.yaml** - 讀取 `version: X.Y.Z` 行
4. **git 標籤** - 查詢最新的版本標籤

偵測流程：`--version 參數 -> git branch (feature/vX.Y) -> pubspec.yaml -> git tag`

## 支援的版本格式

| 格式     | 範例     | 說明                    |
| -------- | -------- | ----------------------- |
| 完整版本 | `0.19.8` | 三段版本號              |
| 中版本   | `0.19`   | 二段版本號（自動加 .0） |
| 當前版本 | 不指定   | 自動偵測                |

範例：

```bash
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.19
# -> 自動轉換為 0.19.0（或查詢最新的 0.19.x）

uv run .claude/skills/version-release/scripts/version_release.py release --version 0.19.8
# -> 使用 0.19.8

uv run .claude/skills/version-release/scripts/version_release.py release
# -> 自動偵測版本（從 git branch/pubspec.yaml）
```
