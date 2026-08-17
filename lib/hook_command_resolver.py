"""共用模組：解析 settings.json hooks[].hooks[].command 字串。

收斂原本分散於 hook-completeness-check.py 與 hook_output_validator.py 的
兩份重複實作。統一三項曾各自漂移的語意：

- 變數展開形式：`$VAR` 與 `${VAR}` 兩種形式皆支援（原本各只支援其一）
- Tokenize 方式：統一採 `shlex.split()`（正確處理含引號/空白的路徑，取代
  其中一份原本使用的樸素 `command.split()`）
- 副檔名判定：`.py` 與 `.sh` 皆視為腳本（其中一份原本只認 `.py`）

呼叫端依需求選用不同抽象層級：
- `resolve_hook_script_path()`：取單一 `Optional[Path]`（適合「這個 hook
  對應的檔案是否存在/可執行」類檢查，hook-completeness-check.py 用途）
- `tokenize_hook_command()`：取完整 argv（適合實際 subprocess 執行，
  hook_output_validator.py 用途）

兩函式對 shlex 解析失敗（引號不成對等畸形字串）的容錯策略刻意不同，見各自
docstring：`tokenize_hook_command` 忠實傳播 ValueError（供需要精確錯誤回報
的呼叫端處理），`resolve_hook_script_path` 內部吞下並降級（供只需「盡量解析
出路徑」的完整性檢查類呼叫端使用），不可合併為單一決定。

Source: 收斂多視角 Phase 4 審查發現的重複命令字串解析實作。
"""

import shlex
from pathlib import Path
from typing import List, Optional, Tuple

# 唯一真實來源：settings.json 命令字串中實際出現的變數集合。
# .claude/settings.json / .claude/settings.local.json 實測僅此兩者；
# 新增變數時只需在此擴充，兩個呼叫端自動同步。
HOOK_COMMAND_VARS: Tuple[str, ...] = ("CLAUDE_PROJECT_DIR", "CLAUDE_FILE_PATH")

HOOK_SCRIPT_SUFFIXES: Tuple[str, ...] = (".py", ".sh")


def hook_command_var_values(project_root: Path) -> dict:
    """建立變數名稱到展開值的對照表。

    CLAUDE_FILE_PATH 無專案根目錄以外的合理預設值，展開為專案內 CLAUDE.md
    佔位——僅供 dry-run 執行/測試用途；不影響腳本路徑解析，因該變數只出現
    於 command 字串的尾端引數，從不出現在腳本路徑 token 本身。

    公開此函式（非僅供本模組內部使用）供呼叫端需要相同對照表時直接複用
    （如 hook_output_validator.py 以此表填 subprocess env），避免各自維護
    一份常數字面值造成新的漂移。
    """
    return {
        "CLAUDE_PROJECT_DIR": str(project_root),
        "CLAUDE_FILE_PATH": str(project_root / "CLAUDE.md"),
    }


def substitute_hook_command_vars(command: str, project_root: Path) -> str:
    """展開 command 字串中的已知變數，`$VAR` 與 `${VAR}` 兩形式皆支援。"""
    substitutions = hook_command_var_values(project_root)
    for var in HOOK_COMMAND_VARS:
        value = substitutions[var]
        command = command.replace("${" + var + "}", value)
        command = command.replace("$" + var, value)
    return command


def tokenize_hook_command(command: str, project_root: Path) -> List[str]:
    """展開變數後，以 shlex 切分為 argv（正確處理含引號/空白的路徑）。

    shlex.split 對引號不成對等畸形字串會拋出 ValueError——本函式刻意不吞
    此例外，交由呼叫端決定容錯策略。`resolve_hook_script_path` 對此有自己
    的降級處理，本函式若也吞掉會使兩者的錯誤處理各自為政、產生新的漂移。
    """
    expanded = substitute_hook_command_vars(command, project_root)
    return shlex.split(expanded)


def resolve_hook_script_path(
    command: str,
    project_root: Path,
    suffixes: Tuple[str, ...] = HOOK_SCRIPT_SUFFIXES,
) -> Optional[Path]:
    """從 command 字串取出腳本檔案的絕對路徑，非本機腳本回傳 None。

    取 argv 中第一個副檔名符合 suffixes 的 token，容忍 runner 前綴（如
    `uv run <path>`）與尾端引數（如 `<path> $CLAUDE_FILE_PATH`）。

    tokenize 失敗（畸形字串）時降級為樸素空白切分——本函式供註冊完整性
    檢查使用，容錯優先於精確，不因單一畸形 command 字串使整體掃描中斷。
    """
    if not command:
        return None
    try:
        tokens = tokenize_hook_command(command, project_root)
    except ValueError:
        tokens = substitute_hook_command_vars(command, project_root).split()

    script_token = next((tok for tok in tokens if tok.endswith(suffixes)), None)
    if script_token is None:
        return None

    path = Path(script_token)
    if not path.is_absolute():
        path = project_root / path
    return path
