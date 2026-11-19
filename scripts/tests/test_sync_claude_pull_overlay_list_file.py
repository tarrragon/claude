"""全量 overlay dry-run 完整清單檔（3.4.0-W1-320）。

E1 對照：超過 50 條時 stdout 截斷而清單檔含全部；50 條以內時兩者條目一致。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sync_claude_pull_overlay_abort as base  # noqa: E402

pull = base.pull
LIST_PREFIX = "[dry-run] 完整清單檔: "


def _populate(project_root: Path, upstream: Path, count: int) -> None:
    for i in range(count):
        name = f"f{i:03d}.md"
        (upstream / "rules" / name).write_text("new\n", encoding="utf-8")
        (project_root / ".claude" / "rules" / name).write_text("old\n", encoding="utf-8")
    base._git(["add", "-A"], upstream)
    base._git(["commit", "-q", "-m", "more"], upstream)


def _run(tmp_path, monkeypatch, capsys, count):
    project_root, upstream = base._setup(tmp_path, monkeypatch)
    _populate(project_root, upstream, count)
    base._tty(monkeypatch, False)
    rc, raw_out = base._run_main(capsys)
    out = re.sub(r"\x1b\[[0-9;]*m", "", raw_out)
    list_line = next(ln for ln in out.splitlines() if LIST_PREFIX in ln)
    list_file = Path(list_line.split(LIST_PREFIX, 1)[1].strip())
    stdout_items = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("~ ")]
    return project_root, rc, list_file, stdout_items


def _file_items(list_file: Path) -> list[str]:
    return [ln for ln in list_file.read_text("utf-8").splitlines() if ln.startswith("~ ")]


def test_over_50_stdout_truncated_file_complete(tmp_path, monkeypatch, capsys) -> None:
    project_root, rc, list_file, stdout_items = _run(tmp_path, monkeypatch, capsys, 60)
    assert rc == pull.EXIT_CONFIRM_REQUIRED
    assert len(stdout_items) == 50
    assert len(_file_items(list_file)) == 61  # 60 + keep.md
    assert list_file.parent.name.startswith("claude-backup-")
    assert "target SHA:" in list_file.read_text("utf-8")
    # 中止時 .claude/ 未被寫入
    assert (project_root / ".claude" / "rules" / "keep.md").read_text("utf-8") == "old\n"
    assert not list(project_root.rglob("overlay-dry-run-list.txt"))


def test_up_to_50_stdout_and_file_match(tmp_path, monkeypatch, capsys) -> None:
    _root, rc, list_file, stdout_items = _run(tmp_path, monkeypatch, capsys, 10)
    assert rc == pull.EXIT_CONFIRM_REQUIRED
    assert sorted(stdout_items) == sorted(_file_items(list_file))
    assert len(stdout_items) == 11
