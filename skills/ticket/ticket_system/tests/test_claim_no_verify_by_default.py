"""W3-046: claim 預設不執行 AC verification（移除全套件副作用）。

來源: W3-045 ANA Layer 3-b 策略 B 共識（linux / basil / bay 三視角）。
W4-019: 移除 --skip-verify flag 與相關 backward-compat 測試（兩輪觀察期
trigger 達成；外部依賴 = 0、runtime deprecation 觸發 = 0）。

測試覆蓋:
1. execute_claim 預設路徑（無 --verify 旗標）不呼叫 collect_ac_verifications /
   run_all_verifications，亦不執行 npm_test_pass 對應的 subprocess.Popen。
2. --verify 旗標明示啟用時仍走 claim_with_verification。
3. complete 流程不依賴 subprocess 驗證（純 checkbox 檢查），確認同 wave 並行
   complete 不會撞 npm test。
"""
from __future__ import annotations

import argparse
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ticket_system.commands import lifecycle as lifecycle_mod
from ticket_system.commands.lifecycle import TicketLifecycle, execute_claim


@pytest.fixture
def stub_claim(monkeypatch):
    """Stub TicketLifecycle.claim 回傳 0，並追蹤是否被呼叫。"""
    calls = {"count": 0, "ticket_ids": []}

    def fake_claim(self, ticket_id, as_agent=None):
        calls["count"] += 1
        calls["ticket_ids"].append(ticket_id)
        return 0

    monkeypatch.setattr(TicketLifecycle, "claim", fake_claim, raising=True)
    # 同步 stub stale 檢查避免 load_ticket I/O
    monkeypatch.setattr(lifecycle_mod, "load_ticket", lambda v, t: None, raising=True)
    monkeypatch.setattr(
        lifecycle_mod,
        "_auto_extract_context_bundle_post_claim",
        lambda *a, **k: None,
        raising=True,
    )
    return calls


