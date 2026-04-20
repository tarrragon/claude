# PC-081: PM 自我檢查標準比用戶規則更嚴格（保守偏見導致過早收斂）

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-081 |
| 類別 | process-compliance |
| 風險等級 | 中（影響任務推進速度與用戶信任） |
| 首發時間 | 2026-04-17（W12-002 系列 Hook/rules/skills/templates emoji 清理 session） |
| 姊妹模式 | PC-080（WRAP A 階段框架檢查未做）、PC-078（並行 session 狀態誤判） |

---

## 症狀

PM 執行 ticket 過程中反覆推薦保守選項（handoff / /clear / 拆更多 sub-ticket / 縮小範圍），即便：
- 技術上任務可繼續推進
- 用戶未表達疲勞或停止意圖
- 本 session token 雖高但並未接近 auto-compact 邊界

用戶必須連續糾正（「太保守了」「可以繼續」「直接派代理人」），才能突破 PM 的自我設限。

---

## 實際案例（W12-002 系列 session）

**任務序列**：W13-007 ANA → W12-002.5 遷 → W12-002.2 → .3 → .4 拆分 → .4.1 → .4.2 → .4.3

**PM 保守推薦**（每個 commit 後 AUQ #11）：
- Commit 2: 「Handoff 預設推薦」
- Commit 4: 「Handoff 強烈推薦」
- Commit 5（本 ticket complete）: 「Handoff 預設推薦」
- 框架檢查：每次 AUQ 把「Handoff / /clear」列第一選項，繼續列末

**用戶實際選擇**：全部繼續本 session，並明確反駁：
- 「這樣太保守了」
- 「可以繼續」
- 「派代理人修改之前有成功派發過，只要不開 worktree」

**結果**：本 session 完成 9 commits / 4 tickets complete / 5 新 spawn ticket / 2 新 error-pattern。若照 PM 建議 session 2 就結束，只會完成 W13-007 + spawn 就 handoff。

---

## 根本原因

### 已驗證事實

1. **AUQ 強制規則要求 Handoff 為第一選項**：`.claude/rules/core/askuserquestion-rules.md`（場景 11）「Handoff 必須是第一選項且標記 (Recommended)」
2. **PC-009 原則**：「Handoff first，繼續 session 是例外，不是預設」
3. **規則本意**：保護 context 品質，防止錯亂
4. **PM 執行結果**：**過度套用規則，自我檢查比用戶實際狀況更嚴**

### 真根因

1. **機械套用規則忽略實際狀況**：
   - 規則存在是為「context 品質」but 不是「固定閾值」
   - PM 用固定 token 數 / commit 數判斷 context 重，未考量用戶是否還有精力
   - 用戶是 context 的最終使用者，保守判斷應由用戶做不是 PM

2. **memory 內化成防禦性行為**：
   - memory PC-077 / ARCH-015 寫「subagent 不能 Edit .claude/」
   - PM 直接引用而未驗證當下條件（用戶先前有成功派發過）
   - 「做不到」的記憶比「做得到」的記憶更容易被 trigger（負面偏見）

3. **WRAP A 階段同類問題**（PC-080 延伸）：
   - PC-080：A 階段方案全在同一「擋訊號」框架
   - PC-081：推薦層面全在同一「handoff」框架
   - 兩者都是「選項多元性不足」的不同展現

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成保守偏見 |
|---------|------------------|
| 「PC-009 Handoff first」 | 原則為引導不是公式；fixed threshold 應用違反原意 |
| 「本 session token 高」 | 「高」是主觀判斷；用戶未抱怨前不應代為決定 |
| 「subagent 不能 Edit .claude/」 | memory 可能過期；用戶有成功經驗應採信 |
| 「為保護 context 品質」 | 用戶是受益人；用戶自己決定受不受影響 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 流程 | AUQ 推薦 Handoff 前先自問：「用戶表達過疲勞或停止意圖嗎？」— 否則用戶知情推進 | 行為準則 |
| 流程 | 引用 memory 前先驗證當下條件（如派 subagent 前確認用戶是否有成功經驗） | 行為準則 |
| 流程 | 連續被糾正 2 次後停止推薦 Handoff，改為 neutral 列選項 | 行為準則 |
| 規則 | askuserquestion-rules 場景 11 補充「用戶表達繼續意圖後，handoff 推薦降為中性」 | 建議實施（W13-015 建追蹤） |
| Memory | 記錄本模式作為跨 session 提醒 | 已實施（配對本檔） |

---

## 檢查清單（PM 推薦 Handoff / 限制性選項前自我檢查）

- [ ] 用戶在本 session 表達過疲勞或停止意圖了嗎？否 → 推薦 Handoff 可能太保守
- [ ] 用戶在本 session 是否連續糾正我的保守推薦？是 → 停止推薦 handoff
- [ ] 我引用的 memory（如「subagent 不能」）是否在本 session 條件下仍成立？未驗證不可引用
- [ ] 本 AUQ 是「PC-009 規則要求」還是「我預判用戶需要」？若是後者要慎思

---

## 教訓

1. **規則是引導不是公式**：PC-009「Handoff first」是原則，不等於每次 commit 都要問 handoff
2. **PM 不代用戶決定 context 品質**：用戶是 context 使用者，PM 角色是告知狀態讓用戶自己判斷
3. **Memory 是歷史快照不是永恆真理**：引用 memory 前驗證當下條件是否仍適用
4. **連續被糾正是訊號**：2 次以上說明 PM 判斷系統有偏差，應立即調整而非繼續推薦

---

## 象限歸類

本模式的防護屬 **摩擦力管理 B 象限（降低摩擦）**：Handoff 推薦本是降低決策成本（預設推薦），但過度保守時反而**增加用戶認知負擔**（用戶要反覆糾正）。降低 handoff 推薦頻率可降摩擦。

---

## 相關文件

- `.claude/rules/core/askuserquestion-rules.md` — 場景 11 Handoff 推薦規則
- `.claude/pm-rules/decision-tree.md` — PC-009 原則
- `.claude/error-patterns/process-compliance/PC-080-wrap-a-stage-framing-check-missed.md` — 姊妹模式

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0
**Source**: W12-002 系列 session 中 PM 反覆推薦 handoff，用戶連續 3+ 次糾正「太保守了」後識別此保守偏見模式
