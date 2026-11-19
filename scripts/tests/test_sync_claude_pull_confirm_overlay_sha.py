"""--confirm-overlay 綁定確認時的上游 commit（3.4.0-W1-319）。

E1 對照：同一 fixture 下，相符 SHA 套用、不符 SHA 中止且 .claude/ 逐位元組不變、
裸旗標維持現行行為（相容 3.4.0-W1-293 以舊 sync-pull.md 搭配新腳本的情境）。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_confirm_sha", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_confirm_sha"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

SUCCESS_MSG = "成功拉取 .claude 更新"
SHA_RE = re.compile(r"target SHA: ([0-9a-f]{40})")


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


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

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "_validate_environment", lambda _p: None)
    monkeypatch.setattr(
        pull, "_clone_and_backup",
        lambda root, confirm_overlay=False, bump_target=pull._BUMP_NOT_SET: (
            upstream,
            pull._sync_with_backup(root, upstream, confirm_overlay, bump_target),
        ),
    )
    monkeypatch.setattr(pull, "_update_project_templates", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "cleanup_legacy_github_dir", lambda *_a, **_k: [])
    monkeypatch.setattr(pull, "cleanup_old_backups", lambda *_a, **_k: 0)
    monkeypatch.setattr(pull, "auto_register_hooks", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "verify_local_settings_no_hooks", lambda *_a, **_k: None)
    monkeypatch.setattr(pull, "verify_hook_imports", lambda *_a, **_k: 0)
    monkeypatch.setattr(pull, "check_conflict_marker_residue", lambda *_a, **_k: 0)
    monkeypatch.setattr(pull.sys.stdin, "isatty", lambda: False, raising=False)
    return project_root, upstream


def _run(monkeypatch, capsys, *flags: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", *flags])
    rc = 0
    try:
        pull.main()
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 1
    return rc, capsys.readouterr().out


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted((root / ".claude").rglob("*")) if p.is_file()
    }


def test_dry_run_prints_target_sha(tmp_path, monkeypatch, capsys) -> None:
    _, upstream = _setup(tmp_path, monkeypatch)
    rc, out = _run(monkeypatch, capsys)
    assert rc == pull.EXIT_CONFIRM_REQUIRED
    match = SHA_RE.search(out)
    assert match and match.group(1) == _git(["rev-parse", "HEAD"], upstream)


def test_matching_sha_applies(tmp_path, monkeypatch, capsys) -> None:
    project_root, upstream = _setup(tmp_path, monkeypatch)
    sha = _git(["rev-parse", "HEAD"], upstream)
    rc, out = _run(monkeypatch, capsys, "--confirm-overlay", sha)
    assert rc == 0
    assert SUCCESS_MSG in out
    assert (project_root / ".claude" / "rules" / "keep.md").read_text("utf-8") == "keep\n"


def test_mismatched_sha_aborts_claude_unchanged(tmp_path, monkeypatch, capsys) -> None:
    project_root, upstream = _setup(tmp_path, monkeypatch)
    before = _snapshot(project_root)
    rc, out = _run(monkeypatch, capsys, "--confirm-overlay", "0" * 40)
    assert rc == pull.EXIT_CONFIRM_REQUIRED
    assert SUCCESS_MSG not in out
    assert _snapshot(project_root) == before
    # 沿用結束碼 10：須同時印出新 dry-run 清單與新 target SHA，供重新確認
    assert "[dry-run]" in out
    match = SHA_RE.search(out)
    assert match and match.group(1) == _git(["rev-parse", "HEAD"], upstream)
    assert not (project_root / ".claude" / "sync-base.json").exists()


def test_bare_flag_keeps_current_behavior(tmp_path, monkeypatch, capsys) -> None:
    project_root, _ = _setup(tmp_path, monkeypatch)
    rc, out = _run(monkeypatch, capsys, "--confirm-overlay")
    assert rc == 0
    assert SUCCESS_MSG in out
    assert (project_root / ".claude" / "rules" / "keep.md").read_text("utf-8") == "keep\n"


def test_parse_args_forms() -> None:
    assert pull.parse_args(["--confirm-overlay"]).confirm_overlay is True
    assert pull.parse_args(["--confirm-overlay", "abc1234"]).confirm_overlay == "abc1234"
    assert pull.parse_args([]).confirm_overlay is False
