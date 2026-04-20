# PC-103: 大型類比框架分析時漏排比較維度

## 基本資訊

- **Pattern ID**: PC-103
- **分類**: 流程合規（process-compliance）
- **風險等級**: 中（僅在用大型系統做類比分析時觸發）
- **相關 Pattern**: PC-066（decision quality autopilot）、PC-080（WRAP A 框架測試）、PC-102（ROI 表遺漏）

---

## 問題描述

### 症狀

使用大型系統（Linux/POSIX、資料庫 ACID、OSI 七層等）作為類比框架分析目標系統時，PM 擷取「表面相關」的維度（例如 Linux process lifecycle 裡的 fork/exec/waitpid），漏掉同等重要但較不顯眼的層級（如 scheduler/IPC/memory management），造成類比表覆蓋不全。

結果：分析結論看似完整，實際遺漏關鍵維度；遺漏項需外部人員（用戶、code reviewer）查問才察覺。

### 典型徵兆

- 類比表有 10+ 項對應，但全集中在某 2-3 個子系統（例如 process lifecycle）
- 用戶追問「X 改進設計有嗎？」時才察覺漏了某維度
- 遺漏維度對應的修復方向沒建 ticket

---

## 根因分析

### 直接原因

類比思維在發散階段被「字面相似」的概念拉走（fork vs Agent 派發極直觀），收斂時未自檢「類比的原系統還有哪些大層級未被對應」。

### 深層原因

| 類型 | 說明 |
|------|------|
| A 發散被刻板錨定 | 提到 Linux process，PM 腦中率先浮現 fork/exec/waitpid；scheduler/IPC 觸發頻率低不被啟動 |
| B 收斂無全景 checklist | 類比完成後未列「原系統大層級清單」做覆蓋性檢查 |
| C 類比量尺不完整 | W17-004.1 產出 8 項 POSIX 成功模式為量尺，但量尺本身聚焦「介面設計」不含「scheduling/runtime 管理」 |
| D WRAP 未對「維度完整性」做框架測試 | PC-080 要求 WRAP A 階段做框架測試，但未明確要求「類比覆蓋全層級」 |

---

## 防護措施

### 類比完成後 checklist

以 Linux 為例，類比表完成後必檢以下層級是否皆對應：

| Linux 大層級 | 必檢項目 |
|-------------|---------|
| 1. Process lifecycle | PCB / fork / exec / wait / exit |
| 2. Scheduler | runqueue / schedule() / priority / nice |
| 3. IPC | signal / pipe / socket / shm |
| 4. Memory management | address space / mmap / page fault / swap |
| 5. File system | /proc / /dev / path resolution |
| 6. Security / permissions | uid / gid / capabilities |

每層級至少標記「有對應」「無對應（理由）」「待分析」其中之一；不可留空。

### 其他類比框架的對應 checklist

| 框架 | 層級清單 |
|------|---------|
| POSIX 介面 | man page / errno / syscall / command line / file ops / I/O / signals |
| OSI 七層 | Physical / Data Link / Network / Transport / Session / Presentation / Application |
| ACID | Atomicity / Consistency / Isolation / Durability |
| MVC | Model / View / Controller / (Routing) / (Service) |

### 整合 WRAP 框架

類比完成進入收斂時，WRAP A 階段（Attain distance）應主動執行「Vanishing dimension test」：
- 「若某維度從類比中消失，會失去什麼洞察？」
- 若答案是「很多」，代表該維度必須包含在類比表中

---

## 觸發案例

### W17-001 類比表漏排 scheduler 層（本 Pattern 發現案例）

W17-001 Linux 類比表覆蓋：
- Process lifecycle: PID / PCB / fork / exec / waitpid / zombie
- IPC: signal（類比 append-log）
- Memory: mm_struct / page fault（隱喻 PCB 半填）
- 介面: /proc / ELF / argv / ARG_MAX

**漏排**：
- **Scheduler 層**：runqueue / schedule() / TASK_RUNNING / nice / top — 完全沒對應
- 後果：修復方向表僅 4 項（C PCB 自動化 / A dispatch-check / waitpid / signal），用戶追問「任務鏈串連執行順序」才建 W17-009 補 scheduler 層

**ROI 影響**：若 scheduler 層先被識別，W17 Wave 修復順序會不同（W17-009 的 `ticket track next` 實作對日常 PM 派發影響比 W17-007 waitpid 更大）。

---

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-080 | WRAP A 階段要求框架測試；PC-103 是其「維度覆蓋」子情境 |
| PC-066 | Context 重時決策易用刻板錨定；PC-103 是刻板錨定的類比具體表現 |
| PC-102 | ROI 表條目遺漏；PC-103 是更早一步的遺漏（維度層級遺漏導致整層 ROI 條目缺席）|
| PC-101 | 並行代理人仲裁可反向防護——若三個視角各看不同層級，矛盾反而暴露漏排 |

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17-001 類比漏排 scheduler 層案例建立
