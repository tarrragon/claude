---
name: version-release
description: "版本發布整合工具。Use for: (1) 發布新版本（合併到 main、打 Tag、推送）, (2) 發布前健康檢查（所有 Ticket 完成？CHANGELOG 更新？）, (3) 更新版本文件（worklog 狀態、CHANGELOG）。Use when: 準備發布版本、執行 /version-release check 確認發布前狀態、完成所有 Ticket 後要收尾時。"
---

# Version Release Skill

版本發布整合工具，處理完整的版本發布流程。結合工作日誌檢查、CHANGELOG 更新、Git 操作（合併、Tag、推送、清理）。

## 核心功能

**目的**: 自動化版本發布流程，確保所有檢查通過後再進行 Git 操作

**工作流程**:

1. **Pre-flight 檢查** - 驗證 worklog 完成度、技術債務狀態、版本同步
2. **文件更新** - 清理 todolist、更新 CHANGELOG、確認版本號
3. **Git 操作** - 合併、建立 Tag、推送、清理分支

## 三步驟發布流程

### Step 1: Pre-flight 檢查

驗證發布前置條件是否滿足：

```python
def preflight_check(version: str):
    """
    1.1 確認 worklog 目標達成
        - 掃描 docs/work-logs/v{VERSION}*.md
        - 檢查主工作日誌中的 Phase 是否都標記完成 (✅)
        - 驗證 Phase 0-4 都已執行並記錄

    1.2 檢查技術債務狀態
        - 讀取 todolist.yaml 的「技術債務追蹤」區塊
        - 確認當前版本的 TD 是否都已處理或延遲到下一版本
        - 驗證沒有未分類的 TD

    1.3 版本同步檢查
        - pubspec.yaml 版本 vs worklog 版本一致
        - 當前分支是否為 feature/v{VERSION}
        - 工作目錄是否乾淨（沒有未提交的修改）

    1.4 檔案存在檢查
        - CHANGELOG.md 存在
        - 主工作日誌存在 (v{VERSION}.0-main.md)
        - todolist.yaml 存在
    """
```

**檢查項目**:

- ✅ 所有 Phase 工作日誌已完成
- ✅ 技術債務已分類和處理
- ✅ 版本號在所有地方一致
- ✅ 當前分支正確
- ✅ 工作目錄乾淨

### Step 2: 文件更新

更新 CHANGELOG、todolist 等文件：

```python
def update_documents(version: str):
    """
    2.1 清理 todolist.yaml
        - 找出當前版本系列在任務表格中的行
        - 標記該版本為已完成
        - 更新版本狀態表格的 「開發狀態」 列
        - 格式: ✅ Phase 3b 完成 → ✅ 已完成

    2.2 更新 CHANGELOG.md（Keep a Changelog 格式）
        - 讀取工作日誌提取功能變動
        - 生成版本區塊: ## [X.Y.Z] - YYYY-MM-DD
        - 分類: Added, Changed, Fixed, Removed
        - 複製到 CHANGELOG.md 頂部（在其他版本之前）

    2.3 確認 pubspec.yaml 版本號正確
        - 驗證 version: X.Y.Z 行存在
        - 與 worklog 版本號一致
    """
```

**更新檔案**:

- `docs/todolist.yaml` - 標記版本為已完成
- `CHANGELOG.md` - 新增版本變動記錄
- `pubspec.yaml` - 驗證版本號

### Step 3: Git 操作

執行 Git 相關操作：

```python
def git_merge_and_push(version: str, dry_run: bool = False):
    """
    3.1 提交所有變更（如果有未提交的）
        git add docs/todolist.yaml CHANGELOG.md
        git commit -m "docs: 版本 {version} 發布準備"

    3.2 切換到 main 分支
        git checkout main

    3.3 git pull origin main（確保最新）
        git pull origin main

    3.4 合併 feature 分支（--no-ff 保留合併記錄）
        git merge feature/v{VERSION} --no-ff -m "Merge v{VERSION}"

    3.5 建立 Tag（v{VERSION}-final，如 v0.19-final）
        git tag v{VERSION}-final
        git tag -a v{VERSION}-final -m "Release v{VERSION}"

    3.6 推送到遠端（包含 tag）
        git push origin main
        git push origin v{VERSION}-final

    3.7 刪除本地和遠端 feature 分支
        git branch -d feature/v{VERSION}
        git push origin --delete feature/v{VERSION}
    """
```

**Git 操作順序**:

1. 提交檔案變更
2. 切換到 main 分支
3. 拉取最新 main
4. 合併 feature 分支（保留合併記錄）
5. 建立 Tag
6. 推送 main + Tag
7. 刪除本地/遠端 feature 分支

## CLI 介面設計

### 主要使用方式

```bash
# 自動偵測當前版本
uv run .claude/skills/version-release/scripts/version_release.py release

# 指定版本
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.19

# 預覽模式（不實際執行 git 操作）
uv run .claude/skills/version-release/scripts/version_release.py release --dry-run

# 只執行檢查
uv run .claude/skills/version-release/scripts/version_release.py check

# 只更新文件
uv run .claude/skills/version-release/scripts/version_release.py update-docs
```

### 子命令說明

| 子命令 | 說明 | 範例 |
|--------|------|------|
| `release` | 完整發布流程 | `release --version 0.19 --dry-run` |
| `check` | 只執行 Pre-flight 檢查 | `check --version 0.19` |
| `update-docs` | 只更新文件 | `update-docs --dry-run` |

**release Options**: `--version TEXT`（版本號）、`--dry-run`（預覽模式）、`--force`（跳過檢查，不推薦）

## 版本偵測

偵測優先順序：`--version 參數` -> `git branch (feature/vX.Y)` -> `pubspec.yaml` -> `git tag`

支援格式：完整版本（`0.19.8`）、中版本（`0.19`，自動加 .0）、自動偵測（不指定）。

詳細說明和輸出範例：`references/cli-output-examples.md`

## 前置條件

- **系統要求**: Python 3.10+、Git 2.0+
- **Python 依賴**: `pyyaml`（YAML 解析）、`click`（CLI 框架，可選）
- 完成 Phase 4 重構評估，所有工作日誌已記錄
- 技術債務已分類，在 `feature/v{VERSION}` 分支上
- `pubspec.yaml` 版本號已更新

## 錯誤排除

常見問題和恢復指引：`references/troubleshooting.md`

## 相關資源

- **前置 Skill**: `tech-debt-capture`（Phase 4 技術債務提取）
- **後置操作**: GitHub Release 建立（手動）、版本公告發佈（手動）
- **相關文件**: `docs/todolist.yaml`、`CHANGELOG.md`、`pubspec.yaml`、`docs/work-logs/`
- **錯誤排除**: `references/troubleshooting.md`
- **輸出範例**: `references/cli-output-examples.md`

## 使用流程檢查清單

- [ ] 所有 Phase 工作日誌已完成
- [ ] Phase 0-4 都標記為 ✅
- [ ] 技術債務已分類到 todolist.yaml
- [ ] 運行 `check` 確認所有檢查通過
- [ ] 運行 `release --dry-run` 預覽
- [ ] 運行 `release` 完成發布
- [ ] 驗證 main 分支已更新
- [ ] 驗證 Tag 已建立
- [ ] 確認 feature 分支已清理
