# 反思終止閘門（Layer 3 PM 規則）

本文件定義反思流程的 PM 強制終止條件，是 three-phase-reflection-methodology 三層防護的 Layer 3。

> **三層防護概覽**：
> - Layer 1（質性）：three-phase-reflection-methodology.md「終止條件」章節
> - Layer 2（結構警示）：`ticket track deps` 鏈深度警示 + reflection-chain-depth-warn-hook.py（W15-021）
> - Layer 3（用戶閘門）：**本文件** — PM 行為強制 + AskUserQuestion 詢問終止
> - Layer 4（元條件保護）：直接寫入方法論，禁止再 spawn 終止條件的終止條件 ANA

---

## 反思終止閘門

### 觸發條件

PM 偵測到以下任一狀態時，**必須**執行 AskUserQuestion 詢問是否終止反思：

| 條件 ID | 觸發條件 | 偵測方式 |
|---------|---------|---------|
| T-S | session 內連續 ≥ 3 個 ANA Ticket | `ticket track list --status completed,in_progress` 計算本 session ANA 數量 |
| T-D | spawned_tickets 反思鏈深度 ≥ 3 | `ticket track deps <id>` 顯示 `[WARNING] 反思鏈深度 = N` |
| T-H | 單一主題 ANA 累計耗時 > 4 hr | 比較最早 ANA started_at 與當前時間 |

**說明**：
- T-S 針對 session 層級防護（廣度控制）
- T-D 針對衍生鏈深度防護（深度控制，與 Layer 2 Hook 銜接）
- T-H 針對時間成本上限（資源控制）
- 任一觸發即必須執行閘門，不等全部觸發

### AUQ 選項設計

觸發時使用 AskUserQuestion，標準選項如下：

| 選項 | 標記 | 說明 |
|------|------|------|
| 終止反思，切換到實作線 / handoff | Recommended | 繼續處理 W15-014/015/016/017 等 IMP 排隊任務 |
| 繼續反思（需說明理由） | — | 用戶需明示「還不夠深」的具體理由（非「感覺」） |
| /clear 結束 session | — | 若用戶已疲勞或需要重置 context |

**AUQ 頻率限制**：每個 session 同一反思主題最多觸發 1 次閘門詢問，避免疲勞轟炸。
觸發後若用戶選擇「繼續反思」，本 session 不再對同一主題重複詢問。

---

## 偵測流程

```
PM 準備建立或 claim ANA Ticket
    |
    v
計算 session ANA 數量（T-S 檢查）
    |
    +── ≥ 3 → 觸發閘門
    |
    v
執行 ticket track deps 確認鏈深度（T-D 檢查）
    |
    +── ≥ 3 → 觸發閘門
    |
    v
計算同主題最早 ANA started_at 至今（T-H 檢查）
    |
    +── > 4 hr → 觸發閘門
    |
    v
無觸發 → 繼續正常流程
```

---

## 與三層防護的整合

| 層 | 機制 | 強制性 | 來源 |
|----|------|--------|------|
| Layer 1 | 質性自檢：Phase 1/2/3 深度門檻 + 用戶明確表達「夠了」 | PM 自檢 | three-phase-reflection-methodology.md |
| Layer 2 | 結構警示：deps 指令 + Hook stderr 警示（≥ 3 層時） | 軟性訊號 | W15-021 實作 |
| Layer 3 | 用戶閘門：AskUserQuestion 三選一終止詢問 | **強制** | 本文件 |
| Layer 4 | 元條件保護：禁止 spawn 終止條件的終止條件 ANA | 方法論硬性 | three-phase-reflection-methodology.md |

**Layer 2 → Layer 3 銜接**：Layer 2 Hook 輸出 `[WARNING] 反思鏈深度 = N` 後，PM 必須在當次決策前執行本文件的 Layer 3 閘門流程（禁止忽略 Layer 2 警示繼續派發）。

---

## 失敗模式防護

| 失敗模式 | 防護機制 |
|---------|---------|
| 用戶因 AUQ 疲勞選錯「繼續」 | 閘門顯示具體鏈深度與 session ANA 數量，讓用戶有資料決策 |
| PM 忽略 T-D 因 Layer 2 訊號不顯眼 | Layer 2 輸出後 PM 必須回到本文件確認是否觸發 Layer 3 |
| 終止後發現仍有盲點 | 用戶可手動重開 ANA（本閘門非一次性鎖定，而是強制詢問） |
| 元遞迴：終止條件自身再被反思 | Layer 4 硬性禁止，直接修改方法論不另開 ANA |

---

## 相關文件

- `.claude/methodologies/three-phase-reflection-methodology.md` — Layer 1（質性終止條件）
- `.claude/pm-rules/decision-tree.md` — 路由表（本文件入口）
- W15-021 — Layer 2 Hook 實作（reflection-chain-depth-warn-hook.py）
- W15-010 — 終止條件設計 ANA（WRAP 分析來源）

---

**Last Updated**: 2026-04-18
**Version**: 1.0.0 — 初版，實作 W15-010 Layer 3 設計（反思終止閘門 PM 規則，三觸發條件 + AUQ 標準選項）
