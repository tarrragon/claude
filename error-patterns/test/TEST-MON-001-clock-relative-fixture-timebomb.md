---
id: TEST-MON-001
title: 硬編碼時間戳 fixture × 時間相對查詢窗 = clock 時間炸彈
type: test
severity: high
status: active
source: 0.2.0-W1-008 incident-responder 根因分析
related:
  - PC-168
  - TEST-001
  - pre-fix-eval
---

# TEST-MON-001: Clock-relative Fixture 時間炸彈

## 摘要

測試 fixture 硬編碼絕對時間戳（如 `2026-06-22T10:00:00Z`）搭配產品端「無 from/to 時預設查最近 N 小時」（時間相對查詢窗）= **clock 時間炸彈**。寫測當天 fixture 落在查詢窗內全綠；wall-clock 推進到 `now - N` 超過 fixture 日期後，預設窗排除全部 fixture → 查詢回 0、整批整合測試由綠轉紅。本質是「發布時 false-positive、數天後變紅」的延遲失效。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| 整合測試「POST accepted 但 Query/Count 回 0」 | `expected total=N, got 0` 大量出現 |
| 只 POST 不查的測試（如只檢 accepted 數）不受影響 | 失敗集中在「寫入後查詢」類 |
| 隔離單跑 vs 全套件結果一致（非 flaky） | 確定性失敗（0.00s），非 race |
| 「昨天還綠、今天紅」且無相關 commit | git log 顯示 storage/query 近期無實質變更 |

## 根因

fixture 的**絕對時間基準**與查詢的**相對 now 基準**是兩個獨立時間軸，隨真實時間漂移。測試在固定時間點驗證，看不到未來漂移。容易誤判為「最近某個 storage/query commit 引入回歸」——本案 PM 初判 `ORDER BY ASC→DESC` 變更是元兇，incident-responder 用時間窗數學（`now-24h` vs fixture 日期 `2026-06-22`）排除它，定位真因是 fixture。

## 防護

1. 整合/查詢測試 fixture 時間戳改**相對 now**（`now - 2h + offset`），落在預設查詢窗內，保留相對 offset 維持排序/範圍語意。
2. 靜態共享 fixture（如 `schema/test-fixtures/*.json`）無法相對化 → **載入時改寫時間戳**（`LoadFixtureRecent` 模式），不動共享契約檔，避免污染 schema 驗證測試。
3. 見此症狀先查「產品是否有時間相對預設窗 × fixture 是否硬編碼過去時間」，**派 incident-responder 而非自修**（skip-gate）——時間窗數學能快速排除無辜 commit。

## 來源

0.2.0-W1-008（根因分析）→ 0.2.0-W1-009（fixture 相對化修復）。專案 memory `clock-timebomb-fixture` 升級（0.2.0-W4-005）。
