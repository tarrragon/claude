<!--
系統層模板 — 複製為 docs/system-layer.md（整個專案一份）。

用途：承接「跨 domain」的系統級決策。單一 domain 內的 bundle 邊界、分層與測試策略
屬 `domain-map-template.md`（每個 domain 一份）；本文件只寫兩個以上 domain-map 之間
才成立的事：bundle 間依賴方向、共用通道、跨 domain 邊界決策、容錯策略、待決事項。

與 domain-map 的連結方式：
- 每份 domain-map 的 frontmatter 以 `depends_on_bundles` 宣告出邊（目標為另一份
  domain-map 的 id，如 DOMAIN-MAP-{domain}）；本文件 §2 彙整這些出邊並說明理由。
- 出邊的唯一權威在各 domain-map frontmatter，本文件 §2 的表格是彙整視圖，不另設權威。
  兩者不一致時以 frontmatter 為準，並修正本文件。
- `doc validate DOMAIN-MAP-{domain}` 檢查出邊目標是否存在。

填寫順序：先讀完全部 domain-map，再填 §2；§3-§6 僅記錄跨 domain 才成立的內容，
單一 domain 內的內容回填到該 domain 的 domain-map，不在此重複。
-->

---
title: "系統層 — {專案名稱}"
bundles: []                      # 納入的 DomainBundle id，如 [DOMAIN-MAP-{domain}]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---

# 系統層 — {專案名稱}

> 產出來源：{規劃票 ticket-id}。本文件承接跨 domain 的系統級決策；單一 domain 的 bundle 邊界見各 domain-map（`domain-map-template.md`）。

## 1. 目的與適用範圍

<!-- 說明本專案有哪些 domain-map 納入本文件，以及哪些決策因為跨 domain 才寫在這裡。 -->

| 決策類型 | 寫在哪裡 | 判準 |
|---|---|---|
| 單一 domain 內的分層、bundle 界定、測試策略 | 該 domain 的 domain-map | 移除其他 domain 後決策仍成立 |
| bundle 間依賴方向、共用通道、跨 domain 邊界、容錯、待決 | 本文件 | 決策涉及兩個以上 domain-map |

## 2. 分層與依賴方向（跨 bundle）

<!-- 畫出 bundle 之間的依賴 DAG。依賴方向必須單向、不成環。此圖的出邊逐條對應各 domain-map frontmatter 的 depends_on_bundles。 -->

```
{DOMAIN-MAP-A}
      │ depends_on_bundles（單向）
      ▼
{DOMAIN-MAP-B}
      │ depends_on_bundles（單向）
      ▼
{DOMAIN-MAP-C}
```

### 2.1 出邊彙整表

| 來源 bundle | 目標 bundle | 依賴理由 | 依賴的公開面 |
|---|---|---|---|
| {DOMAIN-MAP-A} | {DOMAIN-MAP-B} | {為什麼 A 需要 B} | {A 只能透過 B 的哪個公開面使用它} |

### 2.2 依賴方向底線（不可違反）

<!-- 每條底線寫「規則 + 違反後果」。底線必須用實際 import 鏈或呼叫鏈驗證，不可憑心智模型宣告。 -->

- bundle 間依賴不得成環。違反則無法決定初始化與測試的先後順序。
- 依賴只經由目標 bundle 的公開面，不得穿透到其內部。違反則目標 bundle 的內部重構會擴散到所有依賴者。
- {其他跨 bundle 依賴底線 + 違反後果}

## 3. 通道

<!-- 跨 domain 共用的稀缺資源（連線池、單一事件迴圈、全域提示載體等）。單一 domain 專屬的通道回填到該 domain-map 的通道節，不在此重複。 -->

| 通道 | 真持有者 | 持有層 | 請求它的 bundle | 仲裁方式 |
|---|---|---|---|---|
| {通道名稱} | {真持有者} | {該通道所屬的層} | {對此通道發出請求的 bundle 清單} | {誰仲裁、依什麼鍵排序或配額} |

## 4. 邊界決策

<!-- 記錄跨 domain 邊界上有真實取捨的決策（拍板結論 + 依據）。每個決策一小節。 -->

### 4.1 {決策標題}

- **決策**：{定案結論}
- **依據**：{為什麼選這個而不是其他方案}
- **影響的 bundle**：{DOMAIN-MAP-X、DOMAIN-MAP-Y}
- **現況或目標**：{若描述的是目標邊界而非現況，明文標註「此為目標邊界，非現況」}

## 5. 容錯策略

<!-- 一個 bundle 失敗時，依賴它的 bundle 怎麼辦。逐條出邊回答，不寫泛稱的「錯誤處理」。 -->

| 失敗的 bundle | 失敗型態 | 依賴者的行為 | 使用者可見的結果 |
|---|---|---|---|
| {DOMAIN-MAP-B} | {資源缺失／逾時／資料損壞} | {阻擋／降級／重試／略過} | {畫面或回報上看到什麼} |

## 6. 待決事項

<!-- 每項待決必須綁定 trigger：已有結論的寫結論；尚無結論的寫「等 {ticket-id} 完成後決定」。不寫無 trigger 的「之後再說」。 -->

| 事項 | 狀態 | 結論或 trigger |
|---|---|---|
| {待決事項} | {已決策／等待 ticket} | {結論；或 {ticket-id} 完成後執行什麼} |

---

**Last Updated**: YYYY-MM-DD | **Source**: {規劃票 ticket-id}
**Template Updated**: 2026-10-07 | **Version**: 1.0.0 — 新增系統層模板，承接跨 domain 的分層與依賴方向、通道、邊界決策、容錯策略、待決事項；與 `domain-map-template.md` 以 `depends_on_bundles` 出邊互連
