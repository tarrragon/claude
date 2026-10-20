"""track_batch.py 批次認領/完成路徑的 registry lease 接線測試（0.2.1-W3-779）。

驗證重點：`_execute_batch_operation` 逐票成功分支必須併同呼叫
`claim_lease`（operation=claim）或 `release_lease`（operation=complete），
使批次路徑與單票路徑（見 test_track_lease_wiring.py）的 registry 狀態一致：

- 部分失敗時只有成功的票觸發 lease 呼叫（與 frontmatter 實況一致）。
- `_process_batch_complete` 對 `is_already_complete` 回傳成功時，仍須呼叫
  `release_lease`（冪等移除，非跳過）。
- lease 呼叫拋錯不得使該票由成功翻為失敗，也不得中斷整批迴圈。

全數以 monkeypatch 重導 track_batch 模組內已綁定的 `claim_lease` /
`release_lease` 名稱，不觸碰真實 ticket 檔案或 registry。
"""

from __future__ import annotations

from argparse import Namespace

from ticket_system.commands import track_batch


def _args(ticket_ids: str) -> Namespace:
    return Namespace(ticket_ids=ticket_ids)


def _ticket(status: str, **overrides) -> dict:
    base = {"id": "dummy", "status": status, "assigned": False}
    base.update(overrides)
    return base


class TestBatchClaimLeaseWiring:
    def test_success_triggers_claim_lease_per_ticket(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            track_batch, "claim_lease",
            lambda version, ticket_id: calls.append((version, ticket_id)),
        )
        tickets = {
            "0.0.0-W1-001": _ticket("pending"),
            "0.0.0-W1-002": _ticket("pending"),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)

        rc = track_batch.execute_batch_claim(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        assert calls == [
            ("0.0.0", "0.0.0-W1-001"),
            ("0.0.0", "0.0.0-W1-002"),
        ]

    def test_partial_failure_only_registers_succeeded_ticket(self, monkeypatch):
        """acceptance 第 3 條：部分失敗時，只有成功票觸發 lease 寫入。"""
        calls = []
        monkeypatch.setattr(
            track_batch, "claim_lease",
            lambda version, ticket_id: calls.append((version, ticket_id)),
        )
        tickets = {
            "0.0.0-W1-001": _ticket("pending"),
            "0.0.0-W1-002": _ticket("in_progress"),  # 不可認領 -> 失敗分支
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)

        rc = track_batch.execute_batch_claim(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_lease_error_does_not_flip_success_or_abort_loop(self, monkeypatch, capsys):
        """claim_lease 拋錯不得讓該票由成功翻為失敗，也不得中斷整批迴圈
        （批次路徑刻意攔截，與單票路徑的裸呼叫不對稱，見 track_batch.py
        註解）。降級訊息走 stderr 且含例外型別名稱。"""
        calls = []

        def _raising_claim_lease(version, ticket_id):
            calls.append(ticket_id)
            if ticket_id == "0.0.0-W1-001":
                raise RuntimeError("registry 不可用")

        monkeypatch.setattr(track_batch, "claim_lease", _raising_claim_lease)
        tickets = {
            "0.0.0-W1-001": _ticket("pending"),
            "0.0.0-W1-002": _ticket("pending"),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)

        rc = track_batch.execute_batch_claim(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        # 兩票都嘗試呼叫 claim_lease（迴圈未中斷），且兩票皆計為成功
        assert calls == ["0.0.0-W1-001", "0.0.0-W1-002"]
        captured = capsys.readouterr()
        assert "0.0.0-W1-001" in captured.err
        assert "RuntimeError" in captured.err
        assert "registry 與 frontmatter 暫不同步" in captured.err


class TestBatchCompleteLeaseWiring:
    def test_success_triggers_release_lease_per_ticket(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            track_batch, "release_lease",
            lambda version, ticket_id: calls.append((version, ticket_id)),
        )
        tickets = {
            "0.0.0-W1-001": _ticket("in_progress", acceptance=[]),
            "0.0.0-W1-002": _ticket("in_progress", acceptance=[]),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)
        monkeypatch.setattr(track_batch, "append_worklog_progress", lambda v, tid, title: None)

        rc = track_batch.execute_batch_complete(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        assert calls == [
            ("0.0.0", "0.0.0-W1-001"),
            ("0.0.0", "0.0.0-W1-002"),
        ]

    def test_already_complete_skip_still_releases_lease(self, monkeypatch):
        """`is_already_complete` skip 分支仍需呼叫 release_lease（冪等移除，
        非跳過語意，Problem Analysis「兩個需明確處置的邊界」固定此行為）。"""
        calls = []
        monkeypatch.setattr(
            track_batch, "release_lease",
            lambda version, ticket_id: calls.append((version, ticket_id)),
        )
        tickets = {
            "0.0.0-W1-001": _ticket(
                "completed", acceptance=[], completed_at="2026-01-01T00:00:00"
            ),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)
        monkeypatch.setattr(track_batch, "append_worklog_progress", lambda v, tid, title: None)

        rc = track_batch.execute_batch_complete(_args("0.0.0-W1-001"), "0.0.0")

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_partial_failure_only_releases_succeeded_ticket(self, monkeypatch):
        """acceptance 第 3 條：部分失敗（驗收條件未完成）時，只有成功票觸發
        release_lease。"""
        calls = []
        monkeypatch.setattr(
            track_batch, "release_lease",
            lambda version, ticket_id: calls.append((version, ticket_id)),
        )
        tickets = {
            "0.0.0-W1-001": _ticket("in_progress", acceptance=[]),
            "0.0.0-W1-002": _ticket("in_progress", acceptance=["[ ] 未完成項目"]),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)
        monkeypatch.setattr(track_batch, "append_worklog_progress", lambda v, tid, title: None)

        rc = track_batch.execute_batch_complete(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        assert calls == [("0.0.0", "0.0.0-W1-001")]

    def test_lease_error_does_not_flip_success_or_abort_loop(self, monkeypatch, capsys):
        """release_lease 拋錯不得讓該票由成功翻為失敗，也不得中斷整批迴圈。
        降級訊息走 stderr 且含例外型別名稱。"""
        calls = []

        def _raising_release_lease(version, ticket_id):
            calls.append(ticket_id)
            if ticket_id == "0.0.0-W1-001":
                raise RuntimeError("registry 不可用")

        monkeypatch.setattr(track_batch, "release_lease", _raising_release_lease)
        tickets = {
            "0.0.0-W1-001": _ticket("in_progress", acceptance=[]),
            "0.0.0-W1-002": _ticket("in_progress", acceptance=[]),
        }
        monkeypatch.setattr(
            track_batch, "load_and_validate_ticket",
            lambda version, ticket_id, auto_print_error=False: (tickets[ticket_id], None),
        )
        monkeypatch.setattr(track_batch, "resolve_ticket_path", lambda t, v, tid: f"/tmp/{tid}.md")
        monkeypatch.setattr(track_batch, "save_ticket", lambda t, p: None)
        monkeypatch.setattr(track_batch, "append_worklog_progress", lambda v, tid, title: None)

        rc = track_batch.execute_batch_complete(
            _args("0.0.0-W1-001,0.0.0-W1-002"), "0.0.0"
        )

        assert rc == 0
        assert calls == ["0.0.0-W1-001", "0.0.0-W1-002"]
        captured = capsys.readouterr()
        assert "0.0.0-W1-001" in captured.err
        assert "RuntimeError" in captured.err
        assert "registry 與 frontmatter 暫不同步" in captured.err
