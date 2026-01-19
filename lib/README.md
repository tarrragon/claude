# Hook 共用模組程式庫

## 概述

v0.28.0 重構建立了 `.claude/lib/` 共用模組系統，遵循 Linux Good Taste 原則，將 Hook 系統中的重複程式碼提取為四個核心模組。

**設計目標**：
- 消除重複程式碼（DRY 原則）
- 統一 API 介面
- 提高可維護性和可測試性

**四個核心模組**：

| 模組 | 主要功能 | 適用場景 |
|------|----------|----------|
| `config_loader` | 配置檔案載入 | 需要讀取 YAML/JSON 配置的 Hook |
| `git_utils` | Git 操作封裝 | 需要分支檢查、worktree 操作的 Hook |
| `hook_io` | I/O 標準化 | 所有 Hook 的輸入輸出處理 |
| `hook_logging` | 日誌系統 | 需要記錄執行日誌的 Hook |

---

## API 參考

### config_loader - 配置載入

提供統一的 YAML/JSON 配置檔案載入功能，支援從 `.claude/config/` 目錄載入配置。

#### 函式列表

```python
def get_config_dir() -> Path
```
獲取配置目錄路徑（`.claude/config/`）。

```python
def load_config(config_name: str) -> dict
```
載入指定的配置檔案。

- **參數**：`config_name` - 配置檔案名稱（不含副檔名）
- **回傳**：配置內容字典
- **例外**：`FileNotFoundError`（檔案不存在）、`ValueError`（格式錯誤）
- **支援格式**：優先 `.yaml` > `.yml` > `.json`

```python
def load_agents_config() -> dict
```
載入代理人配置（帶快取）。

- **回傳**：包含 `known_agents`、`agent_dispatch_rules`、`task_type_priorities`、`weight_map`、`exclude_keywords`

```python
def load_quality_rules() -> dict
```
載入品質規則配置（帶快取）。

- **回傳**：包含 `trigger_conditions`、`cache`、`code_smell_rules`、`decision_rules`

```python
def clear_config_cache() -> None
```
清除配置快取（用於測試或配置熱更新）。

#### 使用範例

```python
from lib.config_loader import load_config, load_agents_config

# 載入自訂配置
config = load_config("my_config")
value = config.get("key", "default")

# 載入代理人配置（帶快取）
agents_config = load_agents_config()
known_agents = set(agents_config.get("known_agents", []))
dispatch_rules = agents_config.get("agent_dispatch_rules", {})
```

---

### git_utils - Git 操作

提供統一的 Git 命令執行和分支管理功能。

#### 常數定義

```python
PROTECTED_BRANCHES = ["main", "master", "develop", "release/*", "production"]
ALLOWED_BRANCHES = ["feat/*", "feature/*", "fix/*", "hotfix/*", "bugfix/*", "chore/*", "docs/*", "refactor/*", "test/*"]
```

#### 函式列表

```python
def run_git_command(
    args: list[str],
    cwd: Optional[str] = None,
    timeout: int = 10
) -> tuple[bool, str]
```
執行 git 命令並返回結果。

- **參數**：
  - `args` - git 命令參數列表（不含 'git'）
  - `cwd` - 執行目錄，預設為當前目錄
  - `timeout` - 命令超時時間（秒）
- **回傳**：`(是否成功, 輸出內容或錯誤訊息)`

```python
def get_current_branch() -> Optional[str]
```
獲取當前分支名稱。

- **回傳**：分支名稱，如果無法獲取則返回 `None`

```python
def get_project_root() -> str
```
獲取專案根目錄（git 倉庫根目錄）。

- **回傳**：專案根目錄路徑，如果無法獲取則返回當前工作目錄

```python
def get_worktree_list() -> list[dict]
```
獲取所有 worktree 列表。

- **回傳**：worktree 資訊列表，每個元素包含 `path`、`branch`（可選）、`detached`（可選）

```python
def is_protected_branch(branch: str) -> bool
```
檢查是否為保護分支。

```python
def is_allowed_branch(branch: str) -> bool
```
檢查是否為允許編輯的分支。

```python
def generate_worktree_info() -> str
```
生成 worktree 資訊字串（用於顯示）。

- **回傳**：格式化的 worktree 資訊，如果只有一個 worktree 則返回空字串

#### 使用範例

```python
from lib.git_utils import (
    get_current_branch,
    is_protected_branch,
    is_allowed_branch,
    run_git_command
)

# 檢查當前分支
branch = get_current_branch()
if branch and is_protected_branch(branch):
    print(f"Warning: working on protected branch '{branch}'")

# 執行 git 命令
success, output = run_git_command(["status", "--porcelain"])
if success:
    print(f"Changes: {output}")
```

---

### hook_io - I/O 標準化

提供統一的 Hook JSON 輸入讀取和輸出生成功能。

#### 函式列表

```python
def read_hook_input() -> dict
```
從 stdin 讀取 Hook 輸入。

- **回傳**：解析後的 JSON 資料，解析失敗時返回空字典

```python
def write_hook_output(
    output: dict,
    ensure_ascii: bool = False,
    indent: int = 2
) -> None
```
輸出 Hook 結果到 stdout。

- **參數**：
  - `output` - 要輸出的字典
  - `ensure_ascii` - 是否確保 ASCII 編碼（預設 `False` 以支援中文）
  - `indent` - JSON 縮排空格數

```python
def create_pretooluse_output(
    decision: str,
    reason: str,
    user_prompt: Optional[str] = None,
    system_message: Optional[str] = None,
    suppress_output: bool = False
) -> dict
```
建立 PreToolUse Hook 輸出格式。

