# PC-APP-007: 多個 Spawn Request 合併為單票時驗收項遺失與憑空補入

## 基本資訊

- **Pattern ID**: PC-APP-007
- **分類**: 流程合規（process-compliance）
- **風險等級**: 高（agent 提出 2+ Spawn Request 時每次都可能踩）
- **相關 Pattern**: PC-073（spawned vs children 語意）、PC-075（spawned/children 狀態檢查不對稱）、PC-100（衍生票 PCB 未繼承）、PC-166（confabulation 幻覺工具結果）、PC-055（AC 漂移）

---

## 問題描述

### 症狀

執行 agent 在 Exit Status 提出 N 個獨立 Spawn Request（SR-1 ~ SR-N），PM 將其合併為 M 張票（M < N）。合併過程產生四類缺陷，且**彼此獨立發生**，不會一起出現：

| 缺陷 | 表現 | 為何難察覺 |
|------|------|-----------|
| 驗收項整條遺失 | 新票標題保留兩個 SR 的關鍵字，但 acceptance 只承接其中一個 | 標題看起來涵蓋齊全，不讀 acceptance 不會發現 |
| 憑空補入驗收項 | acceptance 出現 source ticket 與所有 SR 均未提及的檔名 | 該檔名**真實存在於 repo**，躲過「檔案不存在」的破綻 |
| 數字無來源 | acceptance 寫「全套件 -N 降至 0」，N 無法從 source ticket 的任何敘述推導 | 數字看起來精確，反而增加可信度 |
| SR status 未回填 | 票建了，但 source ticket 的 SR 條目仍是 `status: pending` | 下個接手者會重複建票 |

### 根本矛盾

**標題層與 acceptance 層的資訊不同步。** 合併時傾向在標題並列兩個 SR 的關鍵字（標題是敘述性的，並列不需成本），但 acceptance 是逐條的，承接第二個 SR 需要實際寫出對應條目——這一步被省略後，標題仍宣稱涵蓋，形成「標題說有、驗收說沒有」的靜默落差。

**憑空補入是 confabulation 的變體。** 撰寫 acceptance 時模型用預期分布填補「這種票應該驗收什麼」，產出的檔名符合專案命名慣例，因而恰好真實存在。PC-166 描述的幻覺工具結果靠 raw stdout 形態辨識，但此處產物是 ticket 欄位，沒有 stdout 可比對，只能靠來源追溯。

**合併本身常違反 atomic ticket。** N 個 SR 之所以被 agent 分開提出，往往正因為它們性質不同（例：補翻譯資源 vs debug 佈局約束）。合併等於把兩種需要不同技能、不同驗收方式的工作綁在一張票上。

---

## 偵測方式

### 對每張由多個 SR 合併而成的票

```bash
# 1. acceptance 每個檔名/測試名是否有來源
#    對 source ticket body 與所有 SR 描述做全域 grep，排除新票自身
grep -rn "<acceptance 中出現的檔名>" <worklog 目錄> | grep -v "<新票 ID>"
# 零命中 = 無來源支撐，該條目屬憑空補入
```

```bash
# 2. SR 數量 vs 已落地數量對照
grep -c "^- \*\*SR-" <source-ticket>.md          # SR 總數
grep -c "status: processed" <source-ticket>.md   # 已落地數
# 兩數不等 = 有 SR 未處理
```

### 逐條對照表（合併前必做）

| SR 編號 | 承接票 | 對應 acceptance 條目 |
|---------|--------|---------------------|
| SR-1 | ? | ? |
| SR-N | ? | ? |

任一格為空即為缺口。**「標題有提到」不算承接**，必須有可驗證的 acceptance 條目。

---

## 防護措施

### 規則層

1. **SR 一對一建票為預設**。合併需明確論證兩個 SR 性質相同（同技能、同驗收方式、同檔案範圍），論證寫入新票的 Problem Analysis。
2. **acceptance 每條須可回溯**至 source ticket body 或某個 SR 的具體敘述。寫不出來源就不該存在。
3. **數字不寫死在 acceptance**。「全套件降至 0」優於「-5 降至 0」——後者的 5 會過期，且無法驗證來源。
4. 建票後**立即回填** SR `status: processed (<日期>) -> <新票 ID>` 或 `dismissed + 理由`（quality-baseline 規則 5）。

### Hook 層現況與缺口

`acceptance-gate-hook` 已在 complete 前偵測「Spawn Requests 尚有未處理條目」，可攔截缺陷四（status 未回填）。

**但它偵測不到缺陷一至三**——它只檢查 SR 條目的 status 欄位，不驗證新票的 acceptance 是否真的涵蓋該 SR 的驗收需求，也無法判斷某條 acceptance 是否有來源。此為已知缺口，補強方向：合併建票時要求填寫 SR 到 acceptance 的對照表，由 hook 驗證每個 SR 至少對應一條 acceptance。

---

## 案例背景

某 test-only scope 的 IMP 票以 `partial_success` 結束，Exit Status 誠實回報 `acceptance_unmet`，並提出兩個獨立 SR（一為補 i18n 翻譯資源，一為修 lib 佈局約束）。同時其 body 敘述中另有兩項被判定為 flaky 的測試。

後續將兩個 SR 壓成單一張票，結果：i18n 的驗收整條消失（標題仍寫著 i18n）、acceptance 憑空多出一個從未被提及但真實存在的測試檔、殘留數字無法從任何來源推導、兩項 flaky 完全無票承接。三個缺口在同一張票上並存，而 hook 只攔到 SR status 未回填。

**執行 agent 沒有犯錯。** 缺口全部發生在 spawn 落地環節。這是本 pattern 值得記錄的核心——agent 端的 Exit Status 協議運作良好時，缺陷會完整地轉移到接手處理的一方。

附帶教訓：該票的 flaky 判定僅取樣 3 次，低於 quality-baseline 規則 1 邊界要求的 N >= 5 門檻。合併建票時若連同繼承此結論，會讓取樣不足的判斷取得「已被追蹤」的正當性。

---

## 相關規則

- `.claude/rules/core/quality-baseline.md` 規則 5（所有發現必須追蹤；Solution 內 spawn 落地確認）與規則 1 邊界（flaky 取樣 N >= 5）
- `.claude/pm-rules/ticket-body-schema.md`（Spawn 落地確認子節）
- `.claude/rules/core/tool-output-trust-rules.md` 規則 3（用無法腦補的固定值交叉驗證——此處的固定值是 grep 的零命中）
- `.claude/references/field-semantics.md`（spawned_tickets vs children 語意）

---

**建立日期**: 2026-07-10
**Version**: 1.0.0
