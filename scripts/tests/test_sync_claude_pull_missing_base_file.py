"""sync-pull：本地缺少 base 已有檔案時，遠端檔須帶入或明確警示（不靜默略過）。

fixture：本地 bare 上游 + 本地專案（git），不連網。
- 本地從未取得（無 git 歷史）：上游 M 時帶入
- E1 對照組：本地刻意刪除（有 git 歷史）：維持不帶入
- 非 git 專案（無法判定）：不帶入，stderr 列檔警示
- resolve_done：pending 輪 A/M 檔本地缺漏時列出
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_missing_base", _SCRIPT)
assert _spec and _spec.loader
scp = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_missing_base"] = scp
_spec.loader.exec_module(scp)  # type: ignore[union-attr]


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
        if (self.proj / ".git").exists():
            sh("git", "-C", str(self.proj), "add", "-A")
            sh("git", "-C", str(self.proj), "commit", "-qm", "p", "--allow-empty")

    def pull(self) -> None:
        t = self.root / f"clone{len(list(self.root.glob('clone*')))}"
        sh("git", "clone", "-q", str(self.bare), str(t))
        scp._sync_with_backup(self.proj, t, confirm_overlay=True)

    def set_base(self, sha: str) -> None:
        sf = self.proj / ".claude/sync-base.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        st["last_synced_base_sha"] = sha
        sf.write_text(json.dumps(st))

    def f(self, rel: str) -> str | None:
        p = self.proj / ".claude" / rel
        return p.read_text() if p.exists() else None


def _quiet(monkeypatch) -> None:
    monkeypatch.setattr(scp, "report_skill_repo_drift", lambda d: "")
    monkeypatch.setattr(scp, "detect_changed_packages", lambda p: None)


def _base_has_x_local_lacks(tmp_path: Path) -> Fx:
    """base 已含 hooks/new.py，本地從未取得（base 在缺檔時被推進）。"""
    fx = Fx(tmp_path / "fx")
    fx.up({"rules/a.md": "a\n", "hooks/h.py": "h\n"})
    fx.pull()
    fx.commit_proj()
    c2 = fx.up({"hooks/new.py": "n\n"})
    fx.set_base(c2)
    fx.commit_proj()
    return fx


def test_never_obtained_file_is_brought_in_on_upstream_modify(tmp_path, monkeypatch):
    _quiet(monkeypatch)
    fx = _base_has_x_local_lacks(tmp_path)
    fx.up({"hooks/new.py": "n2\n"})
    fx.pull()
    assert fx.f("hooks/new.py") == "n2\n"


def test_locally_deleted_file_stays_deleted_control(tmp_path, monkeypatch):
    """E1 對照組：本地刻意刪除（git 歷史有該檔）仍不帶入。"""
    _quiet(monkeypatch)
    fx = Fx(tmp_path / "fx")
    fx.up({"rules/a.md": "a\n", "hooks/new.py": "n\n"})
    fx.pull()
    fx.commit_proj()
    assert fx.f("hooks/new.py") == "n\n"
    (fx.proj / ".claude/hooks/new.py").unlink()
    fx.commit_proj()
    fx.up({"hooks/new.py": "n2\n"})
    fx.pull()
    assert fx.f("hooks/new.py") is None


def test_undeterminable_missing_file_warns_on_stderr(tmp_path, monkeypatch, capsys):
    _quiet(monkeypatch)
    fx = _base_has_x_local_lacks(tmp_path)
    shutil.rmtree(fx.proj / ".git")  # 非 git：無法判定
    fx.up({"hooks/new.py": "n2\n"})
    fx.pull()
    assert fx.f("hooks/new.py") is None
    err = capsys.readouterr().err
    assert "hooks/new.py" in err and "無法判定" in err


def test_resolve_done_lists_pending_round_files_missing_locally(
    tmp_path, monkeypatch, capsys
):
    _quiet(monkeypatch)
    fx = Fx(tmp_path / "fx")
    fx.up({"rules/a.md": "a\n", "hooks/h.py": "h\n"})
    fx.pull()
    (fx.proj / ".claude/rules/a.md").write_text("LOCAL\n")
    fx.commit_proj()
    fx.up({"rules/a.md": "UP\n", "hooks/new.py": "n\n"})
    fx.pull()  # 衝突輪：new.py 帶入、base 不推進
    sh("git", "-C", str(fx.proj), "checkout", "--", ".claude/rules/a.md")
    sh("git", "-C", str(fx.proj), "clean", "-fdq", ".claude/hooks")
    capsys.readouterr()
    rc = scp.resolve_done(fx.proj / ".claude")
    assert rc == 0
    assert "hooks/new.py" in capsys.readouterr().err
