# IMP-072: ticket create 並行執行時 ID 分配 race condition

## 基本資訊

- **Pattern ID**: IMP-072
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-12
- **風險等級**: 中
- **影響範圍**: `.claude/skills/ticket/ticket_system/commands/create.py`

---

## 問題描述

### 症狀

PM 在單一 session 中並行執行 2+ 個 `ticket create` 命令（如 background bash），兩個命令同時讀取「最新 ticket 編號」並各自 +1，最終分配到**同一個 ID**。後執行的 commit 會 overwrite 先執行的 commit 內容。

### 表現形式

| 階段 | 行為 |
|------|------|
| t=0 | 兩個 bash 同時讀取最大編號為 N |
| t=1 | 兩個 bash 各自寫入 N+1.md（無 file lock）|
| t=2 | 後完成的 process overwrite 前一個的內容 |
| 通知 | 兩個 bash 都通知 `completed exit 0` |
| 結果 | 檔案系統只剩 1 個 N+1.md（內容是後者）|

---

## W10-105 ANA 收尾案例

### 時序

1. PM W10-105 ANA 結論需建 2 個 spawned IMP（hook accessibility + CLI/schema 對齊）
2. PM 並行派發 2 個 background bash `ticket create`：
   - bash bi43cud13: hook accessibility IMP
   - bash b6uyaczhp: CLI/schema 對齊 IMP
3. 兩個 bash 都通知 completed exit 0
4. ls 只看到 `W10-107.md`，內容為「CLI/schema 對齊」（後執行的 b6uyaczhp 內容）
5. 第一個 bash 的「hook accessibility」內容被 overwrite 遺失
6. PM 重新 serial 執行第一個 ticket create，建出 `W10-108.md`

### 證據

- `cat b6uyaczhp.output` 顯示 Context Bundle 抽取成功訊息
- `cat bi43cud13.output` 顯示同樣 Context Bundle 抽取訊息
- `ls` 只有 W10-107.md（內容對應 b6uyaczhp）
- 重新 serial 執行才建出 W10-108.md

---

## 根因分析

### 直接原因

`ticket create` 分配 ID 流程：

```
1. 掃描 docs/work-logs/.../tickets/ 找最大編號 N
2. 設定新 ticket 為 N+1
3. 寫入 N+1.md
```

步驟 1-2 與步驟 3 之間無 atomic lock，並行執行時：

- Process A: 讀 N=106 → 設定 ID=107 → 寫 107.md
- Process B: 讀 N=106（同時）→ 設定 ID=107 → 寫 107.md（overwrite A）

### 深層原因

| 動機類型 | 表面說法 | 深層動機 |
|---------|---------|---------|
| A 設計假設 | 「ticket create 是低頻操作」 | 未考慮並行 PM 派發場景 |
| B 缺乏並行測試 | 「單機開發無 race condition」 | 測試覆蓋不涵蓋並行 create |
| C 缺 file lock | 「Python file lock 跨平台不一致」 | 避難式設計而非正面解決 |

---

## 防護機制

### 修補方向

| 方案 | 描述 | 成本 |
|------|------|------|
| A. fcntl/lockfile 原子化 | 在 ID 分配 + 寫入之間加 file lock | 中（跨平台處理 fcntl vs msvcrt）|
| B. ID 預留 + retry | 寫入前 atomic test-and-set；衝突則 retry 下一 ID | 中-高 |
| C. PM 規則禁止並行 create | 規則層約束 PM 序列化 create | 低（但靠自律）|
| D. 編號改為 UUID | 完全消除 race | 高（破壞性變更，影響 ID 可讀性）|

推薦：**A**（fcntl-based file lock）+ **C**（規則層補強）雙層防護。

### PM 層 workaround

當前 v0.18.0 在修補前，PM 應：

- **禁止並行 `ticket create`**：多 ticket 一次只能序列建立
- **驗證新建 ticket 存在性**：每次 create 後 `ls -t .../tickets/*.md | head -1` 確認新檔
- **避免 background bash 並行 ticket create**：用 foreground bash 序列執行

---

## 與其他 race condition 的差異

| 場景 | 鎖機制 |
|------|--------|
| git index.lock（PC-139）| git 自帶 lock 但跨 process 競爭 |
| sqlite WAL | DB 層原子化 |
| ticket create | **無 lock**（本 IMP）|

---

**Last Updated**: 2026-05-12
**Version**: 1.0.0
**Source**: W10-105 ANA 收尾時並行派發 2 個 ticket create 撞 ID（bi43cud13 vs b6uyaczhp），實際只建出 W10-107（後者內容），前者內容遺失需 serial 重建為 W10-108
