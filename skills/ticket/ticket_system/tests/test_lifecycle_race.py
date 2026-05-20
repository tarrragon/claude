"""Phase 2 RED — lifecycle.py claim race regression test (W14-044).

對應 ticket 0.18.0-W14-044：lifecycle.py 4 處 (claim/complete/release/close)
load → modify → save 序列需 file_lock 保護。

設計：
-----
claim 的 race 語意不同於 update_parent_children 的 lost-update（list append）。
claim 是 status transition：pending → in_progress，期望「恰好一個 claimant 成功」。

無 lock 時，N 個並發 claimant 可能：
- 全部 load 到 status=pending
- 全部通過 validate_claimable_status
- 全部執行 save，最後寫者的 started_at 覆蓋前面所有人

預期觀察：未鎖時 successful_count > 1（lost-update of status check）。
有鎖時：恰好 1 個 claimant 觀察 status=pending 並 save 成功；其餘觀察
status=in_progress 並回傳 1。
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Tuple

import pytest

from ticket_system.lib import parser, ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture(scope="module", autouse=True)
def _force_fork_mode():
    """macOS Python 3.13 預設 spawn，顯式切回 fork 以共享 monkeypatch state。"""
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    current = mp.get_start_method()
    assert current == "fork", (
        f"fork mode required; current={current!r}. "
        f"spawn 模式下 monkeypatch 不傳遞至 child，會 false GREEN"
    )


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_pending_ticket(path: Path, tid: str) -> None:
    """最小合法 ticket，status=pending，可被 claim。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: race target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "acceptance: []",
        "tdd_phase: ''",
        "children: []",
        "blockedBy: []",
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def pending_ticket(tmp_ticket_dir: Path) -> Tuple[str, Path]:
    tid = "0.0.0-W0-CLAIMRACE"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid)
    return tid, path


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 lifecycle 內部的 get_ticket_path / load_ticket 至 tmp dir。

    lifecycle.py 透過 `from ticket_system.lib.ticket_loader import ...` 引入；
    monkeypatch 必須對 ticket_loader 模組命名空間 + lifecycle 模組命名空間都
    patch（lifecycle 內已用名稱直接引用）。
    """
    from ticket_system.commands import lifecycle as lifecycle_mod

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    # ticket_loader 模組（save_ticket 內部會用 _path）
    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)
    # lifecycle 模組命名空間（from ... import 已綁定）
    monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    # ticket_ops.load_and_validate_ticket 內部用 load_ticket → 同樣需 patch
    from ticket_system.lib import ticket_ops
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)


# ============================================================
# Worker（module top-level；fork 繼承 patch）
# ============================================================

def _worker_claim(args):
    """並發呼叫 TicketLifecycle.claim。回傳 exit code。"""
    version, ticket_id = args
    # 抑制子 process 的 stdout（避免測試輸出污染）
    import io
    import sys
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.commands.lifecycle import TicketLifecycle
        lifecycle = TicketLifecycle(version)
        return lifecycle.claim(ticket_id)
    finally:
        sys.stdout = saved


# ============================================================
# Tests
# ============================================================

class TestClaimRace:
    """N 並發 claim → 恰好 1 個成功（exit=0），其餘失敗（exit=1）。"""

    def test_concurrent_claim_exactly_one_winner(
        self, pending_ticket, patch_ticket_paths
    ):
        ticket_id, ticket_path = pending_ticket
        N = 10
        N_ROUNDS = 3

        winners_per_round = []
        for round_idx in range(N_ROUNDS):
            # 每輪重置 ticket 為 pending
            _write_pending_ticket(ticket_path, ticket_id)
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            args = [("0.0.0", ticket_id)] * N
            with mp.Pool(N) as pool:
                results = pool.map(_worker_claim, args)

            winners = sum(1 for r in results if r == 0)
            winners_per_round.append(winners)

            # 最終檔案狀態必為 in_progress
            content = ticket_path.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            assert fm.get("status") == "in_progress", (
                f"round {round_idx}: final status={fm.get('status')!r}, "
                f"exit codes={results}"
            )

        # 核心斷言：每輪恰好 1 個 winner（無 lock 時可能 > 1）
        assert all(w == 1 for w in winners_per_round), (
            f"claim race: expected exactly 1 winner per round, "
            f"got winners_per_round={winners_per_round}. "
            f"> 1 表示多個 claimant 同時通過 status=pending check "
            f"並 save（lost-update of status transition）"
        )
