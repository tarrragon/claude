"""dispatch-validate 規則 5（UC 對齊）測試。"""

import json
import subprocess
from unittest.mock import patch

import pytest

from ticket_system.commands.track_dispatch_validate import (
    check_acceptance_uc_alignment,
)


class TestCheckAcceptanceUcAlignment:
    def _make_json_output(self, results, summary, sidecar_exists=True, exit_code=0):
        return json.dumps({
            "ticket_id": "1.0.0-W1-001",
            "results": results,
            "summary": summary,
            "sidecar_exists": sidecar_exists,
            "exit_code": exit_code,
        })

    def test_all_pass(self):
        stdout = self._make_json_output(
            results=[{"uc_id": "UC-01", "status": "PASS", "title": "test"}],
            summary={"pass": 1, "drift": 0, "missing": 0},
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "1 個 UC 引用全部對齊" in msg

    def test_drift_detected(self):
        stdout = self._make_json_output(
            results=[{"uc_id": "UC-01", "status": "DRIFT", "title": "test"}],
            summary={"pass": 0, "drift": 1, "missing": 0},
            exit_code=1,
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, stdout=stdout, stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is False
        assert "UC-01=DRIFT" in msg

    def test_missing_detected(self):
        stdout = self._make_json_output(
            results=[{"uc_id": "UC-99", "status": "MISSING", "title": None}],
            summary={"pass": 0, "drift": 0, "missing": 1},
            exit_code=1,
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, stdout=stdout, stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is False
        assert "UC-99=MISSING" in msg

    def test_no_uc_in_acceptance(self):
        stdout = self._make_json_output(
            results=[],
            summary={"pass": 0, "drift": 0, "missing": 0},
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "無 UC 引用" in msg

    def test_doc_cli_not_available(self):
        with patch("subprocess.run", side_effect=OSError("no doc")):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "doc CLI 不可用" in msg

    def test_doc_cli_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 15)):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "doc CLI 不可用" in msg

    def test_io_error_exit_2(self):
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 2, stdout="", stderr="IO error"),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "IO 錯誤" in msg

    def test_invalid_json_output(self):
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout="not json", stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is True
        assert "無法解析" in msg

    def test_mixed_results(self):
        stdout = self._make_json_output(
            results=[
                {"uc_id": "UC-01", "status": "PASS", "title": "ok"},
                {"uc_id": "UC-02", "status": "DRIFT", "title": "drifted"},
                {"uc_id": "UC-99", "status": "MISSING", "title": None},
            ],
            summary={"pass": 1, "drift": 1, "missing": 1},
            exit_code=1,
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, stdout=stdout, stderr=""),
        ):
            ok, msg = check_acceptance_uc_alignment("1.0.0-W1-001")
        assert ok is False
        assert "2 個 UC 對齊問題" in msg
        assert "UC-02=DRIFT" in msg
        assert "UC-99=MISSING" in msg
