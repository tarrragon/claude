---
id: IMP-BAL-006
title: 同一排除集合在同一同步方向的兩條消費路徑處置相反——套用與否由呼叫端各自決定而非集合定義強制
severity: high
category: implementation
related: [ARCH-BAL-017, ARCH-BAL-009, IMP-BAL-002]
canonical_issue: tarrragon/claude#50
created: 2026-08-12
---

# IMP-BAL-006: 同一排除集合在同一同步方向的兩條消費路徑處置相反——套用與否由呼叫端各自決定而非集合定義強制

## 症狀

`sync-claude-pull.py` 對同一個 pull 方向，存在兩條消費 `PUSH_ONLY_EXCLUDE_PATTERNS`（經 `should_exclude` 判定）的路徑，處置完全相反：

| 路徑 | 函式 | 是否呼叫 `should_exclude` | 對 `project-integration` 目錄的處置 |
|------|------|-------------------------|-----------------------------------|
| 三方合併 | `apply_upstream_delta` | 呼叫 | 正確跳過，per-project 內容不受影響 |
| full overlay | `cleanup_stale_files` | 不呼叫（grep 呼叫計數為 0） | 當 stale 檔案整目錄刪除 |
| full overlay | `sync_directory` | 不呼叫 | 以上游內容整目錄覆蓋 |

實證：某 consumer 專案的 `references/project-integration/` 7 檔於一次 full overlay sync-pull（`cleanup_stale_files`）被靜默刪除，其後多次三方合併路徑（`apply_upstream_delta`）未觸發修復——不是三方合併無法恢復，而是刪除本身發生在三方合併不會經過的另一條路徑，兩條路徑對同一目錄的判定從未有機會互相校正。刪除當下無記錄、後續同步無告警，該專案在兩次 sync-pull 之後結構殘缺而無任何可觀測訊號，直到跨專案盤點才發現差額。

## 根因

**排除集合的套用不是集合定義的一部分，而是由每個消費路徑各自決定要不要呼叫判定函式。** 集合本身（`PUSH_ONLY_EXCLUDE_PATTERNS` 經 `should_exclude`）定義完整且語意正確——類型註解明文「這些名稱在 sync push/pull 時排除」，判定函式本身邏輯無誤。缺陷發生在消費端：`apply_upstream_delta` 寫成時記得呼叫，`cleanup_stale_files`／`sync_directory` 寫成時沒有，三者是三次獨立的實作決定，彼此不互相檢查。

這與「清單本身過期或錯誤」不同——`should_exclude` 從未被錯誤呼叫過，它只是沒有被全部該呼叫的地方呼叫。新路徑加入時（`sync-claude-pull.py` 隨版本迭代新增 full overlay 的清理/同步邏輯），作者的心智模型是「如何正確走訪並清理/同步檔案」，不會回頭檢查「是否已有其他路徑對同一批資料套用了排除政策」，因為排除政策這個維度不在該路徑的介面設計裡出現過。

**與 ARCH-BAL-017 的關係**：ARCH-BAL-017 記錄的是同一根因家族的另一起案例（skill 庫檢查的唯讀報告路徑對 `private` 排除清單零知識），並將其歸納為一般化的架構模式——「排除政策只在寫入路徑生效，其餘路徑對其零知識」。本案例是該模式在 sync-pull 場景的具體實例，差異在於本案例的兩條路徑都是寫入路徑（三方合併與 full overlay 皆會修改本地檔案），並非「寫入 vs 唯讀報告」的分工，說明此根因不限於「寫入/報告」的二分，任何多路徑消費同一判準的場景皆可能發生。

## 診斷歷程：多次分析依集合名稱推論方向語意而誤判

事故追查初期，連續兩輪分析皆從識別符名稱 `PUSH_ONLY_EXCLUDE_PATTERNS` 直接推論「push-only」修飾的是排除**方向**——認定該集合本不該在 pull 端生效，pull 端生效即為缺陷，因而規劃修法方向為「讓 pull 傳遞該目錄」或「新增 `direction` 參數拆分 `should_exclude`」。第三輪分析起草時延續了同一前提，直到後續一輪獨立覆核前才被推翻。

**正確語意寫在名稱上方兩行的類型註解，前兩輪分析皆未讀到**：

```
# 類型 E - Push-only exclude（git tracked 但不跨專案同步）
# 這些名稱在 sync push/pull 時排除，但不加入 .gitignore（專案要 git track）。
PUSH_ONLY_EXCLUDE_PATTERNS = frozenset({
    "project-integration",  # 各 skill 的專案落地層（per-project 案例/Hook 對齊/CLI 接線）
})
```