- **參數**：
  - `decision` - 決策結果：`"allow"` | `"deny"` | `"ask"`
  - `reason` - 決策原因說明
  - `user_prompt` - 詢問用戶的訊息（僅當 decision 為 `"ask"` 時使用）
  - `system_message` - 系統訊息（可選）
  - `suppress_output` - 是否抑制輸出（預設 `False`）

```python
def create_posttooluse_output(
    decision: str,
    reason: str,
    additional_context: Optional[str] = None
) -> dict
```
建立 PostToolUse Hook 輸出格式。

- **參數**：
  - `decision` - 決策結果：`"allow"` | `"block"`
  - `reason` - 決策原因說明
  - `additional_context` - 額外上下文資訊（可選）

```python
def create_simple_output(decision: str, reason: str = "") -> dict
```
建立簡單的 Hook 輸出格式。

- **參數**：
  - `decision` - 決策結果：`"approve"` | `"allow"` | `"block"` | `"deny"`
  - `reason` - 決策原因說明（可選）

#### 輸出格式說明

**PreToolUse 輸出結構**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "原因說明",
    "userPrompt": "詢問訊息（可選）"
  },
  "systemMessage": "系統訊息（可選）",
  "suppressOutput": false
}
```

**PostToolUse 輸出結構**：
```json
{
  "decision": "allow|block",
  "reason": "原因說明",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "額外資訊（可選）"
  }
}
```

#### 使用範例

```python
from lib.hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
    create_posttooluse_output
)

# 讀取輸入
input_data = read_hook_input()
tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})

# PreToolUse 輸出
output = create_pretooluse_output(
    decision="ask",
    reason="在保護分支上編輯",
    user_prompt="是否繼續在 main 分支上編輯？"
)
write_hook_output(output)

# PostToolUse 輸出
output = create_posttooluse_output(
    decision="allow",
    reason="檢測通過",
    additional_context="## 檢測報告\n詳細內容..."
)
write_hook_output(output)
```

---

### hook_logging - 日誌系統

提供統一的 Hook 日誌設定功能。

#### 函式列表

```python
def setup_hook_logging(
    hook_name: str,
    log_subdir: Optional[str] = None,
    log_level: Optional[int] = None,
    include_stderr: bool = False
) -> logging.Logger
```
設定 Hook 日誌系統。

- **參數**：
  - `hook_name` - Hook 名稱，用於識別日誌來源和檔案名稱
  - `log_subdir` - 日誌子目錄，預設為 `hook_name`
  - `log_level` - 日誌等級，預設根據 `HOOK_DEBUG` 環境變數決定
  - `include_stderr` - 是否同時輸出到 stderr
- **回傳**：配置好的 Logger 實例

```python
def get_hook_log_dir(hook_name: str) -> Path
```
獲取 Hook 日誌目錄路徑。

- **回傳**：日誌目錄路徑

#### 日誌位置說明

日誌檔案存放於：
```
.claude/hook-logs/{log_subdir}/{hook_name}-{YYYYMMDD-HHMMSS}.log
```

日誌格式：
```
[2025-01-19 10:30:45] INFO - Hook started
[2025-01-19 10:30:46] ERROR - Something went wrong
```

#### 使用範例

```python
from lib.hook_logging import setup_hook_logging, get_hook_log_dir

# 設定日誌
logger = setup_hook_logging("branch-verify")
logger.info("Hook started")
logger.debug("Debug info")  # 需設定 HOOK_DEBUG=true 才會顯示
logger.error("Something went wrong")

# 取得日誌目錄
log_dir = get_hook_log_dir("branch-verify")
print(f"Logs at: {log_dir}")
```

---

## 使用範例

### 典型 Hook 腳本結構

```python
#!/usr/bin/env python3
"""
範例 Hook 腳本

展示如何使用共用模組建立 Hook。
"""

from lib.hook_io import read_hook_input, write_hook_output, create_pretooluse_output
from lib.hook_logging import setup_hook_logging
from lib.config_loader import load_agents_config
from lib.git_utils import get_current_branch, is_protected_branch

# 初始化日誌
logger = setup_hook_logging("my-hook")

def main():
    logger.info("Hook started")

    # 讀取輸入
    input_data = read_hook_input()
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    logger.debug(f"Tool: {tool_name}")

    # 檢查分支
    branch = get_current_branch()
    if branch and is_protected_branch(branch):
        logger.warning(f"Protected branch detected: {branch}")
        output = create_pretooluse_output(
            decision="ask",
            reason=f"正在保護分支 '{branch}' 上操作",
            user_prompt=f"是否繼續在 {branch} 分支上編輯？"
        )
        write_hook_output(output)
        return

    # 載入配置
    config = load_agents_config()
    known_agents = set(config.get("known_agents", []))

    # 通過檢查
    logger.info("Check passed")
    output = create_pretooluse_output(
        decision="allow",
        reason="檢查通過"
    )
    write_hook_output(output)

if __name__ == "__main__":
    main()
```

---

## 測試執行

```bash
# 執行所有測試
uv run pytest .claude/lib/tests/ -v

# 執行單一模組測試
uv run pytest .claude/lib/tests/test_hook_io.py -v
uv run pytest .claude/lib/tests/test_config_loader.py -v
uv run pytest .claude/lib/tests/test_git_utils.py -v
uv run pytest .claude/lib/tests/test_hook_logging.py -v

# 執行測試並顯示覆蓋率
uv run pytest .claude/lib/tests/ -v --cov=.claude/lib --cov-report=term-missing
```

---

## 相關文件

- [Hook 系統快速參考]($CLAUDE_PROJECT_DIR/.claude/hook-system-reference.md)
- [Hook 系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hook-system-methodology.md)
