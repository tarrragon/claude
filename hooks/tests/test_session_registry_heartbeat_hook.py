#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session-registry-heartbeat-hook 測試套件（multi-PM 協調層 Phase 1）

覆蓋：subagent 環境跳過 / session_id 缺失跳過 / 正常呼叫 update_heartbeat
（含 debounce 命中/未命中兩種回傳值）/ OSError 不阻擋。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib import ENV_SESSION_ID

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "session-registry-heartbeat-hook.py"
spec = importlib.util.spec_from_file_location(
    "session_registry_heartbeat_hook", hook_file
)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

EXIT_SUCCESS = hook.EXIT_SUCCESS


class TestMain:
    def _run(self, input_data, subagent=False, update_return=True):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook,
            "get_registry_paths",
            return_value=(
                Path("/repo/.git/pm-registry.json"),
                Path("/repo/.git/pm-registry.lock"),
            ),
        ), patch.object(
            hook, "update_heartbeat", return_value=update_return
        ) as mock_update:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = input_data
            mock_sub.return_value = subagent
            mock_root.return_value = Path("/repo")

            result = hook.main()

        return result, mock_update

    def test_subagent_environment_skips_update(self):
        result, mock_update = self._run({"session_id": "s1"}, subagent=True)
        assert result == EXIT_SUCCESS
        mock_update.assert_not_called()

    def test_missing_session_id_skips_update(self, monkeypatch, capsys):
        monkeypatch.delenv(ENV_SESSION_ID, raising=False)
        result, mock_update = self._run({}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_update.assert_not_called()
        assert "無法取得 session_id" in capsys.readouterr().err

    def test_normal_heartbeat_write_calls_update(self):
        result, mock_update = self._run(
            {"session_id": "pm-session-1"}, subagent=False, update_return=True
        )
        assert result == EXIT_SUCCESS
        mock_update.assert_called_once()
        assert mock_update.call_args.kwargs["session_id"] == "pm-session-1"

    def test_debounce_hit_still_returns_success(self):
        """update_heartbeat 回傳 False（debounce 命中）仍視為正常路徑。"""
        result, mock_update = self._run(
            {"session_id": "pm-session-1"}, subagent=False, update_return=False
        )
        assert result == EXIT_SUCCESS
        mock_update.assert_called_once()

    def test_non_git_environment_skips_update(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "get_registry_paths", return_value=None
        ), patch.object(
            hook, "update_heartbeat"
        ) as mock_update:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        mock_update.assert_not_called()
        assert "非 git 環境" in capsys.readouterr().err

    def test_update_heartbeat_oserror_does_not_block(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook,
            "get_registry_paths",
            return_value=(
                Path("/repo/.git/pm-registry.json"),
                Path("/repo/.git/pm-registry.lock"),
            ),
        ), patch.object(
            hook, "update_heartbeat", side_effect=OSError("disk full")
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        assert "heartbeat 更新失敗" in capsys.readouterr().err
