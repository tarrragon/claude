"""sync-claude-push：dry-run 預覽 --clean 刪除範圍、同版號只做 --clean 的清理推送。

涵蓋：
  - plan_clean_deletions 與 clean_stale_files 共用判定：dry-run 列出的刪除即實際刪除
  - dry-run 預覽在 base 可達時列出刪除、不可達時明示 --clean 會中止（E1 對照）
  - 同版號清理推送的四道閘門：版號、tag 位置、只含刪除、tag 移動，各含該紅的對照（E2）
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_same_version_clean", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_same_version_clean"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "-b", "main"], path)
    _git(["config", "user.email", "t@example.com"], path)
    _git(["config", "user.name", "t"], path)


def _commit_all(path: Path, msg: str) -> str:
    _git(["add", "-A"], path)
    _git(["commit", "-q", "-m", msg], path)
    return _git(["rev-parse", "HEAD"], path)


# ---------- dry-run 預覽與實際刪除一致 ----------


@pytest.fixture
def push_scene(tmp_path: Path) -> dict:
    """本地已 git rm gone.md；上游 base 有 keep/gone，base 之後他方新增 other.md。"""
    project = tmp_path / "project"
    _init(project)
    claude = project / ".claude"
    claude.mkdir()
    (claude / "keep.md").write_text("k\n", encoding="utf-8")
    (claude / "gone.md").write_text("g\n", encoding="utf-8")
    _commit_all(project, "seed")
    (claude / "gone.md").unlink()
    _commit_all(project, "remove gone")

    upstream = tmp_path / "upstream"
    _init(upstream)
    (upstream / "keep.md").write_text("k\n", encoding="utf-8")
    (upstream / "gone.md").write_text("g\n", encoding="utf-8")
    base_sha = _commit_all(upstream, "base")
    (upstream / "other.md").write_text("o\n", encoding="utf-8")
    _commit_all(upstream, "other consumer adds")
    return {"project": project, "claude": claude, "upstream": upstream, "base": base_sha}


def _write_base(claude: Path, sha: str) -> None:
    (claude / sync_mod.SYNC_STATE_FILENAME).write_text(
        json.dumps({sync_mod.BASE_SHA_FIELD: sha}), encoding="utf-8"
    )


def test_dry_run_plan_lists_true_orphan_only(push_scene: dict, capsys):
    _write_base(push_scene["claude"], push_scene["base"])
    plan = sync_mod._dry_run_report_clean_plan(
        push_scene["project"], push_scene["upstream"], "HEAD"
    )
    assert plan is not None
    assert [rel for rel, _ in plan.deletions] == ["gone.md"]
    out = capsys.readouterr().out
    assert "刪除過時檔案: gone.md" in out
    assert "other.md" in out and "首次推送即帶 --clean" in out
    # 純預覽：上游檔案一個都沒刪
    assert (push_scene["upstream"] / "gone.md").exists()


def test_dry_run_plan_reports_abort_when_base_unreachable(push_scene: dict, capsys):
    """E1 對照：同一場景不寫 base，預覽回報 --clean 會中止而非列出刪除。"""
    plan = sync_mod._dry_run_report_clean_plan(
        push_scene["project"], push_scene["upstream"], "HEAD"
    )
    assert plan is None
    out = capsys.readouterr().out
    assert "會中止" in out
    assert "刪除過時檔案" not in out


def test_dry_run_plan_matches_actual_clean_deletions(push_scene: dict, tmp_path: Path):
    _write_base(push_scene["claude"], push_scene["base"])
    plan = sync_mod._dry_run_report_clean_plan(
        push_scene["project"], push_scene["upstream"], "HEAD"
    )
    staging = tmp_path / "staging"
    sync_mod.stage_tracked_tree(push_scene["project"], staging, "HEAD")
    before = {p.name for p in push_scene["upstream"].iterdir() if p.is_file()}
    sync_mod.clean_stale_files(
        push_scene["upstream"], staging, base_sha=push_scene["base"],
        claude_dir=push_scene["claude"], project_root=push_scene["project"],
    )
    after = {p.name for p in push_scene["upstream"].iterdir() if p.is_file()}
    assert sorted(before - after) == [rel for rel, _ in plan.deletions]


# ---------- 同版號判定與版號閘門 ----------


@pytest.mark.parametrize(
    ("local", "remote", "clean", "expected"),
    [
        ("3.3.0", "3.3.0", True, True),
        ("3.3.0", "3.3.0", False, False),
        ("3.3.1", "3.3.0", True, False),
        ("3.3.0", None, True, False),
    ],
)
def test_is_same_version_clean(local, remote, clean, expected):
    assert sync_mod.is_same_version_clean(local, remote, clean) is expected


def test_check_release_version_allows_equal_only_when_asked(capsys):
    sync_mod.check_release_version("3.3.0", "3.3.0", allow_equal=True)
    with pytest.raises(SystemExit) as exc:
        sync_mod.check_release_version("3.3.0", "3.3.0")
    assert exc.value.code == 1
    assert "改帶 --clean" in capsys.readouterr().out


def test_check_release_version_rejects_lower_even_when_equal_allowed():
    with pytest.raises(SystemExit) as exc:
        sync_mod.check_release_version("3.2.9", "3.3.0", allow_equal=True)
    assert exc.value.code == 1


# ---------- 只含刪除的內容閘門 ----------


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    repo = tmp_path / "clone"
    _init(repo)
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    (repo / "b.md").write_text("b\n", encoding="utf-8")
    _commit_all(repo, "release")
    return repo


def test_ensure_deletions_only_passes_pure_deletion(clone: Path):
    (clone / "a.md").unlink()
    _git(["add", "-A"], clone)
    sync_mod.ensure_deletions_only(clone)


def test_ensure_deletions_only_rejects_modification(clone: Path, capsys):
    """E2 正向對照：刪除夾帶修改時必須擋下。"""
    (clone / "a.md").unlink()
    (clone / "b.md").write_text("changed\n", encoding="utf-8")
    _git(["add", "-A"], clone)
    with pytest.raises(SystemExit) as exc:
        sync_mod.ensure_deletions_only(clone)
    assert exc.value.code == 1
    assert "b.md" in capsys.readouterr().out


def test_ensure_deletions_only_rejects_addition(clone: Path):
    (clone / "a.md").unlink()
    (clone / "new.md").write_text("n\n", encoding="utf-8")
    _git(["add", "-A"], clone)
    with pytest.raises(SystemExit):
        sync_mod.ensure_deletions_only(clone)


# ---------- tag 位置閘門與 tag 移動 ----------


@pytest.fixture
def remote_pair(tmp_path: Path) -> tuple[Path, Path]:
    """bare remote 上 main 有一個 commit 並打 v1.0.0；回傳 (clone, bare)。"""
    bare = tmp_path / "remote.git"
    _git(["init", "--bare", "-q", "-b", "main", str(bare)], tmp_path)
    seed = tmp_path / "seed"
    _init(seed)
    (seed / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (seed / "gone.md").write_text("g\n", encoding="utf-8")
    _commit_all(seed, "v1.0.0")
    _git(["tag", "-a", "v1.0.0", "-m", "Release v1.0.0"], seed)
    _git(["remote", "add", "origin", str(bare)], seed)
    _git(["push", "-q", "origin", "main", "--tags"], seed)
    work = tmp_path / "work"
    _git(["clone", "-q", str(bare), str(work)], tmp_path)
    _git(["config", "user.email", "t@example.com"], work)
    _git(["config", "user.name", "t"], work)
    return work, bare


def test_require_tag_at_remote_head_returns_tag_sha(remote_pair):
    work, _bare = remote_pair
    sha = sync_mod.require_tag_at_remote_head(work, "1.0.0")
    assert sha == _git(["rev-parse", "refs/tags/v1.0.0"], work)


def test_require_tag_at_remote_head_rejects_missing_tag(remote_pair):
    work, _bare = remote_pair
    with pytest.raises(SystemExit) as exc:
        sync_mod.require_tag_at_remote_head(work, "9.9.9")
    assert exc.value.code == 1


def test_require_tag_at_remote_head_rejects_tag_behind_head(remote_pair):
    """E2 正向對照：tag 之後遠端另有推送時拒絕，避免移動 tag 夾帶他人內容。"""
    work, _bare = remote_pair
    (work / "later.md").write_text("l\n", encoding="utf-8")
    _commit_all(work, "later")
    with pytest.raises(SystemExit) as exc:
        sync_mod.require_tag_at_remote_head(work, "1.0.0")
    assert exc.value.code == 1


def test_move_version_tag_points_remote_tag_at_new_head(remote_pair):
    work, bare = remote_pair
    old = sync_mod.require_tag_at_remote_head(work, "1.0.0")
    (work / "gone.md").unlink()
    new_head = _commit_all(work, "v1.0.0: clean")
    _git(["push", "-q", "origin", "main"], work)
    sync_mod.move_version_tag(work, "1.0.0", old)
    assert _git(["rev-parse", "refs/tags/v1.0.0^{commit}"], bare) == new_head


@pytest.fixture
def release_scene(tmp_path: Path, monkeypatch) -> dict:
    """遠端 v1.0.0 殘留本地已刪除的 gone.md；本地版號仍為 1.0.0。

    main() 的網路與重型前置（smoke test、skill 殘留、skill 庫漂移）以替身略過，
    其餘照實執行，REPO_URL 指向本地 bare repo。
    """
    changelog = "# Changelog\n\n## 1.0.0\n"
    bare = tmp_path / "remote.git"
    _git(["init", "--bare", "-q", "-b", "main", str(bare)], tmp_path)
    seed = tmp_path / "seed"
    _init(seed)
    for name, text in {"VERSION": "1.0.0\n", "CHANGELOG.md": changelog,
                       "keep.md": "k\n", "gone.md": "g\n"}.items():
        (seed / name).write_text(text, encoding="utf-8")
    base_sha = _commit_all(seed, "v1.0.0")
    _git(["tag", "-a", "v1.0.0", "-m", "Release v1.0.0"], seed)
    _git(["remote", "add", "origin", str(bare)], seed)
    _git(["push", "-q", "origin", "main", "--tags"], seed)

    project = tmp_path / "project"
    _init(project)
    claude = project / ".claude"
    claude.mkdir()
    for name, text in {"VERSION": "1.0.0\n", "CHANGELOG.md": changelog,
                       "keep.md": "k\n", "gone.md": "g\n"}.items():
        (claude / name).write_text(text, encoding="utf-8")
    _commit_all(project, "seed")
    (claude / "gone.md").unlink()
    _commit_all(project, "remove gone")
    _write_base(claude, base_sha)

    monkeypatch.setattr(sync_mod, "REPO_URL", str(bare))
    monkeypatch.setattr(sync_mod, "find_project_root", lambda: project)
    monkeypatch.setattr(sync_mod, "run_framework_smoke_test", lambda _d: None)
    monkeypatch.setattr(sync_mod, "check_skill_residue", lambda *_a, **_k: True)
    monkeypatch.setattr(sync_mod, "report_skill_repo_drift", lambda _d: "")
    return {"bare": bare, "project": project, "claude": claude, "base": base_sha}


def _run_main(monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["sync-push", *argv])
    sync_mod.main()


def _remote_files(bare: Path) -> list[str]:
    return sorted(_git(["ls-tree", "--name-only", "main"], bare).split())


def test_main_same_version_clean_deletes_and_moves_tag(release_scene, monkeypatch):
    bare = release_scene["bare"]
    _run_main(monkeypatch, "--clean", "clean v1.0.0")
    assert _remote_files(bare) == ["CHANGELOG.md", "VERSION", "keep.md"]
    head = _git(["rev-parse", "main"], bare)
    assert head != release_scene["base"]
    assert _git(["rev-parse", "refs/tags/v1.0.0^{commit}"], bare) == head


def test_main_same_version_without_clean_is_rejected(release_scene, monkeypatch, capsys):
    """E1 對照：同一場景不帶 --clean，照舊被版號閘門拒絕，遠端不變。"""
    bare = release_scene["bare"]
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, "clean v1.0.0")
    assert exc.value.code == 1
    assert "不高於遠端" in capsys.readouterr().out
    assert "gone.md" in _remote_files(bare)
    assert _git(["rev-parse", "main"], bare) == release_scene["base"]


def test_main_same_version_clean_with_modification_is_rejected(
    release_scene, monkeypatch, capsys
):
    """E2 正向對照：同版號 --clean 夾帶修改時擋在 commit 前，遠端與 tag 不變。"""
    bare, project = release_scene["bare"], release_scene["project"]
    (release_scene["claude"] / "keep.md").write_text("changed\n", encoding="utf-8")
    _commit_all(project, "modify keep")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, "--clean", "clean v1.0.0")
    assert exc.value.code == 1
    assert "只允許刪除" in capsys.readouterr().out
    assert _git(["rev-parse", "main"], bare) == release_scene["base"]
    assert _git(["rev-parse", "refs/tags/v1.0.0^{commit}"], bare) == release_scene["base"]


def _bump_local_version(scene: dict) -> None:
    (scene["claude"] / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    _commit_all(scene["project"], "bump 1.0.1")


def test_main_orphan_hint_suggests_clean_when_base_reachable(
    release_scene, monkeypatch, capsys
):
    _bump_local_version(release_scene)
    # 有真孤兒時須明示；帶 --no-clean 推送完成後才會出現結尾提醒
    _run_main(monkeypatch, "release v1.0.1", "--no-clean")
    out = capsys.readouterr().out
    assert "- gone.md" in out
    assert "請重跑：sync-push --clean" in out


def test_main_orphans_without_flags_exit_before_push(release_scene, monkeypatch, capsys):
    """正向對照：同一場景不帶 --clean／--no-clean，推送前以 1 結束、遠端不前進。"""
    _bump_local_version(release_scene)
    before = _git(["rev-parse", "main"], release_scene["bare"])

    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, "release v1.0.1")

    assert exc.value.code == 1
    assert "gone.md" in capsys.readouterr().out
    assert _git(["rev-parse", "main"], release_scene["bare"]) == before


def test_main_orphan_hint_avoids_clean_when_base_unreachable(
    release_scene, monkeypatch, capsys
):
    """E1 對照：同一場景移除 base，提醒不建議會被三方保護中止的 --clean。"""
    (release_scene["claude"] / sync_mod.SYNC_STATE_FILENAME).unlink()
    _bump_local_version(release_scene)
    _run_main(monkeypatch, "release v1.0.1", "--no-clean")
    out = capsys.readouterr().out
    assert "- gone.md" in out
    assert "未經三方比對" in out
    assert "請重跑：sync-push --clean" not in out


def test_move_version_tag_rejects_stale_lease(remote_pair):
    """E2 正向對照：遠端 tag 已不是預期值時推送被拒，不覆蓋他人移動的 tag。"""
    work, bare = remote_pair
    (work / "gone.md").unlink()
    _commit_all(work, "v1.0.0: clean")
    stale = "0" * 40
    with pytest.raises(SystemExit) as exc:
        sync_mod.move_version_tag(work, "1.0.0", stale)
    assert exc.value.code == 1
    seed_head = _git(["rev-parse", "main"], bare)
    assert _git(["rev-parse", "refs/tags/v1.0.0^{commit}"], bare) == seed_head
