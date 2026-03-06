# .claude 資料夾同步機制

## 概述

本文件是同步機制技術文件，說明 `.claude` 資料夾的同步設計原理、操作方式和衝突處理。新專案首次設置請參考 [README.md](./README.md)。

本專案使用同步腳本管理 `.claude` 資料夾，實現跨專案配置共享。

- **本地管理**: `.claude` 是實體目錄，納入主專案 Git 版本控制
- **獨立 Repo**: https://github.com/tarrragon/claude.git
- **同步方式**: 雙向同步（推送和拉取）
- **同步範圍**: `.claude/` 目錄（FLUTTER.md 位於 `.claude/project-templates/` 中，隨 rsync 自動包含）

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

### settings.local.json 管理

- **包含在獨立 repo** - 完整推送
- **其他專案需調整** - 根據專案需求修改權限配置

### 衝突處理

如果推送或拉取時出現衝突：

1. **備份本地變更**
2. **手動解決衝突**
3. **測試 Hook 系統**
4. **再次推送/拉取**

## 相關連結

- 獨立 Repo: https://github.com/tarrragon/claude.git

## 最佳實踐

1. **定期同步** - 有重大變更時推送到獨立 repo
2. **測試驗證** - 同步後測試 Hook 系統是否正常
3. **文件更新** - 同步配置變更時更新此 README
4. **版本管理** - 獨立 repo 使用語意化版本號（自動遞增）

---

**Last Updated**: 2026-03-04
**Version**: 2.0.0 - 定位為同步機制技術文件，首次設置引導移至 README.md
