"""W14-045 — commands/{fields,track_acceptance,track_relations,track_set_acceptance}.py
race regression tests.

涵蓋四個 caller 的 load→modify→save 序列在多 process 並發下的正確性。
模式參考 test_lifecycle_race.py（fork mode + monkeypatch ticket paths）。

無 lock 時 list-append 類序列會發生 lost update（W14-005 重現確認同類 pattern
lost rate 55.6%~71.9%）；有 lock 時 N 並發呼叫應達成完整保留所有變更（無 lost）。
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Tuple

import pytest

from ticket_system.lib import parser, ticket_loader
from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# Fixtures
# ============================================================

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


def _write_ticket(path: Path, tid: str, *, acceptance: list[str] | None = None,
                  spawned: list[str] | None = None,
                  blocked_by: list[str] | None = None) -> None:
    """寫入最小合法 ticket（含可選 acceptance/spawned_tickets/blockedBy）。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: race target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "tdd_phase: phase1",
        "children: []",
    ]
    if blocked_by is None:
        blocked_by = []
    lines.append("blockedBy: " + ("[]" if not blocked_by else ""))
    for bid in blocked_by:
        lines.append(f"- {bid}")
    if acceptance is None:
        acceptance = []
    if not acceptance:
        lines.append("acceptance: []")
    else:
        lines.append("acceptance:")
        for item in acceptance:
            lines.append(f"- '{item}'")
    if spawned is None:
        spawned = []
    if not spawned:
        lines.append("spawned_tickets: []")
    else:
        lines.append("spawned_tickets:")
        for sid in spawned:
            lines.append(f"- {sid}")
    lines += ["---", "", "body"]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 ticket_loader / ticket_ops / commands 內部的 path 解析至 tmp dir。"""

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

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)

    from ticket_system.lib import ticket_ops
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)

    # commands 模組命名空間（from ... import 已綁定）
    from ticket_system.commands import fields as fields_mod
    monkeypatch.setattr(fields_mod, "get_ticket_path", _fake_get_ticket_path)

    from ticket_system.commands import track_acceptance as ta_mod
    monkeypatch.setattr(ta_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ta_mod, "load_ticket", _fake_load_ticket)

    from ticket_system.commands import track_relations as tr_mod
    monkeypatch.setattr(tr_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(tr_mod, "load_ticket", _fake_load_ticket)

    from ticket_system.commands import track_set_acceptance as tsa_mod
    monkeypatch.setattr(tsa_mod, "get_ticket_path", _fake_get_ticket_path)


# ============================================================
# Workers (module top-level for fork to inherit patches)
# ============================================================

class _Args:
    """簡易 argparse.Namespace 替身（multiprocessing fork 友好）。"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _worker_add_acceptance(args):
    version, ticket_id, value = args
    import io
    import sys
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.commands.fields import execute_add_acceptance
        ns = _Args(ticket_id=ticket_id, value=value)
        return execute_add_acceptance(ns, version)
    finally:
        sys.stdout = saved


def _worker_add_spawned(args):
    version, ticket_id, value = args
    import io
    import sys
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.commands.fields import execute_add_spawned
        ns = _Args(ticket_id=ticket_id, value=[value])
        return execute_add_spawned(ns, version)
    finally:
        sys.stdout = saved


def _worker_append_log(args):
    version, ticket_id, content = args
    import io
    import sys
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.commands.track_acceptance import execute_append_log
        ns = _Args(ticket_id=ticket_id, section="Execution Log", content=content)
        return execute_append_log(ns, version)
    finally:
        sys.stdout = saved


def _worker_set_blocked_by_add(args):
    version, ticket_id, ref_id = args
    import io
    import sys
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.commands.track_relations import execute_set_blocked_by
        ns = _Args(ticket_id=ticket_id, value=ref_id, add=True, remove=False)
        return execute_set_blocked_by(ns, version)
    finally:
        sys.stdout = saved


# ============================================================
# Tests
# ============================================================

