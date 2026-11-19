"""帶 .skill-sync-override 的 skill：pull 保護與 push 警告（3.4.0-W1-307.8）。

結束碼、被擋條件與逃生閥：
- `pull <name>`：本地 skill 根層有標記時以結束碼 1 拒絕，在 clone 前停下；`--force` 單獨不解除。
- `pull <name> --discard-local`：解除保護，仍進 [y/N] 確認。
- `pull <name> --discard-local --force`：解除保護並略過確認。
- `push <name>`：只寫 stderr 警告，不阻擋。
每個被擋的情境都附「不放標記」或「帶逃生旗標」的對照，避免保護退化為空操作時測試照綠。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skill_sync.cli as cli_module  # noqa: E402
from skill_sync.cli import (  # noqa: E402
    SKILL_SYNC_OVERRIDE_MARKER,
    build_parser,
    cmd_pull,
    cmd_push,
)


def _make_skill(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


class _Args:
    def __init__(self, name, force=False, discard_local=False, prune=False, message=None):
        self.name = name
        self.force = force
        self.discard_local = discard_local
        self.prune = prune
        self.message = message


class _Done:
    returncode = 1
    stdout = ""
    stderr = ""


def _setup(tmp_path, monkeypatch, *, marker: bool) -> tuple[Path, list[list[str]]]:
    skills_dir = tmp_path / "skills"
    files = {"SKILL.md": "customized"}
    if marker:
        files[SKILL_SYNC_OVERRIDE_MARKER] = "deliberate fork"
    local = _make_skill(skills_dir / "demo", files)
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    _make_skill(scratch / "repo" / "demo", {"SKILL.md": "upstream"})

    @contextlib.contextmanager
    def _fixed():
        yield str(scratch)

    monkeypatch.setattr(cli_module.tempfile, "TemporaryDirectory", _fixed)

    calls: list[list[str]] = []

    def _fake_run_git(args, cwd=None):
        calls.append(args)
        return _Done()

    monkeypatch.setattr(cli_module, "run_git", _fake_run_git)
    monkeypatch.setattr(cli_module.subprocess, "run", lambda *a, **k: _Done())
    monkeypatch.setattr(cli_module, "update_sync_manifest", lambda tmp: None)
    return local, calls


def _forbid_prompt(monkeypatch) -> None:
    def _no_input(prompt=""):
        raise AssertionError(f"unexpected confirmation prompt: {prompt!r}")

    monkeypatch.setattr("builtins.input", _no_input)


# --- pull 被擋 ----------------------------------------------------------------


def test_pull_with_override_marker_refuses_before_clone(tmp_path, monkeypatch, capsys):
    local, calls = _setup(tmp_path, monkeypatch, marker=True)

    with pytest.raises(SystemExit) as exc:
        cmd_pull(_Args("demo"))

    assert exc.value.code == 1
    assert calls == []
    assert (local / "SKILL.md").read_text() == "customized"
    err = capsys.readouterr().err
    assert str(local / SKILL_SYNC_OVERRIDE_MARKER) in err
    assert "skill-sync pull demo --discard-local" in err
    assert "skill-sync pull demo --discard-local --force" in err


def test_pull_with_override_marker_force_alone_still_refuses(tmp_path, monkeypatch):
    local, calls = _setup(tmp_path, monkeypatch, marker=True)

    with pytest.raises(SystemExit) as exc:
        cmd_pull(_Args("demo", force=True))

    assert exc.value.code == 1
    assert calls == []
    assert (local / "SKILL.md").read_text() == "customized"


def test_pull_without_marker_force_overwrites_contrast(tmp_path, monkeypatch):
    local, _ = _setup(tmp_path, monkeypatch, marker=False)
    _forbid_prompt(monkeypatch)

    cmd_pull(_Args("demo", force=True))

    assert (local / "SKILL.md").read_text() == "upstream"


# --- 逃生閥 ------------------------------------------------------------------


def test_pull_discard_local_asks_confirmation_and_applies_on_yes(tmp_path, monkeypatch):
    local, _ = _setup(tmp_path, monkeypatch, marker=True)
    prompts: list[str] = []

    def _yes(prompt=""):
        prompts.append(prompt)
        return "y"

    monkeypatch.setattr("builtins.input", _yes)

    cmd_pull(_Args("demo", discard_local=True))

    assert len(prompts) == 1
    assert (local / "SKILL.md").read_text() == "upstream"
    assert (local / SKILL_SYNC_OVERRIDE_MARKER).exists()


def test_pull_discard_local_declined_keeps_local(tmp_path, monkeypatch):
    local, _ = _setup(tmp_path, monkeypatch, marker=True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    # 確認被拒時以非零結束（取消結束碼見 test_confirm_abort_exit.py）
    with pytest.raises(SystemExit) as exc:
        cmd_pull(_Args("demo", discard_local=True))

    assert exc.value.code != 0
    assert (local / "SKILL.md").read_text() == "customized"


def test_pull_discard_local_with_force_skips_confirmation(tmp_path, monkeypatch):
    local, _ = _setup(tmp_path, monkeypatch, marker=True)
    _forbid_prompt(monkeypatch)

    cmd_pull(_Args("demo", force=True, discard_local=True))

    assert (local / "SKILL.md").read_text() == "upstream"


def test_parser_accepts_discard_local_on_pull_only():
    parser = build_parser()
    assert parser.parse_args(["pull", "demo", "--discard-local"]).discard_local is True
    assert parser.parse_args(["pull", "demo"]).discard_local is False
    with pytest.raises(SystemExit):
        parser.parse_args(["push", "demo", "--discard-local"])


# --- push 只警告 -------------------------------------------------------------


def test_push_with_override_marker_warns_but_pushes(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, marker=True)
    remote = tmp_path / "scratch" / "repo" / "demo"

    cmd_push(_Args("demo", force=True))

    assert (remote / "SKILL.md").read_text() == "customized"
    assert not (remote / SKILL_SYNC_OVERRIDE_MARKER).exists()
    assert SKILL_SYNC_OVERRIDE_MARKER in capsys.readouterr().err


def test_push_without_marker_has_no_override_warning_contrast(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, marker=False)

    cmd_push(_Args("demo", force=True))

    assert SKILL_SYNC_OVERRIDE_MARKER not in capsys.readouterr().err
