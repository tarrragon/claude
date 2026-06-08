"""W9-008 — 回歸測試：pytest 不得產生巢狀 .claude/hook-logs 副產物。

背景（PM 前台調查 + W9-007 驗收發現）：
`precondition._resolve_hook_logs_dir()` 預設用 cwd-relative `.claude/hook-logs`。
從 skill cwd（`.claude/skills/ticket/`）執行 pytest 且測試未隔離 `HOOK_LOGS_DIR`
env 時，force-usage log 寫入 `.claude/skills/ticket/.claude/hook-logs/`，造成巢狀污染
（git untracked，干擾 session-start 清點）。

方案 B：在 conftest.py 加 autouse fixture 注入 `HOOK_LOGS_DIR=tmp_path`，使所有測試
預設隔離。本檔驗證該防護生效。
"""
from __future__ import annotations

import os
from pathlib import Path

from ticket_system.lib import precondition as precondition_mod


class TestHookLogsIsolation:
    """驗證 autouse fixture 將 HOOK_LOGS_DIR 導向 tmp，避免巢狀污染。"""

    def test_hook_logs_dir_env_points_to_tmp(self):
        """autouse fixture 應已注入 HOOK_LOGS_DIR，且不指向 cwd-relative 預設值。"""
        env_value = os.environ.get(precondition_mod._HOOK_LOGS_DIR_ENV)
        assert env_value is not None, (
            "autouse fixture 應注入 HOOK_LOGS_DIR，使測試預設隔離"
        )
        resolved = precondition_mod._resolve_hook_logs_dir()
        assert resolved != Path(precondition_mod._DEFAULT_HOOK_LOGS_DIR), (
            "HOOK_LOGS_DIR 不應落在 cwd-relative 預設路徑（否則從 skill cwd 跑會巢狀污染）"
        )

    def test_force_log_write_lands_in_tmp_not_nested(self):
        """write_force_usage_log 寫入位置應為 autouse 注入的 tmp，不在 .claude/skills 下。"""
        precondition_mod.write_force_usage_log(
            "0.0.0-W0-ISOLATION", "append-log", "pending", reason="regression-test"
        )
        resolved = precondition_mod._resolve_hook_logs_dir()
        log_file = resolved / precondition_mod._FORCE_LOG_FILENAME
        assert log_file.exists(), "force log 應寫入隔離後的 tmp 目錄"
        # 巢狀污染路徑斷言：絕不應落在 .claude/skills/*/.claude 下
        assert ".claude/skills" not in str(resolved.resolve()), (
            f"force log 落在巢狀路徑 {resolved}（污染源）"
        )