class TestAddAcceptanceRace:
    """fields.execute_add_acceptance 並發 → 全部變更保留（無 lost update）。"""

    def test_concurrent_add_acceptance_no_lost_update(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        ticket_id = "0.0.0-W0-ADDACC"
        path = tmp_ticket_dir / f"{ticket_id}.md"
        N = 10
        N_ROUNDS = 3

        for round_idx in range(N_ROUNDS):
            _write_ticket(path, ticket_id, acceptance=[])
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            args = [("0.0.0", ticket_id, f"item-r{round_idx}-{i}") for i in range(N)]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_add_acceptance, args)

            assert all(r == 0 for r in results), f"round {round_idx}: exit codes={results}"

            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            acceptance = fm.get("acceptance") or []
            assert len(acceptance) == N, (
                f"round {round_idx}: expected {N} items (no lost update), "
                f"got {len(acceptance)}; items={acceptance}"
            )


class TestAddSpawnedRace:
    """fields.execute_add_spawned 並發 → 全部 ID 保留。"""

    def test_concurrent_add_spawned_no_lost_update(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        ticket_id = "0.0.0-W0-ADDSPN"
        path = tmp_ticket_dir / f"{ticket_id}.md"
        N = 10
        N_ROUNDS = 3

        for round_idx in range(N_ROUNDS):
            _write_ticket(path, ticket_id, spawned=[])
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            args = [("0.0.0", ticket_id, f"0.0.0-W0-CHILD{round_idx}-{i:02d}") for i in range(N)]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_add_spawned, args)

            assert all(r == 0 for r in results), f"round {round_idx}: exit codes={results}"

            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            spawned = fm.get("spawned_tickets") or []
            assert len(spawned) == N, (
                f"round {round_idx}: expected {N} spawned ids (no lost update), "
                f"got {len(spawned)}; spawned={spawned}"
            )


class TestAppendLogRace:
    """track_acceptance.execute_append_log 並發 → body 含所有訊息（無覆蓋）。"""

    def test_concurrent_append_log_no_lost_content(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        ticket_id = "0.0.0-W0-LOGRACE"
        path = tmp_ticket_dir / f"{ticket_id}.md"
        N = 10
        N_ROUNDS = 3

        # body 必須含 ## Execution Log 區段；_write_ticket 預設只給 "body"
        def _seed():
            content = (
                "---\n"
                f"id: {ticket_id}\n"
                "title: race target\n"
                "type: IMP\n"
                # W3-044: append-log 需 status=in_progress（precondition）
                "status: in_progress\n"
                "assigned: true\n"
                "tdd_phase: phase3b\n"
                "children: []\n"
                "blockedBy: []\n"
                "acceptance: []\n"
                "spawned_tickets: []\n"
                "---\n\n"
                "## Execution Log\n\n"
            )
            path.write_text(content, encoding="utf-8")

        for round_idx in range(N_ROUNDS):
            _seed()
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            sentinels = [f"SENTINEL-r{round_idx}-{i:02d}" for i in range(N)]
            args = [("0.0.0", ticket_id, s) for s in sentinels]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_append_log, args)

            assert all(r == 0 for r in results), f"round {round_idx}: exit codes={results}"

            body = path.read_text(encoding="utf-8")
            missing = [s for s in sentinels if s not in body]
            assert not missing, (
                f"round {round_idx}: lost {len(missing)}/{N} log entries: {missing[:5]}..."
            )


class TestSetBlockedByAddRace:
    """track_relations.execute_set_blocked_by --add 並發 → 所有 ref_id 保留。"""

    def test_concurrent_set_blocked_by_add_no_lost_update(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        ticket_id = "0.0.0-W0-BLKRACE"
        path = tmp_ticket_dir / f"{ticket_id}.md"
        N = 10
        N_ROUNDS = 3

        # 被引用的 ticket 必須存在（add 模式會 validate_ticket_exists）
        ref_ids = [f"0.0.0-W0-REF{i:02d}" for i in range(N)]
        for rid in ref_ids:
            _write_ticket(tmp_ticket_dir / f"{rid}.md", rid)

        for round_idx in range(N_ROUNDS):
            _write_ticket(path, ticket_id, blocked_by=[])
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            args = [("0.0.0", ticket_id, rid) for rid in ref_ids]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_set_blocked_by_add, args)

            assert all(r == 0 for r in results), f"round {round_idx}: exit codes={results}"

            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            blocked_by = fm.get("blockedBy") or []
            assert len(blocked_by) == N, (
                f"round {round_idx}: expected {N} blockedBy ids (no lost update), "
                f"got {len(blocked_by)}; blockedBy={blocked_by}"
            )
