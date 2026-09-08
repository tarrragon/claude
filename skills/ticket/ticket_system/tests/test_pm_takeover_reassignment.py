"""PM 暫代管票的 complete 前置重新指派（reassign_who_from_pm_if_takeover）。

背景：PM 依 pm-role 流程先 claim 再派發時，who.current 停在 PM
（rosemary-project-manager）。派發的代理人執行 ``complete --as <self>``
會因 who.current 為 PM 而非自己被 identity_guard 以身份不符 deny——兩條
既有出口（帶 --as 被拒 / PM 代跑 complete）都不是正確處置，執行者也不該
自行 set-who（who 是權責歸屬欄位）。本檔驗證新出口：僅當目前持有者確實
是 PM 本人時，complete/finish 前置自動讓出 who.current 給申報身份的
具名執行者，使後續 identity_guard 走「相符放行」。

測試覆蓋:
1. who.current = PM → reassign 為具名執行者，回傳 True
2. who.current = 其他具名代理人（非 PM）→ 不覆蓋，回傳 False（既有誤指派保護不受影響）
3. as_agent 為 None / 空字串 → 不覆蓋（不應無條件清空 who）
4. as_agent = PM_AGENT_NAME 本人 → 不覆蓋（PM 完成自己暫代管的票，維持既有豁免路徑）
5. 整合：reassign 後 identity_guard.check_identity 對相同 --as 值放行
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from ticket_system.lib.identity_guard import PM_AGENT_NAME
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_ticket(path: Path, tid: str, who_lines: List[str]) -> None:
    """最小合法 in_progress ticket（PM 已 claim），who 區塊由 who_lines 注入。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: pm-takeover target",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "started_at: '2026-09-07T00:00:00'",
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
    """重導 lifecycle 的 path/load 至 tmp dir（仿 test_claim_as_sets_who.py）。"""
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

    monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)


def _read_who(path: Path) -> dict:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm.get("who")


def _reassign(tid: str, as_agent) -> bool:
    from ticket_system.commands.lifecycle import reassign_who_from_pm_if_takeover

    return reassign_who_from_pm_if_takeover("0.0.0", tid, as_agent)


_WHO_DICT_PM = [
    "who:",
    f"  current: {PM_AGENT_NAME}",
    "  history: {}",
]


def test_pm_held_ticket_reassigns_to_named_agent(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """who.current = PM → reassign 為具名執行者，回傳 True。"""
    tid = "0.0.0-W0-TAKEOVER1"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, _WHO_DICT_PM)

    assert _reassign(tid, "thyme-python-developer") is True

    who = _read_who(path)
    assert who["current"] == "thyme-python-developer"


def test_other_named_agent_not_overwritten(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """who.current 已是其他具名代理人（非 PM）→ 不覆蓋，回傳 False。

    誤指派保護不受影響（PC-V1-002）：本函式僅處理 PM 暫代管的狀態，
    不處理代理人之間的身份衝突。
    """
    tid = "0.0.0-W0-TAKEOVER2"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(
        path, tid, ["who:", "  current: other-agent", "  history: {}"]
    )

    assert _reassign(tid, "thyme-python-developer") is False

    who = _read_who(path)
    assert who["current"] == "other-agent"


def test_missing_as_agent_not_overwritten(tmp_ticket_dir: Path, patch_ticket_paths):
    """as_agent 為 None → 不覆蓋（不應無條件清空 who）。"""
    tid = "0.0.0-W0-TAKEOVER3"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, _WHO_DICT_PM)

    assert _reassign(tid, None) is False

    who = _read_who(path)
    assert who["current"] == PM_AGENT_NAME


def test_empty_as_agent_not_overwritten(tmp_ticket_dir: Path, patch_ticket_paths):
    """as_agent 為空字串 → 不覆蓋（同上，防禦性檢查）。"""
    tid = "0.0.0-W0-TAKEOVER4"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, _WHO_DICT_PM)

    assert _reassign(tid, "  ") is False

    who = _read_who(path)
    assert who["current"] == PM_AGENT_NAME


def test_pm_completing_own_ticket_not_overwritten(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """as_agent = PM_AGENT_NAME 本人 → 不覆蓋，維持既有 PM 豁免路徑。"""
    tid = "0.0.0-W0-TAKEOVER5"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, _WHO_DICT_PM)

    assert _reassign(tid, PM_AGENT_NAME) is False

    who = _read_who(path)
    assert who["current"] == PM_AGENT_NAME


def test_integration_with_identity_guard_pass(
    tmp_ticket_dir: Path, patch_ticket_paths, monkeypatch
):
    """整合：reassign 後 identity_guard.check_identity 對相同 --as 值放行。"""
    from ticket_system.lib import identity_guard

    tid = "0.0.0-W0-TAKEOVER6"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, _WHO_DICT_PM)

    def _fake_load_ticket(version: str, ticket_id: str):
        p = tmp_ticket_dir / f"{ticket_id}.md"
        if not p.exists():
            return None
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        return fm or None

    monkeypatch.setattr(identity_guard, "load_ticket", _fake_load_ticket)

    assert _reassign(tid, "thyme-python-developer") is True

    result = identity_guard.check_identity(
        "0.0.0", tid, "thyme-python-developer", command="complete"
    )
    assert result is None  # None = 放行（情境 3：--as == who.current）
