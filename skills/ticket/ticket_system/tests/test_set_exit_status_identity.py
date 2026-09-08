"""set-exit-status 身份檢查（Round 3 finding 3-F F3）。

set-exit-status 原無身份檢查，接手者可代填他人票的 Exit Status 章節，
製造 reclaim 鑑識三查第 3 查（Exit Status 存在）通過的假象。本檔驗證
新增的 --as／who.current 比對：未提供 --as 維持 warn-only（向後相容，
set-exit-status 非 ENFORCED_COMMANDS）；提供 --as 且與 who.current 不符
則 deny，不寫入 ticket；--force 不可用於旁路本身份檢查。
"""
from __future__ import annotations

import argparse
from unittest.mock import patch

from ticket_system.commands import track_structured_body
from ticket_system.lib import identity_guard


_TICKET_ID = "0.2.1-W3-999"
_VERSION = "0.2.1"


def _args(as_agent=None, force=False):
    return argparse.Namespace(
        ticket_id=_TICKET_ID,
        status="success",
        reason="",
        confidence="0.9",
        acceptance_met=None,
        acceptance_unmet=None,
        artifacts=None,
        force=force,
        as_agent=as_agent,
    )


class TestSetExitStatusIdentityCheck:
    def test_missing_as_still_warn_only_and_proceeds(self, tmp_path, monkeypatch):
        """未提供 --as：非 ENFORCED_COMMANDS，維持 warn-only 放行（向後
        相容，不因新增身份檢查而破壞既有未帶 --as 呼叫端）。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            track_structured_body, "_delegate_to_append_log", return_value=0
        ) as mock_delegate:
            rc = track_structured_body.execute_set_exit_status(_args(), _VERSION)
        assert rc == 0
        mock_delegate.assert_called_once()

    def test_as_matches_who_current_passes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            identity_guard, "load_ticket",
            return_value={"who": {"current": "thyme-python-developer"}},
        ), patch.object(
            track_structured_body, "_delegate_to_append_log", return_value=0
        ) as mock_delegate:
            rc = track_structured_body.execute_set_exit_status(
                _args(as_agent="thyme-python-developer"), _VERSION
            )
        assert rc == 0
        mock_delegate.assert_called_once()

    def test_as_mismatches_who_current_denies_without_writing(self, tmp_path, monkeypatch):
        """接手者以 --as 自己身份填寫他人票的 Exit Status：與 who.current
        不符即 deny，不落地寫入（3-F F3 核心修法）。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            identity_guard, "load_ticket",
            return_value={"who": {"current": "parsley-flutter-developer"}},
        ), patch.object(
            track_structured_body, "_delegate_to_append_log"
        ) as mock_delegate:
            rc = track_structured_body.execute_set_exit_status(
                _args(as_agent="thyme-python-developer"), _VERSION
            )
        assert rc != 0
        mock_delegate.assert_not_called()

    def test_force_flag_does_not_bypass_identity_check(self, tmp_path, monkeypatch):
        """--force 僅旁路委派寫入時的 status precondition，不可用於旁路
        身份不符（3-F F3：舊行為下缺身份檢查使 --force 間接旁路整個
        precondition 鏈；新檢查獨立於 --force，仍須擋下）。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            identity_guard, "load_ticket",
            return_value={"who": {"current": "parsley-flutter-developer"}},
        ), patch.object(
            track_structured_body, "_delegate_to_append_log"
        ) as mock_delegate:
            rc = track_structured_body.execute_set_exit_status(
                _args(as_agent="thyme-python-developer", force=True), _VERSION
            )
        assert rc != 0
        mock_delegate.assert_not_called()

    def test_pm_agent_exempt(self, tmp_path, monkeypatch):
        """PM bookkeeping 豁免（identity_guard 既有情境 2），set-exit-status
        直接複用 check_identity，不重造豁免邏輯。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            track_structured_body, "_delegate_to_append_log", return_value=0
        ) as mock_delegate:
            rc = track_structured_body.execute_set_exit_status(
                _args(as_agent=identity_guard.PM_AGENT_NAME), _VERSION
            )
        assert rc == 0
        mock_delegate.assert_called_once()
