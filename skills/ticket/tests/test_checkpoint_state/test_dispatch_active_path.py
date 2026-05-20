"""W16-006 回歸測試：_DISPATCH_ACTIVE_RELPATH 路徑修正。

驗證 checkpoint_state.py 讀取 dispatch-active.json 的路徑為 .claude/dispatch-active.json
（而非 .claude/state/dispatch-active.json）。

歷史背景：W10-017.2 實作時發現 hardcoded .claude/state/dispatch-active.json 但實際檔案
位於 .claude/dispatch-active.json，導致 checkpoint_state() 永遠走 fail-open fallback
而非讀到真實資料。
"""

from __future__ import annotations

import json
from pathlib import Path

from ticket_system.lib.checkpoint_state import (
    _DISPATCH_ACTIVE_RELPATH,
    _read_dispatch_active,
)


def test_dispatch_active_relpath_constant():
    """常數路徑應為 .claude/dispatch-active.json，無 state/ 中間層。"""
    assert _DISPATCH_ACTIVE_RELPATH == Path(".claude/dispatch-active.json")


def test_read_dispatch_active_integration(tmp_path: Path):
    """整合測試：在 tmp_path/.claude/dispatch-active.json 建立 fixture，
    驗證 _read_dispatch_active 能正確讀取並計算 active_agents。
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    fixture = {
        "dispatches": [
            {"status": "active"},
            {"status": "completed"},
        ]
    }
    (claude_dir / "dispatch-active.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )

    active_agents, raw = _read_dispatch_active(project_root=tmp_path)

    assert active_agents == 1
    assert isinstance(raw, dict)
    assert raw == fixture
