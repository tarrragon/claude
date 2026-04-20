"""Ticket 0.18.0-W11-001.1.x — claim_verification 單元測試。

- Group B：``summarize_results``（5 案例，sub 1.1）
- Group C：``render_results``（4 案例，sub 1.1）
- Group D：``execute_verification`` 4 parse_strategy（sub 1.2）
- Group E：``run_all_verifications`` 循序 + 中斷處理（sub 1.2）
- Group I：subprocess cwd/env 驗證（sub 1.2）
- Group J：M4 Popen bytes decode（sub 1.2）
"""
from __future__ import annotations

import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from ticket_system.lib.ac_parser import AC
from ticket_system.lib.validation_templates import ValidationCommand
from ticket_system.lib.verification_result import (
    VerificationResult,
    VerificationSummary,
)
from ticket_system.commands.claim_verification import (
    apply_parse_strategy,
    collect_ac_verifications,
    execute_verification,
    render_results,
    run_all_verifications,
    summarize_results,
)


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------


def _make_ac(index: int, text: str = "sample AC") -> AC:
    """建立測試用 AC 物件。"""
    return AC(index=index, text=text, checked=False, raw=f"[ ] {text}")


def _make_result(
    index: int,
    status: str,
    template_name: str | None = "tpl",
    message: str = "msg",
    exit_code: int | None = 0,
) -> VerificationResult:
    """建立測試用 VerificationResult。"""
    return VerificationResult(
        ac=_make_ac(index),
        status=status,  # type: ignore[arg-type]
        template_name=template_name,
        message=message,
        exit_code=exit_code,
    )


# ----------------------------------------------------------------------
# Group B：summarize_results
# ----------------------------------------------------------------------


class TestSummarizeResults:
    """Group B：summarize_results 聚合邏輯。"""

    def test_b1_empty_list_returns_no_ac(self):
        """B1：空 list → status='no_ac', total=0。"""
        summary = summarize_results([])
        assert summary.status == "no_ac"
        assert summary.total == 0
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.unverifiable == 0

    def test_b2_all_passed(self):
        """B2：3 個 passed → status='all_passed'。"""
        results = [_make_result(i, "passed") for i in range(3)]
        summary = summarize_results(results)
        assert summary.status == "all_passed"
        assert summary.total == 3
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.unverifiable == 0

    def test_b3_has_failures(self):
        """B3：1 passed + 1 failed + 1 no_template → has_failures。"""
        results = [
            _make_result(0, "passed"),
            _make_result(1, "failed", exit_code=1),
            _make_result(2, "no_template", template_name=None),
        ]
        summary = summarize_results(results)
        assert summary.status == "has_failures"
        assert summary.total == 3
        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.unverifiable == 1

    def test_b4_none_verifiable(self):
        """B4：2 no_template + 1 unverifiable → none_verifiable。"""
        results = [
            _make_result(0, "no_template", template_name=None),
            _make_result(1, "no_template", template_name=None),
            _make_result(2, "unverifiable"),
        ]
        summary = summarize_results(results)
        assert summary.status == "none_verifiable"
        assert summary.total == 3
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.unverifiable == 3

    def test_b5_timeout_and_env_error_count_as_unverifiable(self):
        """B5：passed + timeout + env_error → timeout/env_error 計入 unverifiable。"""
        results = [
            _make_result(0, "passed"),
            _make_result(1, "timeout", exit_code=None),
            _make_result(2, "env_error", exit_code=None),
        ]
        summary = summarize_results(results)
        # 有 passed 且無 failed → all_passed（B5 著重計數邏輯）
        assert summary.passed == 1
        assert summary.failed == 0
        assert summary.unverifiable == 2
        assert summary.total == 3


# ----------------------------------------------------------------------
# Group C：render_results
# ----------------------------------------------------------------------


