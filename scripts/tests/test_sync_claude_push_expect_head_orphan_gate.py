#!/usr/bin/env python3
"""--expect-head 釘選推送 HEAD；真孤兒存在時要求明示 --clean 或 --no-clean。

- --expect-head：一致放行；不一致非零結束並列出差異 commit；不帶旗標行為不變。
- 真孤兒：有清單且兩個旗標都沒帶時，推送前非零結束；無孤兒或已明示時放行。
每組都附放行的對照，避免檢查退化為一律放行或一律阻擋時測試照綠。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_gate", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_gate"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, list[str]]:
    repo = tmp_path / "proj"
    (repo / ".claude").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    shas = []
    for i in range(3):
        (repo / ".claude" / f"f{i}.md").write_text(str(i), encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", f"c{i}")
        shas.append(_git(repo, "rev-parse", "HEAD"))
    return repo, shas


# --- 旗標解析 -----------------------------------------------------------------


def test_parse_args_accepts_expect_head_and_no_clean():
    args = sync_mod.parse_args(["--expect-head", "abc123", "--no-clean"])
    assert args.expect_head == "abc123"
    assert args.no_clean is True


def test_parse_args_defaults_contrast():
    args = sync_mod.parse_args([])
    assert args.expect_head is None
    assert args.no_clean is False


def test_parse_args_rejects_clean_with_no_clean():
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["--clean", "--no-clean"])
    assert exc.value.code == 2


# --- --expect-head ------------------------------------------------------------


def test_expect_head_matching_passes(tmp_path):
    repo, shas = _repo(tmp_path)
    sync_mod.check_expect_head(repo, "HEAD", shas[-1])


def test_expect_head_short_sha_matching_passes(tmp_path):
    repo, shas = _repo(tmp_path)
    sync_mod.check_expect_head(repo, "HEAD", shas[-1][:9])


def test_expect_head_mismatch_exits_and_lists_commits(tmp_path, capsys):
    repo, shas = _repo(tmp_path)

    with pytest.raises(SystemExit) as exc:
        sync_mod.check_expect_head(repo, "HEAD", shas[0])

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "c1" in out and "c2" in out


def test_expect_head_unresolvable_exits(tmp_path):
    repo, _ = _repo(tmp_path)

    with pytest.raises(SystemExit) as exc:
        sync_mod.check_expect_head(repo, "HEAD", "deadbeefdeadbeef")

    assert exc.value.code == 1


def test_expect_head_absent_is_noop(tmp_path):
    repo, _ = _repo(tmp_path)
    sync_mod.check_expect_head(repo, "HEAD", None)


def test_expect_head_follows_ref(tmp_path):
    repo, shas = _repo(tmp_path)
    sync_mod.check_expect_head(repo, shas[1], shas[1])
    with pytest.raises(SystemExit):
        sync_mod.check_expect_head(repo, shas[1], shas[-1])


# --- 真孤兒要求明示 -----------------------------------------------------------


def test_orphans_without_flags_exit_before_push(capsys):
    with pytest.raises(SystemExit) as exc:
        sync_mod.require_orphan_decision(
            ["rules/old.md"], clean_mode=False, no_clean=False, clean_would_abort=False
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "rules/old.md" in out
    assert "--clean" in out and "--no-clean" in out


def test_orphans_with_no_clean_pass():
    sync_mod.require_orphan_decision(
        ["rules/old.md"], clean_mode=False, no_clean=True, clean_would_abort=False
    )


def test_orphans_with_clean_pass():
    sync_mod.require_orphan_decision(
        ["rules/old.md"], clean_mode=True, no_clean=False, clean_would_abort=False
    )


def test_no_orphans_without_flags_pass():
    sync_mod.require_orphan_decision(
        [], clean_mode=False, no_clean=False, clean_would_abort=False
    )


def test_orphans_with_unreachable_base_suggest_no_clean(capsys):
    with pytest.raises(SystemExit):
        sync_mod.require_orphan_decision(
            ["rules/old.md"], clean_mode=False, no_clean=False, clean_would_abort=True
        )

    assert "--no-clean" in capsys.readouterr().out
