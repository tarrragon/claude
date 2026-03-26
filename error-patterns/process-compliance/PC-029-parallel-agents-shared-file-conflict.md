# PC-029: 並行代理人修改同一檔案導致衝突和 linter 擴散

## 錯誤編號
PC-029

## 分類
process-compliance

## 症狀

1. **共用檔案衝突**：4 個並行代理人中，W3-003.1 和 W3-004 都修改 test-setup.js，W3-005.1 和 W3-006 都修改 ErrorCodes.js 相關檔案。git checkout 還原 W3-006 的意外修改時，連帶還原了 W3-003.1 和 W3-005.1 的目標修改。
2. **Linter 意外擴散**：W3-006 代理人觸發了 linter，自動修改了 82 個非目標檔案（tests/ 目錄下的 import 路徑格式化），導致測試從 4135 通過暴跌至 3940 通過（7 個 suite 失敗）。
3. **git index.lock 殘留**：W3-006 代理人大量操作後產生 .git/index.lock，阻擋後續 git 操作。

## 根因

1. **派發時未分析檔案所有權重疊**：主線程派發 4 個並行代理人時，未確認它們修改的檔案是否互斥。test-setup.js 和 ErrorCodes.js 是多個代理人的共用修改目標。
2. **代理人無法控制 linter 範圍**：PostToolUse hook 中的 linter 對整個 tests/ 目錄執行格式化，而非只對修改的檔案執行。
3. **git checkout 是粗粒度還原**：按檔名還原時無法區分「同一檔案中不同代理人的修改」。

## 影響

- 需要額外派發代理人重新套用被還原的修改（W3-003.1 + W3-005.1）
- 浪費約 10 分鐘排查和還原
- Context 空間被大量 git status 和還原操作消耗

## 解決方案

1. git checkout 還原非目標檔案後，重新派發合併代理人恢復目標修改
2. rm .git/index.lock 解除 git 鎖定
3. 最終測試 4136 通過、0 失敗

## 預防措施

### 規則：並行代理人必須修改互斥的檔案集

| 步驟 | 動作 |
|------|------|
| 1 | 派發前列出每個代理人預計修改的檔案清單 |
| 2 | 檢查是否有交集（特別是 test-setup.js、配置檔等共用檔案） |
| 3 | 有交集 → 序列執行或合併為同一代理人 |
| 4 | 無交集 → 可安全並行 |

### 高風險共用檔案清單

- `tests/test-setup.js` — 全域 mock 和環境設定
- `src/core/errors/ErrorCodes.js` — 錯誤代碼常數
- `src/core/errors/index.js` — 錯誤模組匯出
- `package.json` — 專案配置

### Linter 擴散防護

- 代理人執行大量修改前，應先 `git stash` 或在 worktree 中隔離
- 或：限制 linter 只對 git diff 中的檔案執行

## 關聯 Ticket

- 0.15.0-W3-003.1（修改 test-setup.js）
- 0.15.0-W3-004（修改 test-setup.js）
- 0.15.0-W3-005.1（修改 ErrorCodes.js）
- 0.15.0-W3-006（修改 StandardError + UC 適配器，觸發 linter 擴散）

## 相關錯誤模式

- ARCH-004: 任務拆分檔案所有權重疊
- PC-018: 並行代理人重疊後續 Ticket

## 發現日期

2026-03-27

## 發現者

主線程（還原 W3-006 意外修改時發現）
