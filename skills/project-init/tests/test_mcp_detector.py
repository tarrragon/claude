"""測試 MCP server 偵測模組（mcp_detector.py）。

驗收 W6-001.2 acceptance #5：覆蓋 success / missing CLI / stale index 三情境。
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from project_init.lib.mcp_detector import (
    INDEX_MCP_MANAGED,
    INDEX_MISSING,
    INDEX_OK,
    INDEX_UNKNOWN,
    McpInfo,
    detect_codebase_memory_mcp,
    detect_codegraph,
)


class TestCodebaseMemoryMcpDetection:
    """測試 codebase-memory-mcp 偵測（cbm 索引由 MCP 工具管理）。"""

    def test_cbm_found_success(self) -> None:
        """成功偵測到 cbm binary 與版本，index_status 為 MCP_MANAGED."""
        with patch("project_init.lib.mcp_detector.shutil.which") as mock_which:
            mock_which.return_value = "/opt/homebrew/bin/codebase-memory-mcp"
            with patch("project_init.lib.mcp_detector.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="codebase-memory-mcp 0.6.1\n",
                )
                info = detect_codebase_memory_mcp()
                assert info.is_available is True
                assert info.name == "codebase-memory-mcp"
                assert info.version == "codebase-memory-mcp 0.6.1"
                assert info.path == "/opt/homebrew/bin/codebase-memory-mcp"
                assert info.index_status == INDEX_MCP_MANAGED
                assert info.failure_reason is None

    def test_cbm_missing(self) -> None:
        """cbm binary 不在 PATH，is_available=False + failure_reason."""
        with patch(
            "project_init.lib.mcp_detector.shutil.which", return_value=None
        ):
            info = detect_codebase_memory_mcp()
            assert info.is_available is False
            assert info.path is None
            assert info.version == ""
            assert "PATH" in info.failure_reason

    def test_cbm_version_command_failed(self) -> None:
        """binary 存在但 --version 失敗，視為 not available."""
        with patch(
            "project_init.lib.mcp_detector.shutil.which",
            return_value="/opt/homebrew/bin/codebase-memory-mcp",
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                info = detect_codebase_memory_mcp()
                assert info.is_available is False
                assert info.path is None

    def test_cbm_timeout(self) -> None:
        """--version 命令超時，視為 not available."""
        with patch(
            "project_init.lib.mcp_detector.shutil.which",
            return_value="/opt/homebrew/bin/codebase-memory-mcp",
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(
                    "codebase-memory-mcp", 5
                )
                info = detect_codebase_memory_mcp()
                assert info.is_available is False


class TestCodegraphDetection:
    """測試 codegraph (@astudioplus/codegraph-mcp) 偵測與 .codegraph/ 索引判定。"""

    def test_codegraph_found_with_index(self, tmp_path: Path) -> None:
        """成功偵測 codegraph-mcp + .codegraph/ 目錄存在 → INDEX_OK."""
        codegraph_dir = tmp_path / ".codegraph"
        codegraph_dir.mkdir()

        def fake_which(name: str):
            return (
                "/opt/homebrew/bin/codegraph-mcp"
                if name == "codegraph-mcp"
                else None
            )

        with patch(
            "project_init.lib.mcp_detector.shutil.which", side_effect=fake_which
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="codegraph-server v0.16.6 (17d1417)\nAuthor: ...\n",
                )
                info = detect_codegraph(project_root=tmp_path)
                assert info.is_available is True
                assert info.name == "codegraph"
                assert info.version == "codegraph-server v0.16.6 (17d1417)"
                assert info.path == "/opt/homebrew/bin/codegraph-mcp"
                assert info.index_status == INDEX_OK
                assert info.failure_reason is None

    def test_codegraph_missing_cli(self) -> None:
        """codegraph-mcp 與 fallback codegraph 都不存在 → is_available=False."""
        with patch(
            "project_init.lib.mcp_detector.shutil.which", return_value=None
        ):
            info = detect_codegraph(project_root=Path("/tmp/nonexistent"))
            assert info.is_available is False
            assert info.path is None
            assert "PATH" in info.failure_reason
            assert "@astudioplus/codegraph-mcp" in info.failure_reason

    def test_codegraph_found_but_index_missing(self, tmp_path: Path) -> None:
        """codegraph-mcp OK 但 .codegraph/ 不存在 → INDEX_MISSING（stale 情境）."""

        def fake_which(name: str):
            return (
                "/opt/homebrew/bin/codegraph-mcp"
                if name == "codegraph-mcp"
                else None
            )

        with patch(
            "project_init.lib.mcp_detector.shutil.which", side_effect=fake_which
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="codegraph-server v0.16.6\n"
                )
                # tmp_path 不含 .codegraph/ 目錄
                info = detect_codegraph(project_root=tmp_path)
                assert info.is_available is True
                assert info.index_status == INDEX_MISSING

    def test_codegraph_index_unknown_without_project_root(self) -> None:
        """未傳 project_root → index_status = INDEX_UNKNOWN."""

        def fake_which(name: str):
            return (
                "/opt/homebrew/bin/codegraph-mcp"
                if name == "codegraph-mcp"
                else None
            )

        with patch(
            "project_init.lib.mcp_detector.shutil.which", side_effect=fake_which
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="codegraph-server v0.16.6\n"
                )
                info = detect_codegraph(project_root=None)
                assert info.is_available is True
                assert info.index_status == INDEX_UNKNOWN

    def test_codegraph_fallback_to_legacy_name(self, tmp_path: Path) -> None:
        """codegraph-mcp 不存在但舊版 codegraph 存在 → fallback 成功."""
        codegraph_dir = tmp_path / ".codegraph"
        codegraph_dir.mkdir()

        def fake_which(name: str):
            # codegraph-mcp 不存在，codegraph 存在
            return "/usr/local/bin/codegraph" if name == "codegraph" else None

        with patch(
            "project_init.lib.mcp_detector.shutil.which", side_effect=fake_which
        ):
            with patch(
                "project_init.lib.mcp_detector.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="codegraph 0.12.3 (legacy)\n"
                )
                info = detect_codegraph(project_root=tmp_path)
                assert info.is_available is True
                assert info.path == "/usr/local/bin/codegraph"
                assert info.index_status == INDEX_OK
