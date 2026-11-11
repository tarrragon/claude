"""_finalize_sync 的新專案初始化提示指向 README〈首次安裝〉，不重列步驟（3.2.0-W1-141）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_finalize_hint", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_finalize_hint"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def test_init_hint_points_to_readme_without_steps(tmp_path, capsys):
    pull._finalize_sync(tmp_path)
    out = capsys.readouterr().out
    assert "首次安裝" in out
    assert ".claude/README.md" in out
    # 不重列步驟（舊提示含這些字串）
    assert "CLAUDE-template" not in out
    assert "填入專案特定資訊" not in out