class TestRenderResults:
    """Group C：render_results 格式化輸出。"""

    def test_c1_standard_6_ac_within_15_lines(self):
        """C1：6 AC → 標題 + 每 AC 一行 + 總行數 <= 15。"""
        ticket_id = "0.18.0-W5-002"
        results = [
            _make_result(0, "passed", message="npm test 通過"),
            _make_result(1, "failed", message="coverage 72%"),
            _make_result(2, "timeout", message="exceeded 60s"),
            _make_result(3, "env_error", message="command not found"),
            _make_result(4, "unverifiable", message="manual check"),
            _make_result(5, "no_template", template_name=None, message="no match"),
        ]
        summary = summarize_results(results)

        output = render_results(summary, results, ticket_id)
        lines = output.split("\n")

        # (a) 標題行含 ticket_id 與 AC 總數
        assert ticket_id in lines[0]
        assert "6" in lines[0]
        # (b) 每 AC 至少一行（6 行中段）
        ac_lines = [l for l in lines if l.startswith("  [")]
        assert len(ac_lines) == 6
        # (c) 總行數 <= 15
        assert len(lines) <= 15

    def test_c2_no_ac_returns_empty_or_title_only(self):
        """C2：N=0（no_ac）時不 crash，回傳空字串。"""
        summary = summarize_results([])
        output = render_results(summary, [], "0.18.0-W5-001")
        # 允許空字串或僅標題行（不 crash 即可）
        assert output == "" or len(output.split("\n")) <= 1

    def test_c3_more_than_10_folds(self):
        """C3：N=12 → 前 10 行 + '... (2 more)' + 總行數 <= 15。"""
        results = [_make_result(i, "passed") for i in range(12)]
        summary = summarize_results(results)

        output = render_results(summary, results, "0.18.0-W5-003")
        lines = output.split("\n")

        # 存在折疊標記
        assert any("(2 more)" in l for l in lines)
        # 只顯示前 10 個 AC 行
        ac_lines = [l for l in lines if l.startswith("  [PASS]")]
        assert len(ac_lines) == 10
        # 總行數 <= 15
        assert len(lines) <= 15

    def test_c4_status_tag_mapping(self):
        """C4：各 status 對應正確的狀態標籤。"""
        results = [
            _make_result(0, "passed"),
            _make_result(1, "failed"),
            _make_result(2, "timeout"),
            _make_result(3, "env_error"),
            _make_result(4, "unverifiable"),
            _make_result(5, "no_template", template_name=None),
        ]
        summary = summarize_results(results)
        output = render_results(summary, results, "0.18.0-W5-004")

        assert "[PASS]" in output  # passed
        assert "[FAIL]" in output  # failed
        # timeout / env_error 都映射為 SKIP
        assert output.count("[SKIP]") == 2
        assert "[N/A]" in output  # unverifiable
        assert "[----]" in output  # no_template


# ----------------------------------------------------------------------
# Helper：建立 ValidationCommand 物件
# ----------------------------------------------------------------------


def _make_vc(
    template_name: str = "npm_test_pass",
    command: str | None = "npm test",
    timeout_sec: int = 60,
    parse_strategy: str = "exit_code",
    is_verifiable: bool = True,
    unverifiable_reason: str | None = None,
) -> ValidationCommand:
    """建立測試用 ValidationCommand。"""
    return ValidationCommand(
        template_name=template_name,
        command=command,
        timeout_sec=timeout_sec,
        parse_strategy=parse_strategy,  # type: ignore[arg-type]
        is_verifiable=is_verifiable,
        unverifiable_reason=unverifiable_reason,
    )


def _make_popen_mock(
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    communicate_side_effect=None,
) -> Mock:
    """建立 subprocess.Popen 的 Mock 實例。"""
    proc = Mock()
    proc.pid = 12345
    proc.returncode = returncode
    if communicate_side_effect is not None:
        proc.communicate = Mock(side_effect=communicate_side_effect)
    else:
        proc.communicate = Mock(return_value=(stdout, stderr))
    return proc


# ----------------------------------------------------------------------
# Group D：execute_verification 的 4 種 parse_strategy
# ----------------------------------------------------------------------


