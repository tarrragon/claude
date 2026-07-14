---
id: PC-APP-010
title: code agent 杜撰 UC- 前綴偽需求 ID——TDD 實作註解未對照 spec use case
severity: medium
category: process-compliance
created: "2026-07-14"
source_tickets: [0.38.1-W1-046, 0.38.1-W1-045]
related_patterns: [PC-APP-009]
---

# PC-APP-010: code agent 杜撰 UC- 前綴偽需求 ID

## 症狀

實作程式碼的 `需求：[UC-XXX]` 註解引用大量 `UC-` 編號，但這些編號多數在需求規格（`use-cases.md`）中不存在。實作 agent 在 TDD 各階段為內部函式/元件自行發明「需求 ID」，濫用 `UC-` 前綴，卻從未對照 spec 定義的真實 use case。

**識別特徵**：
- code 的 UC 引用數遠超 spec 定義數（實證：code 38 個不同 token vs spec 10 個）。
- 多種編號方言並存：單位數（`UC-1`）、兩位數（`UC-01`）、三位數扁平（`UC-013`）、三位數階層（`UC-008.1.1`）——出自不同 agent 不同時期。
- 語意碰撞：同一編號跨無關 domain（`UC-008` 同時標註 query builder / test repair / json classifier）；同一語意用不同編號（`UC-013` 與 spec `UC-02` 皆為「匯出」）。

## 實證案例（0.38.1-W1-046，2026-07-14）

W1-045 回填單一 spec（UC-001）時發現 code 引用它但 spec 缺失。延伸稽核 `lib/` 全量 UC 引用揭露系統性斷裂：

| 面向 | 數字 |
|------|------|
| spec 定義真 UC | 10（UC-01~09 + UC-001） |
| code 引用不同 token | 38 |
| 其中可追溯 spec 的真 UC | 10 |
| 杜撰的偽需求 ID | 28（UC-002.1.x 書籍新增、UC-008.1.x 測試修復、UC-015~019 相似度、UC-041~045 API 方法…） |

ticket 草稿原估「17 vs 10」，實測 38 vs 10——**接手者獨立驗證揭露斷裂規模遠超草稿**（呼應 PC-162：ticket 描述是草稿）。

## 根因

1. **UC- 前綴無使用約束**：缺乏「`UC-` 只能標註可追溯 spec 的真 use case」的規則，agent 遂把它當通用「需求註解」前綴，為任何函式/元件發明編號。
2. **TDD 分階段 + 多 agent**：每個 domain 由不同 agent 在不同時期實作，各自發明編號體系，無共用 SSOT 對照，方言必然分裂。
3. **註解不進 CI/lint**：`UC-XXX` 是純註解，不被任何靜態檢查驗證是否對應真 UC，斷裂靜默累積至稽核才暴露。

**後果**：需求追溯完整性崩解——無法從 spec UC 反查實作、無法確認 UC 測試覆蓋、把實作細節誤當需求。修復成本隨引用量放大（本例 ~90 檔）。

## 解決方案

**稽核時**：全量 grep 而非信任草稿數字，並區分真/偽 UC（策略 A 真/偽分流）：

```bash
grep -rhoE 'UC-[0-9]+' lib/ | sort | uniq -c        # code 全量 token
grep -oE 'UC-[0-9]+' docs/app-use-cases.md | sort -u  # spec 定義
```

- **真 UC**（追溯 spec）：保留 `UC-` 前綴，統一為單一格式。
- **偽 UC**（杜撰內部 ID）：改標為內部前綴（如 `FR-`）或語意化元件註解，移除 `UC-` 前綴。禁止把偽 UC 回填進 spec（會把實作細節污染成需求）。

## 預防措施

1. **規則層**：明訂「`UC-` 前綴只能引用 `use-cases.md` 已定義的 UC」，實作 agent 需要標註內部需求時用區隔前綴（`FR-`/`REQ-`）。
2. **Hook 層（建議）**：commit-time 掃 `lib/` 的 `UC-\d+` 引用，對照 spec 定義集，命中未定義編號則 WARNING。使斷裂在源頭可見，不累積到稽核。
3. **回填前先稽核**：回填單一 spec 前全量掃描 code UC 引用比對 spec（memory `feedback_spec_backfill_audit_full_uc_references`），斷裂常非孤例。

## 相關

- `feedback_spec_backfill_audit_full_uc_references`（memory）——回填前全量掃描
- PC-APP-009——規範描述多載體漂移（同屬追溯一致性家族）
- 修復 tickets：0.38.1-W1-047（格式/改標決策 foundation）→ W1-048（偽 UC 改標）/ W1-049（spec 對齊）
