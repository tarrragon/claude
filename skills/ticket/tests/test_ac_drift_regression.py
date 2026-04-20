"""W3-001 原始觸發案例 AC 漂移回歸測試（0.18.0-W11-001.4）。

背景（PC-055 / PROP-010）:
    W3-001「修復整合測試 + flaky test 清理」建立於 2026-04-03，pending 期間
    （9 天）AC 已由上游 Ticket（W1-002 / W2-001 / W3-006）外溢達成。
    2026-04-12 claim 時，若無 AC 自動驗證 + stale 警告機制，PM 無從得知 AC
    已達成，可能誤派代理人執行已完成的任務。

本回歸測試模擬該情境，驗證 W11-001.1 的 claim 前 AC 驗證 + W11-001.2 的
stale 警告可以協力偵測並阻擋 claim：

1. Stale INFO 警告（created 為 9 天前，INFO 閾值 7 天）
2. AC 已達成提示（all_passed → S4 拒絕 claim）
3. claim 被拒絕（exit code 1，而非繼續執行）

備註：Ticket AC 原寫「提供 y/n/c 三選一」，但目前實作在 all_passed（S4）
情境會直接拒絕 claim 並建議 `ticket track complete`，不會進入互動 prompt
（S4 在 prompt 之前就回 1，見 claim_with_verification §S4）。本測試依實作
現況驗證「拒絕 + 建議訊息」，比原始 AC 更嚴格（完全不給 claim 機會）。
三選一設計若未來實作，應擴充本測試。
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from ticket_system.commands.lifecycle import execute_claim
from ticket_system.lib.ac_parser import AC
from ticket_system.lib.validation_templates import ValidationCommand
from ticket_system.lib.verification_result import VerificationResult


# W3-001 原始情境常數
_W3_001_ID = "0.18.0-W3-001"
_W3_001_AGE_DAYS = 9  # 2026-04-03 建立 → 2026-04-12 claim
_STALE_INFO_THRESHOLD = 7


def _w3_001_ticket_fixture() -> dict:
    """模擬 W3-001 Ticket frontmatter（pending 狀態，9 天前建立）。"""
    created = (date.today() - timedelta(days=_W3_001_AGE_DAYS)).isoformat()
    return {
        "id": _W3_001_ID,
        "title": "修復 整合測試 + flaky test 清理",
        "status": "pending",
        "type": "IMP",
        "version": "0.18.0",
        "wave": 3,
        "created": created,
        "acceptance": [
            "[ ] 整合測試全部通過",
            "[ ] flaky test 已修復或標記原因",
            "[ ] 無不穩定測試",
        ],
    }


def _make_passed_ac_result(index: int, text: str) -> VerificationResult:
    """模擬「測試已通過」驗證結果（模擬 W3-001 AC 已由上游外溢達成）。"""
    return VerificationResult(
        ac=AC(index=index, text=text, checked=False, raw=f"[ ] {text}"),
        status="passed",
        template_name="npm_test_pass",
        message="634 passed, 0 failed",
        exit_code=0,
    )


def _all_passed_pairs_and_results() -> tuple[list, list]:
    """組出 W3-001 三個 AC 皆 passed 的 pairs + results（all_passed summary）。"""
    acs_text = [
        "整合測試全部通過",
        "flaky test 已修復或標記原因",
        "無不穩定測試",
    ]
    vc = ValidationCommand(
        template_name="npm_test_pass",
        command="npm run test:integration 2>&1 | tail -5",
        timeout_sec=300,
        parse_strategy="tail_lines",
        is_verifiable=True,
        unverifiable_reason=None,
    )
    pairs = [
        (AC(index=i, text=t, checked=False, raw=f"[ ] {t}"), vc)
        for i, t in enumerate(acs_text)
    ]
    results = [_make_passed_ac_result(i, t) for i, t in enumerate(acs_text)]
    return pairs, results


class TestW3_001RegressionACDrift:
    """W3-001 原始觸發案例回歸測試（PROP-010 / PC-055 防護驗證）。"""

    def _claim_args(self) -> argparse.Namespace:
        return argparse.Namespace(
            ticket_id=_W3_001_ID,
            skip_verify=False,
            yes=False,
        )

    def test_regression_stale_info_warning_emitted(self, capsys):
        """回歸 1：9 天前建立的 Ticket claim 時應輸出 stale INFO 警告。

        驗證 W11-001.2（stale 警告機制）在此情境啟動。
        """
        ticket = _w3_001_ticket_fixture()
        pairs, results = _all_passed_pairs_and_results()

        with patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value=ticket,
        ), patch(
            "ticket_system.commands.lifecycle.collect_ac_verifications",
            return_value=pairs,
        ), patch(
            "ticket_system.commands.lifecycle.run_all_verifications",
            return_value=results,
        ), patch(
            "ticket_system.commands.lifecycle.resolve_project_cwd",
            return_value="/fake",
        ), patch("sys.stdin.isatty", return_value=True):
            execute_claim(self._claim_args(), version="0.18.0")

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # Stale INFO 標記 + 天數提示（>= 7 天閾值）
        assert "[INFO]" in combined, "應輸出 stale INFO 警告（9 天 >= 7 天閾值）"
        assert _W3_001_ID in combined, "stale 警告應含 Ticket ID"
        assert f">= {_STALE_INFO_THRESHOLD} 天" in combined, (
            "stale 警告應標示 INFO 閾值"
        )

    def test_regression_ac_achieved_message_emitted(self, capsys):
        """回歸 2：AC 已達成（all_passed）應輸出拒絕訊息 + 建議 complete。

        驗證 W11-001.1（claim 前 AC 驗證 S4 all_passed）在此情境啟動。
        """
        ticket = _w3_001_ticket_fixture()
        pairs, results = _all_passed_pairs_and_results()

        with patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value=ticket,
        ), patch(
            "ticket_system.commands.lifecycle.collect_ac_verifications",
            return_value=pairs,
        ), patch(
            "ticket_system.commands.lifecycle.run_all_verifications",
            return_value=results,
        ), patch(
            "ticket_system.commands.lifecycle.resolve_project_cwd",
            return_value="/fake",
        ), patch("sys.stdin.isatty", return_value=True):
            execute_claim(self._claim_args(), version="0.18.0")

        captured = capsys.readouterr()
        # AC 已達成提示輸出到 stderr（見 claim_with_verification S4）
        assert "已達成" in captured.err, "應輸出 AC 已達成提示"
        assert "complete" in captured.err, "應建議使用 ticket track complete"

    def test_regression_claim_rejected_exit_code_one(self):
        """回歸 3：AC 已達成 + stale 情境下，claim 應被拒絕（exit code 1）。

        這是 W3-001 觸發案例的核心保護：避免派發代理人執行已完成的任務。
        PROP-010 驗證標準 — 觸發案例不再發生。
        """
        ticket = _w3_001_ticket_fixture()
        pairs, results = _all_passed_pairs_and_results()

        with patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value=ticket,
        ), patch(
            "ticket_system.commands.lifecycle.collect_ac_verifications",
            return_value=pairs,
        ), patch(
            "ticket_system.commands.lifecycle.run_all_verifications",
            return_value=results,
        ), patch(
            "ticket_system.commands.lifecycle.resolve_project_cwd",
            return_value="/fake",
        ), patch("sys.stdin.isatty", return_value=True):
            rc = execute_claim(self._claim_args(), version="0.18.0")

        assert rc == 1, "W3-001 觸發案例應被拒絕 claim（exit code 1）"

    def test_regression_all_three_signals_co_occur(self, capsys):
        """回歸 4：綜合驗證 — 三個防護訊號同時出現（stale + AC 達成 + 拒絕）。

        驗證 W11-001.1 + W11-001.2 協力運作，完整阻擋 W3-001 類型觸發案例。
        """
        ticket = _w3_001_ticket_fixture()
        pairs, results = _all_passed_pairs_and_results()

        with patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value=ticket,
        ), patch(
            "ticket_system.commands.lifecycle.collect_ac_verifications",
            return_value=pairs,
        ), patch(
            "ticket_system.commands.lifecycle.run_all_verifications",
            return_value=results,
        ), patch(
            "ticket_system.commands.lifecycle.resolve_project_cwd",
            return_value="/fake",
        ), patch("sys.stdin.isatty", return_value=True):
            rc = execute_claim(self._claim_args(), version="0.18.0")

        captured = capsys.readouterr()
        combined = captured.out + captured.err

        # 三訊號同時出現
        assert "[INFO]" in combined, "訊號 1：stale INFO 警告"
        assert "已達成" in captured.err, "訊號 2：AC 已達成提示"
        assert rc == 1, "訊號 3：claim 被拒絕（exit code 1）"
