#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session-registry-start-hook 測試套件（multi-PM 協調層 Phase 1）

覆蓋：subagent 環境跳過 / session_id 缺失跳過（stdin 與環境變數皆無）/
正常註冊呼叫 register_session / OSError 不阻擋。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib import ENV_SESSION_ID

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "session-registry-start-hook.py"
spec = importlib.util.spec_from_file_location("session_registry_start_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

EXIT_SUCCESS = hook.EXIT_SUCCESS

# resolve_session_id 本體測試已收斂至 lib 單一定義，見
# test_hook_logging_session_id.py；本檔不再重複測（0.2.1-W3-560 DRY 下沉）。


class TestMain:
    def _run(self, input_data, subagent=False):
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
            hook, "register_session"
        ) as mock_register:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = input_data
            mock_sub.return_value = subagent
            mock_root.return_value = Path("/repo/worktree-b6")

            result = hook.main()

        return result, mock_register

    def test_subagent_environment_skips_registration(self):
        result, mock_register = self._run({"session_id": "s1"}, subagent=True)
        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()

    def test_missing_session_id_skips_registration(self, monkeypatch, capsys):
        monkeypatch.delenv(ENV_SESSION_ID, raising=False)
        result, mock_register = self._run({}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()
        assert "無法取得 session_id" in capsys.readouterr().err

    def test_normal_registration_calls_register_session(self):
        result, mock_register = self._run({"session_id": "pm-session-1"}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_register.assert_called_once()
        kwargs = mock_register.call_args.kwargs
        assert kwargs["session_id"] == "pm-session-1"
        assert kwargs["name"] == "worktree-b6"
        assert kwargs["project"] == "/repo/worktree-b6"
        assert kwargs["source"] == ""

    def test_resume_source_passed_through(self):
        """registry 契約 v2 D4 增補 1：source 欄位原樣傳給 register_session，
        merge/reset 分流邏輯由 pm_registry.register_session 負責，本 hook
        只負責傳遞。"""
        result, mock_register = self._run(
            {"session_id": "pm-session-1", "source": "resume"}, subagent=False
        )
        assert result == EXIT_SUCCESS
        assert mock_register.call_args.kwargs["source"] == "resume"

    def test_startup_source_passed_through(self):
        result, mock_register = self._run(
            {"session_id": "pm-session-1", "source": "startup"}, subagent=False
        )
        assert result == EXIT_SUCCESS
        assert mock_register.call_args.kwargs["source"] == "startup"

    def test_non_git_environment_skips_registration(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "get_registry_paths", return_value=None
        ), patch.object(
            hook, "register_session"
        ) as mock_register:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()
        assert "非 git 環境" in capsys.readouterr().err

    def test_register_session_oserror_does_not_block(self, capsys):
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
            hook, "register_session", side_effect=OSError("disk full")
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        assert "registry 註冊失敗" in capsys.readouterr().err
