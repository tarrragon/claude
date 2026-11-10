---
id: TEST-LLM-002
title: "測試呼叫會 chdir 的函式卻未以 monkeypatch.chdir 隔離，cwd 外洩到其他測試檔，各檔單獨跑全綠、全套件依收集順序紅燈"
severity: medium
status: active
related:
 - TEST-GPD-003
 - IMP-LLM-003
---

# TEST-LLM-002: 測試呼叫會 chdir 的函式卻未以 monkeypatch.chdir 隔離，cwd 外洩到其他測試檔，各檔單獨跑全綠、全套件依收集順序紅燈

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 來源版本 | 3.1.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-11-10 |

**判準**：如果被測函式的副作用會改變行程狀態（cwd、全域變數、環境變數），測試要用 monkeypatch 鎖住這些狀態，結束時還原。只用 monkeypatch 設定輸入不夠。

## 症狀

- 新增的測試檔單獨跑全綠，被影響的那個測試檔單獨跑也全綠。
- 全套件跑時，與本次修改無關的測試檔紅燈，例如相對路徑被算成 `../../../../docs/...`、git 操作回傳 `failed`。
- 調換兩個檔的執行順序就全綠，可以確認是順序依賴。

## 根因

pytest 的所有測試在同一個行程裡跑。被測函式呼叫 `os.chdir` 時，改的是整個行程的 cwd。測試只用 `monkeypatch.setenv` 設定輸入、沒有鎖住 cwd，函式切換過去的目錄（tmp 目錄或其他路徑）就會留到後面的測試。收集順序在前的檔一旦改了 cwd，排在後面、依賴 cwd 的檔就會紅燈，所以紅燈出現在與修改無關的地方。

## 解決方案

- 在測試或 fixture 開頭呼叫 `monkeypatch.chdir(os.getcwd())`。monkeypatch 會記下原本的 cwd，拆除時還原，即使函式在中間直接呼叫 `os.chdir` 也一樣會還原。
- 這類函式若可能經由多個測試檔被呼叫（例如 CLI 的 `main()`），把隔離做成 autouse fixture，放在涵蓋全部 testpaths 的 conftest（skill 根目錄或 rootdir），一處就能涵蓋所有測試檔，不要逐檔手寫 try/finally。

## 預防措施

- 撰寫會呼叫 `os.chdir`、或會呼叫內含 chdir 的入口的測試時，以兩檔組合驗證：「新測試檔 + 一個依賴 cwd 的既有測試檔」，新測試排在前面跑。單檔全綠不能當作隔離成立的依據。
- 判讀「全套件紅、單檔綠」時，先調換兩檔的執行順序。換序後轉綠，就是行程狀態外洩，不是被影響的那個測試本身有問題。

## 驗證方式（本次）

兩檔組合依序跑（新測試在前）：13 failed，與全套件的失敗數一致。調換順序：119 passed。加上 `monkeypatch.chdir(os.getcwd())` 的 autouse fixture 後，原順序轉綠。

## 相關 Pattern

- TEST-GPD-003：全域 sleep monkeypatch 波及子行程（同屬測試替換或副作用的範圍超出預期）
- IMP-LLM-003：交接環境變數未移除。本例的第二個外洩來源：環境裡帶有該變數時，直接呼叫 `main()` 的測試會被 chdir
