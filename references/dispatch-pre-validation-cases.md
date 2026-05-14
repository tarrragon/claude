# 派發前假設驗證案例集

本檔記錄 PM 派發 IMP 前驗證 ANA 結論關鍵假設的具體案例，作為「派發前假設驗證」機制的對照參考。

> **入口**：`.claude/pm-rules/dispatch-gate.md` 關卡三 / `.claude/skills/wrap-decision/SKILL.md` R.2
> **背景**：本機制源於 W10-140 第四輪 4 視角分析，融合 saffron 切入點 + ginger 按需 + bay tripwire 警告

---

## 何時觸發假設驗證

PM 派發 IMP 前，若任一條件成立，必須執行假設驗證：

| 觸發條件 | 範例 |
|---------|------|
| ANA 結論依賴未驗證的事實宣稱 | 「Hook 已強制執行 X」「函式 F 已存在」「rules 已涵蓋 Y」 |
| 動作不可逆且影響範圍 > 單檔 | 刪除 `.claude/rules/` 內檔案、修改 auto-load 入口、改變 hook 行為 |
| 觸碰 auto-load 層 | 任何 `.claude/rules/core/` 修改、CLAUDE.md 引用變更 |
| ANA 含 dissenting view 警告 | parallel-evaluation 駐委員 / devil's advocate 對某假設提出疑慮 |

---

## 驗證動作模板

| 假設類型 | 驗證指令 |
|---------|---------|
| 「Hook X 已強制執行 Y」 | `grep -A 10 "exit\|behavior" .claude/hooks/<hook>.py` 確認 exit code 與阻擋行為 |
| 「檔案 / 函式 / 章節 X 存在」 | `ls / grep / wc` 直接確認 |
| 「規則 X 已涵蓋場景 Y」 | `grep -rn "Y" .claude/rules/ .claude/pm-rules/` |
| 「ANA 結論 X 適用於本案」 | 讀 ANA Solution + 對照本案具體條件 |

---

## 案例 1：W10-137 — Hook 強制狀態驗證

**情境**（2026-05-14）：

W10-134 第二輪 linux 結論建議「P0：刪除 `.claude/rules/core/ticket-skill-sync-check.md`」，理由：「對應 hook 已強制執行 + 0 PC 引用 = 安全刪除」。

**bay devil's advocate 警告**（W10-134.7）：「unknown unknowns 風險」「prose rules 同時是規範 + 教育材料」。

**主線程派發前驗證指令**：

```bash
grep -A 10 "exit\|behavior" .claude/hooks/ticket-skill-sync-check-hook.py
```

**驗證結果**：

| 項目 | linux 假設 | 實際 |
|------|---------|------|
| Hook 存在 | 是 | 是 |
| Hook 行為 | 「強制執行」（阻擋）| **「輸出 INFO 提示，不阻擋 commit」（exit 0）** |
| 刪除 prose 後果 | 「無影響」 | **PC-066 自律失效風險（PM 收提示但缺 prose 解釋「為何」）** |

**修正動作**：

W10-137 IMP 範圍從「刪除 ticket-skill-sync-check.md」調整為「移到 references/，rules/core 留 stub」（同 pm-role.md v4.0.0 的 73% 裁剪模式）。

**結果**：保留 prose 教育價值（避免 PC-066 風險），同時實現 -19.3% rules/core 縮減 / -5.5K tokens 節省。

**關鍵教訓**：

- ANA 結論的關鍵假設（如「Hook 已強制」）若未經主線程驗證，可能引入 PC-066 自律失效模式
- bay devil's advocate 警告在具體案例層需要主線程實證驗證才能確認適用度
- 驗證成本極低（一個 grep 指令），相對救援價值（避免誤刪 + 未來 N 次同模式）的 ROI 高

---

## 案例 2：W10-141 派發前驗證（自我示範）

**情境**（2026-05-14）：

W10-141 IMP「派發前假設驗證機制最小可行版本」涉及修改 wrap-decision SKILL.md / dispatch-gate.md / 新建 references/。派發 thyme-python-developer 前主線程執行假設驗證。

**驗證指令**：

```bash
grep -n "^## R\|R (Reality" .claude/skills/wrap-decision/SKILL.md  # 確認 R 階段存在
ls -la .claude/pm-rules/dispatch-gate.md                            # 確認檔案存在
ls -d .claude/references/                                           # 確認目錄存在
ls .claude/references/ | grep -i "dispatch\|pre-validation"        # 既有相關檔案
```

**驗證結果**：

| 假設 | 驗證 |
|------|------|
| wrap-decision SKILL.md 有 R 階段 | 通過（line 195 「## R — 現實檢驗」）|
| dispatch-gate.md 存在 | 通過（5167 bytes）|
| references/ 目錄存在 | 通過 |
| 既有 dispatch-* references | 補充發現（4 檔，避免重複造輪子）|

**結果**：所有假設通過，派發無修正。並補充發現「既有 4 個 dispatch-* references」需在實作中互引避免重複造輪子（saffron 第三輪共識）。

---

## 與既有 dispatch references 的關係

| 既有檔案 | 用途 | 與本檔關係 |
|---------|------|---------|
| `agent-dispatch-decision.md` | 派發代理人選擇決策 | 本檔處理「派發前假設驗證」，互補不重複 |
| `agent-dispatch-template.md` | 派發 prompt 模板 | 本檔關注「驗證環節」，模板用於「派發環節」 |
| `background-dispatch-rules.md` | 背景派發規則 | 互不重疊 |
| `parallel-dispatch-details.md` | 並行派發細節 | 互不重疊 |

**邊界**：本檔只記錄「派發前假設驗證」具體案例與動作模板，不涉及代理人選擇 / prompt 設計 / 並行策略。

---

## Tripwire（W10-140 仲裁設計）

**升級條件**（任一觸發即評估擴展）：

1. **30 天觀察期內**：W10-137 類事件 ≥ 3 次 → 評估升級加 D 強制（wrap-decision R.2 改強制問）
2. **6 個月內**：W10-137 類事件再爆 2 次 → 評估升級加 B 窄場景 hook
3. **規則超載閾值**：rules/core + pm-rules 總 checklist 項超 200 → 強制裁剪而非新增

**回滾條件**：

- 30 天內無 W10-137 類事件 → 本檔改 references-only（更輕）
- 機制造成 PM 自動駕駛跳過（PC-066 模式發生）→ 改純 self-audit（不再強制）

---

**Last Updated**: 2026-05-14
**Version**: 1.0.0 — 從 W10-140 第四輪 4 視角分析建立（W10-141 落地）
**Source**: W10-137 案例（首例）+ W10-140 PM 仲裁（融合 saffron / ginger / bay 視角）