@patch("ticket_system.commands.claim_verification.subprocess.Popen")
class TestExecuteVerification:
    """Group D：execute_verification 依 parse_strategy 判定 status。"""

    def test_d1_exit_code_strategy_pass(self, mock_popen_cls):
        """D1：exit_code 策略 + returncode=0 → passed。"""
        mock_popen_cls.return_value = _make_popen_mock(returncode=0)
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code", command="npm run lint")

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"
        assert result.exit_code == 0
        assert result.template_name == "npm_test_pass"

    def test_d2_exit_code_strategy_fail(self, mock_popen_cls):
        """D2：exit_code 策略 + returncode=1 → failed。"""
        mock_popen_cls.return_value = _make_popen_mock(returncode=1)
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code", command="npm run lint")

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "failed"
        assert result.exit_code == 1

    def test_d3_tail_lines_strategy_pass(self, mock_popen_cls):
        """D3：tail_lines 策略 + 末 5 行無 failed 且 exit_code=0 → passed。"""
        stdout = b"Running tests...\n5 passing\n0 failed\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=0, stdout=stdout
        )
        ac = _make_ac(0, "測試全部通過")
        vc = _make_vc(parse_strategy="tail_lines", command="npm test")

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"

    def test_d4_tail_lines_strategy_fail(self, mock_popen_cls):
        """D4：tail_lines 策略 + 末 5 行含「3 failed」→ failed。"""
        stdout = b"Running...\n2 passing\n3 failed\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=1, stdout=stdout
        )
        ac = _make_ac(0, "測試全部通過")
        vc = _make_vc(parse_strategy="tail_lines", command="npm test")

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "failed"

    def test_d5a_coverage_explicit_threshold_pass(self, mock_popen_cls):
        """D5a：AC 含「>= 90%」+ 實測 92% → passed。"""
        stdout = b"Statements: 92%\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=0, stdout=stdout
        )
        ac = _make_ac(0, "覆蓋率 >= 90%")
        vc = _make_vc(
            parse_strategy="coverage_number", command="npm run test:coverage"
        )

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"

    def test_d5b_coverage_fallback_threshold_fail(self, mock_popen_cls):
        """D5b：AC 無百分比 + 實測 79% → failed（fallback 80%）。"""
        stdout = b"Statements: 79%\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=0, stdout=stdout
        )
        ac = _make_ac(0, "覆蓋率達標")
        vc = _make_vc(
            parse_strategy="coverage_number", command="npm run test:coverage"
        )

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "failed"

    def test_d5c_coverage_fallback_threshold_boundary(self, mock_popen_cls):
        """D5c：AC 無百分比 + 實測 80% → passed（邊界值）。"""
        stdout = b"Statements: 80%\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=0, stdout=stdout
        )
        ac = _make_ac(0, "覆蓋率達標")
        vc = _make_vc(
            parse_strategy="coverage_number", command="npm run test:coverage"
        )

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"

    def test_d5d_coverage_no_number_in_stdout_fail(self, mock_popen_cls):
        """D5d：stdout 無百分比 → failed（無法抽取實測）。"""
        stdout = b"No coverage info emitted\n"
        mock_popen_cls.return_value = _make_popen_mock(
            returncode=0, stdout=stdout
        )
        ac = _make_ac(0, "覆蓋率 >= 80%")
        vc = _make_vc(
            parse_strategy="coverage_number", command="npm run test:coverage"
        )

        result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "failed"


# ----------------------------------------------------------------------
# Group E：run_all_verifications 循序 + 中斷處理
# ----------------------------------------------------------------------


