"""sync-pull 暫存 clone 不得觸發 git auto gc（#143），失敗訊息區分網路與 clone 損壞。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_auto_gc", _SCRIPT)
assert _spec and _spec.loader
scp = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_auto_gc"] = scp
_spec.loader.exec_module(scp)  # type: ignore[union-attr]

N_BLOBS = 60


def sh(*a: str) -> str:
    r = subprocess.run(list(a), capture_output=True, text=True)
    assert r.returncode == 0, f"{a}: {r.stderr}"
    return r.stdout.strip()


@pytest.fixture
def upstream(tmp_path: Path):
    bare, work = tmp_path / "up.git", tmp_path / "work"
    sh("git", "init", "-q", "--bare", str(bare))
    sh("git", "-C", str(bare), "config", "uploadpack.allowFilter", "true")
    sh("git", "-C", str(bare), "config", "uploadpack.allowAnySHA1InWant", "true")
    sh("git", "init", "-q", str(work))
    for k, v in (("user.email", "f@x"), ("user.name", "f")):
        sh("git", "-C", str(work), "config", k, v)
    for i in range(N_BLOBS):
        (work / f"f{i}.txt").write_text(f"base {i}\n")
    sh("git", "-C", str(work), "add", "-A")
    sh("git", "-C", str(work), "commit", "-qm", "base")
    base_sha = sh("git", "-C", str(work), "rev-parse", "HEAD")
    # 第二個 commit 改寫全部檔案：clone checkout 只抓 HEAD blob，base blob 須逐檔 lazy fetch
    for i in range(N_BLOBS):
        (work / f"f{i}.txt").write_text(f"head {i}\n")
    sh("git", "-C", str(work), "commit", "-qam", "head")
    sh("git", "-C", str(work), "push", "-q", str(bare), "HEAD:main")
    return bare, base_sha


def _read_all_blobs(clone: Path, sha: str) -> list[str]:
    """逐檔讀 base blob（每次讀取在 partial clone 新增一個 pack），回傳失敗訊息。"""
    errors = []
    for i in range(N_BLOBS):
        try:
            scp._read_upstream_blob(clone, sha, f"f{i}.txt")
        except scp.BaseBlobReadError as exc:
            errors.append(str(exc))
            break
    return errors


def _tight_pack_limit(clone: Path) -> None:
    # 縮小 autoPackLimit 讓測試在少量 pack 即達觸發門檻（預設 50）
    sh("git", "-C", str(clone), "config", "gc.autoPackLimit", "5")
    sh("git", "-C", str(clone), "config", "gc.autoDetach", "false")


def _pack_count(clone: Path) -> int:
    return len(list((clone / ".git/objects/pack").glob("*.pack")))


def test_control_default_partial_clone_triggers_gc(upstream, tmp_path):
    """對照：未關閉 gc 的 partial clone 在逐檔讀取時 pack 數被 auto gc 合併。"""
    bare, sha = upstream
    clone = tmp_path / "ctl"
    sh("git", "clone", "-q", "--filter=blob:none", "file://" + str(bare), str(clone))
    _tight_pack_limit(clone)
    _read_all_blobs(clone, sha)
    assert _pack_count(clone) < N_BLOBS // 2, "對照組應已觸發 auto gc 合併 pack"


def test_clone_repo_disables_auto_gc(upstream, tmp_path, monkeypatch):
    bare, sha = upstream
    monkeypatch.setattr(scp, "REPO_URL", "file://" + str(bare))
    clone = tmp_path / "fixed"
    scp.clone_repo(clone)
    assert sh("git", "-C", str(clone), "config", "--get", "gc.auto") == "0"
    assert sh("git", "-C", str(clone), "config", "--get", "maintenance.auto") == "false"
    _tight_pack_limit(clone)
    assert _read_all_blobs(clone, sha) == []
    assert _pack_count(clone) >= N_BLOBS // 2, "gc 關閉時 pack 不應被合併"


def test_error_message_distinguishes_network_and_corruption():
    net = scp.BaseBlobReadError(
        "a" * 40, "x", b"fatal: unable to access 'https://h/': Could not resolve host")
    bad = scp.BaseBlobReadError("a" * 40, "x", b"fatal: bad object " + b"b" * 40)
    assert "網路" in str(net) and "clone 損壞" not in str(net)
    assert "clone 損壞" in str(bad)
