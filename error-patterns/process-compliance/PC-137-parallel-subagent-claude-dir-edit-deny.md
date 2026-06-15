# PC-137: 並行派發 subagent 對 `.claude/` Edit 觸發 runtime deny

**類別**: process-compliance
**嚴重度**: Medium
**首次發現**: 2026-05-10（W17-177 ANA 收斂）
**相關**: PC-115（主 error pattern，調查全紀錄）、ARCH-015、W17-097、W17-108、W17-110、W17-154、W17-177、W17-177.1

---

## 症狀

並行派發 3+ subagent 同時對 `.claude/` 下任意檔案做 Edit/Write 時，CC runtime 觸發 hardcoded deny。表現：

1. 標準 CC 模板 deny 訊息（「Permission to use Edit has been denied」）
2. 無 hook stderr 訊息、無 `.claude/hook-logs/` 紀錄
3. 所有 PreToolUse hook 顯示 allow，settings 三層權限均允許
4. PM 主線程接手手動 Edit 同檔可成功，subagent 序列重試也成功
5. 並行愈多，deny 機率愈高（7/7 並行 deny vs 18/18 非並行 success — W17-177 樣本）

---

## 根因

CC runtime 對 subagent 並行 Edit `.claude/` 存在保護層，超出 hook 與 permissions 配置可見範圍。並行派發本身為觸發因子，與檔案類型（hook .py / pm-rules .md / error-patterns .md 等）、cwd（主 repo vs worktree）、agent frontmatter（permissionMode: bypassPermissions 亦不繞過）無關。

對照組實驗（非並行單發 thyme 對 `.claude/` Edit）尚未執行（W17-177 AC5 deferred），故並行假設證據強度為「中等」而非「強」；可能仍有與並行高度相關的其他變因未識別。

---

## 案例

| 案例 | 派發數 | 結果 | 來源 |
|------|-------|------|------|
| W17-097.1-.4 | 4 並行 thyme（`.claude/skills/ticket/`） | 4/4 deny | PC-115 base rate 觀察前 baseline |
| W17-174.2.1/.3/.4 | 3 並行 thyme（`.claude/hooks/`、`.claude/pm-rules/`、`.claude/error-patterns/`） | 3/3 deny | W17-154 trigger 達標案例 |
| W17-108/109/110.1-.4 + 其他 | 非並行系列 | 18/18 success | PC-115 Base Rate 觀察 |

---

## 防護

### 強制（已落地 W17-177.1）

`.claude/pm-rules/parallel-dispatch.md` §`.claude/` 修改類並行數限 ≤ 2：

| 並行數 | 處理方式 |
|-------|---------|
| 1 | 序列派發，無限制 |
| 2 | 允許並行；確認檔案邊界互斥 |
| 3+ | 拆 batch（每批 ≤ 2）或改序列；緊急豁免需在 dispatch-plan 註明並接受 deny 風險 |

### 觀察（W17-154 trigger 計數機制）

PC-115「Deny 事件累積」表持續追蹤；若 ≤ 2 並行仍出現 `.claude/` Edit deny，trigger 重啟調查並執行 W17-177 AC5 對照組實驗區辨「並行假設」vs 未識別變因。

### 派發前自查

派發 `.claude/` 修改類 ticket 前 PM 自問：

- [ ] 同時派發數 ≤ 2？
- [ ] 若 > 2，已拆 batch 或改序列？
- [ ] dispatch-plan 已記錄並行策略？

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-115-subagent-claude-dir-edit-runtime-deny-without-log.md` — 主 error pattern，含完整調查歷史、候選假設表、Base Rate 觀察、Deny 事件累積
- `.claude/pm-rules/parallel-dispatch.md` §`.claude/` 例外 + §`.claude/` 修改類並行數限 ≤ 2 — 強制防護
- `.claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md` — CC runtime 保護層理論基礎

---

## bgIsolation: none 例外（受控實驗驗證）

並行 ≤ 2 規則為 bgIsolation: worktree（預設）模式下的觀察結論。bgIsolation: none 模式下的並行行為已透過受控實驗驗證為不同模式。

**並行受控實驗結果**：bgIsolation: none + 並行 3 subagent + `.claude/` Edit → **3/3 success**，0/3 deny。 <!-- PC-093-exempt: history:0.19.0-W3-034.4 為實驗驗證歷史錨點 -->

**新規則**：

| 模式 | 並行 `.claude/` 修改限制 |
|------|----------------------|
| bgIsolation: worktree（預設） | **≤ 2**（原規則維持，W17-097.1-.4 + W17-174.2.1/.3/.4 7/7 deny 證據） |
| bgIsolation: none | **未受並行數限制**（單一 + 並行 3 已驗證 success），但仍受 git index 競爭風險限制 |

**未驗證情境（仍需謹慎）**：

- bgIsolation: none + 並行 + git add / commit（PC-092 共享 index 風險未測）
- bgIsolation: none + 並行 5+ subagent（更高並行度未測）

**Action 更新**：

| 並行數 | bgIsolation: worktree | bgIsolation: none |
|-------|----------------------|------------------|
| 1 | 序列派發，無限制 | 序列派發，無限制 |
| 2 | 允許並行；確認檔案邊界互斥 | 允許並行；同左 |
| 3+ | 拆 batch（每批 ≤ 2）或改序列 | 允許並行 Edit；但 commit 仍需精準 staging |

---

**Last Updated**: 2026-05-26
**Version**: 1.1.0 — 並行受控實驗驗證 bgIsolation: none 模式下並行限制例外（W3-034.4 落地） <!-- PC-093-exempt: history:0.19.0-W3-034.4 為實驗驗證歷史錨點 -->
**Version**: 1.0.0 — 從 W17-177 saffron ANA 收斂落地（W17-177.1 IMP 防護的反模式描述層）
