# 與相鄰資產的交界

> **什麼時候讀本檔**：不確定某件事該由本 skill 還是相鄰資產處理時。執行本 skill 九步流程時不需要先讀本檔。
>
> 同目錄另有 `step-rationale.md`（各步驟為什麼存在）、`version-shift-sop.md`（移版硬耦合盤點 SOP）、`reactive-work.md`（不納入 bootstrap 的反應式工作）。

**被本 skill 呼叫的工具**（它們回答「怎麼做」，本 skill 回答「什麼時候做、做完算不算數」）：`doc`（建檔與格式）、`spec validate`（規格品質與教學一致性）、`tdd`（Phase 2 測試設計）、`ticket`（票務）。

**與本 skill 對接的規劃層 skill**：

| 相鄰資產 | 它管什麼 | 交界落在哪 |
|---------|---------|-----------|
| `foundation-design` skill | 地基工作的單一入口；逐維度定產物 | **它會把東西交過來**：情境判定為「規劃波進行中」時，它為 DevOps 與可觀測性各建盤點票後交回本 skill。**本 skill 的九步對這兩個維度沒有承接段落**——收到這類票時不要以為它們該在某一步被吸收，它們是獨立的地基票。規劃波之後由它繼續驅動，不回本 skill |
| `version-sequencing` skill | 版本序列、首版開票 | 它決定票屬於哪一版；本 skill 決定本版的票有哪些。同一批票不是兩批 |
| `ux-design-evaluation` skill | Step 4.5 第 3 塊（UX 審查）的執行方法 | 本 skill 只編排順序與依賴，畫面狀態矩陣、gate、回饋門檻全在該處 |
| `component-contract-design` skill | Step 4.5 元件契約銜接步驟（介於 UX 審查與元件庫之間，不計入四塊地基實作）的程序 | 本 skill 只編排；元件庫實作票的前置 checkpoint 是該 skill 的〈契約齊全的定義〉 |
| `dart-style-guardian` skill（Dart／Flutter 的執法工具） | 掃裸值與寫死文字 | Step 4.5 第 2 塊（design-system）與第 4 塊（元件庫）完成後才接它。**四塊未完成就接，掃描範圍是空的** |