「Push-only」修飾的是排除**類型**（與 `LOCAL_ONLY_PATTERNS` 相對——後者同時要求 `.gitignore` 涵蓋，前者不要求），不是排除**方向**。註解明文「sync push/pull 時排除」即雙向語意，且成員註解「per-project」進一步說明這是刻意不跨專案同步的落地層內容。後續獨立覆核類型註解、成員註解、README 明文、架構設計（同檔另一判定函式有 `direction` 參數而 `should_exclude` 刻意沒有）等多項證據後判定：雙向排除是設計意圖，前序分析的方向語意推論本身是誤判，真正的缺陷是本 pattern 記載的路徑處置不一致。

**教訓**：識別符名稱是壓縮過的線索，不是語意本身。判斷一個集合的排除方向或適用範圍時，必須連帶讀取名稱上下緊鄰的類型/分類註解與成員註解，不能只靠名稱字面推論；命名可能是歷史遺留（此案例的類型分類系統早於方向語意被關注），與當前行為的對應關係需要靠註解與程式碼行為雙重覆核。

## 解決方案

修復方式為在 `cleanup_stale_files` 與 `sync_directory` 兩處各加入 `if should_exclude(rel): continue` guard clause，使 full overlay 路徑與三方合併路徑對 `PUSH_ONLY_EXCLUDE_PATTERNS` 的處置一致（per-project 目錄兩條路徑皆不刪除、不覆蓋）。**不改 `should_exclude` 本身**——集合定義與判定邏輯已正確，缺陷純粹在消費端。

修復過程額外發現一個隱藏的第三個消費落點：`sync_directory` 對「本地完全不存在的新目錄樹」會走 `shutil.copytree` 整批複製捷徑，該捷徑用 `shutil.ignore_patterns` 只按裸名稱比對固定清單，不會逐層呼叫 `should_exclude`，新目錄樹若巢狀含 `project-integration/` 仍會被整批帶入。修復方式為新增一個包裝函式，產出與 `shutil.copytree` 相容的 `ignore` callback，在走訪每一層時重建正確的相對路徑後才交給 `should_exclude` 判斷——同一個「消費點」實際上藏了主迴圈與捷徑分支兩個入口，兩者都要修，只改前者仍會漏放。

## 預防措施

- 新增或維護排除／過濾／豁免類集合時，先列舉所有消費該集合的路徑（可用 `rg -n "should_exclude\(" <腳本>` 之類的計數指令列出呼叫點清單），逐一確認每條路徑是否套用，而非只驗證「集合定義本身正確」
- 新增一個會走訪同一批資料的路徑（清理、同步、預覽、報告）時，先問「這批資料是否已有其他路徑套用排除政策」，有則同批加入同樣的判定，不留給下一次事故發現
- 對「批次複製/清理」類函式，檢查是否存在整批處理的捷徑分支（如 `shutil.copytree`、`os.walk` 提前剪枝）——捷徑常繞過主迴圈的逐項判定，形成同一函式內的第二個消費落點
- 判斷識別符語意（尤其是方向、範圍、類型）時，讀取名稱緊鄰的類型註解與成員註解，不憑名稱字面推論；有跨輪分析時，優先覆核前序分析是否已讀過這些註解
- 集合套用的消費點清單應可被列舉並固化為測試斷言（如「對同一組 fixture 輸入，三方合併路徑與 full overlay 路徑的排除結果必須一致」），單靠人工審查無法持續攔住新路徑遺漏

## 關聯

- `ARCH-BAL-017` — 同根因家族的一般化架構模式（排除政策只在部分路徑生效，其餘路徑零知識），本案例為 sync-pull 場景的具體實例
- `ARCH-BAL-009` — 同批修復發現的相鄰缺口：full overlay 的 dry-run 預覽同樣不呼叫 `should_exclude`，使預覽訊息與實際執行結果不一致（已記錄為待評估技術債，未隨本修復一併處理），屬「預覽路徑與執行路徑各自判定」的同根因分支
- `IMP-BAL-002` — 同屬「狀態/判定未綁定實際消費路徑」根因家族的另一實例（該案例是 base SHA 推進未綁定 delta 是否套用成功，本案例是排除判定未綁定所有消費路徑）
- `tarrragon/claude#50` — 框架層 canonical issue（sync 排除契約散落多處獨立實作），本 pattern 記載的路徑處置不一致為該 issue 涵蓋的具體症狀之一，完整調查脈絡與修法追蹤見該 issue
- 實證：某 consumer 專案 sync-pull 時，`references/project-integration/` 7 檔被 `cleanup_stale_files` 刪除；修復測試涵蓋三個消費落點（三方合併路徑不受影響、full overlay 兩條路徑加入過濾、copytree 捷徑巢狀過濾回歸）