class TestRunAllVerifications:
    """Group E：循序執行多 AC + timeout/KeyboardInterrupt 處理。"""

    def test_e1_normal_sequential_execution(self):
        """E1：3 對可驗證 pair → Popen 被呼叫 3 次。"""
        pairs = [
            (_make_ac(i, "lint 通過"), _make_vc(parse_strategy="exit_code"))
            for i in range(3)
        ]
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(returncode=0)
            results = run_all_verifications(pairs, "/fake/root")

        assert len(results) == 3
        assert mock_popen.call_count == 3
        assert all(r.status == "passed" for r in results)

    def test_e2_vc_none_yields_no_template(self):
        """E2：vc=None → status='no_template'，Popen 未被呼叫。"""
        pairs = [(_make_ac(0, "some AC"), None)]
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            results = run_all_verifications(pairs, "/fake/root")

        assert len(results) == 1
        assert results[0].status == "no_template"
        assert results[0].template_name is None
        mock_popen.assert_not_called()

    def test_e3_is_verifiable_false_yields_unverifiable(self):
        """E3：vc.is_verifiable=False → status='unverifiable'，取 reason。"""
        vc = _make_vc(
            template_name="flaky_fixed",
            command=None,
            parse_strategy="manual",
            is_verifiable=False,
            unverifiable_reason="flaky 需人工審查",
        )
        pairs = [(_make_ac(0, "flaky 修復"), vc)]
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            results = run_all_verifications(pairs, "/fake/root")

        assert len(results) == 1
        assert results[0].status == "unverifiable"
        assert results[0].message == "flaky 需人工審查"
        mock_popen.assert_not_called()

    def test_e4_timeout_marks_and_continues(self):
        """E4：Popen.communicate 拋 TimeoutExpired → status='timeout' 且 killpg 被呼叫後繼續下一 AC。"""
        pairs = [
            (_make_ac(0, "lint 通過"), _make_vc(parse_strategy="exit_code")),
            (_make_ac(1, "lint 通過"), _make_vc(parse_strategy="exit_code")),
        ]
        proc_timeout = _make_popen_mock(
            communicate_side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60)
        )
        proc_ok = _make_popen_mock(returncode=0)
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen",
            side_effect=[proc_timeout, proc_ok],
        ), patch(
            "ticket_system.commands.claim_verification.os.killpg"
        ) as mock_killpg, patch(
            "ticket_system.commands.claim_verification.os.getpgid",
            return_value=12345,
        ), patch("ticket_system.commands.claim_verification.time.sleep"):
            results = run_all_verifications(pairs, "/fake/root")

        assert len(results) == 2
        assert results[0].status == "timeout"
        assert results[0].exit_code is None
        assert results[1].status == "passed"
        # SIGTERM + SIGKILL → killpg 被呼叫 2 次
        assert mock_killpg.call_count >= 1

    def test_e4a_killpg_sigterm_then_sigkill_order(self):
        """E4a：timeout 時 SIGTERM 先、sleep、再 SIGKILL。"""
        import signal as _signal

        pairs = [(_make_ac(0, "lint 通過"), _make_vc(parse_strategy="exit_code"))]
        proc = _make_popen_mock(
            communicate_side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60)
        )
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen",
            return_value=proc,
        ), patch(
            "ticket_system.commands.claim_verification.os.killpg"
        ) as mock_killpg, patch(
            "ticket_system.commands.claim_verification.os.getpgid",
            return_value=12345,
        ), patch(
            "ticket_system.commands.claim_verification.time.sleep"
        ) as mock_sleep:
            run_all_verifications(pairs, "/fake/root")

        # 兩次 killpg 分別為 SIGTERM 和 SIGKILL
        signals_sent = [call.args[1] for call in mock_killpg.call_args_list]
        assert _signal.SIGTERM in signals_sent
        assert _signal.SIGKILL in signals_sent
        mock_sleep.assert_called()

    def test_e5_keyboard_interrupt_propagates(self):
        """E5：Popen.communicate 拋 KeyboardInterrupt → killpg 並往上傳播。"""
        pairs = [(_make_ac(0, "lint 通過"), _make_vc(parse_strategy="exit_code"))]
        proc = _make_popen_mock(communicate_side_effect=KeyboardInterrupt())
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen",
            return_value=proc,
        ), patch(
            "ticket_system.commands.claim_verification.os.killpg"
        ) as mock_killpg, patch(
            "ticket_system.commands.claim_verification.os.getpgid",
            return_value=12345,
        ), patch("ticket_system.commands.claim_verification.time.sleep"):
            with pytest.raises(KeyboardInterrupt):
                run_all_verifications(pairs, "/fake/root")

        mock_killpg.assert_called()

    def test_e6_os_error_marks_env_error(self):
        """E6（K1 併入 Group E）：Popen 拋 FileNotFoundError → status='env_error'。"""
        pairs = [(_make_ac(0, "lint 通過"), _make_vc(parse_strategy="exit_code"))]
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen",
            side_effect=FileNotFoundError("npm not found"),
        ):
            results = run_all_verifications(pairs, "/fake/root")

        assert len(results) == 1
        assert results[0].status == "env_error"
        assert "npm" in results[0].message or "missing" in results[0].message


