---
id: IMP-063
title: Hook 路徑分類混淆 context 引用與實作目標
category: implementation
severity: high
first_seen: 2026-04-16
related_patterns:
- ARCH-015
---

# IMP-063: Hook 路徑分類混淆 context 引用與實作目標

## 症狀

實作代理人派發 prompt 中同時引用 `.claude/skills/...`（實作目標）和 `docs/work-logs/...`（ticket/worklog context 引用）時，dispatch validation hook 誤判為跨路徑混合，三次連續派發都被阻擋。

形成「修 `.claude/` 框架程式碼時派發完全卡死」的雙向阻塞，與 ARCH-015 的 worktree 寫保護疊加形成不可達狀態。

## 根因

Hook 路徑分類器（`_NON_CLAUDE_PATH_PATTERN`）將 `docs/` 列為「非 `.claude/` 實作目標路徑」，但實際使用場景中：

| 路徑模式 | Hook 假設 | 實際用途 |
|---------|-----------|---------|
| `src/`, `tests/`, `lib/`, `app/` | 實作目標 | 通常確實是實作目標 |
| `docs/work-logs/` | 實作目標 | **ticket 檔案引用**（read-only context） |
| `docs/proposals/` | 實作目標 | **提案文件引用**（read-only context） |

PM 派發代理人時必須引用 ticket 路徑才能讓代理人讀取規格，但 Hook 把這視為「修改 docs/」。

## 設計意圖與使用場景脫鉤

| 維度 | 設計時假設 | 實際使用 |
|------|-----------|---------|
| `docs/` 用途 | 文件編輯（如 README、design doc） | ticket/worklog 引用為主 |
| 路徑出現位置 | Edit/Write 上下文 | Read 上下文（context 引用） |
| 派發頻率 | 偶爾 | 高頻（每個派發 prompt 都會引用 ticket） |

設計時未區分「prompt 中提到路徑」=「要寫入該路徑」的兩種情境。

## 影響範圍

- 所有需要修改 `.claude/` 框架程式碼的派發都會被阻擋
- 包括 Hook 修復、Skill 升級、CLI 修復、規則更新
- ARCH-015 已限制 `.claude/` 必須在 main cwd 派發；本 hook 又要求 worktree；兩者疊加形成不可達

## 防護措施

### 1. 路徑分類必須區分 context vs target

| 路徑類型 | 分類 | 處理 |
|---------|------|------|
| `src/`, `tests/`, `lib/`, `app/` | 實作目標 | 觸發 worktree 強制 |
| `docs/work-logs/`, `docs/proposals/` | context 引用 | 不觸發跨路徑檢查 |
| 含 `Edit/Write/修改` 動詞 + 路徑 | 實作目標 | 觸發 worktree 強制 |
| 純路徑引用（`Ticket: docs/...`） | context 引用 | 不觸發跨路徑檢查 |

### 2. Hook 設計時必須做使用場景檢驗

撰寫路徑分類邏輯前必須回答：
- 此路徑出現在 prompt 中代表什麼？（要寫入 vs 要讀取 vs 純引用）
- 高頻使用場景中此路徑會被使用嗎？（如果會，設計必須涵蓋）
- 是否與其他規則疊加形成不可達狀態？（如 ARCH-015 + 本 hook）

### 3. 雙向阻塞自我檢測

當兩個強制規則導致某個合理操作完全無法執行時，至少有一個規則需要放寬。識別流程：
1. 列出規則 A 和規則 B 的強制要求
2. 檢查是否存在「同時滿足 A 和 B」的可行路徑
3. 若無 → 立即修改規則（不能等下次 session）

## 自我檢查清單

撰寫或審查路徑分類 Hook 時：

- [ ] 路徑分類器是否區分「實作目標」vs「context 引用」？
- [ ] `docs/` 等高頻 context 路徑是否被誤列為實作目標？
- [ ] 與其他 Hook/規則疊加是否會產生不可達狀態？
- [ ] 是否有逃生閥（如 `--force` 旗標、明確豁免清單）？

## 修復範例

```python
# 錯誤（會產生雙向阻塞）：
_NON_CLAUDE_PATH_PATTERN = re.compile(
    r"(?<![./\w])(?:src|tests?|lib|docs|app|assets|scripts|public|bin|cmd)/"
)

# 正確（移除 docs，因為 docs/ 多為 context 引用而非實作目標）：
_NON_CLAUDE_PATH_PATTERN = re.compile(
    r"(?<![./\w])(?:src|tests?|lib|app|assets|scripts|public|bin|cmd)/"
)
```

## 相關文件

- `.claude/error-patterns/architecture/ARCH-015-*.md` — `.claude/` 寫保護限制
- `.claude/hooks/agent-dispatch-validation-hook.py` — 修復後的 Hook
