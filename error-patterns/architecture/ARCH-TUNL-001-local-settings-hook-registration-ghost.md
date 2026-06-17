# ARCH-TUNL-001: settings.local.json 註冊 hook 在 relocate 後成幽靈（sync 無法自癒）

## 基本資訊

- **Pattern ID**: ARCH-TUNL-001
- **分類**: 架構設計
- **來源版本**: v1.0.0（1.0.0-W9-001 ANA）
- **發現日期**: 2026-06-17
- **風險等級**: 中

## 問題描述

### 症狀

每次 Stop 事件（或對應 event）runtime 報 `<hook-path>: No such file or directory`。檢查發現 `settings.local.json` 註冊的 hook command 指向舊路徑，該檔已 relocate 到新位置（如 `.claude/hooks/` → `.claude/skills/*/hooks/`）。`settings.json` 已指向新路徑，但 `settings.local.json` 殘留舊註冊。常伴隨同一 hook 跨兩檔重複註冊（additive 合併語意下重複執行）。

### 根本原因 (5 Why 分析)

1. Why 1: `settings.local.json` 註冊的 hook 路徑指向不存在的檔。
2. Why 2: hook relocate 時只更新了 canonical `settings.json`，沒回頭清 `settings.local.json` 的舊副本。
3. Why 3: 「hook 實際位置」與「註冊路徑字串」是同一事實的兩份副本，搬檔不會自動更新註冊（無參照完整性）。
4. Why 4: hook 註冊職責同時存在於兩層，且系統允許不協調的重複註冊（無單一註冊來源原則）。
5. Why 5: **`settings.local.json` 是 sync 排除檔（local-only），上游 relocate 無法觸及下游 local 層，孤兒 `--audit` 也掃不到 local 內部——保護邊界同時是修正盲區，落在此區的舊註冊永久豁免於自癒。**

### 為何 local 層特別危險

| 層 | sync 行為 | relocate 後果 |
|----|----------|--------------|
| settings.json | 被 sync overlay，上游可修正 | 上游更新路徑即修復 |
| settings.local.json | sync 排除，永不觸及 | 舊註冊成幽靈，無任何機制自癒 |

## 解決方案

### 正確做法：hook 註冊單一來源原則

所有 hook 註冊一律寫入 `settings.json`。`settings.local.json` 僅放 `permissions` / `env` / `enabledMcpjsonServers` / `outputStyle`，**禁止註冊任何 hook**。

| 場景 | 做法 |
|------|------|
| 新增 hook | 註冊到 settings.json |
| 發現 local 層已有 hook 註冊 | 移至 settings.json，從 local 移除 |
| hook relocate | 更新 settings.json 路徑；掃所有 settings 檔清理舊註冊 |

### 錯誤做法（避免）

```jsonc
// settings.local.json — 錯誤：local 層註冊 hook
{ "hooks": { "Stop": [{ "matcher": "", "hooks": [
    { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py" }
]}]}}
```

## 檢測方法

```bash
# 偵測 settings.local.json 內任何 hook 註冊（latent ghost）
python3 -c "import json; d=json.load(open('.claude/settings.local.json')); print('hooks key:', 'hooks' in d)"
```

**強制層**：`hook-completeness-check.py`（SessionStart）偵測三類問題並發出 WARNING——(1) 幽靈註冊（檔不存在）、(2) 跨檔重複註冊、(3) `settings.local.json` 內含任何 hook 註冊（latent ghost 預防，即使當下合法）。函式 `find_local_hook_registrations`。

## 預防措施

- 規則 SSOT：`.claude/references/hook-system-operations.md`「Hook 註冊單一來源原則」段。
- hook 強制層：`hook-completeness-check.py` 的 `find_local_hook_registrations`。
- relocate hook 時，將「掃所有 settings 檔清理舊註冊」納入步驟。

## 關聯

- **Ticket**: 1.0.0-W9-001
- **相關規則**: `.claude/references/hook-system-operations.md`
- **概念同源**: `tool-output-trust-rules` 規則 5（記錄平面 vs 世界平面二相性）——本案是該二相性在配置層的翻版。

## 標籤

`#架構` `#配置管理` `#hook註冊` `#sync同步` `#參照完整性`
