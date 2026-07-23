<!--
Domain Map 模板 — 複製到對應 domain 目錄並重新命名。
  多 domain 專案：docs/spec/{domain}/domain-map.md（與該 domain 的 spec 同層）
  單 domain 專案：docs/domain-map.md（根層退化形式）

用途：界定 DDD domain bundle 邊界（水平視角），作為切層、派發、測試策略的權威依據。
正交於 UC（使用者行為，垂直視角）與 spec 目錄分組（feature grouping）。

填寫來源：spec FR 列表 + 現有/規劃程式碼結構。domain 派生自 FR（系統計算什麼），
與 UC 場景（誰怎麼用）正交。切分判準見 .claude/methodologies/domain-bundle-mapping-methodology.md。
-->

---
id: DOMAIN-MAP-{domain}
domain: "{domain 名稱}"
source_specs: []                 # 本 map 覆蓋的 spec，如 [SPEC-001]
related_usecases: []             # 相關 UC，如 [UC-01]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---

# Domain Map — {domain 名稱}

> 產出來源：{規劃波 ticket ID}。本文件界定 DDD domain bundle 邊界，作為切層、派發與測試策略的權威依據。
> 與 traceability.yaml（UC↔測試）、{對應 spec}（FR 清單）交叉引用。

## 1. 目的與 UC / DDD 正交關係

本文件補上 domain 的**水平視角**：按業務知識把 domain 切成 bundle。UC 是**垂直視角**（一條使用者劇本貫穿 UI → 邏輯 → 持久化），一個 UC 橫切多個 bundle。

**核心準則**：domain 層保持純——無 I/O、無 UI 形狀、對顯示偏好（如語系、格式化、單位換算）與框架一無所知。違反則 domain 被 I/O 與顯示偏好污染，測試被迫拖真實依賴、無法純函式驗證。

## 2. 分層與依賴方向

<!-- 畫出本 domain 的分層 DAG。依賴方向必須單向，不成環。 -->

<!-- 依專案形態選擇適用的 DAG 圖：單 aggregate（read-heavy）或多 aggregate（command-side） -->

**單 aggregate 形態**（衍生計算為主）：
```
presentation (UI 層 + 狀態管理)
        │ 依賴（單向）
        ▼
domain read-model（衍生計算，按概念分）
        │ 依賴（單向）
        ▼
domain kernel（共享估值/核心計算，若有）
        │ 依賴（單向）
        ▼
domain aggregate + VO（聚合根 + 值物件）
        ▲ 單向
        │ 依賴
data（repository + 持久化 + 外部服務）
```

**多 aggregate 形態**（含 command-side 協調）：
```
presentation (UI 層 + 狀態管理)
        │
read-model（可跨 aggregate 聚合資料）
        │
kernel（若有共享計算）    domain service / policy / saga
        │                        │
   +---------+           +------+------+
   │         │           │             │
aggregate A  aggregate B（by-id 參照，非直接依賴）
   ▲              ▲
   │              │
 data A         data B（各自 repository）
```

**依賴方向底線（不可違反）**：

<!-- 每條底線寫「規則 + 違反後果」。底線必須用實際 import 鏈驗證，不可憑心智模型宣告（依賴宣告易與現況漂移）。 -->

- domain 不得 import data / presentation / UI 框架 / 外部服務。違反則喪失純函式可測性。
- read-model bundle 依賴 kernel 與 aggregate，**彼此不互相依賴**（允許共同依賴 kernel，不允許 read-model→read-model 成環——DAG，非禁止共享）。違反則單一概念改動沿耦合鏈擴散。
- aggregate 間禁直接 import / 嵌入；僅允許 by-id 參照（VO 持有 ID）。違反則破壞交易一致性邊界。
- domain service 透過 DI 依賴 repository 介面，不持有狀態。policy / event handler 透過 event bus 間接依賴。saga 自身持久化，透過 repository 協調。
- {其他分層依賴底線}

## 3. Bundle 界定表

<!-- 分類軸：真 domain（aggregate/kernel/VO/read-model）vs 非 domain（cross-cutting/infrastructure，列此僅為覆蓋完整性）。 -->

