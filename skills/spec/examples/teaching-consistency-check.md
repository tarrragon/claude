# Spec Validate 維度 4 教學一致性比對 — 以 v0.2 Spec 審查為例

Spec 寫完後跑 validate，維度 1-3 全過——但和教學一比對才發現 API 路徑不一樣。以下展示 `/spec validate` 維度 4（教學一致性）如何偵測這類偏移。

`/spec validate` 有 Lite（維度 1-3，邊界/錯誤路徑/狀態轉換）和 Full（維度 1-4，額外含教學一致性比對）兩種模式。

---

## 背景

v0.2 的多份 Collector spec 在設計推導過程中產出了一套設計決策，但部分決策與 blog 教學衝突。以下展示維度 4 偵測到的偏移和處理方式。

## 執行 Validate

```
/spec validate docs/spec/collector/SPEC-011-jsonl.md
```

選擇 Full 模式（含維度 4）。

## 維度 4 輸出範例

```
#### 維度 4: 教學一致性

對應教學模組：模組四 — Collector（monitoring/04-collector/）

| 偏移面向 | Spec 值 | 教學值 | 嚴重度 |
|---------|---------|--------|--------|
| 查詢端點路徑 | GET /v1/query | GET /v1/events | 高 |
| Downsample 策略 | 同 name 同小時保留一筆 | 聚合摘要表 | 高 |
| name 匹配語法 | 前綴匹配 | * 萬用字元 → SQL LIKE | 低 |

教學缺口：
- JSONL mirror 的日切 + gzip 行為在教學中未定義
  → 建議先在 blog 04-collector/jsonl-storage.md 補完
```

## 處理偏移

### 高嚴重度：必須對齊

1. **查詢端點**：教學已定義 `GET /v1/events`，spec 對齊改用教學路徑
2. **Downsample**：教學已定義聚合摘要策略，spec 對齊

### 低嚴重度：可延後

3. **name 匹配**：spec 補充萬用字元語意，對齊教學

### 教學缺口：先補教學

4. JSONL mirror 行為不在任何教學章節 → 先在 blog 寫完後再落實 spec

## 教訓

- 高嚴重度偏移不處理的話，SDK 實作會依 spec 實作出與教學不同的 API 路徑，之後改動成本極高
- 教學缺口不是偏移——是 spec 走在教學前面，需要先回補教學再繼續
