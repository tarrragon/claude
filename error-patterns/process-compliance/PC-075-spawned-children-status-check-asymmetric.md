# PC-075: spawned 與 children 狀態檢查語義不對稱

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-075 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-17（W11-005 收尾觀察 + W12-003 分析確認） |
| 姊妹模式 | PC-073（ANA spawned 誤用 children），本模式為 PC-073 副作用延伸 |

---

## 症狀

防護性 ANA Ticket（結論本身是「需要這些 IMP 落地才算解決問題」的類型）在 spawned IMP 仍為 pending/in_progress 時，仍能順利 `ticket track complete` 並通過 acceptance-gate-hook。

具體案例：
- W12-002（AUQ 污染調查 ANA）completed
- W12-002.1/.2/.3/.4（4 個防護 IMP）僅 .1 completed，.2-.4 pending
- W11-005 session 中污染仍然再現（用戶端顯示「补」）
- W11-005（多視角審查 ANA）completed + spawned=[W12-001 pending] — 本 ANA 自身也是實例

---

## 根本原因

### 已驗證事實

1. `acceptance_checkers/ana_spawned_checker.py` L62-95 `check_ana_has_spawned_tickets` 僅檢查 spawned_tickets **存在性**，不檢查狀態
2. `acceptance_checkers/children_checker.py` L111-156 `check_children_completed` 有完整狀態檢查 + 遞迴至孫層 + 循環檢測
3. 兩個 checker 對 `children` vs `spawned` 關聯套用不對稱語義

### 真根因

**PC-073 的副作用**：
- PC-073 教訓：ANA 衍生 IMP 用 `--parent`（children 關聯）會阻擋 ANA complete，分析者無法繼續下個任務
- 解法：改用 `source_ticket`/`spawned_tickets`（spawned 關聯）避免阻擋
- 副作用：**spawned 關聯完全失去狀態檢查**，防護性 ANA 無法強制落地

**設計層級問題**：
- children 被視為「強耦合」（父子任務鏈、狀態綁定）
- spawned 被視為「弱耦合」（存在即盡責）
- 兩種關聯在「結案門檻」上語義不對稱，但實際情境中有「弱耦合但需落地」的場景

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成問題 |
|---------|--------------|
| 「ANA 分析完當然可以 complete」 | 防護性 ANA 的結論是「必須 IMP 落地」，未落地就 complete 形同宣示 |
| 「spawned_tickets 欄位有值就代表承諾」 | 承諾無機制保證兌現；pending 永久 pending 仍算承諾？ |
| 「IMP 狀態由 IMP 自己管」 | ANA 產出的 IMP 清單是 ANA 的一部分；若 IMP 不執行則 ANA 結論失效 |
| 「警告即可，不需 block」 | warning fatigue 讓訊號被滑過（linux 視角），效果接近無防護 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Hook Phase 1 | W12-004 擴充 ana_spawned_checker 加 spawned 非 terminal 警告 + AcceptanceCheckResult 結構化欄位 | 待實作 |
| 架構 Phase 2 | W13-001 評估方案 E：修正 children 阻擋語義（ANA completed 允許、version close 檢查整體） | 待評估 |
| 規則 | quality-baseline 已有規則 5（所有發現必須追蹤），但追蹤 != 落地 | 部分達成 |

---

## 教訓

1. **關聯類型的語義邊界不能只看「阻擋」維度**：children 強耦合、spawned 弱耦合是正確的方向，但「強/弱」應該指「跨任務協調」不是「狀態檢查」。兩種關聯都應該在結案時做狀態驗證。
2. **補丁疊補丁是設計債**：PC-073 解決「ANA 被阻擋」是對的，但手段（改用 spawned）把問題推給下游 checker 設計。根本修復方向（方案 E）是把 ANA completed 與 children IMP pending 的共存做為一等設計，而非透過關聯類型迴避。
3. **警告層與封殺層的選擇判準**：warning fatigue 是真實風險。若訊號能 block 且不造成用戶體驗災難（ANA complete 並非頻繁動作），應優先選 block 而非 warn。

---

## 檢查清單（設計任何關聯類型 schema 時）

- [ ] 每種關聯的語義是否在「結案門檻」上一致？
- [ ] 若不一致，是否有明確設計理由（不是為迴避歷史問題）？
- [ ] 結案檢查是否覆蓋所有關聯類型？
- [ ] 警告 vs block 的選擇是否有 warning fatigue 觀察期計畫？

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-073-ana-spawned-misused-as-children.md` — 姊妹模式（本模式的反向副作用）
- `.claude/hooks/acceptance_checkers/ana_spawned_checker.py` — 缺口位置
- `.claude/skills/ticket/ticket_system/lib/constants.py` — `TERMINAL_STATUSES` 單一來源（W14-004 整併；hook 與 skill 共用）
- `.claude/hooks/acceptance_checkers/children_checker.py` — 子任務狀態檢查實作位置
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W12-003.md` — 雙線 ANA 分析
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W12-004.md` — Phase 1 警告層 IMP
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W13-001.md` — Phase 2 方案 E 評估 ANA

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0 — W11-005 收尾觀察 + W12-003 多視角 ANA 整合結論
**Source**: 用戶指出「子任務未完成，父任務不應被關閉，為什麼防護系統沒有阻止」；多視角審查（linux + feature-dev:code-reviewer）確認設計缺口