| Bundle | 分類 | 納入概念 | 排除 | 目標路徑 | 測試層/方法 |
|---|---|---|---|---|---|
| {Aggregate} | aggregate root | {實體/聚合根/核心不變式} | {衍生計算、持久化細節} | `{domain/xxx}` | unit：{斷言重點} |
| {Kernel} | domain kernel（共享） | {共享估值/核心計算} | {各 read-model 衍生視圖} | `{domain/xxx}` | unit：{斷言重點} |
| {Read-model A} | read-model | {衍生計算函式}（{FR}） | {其他 read-model 職責} | `{domain/xxx}` | unit：{斷言重點} |
| {Supporting VO} | supporting VO | {值物件 + 純函式}（{FR}） | {其他屬性} | `{domain/xxx}` | unit：{邊界值} |
| {Domain Service} | domain service | {跨 aggregate 協調邏輯}（{FR}） | aggregate 內部不變式 | `{domain/xxx}` | unit + integration |
| {Policy} | policy / event handler | {事件驅動反應}（{FR}） | 命令協調 | `{domain/xxx}` | unit：餵 event 斷言命令 |
| {Saga} | saga / process manager | {長期協調 + 補償}（{FR}） | 衍生計算 | `{domain/xxx}` | unit（狀態機）+ integration |
| {Cross-cutting} | 非 domain（顯示層）| {i18n/主題/格式化}（{FR}） | 任何 domain 計算 | `{presentation/xxx}` | widget test |
| {Infrastructure} | 非 domain（infra）| {外部服務/持久化/匯入匯出}（{FR}） | domain 計算 | `{data/xxx}` | repository test |

### Bundle 不變式清單（per-bundle）

<!-- 逐 bundle 列出 domain 行為不變式（業務規則、邊界、狀態轉換）。供 version-bootstrap
Step 5 測試設計逐條列舉為 domain unit test，不靠「剛好出現於 UC 場景」被動覆蓋。
判準見 domain-bundle-mapping-methodology §4。 -->

| Bundle | 不變式（每條可轉一個 unit test） |
|---|---|
| {Aggregate} | {如：缺漏項沿用前次值不歸零；狀態轉換前置條件} |
| {Kernel} | {如：估值套用折舊現值；總額 = Σ 資產 − Σ 負債} |
| {Read-model A} | {如：占比加總 = 1；比率分母為 0 時的定義值} |
| {Supporting VO} | {如：折舊不低於 salvage；purchased 之前回傳原值} |

## 4. 邊界決策

<!-- 記錄有真實取捨的 bundle 邊界決策（拍板結論 + 依據）。每個決策一小節。 -->

### 4.1 {決策標題}

{定案結論 + 依據}。若描述的是目標邊界而非現況，明文標註「此為目標邊界，非現況；接線見 §6」（避免依賴宣告與現況漂移）。

## 5. 對實作票的切分指引

<!-- 每張消費本 map 的實作票，說明其層與對齊指引。 -->

| 票 | 層 | domain map 對齊指引 |
|---|---|---|
| {domain 票} | domain | 按 §3 拆 bundle；依賴方向底線見 §2 |
| {data 票} | data | 持久化細節屬 data 層，不混入 domain |
| {presentation 票} | presentation | 衍生值在 presentation 層組合 domain 純函式，畫面聚合在此、不下沉 domain |

## 6. 觀察到的技術債（待追蹤）

<!-- 依賴方向違規、未接線函式等。每項建票或標記追蹤（quality-baseline 規則 5）。 -->

- {技術債項目 + 追蹤票/處理指引}

## 7. FR → Bundle 覆蓋對照

<!-- 逐一比對 spec 全部 FR 到 bundle，確認無遺漏（涵蓋 FR-01 至最後一個 FR）。非 domain 的 FR 標 presentation/data/cross-cutting。 -->

| FR 群 | 覆蓋 | 備註 |
|---|---|---|
| {FR-NN} | {Bundle} | {備註} |
| {FR-NN} | presentation（非 domain）| {畫面/i18n/主題} |
| {FR-NN} | data（非 domain）| {持久化} |

---

**Last Updated**: YYYY-MM-DD | **Source**: {規劃波 ticket ID}
**Template Updated**: 2026-07-23 | **Version**: 2.0.0 — 追加多 aggregate DAG 變體 + command-side bundle 行 + DAG 底線（0.1.0-W2-021）
