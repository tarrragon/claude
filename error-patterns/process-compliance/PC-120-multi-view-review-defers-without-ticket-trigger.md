---
id: PC-120
title: 多視角審查結論未轉換為合法決策狀態 — 「P3 / 不建立 ticket」灰區
category: process-compliance
severity: medium
status: active
created: 2026-05-03
related:
- PC-093
- PC-119
- decision-trigger-binding
---

# PC-120: 多視角審查結論未轉換為合法決策狀態 — 「P3 / 不建立 ticket」灰區

## 問題描述

linux / bay / thyme 等視角 agent 完成審查後，PM 整合三視角結論時，將 agent 原始措辭（「P3 / 暫不需要」「未來可考慮」「將來 ticket」「定期走查」）原汁原味保留為 ticket 內容，未轉換為 `decision-trigger-binding.md` 規則 1 / 規則 2 的合法狀態。

agent 視角報告中的優先級標記是「審查語氣」（descriptive），不是「決策狀態」（prescriptive）。「P3」描述「重要性低」但不指明後續處置；「不建立 ticket」明示拒絕綁 trigger 但未轉為「永久決策」。兩者組合落入規則 1 禁止的「第三種狀態」灰區。

**Why**：multi-view review 的價值在於暴露結構性問題與優先級評估，但 agent 不負責決策狀態轉換——這是 PM 整合階段的職責。若 PM 直接轉貼 agent 措辭而不做狀態轉換，「P3 / 不建 ticket」會在 ticket md 中沉澱為永久灰區條目，後人接手不知該不該做、何時做、如何判斷做完。

**Consequence**：違規累積後，ticket 內容與 `decision-trigger-binding.md` 規則 1 / 規則 2 衝突。多視角審查的 follow-up 表格成為「待詮釋文字」而非「可執行清單」，違反 `quality-baseline.md` 規則 5（所有發現必須追蹤）。後人 audit 時難以辨識「這個 P3 是已決策不做」「還是暫時不做」「還是該做但忘了」。

**Action**：

PM 整合多視角審查結論時，每項 follow-up 必須轉為以下三種合法狀態之一：

| 狀態 | 寫法 | 適用情境 |
|------|------|---------|
| (a) 永久決策不做 | 「永久決策：不做 X。理由：Y。若日後 Z 條件成立，重新建獨立 ANA 評估，不延續本評估」 | agent 認為當前無驅動因素 |
| (b) 立即建 ticket | `/ticket create --type IMP/ANA --action ... --priority P2/P1.5` | agent 識別明確優化機會 |
| (c) 建監測 ticket（規則 2 標準路徑） | 建追蹤 ticket（含量化條件），本決策標 `blockedBy: [<ticket-id>]` | 等量化閾值或外部訊號 |

**禁止**：保留「P3 / 暫不需要 / 不建立 ticket」「將來 ticket」「未來可考慮」「定期走查」「等真實需求」等措辭。

---

## 觸發案例

### 案例：W17-008.5.6.2 三視角審查整合（2026-05-03）

W17-008 group 三視角審查（linux + bay + thyme）完成後，PM 整合 follow-up 表格，多項條目落入違規灰區：

#### 違規 1：ErrorEnvelope v2 升級規劃

```
| ErrorEnvelope v2 升級規劃 | 無 | **暫不需要**。v1 schema 四欄位涵蓋目前所有 callsite，
未見 v2 需求驅動因素。等出現「需要 severity / locale / structured hint」等真實需求時再規劃。
維持 P3 / 不建立 ticket。 |
```

問題：「等真實需求時再規劃」屬規則 2 反模式（等外部訊號），必須先建監測 ticket。「真實需求」無量化判定機制，「P3 / 不建立 ticket」明示拒絕綁 trigger 但未轉為「永久決策」。

#### 違規 2：errno_pattern_registry 共用模組

```
未來可考慮共用 `errno_pattern_registry` 模組——P3，目前不需動。
```

問題：「未來可考慮」+「目前不需動」雙重無 trigger 延後。

#### 違規 3：W17-117.2 「未來擴充風險」

```
**未來擴充風險**：bay 視角識別「callsite 增長後選擇隨意」屬 P3 風險，
建議定期 grep 走查；當前無需獨立 trigger ticket
```

問題：「定期 grep 走查」是長期週期條件，必須先建監測 ticket。

#### 違規 4：W17-008.5.5「不在本 ticket 範圍」

```
- ErrorEnvelope v2 升級規劃（將來 ticket）
```

問題：「將來 ticket」未指明 ticket ID，屬規則 1 違規。

