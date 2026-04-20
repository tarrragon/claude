# PC-102: ANA Solution 修復方向表未逐項轉 spawned ticket

## 基本資訊

- **Pattern ID**: PC-102
- **分類**: 流程合規（process-compliance）
- **風險等級**: 高（ANA 結論看似完整實則追蹤遺漏）
- **相關 Pattern**: PC-100（PCB 未繼承 source）、規則 5（所有發現必須追蹤）

---

## 問題描述

### 症狀

ANA ticket 的 Solution 列出 N 項修復方向（ROI 排序表或 P0-P3 清單），但 PM 僅將部分條目轉為 spawned ticket，其餘條目在文字上存在但無實際追蹤機制。ANA complete 後，未建 ticket 的條目沉沒於 Solution 內文，需用戶或外部查問才能浮現遺漏。

### 典型情境

- ANA Solution 列 4+ 項修復方向
- PM 建 2 個 spawned IMP/ADJ（優先 1、2）
- 優先 3、4 被視為「結論的一部分」未轉 ticket
- 用戶數輪對話後才查問「X 機制有建 ticket 嗎？」

---

## 根因分析

### 直接原因

PM 整合 ANA Solution 後注意力轉移，未完成「逐條目 → spawned ticket」的機械性對照。

### 深層原因

| 類型 | 說明 |
|------|------|
| A 注意力轉移 | Solution 寫完 PM 即進下一任務；「逐項建 ticket」是另一步驟常被忽略 |
| B 表格認知負擔 | 4+ 項條目同時呈現，PM 實際只處理前 1-2 項 |
| C 缺 CLI 檢查 | 無「Solution 表格項數 vs spawned/related ticket 數」一致性檢查 |
| D 規則 5 覆蓋盲區 | 「所有發現必須追蹤」強調頂層 ANA 發現，未明確 cover 「ANA Solution 內部子條目」層級 |
| E Hook 未介入 | acceptance-gate-hook 僅檢查 spawned_tickets 存在性（≥1 即放行），未檢查數量是否對應 Solution 條目 |

---

## 防護措施

### PM 自律（立即可行）

1. ANA Solution 含修復方向表時，**立即**逐條目建 spawned ticket 或明確記錄豁免理由
2. Solution 表格每項加「追蹤狀態」欄位：
   ```
   | # | 修復 | 類比 | 成本 | 追蹤 |
   |---|------|------|------|------|
   | 1 | X | Y | ~Nh | W17-00X |
   | 2 | Y | Z | ~Nh | W17-00Y |
   | 3 | Z | W | ~Nh | **未建（理由：...）** |
   ```
3. ANA complete 前自檢：Solution 表格項數 = 已建 ticket 數 + 明確豁免數

### 系統性（遠期）

新增 CLI `ticket track audit-ana <id>` 掃 Solution markdown 表格，比對 spawned_tickets + related_to 欄位，找出未追蹤條目並回報。

---

## 觸發案例

### W17-001 修復方向表遺漏（本 Pattern 發現案例）

W17-001 Solution 列 4 項修復方向：
1. C Context Bundle 自動化 → 建 W17-002 IMP（已 cover）
2. A dispatch-check 安全網 → 建 W17-003 ADJ（已 cover）
3. **Exit code 標準化（waitpid）→ 未建**
4. **Signal 通道（SIGUSR1）→ 未建**

PM 整合 Solution 後直接進下個任務，方向 3、4 僅在表格文字呈現。用戶於數輪對話後查問「主線程仰賴 polling 的改進設計」才察覺遺漏，補建 W17-007 ANA 處理。

---

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-100 | 都是「ANA 衍生任務建立不完整」類型；PC-100 聚焦「衍生 ticket PCB 空殼」，PC-102 聚焦「衍生 ticket 應建而未建」 |
| 規則 5 | PC-102 是規則 5 的具體子場景（ANA Solution 內部條目應全部追蹤） |

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17-001 修復方向遺漏案例建立
