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
| Glob 排除清單 | 動態收集目標檔時必須排除環境目錄（見下節） |

### 批量腳本 glob 強制排除清單

**Why**：批量腳本若以 `rglob("*.py")` / `glob("**/*.py")` 動態收集目標檔而未排除環境目錄，轉換邏輯會掃進 `.venv` / `__pycache__` / `node_modules` / `.git` 內的第三方套件與快取檔案。觸發案例（2026-06-11）：worktree 內 `.venv` 兩個不同套件的檔案呈現同型去縮排（dedent）損壞——兩檔損壞模式一致、彼此無業務關聯，符合「轉換式批量處理未排除 .venv」的特徵。

**Consequence**：套件檔案被靜默改寫後不會立即報錯，直到 import 階段才爆出 `IndentationError` / `SyntaxError`，且錯誤堆疊指向第三方套件，誤導鑑識方向；`.venv` 等目錄不受 git 追蹤，損壞無法以 `git diff` 回溯，只能整目錄重建。

**Action**：批量腳本收集目標檔時，依優先序擇一：

1. **顯式 FILES 清單（首選）**：沿用本檔「標準範式」的硬編碼清單，根本不走 glob，無掃描外溢風險。
2. **動態 glob 必附排除清單**：以下為正向範例，`EXCLUDED_DIRS` 四項為強制最低集合，可按專案追加（如 `build/`、`dist/`、`.dart_tool/`）：

```python
from pathlib import Path

# 強制最低排除集合：環境目錄與版控內部目錄一律不進入批量轉換範圍
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", "node_modules", ".git"}

def iter_target_files(root: Path, pattern: str = "*.py"):
    for path in root.rglob(pattern):
        # path.parts 逐段比對：任一路徑分段命中排除集合即跳過（涵蓋巢狀情況）
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path
```

3. **執行前 dry-run 列印目標清單**：先以 `print` 列出將被修改的檔案路徑並人工掃一眼，確認無 `.venv` 等路徑混入後才執行寫入版本。

### Code Review 檢查項目（glob 排除）

- [ ] 批量腳本是否使用顯式 FILES 清單？若用動態 glob，是否含 `EXCLUDED_DIRS` 排除邏輯？
- [ ] 排除集合是否至少涵蓋 `.venv` / `__pycache__` / `node_modules` / `.git`？
- [ ] 是否先 dry-run 列印目標清單再執行寫入？

## 修復前證據保存 SOP

**Why**：環境級損壞（`.venv`、`node_modules`、build 產物）的標準修復動作是「刪除 + 重建」，一旦執行 `rm -rf`，損壞現場永久消失。觸發案例（2026-06-11）：PM 發現 worktree `.venv` 同型 dedent 損壞後，`rm -rf` 重建先於證據保存，導致「哪個批量腳本、何時執行、掃過哪些檔案」的一手證據（檔案 mtime、損壞內容 diff、損壞範圍清單）全數遺失，根因評估只能依損壞特徵間接推論。

**Consequence**：失去一手證據後，根因鑑識降級為特徵推論，防護規範的針對性下降（無法確認是哪支腳本、哪條 glob 造成），同型問題可能在未被識別的路徑上復發；且無法區分「批量腳本外溢」與「其他寫入來源」（如並行 session、外部工具）。

**Action**：發現環境級損壞時，依以下順序執行，**禁止跳過步驟 1-3 直接 rm -rf**：

| 步驟 | 動作 | 指令範例 |
|------|------|---------|
| 1 凍結 | 停止一切對該目錄的寫入操作（含其他並行任務） | — |
| 2 快照 | 整目錄 tar 保存到損壞目錄之外 | `tar -czf "$TMPDIR/evidence-venv-$(date +%Y%m%dT%H%M%S).tar.gz" <損壞目錄>` |
| 3 記錄 | 損壞檔案清單、mtime、損壞特徵寫入對應 ticket 的 Problem Analysis | `ls -laT <損壞檔案>`（macOS）記錄 mtime |
| 4 修復 | 完成 1-3 後才執行 `rm -rf` + 重建 | `rm -rf .venv && uv venv ...` |
| 5 鑑識 | 依快照做根因分析；mtime 比對 session 時間軸可定位寫入來源 | — |

**與 evidence-driven-bugfix 的銜接**：`evidence-driven-bugfix` skill 的流程是「重現 → failing test → 根因 → 最小修復 → 回歸防護」；環境級損壞通常不可重現（重建後現場消失），步驟 2 的快照即「重現現場」的替代品——沒有快照，整條證據驅動流程從第一步就斷裂。

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
  - `.claude/skills/evidence-driven-bugfix/SKILL.md`：證據驅動除錯流程（修復前證據保存 SOP 的上游方法論）

## 行為模式

工程界知名反模式「N 次手動 vs 1 次自動化」的具體展現。Edit 工具對單一精確修改最佳，但對機械性批次工作成本過高。當 subagent 被擋時，PM 必須認清這不是「手動 vs 手動」的二選一，而是「手動 N 次 vs 自動化 1 次」的選擇。

Claude Code 本身是自動化框架，用手動 N 次處理機械工作違背框架初衷。將此策略納入 PM 決策樹，能避免 Context 浪費與失誤累積。

---

**Created**: 2026-04-15
**Category**: process-compliance
**Last Updated**: 2026-06-11
**Version**: 1.1.0 — 新增「批量腳本 glob 強制排除清單」（含正向範例與 Code Review 檢查項目）與「修復前證據保存 SOP」（凍結 → 快照 → 記錄 → 修復 → 鑑識五步，銜接 evidence-driven-bugfix）兩節；觸發案例：worktree .venv 同型 dedent 損壞 + rm -rf 先於證據保存（2026-06-11）
