"""Tests for ticket_system/commands/track_td_status.py (W10-083 / PC-094).

覆蓋三狀態校準：
- 已處理（done）：body 標註「已處理 / 已修正 ...」或 commit 訊息引用
- 無需處理（skipped）：body 標註「無需 / 豁免」等
- 仍待處理（pending）：body / commit 均無訊號

並驗證 AC 4 校準提示在有 pending TD 時呼叫即輸出。
"""

from __future__ import annotations

import argparse
from typing import Set

import pytest

from ticket_system.commands import track_td_status as mod


# ---------------------------------------------------------------------------
# _extract_td_numbers
# ---------------------------------------------------------------------------

def test_extract_td_numbers_basic():
    body = (
        "| TD1 | use_cache noop | ... |\n"
        "| TD2 | subprocess 序列 | ... |\n"
        "Phase 4 評估 TD2 並行化\n"
    )
    assert mod._extract_td_numbers(body) == ["1", "2"]


def test_extract_td_numbers_ignores_tdd():
    body = "## TDD Phase 1 功能設計\n本 TDD 流程..."
    # TDD 不應命中（避免誤判）
    assert mod._extract_td_numbers(body) == []


def test_extract_td_numbers_deduplicates():
    body = "TD1 出現一次\nTD1 再次出現\nTD3 新編號"
    assert mod._extract_td_numbers(body) == ["1", "3"]


def test_extract_td_numbers_empty_body():
    assert mod._extract_td_numbers("") == []
    assert mod._extract_td_numbers(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _classify_td_in_body
# ---------------------------------------------------------------------------

def test_classify_done_in_body():
    body = "Phase 3a C3 已修正為 Optional[int]，TD7 關閉"
    assert mod._classify_td_in_body("7", body) == mod.STATUS_DONE


def test_classify_skipped_in_body():
    body = "TD5 無需處理（保留接口供 Phase 4 評估）"
    assert mod._classify_td_in_body("5", body) == mod.STATUS_SKIPPED


def test_classify_skipped_takes_priority_over_done():
    body = "TD5 無需處理；雖然 TD5 已修正 stub"
    # skip 訊號優先
    assert mod._classify_td_in_body("5", body) == mod.STATUS_SKIPPED


def test_classify_returns_none_when_no_signal():
    body = "| TD4 | ticket-query 全掃瞄風險 | 改用 --version 過濾 |"
    assert mod._classify_td_in_body("4", body) is None


def test_classify_ignores_other_td_numbers():
    body = "TD1 已修正\nTD2 待處理"
    assert mod._classify_td_in_body("2", body) is None
    assert mod._classify_td_in_body("1", body) == mod.STATUS_DONE


# ---------------------------------------------------------------------------
# classify_tds（綜合三來源）
# ---------------------------------------------------------------------------

def test_classify_tds_three_states():
    body = (
        "TD1 已處理（Phase 3a）\n"
        "TD2 無需處理\n"
        "TD3 待 Phase 4 評估\n"
        "TD4 待規劃\n"
    )
    td_numbers = ["1", "2", "3", "4"]
    commit_refs: Set[str] = {"4"}  # TD4 在 commit 引用 → done

    result = mod.classify_tds(td_numbers, body, commit_refs)
    result_dict = dict(result)
    assert result_dict["1"] == mod.STATUS_DONE
    assert result_dict["2"] == mod.STATUS_SKIPPED
    assert result_dict["3"] == mod.STATUS_PENDING
    assert result_dict["4"] == mod.STATUS_DONE  # 來自 commit


def test_classify_tds_body_skipped_overrides_commit():
    """body 標註 skipped 時，即使 commit 也引用，仍維持 skipped。"""
    body = "TD1 無需處理"
    result = dict(mod.classify_tds(["1"], body, {"1"}))
    assert result["1"] == mod.STATUS_SKIPPED


def test_classify_tds_empty_inputs():
    assert mod.classify_tds([], "", set()) == []


# ---------------------------------------------------------------------------
# _render: AC 4 校準提示
# ---------------------------------------------------------------------------

def test_render_shows_calibration_hint_when_pending():
    classified = [("1", mod.STATUS_DONE), ("2", mod.STATUS_PENDING)]
    out = mod._render("0.18.0-W10-017.8", classified, set())
    assert "仍有 1 個 TD 未見處理訊號" in out
    assert "PC-094" in out
    assert "[已處理] (1) TD1" in out
    assert "[仍待處理] (1) TD2" in out


def test_render_no_hint_when_all_resolved():
    classified = [("1", mod.STATUS_DONE), ("2", mod.STATUS_SKIPPED)]
    out = mod._render("0.18.0-W10-017.8", classified, set())
    assert "仍有" not in out
    assert "[仍待處理] (0)" in out


def test_render_empty_td_list():
    out = mod._render("0.18.0-W10-001", [], set())
    assert "未發現 TD 編號" in out


# ---------------------------------------------------------------------------
# execute_td_status 端對端
# ---------------------------------------------------------------------------

def test_execute_td_status_full_flow(monkeypatch, capsys):
    fake_ticket = {
        "id": "0.18.0-W10-017.8",
        "_body": (
            "| TD1 | A | done | TD1 已處理\n"
            "| TD2 | B | skip | TD2 無需處理\n"
            "| TD3 | C | pending |\n"
        ),
    }
    monkeypatch.setattr(
        mod, "load_ticket", lambda v, tid: fake_ticket
    )
    # 模擬無 git commit 引用
    monkeypatch.setattr(
        mod, "_collect_commit_td_refs", lambda tid: set()
    )

    ns = argparse.Namespace(
        ticket_id="0.18.0-W10-017.8",
        version="0.18.0",
    )
    rc = mod.execute_td_status(ns, "0.18.0")
    assert rc == 0

    captured = capsys.readouterr().out
    assert "[已處理] (1) TD1" in captured
    assert "[無需處理] (1) TD2" in captured
    assert "[仍待處理] (1) TD3" in captured
    assert "PC-094" in captured


def test_execute_td_status_ticket_not_found(monkeypatch, capsys):
    monkeypatch.setattr(mod, "load_ticket", lambda v, tid: None)
    ns = argparse.Namespace(ticket_id="missing-id", version="0.18.0")
    rc = mod.execute_td_status(ns, "0.18.0")
    assert rc == 1
    out = capsys.readouterr().out
    assert "找不到 Ticket" in out


def test_execute_td_status_commit_signal_promotes_to_done(
    monkeypatch, capsys
):
    fake_ticket = {
        "id": "0.18.0-W10-017.8",
        "_body": "| TD4 | ticket-query 全掃瞄 | 改用 --version 過濾 |",
    }
    monkeypatch.setattr(mod, "load_ticket", lambda v, tid: fake_ticket)
    monkeypatch.setattr(
        mod, "_collect_commit_td_refs", lambda tid: {"4"}
    )

    ns = argparse.Namespace(
        ticket_id="0.18.0-W10-017.8", version="0.18.0"
    )
    rc = mod.execute_td_status(ns, "0.18.0")
    assert rc == 0

    captured = capsys.readouterr().out
    # body 無訊號但 commit 引用 → done
    assert "[已處理] (1) TD4" in captured
    assert "[仍待處理] (0)" in captured
