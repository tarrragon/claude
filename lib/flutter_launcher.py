"""Flutter／Dart 命令的呼叫方式判定。

專案以 FVM 釘選 Flutter 版本時，flutter 與 dart 必須經 fvm 呼叫，否則用到的是
PATH 上的全域預設版；沒有 FVM 的專案則不能帶 fvm 前綴。框架內組命令的地方
（合併閘門的套件命令、hook 訊息給的改寫）一律經本模組決定，不各自寫死。

判定只看檔案是否存在，不呼叫 fvm：從起點目錄往上找，遇到 FVM 設定檔即判為使用 FVM；
遇到含 .git 的目錄（專案根）找完該層即停止，不越過專案根。
"""

from pathlib import Path
from typing import List, Sequence, Union

# FVM 3 的設定檔為 .fvmrc；FVM 2 的設定在 .fvm/fvm_config.json，兩者都視為釘選
FVM_MARKER_FILES = (".fvmrc", ".fvm/fvm_config.json")
FVM_EXECUTABLE = "fvm"
# 經 fvm 呼叫的執行檔
FVM_MANAGED_EXECUTABLES = frozenset({"flutter", "dart"})
_PROJECT_ROOT_MARKER = ".git"

PathLike = Union[str, Path]


def uses_fvm(start: PathLike) -> bool:
    """起點目錄或其上層（不越過專案根）有 FVM 設定檔時回 True。"""
    current = Path(start).resolve()
    for directory in (current, *current.parents):
        if any((directory / marker).is_file() for marker in FVM_MARKER_FILES):
            return True
        if (directory / _PROJECT_ROOT_MARKER).exists():
            return False
    return False


def launch_argv(argv: Sequence[str], start: PathLike) -> List[str]:
    """依專案是否使用 FVM 補上或不補 fvm 前綴。

    只處理開頭為 flutter／dart 的 argv；已帶 fvm 或其他命令原樣回傳。
    """
    command = list(argv)
    if command and command[0] in FVM_MANAGED_EXECUTABLES and uses_fvm(start):
        return [FVM_EXECUTABLE, *command]
    return command
