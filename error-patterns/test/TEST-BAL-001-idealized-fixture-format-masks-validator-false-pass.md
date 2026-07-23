---
id: TEST-BAL-001
title: 測試 fixture 用理想化格式，真實輸入格式不同致 validator 靜默假通過
severity: high
category: test
source_ticket: 0.1.0-W2-016.3
related:
 - PC-165
---

# TEST-BAL-001：理想化測試 fixture 遮蔽 validator 假通過

## 症狀

一個機械 validator / gate（覆蓋檢查、格式檢查、解析器）對真實目標檔案執行時回傳 exit 0「通過」，但**實際一個項目都沒檢查**——因為它的解析 regex / parser 只認測試 fixture 用的理想化格式，真實檔案用了不同但合法的變體格式，導致抽取結果為空集、差集為空、假通過。

**本案具體樣態**（W2-016.3 check_domain_coverage.py）：

- validator 抽 spec FR：`FR_HEADER_RE = ^###\s+(FR-\d+):`（只認 H3 `### FR-XX:`）。
- 單元測試的 fixture 全用 H3（對齊 domain-map-template 的 H3 慣例）→ 11 測試全綠。
- 手動整合驗證對真實 SPEC-001 執行 → 輸出「檢核通過」exit 0。
- 但真實 SPEC-001 的 26 個 FR 全用 **H4** `#### FR-XX:` → `extract_spec_frs = ∅` → 覆蓋差集為空 → 假通過。gate 的動機（抓漏覆蓋的 FR）被自己架空。

## 根因

**測試 fixture 由撰寫者依「理想格式」構造，與真實資料的格式變體分歧**。撰寫者寫 validator 時腦中的格式（H3）也是寫測試時的格式，兩者同源；測試綠燈只證明「validator 對撰寫者想像的格式正確」，不證明「對真實輸入正確」。這是 quality-baseline 規則 1 邊界「測試綠燈不等於 Runtime 正確」的解析器變體——手動整合驗證也被同一假綠燈欺騙（輸出「通過」時無人追問「真的檢查了幾項」）。

**一般化**：任何「解析真實文件 → 抽取項目 → 比對」的 validator，若測試 fixture 的格式由撰寫者構造而非取自真實樣本，就有「抽取回空集 → 假通過」的風險。空集的語意是「沒有不符」與「沒東西可檢查」重疊——validator 不區分兩者即假通過。

## 解決方案

1. **放寬解析 regex 容納真實變體**：`^###\s+` → `^#{3,}\s+`（H3 以上任一層級）。
2. **加真實格式的回歸測試**：用真實檔案實際用的格式（H4）構造 fixture，證明抽取非空。
3. **對真實目標重驗抽取數量**：不只看 exit code，確認「抽到幾項」非零（本案：spec FRs found 應為 26，非 0）。

## 預防措施

| 情境 | 動作 |
|------|------|
| 寫解析真實文件的 validator | 至少一個測試 fixture 取自**真實樣本**格式，不全用撰寫者構造的理想格式 |
| validator 回「通過」 | 追問「抽取到幾項」——抽取數為 0 卻通過是假通過訊號，validator 應對「空抽取」發 warning 而非靜默 pass |
| 整合驗證 | 不只看 exit 0，用固定值（抽取計數）交叉驗證真的檢查了東西（呼應 tool-output-trust 規則 3） |

**validator 設計原則**：「沒有不符」與「沒東西可檢查」是不同語意，validator 應區分——抽取回空集時輸出「未抽到任何待檢項目（格式不符？）」而非「檢核通過」。

## 相關

- 來源：`0.1.0-W2-016.3`；由 multi-round-review Round 2-C（可執行性 walkthrough 對真實 SPEC-001）抓出——單元測試（理想 fixture）與撰寫者手動整合驗證皆未觸及，證明「對真實輸入執行」是不可省的 frame。
- 相關：`PC-165`（false-positive fix chain，mock 遮蔽 runtime）、quality-baseline 規則 1 邊界（測試綠燈 ≠ Runtime 正確）、`tool-output-trust-rules` 規則 3（固定值交叉驗證）。
