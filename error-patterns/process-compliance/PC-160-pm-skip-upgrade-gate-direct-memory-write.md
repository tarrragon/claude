# PC-160: PM 跳過升級評估閘門直接寫 memory 處理 session 浮現洞察

> **錯誤類別**：流程合規（quality-baseline 規則 5「所有發現必須追蹤」解讀偏差）
> **嚴重度**：中（洞察可能停留 memory 不升級為 framework 資產，跨 session 復用受限）
> **本檔定位**：**PC-061 的 v2 實證案例 + session 浮現洞察情境的 specific 防護**。一般 memory 升級盲區的症狀、根因、防護措施請參考 PC-061；本檔僅補充 PC-061 未涵蓋的「session 內浮現洞察」情境差異與五步驟防護。

---

## 主指向

**主要 error-pattern**：[PC-061: Memory 寫入後未評估升級為框架規則](PC-061-memory-upgrade-blindness.md)

PC-061 已完整描述「memory 寫入後未升級為框架」的症狀、四大根因（認知摩擦差 / 邊界判斷缺失 / 工具提示偏向 / 依賴用戶介入）、防護措施（規則 7 / continuous-learning skill / hook / 歷史債務清理 / 回填）與自我檢查清單。

**本檔差異**：PC-061 案例 1-2 聚焦「原則類 memory 升級延遲」（識別正確但升級步驟未發生）；本檔 v2 案例聚焦「session 內浮現洞察的處理路徑」——PM 在 ticket 執行過程中發現洞察時，第一動作即跳過評估閘門直接寫 memory，連「識別 → 待升級」的中間狀態都不存在。

---

## v2 實證案例：W3-028.2 → W3-058

| 階段 | 動作 | 評估 |
|------|------|------|
| W3-028.2 實機驗證完成 | PM 發現「實驗工具觀察自身執行循環」設計洞察（diagnostic hook 被 PM session /clear 觸發產生非實驗目的紀錄） | OK |
| PM 第一輪處理 | (a) 補入 ticket md Test Results 章節「實驗工具自指涉觀察」小節 (b) Write memory `feedback_experiment_tool_self_observation.md` (c) 更新 MEMORY.md (d) commit `a266807a` | (a) OK；(b/c/d) 違反：跳過升級評估閘門 |
| 用戶糾正 | 「這應該新增一個 ticket，評估是否應該補充相關處理的方法或者規則」 | 用戶識別出 PM 跳過閘門 |
| 補救 | 建 W3-058 ANA ticket，acceptance #4「評估方法論補強：檢視 PM 將 session 內浮現的洞察直接寫入 memory 是否跳過升級評估閘門，若是則建議補強流程」 | 補建閘門 |
| W3-058 ANA 結論 | 確認 PC-160 = PC-061 同模式 v2 案例；改為 cross-reference 而非合併刪除（PC-061 已被多處引用，合併維護成本高） | 知識債 cross-ref 重構 |

> 完整時間軸見 W3-028.2、W3-058 ticket md 與 commits `a266807a`（直接寫 memory）、`7d09c3bd`（補建 ANA）、`f0dddc37`（W3-058 ANA complete）。

---

## Session 浮現洞察的 specific 防護五步驟

PC-061 防護措施聚焦「memory 寫入時的四問檢查」（跨專案適用？屬哪類？升級至哪？是否已升級？）。本檔針對「session 內浮現洞察」情境，補充五步驟流程，**填補 PC-061 自我檢查清單觸發前的「識別 → 處理」缺口**：

1. **寫 ticket md 章節**（OK，屬 ticket 內容固化，無需評估）
2. **評估跨 session 適用性**：自問「下一個 session 接手任何 ticket 時，這個洞察會有用嗎？」
3. **若跨 session 適用 → 建 ANA ticket 評估升級路徑**（含「該屬 rule / methodology / skill / memory 何者」評估）
4. **ANA 評估結論決定歸屬**：
   - 「memory 即可」→ 寫 memory feedback（此時才走 PC-061 四問檢查）
   - 「升級為 rule / methodology / skill」→ spawn IMP/DOC ticket
   - 「不需追蹤」→ 文件化評估理由後結案
5. **禁止「跳過步驟 3-4 直接寫 memory」**（本檔的核心違規模式）

### 識別觸發條件

PM 在以下情境準備寫 memory 時應停下檢查：

| 觸發 | 動作 |
|------|------|
| 想 Write 到 `.claude/projects/.../memory/feedback_*.md` 處理 session 內剛浮現的洞察 | 先問「已建 ANA 評估？」若無則停止，走步驟 3 |
| 想 Write 到 `.claude/projects/.../memory/project_*.md` 處理 session 內剛浮現的洞察 | 同上 |
| commit 訊息含「補 memory feedback」或「update MEMORY.md」且洞察來源是本 session | 確認是否有對應 ANA ticket 連結 |
| 用戶提問「這部份記錄了嗎？」 | 警惕：可能正觸發本模式 |

---

## 相關條目

- **PC-061**：本檔的主要 error-pattern（memory 升級盲區的完整論述）
- **W3-058**：ANA 評估「實驗工具自指涉觀察」升級路徑 + 確認 PC-160 = PC-061 v2 案例的 source ticket
- **W3-028.2**：v2 source 洞察的 ticket（自指涉觀察小節）
- **W3-061**：本檔 cross-reference 重構 ticket
- **quality-baseline 規則 5/6**：所有發現必須追蹤 + 失敗案例學習原則
- **continuous-learning skill**：memory 升級評估的動態觸發機制（被本 PC v2 案例識別為可繞過）
- **memory feedback `feedback_skip_upgrade_gate_directly_writing_memory.md`**：本 PC 對應的 memory 條目
- **相關方法論**：[`.claude/methodologies/hook-system-methodology.md`](../../methodologies/hook-system-methodology.md) § 6「觀察類工具的雙重身份設計」（W3-028.2 浮現洞察 → W3-058 ANA → W3-059 升級落地的完整鏈條，本 PC 防護五步驟的成功應用範例）

## Last Updated

2026-05-26 / PC-160 v2.0（改為 PC-061 v2 案例 cross-reference stub，W3-061 落地）
