---
id: PC-APP-006
title: .gitignore 排除了需要被追蹤的檔案（測試 fixture、uv.lock 等鎖定檔）：本地存在、新環境缺檔，sync --clean 當成孤兒
category: process-compliance
severity: medium
created: "2026-07-01"
---

# PC-APP-006: .gitignore 排除了需要被追蹤的檔案，本地看不出問題、新環境缺檔

> 檔名 slug 仍為 `gitignore-excludes-test-fixture`，反映第一個實例；機制不限測試 fixture，語意由標題與本檔內容承擔。

## 症狀

- `sync-push --clean` 報告孤兒檔（本地存在但遠端沒有），或把它列為清除對象
- 新 clone 環境缺少該檔：測試報 `FileNotFoundError`，或依賴鎖定檔的安裝結果與本地不同
- `git ls-files --error-unmatch <file>` 回報 untracked，`git check-ignore -v <file>` 命中某條 `.gitignore` 規則

## 根因

`.gitignore` 的某條規則排除了一個應該被追蹤的檔案。本地仍有這個檔，開發者感知不到問題；新 clone、或任何只看已追蹤內容的工具（sync、CI），都看不到它。

核心區分是**需要追蹤的檔**與 **runtime 產物**：前者是其他程式或環境重建時會讀的輸入（靜態測試 fixture、`uv.lock` 等鎖定檔），後者是執行時才產生、可以重建的輸出。排除規則把前者誤歸為後者，就會出現本模式。

**命中率取決於規則寫下的時間點**：`.gitignore` 不影響已經被追蹤的檔案。規則寫下時，已追蹤的檔照舊被追蹤，不會出現任何症狀；直到這個檔被 `git rm`，或在新環境重新產生，規則才開始生效。所以錯誤規則可能潛伏很久，觸發時與寫下規則的那次變更已經沒有明顯關聯。

## 實例

**實例 1：測試 fixture。** 測試 fixture 檔案（如 `sample_events.jsonl`）在某次重構中被 `git rm` 刪除，同時加入 `.gitignore`。之後某次操作在本地重新產生了該檔，但因被排除而無法 `git add`。本地測試通過（檔案存在），新 clone 環境測試失敗（檔案不存在），`sync-push --clean` 把它報成孤兒。

根因鏈：`git rm` + 加入 `.gitignore` → 本地殘留 untracked → 本地測試通過 → 新環境測試失敗

**實例 2：鎖定檔。** 另一個 consumer 的 `uv.lock` 被 `.gitignore` 排除，命中完全相同的機制：本地有檔，`sync-push --clean` 把它當孤兒處理。這個 pattern 當時的標題與辨識訊號都限定在測試 fixture，以「uv.lock」「孤兒」「--clean」查詢都找不到它，於是經過三個根因版本才重新推導出同一件事。

## 解決方案

1. 以 `git check-ignore -v <file>` 找出命中的規則
2. 判定該檔是需要追蹤的輸入，還是 runtime 產物：
   - 被其他程式讀取（`shutil.copy`／`open`／`Path`）、或環境重建依賴它（鎖定檔），屬需要追蹤
   - 由程式執行時動態產生、可以重建，屬 runtime 產物
3. 需要追蹤者：移除或收窄排除規則，`git add` 重新追蹤
4. runtime 產物：保留排除規則

```bash
# 診斷指令
git check-ignore -v <file>          # 找出匹配的 .gitignore 規則
git ls-files --error-unmatch <file> # 確認是否被追蹤
grep -rn "<filename>" .             # 確認是否被程式或測試引用
```

## 預防措施

- **新增或修改 `.gitignore` 規則時，全庫掃一次**：`git ls-files -ci --exclude-standard` 列出「已追蹤、但符合排除規則」的檔案。這些檔目前不受影響，但只要被 `git rm` 或在新環境重新產生，就會被排除。逐一確認它們是不是 runtime 產物；不是的話，收窄規則。
- 刪除檔案前，先 `grep -rn` 確認沒有引用，再決定要不要加入 `.gitignore`
- 鎖定檔（`uv.lock`、`package-lock.json` 等）與靜態 fixture 預設屬需要追蹤；把它們加入排除規則前要有明確理由

## 辨識訊號

| 訊號 | 含義 |
|------|------|
| `sync-push --clean` 報告孤兒檔，或列為清除對象 | 可能是被 `.gitignore` 排除、卻需要追蹤的檔 |
| 新 clone 環境缺檔（測試 `FileNotFoundError`、安裝結果與本地不同） | 該檔未被追蹤 |
| `git check-ignore -v` 命中一個被程式讀取的檔，或鎖定檔 | 應審查是否為誤排除 |
| `git ls-files -ci --exclude-standard` 有輸出 | 有已追蹤的檔落在排除規則內，屬潛伏中的本模式 |

---

**Last Updated**: 2026-11-20 — 標題、症狀、辨識訊號由「測試 fixture」泛化為「被排除卻需要追蹤的檔案」；新增實例 2（uv.lock）；預防措施補「規則寫下時全庫掃一次」（`git ls-files -ci --exclude-standard`）。來源 tarrragon/claude#91 缺口一。
