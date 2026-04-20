---
id: PC-069
title: Subagent 被擋時多檔案機械性修改的批次腳本策略
category: process-compliance
severity: medium
first_seen: 2026-04-15
---

# PC-069: Subagent 被擋時多檔案機械性修改的批次腳本策略

## 症狀

PM 面臨需要在多個 `.claude/` 下檔案進行機械性統一修改（如批次補參數、批次加 encoding、批次重命名 import）時，典型誤判：

1. 嘗試派發 subagent（thyme-python-developer 等）執行批次修改
   → 被 CC runtime 擋（ARCH-015：subagent 對 `.claude/` Edit 在主 repo 和 worktree 都被阻擋）
2. 轉為 PM 前台使用 Edit 工具逐一修改
   → N 個 Edit 工具呼叫（例：37 處 subprocess 修補 = 37 次 Edit）
   → 認知負擔爆表、容易失誤、Context 被大量工具結果佔用

## 根因

PM 對「修改工作的性質」判斷錯誤，把**機械性批次工作**當成**逐一審慎工作**處理。

兩者差異：

| 性質 | 判斷依據 | 合適工具 |
|------|---------|---------|
| 機械性批次 | 模式統一、風險低、覆蓋面廣（N > 10） | Inline Python 腳本 via Bash heredoc |
| 逐一審慎 | 每處上下文不同、需獨立判斷、風險各異 | Edit 工具逐個 |

## 解決方案

### 策略：Bash heredoc 執行 inline Python 腳本

當以下三條件同時成立時，採用批次腳本：

1. **Subagent 被擋**（ARCH-015 或其他攔截機制）
2. **模式統一**（正則可識別、修改規則一致）
3. **N >= 10**（工具呼叫成本明顯高於腳本撰寫成本）

### 標準範式

```bash
python3 <<'PYEOF'
import re
from pathlib import Path

FILES = [
    ".claude/hooks/file1.py",
    ".claude/hooks/file2.py",
    # ...
]

def patch_file(path):
    content = path.read_text(encoding="utf-8")
    # 正則識別需修改的位置
    # 保持冪等（已修改則跳過）
    # 套用 patch（reverse-order 避免 offset 失效）
    path.write_text(new_content, encoding="utf-8")
    return patch_count

for rel in FILES:
    p = Path(rel)
    if p.exists():
        print(f"{rel}: {patch_file(p)}")
PYEOF
```

### 關鍵設計要素

| 要素 | 說明 |
|------|------|
| 冪等性 | 檢查「是否已修改」，避免重複 patch |
| Reverse-order | 從後往前 apply patches 避免 offset 偏移 |
| 括號配對 | 處理多行函式呼叫需支援字串轉義與 triple-quoted |
| 縮排保留 | 依原始縮排同行或換行插入，不破壞 PEP 8 |
| 驗證迴圈 | Patch 後跑 AST parse + 既有測試確認無回歸 |

## 防護措施

### 判斷流程

PM 在派發/執行前必須走以下判斷：

```
任務是否為多檔案機械性修改？（N >= 10 且模式統一）
├── 是 → 嘗試派發 subagent
│      ├── 成功 → 派發
│      └── 失敗（ARCH-015 等）→ PM 前台 inline Python 批次腳本
│             禁止：PM 前台 N 次 Edit 工具逐一修改
└── 否 → PM 前台 Edit 工具逐一處理（或派發單一 ticket）
```

### Code Review 檢查項目

- [ ] 多檔案機械性修改是否使用批次腳本而非逐一 Edit？
- [ ] 腳本是否冪等？（重複執行結果一致）
- [ ] 腳本是否有 AST parse 驗證？
- [ ] 腳本是否有回歸測試驗證？

## 相關資訊

- **首次應用**：37 處 subprocess encoding 批次修補，從「37 次 Edit」改為「1 次 inline Python」，節省約 90% Context 消耗
- **關聯模式**：
  - ARCH-015：Subagent .claude/ Edit Universal Block（觸發前提）
  - IMP-062：Windows 平台 Hook 啟動失敗（觸發此策略的起點 Ticket）

## 行為模式

工程界知名反模式「N 次手動 vs 1 次自動化」的具體展現。Edit 工具對單一精確修改最佳，但對機械性批次工作成本過高。當 subagent 被擋時，PM 必須認清這不是「手動 vs 手動」的二選一，而是「手動 N 次 vs 自動化 1 次」的選擇。

Claude Code 本身是自動化框架，用手動 N 次處理機械工作違背框架初衷。將此策略納入 PM 決策樹，能避免 Context 浪費與失誤累積。

---

**Created**: 2026-04-15
**Category**: process-compliance
