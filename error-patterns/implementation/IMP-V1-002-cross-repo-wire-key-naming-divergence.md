---
id: IMP-V1-002
title: 跨 repo 交換格式 wire key 命名慣例分歧（DB snake_case 洩漏至 wire format）
category: implementation
severity: medium
first_seen: 2026-06-18
ticket: 1.0.0-W5-004
status: resolved
---

## 症狀

V1↔APP 跨端 canonical round-trip 驗證中，V1 匯入 APP 匯出的 canonical JSON 後 `readingStatus` 欄位為 `undefined`。V1 adapter 的 `mapCanonicalToV1Book` 找不到 `tags.readingStatus` key。

## 根因

APP 端 `Book._groupBookTags()` 直接用 DB 的 `tag.categoryId`（`reading_status`，snake_case）作為匯出 JSON 的 tags key。spec（book-interchange-v1 §5/§7）定義 wire format 為 camelCase（`readingStatus`）。APP 匯入方向有 `TagCategoryIds.canonicalCategoryId()` 做 wire→DB 正規化，但匯出方向缺少反向映射（DB→wire）。

## 行為模式

跨 repo 共用交換格式時，兩端各自實作 adapter。當一端的 DB schema naming convention（snake_case）與 wire format naming convention（camelCase）不同，且匯出方向未做 DB→wire 轉換，DB 的 snake_case 會洩漏至 wire output，使另一端 adapter 找不到對應 key。

匯入方向通常先實作且有測試（因為需要 parse 外部輸入），匯出方向的反向映射容易遺漏。

## 解決方案

1. 在 `TagCategoryIds` 新增反向映射 `wireCategoryKey()`（DB snake_case → wire camelCase）
2. `Book._groupBookTags()` 使用 `wireCategoryKey()` 而非直接用 `tag.categoryId`
3. 反向映射表由既有 `_wireKeyToCanonical` 自動生成（單一維護點）

## 預防措施

- 跨 repo 交換格式實作 adapter 時，匯入和匯出方向都需要 naming convention 轉換
- round-trip 整合測試應涵蓋雙向（V1→APP→V1 + APP→V1→APP），不只單向
- wire format 的 key naming 以 spec 為 SSOT，兩端 adapter 各自負責 DB↔wire 轉換
