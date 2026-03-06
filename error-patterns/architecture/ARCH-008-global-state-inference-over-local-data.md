# ARCH-008: 依賴全域狀態推斷而非從本地資料提取

## 基本資訊

- **Pattern ID**: ARCH-008
- **分類**: 架構設計
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-05
- **風險等級**: 中

## 問題描述

### 症狀

- `ticket track query 0.1.0-W1-017` 回傳「找不到 Ticket」
- `ticket track set-* 0.1.0-W1-017` 同樣失敗
- 但 `ticket track list --version 0.1.0` 正常顯示該 Ticket

### 根本原因 (5 Why 分析)

1. Why 1: 系統在 `v0.3.0` 目錄下尋找 `0.1.0-W1-017.md`，但檔案在 `v0.1.0/` 下
2. Why 2: `require_version(None)` 自動選擇了最高版本 v0.3.0
3. Why 3: `_scan_worklog_directories()` 按版本號降序排列，返回最高版本
4. Why 4: 版本推斷邏輯不考慮輸入的 Ticket ID
5. Why 5: **當本地資料（Ticket ID）已包含足夠資訊時，系統卻依賴全域狀態（「當前版本」）推斷**

### 行為模式

設計 CLI 或 API 時，容易建立一個「全域當前狀態」（如 current version、current branch）作為所有操作的預設值，即使輸入參數本身已包含所需資訊。

## 解決方案

### 正確做法

建立明確的資訊提取優先級，優先從輸入資料本身提取：

```python
# 版本推斷優先級：
# 1. 明確指定的 --version（使用者意圖最明確）
# 2. 從 Ticket ID 提取（資料本身包含資訊）
# 3. 自動偵測當前版本（全域狀態 fallback）

explicit_version = getattr(args, 'version', None)

if not explicit_version and hasattr(args, 'ticket_id'):
    # 從 ID 提取：0.1.0-W1-017 → 0.1.0
    extracted = _extract_version_from_ticket_id(args.ticket_id)
    if extracted:
        version = extracted

if not version:
    version = require_version(explicit_version)  # fallback
```

### 設計原則

| 資訊來源 | 優先級 | 理由 |
|---------|--------|------|
| 使用者明確指定 | 最高 | 意圖最清楚 |
| 輸入資料本身 | 高 | 資料自描述，無歧義 |
| 全域/推斷狀態 | 最低 | 可能過時或不適用當前操作 |

## 預防措施

### 設計時檢查清單

設計 CLI 命令或 API 時：

- [ ] 輸入參數是否已包含推斷所需的資訊？（如 ID 中的版本號）
- [ ] 全域狀態（「當前版本」）是否可能與操作目標不一致？
- [ ] 是否建立了明確的資訊提取優先級？
- [ ] 多版本/多狀態並存時，推斷邏輯是否仍正確？

### 適用場景

- CLI 工具的 ID 解析（版本、環境、命名空間）
- API 路由的參數推斷
- 任何「有預設值但接受覆蓋」的設計

## 關聯 Ticket

- 0.1.0-W1-018：ticket track query/set-* 找不到 Ticket（已修復）

---

**Last Updated**: 2026-03-05
