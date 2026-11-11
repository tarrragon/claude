"""全量 overlay 確認提示中止後的結束碼與收尾（3.2.0-W1-127）。

E1 對照：同一 fixture 下，stdin 為 EOF（中止）與回答 y（套用）的結束碼、
成功訊息、基準點寫入必須各自不同。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_overlay_abort", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_overlay_abort"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

SUCCESS_MSG = "成功拉取 .claude 更新"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _setup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    upstream = tmp_path / "upstream"
    (upstream / "rules").mkdir(parents=True)
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@t.t"], upstream)
    _git(["config", "user.name", "t"], upstream)
    (upstream / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    _git(["add", "-A"], upstream)
    _git(["commit", "-q", "-m", "base"], upstream)

    project_root = tmp_path / "proj"
    (project_root / ".claude" / "rules").mkdir(parents=True)
    (project_root / ".claude" / "rules" / "keep.md").write_text("old\n", encoding="utf-8")
    # 無 .sync-state.json → 全量 overlay；本地內容不同 → 預覽有覆蓋 → 觸發確認

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "_validate_environment", lambda _p: None)
    monkeypatch.setattr(
        pull, "_clone_and_backup",
        lambda root: (upstream, pull._sync_with_backup(root, upstream)),
    )
    monkeypatch.setattr(pull, "_update_project_templates", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "cleanup_legacy_github_dir", lambda *_a, **_k: [])
    monkeypatch.setattr(pull, "cleanup_old_backups", lambda *_a, **_k: 0)
    monkeypatch.setattr(pull, "auto_register_hooks", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "verify_local_settings_no_hooks", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "verify_hook_imports", lambda *_a, **_k: 0)
    monkeypatch.setattr(pull, "check_conflict_marker_residue", lambda *_a, **_k: 0)
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])
    return project_root, upstream


def _run_main(capsys) -> tuple[int, str]:
    rc = 0
    try:
        pull.main()
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 1
    return rc, capsys.readouterr().out


def _base_written(project_root: Path) -> bool:
    state = project_root / ".claude" / ".sync-state.json"
    return state.exists() and "last_synced_base_sha" in json.loads(state.read_text("utf-8"))


def test_eof_aborts_nonzero_without_success_or_base(tmp_path, monkeypatch, capsys) -> None:
    project_root, _ = _setup(tmp_path, monkeypatch)

    def _eof(*_a, **_k):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    rc, out = _run_main(capsys)

    assert rc != 0
    assert SUCCESS_MSG not in out
    assert "拉取已中止" in out and "重跑" in out
    assert not _base_written(project_root)
    assert (project_root / ".claude" / "rules" / "keep.md").read_text("utf-8") == "old\n"


def test_answer_y_applies_zero_exit_success_and_base(tmp_path, monkeypatch, capsys) -> None:
    project_root, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")
    rc, out = _run_main(capsys)

    assert rc == 0
    assert SUCCESS_MSG in out
    assert "拉取已中止" not in out
    assert _base_written(project_root)
    assert (project_root / ".claude" / "rules" / "keep.md").read_text("utf-8") == "keep\n"


@pytest.mark.parametrize("answer", ["", "n", "no"])
def test_declined_answers_abort_nonzero(tmp_path, monkeypatch, capsys, answer) -> None:
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: answer)
    rc, out = _run_main(capsys)
    assert rc != 0
    assert SUCCESS_MSG not in out
