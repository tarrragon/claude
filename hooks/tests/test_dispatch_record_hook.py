#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-record-hook 測試套件（幽靈派發記錄修復票：本 hook 已停用為 no-op）

背景：派發記錄職責（原本掛在本 hook，PreToolUse:Agent）已完整遷移至
active-dispatch-tracker-hook.py（PostToolUse:Agent），理由與 who.current
綁定遷移票相同——PreToolUse(Agent) matcher 下 deny 為彙總結果，寫入端無法
感知同批次是否已被其他 PreToolUse hook 拒絕，被阻擋的派發會留下 agent_id
為 None 的幽靈記錄。詳見 active-dispatch-tracker-hook.py 頂部 docstring。

本檔僅驗證停用後的 no-op 行為；record_dispatch 呼叫參數等測試已隨邏輯
遷移至 test_active_dispatch_tracker_hook.py。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# 動態載入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "dispatch-record-hook.py"
spec = importlib.util.spec_from_file_location("dispatch_record_hook", hook_file)
dispatch_record_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch_record_hook)

EXIT_SUCCESS = dispatch_record_hook.EXIT_SUCCESS


class TestDeprecatedNoOp:
    """本 hook 已停用：main() 為純 no-op，不再有 record_dispatch 呼叫。"""

    def test_no_record_dispatch_function(self):
        assert not hasattr(dispatch_record_hook, "record_dispatch")

    def test_no_extract_ticket_id_function(self):
        assert not hasattr(dispatch_record_hook, "extract_ticket_id")

    def test_main_returns_success_without_stdin(self):
        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log:
            mock_log.return_value = MagicMock()
            assert dispatch_record_hook.main() == EXIT_SUCCESS

    def test_main_logs_deprecation_debug(self):
        mock_logger = MagicMock()
        with patch.object(
            dispatch_record_hook, "setup_hook_logging", return_value=mock_logger
        ):
            dispatch_record_hook.main()
        mock_logger.debug.assert_called_once()
