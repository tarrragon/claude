# IMP-017: 全局安裝 CLI 工具未隨原始碼修復同步

## 分類

| 項目 | 值 |
|------|-----|
| 編號 | IMP-017 |
| 類別 | implementation |
| 風險等級 | 中 |
| 首次發現 | 2026-03-06 |
| 來源 Ticket | 0.1.0-W1-018, 0.1.0-W1-019 |

## 症狀

- CLI 工具（如 `ticket track query`）執行失敗，報「找不到 Ticket」
- 同一指令用 `uv run ticket` 執行卻正常
- `ticket track list` 正常但 `ticket track query` 失敗（list 和 query 的搜尋邏輯不同版本）
- 修復已寫入原始碼並通過測試，但問題持續存在

## 根因

使用 `uv tool install .` 全局安裝的 CLI 工具，其執行檔是安裝時的快照副本。原始碼修改後（如 W1-019 修復 stale 過濾邏輯），**全局安裝的版本不會自動更新**，必須重新執行 `uv tool install . --force` 才能同步。

**行為模式**：

```
原始碼修復 → 測試通過（uv run 環境） → commit
                                         ↓
全局 CLI 仍為舊版 → 用戶使用 ticket 指令 → 舊邏輯執行 → 問題持續
```

**混淆因素**：
- `ticket track list` 使用全量掃描邏輯，不依賴修復的函式 → 正常
- `ticket track query` 使用精確查找邏輯，依賴修復的函式 → 失敗
- 兩個指令行為不一致，容易誤判為新 bug

## 解決方案

修復原始碼後，必須重新安裝全局 CLI：

```bash
(cd .claude/skills/ticket && uv tool install . --force)
```

## 預防措施

### 已有防護

- `package-version-sync-hook.py`（SessionStart Hook）會在 session 啟動時檢查套件版本是否需要重新安裝
- `ticket-reinstall-hook.py` 會偵測 ticket 原始碼變更並自動重新安裝

### 建議加強

1. **commit 後自動重新安裝**：在 PostToolUse Hook（git commit）中偵測 `.claude/skills/ticket/` 目錄下的變更，自動觸發 `uv tool install . --force`
2. **版本號機制**：在 `pyproject.toml` 中維護版本號，全局安裝後可透過 `ticket --version` 比對是否為最新

## 檢查清單

修改 `.claude/skills/ticket/` 下的 Python 程式碼後：

- [ ] 測試通過（`uv run pytest`）
- [ ] 重新安裝全局 CLI（`uv tool install . --force`）
- [ ] 驗證全局 CLI 行為正確（`ticket track query <id>`）

## 相關錯誤模式

- IMP-016: Lockfile stale after config change（類似的「修改未生效」模式）
- ARCH-007: Per-project tracking global resource（全局 vs 專案資源追蹤）