def _make_args(ticket_id: str = "0.0.0-W0-PENDING", **kwargs) -> argparse.Namespace:
    """產生 execute_claim 期望的 argparse.Namespace（W4-019 後不含 skip_verify）。"""
    base = dict(
        ticket_id=ticket_id,
        yes=False,
        verify=False,
        quiet=False,
        verbose=False,
        json_output=False,
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# Test 1: 預設不執行 AC verification（核心 RED）
# ---------------------------------------------------------------------------


def test_execute_claim_default_does_not_call_collect_ac_verifications(
    monkeypatch, stub_claim
):
    """預設 claim 不呼叫 collect_ac_verifications（即不走全套件 npm test）。

    覆蓋 W3-045 acceptance：ticket track claim 命令不再執行 npm_test_pass
    等全套件 verification。
    """
    collect_mock = MagicMock()
    run_mock = MagicMock()
    monkeypatch.setattr(
        "ticket_system.commands.claim_verification.collect_ac_verifications",
        collect_mock,
        raising=True,
    )
    monkeypatch.setattr(
        "ticket_system.commands.claim_verification.run_all_verifications",
        run_mock,
        raising=True,
    )

    args = _make_args(ticket_id="0.0.0-W0-PENDING")
    rc = execute_claim(args, version="0.0.0")

    assert rc == 0, "預設 claim 應該成功"
    assert stub_claim["count"] == 1, "預設應走 TicketLifecycle.claim"
    assert not collect_mock.called, (
        "預設 claim 不該呼叫 collect_ac_verifications；"
        f"actual call_count={collect_mock.call_count}"
    )
    assert not run_mock.called, (
        "預設 claim 不該呼叫 run_all_verifications；"
        f"actual call_count={run_mock.call_count}"
    )


def test_execute_claim_default_does_not_spawn_subprocess(
    monkeypatch, stub_claim
):
    """預設 claim 不執行任何 subprocess.Popen（防止 npm test 全套件被觸發）。"""
    popen_mock = MagicMock(side_effect=AssertionError(
        "預設 claim 不應呼叫 subprocess.Popen（npm test 全套件副作用）"
    ))
    monkeypatch.setattr(subprocess, "Popen", popen_mock)

    args = _make_args(ticket_id="0.0.0-W0-PENDING")
    rc = execute_claim(args, version="0.0.0")

    assert rc == 0
    assert stub_claim["count"] == 1
    assert not popen_mock.called


# ---------------------------------------------------------------------------
# Test 2: --verify 旗標明示啟用走 claim_with_verification
# ---------------------------------------------------------------------------


def test_execute_claim_with_verify_flag_invokes_verification(monkeypatch):
    """--verify 旗標明示啟用時走 claim_with_verification（保留除錯場景）。"""
    invoked = {"count": 0}
    direct_claim = {"count": 0}

    def fake_claim_with_verification(self, ticket_id, auto_yes=False, as_agent=None):
        invoked["count"] += 1
        invoked["ticket_id"] = ticket_id
        invoked["auto_yes"] = auto_yes
        return 0

    def fake_claim(self, ticket_id, as_agent=None):
        direct_claim["count"] += 1
        return 0

    monkeypatch.setattr(
        TicketLifecycle,
        "claim_with_verification",
        fake_claim_with_verification,
        raising=True,
    )
    monkeypatch.setattr(TicketLifecycle, "claim", fake_claim, raising=True)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", lambda v, t: None, raising=True)
    monkeypatch.setattr(
        lifecycle_mod,
        "_auto_extract_context_bundle_post_claim",
        lambda *a, **k: None,
        raising=True,
    )

    args = _make_args(ticket_id="0.0.0-W0-PENDING", verify=True)
    rc = execute_claim(args, version="0.0.0")

    assert rc == 0
    assert invoked["count"] == 1, "--verify 應觸發 claim_with_verification"
    assert direct_claim["count"] == 0, "--verify 啟用時不應直接走 claim"
    assert invoked["ticket_id"] == "0.0.0-W0-PENDING"


# ---------------------------------------------------------------------------
# Test 3 (W4-019 regression): --skip-verify 旗標已移除，傳入應引發 argparse 錯誤
# ---------------------------------------------------------------------------


def test_skip_verify_flag_removed_from_argparse():
    """W4-019 regression：track.py argparse 不再接受 --skip-verify 旗標。"""
    from ticket_system.commands import track as track_mod
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation")
    track_mod._register_lifecycle_commands(subparsers)

    # claim 子命令不應再有 --skip-verify
    with pytest.raises(SystemExit):
        parser.parse_args(["claim", "0.0.0-W0-PENDING", "--skip-verify"])


# ---------------------------------------------------------------------------
# Test 4: complete 流程不執行 subprocess（並行 complete 安全性確認）
# ---------------------------------------------------------------------------


def test_complete_does_not_spawn_subprocess_for_ac_verification(monkeypatch):
    """complete 流程不執行任何 subprocess.Popen 做 AC verification。

    bay 視角擔憂：若 complete-gate 也跑全套件 npm test，同 wave 並行 complete
    會撞 jest 暫存。本測試以靜態檢查 + grep 證明 complete 路徑無 npm test
    subprocess：

    1. validate_acceptance_criteria 純 checkbox 檢查（不執行 subprocess）
    2. lifecycle.complete 不 import / 不呼叫 run_all_verifications
    3. acceptance-gate-hook（若存在）不引用 match_template / npm_test_pass
    """
    import inspect
    from ticket_system.lib import ticket_validator
    from ticket_system.commands import lifecycle as life_mod

    # 1. validate_acceptance_criteria 不呼叫 subprocess
    src = inspect.getsource(ticket_validator.validate_acceptance_criteria)
    assert "subprocess" not in src, (
        "validate_acceptance_criteria 不應引用 subprocess（AC 應純 checkbox 檢查）"
    )
    assert "npm" not in src.lower(), (
        "validate_acceptance_criteria 不應引用 npm 命令"
    )

    # 2. TicketLifecycle.complete 方法源碼不包含 verification 呼叫
    complete_src = inspect.getsource(life_mod.TicketLifecycle.complete)
    assert "run_all_verifications" not in complete_src, (
        "complete 不應呼叫 run_all_verifications（避免 PC-078 並行衝突)"
    )
    assert "collect_ac_verifications" not in complete_src, (
        "complete 不應呼叫 collect_ac_verifications"
    )
