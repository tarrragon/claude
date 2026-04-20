"""
Ticket System 常數定義（向後相容 shim）

canonical location 已遷移至 `ticket_system.constants`。
本模組保留以維持 skill 內部既有 `from ticket_system.lib.constants import X` 路徑相容。

設計背景（W14-016）：
    原先 constants 位於此處（lib/constants.py），skill 和 hook 皆 `from ticket_system.lib.constants import X`。
    但 lib/__init__.py eager-import ticket_loader → parser → yaml，導致 hook 在系統 Python（無 yaml）
    環境下觸發 ModuleNotFoundError（session 累積 97 次 traceback）。

    修復方式：將常數上移至 `ticket_system.constants`（package 頂層，無 yaml 依賴鏈）。
    本模組僅作 shim，skill 內部無需同步修改 N 處 import 路徑。

新程式碼建議：
    - skill 內部：可繼續用 `from ticket_system.lib.constants import X`（透過本 shim）
    - hook / 無 yaml 環境：必須用 `from ticket_system.constants import X`
"""
# ruff: noqa: F401, F403
from ticket_system.constants import *
from ticket_system.constants import __all__  # 明確 re-export __all__ 清單

if __name__ == "__main__":
    # __main__ guard：不 import lib.messages 避免循環 / 依賴
    import sys
    print("=" * 60)
    print("此模組不可直接執行：ticket_system/lib/constants.py")
    print("（本模組為 shim，請改用 `from ticket_system.constants import X`）")
    print("=" * 60)
    sys.exit(1)
