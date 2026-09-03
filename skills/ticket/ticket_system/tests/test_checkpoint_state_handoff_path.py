"""迴歸測試：checkpoint_state handoff pending 目錄路徑正確性（0.2.1-W3-310）。

背景：_HANDOFF_PENDING_RELDIR 曾誤寫為 .claude/handoffs/pending（多一個 s），
實際目錄為 .claude/handoff/pending（比照 constants.HANDOFF_DIR /
HANDOFF_PENDING_SUBDIR）。錯字使 _read_handoff_pending 恆讀不到目錄、
active_handoff 恆為 None、PriorityRule C2（handoff 就緒）從未觸發。

本檔驗證：
1. _HANDOFF_PENDING_RELDIR 與 constants.HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
   結構一致（防止路徑字面再次漂移）。
2. _read_handoff_pending 對真實 .claude/handoff/pending/*.json 能正確讀出
   ticket_id。
3. checkpoint_state() 在有 pending handoff 且無更高優先級狀態時，
   active_handoff 非 None 且 current_phase 為 "2"（PriorityRule C2 觸發，
   對應本票 acceptance 第 2 項）。

Sociable Unit Tests 原則（與 tests/test_checkpoint_state/conftest.py 一致）：
mock subprocess.run（git / ticket CLI 呼叫端），不 mock 業務函式本體。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import checkpoint_state as checkpoint_state_mod
from ticket_system.lib.checkpoint_state import (
    _HANDOFF_PENDING_RELDIR,
    _read_handoff_pending,
    checkpoint_state,
)
from ticket_system.lib.constants import HANDOFF_DIR, HANDOFF_PENDING_SUBDIR


def test_handoff_pending_reldir_matches_constants_source_of_truth() -> None:
    """_HANDOFF_PENDING_RELDIR 須與 HANDOFF_DIR / HANDOFF_PENDING_SUBDIR 描述
    同一個實體目錄，非曾經誤寫的 .claude/handoffs/pending（多一個 s）。"""
    assert _HANDOFF_PENDING_RELDIR == Path(HANDOFF_DIR) / HANDOFF_PENDING_SUBDIR
    assert "handoffs" not in _HANDOFF_PENDING_RELDIR.parts


def test_read_handoff_pending_finds_ticket_id_in_correct_directory(
    tmp_path: Path,
) -> None:
    """路徑字面修正後，_read_handoff_pending 應能在 .claude/handoff/pending/
    找到真實寫入的 handoff json。"""
    pending_dir = tmp_path / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
    pending_dir.mkdir(parents=True)
    (pending_dir / "T1.json").write_text(
        json.dumps({"ticket_id": "T1"}), encoding="utf-8"
    )

    assert _read_handoff_pending(tmp_path) == "T1"


def _fake_subprocess_run(argv: list, **_kwargs) -> "subprocess.CompletedProcess[str]":
    """統一攔截 checkpoint_state 內三個 subprocess.run 呼叫端（git status /
    git worktree / ticket query），使其確定性走 SAFE_CALL fallback，只留
    handoff-pending 這條真實資料源決定測試結果。"""
    if argv[:2] == ["git", "status"] or argv[:2] == ["git", "worktree"]:
        raise subprocess.CalledProcessError(128, argv)
    if argv[:1] == ["ticket"]:
        raise FileNotFoundError("ticket CLI not mocked in this test")
    raise AssertionError(f"unexpected subprocess.run call in test: {argv}")


def test_checkpoint_state_active_handoff_non_none_triggers_priority_c2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2：active_handoff 在有 pending handoff 時非 None，PriorityRule C2
    （current_phase == "2"）可觸發。"""
    monkeypatch.setattr(checkpoint_state_mod.subprocess, "run", _fake_subprocess_run)

    pending_dir = tmp_path / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
    pending_dir.mkdir(parents=True)
    (pending_dir / "T2.json").write_text(
        json.dumps({"ticket_id": "T2"}), encoding="utf-8"
    )

    state = checkpoint_state(
        ticket_id=None,
        log_metrics=False,
        project_root=tmp_path,
    )

    assert state.active_handoff == "T2"
    assert state.current_phase == "2"
