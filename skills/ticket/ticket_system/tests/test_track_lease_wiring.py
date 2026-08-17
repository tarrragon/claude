"""track.py 生命週期指令與 lease 寫入端的接線測試（multi-PM 協調層 Phase 3）。

驗證重點：claim/complete/release 成功（rc==0）時併同呼叫 lease.py 對應函式；
失敗（rc!=0）時不呼叫，避免對未實際發生的狀態轉換寫入 lease。reclaim 則
驗證薄包裝層正確轉發 ticket_id / confirm 給 `lease.reclaim_ticket`。release
另驗證前置閘門（`check_release_guard`）：非自身 FRESH lease 持有時阻擋，
`--force-release-others` 旗標旁路且不觸發閘門查詢。

全數以 monkeypatch 重導 track 模組內已綁定的名稱（`execute_claim` /
`execute_complete` / `execute_release` / `claim_lease` / `release_lease` /
`check_release_guard` / `reclaim_ticket`），不觸碰真實 ticket 檔案或
registry。
"""

from __future__ import annotations

import argparse
from argparse import Namespace

from ticket_system.commands import track


def _args(**kwargs) -> Namespace:
    return Namespace(**kwargs)


class TestClaimWiring:
    def test_success_triggers_claim_lease(self, monkeypatch):
        calls = []
        monkeypatch.setattr(track, "execute_claim", lambda args, version: 0)
        monkeypatch.setattr(
            track, "claim_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_claim(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_failure_does_not_trigger_claim_lease(self, monkeypatch):
        calls = []
        monkeypatch.setattr(track, "execute_claim", lambda args, version: 1)
        monkeypatch.setattr(
            track, "claim_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_claim(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 1
        assert calls == []


class TestCompleteWiring:
    def test_success_triggers_release_lease(self, monkeypatch):
        calls = []
        # _execute_complete 內以 local import 呼叫 check_identity（W1-048 前置檢查），
        # 需 patch 其來源模組（非 track 模組綁定名稱，該函式為呼叫當下才 import）
        from ticket_system.lib import identity_guard
        monkeypatch.setattr(identity_guard, "check_identity", lambda *a, **k: None)
        monkeypatch.setattr(track, "execute_complete", lambda args, version: 0)
        monkeypatch.setattr(
            track, "release_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_complete(
            _args(ticket_id="0.0.0-W1-001", as_agent=None, operation="complete"), "0.0.0"
        )

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_failure_does_not_trigger_release_lease(self, monkeypatch):
        calls = []
        from ticket_system.lib import identity_guard
        monkeypatch.setattr(identity_guard, "check_identity", lambda *a, **k: None)
        monkeypatch.setattr(track, "execute_complete", lambda args, version: 1)
        monkeypatch.setattr(
            track, "release_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_complete(
            _args(ticket_id="0.0.0-W1-001", as_agent=None, operation="complete"), "0.0.0"
        )

        assert rc == 1
        assert calls == []


class TestReleaseWiring:
    def test_success_triggers_release_lease(self, monkeypatch):
        calls = []
        monkeypatch.setattr(track, "check_release_guard", lambda ticket_id: (True, "allowed"))
        monkeypatch.setattr(track, "execute_release", lambda args, version: 0)
        monkeypatch.setattr(
            track, "release_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_release(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_failure_does_not_trigger_release_lease(self, monkeypatch):
        calls = []
        monkeypatch.setattr(track, "check_release_guard", lambda ticket_id: (True, "allowed"))
        monkeypatch.setattr(track, "execute_release", lambda args, version: 1)
        monkeypatch.setattr(
            track, "release_lease", lambda version, ticket_id: calls.append((version, ticket_id))
        )

        rc = track._execute_release(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 1
        assert calls == []

    def test_other_fresh_owner_blocks_without_force_flag(self, monkeypatch):
        """閘門拒絕（allowed=False）時不呼叫 execute_release / release_lease，
        票面狀態與 lease 皆不受影響（0.2.1-W3-582 核心行為）。"""
        execute_calls = []
        release_lease_calls = []
        monkeypatch.setattr(
            track,
            "check_release_guard",
            lambda ticket_id: (False, f"{ticket_id} 由其他存活中的 session sess-B（FRESH）持有"),
        )
        monkeypatch.setattr(
            track, "execute_release",
            lambda args, version: execute_calls.append((args, version)) or 0,
        )
        monkeypatch.setattr(
            track, "release_lease",
            lambda version, ticket_id: release_lease_calls.append((version, ticket_id)),
        )

        rc = track._execute_release(
            _args(ticket_id="0.0.0-W1-001", force_release_others=False), "0.0.0"
        )

        assert rc == 1
        assert execute_calls == []
        assert release_lease_calls == []

    def test_force_flag_bypasses_guard_without_consulting_it(self, monkeypatch):
        """`--force-release-others` 旁路時，`check_release_guard` 完全不被
        呼叫（非僅忽略其結果）——確保旁路路徑不依賴閘門查詢是否可用。"""
        guard_calls = []
        release_lease_calls = []
        monkeypatch.setattr(
            track,
            "check_release_guard",
            lambda ticket_id: guard_calls.append(ticket_id) or (False, "should not be consulted"),
        )
        monkeypatch.setattr(track, "execute_release", lambda args, version: 0)
        monkeypatch.setattr(
            track, "release_lease",
            lambda version, ticket_id: release_lease_calls.append((version, ticket_id)),
        )

        rc = track._execute_release(
            _args(ticket_id="0.0.0-W1-001", force_release_others=True), "0.0.0"
        )

        assert rc == 0
        assert guard_calls == []
        assert release_lease_calls == [("0.0.0", "0.0.0-W1-001")]

    def test_missing_force_flag_attribute_defaults_to_guarded(self, monkeypatch):
        """Namespace 未帶 force_release_others 屬性（如既有未經新 CLI 解析的
        呼叫端）時 getattr 預設 False，閘門仍生效——回歸測試，確認新增旗標
        不破壞既有呼叫慣例（Never break userspace）。"""
        monkeypatch.setattr(track, "check_release_guard", lambda ticket_id: (True, "allowed"))
        monkeypatch.setattr(track, "execute_release", lambda args, version: 0)
        monkeypatch.setattr(track, "release_lease", lambda version, ticket_id: None)

        rc = track._execute_release(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 0


class TestReleaseForceFlagCliRegistration:
    """`--force-release-others` 旗標需經 `_register_lifecycle_commands` 正確
    註冊於 `release` 子命令，預設 False，可顯式傳入 True。"""

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        track._register_lifecycle_commands(subparsers)
        return parser

    def test_flag_defaults_to_false(self):
        parser = self._build_parser()

        args = parser.parse_args(["release", "0.0.0-W1-001"])

        assert args.force_release_others is False

    def test_flag_can_be_set_true(self):
        parser = self._build_parser()

        args = parser.parse_args(
            ["release", "0.0.0-W1-001", "--force-release-others"]
        )

        assert args.force_release_others is True


class TestReclaimWiring:
    def test_forwards_ticket_id_and_confirm_false_by_default(self, monkeypatch):
        captured = {}

        def _fake_reclaim(version, ticket_id, *, confirm):
            captured["version"] = version
            captured["ticket_id"] = ticket_id
            captured["confirm"] = confirm
            return 0

        monkeypatch.setattr(track, "reclaim_ticket", _fake_reclaim)

        rc = track._execute_reclaim(_args(ticket_id="0.0.0-W1-001"), "0.0.0")

        assert rc == 0
        assert captured == {"version": "0.0.0", "ticket_id": "0.0.0-W1-001", "confirm": False}

    def test_forwards_confirm_true(self, monkeypatch):
        captured = {}

        def _fake_reclaim(version, ticket_id, *, confirm):
            captured["confirm"] = confirm
            return 0

        monkeypatch.setattr(track, "reclaim_ticket", _fake_reclaim)

        track._execute_reclaim(_args(ticket_id="0.0.0-W1-001", confirm=True), "0.0.0")

        assert captured["confirm"] is True
