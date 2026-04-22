# Sync 排除清單分類規範

本文件定義 `.claude/scripts/sync-claude-push.py` 與 `.claude/scripts/sync-claude-pull.py` 排除清單的四類分類規範，以及框架新增機制時的評估流程。

> **Why**：dispatch-active.json 和 hook-state/ 曾被同步到其他專案，暴露「框架新增機制時無 sync 評估強制點」的結構性缺口。
> **Consequence**：不對稱的排除（push 排但 pull 不排，或反之）會導致 runtime state 被誤推到公開 repo、settings.local.json 被遠端覆蓋。
> **Action**：新增任何 runtime state / local settings / session log 機制時，必須依本文件 checklist 對兩端腳本同步更新。

---

## 適用範圍

| 對象 | 是否需套用本規範 |
|------|----------------|
| 新增 Hook 產生的 runtime state 檔案 | 是 |
| 新增 Skill 產生的本地設定檔 | 是 |
| 新增 PM 追蹤用的 session-bound log | 是 |
| 修改既有機制的檔案輸出路徑 | 是（檢查是否跨類別） |
| `.claude/` 下的靜態規則/方法論檔案 | 否（預設應跨專案同步） |

---

## 四類分類定義

### 類型 A - Runtime state

本 session 執行期狀態，專案特定且會隨時間變動。

| 特徵 | 說明 |
|------|------|
| 生命週期 | 本 session 或本次執行 |
| 跨專案共用 | 不可，會造成狀態污染 |
| 範例 | `dispatch-active.json`、`hook-state/`、`pm-status.json` |

**辨識問題**：這個檔案若同步到另一個專案，會不會被誤認為該專案的狀態？若會，屬類型 A。

### 類型 B - Local-only settings

各專案個別設定，不應跨專案同步。

| 特徵 | 說明 |
|------|------|
| 生命週期 | 跨 session 保留，但專案獨立 |
| 跨專案共用 | 不可，每個專案獨立管理 |
| 範例 | `settings.local.json`、`sync-preserve.yaml`、`.sync-state.json` |

**辨識問題**：這個檔案的內容對不同專案是否有不同取值？若是，屬類型 B。

### 類型 C - Session-bound log

本地產生的日誌/交接檔案。

| 特徵 | 說明 |
|------|------|
| 生命週期 | 本 session 或本機歷史 |
| 跨專案共用 | 不可，無跨專案共用價值 |
| 範例 | `hook-logs/`、`handoff/`、`PM_INTERVENTION_REQUIRED`、`ARCHITECTURE_REVIEW_REQUIRED` |

**辨識問題**：這個檔案是 Hook / PM 執行過程中寫出的嗎？若是，屬類型 C。

### 類型 D - 敏感憑證

嚴禁推送至公開 repo 的憑證/密鑰/環境變數。

| 特徵 | 說明 |
|------|------|
| 生命週期 | 不限 |
| 跨專案共用 | 不可，且推送會造成安全事故 |
| 範例 | `.env*`、`credentials.json`、`secrets.*`、`.keys`、私鑰副檔名（`.pem`、`.key` 等） |

**辨識問題**：這個檔案被外人看到會不會造成安全風險？若會，屬類型 D。

---

## 新增機制時的 4 項 Checklist

新增產生上述任一類型檔案的 Hook / Skill / Script 時，提交前依序完成：

### Checklist 1：分類確認

- [ ] 新檔案屬於四類（A/B/C/D）中的哪一類？
- [ ] 若都不符合，該檔案是否真的需要放在 `.claude/`？（考慮改放 `docs/` 或外部路徑）

### Checklist 2：push 端排除

- [ ] `.claude/scripts/sync-claude-push.py` 的 `EXCLUDE_PATTERNS` 已加入新檔案/目錄名稱
- [ ] 注解標註所屬類別（類型 A/B/C/D）
- [ ] 若為目錄層級排除（如 `hook-state`），確認 `should_exclude` 的 `path.parts` 檢查能正確攔截

