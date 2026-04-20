"""Ticket 0.18.0-W11-001.1.3 — 互動層 + lifecycle 整合測試。

測試範圍：

- Group F：``prompt_user_decision`` 互動決策（7 案例）。
- Group G：``collect_ac_verifications`` 配對邏輯（3 案例）。
- Group H：``claim_with_verification`` 端到端主流程（12 案例）。
- Group K：錯誤處理邊界 K2/K3（2 案例，K1 已在 Group E 的
  ``test_e6_os_error_marks_env_error`` 覆蓋）。

測試策略：

- Group F：mock ``builtins.input`` / ``sys.stdin.isatty`` 直接單元測試。
- Group G：mock ``parse_ac``，避免檔案系統依賴。
- Group H：mock ``collect_ac_verifications`` 和 ``TicketLifecycle.claim``
  以隔離 AC 驗證邏輯與既有 claim 流程。
"""
from __future__ import annotations

import io
import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from ticket_system.lib.ac_parser import AC
from ticket_system.lib.validation_templates import ValidationCommand
from ticket_system.lib.verification_result import (
    VerificationResult,
    VerificationSummary,
)
from ticket_system.commands.claim_verification import (
    collect_ac_verifications,
    prompt_user_decision,
)
from ticket_system.commands.lifecycle import TicketLifecycle


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_ac(index: int, text: str = "sample AC") -> AC:
    return AC(index=index, text=text, checked=False, raw=f"[ ] {text}")


def _make_vc(
    template_name: str = "npm_test_pass",
    command: str | None = "npm test 2>&1 | tail -5",
    timeout_sec: int = 300,
    parse_strategy: str = "tail_lines",
    is_verifiable: bool = True,
    unverifiable_reason: str | None = None,
) -> ValidationCommand:
    return ValidationCommand(
        template_name=template_name,
        command=command,
        timeout_sec=timeout_sec,
        parse_strategy=parse_strategy,  # type: ignore[arg-type]
        is_verifiable=is_verifiable,
        unverifiable_reason=unverifiable_reason,
    )


def _make_summary(
    status: str = "has_failures",
    total: int = 1,
    passed: int = 0,
    failed: int = 1,
    unverifiable: int = 0,
) -> VerificationSummary:
    return VerificationSummary(
        total=total,
        passed=passed,
        failed=failed,
        unverifiable=unverifiable,
        status=status,  # type: ignore[arg-type]
    )


# ======================================================================
# Group F：prompt_user_decision
# ======================================================================


class TestPromptUserDecision:
    """Group F：y/n 互動決策 + --yes 短路 + 非 tty 處理。"""

    def test_f1_input_yes(self):
        """F1：輸入 'y' → 回 'y'。"""
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value="y"
        ):
            assert prompt_user_decision(_make_summary(), auto_yes=False) == "y"

    def test_f2_input_no(self):
        """F2：輸入 'n' → 回 'n'。"""
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value="n"
        ):
            assert prompt_user_decision(_make_summary(), auto_yes=False) == "n"

    def test_f3_empty_defaults_yes(self):
        """F3：空字串 → 預設 'y'。"""
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value=""
        ):
            assert prompt_user_decision(_make_summary(), auto_yes=False) == "y"

    def test_f4_three_invalid_defaults_no(self):
        """F4：3 次無效輸入 → 預設 'n'（fail-closed）。"""
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", side_effect=["x", "abc", "?"]
        ) as mock_input:
            assert prompt_user_decision(_make_summary(), auto_yes=False) == "n"
        assert mock_input.call_count == 3

    def test_f5_auto_yes_short_circuits(self):
        """F5：--yes 短路，input 不被呼叫。"""
        with patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input"
        ) as mock_input:
            assert prompt_user_decision(_make_summary(), auto_yes=True) == "y"
        mock_input.assert_not_called()

    def test_f6_non_tty_without_yes_cancels(self, capsys):
        """F6：非 tty 且無 --yes → 回 'n' + stderr 含警告。"""
        with patch("sys.stdin.isatty", return_value=False):
            assert prompt_user_decision(_make_summary(), auto_yes=False) == "n"
        captured = capsys.readouterr()
        assert "non-interactive" in captured.err

    def test_f7_non_tty_with_yes_returns_yes(self):
        """F7：非 tty 但 --yes → 回 'y'（--yes 短路不受 tty 影響）。"""
        with patch("sys.stdin.isatty", return_value=False), patch(
            "builtins.input"
        ) as mock_input:
            assert prompt_user_decision(_make_summary(), auto_yes=True) == "y"
        mock_input.assert_not_called()


# ======================================================================
# Group G：collect_ac_verifications
# ======================================================================


