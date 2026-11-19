"""加法式 .skill-sync-ignore 標記的測試（3.4.0-W1-307.7）。

驗證三件事：標記目錄整棵子樹不進 push／pull／雜湊／prune；標記只增加排除，
遺失時退化為排除較少而名稱式排除照常生效；根層標記不合法，push／pull 拒絕。
每個排除斷言都附「同一 fixture 不放標記」的對照，避免標記退化為空操作時測試照綠。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skill_sync.cli as cli_module  # noqa: E402
from skill_sync.cli import (  # noqa: E402
    SKILL_SYNC_IGNORE_MARKER,
    _should_exclude_file,
    cmd_pull,
    cmd_push,
    compute_content_hash,
    compute_diff,
)


def _make_skill(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


# --- 標記檔本身 ---------------------------------------------------------------


def test_marker_file_excluded_by_name_at_any_depth():
    assert _should_exclude_file(SKILL_SYNC_IGNORE_MARKER) is True
    assert _should_exclude_file(f"notes/{SKILL_SYNC_IGNORE_MARKER}") is True
    assert _should_exclude_file("notes/plan.md") is False


# --- compute_diff ------------------------------------------------------------


def test_compute_diff_marker_excludes_subtree_from_added(tmp_path):
    files = {"SKILL.md": "x", "notes/plan.md": "local", "notes/deep/a.md": "local"}
    src = _make_skill(tmp_path / "src", {**files, f"notes/{SKILL_SYNC_IGNORE_MARKER}": ""})
    dst = tmp_path / "dst"

    diff = compute_diff(src, dst)

    assert diff["added"] == ["SKILL.md"]


def test_compute_diff_without_marker_includes_subtree_contrast(tmp_path):
    src = _make_skill(
        tmp_path / "src", {"SKILL.md": "x", "notes/plan.md": "local", "notes/deep/a.md": "local"}
    )

    diff = compute_diff(src, tmp_path / "dst")

    assert diff["added"] == ["SKILL.md", "notes/deep/a.md", "notes/plan.md"]


def test_compute_diff_marker_on_dst_side_protects_local_subtree(tmp_path):
    """pull 方向：標記在本地（dst），遠端（src）同路徑的檔不得覆蓋、本地檔不算 dst_only。"""
    src = _make_skill(tmp_path / "remote", {"SKILL.md": "x", "notes/plan.md": "upstream"})
    dst = _make_skill(
        tmp_path / "local",
        {
            "SKILL.md": "x",
            "notes/plan.md": "customized",
            "notes/mine.md": "local only",
            f"notes/{SKILL_SYNC_IGNORE_MARKER}": "",
        },
    )

    diff = compute_diff(src, dst)

    assert diff == {"added": [], "modified": [], "unchanged": ["SKILL.md"], "dst_only": []}


def test_compute_diff_without_dst_marker_reports_overwrite_contrast(tmp_path):
    src = _make_skill(tmp_path / "remote", {"SKILL.md": "x", "notes/plan.md": "upstream"})
    dst = _make_skill(
        tmp_path / "local",
        {"SKILL.md": "x", "notes/plan.md": "customized", "notes/mine.md": "local only"},
    )

    diff = compute_diff(src, dst)

    assert diff["modified"] == ["notes/plan.md"]
    assert diff["dst_only"] == ["notes/mine.md"]


def test_marker_loss_degrades_to_less_exclusion_name_based_still_holds(tmp_path):
    """加法式：標記遺失只讓被標記的子樹回到同步，名稱式排除成員照常排除。"""
    src = _make_skill(
        tmp_path / "src",
        {
            "SKILL.md": "x",
            "notes/plan.md": "local",
            "project-integration/local.yaml": "per project",
            "notes/.env": "TOKEN=x",
        },
    )

    diff = compute_diff(src, tmp_path / "dst")

    assert diff["added"] == ["SKILL.md", "notes/plan.md"]


def test_marker_cannot_reduce_name_based_exclusion(tmp_path):
    """標記放在名稱式排除目錄內也只是多一層排除，不會讓該目錄回到同步。"""
    src = _make_skill(
        tmp_path / "src",
        {
            "SKILL.md": "x",
            "project-integration/local.yaml": "per project",
            f"project-integration/{SKILL_SYNC_IGNORE_MARKER}": "",
        },
    )

    diff = compute_diff(src, tmp_path / "dst")

    assert diff["added"] == ["SKILL.md"]


# --- compute_content_hash ----------------------------------------------------


def test_content_hash_ignores_marked_subtree_and_marker(tmp_path):
    plain = _make_skill(tmp_path / "plain", {"SKILL.md": "x"})
    marked = _make_skill(
        tmp_path / "marked",
        {"SKILL.md": "x", "notes/plan.md": "local", f"notes/{SKILL_SYNC_IGNORE_MARKER}": ""},
    )

    assert compute_content_hash(marked) == compute_content_hash(plain)


def test_content_hash_counts_subtree_without_marker_contrast(tmp_path):
    plain = _make_skill(tmp_path / "plain", {"SKILL.md": "x"})
    unmarked = _make_skill(tmp_path / "unmarked", {"SKILL.md": "x", "notes/plan.md": "local"})

    assert compute_content_hash(unmarked) != compute_content_hash(plain)


# --- cmd_push / cmd_pull -------------------------------------------------------


class _Args:
    def __init__(self, name, force=True, prune=False, message=None):
        self.name = name
        self.force = force
        self.prune = prune
        self.message = message


def _stub_git(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    class _Done:
        returncode = 1
        stdout = ""
        stderr = ""

    def _fake_run_git(args, cwd=None):
        calls.append(args)
        return _Done()

    monkeypatch.setattr(cli_module, "run_git", _fake_run_git)
    monkeypatch.setattr(cli_module.subprocess, "run", lambda *a, **k: _Done())
    monkeypatch.setattr(cli_module, "update_sync_manifest", lambda tmp: None)
    return calls


def _stub_tempdir(monkeypatch, scratch: Path) -> None:
    @contextlib.contextmanager
    def _fixed():
        yield str(scratch)

    monkeypatch.setattr(cli_module.tempfile, "TemporaryDirectory", _fixed)


def test_cmd_push_skips_marked_subtree_and_keeps_remote_copy_on_prune(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    _make_skill(
        skills_dir / "demo",
        {"SKILL.md": "new", "notes/plan.md": "local", f"notes/{SKILL_SYNC_IGNORE_MARKER}": ""},
    )
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)
    scratch = tmp_path / "scratch"
    remote = _make_skill(scratch / "repo" / "demo", {"SKILL.md": "old", "notes/old.md": "pushed earlier"})
    _stub_tempdir(monkeypatch, scratch)
    _stub_git(monkeypatch)

    cmd_push(_Args("demo", prune=True))

    assert (remote / "SKILL.md").read_text() == "new"
    assert not (remote / "notes" / "plan.md").exists()
    assert not (remote / "notes" / SKILL_SYNC_IGNORE_MARKER).exists()
    assert (remote / "notes" / "old.md").exists()


def test_cmd_push_rejects_root_level_marker(tmp_path, monkeypatch, capsys):
    skills_dir = tmp_path / "skills"
    _make_skill(skills_dir / "demo", {"SKILL.md": "x", SKILL_SYNC_IGNORE_MARKER: ""})
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)
    calls = _stub_git(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        cmd_push(_Args("demo"))

    assert exc.value.code == 1
    assert calls == []
    assert SKILL_SYNC_IGNORE_MARKER in capsys.readouterr().err


def test_cmd_pull_rejects_root_level_marker(tmp_path, monkeypatch, capsys):
    skills_dir = tmp_path / "skills"
    _make_skill(skills_dir / "demo", {"SKILL.md": "local", SKILL_SYNC_IGNORE_MARKER: ""})
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)
    calls = _stub_git(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        cmd_pull(_Args("demo"))

    assert exc.value.code == 1
    assert calls == []
    assert (skills_dir / "demo" / "SKILL.md").read_text() == "local"
    assert SKILL_SYNC_IGNORE_MARKER in capsys.readouterr().err


def test_cmd_pull_keeps_marked_local_subtree(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    local = _make_skill(
        skills_dir / "demo",
        {"SKILL.md": "old", "notes/plan.md": "customized", f"notes/{SKILL_SYNC_IGNORE_MARKER}": ""},
    )
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)
    scratch = tmp_path / "scratch"
    _make_skill(scratch / "repo" / "demo", {"SKILL.md": "new", "notes/plan.md": "upstream"})
    _stub_tempdir(monkeypatch, scratch)
    _stub_git(monkeypatch)

    cmd_pull(_Args("demo"))

    assert (local / "SKILL.md").read_text() == "new"
    assert (local / "notes" / "plan.md").read_text() == "customized"
