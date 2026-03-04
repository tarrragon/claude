# PC-002: Ticket 設計建立新功能時未確認現有類似實作

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-002 |
| 類別 | process-compliance |
| 來源版本 | v0.31.1 |
| 發現日期 | 2026-03-04 |
| 風險等級 | 中 |
| 來源 | 0.31.1-W5-001 執行過程 |

### 症狀

1. Ticket 的 `where.files` 指定了一個不存在的新檔案（如 `branch-edit-guard-hook.py`）
2. 執行代理人分析現有程式碼後發現，類似功能的檔案已存在（`branch-verify-hook.py`）
3. 實際只需修改現有檔案的少量行為（如 "ask" 改為 "block"），而非建立全新實作
4. 代理人需要中途更改執行策略，造成設計文件不一致

### 根本原因（5 Why 分析）

1. Why 1：Ticket `where.files` 寫入了不存在的新檔案名稱
2. Why 2：Ticket 建立者（PM）依據錯誤模式文件（PC-001）直接構想解決方案，未先搜尋現有程式碼
3. Why 3：建立 Ticket 前缺乏「現有功能搜尋」步驟
4. Why 4：系統分析師（SA）前置審查未觸發（任務被視為 IMP 直接指派）
5. Why 5：根本原因：「建立新功能型 Ticket」與「修改現有功能型 Ticket」的設計決策缺乏強制的現有程式碼確認步驟

---

## 解決方案

### 正確做法

建立任何「新增檔案」類型的 Ticket 前，先搜尋現有類似實作：

```bash
# 搜尋類似功能的現有 hook
grep -l "branch\|protect\|Edit\|Write" .claude/hooks/*.py

# 搜尋特定行為關鍵字
grep -r "is_protected_branch\|protected_branch" .claude/hooks/

# 確認 settings.json 現有 matcher 配置
grep -A3 "Edit\|Write" .claude/settings.json
```

確認搜尋結果後：
- 若**現有實作存在但行為錯誤** → Ticket 設計為「修改現有檔案」
- 若**完全無相關實作** → Ticket 設計為「建立新檔案」

### 錯誤做法（避免）

```yaml
# 錯誤：未搜尋就直接指定新檔案
where:
  files:
  - .claude/hooks/branch-edit-guard-hook.py  # 實際上同功能的 hook 已存在
```

```yaml
# 正確：搜尋後確認修改現有檔案
where:
  files:
  - .claude/hooks/branch-verify-hook.py  # 修改現有 hook 的 decision mode
```

---

## 預防措施

**短期（人工）**：
- Ticket 建立前，對 `where.files` 中的每個新檔案名稱，執行關鍵字搜尋確認無類似實作
- 在 PC-001 等錯誤模式提出「建立新 Hook」解決方案時，先確認是否有現有 Hook 可修改

**長期（SA 審查強化）**：
- 涉及 `.claude/hooks/` 的新增 Ticket，強制觸發 SA 前置審查（現有 Hook 清單掃描）
- 在 Ticket 驗收條件中加入「已確認無現有類似實作」核查項目

---

### 與現有機制的關係

| 機制 | 現況 | 改善建議 |
|------|------|---------|
| SA 前置審查 | Hook 類 IMP Ticket 未強制觸發 | 「新增 hook 檔案」類 Ticket 應強制 SA 審查 |
| 建立後審核 | acceptance-auditor 檢查 Ticket 格式 | 新增：`where.files` 中的新檔案需確認不重複 |
| 錯誤模式建議解決方案 | 直接描述解決方案 | 加入「先確認現有實作」提示 |

### 關聯

- 發現 Ticket: 0.31.1-W5-001
- 相關 Hook: `.claude/hooks/branch-verify-hook.py`
- 相關錯誤模式: PC-001（觸發此 Ticket 建立的錯誤）

---

**Last Updated**: 2026-03-04
**Version**: 1.0.0
