"""uc acceptance-check 子命令測試。"""

import argparse
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc_system.commands import uc
from doc_system.core.file_locator import FileLocator
from doc_system.core.uc_registry import update_fingerprints


def _setup_project(tmp_path, uc_content=None):
    """建立含 SSOT 的最小專案骨架。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    content = uc_content or "## UC-01: 匯入書庫\n內容A\n\n## UC-02: 匯出書庫\n內容B\n"
    (docs_dir / "app-use-cases.md").write_text(content, encoding="utf-8")
    return str(tmp_path)


def _make_ticket_output(acceptance_items):
    """產生模擬 ticket track full 輸出。"""
    import yaml

    frontmatter = {
        "id": "1.0.0-W1-001",
        "title": "test ticket",
        "type": "IMP",
        "status": "in_progress",
        "acceptance": acceptance_items,
    }
    fm_text = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm_text}---\n\n# Execution Log\n"


def _mock_subprocess_for_ticket(acceptance_items):
    """回傳 mock subprocess.run 的 side_effect。"""
    output = _make_ticket_output(acceptance_items)

    def side_effect(cmd, **kwargs):
        if cmd[0] == "ticket":
            return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")
        raise OSError("unexpected command")

    return side_effect


# ---------------------------------------------------------------------------
# _get_ticket_acceptance 測試
# ---------------------------------------------------------------------------


class TestGetTicketAcceptance:
    def test_extracts_acceptance_items(self):
        items = ["[ ] UC-01 相關檢查", "[ ] UC-02 驗證"]
        with patch("subprocess.run", side_effect=_mock_subprocess_for_ticket(items)):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error is None
        assert len(result) == 2
        assert "UC-01" in result[0]

    def test_returns_error_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error == "timeout"
        assert result == []

    def test_returns_error_on_oserror(self):
        with patch("subprocess.run", side_effect=OSError("no such cmd")):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error == "cli_error"

    def test_returns_error_on_nonzero_exit(self):
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="not found"),
        ):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error == "not_found"

    def test_returns_error_on_no_frontmatter(self):
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout="no frontmatter", stderr=""),
        ):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error == "no_frontmatter"

    def test_empty_acceptance(self):
        with patch("subprocess.run", side_effect=_mock_subprocess_for_ticket([])):
            result, error = uc._get_ticket_acceptance("1.0.0-W1-001")
        assert error is None
        assert result == []


# ---------------------------------------------------------------------------
# _cmd_acceptance_check 測試
# ---------------------------------------------------------------------------


class TestCmdAcceptanceCheck:
    def _run(self, tmp_path, acceptance_items, as_json=False, init_sidecar=False):
        """執行 acceptance-check 並回傳 (output, exit_code)。"""
        project_root = _setup_project(tmp_path)
        if init_sidecar:
            update_fingerprints(project_root)

        args = argparse.Namespace(
            uc_command="acceptance-check",
            ticket_id="1.0.0-W1-001",
            json=as_json,
        )

        exit_code = None
        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("subprocess.run", side_effect=_mock_subprocess_for_ticket(acceptance_items)),
            pytest.raises(SystemExit) as exc_info,
        ):
            uc._cmd_acceptance_check(args)
        exit_code = exc_info.value.code
        return exit_code

    def test_all_pass_without_sidecar(self, tmp_path, capsys):
        exit_code = self._run(
            tmp_path,
            ["[ ] UC-01 驗證匯入", "[ ] UC-02 驗證匯出"],
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "[PASS] UC-01" in out
        assert "[PASS] UC-02" in out
        assert "sidecar 不存在" in out

    def test_all_pass_with_sidecar(self, tmp_path, capsys):
        exit_code = self._run(
            tmp_path,
            ["[ ] UC-01 驗證匯入"],
            init_sidecar=True,
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "[PASS] UC-01" in out
        assert "sidecar 不存在" not in out

    def test_missing_uc(self, tmp_path, capsys):
        exit_code = self._run(
            tmp_path,
            ["[ ] UC-99 不存在的 UC"],
        )
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "[MISSING] UC-99" in out
        assert "[FAIL]" in out

    def test_drift_detection(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        update_fingerprints(project_root)

        # Tamper fingerprint to simulate drift
        sidecar_path = Path(project_root) / ".uc-fingerprints.json"
        data = json.loads(sidecar_path.read_text())
        data["UC-01"]["fingerprint"] = "deadbeef" * 8
        sidecar_path.write_text(json.dumps(data))

        args = argparse.Namespace(
            uc_command="acceptance-check",
            ticket_id="1.0.0-W1-001",
            json=False,
        )
        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch(
                "subprocess.run",
                side_effect=_mock_subprocess_for_ticket(["[ ] UC-01 驗證"]),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            uc._cmd_acceptance_check(args)

        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "[DRIFT] UC-01" in out
        assert "[FAIL]" in out

    def test_no_uc_in_acceptance(self, tmp_path, capsys):
        exit_code = self._run(tmp_path, ["[ ] 無 UC 引用的檢查項"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "無 UC 引用" in out

    def test_json_output(self, tmp_path, capsys):
        exit_code = self._run(
            tmp_path,
            ["[ ] UC-01 驗證", "[ ] UC-99 不存在"],
            as_json=True,
        )
        assert exit_code == 1
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["ticket_id"] == "1.0.0-W1-001"
        assert len(data["results"]) == 2
        assert data["summary"]["pass"] == 1
        assert data["summary"]["missing"] == 1
        assert data["exit_code"] == 1

    def test_deduplicates_uc_tokens(self, tmp_path, capsys):
        exit_code = self._run(
            tmp_path,
            ["[ ] UC-01 第一次", "[ ] UC-01 第二次"],
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert out.count("UC-01") == 1

    def test_ticket_not_found_exits_2(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(
            uc_command="acceptance-check",
            ticket_id="99.99.99-W1-999",
            json=False,
        )
        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="not found"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            uc._cmd_acceptance_check(args)
        assert exc_info.value.code == 2

    def test_ticket_not_found_json_exits_2(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(
            uc_command="acceptance-check",
            ticket_id="99.99.99-W1-999",
            json=True,
        )
        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="not found"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            uc._cmd_acceptance_check(args)
        assert exc_info.value.code == 2
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "error" in data
        assert data["exit_code"] == 2
