# ARCH-002: Plugin 清理不完整導致反覆復發

## 基本資訊

- **Pattern ID**: ARCH-002
- **分類**: 架構/環境配置
- **來源版本**: v0.27.0 ~ v0.31.1
- **發現日期**: 2026-02-24
- **最後更新**: 2026-02-24（第四次：stub plugin 導致 startup error）
- **風險等級**: 中

## 問題描述

### 症狀

移除的 Claude Code plugin 在每次啟動 session 時自動重新安裝，導致 SessionStart hook error 反覆出現。歷經 8 次清理才完全根除。

具體錯誤：
```
SessionStart:startup hook error
```

mgrep plugin 的 `mgrep_watch.py:35` 對 None payload 呼叫 `.get()` 觸發 `AttributeError`，且 mgrep CLI 未安裝。

### 根本原因 (5 Why 分析)

1. Why 1: 啟動時出現 SessionStart hook error
2. Why 2: mgrep plugin 的 hook 嘗試執行，但 payload 為 None 且 mgrep CLI 不存在
3. Why 3: mgrep marketplace 目錄已被刪除但每次啟動都自動重新 clone
4. Why 4: 清理只刪除了部分註冊源（enabledPlugins、installed_plugins.json、cache、marketplace 目錄）
5. Why 5: **`~/.claude/plugins/known_marketplaces.json` 中仍有 marketplace 的 git repo 註冊記錄，Claude Code 定期根據此檔重新 clone 整個 marketplace repo**

### 雙重自動重裝機制

Plugin 系統有**兩個獨立的自動重裝觸發源**：

| 觸發源 | 檔案 | 作用 | 觸發時機 |
|--------|------|------|---------|
| Plugin 訂閱 | `settings.json` enabledPlugins | 確保 plugin 安裝 | 每次啟動 |
| Marketplace 訂閱 | `known_marketplaces.json` | 維護 marketplace repo clone | 定期更新 |

兩者必須同時清理，否則任一存在都會導致復發。

## 解決方案

### 正確做法

**第一步：優先使用官方 CLI 指令**

```bash
# 官方指令 - 處理 enabledPlugins + installed_plugins.json + cache
claude plugin uninstall {plugin_name}
claude plugin uninstall {plugin}@{marketplace} --scope user
```

**第二步：清理 known_marketplaces.json（官方指令不處理）**

```bash
# 檢查是否有殘留的 marketplace 註冊
cat ~/.claude/plugins/known_marketplaces.json

# 移除不需要的 marketplace 條目（用 Python json 操作）
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/plugins/known_marketplaces.json')
with open(path) as f:
    data = json.load(f)
data.pop('target_marketplace_name', None)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
"
```

**第三步：驗證是否成功**

```bash
# 確認 plugin 不在列表中
claude plugin list --json

# 確認無殘留（五個位置全檢查）
grep -l "target" ~/.claude/settings.json                    # 1. enabledPlugins
grep -l "target" ~/.claude/plugins/installed_plugins.json   # 2. 安裝記錄
grep -l "target" ~/.claude/plugins/known_marketplaces.json  # 3. Marketplace 訂閱
find ~/.claude/plugins/cache -name "*target*"               # 4. 快取目錄
find ~/.claude/plugins/marketplaces -name "*target*"        # 5. Marketplace 目錄
```

**官方指令失敗時的完整手動 Fallback**

官方 `uninstall` 依賴 `installed_plugins.json` 中的記錄。若之前已手動清理過，uninstall 會靜默失敗。此時按以下順序手動清理：

```bash
# 按優先級清理（5 層全覆蓋）
# 1. settings.json enabledPlugins（Plugin 自動重裝觸發源）
# 2. known_marketplaces.json（Marketplace repo 自動 re-clone 觸發源）
# 3. installed_plugins.json（安裝記錄）
# 4. cache/ 目錄（Plugin 快取）
# 5. marketplaces/ 目錄（Marketplace repo clone）
# 6. /tmp/ 臨時檔案
```

### 完整根除清單（Checklist）

移除 plugin 後必須確認以下 5 層全部清理：

| 順序 | 清理項目 | 路徑 | 不清理的後果 |
|------|---------|------|-------------|
| 1 | enabledPlugins | `~/.claude/settings.json` | Plugin 每次啟動自動重裝 |
| 2 | known_marketplaces | `~/.claude/plugins/known_marketplaces.json` | Marketplace repo 定期被重新 clone |
| 3 | installed_plugins | `~/.claude/plugins/installed_plugins.json` | 安裝記錄殘留 |
| 4 | cache 目錄 | `~/.claude/plugins/cache/{publisher}/` | Hook 從快取載入 |
| 5 | marketplace 目錄 | `~/.claude/plugins/marketplaces/{publisher}/` | Hook 從 marketplace 載入 |

### 錯誤做法 (避免)