### Checklist 3：pull 端對稱

- [ ] `.claude/scripts/sync-claude-pull.py` 的 `LOCAL_ONLY` 已加入同名項目
- [ ] 注解標註所屬類別（類型 A/B/C）
- [ ] 確認兩端對稱：push 排除的，pull 也必須排除（避免遠端反向覆蓋）

### Checklist 4：驗證與文件

- [ ] 本地實際產生該檔案後，執行 `sync-claude-push.py` dry-run（或檢查 `copy_filtered` 行為）確認未被包含
- [ ] 若屬類型 B（local-only settings），確認 `sync-preserve.yaml` 機制是否適用
- [ ] 在新增機制的 Hook/Skill 文件中註記該檔案的排除分類

---

## 決策流程

```
新機制產生 .claude/ 下的檔案
         |
         v
Q1: 內容是否隨 session/執行變動？
  +-- 是 --> 類型 A (Runtime state)
  +-- 否 --> Q2

Q2: 內容是否每個專案不同？
  +-- 是 --> 類型 B (Local-only settings)
  +-- 否 --> Q3

Q3: 是 Hook/執行期寫出的 log 嗎？
  +-- 是 --> 類型 C (Session-bound log)
  +-- 否 --> Q4

Q4: 含密鑰/token/憑證嗎？
  +-- 是 --> 類型 D (敏感憑證)
  +-- 否 --> 該檔案可能屬跨專案共用的規則/方法論，不需排除
             （若不確定，回 Q1 重新評估或向 PM 諮詢）
```

---

## 反模式

| 反模式 | 為何違反 | 修正方向 |
|-------|---------|---------|
| 只改 push 端不改 pull 端 | pull 時遠端會覆蓋本地 local-only 檔案 | 兩端必須對稱同步 |
| 新增時不分類僅用 `# 排除 xxx` 注解 | 後人無法判斷歸屬與同步影響 | 明示類型 A/B/C/D 並附理由 |
| 類型 D（憑證）排除用檔名精確匹配 | 變體（`.env.staging`、`secrets_prod.json`）會漏網 | 使用 `EXCLUDE_NAME_PREFIXES` 前綴或副檔名規則 |
| runtime state 放進 `sync-preserve.yaml` | preserve 是 local-only 但可接收遠端更新，與 runtime state 生命週期不符 | runtime state 走 `EXCLUDE_PATTERNS` / `LOCAL_ONLY`，不走 preserve |

---

## 與既有機制的關係

| 機制 | 用途 | 與本規範關係 |
|------|------|------------|
| `EXCLUDE_PATTERNS` (push) | 推送時排除 | 本規範的直接應用目標 |
| `LOCAL_ONLY` (pull) | 拉取時跳過同步 | 本規範的直接應用目標 |
| `sync-preserve.yaml` | 保留本地特化檔案，但接收遠端更新通知 | 類型 B 的子集，用於「可接收更新提示但不自動覆蓋」的檔案 |
| `EXCLUDE_NAME_PREFIXES` (push) | 前綴匹配變體檔名 | 類型 D 的安全網，避免漏排變體 |
| `EXCLUDE_SUFFIXES` (push) | 副檔名匹配 | 類型 D 的安全網（`.pem`、`.key` 等） |

---

## 相關文件

- `.claude/scripts/sync-claude-push.py` — push 端排除清單實作
- `.claude/scripts/sync-claude-pull.py` — pull 端排除清單實作
- `.claude/references/framework-asset-separation.md` — 框架資產與專案產物分離原則（上位文件）
- `.claude/references/plugin-management.md` — Plugin 安裝前的評估清單（類似評估框架）

---

**Last Updated**: 2026-04-22
**Version**: 1.0.0 — 從 W17-045.1 建立，補齊 sync 排除清單的分類規範與新增機制 checklist
**Source**: W17-045（dispatch-active.json + hook-state 被誤同步事件）
