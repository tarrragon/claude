"""preserve 清單內的檔有上游 delta 時，stderr 摘要列出（3.4.0-W1-301）。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_preserve_warn", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_preserve_warn"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _commit_all(repo, msg):
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _setup(tmp_path):
    up = tmp_path / "upstream"
    up.mkdir()
    _git(["init", "-q"], up)
    _git(["config", "user.email", "t@t.t"], up)
    _git(["config", "user.name", "t"], up)
    _git(["config", "commit.gpgsign", "false"], up)
    (up / "rules").mkdir()
    (up / "rules" / "pinned.md").write_text("base\n", encoding="utf-8")
    (up / "rules" / "quiet.md").write_text("base\n", encoding="utf-8")
    (up / "rules" / "other.md").write_text("base\n", encoding="utf-8")
    base = _commit_all(up, "base")
    (up / "rules" / "pinned.md").write_text("upstream change\n", encoding="utf-8")
    (up / "rules" / "other.md").write_text("upstream other\n", encoding="utf-8")
    _commit_all(up, "head")
    proj = tmp_path / "proj"
    rules = proj / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "pinned.md").write_text("LOCAL\n", encoding="utf-8")
    (rules / "quiet.md").write_text("base\n", encoding="utf-8")
    (rules / "other.md").write_text("base\n", encoding="utf-8")
    return proj, up, base


def test_preserve_with_upstream_delta_listed_and_local_unchanged(tmp_path, capsys):
    proj, up, base = _setup(tmp_path)
    pull.apply_upstream_delta(proj, up, base, preserve={"rules/pinned.md", "rules/quiet.md"})
    err = capsys.readouterr().err
    assert "rules/pinned.md" in err and "修改" in err
    assert (proj / ".claude" / "rules" / "pinned.md").read_text() == "LOCAL\n"


def test_preserve_without_upstream_delta_not_listed(tmp_path, capsys):
    proj, up, base = _setup(tmp_path)
    pull.apply_upstream_delta(proj, up, base, preserve={"rules/pinned.md", "rules/quiet.md"})
    err = capsys.readouterr().err
    assert "rules/quiet.md" not in err
    assert "rules/other.md" not in err


def test_no_preserve_hit_prints_no_summary(tmp_path, capsys):
    proj, up, base = _setup(tmp_path)
    pull.apply_upstream_delta(proj, up, base, preserve={"rules/quiet.md"})
    assert "preserve 清單內" not in capsys.readouterr().err
