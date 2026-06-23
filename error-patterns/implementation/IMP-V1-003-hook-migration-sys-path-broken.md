---
id: IMP-V1-003
title: Hook 搬移後 sys.path 指向錯誤的 lib 目錄導致 import 失敗
category: implementation
severity: medium
created: 2026-06-23
source_ticket: 1.3.0-W1-056
---

# IMP-V1-003: Hook 搬移後 sys.path 指向錯誤的 lib 目錄

## 症狀

搬移 hook 從 `.claude/hooks/` 到 `.claude/skills/<skill>/hooks/` 後，每次 PreToolUse:Bash 觸發時出現 `Failed with non-blocking status code: Traceback (most recent call last): ModuleNotFoundError: No module named 'hook_io'`。

hook 功能靜默失效（non-blocking exit 1），但不阻擋操作，容易被忽略。

## 根因

框架有兩個共用模組目錄，import 路徑不統一：

| 目錄 | 內容 |
|------|------|
| `.claude/lib/` | `hook_io.py`（read_hook_input / write_hook_output） |
| `.claude/hooks/lib/` | `sync_exclude_manifest.py` 等 |

代理人搬移時更新 `sys.path` 為 `parents[3] / "hooks" / "lib"`（指向 `.claude/hooks/lib/`），但 `hook_io` 在 `.claude/lib/`（不在 `hooks/lib/`）。`py_compile` 通過（語法正確），`pytest` 也通過（該 hook 無專屬測試），問題只在 runtime 觸發。

## 解決方案

搬移 hook 後，`sys.path` 必須同時包含三個路徑：

```python
_CLAUDE_DIR = Path(__file__).resolve().parents[3]  # 從 skills/<name>/hooks/<file>.py 算起
sys.path.insert(0, str(_CLAUDE_DIR / "lib"))           # hook_io 等共用模組
sys.path.insert(0, str(_CLAUDE_DIR / "hooks"))         # hooks 目錄本身
sys.path.insert(0, str(_CLAUDE_DIR / "hooks" / "lib")) # sync_exclude_manifest 等
```

## 預防措施

### 搬移 hook 的 Context Bundle 必須包含以下檢查項

1. **搬移後驗證每個 hook 的 import**：
   ```bash
   python3 -c "exec(open('<hook-path>').read())" < /dev/null 2>&1 | grep -i "error"
   ```
   或更精確：
   ```bash
   python3 -c "
   import subprocess, json, os
   hook_input = json.dumps({'hook_event_name':'PreToolUse','tool_name':'Bash','tool_input':{'command':'echo test','description':'test'},'session_id':'test','cwd':os.getcwd(),'permission_mode':'auto','effort':{'level':'medium'},'transcript_path':'/tmp/test.jsonl','tool_use_id':'test-123'})
   r = subprocess.run('<hook-path>', shell=True, input=hook_input, capture_output=True, text=True, timeout=5)
   print('BROKEN' if 'Traceback' in r.stderr else f'OK (exit {r.returncode})')
   "
   ```

2. **確認目標位置的 `parents[N]` 指向正確的 `.claude/` 目錄**：從 `skills/<name>/hooks/<file>.py` 算起，`parents[3]` = `.claude/`。

3. **參考既有正確範例**：查看同一 skill 目錄下已有的 hooks 的 `sys.path` 設定。

### 根本改善方向

統一框架共用模組目錄（`.claude/lib/` 和 `.claude/hooks/lib/` 合併），消除 import 路徑歧義。

## 行為模式

- 代理人在搬移檔案時傾向「機械性更新路徑」（改 parents 層級數）而不驗證 import 是否成功
- `py_compile` 和 `pytest` 都無法攔截 runtime import path 錯誤
- non-blocking hook 失敗容易被忽略（操作本身成功，錯誤只在 stderr 出現）
