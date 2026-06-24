---
id: IMP-APP-001
title: get_project_root 雙實作回傳型別分歧 — consumer 用錯 Path 方法 runtime 才爆
category: implementation
severity: medium
created: 2026-06-24
source_ticket: 0.37.0-W6-003
---

# IMP-APP-001: get_project_root 雙實作回傳型別分歧

## 症狀

SessionStart（或任何事件）出現 non-blocking `Failed with non-blocking status code: Traceback`，定位到 `AttributeError: 'str' object has no attribute 'joinpath'`（或 `.parent` / `.exists` / `/` 運算子 `TypeError`）。

hook 功能靜默失效（exit 非 0 但 non-blocking），操作本身不被阻擋，容易被忽略。

實例：`hook-health-monitor.py` line 280 `project_root.joinpath(*SESSION_MARKER_RELPATH)`，其中 `project_root = get_project_root()` 回傳 str。

## 根因

框架 2.0（v1.61.0 hooks/lib → lib/ 合併，framework issue #10）後，`get_project_root` 存在**兩份回傳型別不一致的實作**：

| import 來源 | 簽名 | 回傳 |
|------------|------|------|
| `lib.git_utils.get_project_root()`（`lib.common_functions` 轉出此版） | `-> str` | git toplevel 或 `os.getcwd()` |
| `hook_utils.hook_base.get_project_root()` | `-> Path` | Path 物件 |

consumer hook import 哪一份，決定 `project_root` 的型別。檔案若整體以 Path 撰寫（型別標註 `project_root: Path`、用 `/` 與 `.joinpath()`），卻 import 了 str 版，靜態檢查與 `py_compile` 不抓（與 IMP-V1-003 斷裂 4 同源：py_compile 只驗語法不解析型別），**runtime 才 AttributeError**。

## 解決方案

最小修復：在賦值點包成 Path，使其符合全檔型別標註。

```python
# 修復前（hook-health-monitor.py:401）
project_root = get_project_root()       # str（from lib.common_functions）
# 修復後
project_root = Path(get_project_root())  # 符合全檔 project_root: Path 標註
```

`get_project_root()` 永不回空字串（fallback `os.getcwd()`），故 `if not project_root` 判斷不受影響。

## 預防措施

### 盤點同類風險

```bash
# 找出 import str 版 get_project_root 的 hook
grep -rlE "from lib\.(common_functions|git_utils) import.*get_project_root" .claude/hooks/*.py
# 逐一確認：是否對結果用 Path-only 方法（/、.joinpath、.parent、.exists、.glob）
# str-safe 用法（os.path.join / os.path.exists）不受影響
```

本專案盤點結果：僅 `hook-health-monitor.py` 與 `git-index-lock-cleanup-hook.py` import str 版，後者用 `os.path.*`（str-safe）無風險。

### 驗證方式（非 py_compile）

```bash
echo '{"hook_event_name":"SessionStart","source":"startup"}' | python3 .claude/hooks/<hook>.py 2>&1 | grep -q Traceback && echo BROKEN || echo OK
```

### 根本改善方向

統一 `get_project_root` 為**單一回傳型別**（建議 Path），移除 `lib.git_utils` 與 `hook_utils.hook_base` 的雙實作分歧。屬 hook lib 重構範圍（hooks/lib 合併後遺症的設計債清理）。

## 行為模式

- hooks/lib 合併期，同名函式存在多份實作回傳型別分歧，是典型過渡設計債
- consumer import 路徑不同 → 型別不同 → 同一段 Path 操作有的 hook 安全有的爆
- `py_compile` / 靜態檢查無法攔截型別分歧，runtime 才暴露

## 關聯

- IMP-V1-003（同為 hooks/lib 合併後遺症：sys.path import 路徑歧義）
- framework issue #10（v1.61.0 hooks/lib 合併 consumer 斷裂清單）
- PC-148 變體 B（hook 搬移須同步所有註冊）
