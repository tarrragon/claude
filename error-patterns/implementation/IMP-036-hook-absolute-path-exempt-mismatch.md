# IMP-036: Hook 路徑豁免比對未處理絕對路徑轉換

## 症狀

- Hook 的路徑豁免邏輯（如 `.claude/` 前綴比對）在本地測試正常，但實際執行時所有豁免路徑都被阻止
- Hook 日誌顯示「非豁免檔案」，但檔案路徑確實在豁免範圍內

## 根因

Claude Code 工具（Edit/Write）傳入的 `file_path` 是**絕對路徑**（如 `/path/to/project/.claude/rules/core/decision-tree.md`），但 Hook 的豁免比對邏輯只做 `lstrip("/")`，結果是 `Users/username/...`，永遠不會匹配 `.claude/` 前綴。

**行為模式**：開發者在寫路徑比對邏輯時，假設輸入是相對路徑，但實際上工具 API 傳入的是絕對路徑。`lstrip("/")` 只移除開頭斜線，不會轉換為相對路徑。

## 解決方案

使用 `get_project_root()` 取得專案根目錄，將絕對路徑轉為相對路徑後再比對：

```python
from git_utils import get_project_root

project_root = get_project_root()
if file_path.startswith(project_root):
    normalized = file_path[len(project_root):].lstrip("/")
else:
    normalized = file_path.lstrip("/")
```

## 預防措施

- Hook 中所有路徑比對邏輯，必須先確認輸入是絕對路徑還是相對路徑
- 使用 `get_project_root()` 進行正規化，不依賴 `lstrip("/")` 做路徑轉換
- 新增 Hook 路徑比對時，應使用真實的絕對路徑進行測試（而非只用相對路徑）

## 相關 Ticket

- 0.1.1-W15-006 — branch-verify-hook 絕對路徑豁免比對修復

---

**Created**: 2026-03-21
**Category**: implementation
**Severity**: 中（功能性失效但有 workaround：建立 feature branch）
