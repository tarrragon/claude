"""Group D：觀測 log JSONL 寫入契約（Phase 2 §3 Group D / Phase 3a §4）。

測試 D1-D7：schema 契約 + append / rotate / fail-open / caller / 欄位型別。

Sociable Unit Tests：直接呼叫 checkpoint_state() 主函式，注入 tmp project_root，
不 mock dataclass / datetime / json；僅隔離外部世界（git / ticket CLI / 檔案系統）。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List

import pytest

from ticket_system.lib.checkpoint_state import (
    CheckpointState,
    PendingCheck,
    _write_metrics_log,
    checkpoint_state,
)


# ---------------------------------------------------------------------------
# D helper：最小化 state 供 _write_metrics_log 直接測試
# ---------------------------------------------------------------------------


def _make_state(
    current_phase: str = "3",
    ticket_id: str | None = None,
    ready_for_clear: bool = True,
    active_agents: int = 0,
    uncommitted_files: int | None = 0,
) -> CheckpointState:
    return CheckpointState(
        current_phase=current_phase,
        ready_for_clear=ready_for_clear,
        pending_checks=[],
        active_agents=active_agents,
        unmerged_worktrees=[],
        active_handoff=None,
        in_progress_tickets=[],
        data_sources={"git-status": "ok"},
        computed_at="2026-04-19T12:00:00+00:00",
        uncommitted_files=uncommitted_files,
        _ticket_id=ticket_id,
    )


# ---------------------------------------------------------------------------
# D1：正常寫入 — JSONL schema 10 欄位
# ---------------------------------------------------------------------------


def test_D1_write_metrics_log_schema_contract(tmp_path: Path):
    """D1：合法 state + log_metrics=True → 檔案末尾追加 1 行 JSON 含 10 欄位。"""
    state = _make_state(
        current_phase="1",
        ticket_id="0.18.0-W10-017.8",
        ready_for_clear=False,
        uncommitted_files=3,
    )
    _write_metrics_log(
        state, caller="snapshot", duration_ms=47.3, errors={"git-status": "ok"},
        project_root=tmp_path,
    )

    log_path = tmp_path / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    expected_keys = {
        "ts", "event", "caller", "ticket_id",
        "current_phase", "ready_for_clear",
        "active_agents", "uncommitted_files",
        "duration_ms", "data_source_errors",
    }
    assert set(entry.keys()) == expected_keys
    assert entry["event"] == "checkpoint_state"
    assert entry["caller"] == "snapshot"
    assert entry["ticket_id"] == "0.18.0-W10-017.8"
    assert entry["current_phase"] == "1"
    assert entry["ready_for_clear"] is False
    assert entry["uncommitted_files"] == 3
    assert entry["duration_ms"] == 47.3
    assert entry["data_source_errors"] == []


# ---------------------------------------------------------------------------
# D2：連續 3 次呼叫 → append 非覆蓋
# ---------------------------------------------------------------------------


def test_D2_append_not_overwrite(tmp_path: Path):
    state = _make_state()
    for i in range(3):
        _write_metrics_log(
            state, caller=f"call{i}", duration_ms=10.0, errors={},
            project_root=tmp_path,
        )

    log_path = tmp_path / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    callers = [json.loads(ln)["caller"] for ln in lines]
    assert callers == ["call0", "call1", "call2"]


# ---------------------------------------------------------------------------
# D3：log_metrics=False → 檔案不被寫入
# ---------------------------------------------------------------------------


def test_D3_log_metrics_false_skips_write(
    tmp_git_repo: Path, mock_ticket_query,
):
    mock_ticket_query(ids=[])

    log_path = tmp_git_repo / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    assert not log_path.exists()

    checkpoint_state(
        ticket_id=None, log_metrics=False, caller="test",
        project_root=tmp_git_repo,
    )

    assert not log_path.exists(), "log_metrics=False 不應建立 log 檔"


# ---------------------------------------------------------------------------
# D4：寫入失敗 → fail-open（主流程不拋 + stderr warning；規則 4）
# ---------------------------------------------------------------------------


def test_D4_write_failure_fail_open(
    tmp_git_repo: Path, mock_ticket_query, capsys,
):
    mock_ticket_query(ids=[])

    # 預先建立 log 目錄，然後把 log 路徑改為唯讀目錄
    logs_dir = tmp_git_repo / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 在 logs_dir 下建立一個「目錄」佔用 log 檔名，造成 open('a') 失敗
    blocker = logs_dir / "pm-automation-metrics.jsonl"
    blocker.mkdir()  # 目錄佔名，open for append 會 IsADirectoryError

    # 主流程不該拋
    state = checkpoint_state(
        ticket_id=None, log_metrics=True, caller="test",
        project_root=tmp_git_repo,
    )
    assert isinstance(state, CheckpointState)

    # stderr 應有 warning（規則 4 雙通道）
    captured = capsys.readouterr()
    assert "metrics log write failed" in captured.err or \
           "metrics log rotate failed" in captured.err


# ---------------------------------------------------------------------------
# D5：rotate — log > 10MB 時 rename 為 .1.jsonl
# ---------------------------------------------------------------------------


def test_D5_rotate_at_10mb(tmp_path: Path, monkeypatch):
    """注入小 rotate 閾值（0 位元組）讓測試快速驗證 rotate 行為。"""
    # 強制從 sys.modules 取當前生效的模組（F3 測試會 reimport）
    import importlib
    mod = importlib.import_module("ticket_system.lib.checkpoint_state")

    log_path = tmp_path / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"pre":"existing"}\n', encoding="utf-8")

    # 注入極小閾值（注入到「當前」模組實例，避免 F3 reimport 後失效）
    monkeypatch.setattr(mod, "_METRICS_LOG_ROTATE_BYTES", 5)

    state = _make_state()
    mod._write_metrics_log(state, "test", 1.0, {}, project_root=tmp_path)

    rotated = log_path.with_suffix(".1.jsonl")
    assert rotated.exists(), "rotate 後應產生 .1.jsonl"
    assert rotated.read_text(encoding="utf-8").startswith('{"pre":"existing"}')
    # 新檔從 0 開始（只含本次寫入一行）
    new_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(new_lines) == 1
    assert json.loads(new_lines[0])["caller"] == "test"


def test_D5b_rotate_keeps_multiple_backups(tmp_path: Path, monkeypatch):
    """W10-017.8.3 (TD3)：保留多份歷史（預設 3 份）— .1 → .2 → .3 滾動。"""
    import importlib
    mod = importlib.import_module("ticket_system.lib.checkpoint_state")
    monkeypatch.setattr(mod, "_METRICS_LOG_ROTATE_BYTES", 5)
    monkeypatch.setattr(mod, "_METRICS_LOG_ROTATE_KEEP", 3)

    log_path = tmp_path / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 第 1 次 rotate：原檔(gen=1) → .1
    log_path.write_text('{"gen":1}\n', encoding="utf-8")
    mod._write_metrics_log(_make_state(), "test", 1.0, {}, project_root=tmp_path)
    assert json.loads(log_path.with_suffix(".1.jsonl").read_text().splitlines()[0])["gen"] == 1

    # 第 2 次 rotate：新原檔(gen=2) → .1；舊 .1(gen=1) → .2
    log_path.write_text('{"gen":2}\n', encoding="utf-8")
    mod._write_metrics_log(_make_state(), "test", 1.0, {}, project_root=tmp_path)
    assert json.loads(log_path.with_suffix(".1.jsonl").read_text().splitlines()[0])["gen"] == 2
    assert json.loads(log_path.with_suffix(".2.jsonl").read_text().splitlines()[0])["gen"] == 1

    # 第 3 次 rotate：gen=3 → .1；gen=2 → .2；gen=1 → .3
    log_path.write_text('{"gen":3}\n', encoding="utf-8")
    mod._write_metrics_log(_make_state(), "test", 1.0, {}, project_root=tmp_path)
    assert json.loads(log_path.with_suffix(".1.jsonl").read_text().splitlines()[0])["gen"] == 3
    assert json.loads(log_path.with_suffix(".2.jsonl").read_text().splitlines()[0])["gen"] == 2
    assert json.loads(log_path.with_suffix(".3.jsonl").read_text().splitlines()[0])["gen"] == 1

    # 第 4 次 rotate：gen=4 → .1；gen=3 → .2；gen=2 → .3；gen=1 被丟棄
    log_path.write_text('{"gen":4}\n', encoding="utf-8")
    mod._write_metrics_log(_make_state(), "test", 1.0, {}, project_root=tmp_path)
    assert json.loads(log_path.with_suffix(".1.jsonl").read_text().splitlines()[0])["gen"] == 4
    assert json.loads(log_path.with_suffix(".2.jsonl").read_text().splitlines()[0])["gen"] == 3
    assert json.loads(log_path.with_suffix(".3.jsonl").read_text().splitlines()[0])["gen"] == 2
    # .4.jsonl 不應存在（keep=3）
    assert not log_path.with_suffix(".4.jsonl").exists()


# ---------------------------------------------------------------------------
# D6：caller 欄位正確標示呼叫端
# ---------------------------------------------------------------------------


def test_D6_caller_field_propagated(
    tmp_git_repo: Path, mock_ticket_query, frozen_time,
):
    mock_ticket_query(ids=[])
    checkpoint_state(
        ticket_id=None, log_metrics=True,
        caller="handoff-ready", project_root=tmp_git_repo,
    )
    log_path = tmp_git_repo / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    entry = json.loads(log_path.read_text().splitlines()[0])
    assert entry["caller"] == "handoff-ready"


# ---------------------------------------------------------------------------
# D7：data_source_errors 為 list[str]，非 truncate
# ---------------------------------------------------------------------------


def test_D7_data_source_errors_list_of_string(tmp_path: Path):
    state = _make_state()
    errors = {
        "git-status": "ok",
        "dispatch-active": "FileNotFoundError: .claude/state/dispatch-active.json",
        "handoff-pending": "PermissionError: denied",
    }
    _write_metrics_log(state, "snapshot", 12.5, errors, project_root=tmp_path)

    log_path = tmp_path / ".claude" / "logs" / "pm-automation-metrics.jsonl"
    entry = json.loads(log_path.read_text().splitlines()[0])
    assert isinstance(entry["data_source_errors"], list)
    assert all(isinstance(x, str) for x in entry["data_source_errors"])
    # 只含非 "ok" 的 source
    assert set(entry["data_source_errors"]) == {"dispatch-active", "handoff-pending"}
