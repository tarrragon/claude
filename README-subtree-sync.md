# .claude 資料夾 Git Subtree 同步機制

## 📋 概述

本專案使用 **Git Subtree** 機制管理 `.claude` 資料夾，實現跨專案配置共享。

- **本地管理**: `.claude` 是實體目錄，納入主專案 Git 版本控制
- **獨立 Repo**: https://github.com/tarrragon/claude.git
- **同步方式**: 雙向同步（推送和拉取）

## 🎯 設計原理

### 為什麼使用這個同步方案？

1. **實體目錄** - `.claude` 在專案中是真實的目錄，Hook 系統可正常運作
2. **獨立版本控制** - `.claude` 可推送到獨立 repo 供多專案共享
3. **簡單推送** - 使用臨時 repo + force push 避免複雜的 Git 歷史問題
4. **安全拉取** - 自動備份當前配置，拉取失敗可輕鬆還原

### 為什麼不用標準 Git Subtree？

原始設計使用 `git subtree`，但因專案歷史複雜（.claude 曾為符號連結），導致 `git subtree push/pull` 失敗。

當前方案改用：
- **推送**：臨時 repo + force push（簡單可靠）
- **拉取**：clone + 檔案複製（安全且有備份）

### 與其他方案的比較

| 特性 | 當前方案 | Git Submodule | 標準 Git Subtree |
|-----|---------|---------------|-----------------|
| 目錄類型 | ✅ 實體目錄 | 符號連結 | 實體目錄 |
| Hook 系統 | ✅ 正常運作 | ⚠️ 需特殊配置 | ✅ 正常運作 |
| 推送方式 | 臨時 repo | 自動追蹤 | subtree push |
| 拉取方式 | clone + 複製 | 自動追蹤 | subtree pull |
| 歷史處理 | ⚠️ 不保留歷史 | ✅ 完整歷史 | ⚠️ 可能失敗 |
| 管理複雜度 | ✅ 低 | 高 | 中 |

## 🚀 使用方式

### 推送本地變更到獨立 Repo

當你在本專案修改了 `.claude` 資料夾的內容，想同步到獨立 repo：

```bash
# 1. 先提交變更到主專案
git add .claude CLAUDE.md FLUTTER.md
git commit -m "feat: 更新 .claude 配置"

# 2. 推送到獨立 repo
./scripts/sync-claude-push.sh "更新說明"
```

### 從獨立 Repo 拉取更新

當獨立 repo 有新的變更，想同步到本專案：

```bash
# 拉取最新配置
./scripts/sync-claude-pull.sh
```

**注意**：拉取會自動合併變更，如有衝突需手動解決。

## 🔧 其他專案如何使用

### 方案 A: 首次設置（新專案）

```bash
# 1. 進入專案目錄
cd your-project

# 2. 添加 claude-shared remote
git remote add claude-shared https://github.com/tarrragon/claude.git

# 3. 使用 subtree 拉取 .claude 資料夾
git subtree add --prefix=.claude claude-shared main --squash

# 4. 複製腳本（可選）
mkdir -p scripts
cp /path/to/book_overview_app/scripts/sync-claude-*.sh scripts/

# 5. 根據專案需求調整 settings.local.json
vim .claude/settings.local.json
```

### 方案 B: 定期更新配置

```bash
# 拉取最新配置
git subtree pull --prefix=.claude claude-shared main --squash
```

## 📁 目錄結構

```text
book_overview_app/
├── .claude/                  # 實體目錄（由 subtree 管理）
│   ├── hooks/               # Hook 腳本
│   ├── agents/              # Agent 配置
│   ├── methodologies/       # 方法論文件
│   └── settings.local.json  # 專案特定配置
├── CLAUDE.md                # 主配置文件
├── FLUTTER.md               # Flutter 特定配置
└── scripts/
    ├── sync-claude-push.sh  # 推送腳本
    └── sync-claude-pull.sh  # 拉取腳本
```

## ⚠️ 注意事項

### settings.local.json 管理

- **包含在獨立 repo** - 完整推送
- **其他專案需調整** - 根據專案需求修改權限配置

### 衝突處理

如果推送或拉取時出現衝突：

1. **備份本地變更**
2. **手動解決衝突**
3. **測試 Hook 系統**
4. **再次推送/拉取**

### Git Subtree 原理

Subtree 會：
- 保留完整 commit 歷史
- 將獨立 repo 的內容合併到主專案
- 推送時只推送 `.claude` 目錄的變更

## 🔗 相關連結

- 獨立 Repo: https://github.com/tarrragon/claude.git
- Git Subtree 官方文件: https://git-scm.com/docs/git-subtree

## 📝 最佳實踐

1. **定期同步** - 有重大變更時推送到獨立 repo
2. **測試驗證** - 同步後測試 Hook 系統是否正常
3. **文件更新** - 同步配置變更時更新此 README
4. **版本管理** - 獨立 repo 使用語意化版本號（可選）