# ----------------------------------------------------------------------
# Group I：subprocess cwd / env 驗證
# ----------------------------------------------------------------------


class TestSubprocessCwdEnv:
    """Group I：Popen 傳遞的 cwd 與 env 參數正確性。"""

    def test_i1_cwd_passed_through(self):
        """I1（P2-cwd1）：傳入的 cwd 原樣傳給 Popen。"""
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code")
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(returncode=0)
            execute_verification(ac, vc, "/fake/root")

        _, kwargs = mock_popen.call_args
        assert kwargs["cwd"] == "/fake/root"

    def test_i2_cwd_from_getcwd(self):
        """I2（P2-cwd2）：當呼叫端傳入 os.getcwd() 時 Popen 收到同一值。"""
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code")
        cwd = os.getcwd()
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(returncode=0)
            execute_verification(ac, vc, cwd)

        _, kwargs = mock_popen.call_args
        assert kwargs["cwd"] == cwd

    def test_i3_env_inherits_parent(self):
        """I3（P2-env1）：Popen kwargs 不包含 env（繼承 parent）。"""
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code")
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(returncode=0)
            execute_verification(ac, vc, "/fake/root")

        _, kwargs = mock_popen.call_args
        # 未指定 env 或 env=None → 繼承父 process
        assert "env" not in kwargs or kwargs["env"] is None


# ----------------------------------------------------------------------
# Group J：M4 Popen bytes decode
# ----------------------------------------------------------------------


class TestPopenBytesDecode:
    """Group J：subprocess 輸出的 bytes 解碼。"""

    def test_j1_utf8_decoded_correctly(self):
        """J1：UTF-8 bytes 正常解碼後進 parse_strategy。"""
        ac = _make_ac(0, "測試全部通過")
        vc = _make_vc(parse_strategy="tail_lines", command="npm test")
        stdout = "5 passing\n0 failed\n".encode("utf-8")
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(
                returncode=0, stdout=stdout
            )
            result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"

    def test_j2_non_utf8_does_not_crash(self):
        """J2：非 UTF-8 bytes 以 errors='replace' 降級，不 crash。"""
        ac = _make_ac(0, "lint 通過")
        vc = _make_vc(parse_strategy="exit_code", command="npm run lint")
        stdout = b"\xff\xfe\xfd invalid bytes"
        with patch(
            "ticket_system.commands.claim_verification.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value = _make_popen_mock(
                returncode=0, stdout=stdout
            )
            # 不應 raise UnicodeDecodeError
            result = execute_verification(ac, vc, "/fake/root")

        assert result.status == "passed"


# ----------------------------------------------------------------------
# 補充：apply_parse_strategy 純函式直接測試（manual strategy）
# ----------------------------------------------------------------------


class TestApplyParseStrategy:
    """apply_parse_strategy 的純函式直接測試（補 manual 路徑）。"""

    def test_manual_strategy_returns_unverifiable(self):
        """manual 策略固定回 unverifiable。"""
        assert (
            apply_parse_strategy("manual", "", b"", 0, "任意 AC 文字")
            == "unverifiable"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
