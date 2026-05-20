"""Tests for ticket_system/commands/track_dashboard.py (W10-114).

28 案測試，覆蓋 sage Phase 2 設計：
- Group A：三章節輸出結構（A1-A6，6 案）
- Group B：[N] 編號規則（B1-B5，5 案）
- Group C：複用既有函式不 subprocess（C1-C3，3 案）
- Group D：邊界條件（D1-D7，7 案）
- Group E：Flag 行為（E1-E4，4 案）
- Group F：Golden output（F1-F3，3 案）

策略：
- 直接 invoke main function（不走 CliRunner）
- ticket loader 注入：monkeypatch track_dashboard.list_tickets
- subprocess spy：monkeypatch subprocess.run/Popen/check_output/check_call
- 動態 stale 分鐘：fixture 內 started_at 用 now - timedelta
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

from ticket_system.commands import track_dashboard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk(
    tid: str,
    status: str = "pending",
    blocked: Optional[List[str]] = None,
    priority: str = "P2",
    wave: int = 10,
    title: Optional[str] = None,
    started_at: Optional[str] = None,
    body_with_cb: bool = True,
    agent: Optional[str] = None,
) -> Dict[str, Any]:
    """建立最小 ticket dict。

    body_with_cb=True 注入含 Context Bundle 區塊的 _body，使
    _compute_readiness 回傳 READY（無 handoff 時走 Context Bundle 分支）。
    """
    body = ""
    if body_with_cb:
        body = (
            "## Context Bundle\n\n"
            "<!-- auto-extracted -->\n\n"
            "### Task Reference\n- relevant context here\n"
        )
    return {
        "id": tid,
        "title": title or f"title-{tid}",
        "status": status,
        "blockedBy": blocked or [],
        "priority": priority,
        "wave": wave,
        "version": "0.18.0",
        "started_at": started_at,
        "who": {"current": agent} if agent else {},
        "_body": body,
    }


def _ns(**kwargs) -> argparse.Namespace:
    defaults = dict(
        top=track_dashboard.DEFAULT_TOP,
        wave=None,
        no_stale=False,
        stale_threshold=track_dashboard.DEFAULT_STALE_THRESHOLD_MIN,
        format=track_dashboard.FORMAT_TEXT,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _patch_loader(monkeypatch, tickets: List[Dict]):
    monkeypatch.setattr(track_dashboard, "list_tickets", lambda v: tickets)
    monkeypatch.setattr(
        track_dashboard, "_get_pending_handoff_info", lambda: {}
    )


def _now_iso(minutes_ago: int = 0) -> str:
    return (datetime.now() - timedelta(minutes=minutes_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


# ---------------------------------------------------------------------------
# Group A：三章節輸出結構（6 案）
# ---------------------------------------------------------------------------

def test_A1_text_three_sections_present(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(5), agent="thyme"),
        _mk("0.18.0-W10-002", priority="P0"),
        _mk("0.18.0-W10-003", status="in_progress",
            started_at=_now_iso(120), agent="parsley"),  # stale
    ]
    _patch_loader(monkeypatch, tickets)
    rc = track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("[In Progress]") == 1
    assert out.count("[Ready Top 5]") == 1
    assert out.count("[Stale Warning]") == 1


def test_A2_text_section_order_stable(monkeypatch, capsys):
    tickets = [_mk("0.18.0-W10-002", priority="P0")]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    ip = out.find("[In Progress]")
    rd = out.find("[Ready Top")
    st = out.find("[Stale Warning]")
    assert 0 <= ip < rd < st


def test_A3_json_three_keys_present(monkeypatch, capsys):
    tickets = [_mk("0.18.0-W10-002", priority="P0")]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(format="json"), "0.18.0")
    payload = json.loads(capsys.readouterr().out)
    assert "in_progress" in payload
    assert "ready" in payload
    assert "stale" in payload


def test_A4_json_text_data_equivalence(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-002", priority="P0"),
        _mk("0.18.0-W10-003", priority="P1"),
    ]
    _patch_loader(monkeypatch, tickets)

    track_dashboard.dashboard_main(_ns(format="json"), "0.18.0")
    j = json.loads(capsys.readouterr().out)
    json_ids = [r["id"] for r in j["ready"]]

    track_dashboard.dashboard_main(_ns(), "0.18.0")
    text_out = capsys.readouterr().out
    text_ids = re.findall(
        r"^\s*\[\d+\]\s+\[P\d\]\s+\[ready\]\s+(\S+)",
        text_out, flags=re.MULTILINE,
    )
    assert json_ids == text_ids


def test_A5_header_meta_present(monkeypatch, capsys):
    _patch_loader(monkeypatch, [])
    track_dashboard.dashboard_main(_ns(wave=10), "0.18.0")
    out = capsys.readouterr().out
    assert re.match(
        r"=== Dashboard \(wave=10, version=0\.18\.0\) ===",
        out.splitlines()[0],
    )


def test_A6_empty_section_renders_none(monkeypatch, capsys):
    _patch_loader(monkeypatch, [])
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    # 三章節 header 出現
    assert "[In Progress] 0 ticket(s)" in out
    assert "[Ready Top 5]" in out
    assert "[Stale Warning] 0 ticket(s) over 60min" in out
    # 三段 (none)
    assert out.count("(none)") == 3


# ---------------------------------------------------------------------------
# Group B：[N] 編號規則（5 案）
# ---------------------------------------------------------------------------

def test_B1_ready_lines_have_bracket_n(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-002", priority="P0"),
        _mk("0.18.0-W10-003", priority="P1"),
        _mk("0.18.0-W10-004", priority="P2"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    pattern = re.compile(r"^\s*\[\d+\]\s+\[P\d\]\s+\[ready\]\s+\S+")
    # 抓 Ready 區段
    ready_section = out.split("[Ready Top 5]")[1].split("[Stale Warning]")[0]
    matched = [ln for ln in ready_section.splitlines() if pattern.match(ln)]
    assert len(matched) == 3


def test_B2_numbering_starts_from_1(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-002", priority="P0"),
        _mk("0.18.0-W10-003", priority="P1"),
        _mk("0.18.0-W10-004", priority="P2"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    nums = re.findall(r"^\s*\[(\d+)\]\s+\[P\d\]\s+\[ready\]", out, flags=re.MULTILINE)
    assert nums == ["1", "2", "3"]


def test_B3_in_progress_no_bracket_n(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(5), agent="thyme"),
        _mk("0.18.0-W10-002", status="in_progress",
            started_at=_now_iso(6), agent="parsley"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    ip_section = out.split("[In Progress]")[1].split("[Ready Top")[0]
    assert not re.search(r"^\s*\[\d+\]", ip_section, flags=re.MULTILINE)


def test_B4_stale_no_bracket_n(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(120), agent="thyme"),
        _mk("0.18.0-W10-002", status="in_progress",
            started_at=_now_iso(200), agent="parsley"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    stale_section = out.split("[Stale Warning]")[1]
    assert not re.search(r"^\s*\[\d+\]", stale_section, flags=re.MULTILINE)


def test_B5_top_limits_numbering(monkeypatch, capsys):
    tickets = [
        _mk(f"0.18.0-W10-{i:03d}", priority="P1") for i in range(2, 7)
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(top=2), "0.18.0")
    out = capsys.readouterr().out
    nums = re.findall(r"^\s*\[(\d+)\]\s+\[P\d\]\s+\[ready\]", out, flags=re.MULTILINE)
    assert nums == ["1", "2"]


# ---------------------------------------------------------------------------
# Group C：禁用 subprocess + ticket index 載入 1 次（3 案）
# ---------------------------------------------------------------------------

def test_C1_no_subprocess_run(monkeypatch, capsys):
    def _fail(*args, **kwargs):
        raise AssertionError("subprocess.run called")
    monkeypatch.setattr(subprocess, "run", _fail)
    _patch_loader(monkeypatch, [_mk("0.18.0-W10-002", priority="P0")])
    rc = track_dashboard.dashboard_main(_ns(), "0.18.0")
    assert rc == 0


def test_C2_no_subprocess_popen(monkeypatch, capsys):
    def _fail(*args, **kwargs):
        raise AssertionError("subprocess.Popen called")
    monkeypatch.setattr(subprocess, "Popen", _fail)
    monkeypatch.setattr(subprocess, "check_output",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("check_output called")))
    monkeypatch.setattr(subprocess, "check_call",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("check_call called")))
    _patch_loader(monkeypatch, [_mk("0.18.0-W10-002", priority="P0")])
    rc = track_dashboard.dashboard_main(_ns(), "0.18.0")
    assert rc == 0


def test_C3_ticket_index_loaded_once(monkeypatch, capsys):
    call_count = {"n": 0}

    def _spy(version):
        call_count["n"] += 1
        return [
            _mk("0.18.0-W10-001", status="in_progress",
                started_at=_now_iso(5)),
            _mk("0.18.0-W10-002", priority="P0"),
            _mk("0.18.0-W10-003", status="in_progress",
                started_at=_now_iso(120)),  # 同時也是 stale 候選
        ]
    monkeypatch.setattr(track_dashboard, "list_tickets", _spy)
    monkeypatch.setattr(
        track_dashboard, "_get_pending_handoff_info", lambda: {}
    )
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Group D：邊界條件（7 案）
# ---------------------------------------------------------------------------

def test_D1_top_zero(monkeypatch, capsys):
    tickets = [_mk("0.18.0-W10-002", priority="P0")]
    _patch_loader(monkeypatch, tickets)
    rc = track_dashboard.dashboard_main(_ns(top=0), "0.18.0")
    out = capsys.readouterr().out
    assert rc == 0
    assert "[Ready Top 0]" in out
    ready_section = out.split("[Ready Top 0]")[1].split("[Stale Warning]")[0]
    assert "(none)" in ready_section


def test_D2_top_exceeds_available(monkeypatch, capsys):
    tickets = [
        _mk(f"0.18.0-W10-{i:03d}", priority="P1") for i in range(2, 5)
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(top=100), "0.18.0")
    out = capsys.readouterr().out
    nums = re.findall(r"^\s*\[(\d+)\]\s+\[P\d\]\s+\[ready\]", out, flags=re.MULTILINE)
    assert len(nums) == 3


def test_D3_wave_not_exist(monkeypatch, capsys):
    tickets = [_mk("0.18.0-W10-002", priority="P0", wave=10)]
    _patch_loader(monkeypatch, tickets)
    rc = track_dashboard.dashboard_main(_ns(wave=999), "0.18.0")
    out = capsys.readouterr().out
    assert rc == 0
    assert "wave=999" in out
    assert out.count("(none)") == 3


def test_D4_no_stale_flag(monkeypatch, capsys):
    tickets = [_mk("0.18.0-W10-001", status="in_progress",
                   started_at=_now_iso(200))]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(no_stale=True), "0.18.0")
    out = capsys.readouterr().out
    assert "[Stale Warning]" not in out


def test_D5_json_no_stale_null(monkeypatch, capsys):
    _patch_loader(monkeypatch, [])
    track_dashboard.dashboard_main(_ns(format="json", no_stale=True), "0.18.0")
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] is None


def test_D6_no_active_version(monkeypatch, capsys):
    # W15-028.2: 無 active version 屬業務拒絕（查無資料），exit code 2
    rc = track_dashboard.dashboard_main(_ns(), None)
    err = capsys.readouterr().err
    assert rc == 2
    assert "No active version detected" in err


def test_D7_ticket_index_load_fail(monkeypatch, capsys):
    def _raise(v):
        raise RuntimeError("simulated index load failure")
    monkeypatch.setattr(track_dashboard, "list_tickets", _raise)
    rc = track_dashboard.dashboard_main(_ns(), "0.18.0")
    captured = capsys.readouterr()
    assert rc == 1
    assert "simulated index load failure" in captured.err
    assert captured.out == ""


# ---------------------------------------------------------------------------
# Group E：Flag 預設行為（4 案）
# ---------------------------------------------------------------------------

def test_E1_default_top_is_5(monkeypatch, capsys):
    tickets = [
        _mk(f"0.18.0-W10-{i:03d}", priority="P1") for i in range(2, 12)
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    nums = re.findall(r"^\s*\[(\d+)\]\s+\[P\d\]\s+\[ready\]", out, flags=re.MULTILINE)
    assert len(nums) == 5


def test_E2_default_stale_threshold_60(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(70)),   # 命中
        _mk("0.18.0-W10-002", status="in_progress",
            started_at=_now_iso(30)),   # 不命中
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    stale_section = out.split("[Stale Warning]")[1]
    assert "0.18.0-W10-001" in stale_section
    assert "0.18.0-W10-002" not in stale_section


def test_E3_custom_stale_threshold(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(35)),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(stale_threshold=30), "0.18.0")
    out = capsys.readouterr().out
    stale_section = out.split("[Stale Warning]")[1]
    assert "0.18.0-W10-001" in stale_section


def test_E4_default_format_text(monkeypatch, capsys):
    _patch_loader(monkeypatch, [])
    track_dashboard.dashboard_main(_ns(), "0.18.0")
    out = capsys.readouterr().out
    assert out.lstrip().startswith("=== Dashboard")
    # 非 JSON：不應為 valid json
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


# ---------------------------------------------------------------------------
# Group F：Golden output 對照（3 案，inline expected）
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """normalize 動態欄位（started_at / stale=Nm）以利字串比對。"""
    text = re.sub(
        r"started_at:\s*[\d\-T:\.]+",
        "started_at: <NORMALIZED>",
        text,
    )
    text = re.sub(r"stale=\d+m", "stale=<MINS>m", text)
    return text


def test_F1_golden_pure_pending(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-101", priority="P0", title="A"),
        _mk("0.18.0-W10-102", priority="P1", title="B"),
        _mk("0.18.0-W10-103", priority="P2", title="C"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(wave=10), "0.18.0")
    out = _normalize(capsys.readouterr().out)
    expected = (
        "=== Dashboard (wave=10, version=0.18.0) ===\n"
        "\n"
        "[In Progress] 0 ticket(s)\n"
        "  (none)\n"
        "\n"
        "[Ready Top 5]  priority 排序，可直接 claim\n"
        "  [1] [P0] [ready] 0.18.0-W10-101  A\n"
        "  [2] [P1] [ready] 0.18.0-W10-102  B\n"
        "  [3] [P2] [ready] 0.18.0-W10-103  C\n"
        "\n"
        "[Stale Warning] 0 ticket(s) over 60min\n"
        "  (none)\n"
        "\n"
        "Hint: ticket track claim <id>\n"
    )
    assert out == expected


def test_F2_golden_with_in_progress(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(5), agent="thyme",
            title="impl"),
        _mk("0.18.0-W10-101", priority="P1", title="X"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(wave=10), "0.18.0")
    out = _normalize(capsys.readouterr().out)
    expected = (
        "=== Dashboard (wave=10, version=0.18.0) ===\n"
        "\n"
        "[In Progress] 1 ticket(s)\n"
        "  - 0.18.0-W10-001  impl  "
        "(started_at: <NORMALIZED>, agent: thyme)\n"
        "\n"
        "[Ready Top 5]  priority 排序，可直接 claim\n"
        "  [1] [P1] [ready] 0.18.0-W10-101  X\n"
        "\n"
        "[Stale Warning] 0 ticket(s) over 60min\n"
        "  (none)\n"
        "\n"
        "Hint: ticket track claim <id>\n"
    )
    assert out == expected


def test_F3_golden_with_stale(monkeypatch, capsys):
    tickets = [
        _mk("0.18.0-W10-001", status="in_progress",
            started_at=_now_iso(87), agent="parsley", title="long"),
        _mk("0.18.0-W10-101", priority="P0", title="P"),
    ]
    _patch_loader(monkeypatch, tickets)
    track_dashboard.dashboard_main(_ns(wave=10, stale_threshold=30), "0.18.0")
    out = _normalize(capsys.readouterr().out)
    expected = (
        "=== Dashboard (wave=10, version=0.18.0) ===\n"
        "\n"
        "[In Progress] 1 ticket(s)\n"
        "  - 0.18.0-W10-001  long  "
        "(started_at: <NORMALIZED>, agent: parsley)\n"
        "\n"
        "[Ready Top 5]  priority 排序，可直接 claim\n"
        "  [1] [P0] [ready] 0.18.0-W10-101  P\n"
        "\n"
        "[Stale Warning] 1 ticket(s) over 30min\n"
        "  - 0.18.0-W10-001  stale=<MINS>m  "
        "status=in_progress  agent=parsley\n"
        "\n"
        "Hint: ticket track claim <id>\n"
    )
    assert out == expected
