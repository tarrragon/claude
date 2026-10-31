---
id: IMP-GPD-019
title: "Flutter 的 Semantics(liveRegion: true) 沒設 container 時，旗標與 label 併入外層擁有節點的祖先，播報範圍擴大到整個容器，連帶把動態計數一起納入"
severity: medium
related:
 - TEST-GPD-1002
---

# IMP-GPD-019: Flutter 的 Semantics(liveRegion: true) 沒設 container 時，旗標與 label 併入外層擁有節點的祖先，播報範圍擴大到整個容器，連帶把動態計數一起納入

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | implementation |
| 來源版本 | 0.5.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-10-29 |

## 症狀

元件規格要求「進入某狀態時，訊息以 liveRegion 播報一次」，實作用 `Semantics(liveRegion: true, child: Text(message))` 包住訊息。語意樹傾印卻顯示：

- liveRegion 旗標落在一個 Rect 為整個畫面的節點上，不是訊息本身。
- 該節點的 label 除了訊息，還包含同區的說明文字（例如「已掃描 N 項」這類會持續更新的計數）。

計數每更新一次，liveRegion 節點的 label 就跟著變，讀屏可能整段重播，與「播報一次」不符。widget 測試的一般斷言（找得到文字、按鈕可點）全部通過，偏離只有傾印看得出來。

實證（2026-10-29）：空狀態元件在「掃描中」時，liveRegion 節點為 960×640 全畫面，label 為「掃描中\n已掃描 0 項」；按鈕則是其子節點。

後續全面盤點（2026-10-30）：同一元件庫內另有 5 處 `Semantics(liveRegion: true)` 未設 container。逐一傾印後，4 處同樣併入外層，label 分別混入路徑、骨架與進度值、版本與說明，或讓按鈕落進 live 子樹。剩下 1 處有獨立節點。盤點時一度判讀為「靠父層兄弟結構偶然分開」，實作修正時才發現是元件根節點設了 `explicitChildNodes: true`，子節點一律各自成節點，屬於元件本身的保證。加上 container 沒有任何可觀測差異，對照測試也做不出轉紅。改成只拿掉 `explicitChildNodes` 來做對照，也不可行：該節點同時設了 `scopesRoute: true`，框架會以 assertion 強制要求 `explicitChildNodes` 為 true，元件會直接建構失敗，得不到斷言層級的紅燈。這類由框架約束鎖住的保證，測試只能定位為回歸斷言，不能當作鑑別力證據。教訓：判讀「偶然符合」之前，要先沿祖先鏈檢查每一層 Semantics 的 `container`、`explicitChildNodes`、`scopesRoute` 設定，不能只看傾印出來的節點形狀就推測成因。

## 根因

**Semantics 沒有 `container: true` 時不會建立自己的節點**。它的屬性會合併到往上第一個擁有節點的祖先。如果那個祖先是頁面級容器，liveRegion 旗標就落在整個容器上，容器內其他文字也被合併進同一個 label。

**播報範圍由語意樹決定，不由程式碼包住的範圍決定**。程式碼看起來只包了訊息，但實際生效的範圍取決於節點邊界。

## 解決方案

- liveRegion 的 Semantics 加上 `container: true`，讓它建立只含訊息的獨立節點。
- 測試以語意樹斷言三件事：liveRegion 節點的 label 只含訊息、不含動態計數；互動元件不在其子樹內；節點 Rect 不是整個容器。另附正向對照：拿掉 `container: true` 時測試必須轉紅。

## 預防措施

- 凡是設定 liveRegion、header、button 等語意角色的 Semantics，檢查是否需要 `container: true` 才能形成獨立節點。傾印顯示目前已是獨立節點，也要確認這是元件自己保證的，還是靠父層結構偶然成立；後者同樣要加 container。判定方法：替換外層容器重新傾印，並逐層查看祖先的 `explicitChildNodes`／`container` 設定。已由元件保證的就不要再加 container，因為加了沒有可觀測效果，測試也驗證不到。
- 發現一處時，對同一元件庫全面 grep 同型寫法。這類偏離通常整批出現，因為寫法是互相抄來的。
- 涉及播報行為的規格條文，驗收要用語意樹傾印或節點斷言，不能只用文字查找。
- 實機讀屏（VoiceOver 等）會不會重播仍需實機確認；widget 測試只能斷言結構。

## 關聯 Ticket

本地案例票號只記在專案票面（框架檔案依引用穩定性規則 8 不引用專案層級識別符）。
