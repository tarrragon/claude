"""測試 ticket track dispatch-readiness 命令（0.18.0-W17-053）。

涵蓋三項核心閾值 + exit code 矩陣：
- 閾值 1（功能職責數 / acceptance 近似）：≤2 pass / 3-4 warn / >4 fail
- 閾值 2（修改檔案數 where.files）：≤5 pass / 6-10 warn / >10 fail
- 閾值 3（Context Bundle tokens 近似）：≤3000 pass / 3001-5000 warn / >5000 fail
- ticket 不存在 / IO 錯誤 → exit 2
- 任一 fail → exit 2；任一 warn 無 fail → exit 1；全 pass → exit 0
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from ticket_system.commands.track_dispatch_readiness import (
    check_context_bundle_tokens,
    check_file_count,
    check_responsibility_count,
    execute_dispatch_readiness,
)


# ---------------------------------------------------------------------------
# 純函式單元測試
# ---------------------------------------------------------------------------


class TestResponsibilityCount:
    def test_two_or_fewer_pass(self):
        status, n, _ = check_responsibility_count(["a", "b"])
        assert status == "pass"
        assert n == 2

    def test_three_to_four_warn(self):
        status, _, _ = check_responsibility_count(["a", "b", "c"])
        assert status == "warn"
        status2, _, _ = check_responsibility_count(["a", "b", "c", "d"])
        assert status2 == "warn"

    def test_more_than_four_fail(self):
        status, n, _ = check_responsibility_count(["a", "b", "c", "d", "e"])
        assert status == "fail"
        assert n == 5

    def test_none_treated_as_zero(self):
        status, n, _ = check_responsibility_count(None)
        assert status == "pass"
        assert n == 0


class TestFileCount:
    def test_five_or_fewer_pass(self):
        status, _, _ = check_file_count(["a", "b", "c", "d", "e"])
        assert status == "pass"

    def test_six_to_ten_warn(self):
        status, _, _ = check_file_count([f"f{i}" for i in range(6)])
        assert status == "warn"
        status2, _, _ = check_file_count([f"f{i}" for i in range(10)])
        assert status2 == "warn"

    def test_more_than_ten_fail(self):
        status, n, _ = check_file_count([f"f{i}" for i in range(11)])
        assert status == "fail"
        assert n == 11

    def test_empty_pass(self):
        status, n, _ = check_file_count([])
        assert status == "pass"
        assert n == 0

    def test_filters_empty_strings(self):
        status, n, _ = check_file_count(["a", "", "b"])
        assert status == "pass"
        assert n == 2


class TestContextBundleTokens:
    def test_missing_section_pass(self):
        status, est, _ = check_context_bundle_tokens("no section")
        assert status == "pass"
        assert est == 0

    def test_small_pass(self):
        body = "## Context Bundle\n\n" + ("x" * 200) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "pass"
        assert est < 3000

    def test_above_soft_warn(self):
        # > 3000 tokens ≈ > 12000 chars
        body = "## Context Bundle\n\n" + ("x" * 13000) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "warn"
        assert est > 3000 and est <= 5000

    def test_above_hard_fail(self):
        # > 5000 tokens ≈ > 20000 chars
        body = "## Context Bundle\n\n" + ("x" * 25000) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "fail"
        assert est > 5000


# ---------------------------------------------------------------------------
# CLI 整合測試（mock load_ticket）
# ---------------------------------------------------------------------------


def _args(ticket_id: str = "0.18.0-W17-053") -> argparse.Namespace:
    return argparse.Namespace(
        operation="dispatch-readiness",
        ticket_id=ticket_id,
        version=None,
    )


def _run(ticket_dict) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "ticket_system.lib.dispatch_common.load_ticket",
        return_value=ticket_dict,
    ), redirect_stdout(out), redirect_stderr(err):
        rc = execute_dispatch_readiness(_args(), "0.18.0")
    return rc, out.getvalue(), err.getvalue()


class TestExecuteDispatchReadiness:
    def test_ticket_not_found_returns_2(self):
        rc, _out, err = _run(None)
        assert rc == 2
        assert "不存在" in err

    def test_yaml_error_returns_2(self):
        rc, _out, err = _run({"_yaml_error": "bad yaml"})
        assert rc == 2
        assert "YAML" in err

    def test_all_pass_returns_0(self):
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket)
        assert rc == 0
        assert "全數通過" in out

    def test_warn_acceptance_returns_1(self):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket)
        assert rc == 1
        assert "軟性警告" in out

    def test_warn_files_returns_1(self):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(7)]},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 1

    def test_fail_acceptance_returns_2(self):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c", "d", "e"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket)
        assert rc == 2
        assert "拆 ticket" in out or "拆分" in out

    def test_fail_files_returns_2(self):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(12)]},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2

    def test_fail_cb_tokens_returns_2(self):
        ticket = {
            "_body": "## Context Bundle\n\n" + ("x" * 25000) + "\n",
            "acceptance": ["a"],
            "where": {"files": []},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2

    def test_fail_overrides_warn(self):
        # 一項 warn + 一項 fail → exit 2
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],  # warn
            "where": {"files": [f"f{i}.py" for i in range(12)]},  # fail
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2