class TestCollectAcVerifications:
    """Group G：parse_ac + match_template 配對。"""

    def test_g1_pairs_acs_with_templates(self):
        """G1：正常配對，每個 AC 對應 VC or None。"""
        acs = [
            _make_ac(0, "npm test 通過"),
            _make_ac(1, "flaky 修復"),
            _make_ac(2, "某個無模板的驗收條件"),
        ]
        with patch(
            "ticket_system.commands.claim_verification.parse_ac",
            return_value=acs,
        ):
            pairs = collect_ac_verifications("0.18.0-W5-002")

        assert len(pairs) == 3
        # 第一項：npm_test_pass
        assert pairs[0][1] is not None
        assert pairs[0][1].template_name == "npm_test_pass"
        # 第二項：flaky_fixed（is_verifiable=False）
        assert pairs[1][1] is not None
        assert pairs[1][1].is_verifiable is False
        # 第三項：無模板
        assert pairs[2][1] is None

    def test_g2_no_acceptance_returns_empty(self):
        """G2：Ticket 無 AC → 回傳空 list。"""
        with patch(
            "ticket_system.commands.claim_verification.parse_ac",
            return_value=[],
        ):
            pairs = collect_ac_verifications("0.18.0-W5-002")
        assert pairs == []

    def test_g3_parse_ac_value_error_propagates(self):
        """G3：parse_ac 拋 ValueError → 傳播給上層。"""
        with patch(
            "ticket_system.commands.claim_verification.parse_ac",
            side_effect=ValueError("YAML 格式錯誤"),
        ):
            with pytest.raises(ValueError, match="YAML"):
                collect_ac_verifications("0.18.0-W5-002")


# ======================================================================
# Group H：claim_with_verification 端到端
# ======================================================================


def _make_passing_result(index: int = 0) -> VerificationResult:
    return VerificationResult(
        ac=_make_ac(index, "npm test 通過"),
        status="passed",
        template_name="npm_test_pass",
        message="ok",
        exit_code=0,
    )


def _make_failing_result(index: int = 0) -> VerificationResult:
    return VerificationResult(
        ac=_make_ac(index, "lint 通過"),
        status="failed",
        template_name="lint_pass",
        message="fail",
        exit_code=1,
    )


def _make_unverifiable_result(index: int = 0) -> VerificationResult:
    return VerificationResult(
        ac=_make_ac(index, "某 AC"),
        status="unverifiable",
        template_name="flaky_fixed",
        message="manual review",
        exit_code=None,
    )


