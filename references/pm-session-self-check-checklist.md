# PM Session 結束自檢 Checklist

**版本**: v1.0.0
**建立日期**: 2026-04-28
**對應方法論**: `.claude/methodologies/pm-judgment-interference-map.md`（13 因子 × 6 層）
**對應 Ticket**: 0.18.0-W17-077（W17-075 IMP-D 落地）

---

## 用途

PM 在 session 結束前（或 `/clear` / handoff 前）以本 checklist 對照本 session 的判斷品質。

**Why**：13 因子 × 6 層干擾若不刻意盤點，會默默累積成跨 session 模式（PC-066 觀察到 context 沉重時 WRAP 觸發率下降至 20%；PC-111 觀察到 PM 被糾正後第一反應是淺層歸因而非分層挖因）。Session 結束前的結構化自檢將「干擾辨識」從反應式（被用戶糾正）轉為預防式（PM 自察）。

**Consequence**：跳過自檢會讓干擾因子隱藏在「以為還好」的主觀感受中，下個 session 仍以同樣模式運作。

**Action**：依 session 規模選擇快速版（3 分鐘）或完整版（10-15 分鐘）；輸出可直接貼入 handoff 檔或 memory feedback。

---

## 快速版（3 分鐘）

Session 結束前以最低代價檢視主要干擾觸發。輸出格式：6 層 × 「觸發 / 未觸發 / 不確定」三狀態。

```
[ ] 層 1 論述生成 — 是否寫過「會導致 / 可能 / 因為...所以...」未附引用的機制論述？
[ ] 層 2 歸因 — 被糾正時是否第一反應「我判斷錯」而非分層挖因？
[ ] 層 3 決策路徑 — 是否撞 CLI 錯後立即猜變體（PC-105）？是否 WRAP A 階段一句話可概括（PC-080）？
[ ] 層 4 輸出污染 — AUQ / ticket body 是否被 hook 攔截（簡體 / 日文漢字 / emoji）？
[ ] 層 5 互動壓力 — 用戶反應字數是否驟降？是否引用 memory 未先驗證當下條件？
[ ] 層 6 WRAP 本身 — Context > 60% 時是否仍主動觸發 WRAP？
```

**判定規則**：任一層觸發 ≥ 2 次或全 session 重複同一因子 ≥ 3 次，必須升級至完整版。

---

## 完整版（10-15 分鐘）

含結構化反思，產出可直接累積至 `.claude/methodologies/pm-judgment-interference-map.md` 案例樣本或 memory feedback 條目。

### 步驟 1：盤點觸發事件（5 分鐘）

逐項列出本 session 干擾事件，欄位：時點 / 因子 / 觸發訊號 / 防護是否啟動 / 替代行為是否被執行。

| 時點（粗略時序） | 因子（13 項擇一） | 觸發訊號 | 防護啟動？ | 替代行為執行？ |
|----------------|------------------|---------|-----------|---------------|
| Tn | (例 1.1 事後合理化編造) | (例 警戒術語 working memory) | (例 Q1-Q3 未自察) | (例 用戶糾正後才補引用) |

**判定 spec**：
- 「防護啟動」= 自察觸發（含 hook 阻擋、規則自查、memory 引用對照）
- 「替代行為執行」= 是否真的改用因子地圖建議的替代行為，還是繼續原模式
- 兩欄皆「是」= 因子地圖有效；「否 / 是」= hook / 用戶救援；「否 / 否」= 隱性累積，下次仍會犯

### 步驟 2：連鎖關係檢查（3 分鐘）

對步驟 1 的事件列表，標出連鎖路徑。

```
範例：
T1（5.1 CLI autopilot）→ 撞錯 → T2（5.1 重試變體）→ 撞錯 → T3（5.1 不查 --help 又猜）
T3（1.1 論述編造）→ 用戶糾正 → T4（2.1 淺層歸因「我判斷錯」）
```

**判定**：
- 連鎖長度 ≥ 3 環 → 該因子的絆腳索失效，需在 spawned IMP 強化
- 跨層連鎖（如層 1 → 層 2）→ 兩層共享根因，可能需要合併防護

### 步驟 3：結構化反思（5 分鐘）

回答下列三題（每題 2-3 句）：

1. **本 session 哪個因子觸發次數最高？為何防護未啟動？**
   - 範例：「層 4 因子 4.1（簡繁 charset），觸發 4 次。第 1 次後未檢查為何輸出簡體，僅機械重試。根因：信任 hook 訊息但不信任『我打的字真的是簡體』。」

