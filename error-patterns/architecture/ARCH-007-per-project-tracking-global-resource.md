# ARCH-007: Per-project 追蹤檔追蹤全域資源

## 基本資訊

- **Pattern ID**: ARCH-007
- **分類**: 架構設計
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-05
- **風險等級**: 中

## 問題描述

### 症狀

- `package-version-sync-hook` 每次 SessionStart 輸出「No packages configured」
- `sync-pull` 拉取新程式碼後，已安裝的全域 CLI 工具不會自動更新
- 跨專案使用相同 `.claude/` 配置時，A 專案更新不影響 B 專案的追蹤狀態

### 根本原因 (5 Why 分析)

1. Why 1: `installed-packages.json` 不存在，Hook 無法追蹤套件
2. Why 2: 沒有自動建立此檔案的機制（首次 `uv tool install` 時不會產生）
3. Why 3: 追蹤檔設計為 per-project（`.claude/installed-packages.json`）
4. Why 4: 但被追蹤的資源是全域的（`uv tool install` 安裝到系統級）
5. Why 5: **追蹤機制的作用域與被追蹤資源的作用域不匹配**

### 行為模式

設計追蹤/快取/狀態檔案時，容易將檔案放在「方便存取的位置」（專案目錄）而非「語義正確的位置」（與資源相同的作用域）。

## 解決方案

### 正確做法

追蹤/偵測機制的作用域應與被追蹤資源一致：

| 被追蹤資源作用域 | 追蹤機制作用域 | 範例 |
|----------------|--------------|------|
| 全域（系統級） | 全域或即時查詢 | `uv tool list`（即時查詢） |
| Per-project | Per-project | `.dart_tool/` |
| Per-user | Per-user | `~/.claude/settings.json` |

### 推薦模式

對於全域資源，優先使用「即時查詢實際狀態」而非「追蹤檔記錄狀態」：

```python
# 錯誤：用 per-project 檔案追蹤全域工具
tracking_file = project_root / ".claude" / "installed-packages.json"
packages = load_tracking_file(tracking_file)

# 正確：即時查詢 + 自動掃描
desired = scan_skill_packages(project_root)  # 掃描 pyproject.toml
installed = get_installed_uv_tools()          # 查詢 uv tool list
for pkg, info in desired.items():
    if installed.get(pkg) != info["version"]:
        reinstall(pkg)
```

## 預防措施

### 設計時檢查清單

新增任何追蹤/快取/狀態檔案時，必須回答：

- [ ] 被追蹤的資源是什麼作用域？（全域 / per-user / per-project）
- [ ] 追蹤檔放在什麼作用域？（必須與資源匹配）
- [ ] 能否用即時查詢取代追蹤檔？（全域資源優先即時查詢）
- [ ] 跨專案使用時追蹤檔是否會不一致？

### 相關規則

- `.claude/rules/core/quality-common.md` 第 1.2.3 節（破壞性操作設計防護）中的「狀態語義一致性」原則同樣適用

## 關聯 Ticket

- 0.1.0-W1-017：重新設計套件追蹤機制（installed-packages.json → 自動掃描 + 實際狀態比對）
- 與 ARCH-006 相關：同為「配置/追蹤放錯作用域」的模式

---

**Last Updated**: 2026-03-05
