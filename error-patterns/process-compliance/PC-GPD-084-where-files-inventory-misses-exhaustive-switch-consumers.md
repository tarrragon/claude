---
id: PC-GPD-084
title: 派發前盤點 where.files 只列出要改的檔與它的直接呼叫端；改動替列舉型別新增成員時，漏列了有窮舉 switch 的消費端，代理人動工前就被範圍擋下
severity: low
related:
 - PC-GPD-047
---

# PC-GPD-084: where.files 盤點漏列窮舉 switch 的消費端

## 基本資訊

- **類別**：process-compliance
- **發現情境**：PM 派發前盤點 where.files。該票替一個結果列舉新增成員，`ticket track commit` 以 where.files 判定提交範圍。

## 症狀

代理人讀完程式碼就停下，回報 NeedsContext：列舉新增成員後，有幾處沒有 default 的 switch 會編譯失敗，而這些檔不在 where.files 內。結果多耗一輪派發，產品碼一行都沒改。

## 根因

PM 盤點時從規格的「介面」出發，只列了實作者（`implements X`）和規格點名要改的畫面。窮舉 switch 是列舉的**消費端**，規格不會點名，但在 Dart 這類靜態型別語言裡，替列舉加成員一定會牽動它們。派發骨架裡的 grep 指引只涵蓋測試目錄，所以 PM 端也沒有對應的檢查步驟。

## 防護

改動會替 enum／sealed class 新增成員，或修改既有成員時，盤點 where.files 要加一步：以型別名稱 grep `lib/`，把所有 `switch` 這個型別的檔案列進去，對應的測試檔一併列入。

```bash
grep -rln "<EnumName>\." lib test | sort
```

Why：窮舉 switch 是編譯期強制同步的耦合，少列一檔，派發就必定在動工前或提交時被擋。
Action：盤點表另立一列「列舉消費端」，寫出 grep 命令與命中的檔數，讓審閱者看得出這一步做過。

## 案例

一張實作票替開檔結果列舉新增「已開啟但未用所選編輯器」成員。PM 盤點列了 22 個檔，漏掉 3 處窮舉 switch（兩個畫面、一個結果鍵對照函式）。第一輪代理人回報缺口後，PM 補進 4 個檔重派。
