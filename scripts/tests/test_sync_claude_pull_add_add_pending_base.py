"""sync-pull：pending base 存在時，衝突輪新增檔被本地增補後重跑 pull 不再判整檔衝突。

重現 3.4.0-W1-311 fixture B3：round1 他檔衝突 + 上游新增 X（X 寫入、base 不推進）；
round2 本地在 X 加一行後重跑 pull，X 在舊 base 無此檔，過去落入 add/add 判整檔衝突。
修法 A：以 pending base 的 blob 作為 base_content 走正常三方合併。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_add_add_pending", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_add_add_pending"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    return _git(["rev-parse", "HEAD"], repo)


def _round1(tmp_path: Path):
    """回傳 (project_root, upstream, base_sha, head_sha)；round1 已套用（other.md 衝突、X 寫入）。"""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@t.t"], upstream)
    _git(["config", "user.name", "t"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    (upstream / "rules").mkdir()
    (upstream / "rules" / "other.md").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (upstream / "rules" / "other.md").write_text("l1\nl2\nUP3\nl4\nl5\n", encoding="utf-8")
    (upstream / "rules" / "x.md").write_text("x1\nx2\n", encoding="utf-8")
    head = _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    (project_root / ".claude" / "rules").mkdir(parents=True)
    (project_root / ".claude" / "rules" / "other.md").write_text(
        "l1\nLOC2\nl3\nl4\nLOC5\n", encoding="utf-8"
    )
    _applied, conflicts, _res = pull.apply_upstream_delta(project_root, upstream, base)
    assert conflicts == ["rules/other.md"]
    x = project_root / ".claude" / "rules" / "x.md"
    assert x.read_text(encoding="utf-8") == "x1\nx2\n"
    return project_root, upstream, base, head


def test_local_append_to_round1_added_file_not_conflict_with_pending_base(tmp_path):
    project_root, upstream, base, head = _round1(tmp_path)
    x = project_root / ".claude" / "rules" / "x.md"
    x.write_text("x1\nx2\nLOCAL-LINE\n", encoding="utf-8")

    _a, conflicts, _r = pull.apply_upstream_delta(
        project_root, upstream, base, pending_base_sha=head
    )
    assert "rules/x.md" not in conflicts
    assert x.read_text(encoding="utf-8") == "x1\nx2\nLOCAL-LINE\n"


def test_e1_without_pending_base_same_fixture_still_conflicts(tmp_path):
    """E1 對照：同 fixture 不帶 pending base 仍判整檔衝突，兩條路徑產物不同。"""
    project_root, upstream, base, _head = _round1(tmp_path)
    x = project_root / ".claude" / "rules" / "x.md"
    x.write_text("x1\nx2\nLOCAL-LINE\n", encoding="utf-8")

    _a, conflicts, _r = pull.apply_upstream_delta(project_root, upstream, base)
    assert "rules/x.md" in conflicts
    assert b"<<<<<<<" in x.read_bytes()


def test_true_add_add_still_conflicts_when_path_absent_in_pending_base(tmp_path):
    """路徑不在 pending base（本輪才新增）且雙方內容不同 → 仍為 add/add 真衝突。"""
    project_root, upstream, base, head = _round1(tmp_path)
    (upstream / "rules" / "y.md").write_text("y-up\n", encoding="utf-8")
    _commit_all(upstream, "more")
    (project_root / ".claude" / "rules" / "y.md").write_text("y-local\n", encoding="utf-8")

    _a, conflicts, _r = pull.apply_upstream_delta(
        project_root, upstream, base, pending_base_sha=head
    )
    assert "rules/y.md" in conflicts


# ---------------------------------------------------------------------------
# 接線：_sync_with_backup 必須把 .sync-state.json 的 pending base 傳給
# apply_upstream_delta（拿掉接線時上面直接呼叫的測試仍綠，死結仍在）
# ---------------------------------------------------------------------------

def _captured_pending_kwarg(tmp_path: Path, monkeypatch, pending: str | None):
    project_root, upstream, base, _head = _round1(tmp_path)
    claude = project_root / ".claude"
    pull.write_base_sha(claude, base)
    pull.write_pending_base_sha(claude, pending)
    seen: dict = {}

    def _spy(*_a, **kwargs):
        seen.update(kwargs)
        return 0, [], []

    monkeypatch.setattr(pull, "apply_upstream_delta", _spy)
    monkeypatch.setattr(pull, "report_skill_repo_drift", lambda d: "")
    monkeypatch.setattr(pull, "detect_changed_packages", lambda p: None)
    pull._sync_with_backup(project_root, upstream, confirm_overlay=True)
    return seen


def test_sync_with_backup_passes_pending_base_from_state(tmp_path, monkeypatch):
    sha = "c" * 40
    seen = _captured_pending_kwarg(tmp_path, monkeypatch, sha)
    assert seen["pending_base_sha"] == sha


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_main_unreadable_pending_base_aborts_exit1_and_changes_nothing(
    tmp_path, monkeypatch, capsys
):
    """pending base 讀不到：exit 1、訊息標明 pending base 與恢復方式、無 traceback、
    .claude 與 .sync-state.json 前後一致（不退回 add/add、不推進 base）。"""
    project_root, upstream, base, head = _round1(tmp_path)
    claude = project_root / ".claude"
    # 解掉 round1 的 other.md 衝突，讓 delta 只剩 x.md 觸發 pending 讀取
    (claude / "rules" / "other.md").write_text("l1\nl2\nUP3\nl4\nl5\n", encoding="utf-8")
    (claude / "rules" / "x.md").write_text("x1\nx2\nLOCAL-LINE\n", encoding="utf-8")
    bad_pending = "d" * 40
    pull.write_base_sha(claude, base)
    pull.write_pending_base_sha(claude, bad_pending)
    before = _snapshot(claude)

    monkeypatch.setattr(pull, "report_skill_repo_drift", lambda d: "")
    monkeypatch.setattr(pull, "detect_changed_packages", lambda p: None)
    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "_validate_environment", lambda _p: None)
    monkeypatch.setattr(pull, "warn_conflict_residue", lambda *_a, **_k: None)
    monkeypatch.setattr(
        pull, "_clone_and_backup",
        lambda *_a, **_k: (
            upstream,
            pull._sync_with_backup(project_root, upstream, confirm_overlay=True),
        ),
    )
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])
    with pytest.raises(SystemExit) as exc:
        pull.main()
    assert exc.value.code == 1
    cap = capsys.readouterr()
    assert f"pending base {bad_pending[:12]}" in cap.err
    assert "pending_base_sha" in cap.err and "--resolve-done" in cap.err
    assert "Traceback" not in cap.out + cap.err
    assert _snapshot(claude) == before


def test_sync_with_backup_passes_none_without_pending_base(tmp_path, monkeypatch):
    """E1 對照：無 pending base 時傳入 None，與上一測試的值不同。"""
    seen = _captured_pending_kwarg(tmp_path, monkeypatch, None)
    assert seen["pending_base_sha"] is None
