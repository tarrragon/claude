"""pull／push 的 [y/N] 確認被取消時以非零結束（3.4.0-W1-310.1）。

取消的三種情形：回答非 y、EOFError（非互動呼叫的 stdin 已關閉）、KeyboardInterrupt。
原本三者都印 Aborted 後以結束碼 0 返回，呼叫端無法從結束碼分辨「已套用」與「未套用」。
每組都附回答 y 的對照，避免改動退化為一律非零時測試照綠。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skill_sync.cli as cli_module  # noqa: E402
from skill_sync.cli import ABORT_EXIT_CODE, cmd_pull, cmd_push  # noqa: E402


class _Args:
    def __init__(self, name):
        self.name = name
        self.force = False
        self.discard_local = False
        self.prune = False
        self.message = None


class _Done:
    returncode = 1
    stdout = ""
    stderr = ""


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _setup(tmp_path, monkeypatch) -> tuple[Path, Path]:
    skills_dir = tmp_path / "skills"
    local = skills_dir / "demo"
    _write(local, {"SKILL.md": "local"})
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote = scratch / "repo" / "demo"
    _write(remote, {"SKILL.md": "remote"})

    @contextlib.contextmanager
    def _fixed():
        yield str(scratch)

    monkeypatch.setattr(cli_module.tempfile, "TemporaryDirectory", _fixed)
    monkeypatch.setattr(cli_module, "run_git", lambda args, cwd=None: _Done())
    monkeypatch.setattr(cli_module.subprocess, "run", lambda *a, **k: _Done())
    monkeypatch.setattr(cli_module, "update_sync_manifest", lambda tmp: None)
    return local, remote


def _answer(value):
    def _input(prompt=""):
        if isinstance(value, BaseException) or (
            isinstance(value, type) and issubclass(value, BaseException)
        ):
            raise value
        return value

    return _input


CANCELLATIONS = [
    pytest.param("n", id="answer-n"),
    pytest.param("", id="answer-empty"),
    pytest.param(EOFError, id="eof"),
    pytest.param(KeyboardInterrupt, id="keyboard-interrupt"),
]


def test_abort_exit_code_is_nonzero():
    assert ABORT_EXIT_CODE != 0


# --- pull --------------------------------------------------------------------


@pytest.mark.parametrize("answer", CANCELLATIONS)
def test_pull_cancelled_exits_nonzero_and_keeps_local(tmp_path, monkeypatch, capsys, answer):
    local, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", _answer(answer))

    with pytest.raises(SystemExit) as exc:
        cmd_pull(_Args("demo"))

    assert exc.value.code == ABORT_EXIT_CODE
    assert (local / "SKILL.md").read_text() == "local"
    assert "Aborted" in capsys.readouterr().err


def test_pull_confirmed_applies_and_returns_contrast(tmp_path, monkeypatch):
    local, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", _answer("y"))

    cmd_pull(_Args("demo"))

    assert (local / "SKILL.md").read_text() == "remote"


# --- push --------------------------------------------------------------------


@pytest.mark.parametrize("answer", CANCELLATIONS)
def test_push_cancelled_exits_nonzero_and_keeps_remote(tmp_path, monkeypatch, capsys, answer):
    _, remote = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", _answer(answer))

    with pytest.raises(SystemExit) as exc:
        cmd_push(_Args("demo"))

    assert exc.value.code == ABORT_EXIT_CODE
    assert (remote / "SKILL.md").read_text() == "remote"
    assert "Aborted" in capsys.readouterr().err


def test_push_confirmed_applies_and_returns_contrast(tmp_path, monkeypatch):
    _, remote = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", _answer("y"))

    cmd_push(_Args("demo"))

    assert (remote / "SKILL.md").read_text() == "local"