class TestClaimWithVerification:
    """Group H：claim_with_verification 主流程（S1-S7 + flag 組合）。"""

    def _lifecycle(self) -> TicketLifecycle:
        return TicketLifecycle(version="0.18.0")

    def test_h1_s1_no_ac_direct_claim(self):
        """H1：S1 無 AC → 直接 claim。"""
        lifecycle = self._lifecycle()
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=[],
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 0
        mock_claim.assert_called_once_with("0.18.0-W5-002")

    def test_h2_s2_all_unverifiable_direct_claim(self, capsys):
        """H2：S2 全部 unverifiable → 顯示摘要 + 直接 claim。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc(is_verifiable=False))]
        results = [_make_unverifiable_result(0)]
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 0
        mock_claim.assert_called_once()
        captured = capsys.readouterr()
        assert "無法自動驗證" in captured.out

    def test_h3_s3_with_y_continues_claim(self):
        """H3：S3 (has_failures) + 'y' → claim。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        results = [_make_failing_result(0)]
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True), patch(
                "builtins.input", return_value="y"
            ):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 0
        mock_claim.assert_called_once()

    def test_h4_s3_with_n_cancels(self):
        """H4：S3 + 'n' → 不 claim，return 1。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        results = [_make_failing_result(0)]
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True), patch(
                "builtins.input", return_value="n"
            ):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 1
        mock_claim.assert_not_called()

    def test_h5_s4_all_passed_rejects_claim(self, capsys):
        """H5：S4 all_passed → 拒絕 claim + stderr 建議訊息 + return 1。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        results = [_make_passing_result(0)]
        with patch.object(lifecycle, "claim") as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 1
        mock_claim.assert_not_called()
        captured = capsys.readouterr()
        assert "complete" in captured.err
        assert "已達成" in captured.err

    def test_h6_s4_with_auto_yes_still_rejects(self, capsys):
        """H6：S4 + --yes → 仍 return 1（all_passed 攔截在 prompt 前）。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        results = [_make_passing_result(0)]
        with patch.object(lifecycle, "claim") as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification(
                "0.18.0-W5-002", auto_yes=True
            )
        assert rc == 1
        mock_claim.assert_not_called()

    def test_h7_s5_skip_verify_bypasses(self, capsys):
        """H7：--skip-verify → 不跑 subprocess，直接 claim。"""
        lifecycle = self._lifecycle()
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications"
            ) as mock_collect, \
            patch(
                "ticket_system.commands.lifecycle.run_all_verifications"
            ) as mock_run:
            rc = lifecycle.claim_with_verification(
                "0.18.0-W5-002", skip_verify=True
            )
        assert rc == 0
        mock_claim.assert_called_once()
        mock_collect.assert_not_called()
        mock_run.assert_not_called()
        captured = capsys.readouterr()
        assert "已跳過" in captured.out

    def test_h8_s6_keyboard_interrupt_returns_130(self, capsys):
        """H8：S6 Ctrl-C → stderr 訊息 + return 130。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        with patch.object(lifecycle, "claim") as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                side_effect=KeyboardInterrupt(),
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 130
        mock_claim.assert_not_called()
        captured = capsys.readouterr()
        assert "中斷" in captured.err

    def test_h9_s7_timeout_continues_to_prompt(self):
        """H9：S7 某 AC timeout → 標 timeout，進 prompt 詢問。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        timeout_result = VerificationResult(
            ac=_make_ac(0),
            status="timeout",
            template_name="npm_test_pass",
            message="exceeded 300s",
            exit_code=None,
        )
        # timeout 並入 unverifiable 計數；若無 passed 無 failed → none_verifiable
        # 為測試「進 prompt」路徑，加一個 failed 結果確保 has_failures
        failing = _make_failing_result(1)
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=[timeout_result, failing],
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True), patch(
                "builtins.input", return_value="y"
            ):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 0
        mock_claim.assert_called_once()

    def test_h10_flag1_skip_plus_yes_warns(self, capsys):
        """H10：P2-flag1 --skip-verify + --yes → stderr warning + 跳過 + return 0。"""
        lifecycle = self._lifecycle()
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim:
            rc = lifecycle.claim_with_verification(
                "0.18.0-W5-002", skip_verify=True, auto_yes=True
            )
        assert rc == 0
        mock_claim.assert_called_once()
        captured = capsys.readouterr()
        assert "--yes 已被忽略" in captured.err
        assert "已跳過" in captured.out

    def test_h11_flag2_only_skip_no_warning(self, capsys):
        """H11：P2-flag2 僅 --skip-verify → stderr 無 warning。"""
        lifecycle = self._lifecycle()
        with patch.object(lifecycle, "claim", return_value=0):
            lifecycle.claim_with_verification(
                "0.18.0-W5-002", skip_verify=True, auto_yes=False
            )
        captured = capsys.readouterr()
        assert "--yes 已被忽略" not in captured.err

    def test_h12_flag3_only_yes_no_warning(self, capsys):
        """H12：P2-flag3 僅 --yes → stderr 無 flag 衝突 warning。"""
        lifecycle = self._lifecycle()
        pairs = [(_make_ac(0), _make_vc())]
        results = [_make_failing_result(0)]
        with patch.object(lifecycle, "claim", return_value=0), \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                return_value=pairs,
            ), patch(
                "ticket_system.commands.lifecycle.run_all_verifications",
                return_value=results,
            ), patch(
                "ticket_system.commands.lifecycle.resolve_project_cwd",
                return_value="/fake",
            ), patch("sys.stdin.isatty", return_value=True):
            lifecycle.claim_with_verification(
                "0.18.0-W5-002", skip_verify=False, auto_yes=True
            )
        captured = capsys.readouterr()
        assert "--yes 已被忽略" not in captured.err


# ======================================================================
# Group K：錯誤處理邊界（K2/K3；K1 已在 test_claim_verification.py test_e6 覆蓋）
# ======================================================================


class TestErrorBoundaries:
    """Group K：錯誤處理邊界。"""

    def test_k2_parse_ac_value_error_degrades_to_direct_claim(self, capsys):
        """K2：collect_ac_verifications 拋 ValueError → stderr warning + 降級直接 claim。"""
        lifecycle = TicketLifecycle(version="0.18.0")
        with patch.object(lifecycle, "claim", return_value=0) as mock_claim, \
            patch(
                "ticket_system.commands.lifecycle.collect_ac_verifications",
                side_effect=ValueError("YAML 損毀"),
            ), patch("sys.stdin.isatty", return_value=True):
            rc = lifecycle.claim_with_verification("0.18.0-W5-002")
        assert rc == 0
        mock_claim.assert_called_once()
        captured = capsys.readouterr()
        assert "AC 解析失敗" in captured.err

    def test_k3_non_tty_without_flags_rejects(self, capsys):
        """K3：非 tty 無 --yes 無 --skip-verify → stderr 警告 + return 1。"""
        lifecycle = TicketLifecycle(version="0.18.0")
        with patch.object(lifecycle, "claim") as mock_claim, patch(
            "sys.stdin.isatty", return_value=False
        ):
            rc = lifecycle.claim_with_verification(
                "0.18.0-W5-002", skip_verify=False, auto_yes=False
            )
        assert rc == 1
        mock_claim.assert_not_called()
        captured = capsys.readouterr()
        assert "非互動" in captured.err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
