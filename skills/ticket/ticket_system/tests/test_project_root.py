"""Ticket 0.18.0-W11-001.1.1 — Group A: resolve_project_cwd 單元測試。

驗證 ``lib/project_root.resolve_project_cwd``：

- A1：git 正常回傳 toplevel 路徑。
- A2：git 失敗（CalledProcessError）時 fallback 到 os.getcwd()。
"""
from __future__ import annotations

import os
import subprocess
from unittest.mock import Mock, patch

from ticket_system.lib.project_root import resolve_project_cwd


class TestResolveProjectCwd:
    """Group A：resolve_project_cwd 單元測試。"""

    def test_a1_git_success_returns_stripped_toplevel(self):
        """A1：git rev-parse 正常回傳時，strip 換行後回傳 stdout。"""
        mock_result = Mock(stdout="/fake/root\n", returncode=0)
        with patch(
            "ticket_system.lib.project_root.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            result = resolve_project_cwd()

        assert result == "/fake/root"
        mock_run.assert_called_once()

    def test_a2_git_failure_falls_back_to_getcwd(self):
        """A2：git 失敗時 fallback 到 os.getcwd()。"""
        expected_cwd = os.getcwd()
        with patch(
            "ticket_system.lib.project_root.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                returncode=128, cmd=["git"]
            ),
        ):
            result = resolve_project_cwd()

        assert result == expected_cwd
