#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session-registry-stop-hook 測試套件（multi-PM 協調層 Phase 1）

覆蓋：subagent 環境跳過 / background_tasks 非空跳過釋放 / session_id
缺失跳過 / 正常釋放呼叫 release_session / OSError 不阻擋。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "session-registry-stop-hook.py"
spec = importlib.util.spec_from_file_location("session_registry_stop_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

EXIT_SUCCESS = hook.EXIT_SUCCESS


class TestHasBackgroundAgents:
    def test_non_dict_returns_false(self):
        assert hook.has_background_agents("not a dict", MagicMock()) is False

    def test_missing_field_returns_false(self):
        assert hook.has_background_agents({}, MagicMock()) is False

    def test_non_list_field_returns_false(self):
        assert hook.has_background_agents({"background_tasks": "x"}, MagicMock()) is False

    def test_empty_list_returns_false(self):
        assert hook.has_background_agents({"background_tasks": []}, MagicMock()) is False

    def test_non_empty_list_returns_true(self):
        assert hook.has_background_agents(
            {"background_tasks": [{"id": "bg1"}]}, MagicMock()
        ) is True


class TestMain:
    def _run(self, input_data, subagent=False):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "release_session"
        ) as mock_release:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = input_data
            mock_sub.return_value = subagent
            mock_root.return_value = Path("/repo")

            result = hook.main()

        return result, mock_release

    def test_subagent_environment_skips_release(self):
        result, mock_release = self._run({"session_id": "s1"}, subagent=True)
        assert result == EXIT_SUCCESS
        mock_release.assert_not_called()

    def test_background_tasks_active_skips_release(self):
        result, mock_release = self._run(
            {"session_id": "s1", "background_tasks": [{"id": "bg1"}]},
            subagent=False,
        )
        assert result == EXIT_SUCCESS
        mock_release.assert_not_called()

    def test_missing_session_id_skips_release(self, monkeypatch, capsys):
        monkeypatch.delenv(hook.ENV_SESSION_ID, raising=False)
        result, mock_release = self._run({}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_release.assert_not_called()
        assert "無法取得 session_id" in capsys.readouterr().err

    def test_normal_release_calls_release_session(self):
        result, mock_release = self._run({"session_id": "pm-session-1"}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_release.assert_called_once()
        assert mock_release.call_args.kwargs["session_id"] == "pm-session-1"

    def test_release_session_oserror_does_not_block(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "release_session", side_effect=OSError("disk full")
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        assert "registry 釋放失敗" in capsys.readouterr().err
