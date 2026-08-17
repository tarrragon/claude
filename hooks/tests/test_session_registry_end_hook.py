#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session-registry-end-hook 測試套件（registry 契約 v2 D1：釋放時機改掛 SessionEnd）

覆蓋：subagent 環境跳過 / session_id 缺失跳過 / 正常釋放呼叫
release_session / 非 git 環境跳過 / OSError 不阻擋。

本專案首次註冊 SessionEnd 事件，unit test 僅驗證函式呼叫邏輯；實機
liveness 驗證（確認 CC runtime 真的觸發本 hook）由 ticket acceptance
另行以 /clear 實測（PM 執行，非本測試涵蓋範圍）。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib import ENV_SESSION_ID

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "session-registry-end-hook.py"
spec = importlib.util.spec_from_file_location("session_registry_end_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

EXIT_SUCCESS = hook.EXIT_SUCCESS


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

    def test_missing_session_id_skips_release(self, monkeypatch, capsys):
        monkeypatch.delenv(ENV_SESSION_ID, raising=False)
        result, mock_release = self._run({}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_release.assert_not_called()
        assert "無法取得 session_id" in capsys.readouterr().err

    def test_normal_release_calls_release_session(self):
        result, mock_release = self._run({"session_id": "pm-session-1"}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_release.assert_called_once()
        assert mock_release.call_args.kwargs["session_id"] == "pm-session-1"

    def test_non_git_environment_skips_release(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "get_registry_paths", return_value=None
        ), patch.object(
            hook, "release_session"
        ) as mock_release:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        mock_release.assert_not_called()
        assert "非 git 環境" in capsys.readouterr().err

    def test_release_session_oserror_does_not_block(self, capsys):
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
            hook, "release_session", side_effect=OSError("disk full")
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        assert "registry 釋放失敗" in capsys.readouterr().err
