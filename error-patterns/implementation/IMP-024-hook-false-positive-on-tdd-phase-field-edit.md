# IMP-024: phase-completion-gate-hook 在編輯 tdd_phase 欄位時誤觸 Phase 3b 完成警告

## 分類
- **類型**: implementation
- **嚴重度**: 低
- **發現版本**: v0.1.0
- **發現日期**: 2026-03-08
- **來源 Ticket**: 0.1.0-W11-004

## 模式描述

`phase-completion-gate-hook` 使用關鍵字比對偵測 Phase 3b 完成（偵測文字 `"phase3b"`）。
當 PM 在 Ticket frontmatter 更新 `tdd_phase` 欄位到其他值（如 `phase4`、`phase1`、`phase2`）時，
若變更後的文字中仍包含 `"phase3b"`（例如 `tdd_stage` 陣列中的 `- phase3b` 條目），
hook 會誤判為「Phase 3b 剛完成」，觸發不必要的 AskUserQuestion #13 提醒。

## 具體案例

### 案例：W11-004 TDD Phase 推進中

PM 執行 Phase 4a 完成後，將 `tdd_phase: phase3b` 更新為 `tdd_phase: phase4`。
檔案中 `tdd_stage` 欄位保留了歷史陣列：

```yaml
tdd_stage:
- phase1
- phase2
- phase3a
- phase3b  # ← hook 看到這行，誤判為 Phase 3b 新完成
- phase4
```

hook 偵測到文字 `phase3b` 出現在被 Edit 的檔案，觸發 Phase 3b 完成提醒，
即使此次變更是 `phase4` 更新（D3a 全自動路由，不需要 AskUserQuestion）。

## 根本原因

hook 使用簡單字串比對（`"phase3b" in modified_content`），未區分：
1. `tdd_phase` 欄位（代表「當前所在 Phase」）
2. `tdd_stage` 欄位（代表「已完成的 Phase 歷史清單」）

正確的偵測應只看 `tdd_phase` 欄位的**值從 `phase3b` 變更為其他值**（diff 層次）。

## 影響

- PM 收到誤導性提醒，需要判斷是否為 false positive
- D3a/D3b 全自動路由被干擾，造成不必要的決策中斷
- 嚴重度低：不影響功能，僅造成流程噪音

## 解決方案

### 短期（當前）

識別 false positive 的特徵：
- 剛完成的是 Phase 4（D3a/D3b/D3c）而非 Phase 3b
- `tdd_phase` 欄位的新值不是 `phase3b`
- 可直接忽略提醒，按正確的 D 路由繼續

### 長期（修復 hook）

改用 diff 層次的欄位比對：

```python
# 正確做法：比對 tdd_phase 欄位值的變化
import re

def detect_phase3b_completion(old_content, new_content):
    old_phase = re.search(r'^tdd_phase:\s*(\S+)', old_content, re.MULTILINE)
    new_phase = re.search(r'^tdd_phase:\s*(\S+)', new_content, re.MULTILINE)
    if old_phase and new_phase:
        return old_phase.group(1) == 'phase3b' and new_phase.group(1) != 'phase3b'
    return False

# 錯誤做法：只看新內容是否包含字串
# return 'phase3b' in new_content  # ← false positive 來源
```

## 防護措施

### 開發 Hook 時
- [ ] 偵測「狀態變更」必須比對新舊內容（diff 比對），不可只看新內容是否包含關鍵字
- [ ] YAML 欄位偵測應使用正規表達式精確匹配欄位名稱和值，不使用字串包含判斷
- [ ] 新 Hook 上線前，測試「欄位值從 A 改為 B」和「欄位保留 A 但其他地方提到 A」兩種場景

### 遇到 false positive 時
- [ ] 確認 `tdd_phase` 欄位的當前值（而非 `tdd_stage` 陣列）
- [ ] 對照決策樹 D1/D2/D3 規則，確認正確路由
- [ ] false positive 不阻止流程，按正確路由繼續即可

## 相關錯誤模式

- IMP-020: PostToolUse Hook 共存時的觸發碰撞（同屬 hook 觸發邏輯設計問題）
- IMP-006-D: hook 只覆蓋部分錯誤路徑（同屬「偵測邏輯不完整」類型）
