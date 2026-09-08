---
id: IMP-BAL-020
title: 未錨定行首的 code fence 正則讓行內三反引號字面翻轉守衛判定
severity: medium
status: active
category: implementation
tags: [regex, code-fence, guard-hook, false-negative, false-positive]
---

# IMP-BAL-020: 未錨定行首的 code fence 正則讓行內三反引號字面翻轉守衛判定

## 基本資訊

| 欄位 | 值 |
|------|-----|
| 類別 | implementation |
| 風險等級 | medium |
| 來源版本 | 0.2.1 |
| 發現情境 | 收尾 skill 入口檔時，代理人刪除一行含 awk 指令示範（示範字串內帶三反引號字面）的內容，被規則 8 守衛 hook 兩次擋下，錯誤訊息指向一處**未被觸碰**的既有專案 ticket ID 引用 |

## 症狀

- 守衛 hook 對「刪除某一行」的編輯報「新增專案 ticket ID 引用」，`git diff` 證實被指名的那一行在前後版本皆存在、內容未變。
- 同一檔案在此之前多次通過該 hook，但人工全掃發現檔內確有一處散文中的專案 ticket ID 引用從未被攔。
- 兩個現象出現在同一檔案、同一 hook，方向相反（一次誤攔、一次漏檢）。

## 根因

hook 在比對前先以正則剝除 code fence：`r"```.*?```"` 搭配 `DOTALL`，**不錨定行首**。任何行內出現的三反引號字面（shell 指令示範、正則說明、對 markdown 語法本身的描述）都被當成 fence 的開或閉。

一處行內三反引號會讓其後所有真正的 fence 配對整體錯位一格：原本在 fence 外的散文段落被剝除（漏檢），原本在 fence 內的示範內容被暴露（誤攔）。刪除含行內三反引號的那一行，配對恢復正確，原本被誤藏的既有引用在「新內容」中首次可見，hook 據此判為新增。

## 為什麼難以察覺

| 因素 | 效果 |
|------|------|
| 漏檢無訊號 | 錯位後被剝除的散文不會產生任何輸出，hook 綠燈與真綠燈同形 |
| 誤攔指向錯誤位置 | 錯誤訊息引用的行是配對錯位的受害者，不是肇因行；編輯者以 `git diff` 核對該行會得到「未變動」，第一反應是 hook 有 bug 而非自己的編輯觸發了什麼 |
| 觸發需要特定內容 | 行內三反引號只出現在少數技術文件（示範 markdown 語法、awk/sed 指令），多數檔案永遠不觸發，hook 看起來長期可靠 |

## 解決方案

fence 開閉只在行首匹配（允許縮排），保留跨行 `DOTALL`：

```python
# 修正前
CODE_FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)

# 修正後：開閉皆須位於行首（允許前導空白），行內字面不再構成邊界
CODE_FENCE_PATTERN = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE)
```

測試最少三案：(1) 行內三反引號不構成 fence，其後的散文引用仍被攔；(2) 行首 fence 內的示範引用不被攔；(3) 刪除含行內三反引號的行，既有引用的判定結果不變。

## 預防措施

- 任何以正則剝除 code fence 再檢查的 hook／linter，fence 邊界一律錨定行首；CommonMark 定義 fence 為獨立一行，行內三反引號是 code span 不是 fence。
- 守衛 hook 的測試夾具至少含一份「示範 markdown 語法本身」的檔案（含行內三反引號），這類檔案在文件型 skill 的 references 中必然存在。
- 收到守衛誤報而 `git diff` 顯示被指名行未變動時，往前找配對類語法（fence、引號、括號）的錯位源，而非直接判 hook 有 bug 或加豁免標記繞過。

## 關聯

- 同型錯誤家族：任何「先剝除／遮罩再檢查」的兩階段守衛，遮罩階段的邊界判定錯誤會同時造成漏檢與誤攔（方向相反、根因相同）。
- 修復追蹤：consumer 專案的 IMP 票（修正正則並補測試）。
