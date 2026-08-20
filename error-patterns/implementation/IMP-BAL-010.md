---
id: IMP-BAL-010
title: 輔助函式以空值表示判定失敗，呼叫端布林轉換使守衛語意靜默反轉
severity: high
category: implementation
related: [IMP-BAL-002, PC-V1-001]
created: 2026-08-20
---

# IMP-BAL-010: 輔助函式以空值表示判定失敗，呼叫端布林轉換使守衛語意靜默反轉

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 高 |
| 首次發現 | 2026-08-20 |
| 適用範圍 | 任何以外部命令查詢結果驅動守衛判定的程式碼；安全關鍵守衛（刪除建議、權限放行、資源回收）為高發區 |

## 症狀

- 守衛邏輯在外部命令失敗時輸出「安全」結論而非「無法判定」——例如稽核工具建議刪除實際上含未落地工作的分支
- 單元測試全綠：測試覆蓋的是「判定成功」路徑，失敗路徑要嘛未測，要嘛斷言的是「不拋例外」而非「輸出正確分類」
- 錯誤不可見：失敗被 `except` 吞掉後回傳空值，呼叫端無從分辨，日誌若缺失則整條路徑無痕跡
- 同一檔案內反覆出現同構問題：修掉一處後在鄰近函式再發現一處，第三處又在另一函式

## 根因

三個各自合理的決策疊加後語意反轉：

1. **輔助函式以「空值」兼表兩種語意**：`return []` / `return None` 同時代表「查到了，結果為空」與「查不到，判定失敗」。單看函式簽章 `-> List[str]` 沒有表達第二種狀態的位置。
2. **呼叫端以布林轉換或成員檢查消費**：`bool(result)`、`if not result`、`x in result` 把兩種語意壓成同一個 `False`。壓縮發生在呼叫端，而寫呼叫端的人看的是型別簽章，簽章沒說會失敗。
3. **守衛的預設方向是「放行」**：`if 有問題: 阻擋` 的結構下，判定失敗落入 else 分支即放行。若寫成 `if 確認無問題: 放行` 則同樣的失敗會落入阻擋側。

三者單獨都不是錯誤——空清單是慣用回傳、布林轉換是慣用消費、守衛寫成正向判斷是慣用結構。錯誤只在三者組合時出現，且組合處跨越函式邊界，程式碼審查看單一 diff 不易發現。

**放大條件**：守衛的作用範圍擴大時，同一個 fail-open 的代價隨之放大。原本只誤判拋棄式對象，範圍放寬後誤判的可能是不可重建的資產。範圍擴大的 diff 本身乾淨、測試全綠，風險不在改動的行裡。

## 解決方案

回傳型別改為可表達三態，呼叫端據以分流：

```python
# 修復前：兩種語意壓成一個空清單
def get_unmerged_commits(branch, logger) -> List[str]:
    try:
        result = subprocess.run([...], timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []                      # 判定失敗
    if result.returncode != 0:
        return []                      # 判定失敗
    return [line for line in result.stdout.splitlines() if line]

has_unmerged = bool(get_unmerged_commits(branch, logger))   # 失敗 → False → 標為「可安全刪除」

# 修復後：None 表判定失敗，各失敗路徑各自記錄
def get_unmerged_commits(branch, logger) -> Optional[List[str]]:
    try:
        result = subprocess.run([...], timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning("git log main..%s 執行逾時，無法判定 ahead 狀態", branch)
        return None
    except FileNotFoundError:
        logger.warning("git log main..%s 找不到 git 執行檔，無法判定 ahead 狀態", branch)
        return None
    if result.returncode != 0:
        logger.warning("git log main..%s 非零退出碼: %d，無法判定 ahead 狀態", branch, result.returncode)
        return None
    return [line for line in result.stdout.splitlines() if line]

unmerged = get_unmerged_commits(branch, logger)
ahead_state = None if unmerged is None else bool(unmerged)   # 三態流到下游
```

下游訊息組裝對 `None` 走獨立分類（「無法判定，需人工確認」），**不併入任何建議破壞性操作的分類**。

## 預防措施

- **檢查觸發點**：擴大既有函式的輸入範圍、放寬選取條件、把守衛從特例套用改為通用套用時，回頭問「它的錯誤路徑原本影響什麼、現在影響什麼」。此類風險不在 diff 的行裡，看改動本身發現不了。
- **簽章即契約**：可能失敗的查詢函式，回傳型別要能表達失敗（`Optional`、Result 型別、或明確拋例外），不要讓空值兼表兩義。
- **失敗路徑逐條測試**：每個 `except` 分支與非零退出碼各補一個測試案例，斷言的是「輸出的分類正確」而非「不拋例外」。
- **同檔全掃**：發現一處後不要只修那一處。本案在同一個稽核 hook 內連續發現三處同構問題（取未合併 commit、取 worktree 清單、取當前分支名），寫作當下的預設風格會在整個檔案重複。
- **守衛預設方向**：安全關鍵的守衛寫成「確認無問題才放行」，使判定失敗自然落入保守側，而非依賴每個呼叫端記得處理失敗。

## 關聯

- 同家族根因（對未知輸入 fail-open）：`IMP-BAL-002`、`PC-V1-001`
- 可觀測性要求（每個 `except` 須有日誌）：`.claude/rules/core/quality-baseline.md` 規則 4、`.claude/rules/core/observability-rules.md` 規則 1
- 實例形態：git worktree 稽核 hook 的三個查詢輔助函式（未合併 commit 數、worktree 分支清單、當前 checkout 分支名），三者皆以空值表示判定失敗；放大條件為該 hook 的孤兒分支掃描範圍由命名前綴比對放寬至全部本地分支，使誤判對象從拋棄式 runtime 分支變為可能含未落地工作的人工命名分支