| 錯誤做法 | 問題 |
|---------|------|
| 只刪目錄不刪註冊記錄 | 兩個觸發源（enabledPlugins、known_marketplaces）會自動重建 |
| 只刪 enabledPlugins 不刪 known_marketplaces | Marketplace repo 仍會被重新 clone |
| 只刪 known_marketplaces 不刪 enabledPlugins | Plugin 仍會被自動安裝 |
| 跳過官方 CLI 直接手動刪 | 可能遺漏項目 |
| 手動清理後再跑 `uninstall` | installed_plugins.json 記錄已移除，uninstall 靜默失敗 |

## Claude Code Plugin 雙重自動安裝機制

### 機制一：Plugin 訂閱（enabledPlugins）

```
啟動 Claude Code
    |
    v
讀取 ~/.claude/settings.json
    |
    v
遍歷 enabledPlugins
    |
    +-- plugin 在 installed_plugins.json 中?
    |   +-- 是 -> 載入 hooks
    |   +-- 否 -> 從 registry 下載安裝 -> 載入 hooks
    |
    v
執行所有 SessionStart hooks
```

### 機制二：Marketplace 訂閱（known_marketplaces.json）

```
啟動 Claude Code / 定期更新
    |
    v
讀取 ~/.claude/plugins/known_marketplaces.json
    |
    v
遍歷所有已註冊的 marketplace
    |
    +-- marketplace 目錄存在?
    |   +-- 是 -> 檢查是否需要更新（git pull）
    |   +-- 否 -> 重新 clone 整個 repo
    |
    v
掃描 marketplaces/ 下所有 hooks.json -> 載入並執行
```

**關鍵洞察**：
- `enabledPlugins` 控制個別 plugin 的安裝
- `known_marketplaces.json` 控制整個 marketplace repo 的 clone
- Marketplace repo 包含所有 plugin，clone 後不需要的 plugin 也會被掃描到
- 兩個機制**互相獨立**，必須同時清理

## Plugin Hook 載入路徑

Claude Code 從兩處載入 plugin hooks：

| 路徑 | 來源 | 說明 |
|------|------|------|
| `~/.claude/plugins/cache/{publisher}/{plugin}/{version}/hooks/` | enabledPlugins | 安裝快取 |
| `~/.claude/plugins/marketplaces/{publisher}/plugins/{plugin}/hooks/` | known_marketplaces | Marketplace 掃描 |

兩處同時存在時，hook 會被觸發**兩次**。

## 相關資源

- `~/.claude/settings.json` - plugin 訂閱設定（enabledPlugins）
- `~/.claude/plugins/known_marketplaces.json` - marketplace repo 訂閱設定
- `~/.claude/plugins/installed_plugins.json` - 安裝記錄
- `~/.claude/plugins/cache/` - plugin 快取目錄
- `~/.claude/plugins/marketplaces/` - marketplace 來源目錄

## 歷史清理記錄摘要

| 次數 | 清理項目 | 結果 | 遺漏 |
|------|---------|------|------|
| 1-5 | cache、installed_plugins.json、/tmp | 失敗 | enabledPlugins |
| 6 | + enabledPlugins | 部分成功 | marketplace 目錄 |
| 7 | + marketplace 目錄 | 暫時成功 | known_marketplaces.json |
| 8 | + known_marketplaces.json | 完全根除 | 無 |
| 9 | pyright-lsp: enabledPlugins + installed_plugins + cache | 完全根除 | 無（第四次） |

### 第四次：Stub Plugin 導致 Startup Error（2026-02-24）

- **症狀**：`SessionStart:startup hook error` 一行錯誤，無詳細資訊
- **根因**：`pyright-lsp@claude-plugins-official` 已啟用但 cache 中只有 README.md（無 plugin.json、無 .lsp.json、無 hooks）
- **背景**：官方 `claude-plugins-official` repo 中所有 11 個 LSP plugin 都是 stub（僅 README + LICENSE）。LSP 設定原本放在 marketplace.json inline，但 Claude Code 安裝時不提取此設定（GitHub Issue #379, #40 確認）
- **修復**：從 enabledPlugins 移除 + installed_plugins.json 刪除條目 + 刪除 cache 目錄
- **新教訓**：安裝 plugin 前應確認 cache 目錄包含 `plugin.json`（`.claude-plugin/plugin.json`），若只有 README 則為未完成的 stub

**關鍵教訓**：
1. Plugin 系統有 5 層清理項目，漏掉任何一層都會導致復發
2. 官方 `claude plugin uninstall` 不處理 `known_marketplaces.json`，需手動清理
3. Marketplace 是整個 repo 共享的，更新任一 plugin 會重新 clone 整個 repo（含不需要的子目錄）
4. **啟用 stub plugin（只有 README 無 plugin.json）會導致 startup error**，安裝前應用 `find ~/.claude/plugins/cache -mindepth 3 -maxdepth 3 -not -exec test -e {}/.claude-plugin/plugin.json \; -print` 檢查

## 標籤

`#plugin` `#環境配置` `#自動重裝` `#enabledPlugins` `#known_marketplaces` `#mgrep` `#stub-plugin` `#pyright-lsp`