2. **是否有本 session 新發現、地圖未涵蓋的干擾因子？**
   - 若有：簡述觸發訊號 + 建議分類層。可作為地圖 v1.x 升級素材。
   - 若無：寫「無新發現」即可。

3. **下個 session 應啟動的預防措施？**
   - 範例：「context > 50% 時提前觸發 wrap-decision SKILL；handoff 前必跑本 checklist。」

### 步驟 4：輸出格式（直接貼入 handoff / memory）

```yaml
session_self_check:
  date: YYYY-MM-DD
  duration_hours: N
  total_factors_triggered: N
  most_frequent_factor: "X.Y 因子名（觸發 N 次）"
  unprotected_chains:
    - "T1 → T2 → T3：因子 X.Y 連鎖未斷（防護未啟動原因：...）"
  new_factors_discovered: []  # 或 ["疑似新因子描述"]
  preventive_action_next_session: "..."
```

---

## 與其他流程整合

| 整合點 | 觸發時機 | 採用版本 |
|-------|---------|---------|
| `/clear` 前 | session-start hook 提示 | 快速版 |
| Handoff 撰寫 | PM 寫 handoff 摘要時 | 完整版 |
| Memory feedback 累積 | 發現新干擾因子或防護失效 | 完整版步驟 3 第 2 題 |
| Wave 結束回顧 | 多 session 累積後 | 完整版（多 session 合併分析） |

**未來擴充**（W17-077 範圍外）：建立 hook（如 `pm-session-end-checklist-reminder-hook.py`）在 session 結束 / `/clear` 前自動提示執行本 checklist；目前依 PM 自律觸發。

---

## 與 pm-judgment-interference-map.md 雙向引用

- 本 checklist 為地圖的**實踐入口**：將 13 因子轉為 session 結束時的可執行檢查
- 地圖為本 checklist 的**理論依據**：所有 6 層分類、觸發訊號、絆腳索均來自地圖

修改任一檔案後，須檢查另一檔案是否需同步更新（特別是新增因子或修改觸發訊號描述時）。

---

## 自測案例：本 session（2026-04-28 W17-077 落地 session）

採用本 checklist 完整版自測：

| 步驟 1 觸發事件 | 因子 | 防護啟動 | 替代執行 |
|---------------|-----|---------|---------|
| AUQ payload `遗漏` 簡體被攔 × 2 | 4.1 簡繁 charset | 是（hook） | 第 2 次後（替代為 ASCII 構字） |
| AUQ payload `独立` 簡體被攔 | 4.1 簡繁 charset | 是（hook） | 是（改詞） |
| Claim W17-075 後未讀 body 即重做 W 階段 | 1.1 + 5.x（記憶引用未驗證當下條件） | 否 | 用戶糾正後才察覺 |

**步驟 2 連鎖**：層 4 charset 連鎖長度 3 環（同類錯誤重複）→ 絆腳索（hook）有效但 PM 替代行為延遲

**步驟 3 反思**：
1. 最高頻：層 4 charset（3 次）。防護全部由 hook 啟動，PM 自察為 0 次 → 顯示 PM 對「自己打的字是繁體還是簡體」無內建檢查
2. 新發現：「claim 後未讀完整 body 即起始工作」可能是因子 5.x 的延伸（memory 引用 = 對 ticket 既有狀態的記憶引用），值得回流地圖
3. 下 session 預防：claim 後第一動作必為 `ticket show <id> -r`（讀完整 body），禁止依 ticket title + 短描述就推進

**步驟 4 YAML 輸出**：

```yaml
session_self_check:
  date: 2026-04-28
  duration_hours: 1
  total_factors_triggered: 4
  most_frequent_factor: "4.1 簡繁 charset（觸發 3 次）"
  unprotected_chains:
    - "T1→T2→T3 charset 連鎖：hook 有效但 PM 替代行為延遲到第 2 次撞牆後才執行"
  new_factors_discovered:
    - "claim 後未讀完整 body 即推進（疑似因子 5.x memory 引用未驗證當下條件之延伸）"
  preventive_action_next_session: "claim 後第一動作為 ticket show <id> -r 完整讀取 body"
```

---

**Last Updated**: 2026-04-28
**Source**: 0.18.0-W17-075 ANA Solution § Spawned IMP-D
**Related**: `.claude/methodologies/pm-judgment-interference-map.md`、`.claude/error-patterns/process-compliance/PC-111-pm-narrative-fabrication-and-shallow-attribution.md`
