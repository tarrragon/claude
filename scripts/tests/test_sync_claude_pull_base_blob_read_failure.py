"""sync-pull：base blob 讀取失敗須 fail-loud，不得與「base 無此檔」同值。

fixture：本地 bare 上游 + partial clone（blob:none），上游移除後 base blob 不可達。
- 讀取失敗：local==base 的檔不得被判整檔衝突，須拋錯並保持本地原樣
- E1 對照組：base 真的沒有該路徑時，維持 add/add 衝突行為
- _read_upstream_blob：缺路徑回 None、存在回內容
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_base_blob", _SCRIPT)
assert _spec and _spec.loader
scp = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_base_blob"] = scp
_spec.loader.exec_module(scp)  # type: ignore[union-attr]

BODY = "".join(f"line{i}\n" for i in range(20))


def sh(*a: str) -> str:
    r = subprocess.run(list(a), capture_output=True, text=True)
    assert r.returncode == 0, f"{a}: {r.stderr}"
    return r.stdout.strip()


class Fx:
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True)
        self.root, self.bare = root, root / "up.git"
        self.work, self.proj = root / "upwork", root / "proj"
        sh("git", "init", "-q", "--bare", str(self.bare))
        sh("git", "-C", str(self.bare), "config", "uploadpack.allowFilter", "true")
        sh("git", "init", "-q", str(self.work))
        sh("git", "-C", str(self.work), "remote", "add", "origin", str(self.bare))
        self.proj.mkdir()
        sh("git", "init", "-q", str(self.proj))
        (self.proj / ".claude").mkdir()
        for d in (self.work, self.proj):
            sh("git", "-C", str(d), "config", "user.email", "f@x")
            sh("git", "-C", str(d), "config", "user.name", "f")

    def up(self, files: dict) -> str:
        for k, v in files.items():
            p = self.work / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v)
        sh("git", "-C", str(self.work), "add", "-A")
        sh("git", "-C", str(self.work), "commit", "-qm", "c")
        sh("git", "-C", str(self.work), "push", "-q", "origin", "HEAD:main")
        return sh("git", "-C", str(self.work), "rev-parse", "HEAD")

    def commit_proj(self) -> None:
        sh("git", "-C", str(self.proj), "add", "-A")
        sh("git", "-C", str(self.proj), "commit", "-qm", "p", "--allow-empty")

    def clone(self, partial: bool = False) -> Path:
        t = self.root / f"clone{len(list(self.root.glob('clone*')))}"
        if partial:
            sh("git", "clone", "-q", "--filter=blob:none",
               "file://" + str(self.bare), str(t))
        else:
            sh("git", "clone", "-q", str(self.bare), str(t))
        return t

    def pull(self) -> None:
        scp._sync_with_backup(self.proj, self.clone(), confirm_overlay=True)

    def f(self, rel: str) -> str | None:
        p = self.proj / ".claude" / rel
        return p.read_text() if p.exists() else None


def _quiet(monkeypatch) -> None:
    monkeypatch.setattr(scp, "report_skill_repo_drift", lambda d: "")
    monkeypatch.setattr(scp, "detect_changed_packages", lambda p: None)


def test_base_blob_read_failure_fails_loud_and_keeps_local(tmp_path, monkeypatch):
    _quiet(monkeypatch)
    fx = Fx(tmp_path / "fx")
    fx.up({"rules/a.md": BODY, "rules/b.md": "other\n"})
    fx.pull()
    fx.commit_proj()
    fx.up({"rules/a.md": BODY.replace("line5", "UP5")})
    clone = fx.clone(partial=True)
    fx.bare.rename(fx.root / "up.git.gone")  # promisor 不可達
    with pytest.raises(Exception, match="無法讀取 base"):
        scp._sync_with_backup(fx.proj, clone, confirm_overlay=True)
    local = fx.f("rules/a.md")
    assert local == BODY
    assert "<<<<<<<" not in local
    assert not (fx.proj / ".claude/.sync-conflicts/rules/a.md").exists()


def test_base_without_path_still_add_add_conflict_control(tmp_path, monkeypatch):
    """E1 對照組：base 真的沒有該路徑，本地與上游各自新增不同內容，維持衝突。"""
    _quiet(monkeypatch)
    fx = Fx(tmp_path / "fx")
    fx.up({"rules/a.md": BODY})
    fx.pull()
    (fx.proj / ".claude/rules/n.md").write_text("LOCAL\n")
    fx.commit_proj()
    fx.up({"rules/n.md": "UPSTREAM\n"})
    fx.pull()
    assert (fx.proj / ".claude/.sync-conflicts/rules/n.md").exists()


def test_main_reports_base_blob_error_exit1_without_traceback(
    tmp_path, monkeypatch, capsys
):
    _quiet(monkeypatch)
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)

    def _raise(*_a, **_k):
        raise scp.BaseBlobReadError("a" * 40, "rules/a.md", b"fatal: promisor")

    monkeypatch.setattr(scp, "find_project_root", lambda: root)
    monkeypatch.setattr(scp, "_validate_environment", lambda _p: None)
    monkeypatch.setattr(scp, "warn_conflict_residue", lambda *_a, **_k: None)
    monkeypatch.setattr(scp, "warn_pending_base", lambda *_a, **_k: None)
    monkeypatch.setattr(scp, "_clone_and_backup", lambda *_a, **_k: (tmp_path, tmp_path))
    monkeypatch.setattr(scp, "_complete_sync", _raise)
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])
    with pytest.raises(SystemExit) as exc:
        scp.main()
    assert exc.value.code == 1
    cap = capsys.readouterr()
    assert "處置" in cap.err and "[sync-pull]" in cap.err
    assert "Traceback" not in cap.out + cap.err


def test_read_upstream_blob_missing_path_none_and_present_bytes(tmp_path):
    fx = Fx(tmp_path / "fx")
    sha = fx.up({"rules/a.md": BODY})
    clone = fx.clone()
    assert scp._read_upstream_blob(clone, sha, "rules/zzz.md") is None
    assert scp._read_upstream_blob(clone, sha, "rules/a.md") == BODY.encode()
