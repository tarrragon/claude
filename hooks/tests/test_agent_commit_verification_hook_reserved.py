"""agent-commit-verification-hook 保留分支提醒測試。

正反對照：
- 保留分支（票 pending）的 worktree 未合併 → 資訊行，無「[強制] 合併後」字樣
- 非保留（in_progress／判不出）的 worktree 未合併 → 仍有「[強制] 合併後」字樣
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "agent-commit-verification-hook.py"


@pytest.fixture
def hook_mod():
    spec = importlib.util.spec_from_file_location("agent_commit_verification_hook_rsv", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(hook_mod, monkeypatch, capsys, tmp_path, reservations):
    wt = hook_mod.WorktreeItems("/wt/x", "feat/3.3.0-W1-007", ["abc1234 c"])
    monkeypatch.setattr(hook_mod, "_lookup_agent_info", lambda *a, **kw: ("agent-X", False))
    monkeypatch.setattr(hook_mod, "get_uncommitted_files", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_worktrees", lambda *a, **kw: [wt])
    monkeypatch.setattr(hook_mod, "get_unmerged_feature_branches", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "scan_hook_errors", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        hook_mod, "_get_error_dedup_state_file", lambda root: tmp_path / "dedup.json"
    )
    import lib.reserved_branch as rb

    monkeypatch.setattr(rb, "find_reservation", lambda branch, root, logger: reservations.get(branch))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"agent_id": "agent-xyz", "stop_hook_active": False})))
    with pytest.raises(SystemExit):
        hook_mod.main()
    out = capsys.readouterr().out
    return json.loads(out)["systemMessage"] if out.strip() else ""


def test_reserved_branch_listed_as_info_without_mandatory(hook_mod, monkeypatch, capsys, tmp_path):
    msg = _run(hook_mod, monkeypatch, capsys, tmp_path, {"feat/3.3.0-W1-007": "3.4.0-W1-214"})
    assert "保留給票 3.4.0-W1-214" in msg
    assert "[強制] 合併後" not in msg


def test_non_reserved_branch_still_mandatory(hook_mod, monkeypatch, capsys, tmp_path):
    msg = _run(hook_mod, monkeypatch, capsys, tmp_path, {})
    assert "[強制] 合併後才能進行 ticket complete" in msg
