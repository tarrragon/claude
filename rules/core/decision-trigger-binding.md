# 決策 Trigger 綁定規則（速查 stub）

> **完整規則**：`.claude/references/decision-trigger-binding-details.md`（按需讀取）。本檔僅保留規則速查與觸發路由。

需要延後執行的決策必須綁定明確 trigger，禁止「以後再說」式的無 trigger 延後。延後不是第三種狀態——延後必須是「等 ticket X 完成後執行 Y」，且 X 必須是 ticket。

## 規則 1：兩種合法狀態，沒有第三種

| 狀態 | 含義 | 範例 |
|------|------|------|
| (a) 已決策 | 含結論的最終決定 | 「採方案 A」「無需重構」「Phase 4 結論：保持現狀」 |
| (b) 明確 trigger 延後 | 等 ticket X 完成後執行 | 「`<follow-up-ticket-id>` 完成後處理 X」 |

**禁止**無 trigger 延後（「Phase X 再決定」「以後再評估」「之後處理」「將來」「暫緩」「待後續觀察」）。**Why**：無 trigger 延後在「以後」與「永不」之間沒有可驗證邊界，必累積為死議題（PC-093）。**Action**：能下結論 → 狀態 (a)；不能 → 建 follow-up ticket 並引用 ID（狀態 b）。

## 規則 2：合法 trigger 限 ticket ID

時間、量化閾值、外部事件都不是合法 trigger，必須先包裝為 ticket（建監測/追蹤 ticket，本決策標 `blockedBy` 或 `spawned_tickets`）。

**邊界**：本規則只管延後決策。`.claude/` 框架檔案內「決策已下完、只等條件成立」的條件式操作規範不綁 ticket ID（`.claude/references/reference-stability-rules.md` 規則 8 硬擋），改為明訂動作；屬自指維護閾值者另須指名偵測承擔者且粒度相符。判別方式與處置見完整規則的規則 2.5 條件式操作規範。

## 寫法替換速查

| 反模式句型 | 替代寫法 |
|-----------|---------|
| 「Phase 4 再決定觸發條件」「之後再評估」「以後再說」 | 建 follow-up ticket，標 `spawned_tickets: [<ticket-id>]` |
| 「暫緩」 | 立刻決策（狀態 a）或建 ticket（狀態 b），沒有第三選項 |
| 「baseline 顯示需要再做」 | 建量測 ticket，量測結果作為 follow-up 的 trigger |

## 何時讀完整規則

| 情境 | 必讀章節（references 詳細版） |
|------|------------------------------|
| 判斷載體是否可述「未來考量」（程式碼/文件 vs worklog/ticket） | 規則 1.5 載體邊界 |
| 在 `.claude/` 框架檔案寫「當條件成立時該做 X」（含量化閾值） | 規則 2.5 條件式操作規範全章（判別問題 / 兩軸四格處置 / 自指維護閾值的粒度相符要求） |
| 寫 PC-093-exempt marker（規則引用 / source ticket 歷史引用 / frontmatter 場景） | Hook 引用豁免機制全章（6 類 category、marker 位置、frontmatter 場景、多命中行） |
| 違規偵測時機與 hook 行為 | 規則 4 違規偵測 |
| 與其他規則邊界釐清 | 與其他規則的邊界表 |

## 檢查清單

- [ ] 內容含「之後」「再決定」「以後」「將來」「暫緩」「Phase X 再」「下週」「下個月」等表述？
- [ ] 載體屬 worklog / ticket / Phase 4 結論？若是，必須為狀態 (a) 或 (b)，不可述「未來考量」
- [ ] 已建對應 follow-up ticket 並標 `spawned_tickets` / `blockedBy`，或內文有 `W\d+-\d+` ticket ID 引用？
- [ ] Phase 4 結論為明確結論（「無需重構」「採方案 A」），而非「Phase 5 再決定」？
- [ ] 載體為 `.claude/` 框架檔案的條件式條文？已依規則 2.5 判定決策是否已下完；若屬自指維護閾值，條文內已指名偵測承擔者且粒度相符？

---

**Last Updated**: 2026-08-18 | **Version**: 1.6.0 — 規則 2 加邊界一行 + 路由至新增的規則 2.5（`.claude/` 框架檔案內的條件式操作規範不綁 ticket ID；自指維護閾值另須指名偵測承擔者且粒度相符），解消與 `reference-stability-rules.md` 規則 8 的衝突；速查表與檢查清單各增一列。**Version**: 1.5.0 — 主文 substance 外移至 `.claude/references/decision-trigger-binding-details.md`，本檔保留速查 stub。**Source**: PC-093 / PC-146。
