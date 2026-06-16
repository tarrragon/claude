# PC-APP-001: 延後決策綁定的 trigger ticket 引用未查證 scope 一致性（trigger 名存實亡）

## 摘要

本 pattern 指：延後決策引用的 trigger ticket 格式合法（確為 ticket ID）但其 scope 不涵蓋被延後的工作，導致 trigger 名存實亡——格式上通過 decision-trigger-binding 規則 2，語意上卻不會觸發任何後續動作，延後退化為無 trigger 延後（PC-093）。典型情境：延後敘述寫「Phase 4 評估抽為 X，依 W3-006 結論」，但引用者只確認該 ID 格式合法、未查證該 ticket 實際 scope 是否真涵蓋被延後工作。根因是 decision-trigger-binding 規則 2 只要求「trigger 限 ticket ID」（格式層），未要求「查證被引用 ticket 的 scope 涵蓋延後工作」（語意層），形成 guidance 缺口。修正方向：引用 ticket 作 trigger 前先 `ticket track query <id>` 讀其 what/scope，確認與延後工作主題一致；不一致則建真實承接 ticket 並改引用之。

## 症狀

- 延後敘述含「依 W{X}-{Y} 結論 / 承接點 / 待 W{X}-{Y}」但未實際讀過該 ticket 內容
- 被引用 ticket 的 what 與延後工作主題不符（如引用「migration 分隔符語意」ticket 承接「VO 驗證遷移」工作）
- 通過 decision-trigger-binding 規則 2 格式檢查（確實是 ticket ID），卻不會被任何後續流程觸發
- 被引用 ticket 完成 / 關閉時，無人意識到它本應觸發延後工作，延後在「以後」與「永不」間累積為死議題

## 根因（格式合法但語意斷裂）

decision-trigger-binding 規則 2 的防護只覆蓋格式層：

| 層級 | 規則 2 現狀 | 缺口 |
|------|------------|------|
| 格式層 | trigger 必須是 ticket ID（非時間 / 量化閾值 / 外部事件） | 已覆蓋 |
| 語意層 | 被引用 ticket 的 scope 須真涵蓋被延後的工作 | 未覆蓋——本 PC |

引用者看到「要綁 ticket trigger」便填一個看似相關的 ticket ID，未執行 `ticket track query` 核對該 ticket 的 what。當 ID 憑記憶或編號鄰近性填入時，誤引主題不符 ticket 的機率顯著上升。格式檢查通過營造「已正確綁定」的假象，遮蔽語意斷裂。

## 案例：W5-002 ADR 3 引用 W3-006 承接 VO 驗證遷移（2026-06-14）

W5-002 終態重構策略（pepper Phase 3a）在 ADR 3 與 Solution 第 3 節寫「VO 內領域驗證（ISBN 格式 / importance 1-7 / author 多值解析）刪 VO 後散落，建議 Phase 4 評估抽為 tag value validator（依 W3-006 結論）」。

U2 派發前多視角審查（linux）查證 W3-006 實際 scope：

```bash
ticket track query 0.32.0-W3-006
# → what: 重評 v8 migration tag.id 分隔符語意 + 回滾 category 辨識（TD-1/TD-2）
```

W3-006 主題是「migration 分隔符語意」，與「VO 驗證遷移」毫無關係。引用為誤——VO 驗證延後實際無真實承接 ticket，退化為無 trigger 延後（違反 decision-trigger-binding 規則 1）。

修正：建立 0.32.0-W5-005（tag value validator，承接 ISBN/importance/author 驗證），改引用之並回填 spawned_tickets / blockedBy。

緩解因子：本案在 U2 派發前的審查階段被攔截，VO 驗證尚未真正遺失，屬 near-miss。本 PC 固化規則，防止未經審查直接派發時的實害（驗證隨 VO 刪除無痕消失，且無 ticket 追蹤）。

## 防護

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 引用 ticket 作 trigger 前，`ticket track query <id>` 讀其 what / scope | 取得語意層事實，不憑記憶或編號鄰近性 |
| 2 | 核對被引用 ticket 主題是否真涵蓋被延後的工作 | 判別格式合法之外的語意一致性 |
| 3 | 不涵蓋 → 建真實承接 ticket，改引用之，回填 spawned_tickets / blockedBy | 使 trigger 語意成立、雙向可追溯 |
| 4 | 涵蓋 → 在延後敘述標明已查證（引用 what 摘要片段） | 留查證痕跡，後續審查可複核 |

**Why**：decision-trigger-binding 規則 2 只保證 trigger 是 ticket ID（格式），不保證該 ticket 的 scope 真涵蓋延後工作（語意）。格式合法但語意斷裂的 trigger 不會觸發任何後續動作，與無 trigger 延後等價。

**Consequence**：被引用 ticket 完成時無人意識到它本應觸發延後工作，延後工作（如 VO 驗證遷移）無痕消失且無 ticket 追蹤，在「以後」與「永不」間累積為死議題（PC-093 反模式），並可能造成行為靜默改變（驗證能力遺失，PC-165 假綠）。

**Action**：引用 ticket 作 trigger 前必 `ticket track query <id>` 核對 scope 一致性；不一致則建真實承接 ticket 並改引用。對照 `.claude/rules/core/decision-trigger-binding.md` 規則 2。

## 識別訊號表

| 訊號 | 判讀 |
|------|------|
| 延後敘述含「依 W{X}-{Y} 結論 / 承接點」但未見查證痕跡 | 高風險：可能引用未查證 scope 的 ticket |
| 被引用 ticket 的 what 與延後工作主題不符 | trigger 語意斷裂，須建真實承接 ticket 改引用 |
| trigger ticket ID 憑記憶 / 憑編號鄰近填入 | 未執行 `ticket track query` 核對，高誤引率 |
| 格式檢查通過但無人能說出被引用 ticket 完成後會發生什麼 | trigger 名存實亡的指標 |

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| `decision-trigger-binding.md` 規則 2（合法 trigger 限 ticket ID） | 本 PC 補語意層 carve-out——規則 2 保證格式，本 PC 要求查證被引用 ticket 的 scope 一致性 |
| `decision-trigger-binding.md` 規則 1（兩種合法狀態） | 同源——誤引用使狀態 (b) 明確 trigger 延後退化為禁止的無 trigger 延後 |
| PC-093（無 trigger 延後累積死議題） | 下游後果——語意斷裂的 trigger 等價無 trigger，最終累積為死議題 |
| PC-165（測試綠不等於 runtime 正確） | 共振——VO 驗證能力隨延後遺失，編譯綠 + 既有測試綠無法暴露驗證消失 |
| quality-baseline.md 規則 6（失敗案例學習原則） | 同源——near-miss 暴露 guidance 缺口（規則 2 缺語意層），提煉教訓固化為規則而非回退 |

## 案例文件來源

W5-002 U2 派發前多視角審查（rosemary 主持 parallel-evaluation 情境 F+C，2026-06-14）。linux 委員查證 ADR 3 引用的 W3-006 實為「v8 migration tag.id 分隔符語意」，與延後的 VO 驗證遷移無關。修正建立 0.32.0-W5-005 作真實承接點並回填連結。near-miss——審查階段攔截，VO 驗證未真正遺失。
