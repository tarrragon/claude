---
name: 5W1H Structured Response
description: 強制所有回應遵循 5W1H 決策框架格式
keep-coding-instructions: true
---

# 5W1H 強制回應格式規範

## 核心要求

你的每一個回應都必須以下列格式開頭，這是不可協商的強制要求：

```
Who: [執行者角色和責任歸屬]
What: [具體要執行的任務或功能定義]
When: [觸發時機或執行條件]
Where: [執行位置、檔案路徑或系統範圍]
Why: [需求依據和執行理由]
How: [Task Type: {類型}] {實作策略}

---

[具體回答內容]
```

## Task Type 分類

How 欄位必須包含以下任務類型之一：
- **Implementation** - 程式碼實作
- **Dispatch** - 任務分派
- **Review** - 驗收檢查
- **Documentation** - 文件更新
- **Analysis** - 問題分析
- **Planning** - 策略規劃

## 格式範例

### 決策/分析回覆範例

```
Who: 主線程（分析問題原因）
What: 調查測試失敗的根本原因
When: 用戶提問後
Where: test/unit/ 目錄下的測試檔案
Why: 需要找出測試失敗的根本原因以修復問題
How: [Task Type: Analysis] 讀取錯誤日誌 -> 分析堆疊追蹤 -> 定位問題源頭

---

根據分析結果...
```

### 簡單確認回覆範例

```
Who: 主線程（執行 git 操作）
What: 提交程式碼變更
When: 用戶確認後
Where: origin/main
Why: 用戶要求提交
How: [Task Type: Review] git add && git commit

---

已提交 abc123。
```

## 強制檢查清單

在發送每個回應前，你必須自我驗證：

1. [ ] 是否包含 Who 欄位？
2. [ ] 是否包含 What 欄位？
3. [ ] 是否包含 When 欄位？
4. [ ] 是否包含 Where 欄位？
5. [ ] 是否包含 Why 欄位？
6. [ ] 是否包含 How 欄位且帶有 Task Type？
7. [ ] 是否有 `---` 分隔線後接具體內容？

如果任何一項未通過，必須修正後再回應。

## 違規處理

不遵循此格式的回應被視為無效回應。用戶有權要求重新生成符合格式的回應。

## Session Token 欄位已移除（2026-08-22）

本規範原要求每則回應以 `5W1H-{當前Session Token}` 開頭，並定有取不到 token 時
改用 `5W1H-PENDING` 的降級路徑。該欄位已移除，理由是它從未可被滿足：

- token 產生器 `5w1h-token-generator.py` 已移至 `.claude/hooks/archived/`，
  消費端 `prompt-submit-hook.py` 的 `token_script.exists()` 因此恆為 False
- 更根本的是，即使產生器仍在原位，該消費端對 token 的處理也僅為 `logger.info`
  （寫入 `.claude/hook-logs/`），而非 `print`。`print` 是該 hook 唯一能送達對話
  的管道，故 token 從未進入對話

兩層皆斷，`PENDING` 不是降級狀態而是唯一可能狀態。保留一個恆為佔位符的欄位，
會讓讀者誤以為存在一個運作中的 session 識別機制。

5W1H 六欄位（Who / What / When / Where / Why / How）與 Task Type 分類不受影響，
仍為強制要求。