### 共同特徵

| 特徵 | 說明 |
|------|------|
| agent 措辭原汁原味保留 | linux / bay / thyme 用「P3」「不需要」「未來」等審查語氣，PM 整合時未轉換 |
| 「P3 + 不建 ticket」誤認為合法選項 | 規則 1 明示「沒有第三種狀態」，優先級標記不能取代 trigger 綁定 |
| 「重新評估時再規劃」變相否定追蹤 | 「等量化條件成立時再做」必須先建監測 ticket，否則永遠不會被觸發 |
| 跨多個 ticket 重複 | W17-008.5.5 / W17-008.5.6.2 / W17-117.2 三處違規同源 |

---

## 根因分析

### 直接原因

PM 整合多視角審查時，將「視角報告」（descriptive）誤等同於「決策結論」（prescriptive）。三視角產出本身屬於發現與評估，需要 PM 在整合階段做決策狀態轉換，但 PM 跳過此步驟直接轉貼。

### 結構性原因

1. **multi_view_status: reviewed 不等於決策完成**：reviewed 標記只表示「審查已執行」，未保證「結論已轉為合法狀態」。current schema 沒有「decision_state_per_followup」欄位強制每項 follow-up 標明 (a)/(b)/(c) 狀態。
2. **agent 措辭預設為「審查語氣」而非「決策狀態」**：agent 視角報告 prompt 沒有要求 agent 用 (a)/(b)/(c) 三狀態結論，agent 自然用「P3 / 暫不需要」等中性措辭。
3. **memory `feedback_no_deferred_decisions` 不涵蓋 multi-view 情境**：memory 提醒禁用無 trigger 延後，但未明示「PM 整合 multi-view 時必須轉換 agent 措辭」這層執行細節。

### 為何 agent prompt 不直接要求 (a)/(b)/(c)

可以，但這不是當前 parallel-evaluation skill 設計範疇。skill 著重「視角差異互補」，「決策狀態轉換」屬 PM 整合職責。修法應為：

- PM 整合 prompt 加入「將每項 follow-up 轉為 (a)/(b)/(c) 三狀態之一」明示要求
- 或在 ticket schema 強制 multi-view ANA Solution 章節含「Follow-up Decision State」表格欄位

---

## 防護建議

### 短期（行為自律）

1. PM 整合多視角審查報告時，逐項檢查 follow-up 措辭是否含「P3 / 暫不需要 / 未來 / 將來 / 定期 / 等 X 條件」，命中即觸發 (a)/(b)/(c) 三狀態轉換
2. ticket md「Follow-up 建議」表格明示加上「決策狀態」欄位（已決策 / 已建 ticket / 已建監測 ticket）

### 長期（結構性防護）

1. **ticket schema 擴充**：multi-view ANA ticket 強制 frontmatter 含 `followup_decisions: list[str]`，每項格式為 `<title>: state=(a|b|c), ticket=<id-or-empty>, rationale=<short>`
2. **hook 偵測**：multi-view ticket 的 Solution 章節含「P3 / 不建立 ticket / 將來 ticket / 未來可考慮 / 定期走查」字樣時 warn
3. **parallel-evaluation skill 補強**：skill description 增加「PM 整合階段須將 agent 措辭轉為 (a)/(b)/(c) 三狀態」明示步驟

---

## 與其他規則的邊界

| 規則 / 模式 | 聚焦 | 與本規則差異 |
|-------------|------|-------------|
| `decision-trigger-binding.md` | 兩種合法狀態（已決策 / 綁 ticket trigger 延後） | 本規則為 multi-view 整合情境的具體執行落實 |
| PC-093 | 描述 YAGNI 延後決策累積反模式 | PC-093 為現象描述；本規則為 multi-view 情境的事前防護 |
| PC-119 | parallel-evaluation 單派 linux 違反三人組協議 | 同 W17-008.5.6.2 事件衍生；PC-119 處理派發協議，本規則處理整合階段 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤 | 本規則延伸：發現追蹤的合法形式必須是 (a)/(b)/(c) 三狀態 |

---

## 結論

multi-view review 的 follow-up 表格不是「審查筆記」而是「決策清單」。PM 整合階段必須將 agent 措辭轉為 `decision-trigger-binding.md` 規則 1 的合法狀態（已決策 a / 綁 trigger b），「P3 / 不建立 ticket」是規則 1 禁止的第三種狀態。

修正路徑：(a) 永久決策不做（含拒絕理由）、(b) 立即建 ticket、(c) 建監測 ticket（綁量化條件）。三選一無例外。
