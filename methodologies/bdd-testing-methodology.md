# BDD 測試方法論（30 秒核心）

> **本檔已瘦身（W8-018.2）**：通用 GWT 設計（場景設計原則、場景類型覆蓋、行為鏈式設計、邊界條件識別）已在 `/tdd` skill 的 `.claude/skills/tdd/references/phase2-test-design.md`「BDD / Given-When-Then 設計」與「測試案例設計」章節。本檔僅保留 30 秒核心 + 本方法論的 distinct 內容（前置條件驗證強制規則）。需要完整 GWT 設計與行為分支窮舉時直接讀 phase2-test-design.md。

BDD 測試行為而非實作：從使用者視角描述系統行為，用 Given-When-Then 結構。核心價值是重構時測試保持穩定——測試只關心可觀察的行為結果，不耦合內部實作。

---

## Given-When-Then 速查（30 秒）

| 元素 | 定義 | 規範 |
|-----|------|------|
| Given | 系統初始狀態 | 明確、完整、可重現 |
| When | 使用者操作 | 單一動作、業務語言 |
| Then | 預期結果 | 可驗證、可觀察的行為 |

**行為 vs 實作判斷**：問三題——使用者能直接觀察到嗎（是→行為）？改變實作會影響測試嗎（會→實作，應避免）？產品經理需要關心嗎（是→行為）？

**Mock 策略**：只 Mock 外層依賴（Repository / Service / Event Publisher）；Domain Entity / Value Object 用真實物件。禁止驗證內部方法呼叫次數。

---

## 前置條件驗證強制規則（distinct 核心）

**每個測試步驟在執行行為（When）之前，必須以明確斷言驗證其前置條件成立。** 這是本方法論相對通用 GWT 設計的 distinct 強制要求。

**Why**：跳過前置驗證直接執行行為，失敗訊息會是「NullPointerException」或「element not found」，難以判斷真正原因是前置條件未滿足還是行為本身有問題。先驗後行讓測試在前置條件失敗時立即停止並給出清晰訊息。

| 前置條件類型 | 驗證方式 | 範例 |
|------------|---------|------|
| UI 元素存在 | `expect(widget, findsOneWidget)` | 按鈕、輸入框、對話框 |
| 資料已載入 | 驗證清單長度 > 0 或特定項目存在 | 清單項目、表單初始值 |
| 系統狀態 | 驗證狀態變數或畫面文字 | 登入狀態、載入完成 |
| 權限具備 | 驗證操作按鈕未被禁用 | 編輯按鈕可點擊 |

**正確模式（先驗後行）**：

```
Then（前置）: 「送出」按鈕存在且可互動
When: 點擊「送出」按鈕
Then: 驗證表單已提交
```

### 前置條件驗證檢查清單

- [ ] Given 中的每個狀態都有對應的驗證斷言
- [ ] UI 元素在互動前先 `expect(element, findsOneWidget)`
- [ ] 資料操作前先確認資料存在或符合預期格式
- [ ] 多步驟場景中每個中間狀態都有驗證斷言
- [ ] 前置驗證的失敗訊息明確（能直接定位問題）

---

## 路由

| 需求 | 讀這裡 |
|------|--------|
| 完整 GWT 設計、場景設計原則、場景類型覆蓋、行為鏈式設計、測試案例格式、邊界條件識別 | `.claude/skills/tdd/references/phase2-test-design.md` |
| 行為 vs 實作判別、分層 Mock、架構分層 × BDD、BDD→單元拆分判準 | `.claude/skills/tdd/references/bdd-behavior-testing.md` |
| Sociable vs Solitary 與前置條件關係 | `.claude/methodologies/behavior-first-tdd-methodology.md` |
| 分層測試決策樹（完整版含判斷流程、覆蓋率語意、monitor 對應） | `.claude/skills/tdd/references/layered-test-strategy.md` |

---

**Last Updated**: 2026-06-13
**Version**: 2.0.0 — W8-018.2 整併瘦身：通用 GWT 設計（場景設計、行為鏈、邊界條件）路由至 `/tdd` skill phase2-test-design.md，保留 30 秒核心 + distinct 的前置條件驗證強制規則。歷史 1.2.0 完整版（含行為鏈式推演框架、測試設計完成標準、邊界條件系統化方法）見 git log。
