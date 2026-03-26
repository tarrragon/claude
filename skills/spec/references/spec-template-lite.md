# Spec 模板 — Lite 模式

適用於小型修改、Bug 修復、單一模組調整。3 個必填區段，目標總量 < 2K tokens。

---

## 模板

```markdown
# {Ticket ID} 功能規格

## 1. Purpose（目的）

<!-- 指引：用 1-3 句話回答以下問題。目標 < 200 tokens。
     - 這個功能解決什麼問題？
     - 為誰解決？（用戶/開發者/系統）
     - 成功的定義是什麼？
-->

{問題描述}。{目標用戶}需要{期望結果}。

## 2. Scenarios（行為場景）

<!-- 指引：用 GWT 格式描述每個行為場景。目標 2-5 個場景，< 800 tokens。
     - 至少 1 個正常流程場景
     - 至少 1 個異常/邊界場景
     - 每個場景的 Then 必須是可驗證的具體結果（非模糊描述）
-->

### 場景 1: {正常流程名稱}
- **Given**: {前置條件——系統處於什麼狀態}
- **When**: {觸發動作——用戶或系統做了什麼}
- **Then**: {預期結果——可觀察到什麼變化}

### 場景 2: {異常/邊界名稱}
- **Given**: {前置條件}
- **When**: {觸發動作}
- **Then**: {預期結果}

## 3. Acceptance（驗收條件）

<!-- 指引：列出可直接驗證的條件。目標 3-6 條，< 300 tokens。
     - 每條以 checkbox 格式開頭
     - 每條必須是「可觀察、可量化」的（避免「正確處理」「適當回應」等模糊詞）
     - 條件應覆蓋所有 Scenarios 的 Then
-->

- [ ] {條件 1：對應場景 1 的可驗證結果}
- [ ] {條件 2：對應場景 2 的可驗證結果}
- [ ] {條件 3：非功能性要求，如效能/相容性}
```

---

## Lite 填寫範例（Bug 修復場景）

```markdown
# 0.2.0-W3-008 功能規格

## 1. Purpose（目的）

Stop Hook 將 direction=auto 的 pending handoff JSON 視為阻塞性錯誤（block），
但 direction=auto 表示「由系統自動判斷方向」，不代表交接有問題。
修正為 INFO 級別提示，不阻塞 session 結束。

## 2. Scenarios（行為場景）

### 場景 1: direction=auto 的 pending handoff
- **Given**: 存在一個 direction=auto 的 pending handoff JSON
- **When**: Stop Hook 執行檢查
- **Then**: 輸出 INFO 級別提示，不阻塞（exit 0）

### 場景 2: direction 為空的 pending handoff
- **Given**: 存在一個 direction 為空字串的 pending handoff JSON
- **When**: Stop Hook 執行檢查
- **Then**: 輸出 WARNING 級別提示，建議執行 /ticket handoff

### 場景 3: 無 pending handoff
- **Given**: 不存在任何 pending handoff JSON
- **When**: Stop Hook 執行檢查
- **Then**: 無輸出，正常結束（exit 0）

## 3. Acceptance（驗收條件）

- [ ] direction=auto 的 handoff 不再觸發阻塞
- [ ] direction 為空字串的 handoff 輸出 WARNING（非 block）
- [ ] 無 pending handoff 時無任何輸出
- [ ] 所有現有測試通過
```

---

## Lite validate 維度（3 個核心維度）

Lite 模式的 `/spec validate` 只掃描以下 3 個維度：

| # | 維度 | 核心問題 |
|---|------|---------|
| 1 | 邊界完整性 | 極端值、空值、上限下限的行為定義了嗎？ |
| 2 | 錯誤路徑 | 每個操作失敗時，系統如何回應？ |
| 3 | 狀態完整性 | 所有狀態和轉換都定義了嗎？ |

---

**Version**: 1.0.0
**Last Updated**: 2026-03-25
