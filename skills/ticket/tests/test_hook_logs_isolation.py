"""skill 根 conftest 的 hook 日誌隔離契約。

兩棵 testpath（tests/、ticket_system/tests/）皆須取得相同隔離：
HOOK_LOGS_DIR 指向 tmp、HOOK_TEST_ISOLATION=1。
"""

import os
from pathlib import Path


def test_hook_logs_dir_points_to_tmp_not_repo():
    logs_dir = os.environ.get("HOOK_LOGS_DIR")
    assert logs_dir, "HOOK_LOGS_DIR 未由 autouse 設定"
    assert Path(logs_dir).name.startswith("hook-logs-default")
    assert Path(logs_dir).is_dir()


def test_hook_test_isolation_flag_set():
    assert os.environ.get("HOOK_TEST_ISOLATION") == "1"
