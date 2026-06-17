"""W2-018: claim --as <agent> 設 who.current，使 complete --as 對稱通過 identity-guard。

來源: W2-018（source W2-010）。SKILL.md 推薦 subagent 裸 claim，但裸 claim
不寫 who.current，導致 who.current="pending" 的 ticket 在後續
complete --as <agent> 被 identity-guard deny，agent 須 set-who 繞過。

修正方案 A：claim 新增 --as，認領時寫入 who.current（與 complete --as 對稱）。

測試覆蓋:
1. claim --as X → who.current == X，who.history 保留
2. 裸 claim（無 --as）→ who.current 不變（向後相容）
3. who 為 legacy string 格式 → claim --as X 重建為 dict 且 current==X，不 raise
4. 整合：who.current="pending" → claim --as X → who.current==X（complete --as 可對稱）
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_pending_ticket(path: Path, tid: str, who_lines: List[str]) -> None:
    """最小合法 pending ticket，who 區塊由 who_lines 注入。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: claim-as target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "acceptance: []",
        "tdd_phase: ''",
        "children: []",
        "blockedBy: []",
        *who_lines,
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 lifecycle / ticket_ops 的 path/load 至 tmp dir（仿 race test）。"""
    from ticket_system.commands import lifecycle as lifecycle_mod
    from ticket_system.lib import ticket_ops

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
    monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)


def _read_who(path: Path) -> dict:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm.get("who")


def _claim(tid: str, as_agent=None) -> int:
    from ticket_system.commands.lifecycle import TicketLifecycle

    return TicketLifecycle("0.0.0").claim(tid, as_agent=as_agent)


# who 區塊：dict 格式，current=pending
_WHO_DICT_PENDING = [
    "who:",
    "  current: pending",
    "  history: {}",
]


def test_claim_as_sets_who_current(tmp_ticket_dir: Path, patch_ticket_paths):
    """claim --as X → who.current == X。"""
    tid = "0.0.0-W0-CLAIMAS1"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, _WHO_DICT_PENDING)

    assert _claim(tid, as_agent="thyme-python-developer") == 0

    who = _read_who(path)
    assert isinstance(who, dict)
    assert who["current"] == "thyme-python-developer"


def test_claim_as_preserves_history(tmp_ticket_dir: Path, patch_ticket_paths):
    """claim --as X 保留既有 who.history。"""
    tid = "0.0.0-W0-CLAIMAS2"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(
        path,
        tid,
        [
            "who:",
            "  current: pending",
            "  history:",
            "    rosemary-project-manager: created",
        ],
    )

    assert _claim(tid, as_agent="thyme-python-developer") == 0

    who = _read_who(path)
    assert who["current"] == "thyme-python-developer"
    assert who.get("history", {}).get("rosemary-project-manager") == "created"


def test_bare_claim_does_not_touch_who(tmp_ticket_dir: Path, patch_ticket_paths):
    """裸 claim（無 --as）→ who.current 不變（向後相容）。"""
    tid = "0.0.0-W0-CLAIMAS3"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, _WHO_DICT_PENDING)

    assert _claim(tid, as_agent=None) == 0

    who = _read_who(path)
    assert who["current"] == "pending"


def test_claim_as_empty_string_does_not_touch_who(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """claim --as ''（空字串）→ 維持現行為（向後相容）。"""
    tid = "0.0.0-W0-CLAIMAS4"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, _WHO_DICT_PENDING)

    assert _claim(tid, as_agent="") == 0

    who = _read_who(path)
    assert who["current"] == "pending"


def test_claim_as_rebuilds_legacy_string_who(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """who 為 legacy string 格式時，claim --as X 重建為 dict 且 current==X，不 raise。"""
    tid = "0.0.0-W0-CLAIMAS5"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, ["who: rosemary-project-manager"])

    assert _claim(tid, as_agent="thyme-python-developer") == 0

    who = _read_who(path)
    assert isinstance(who, dict)
    assert who["current"] == "thyme-python-developer"
    assert "history" in who


def test_claim_as_integration_with_identity_guard(
    tmp_ticket_dir: Path, patch_ticket_paths, monkeypatch
):
    """整合：who.current=pending → claim --as X → identity_guard 視 X 為 current。

    驗證 complete --as X 不再因 who.current=='pending' 被誤擋。
    """
    from ticket_system.lib import identity_guard

    tid = "0.0.0-W0-CLAIMAS6"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, _WHO_DICT_PENDING)

    # identity_guard 透過 parser.load_ticket 讀取，導向 tmp dir
    def _fake_load_ticket(version: str, ticket_id: str):
        p = tmp_ticket_dir / f"{ticket_id}.md"
        if not p.exists():
            return None
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        return fm or None

    monkeypatch.setattr(identity_guard, "load_ticket", _fake_load_ticket)

    assert _claim(tid, as_agent="thyme-python-developer") == 0

    # claim 後 who.current 應為 agent → complete --as 對稱放行（check_identity 回 None）
    result = identity_guard.check_identity(
        "0.0.0", tid, "thyme-python-developer", command="complete"
    )
    assert result is None  # None = 放行（情境 3：--as == who.current）

    who = _read_who(path)
    assert who["current"] == "thyme-python-developer"
