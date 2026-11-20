"""
合併閘門的匯入掃描收斂（3.5.0-W1-005）

- 三處匯入掃描（lib 匯入者、hooks／scripts 消費者、跨 skill 匯入者）共用 scan_sources
- 單次閘門內以快照路徑為鍵快取掃描結果，每個 .py 只讀一次
- 名稱唯一的單檔模組被其他 skill 匯入時加選；重名者不加選
"""

import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude"))

import merge_gate as mg  # noqa: E402
import worktree_manager as wm  # noqa: E402
import merge_cas as mc  # noqa: E402


def _touch(root, rel, text=""):
    f = Path(root) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


@pytest.fixture
def snap(tmp_path):
    r = tmp_path / "snap"
    _touch(r, ".claude/skills/lone/tests/test_a.py")
    _touch(r, ".claude/skills/lone/lone_mod.py", "x = 1\n")
    _touch(r, ".claude/skills/user/tests/test_u.py", "import os\n")
    _touch(r, ".claude/skills/libuser/tests/test_l.py", "from lib import y\n")
    _touch(r, ".claude/hooks/h.py", "import os\n")
    _touch(r, ".claude/scripts/s.py", "import os\n")
    return str(r)


def _count_scans(monkeypatch):
    calls = []
    real = mg.scan_sources

    def counting(root):
        calls.append(root)
        return real(root)

    monkeypatch.setattr(mg, "scan_sources", counting)
    return calls


def _count_reads(monkeypatch):
    reads = Counter()
    real = mg._read_text

    def counting(path):
        reads[str(path)] += 1
        return real(path)

    monkeypatch.setattr(mg, "_read_text", counting)
    return reads


class TestSharedScan:
    def test_three_scans_go_through_scan_sources(self, snap, monkeypatch):
        """三處掃描各自觸發一次 scan_sources（未在快取範圍內時），不另走 os.walk。"""
        calls = _count_scans(monkeypatch)
        assert mg._skills_importing_lib(snap) == ["libuser"]
        assert len(calls) == 1
        mg._consumer_suites(snap, {"lone"})
        assert len(calls) == 2
        mg.cross_skill_importers([".claude/skills/lone/lone_mod.py"], snap)
        assert len(calls) == 3

    def test_scan_sources_result_drives_all_three(self, snap, monkeypatch):
        """E2：scan_sources 回報的文字是三處掃描唯一的資料來源（換掉它，三處結果都跟著變）。"""
        fake = {
            ".claude/skills/user/tests/test_u.py": "from lib import z\nimport lone_mod\n",
            ".claude/hooks/h.py": "import lone_mod\n",
        }
        monkeypatch.setattr(mg, "scan_sources", lambda root: (sorted(fake), dict(fake)))
        assert mg._skills_importing_lib(snap) == ["user"]
        assert mg._consumer_suites(snap, {"lone"}) == {mg.SUITE_HOOKS}
        assert mg.cross_skill_importers([".claude/skills/lone/lone_mod.py"], snap) == {"skill:user": ["lone_mod"]}


class TestCache:
    def test_e1_cache_scope_reads_each_file_once(self, snap, monkeypatch):
        """E1 對照：同兩次選擇，快取範圍外每檔讀兩次，範圍內每檔只讀一次。"""
        change = [".claude/lib/x.py", ".claude/skills/lone/lone_mod.py"]
        reads = _count_reads(monkeypatch)
        mg.select_suites(change, snap)
        mg.select_suites(change, snap)
        assert reads and max(reads.values()) == 2
        reads.clear()
        with mg.source_scan_cache():
            mg.select_suites(change, snap)
            mg.select_suites(change, snap)
            mg.cross_skill_importers(change, snap)
        assert reads and max(reads.values()) == 1

    def test_cache_keyed_by_root(self, snap, tmp_path, monkeypatch):
        other = tmp_path / "other"
        _touch(other, ".claude/skills/libuser/tests/test_l.py", "import os\n")
        calls = _count_scans(monkeypatch)
        with mg.source_scan_cache():
            assert mg._skills_importing_lib(snap) == ["libuser"]
            assert mg._skills_importing_lib(str(other)) == []
            assert mg._skills_importing_lib(snap) == ["libuser"]
        assert len(calls) == 2

    def test_cache_cleared_after_scope(self, snap, monkeypatch):
        with mg.source_scan_cache():
            assert mg._skills_importing_lib(snap) == ["libuser"]
        _touch(snap, ".claude/skills/user/tests/test_u.py", "from lib import y\n")
        assert mg._skills_importing_lib(snap) == ["libuser", "user"]


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_file(repo, name, text, msg):
    _touch(repo, name, text)
    git(repo, "add", name)
    git(repo, "commit", "-m", msg)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    commit_file(r, ".claude/skills/foo/tests/test_a.py", "", "foo tests")
    commit_file(r, ".claude/skills/foo/foo_system/__init__.py", "", "foo pkg")
    commit_file(r, ".claude/skills/bar/tests/test_b.py", "from foo_system import x\n", "bar importer")
    commit_file(r, ".claude/hooks/h.py", "import os\n", "hook")
    git(r, "checkout", "-q", "-b", "feat")
    commit_file(r, ".claude/skills/foo/foo_system/x.py", "x = 1\n", "foo change")
    git(r, "checkout", "-q", "main")
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
    return r


def test_gate_reads_each_snapshot_py_once(repo, monkeypatch):
    """單次閘門（含 _reusable 對每套件的選擇與跨 skill 理由列印）內，快照每個 .py 只讀一次。"""
    reads = _count_reads(monkeypatch)
    gate = mg.MergeGate(str(repo), lambda argv, cwd: (0, "ok"))
    base = git(repo, "rev-parse", "main")
    gate.verified_suites = {"skill:foo": base, "skill:bar": base, mg.SUITE_HOOKS: base}  # 逼 _reusable 逐套件選擇
    out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate)
    assert out.ok
    snap_reads = {p: n for p, n in reads.items() if mg.SNAPSHOT_PREFIX in p}
    assert snap_reads and max(snap_reads.values()) == 1, snap_reads


class TestSingleFileModule:
    def test_e1_unique_single_module_adds_importer(self, snap):
        """E1 對照：同一改動（skill 根的單檔），他 skill 有無匯入，選出的套件不同。"""
        change = [".claude/skills/lone/lone_mod.py"]
        assert mg.select_suites(change, snap) == ["skill:lone"]
        _touch(snap, ".claude/skills/user/tests/test_u.py", "import sys\nsys.path.insert(0, 'x')\nimport lone_mod\n")
        assert mg.select_suites(change, snap) == ["skill:lone", "skill:user"]
        assert mg.cross_skill_importers(change, snap) == {"skill:user": ["lone_mod"]}

    def test_e1_duplicate_single_module_not_added(self, snap):
        """E1 對照：同一匯入，模組名在另一 skill 重名時不加選。"""
        change = [".claude/skills/lone/lone_mod.py"]
        _touch(snap, ".claude/skills/user/tests/test_u.py", "from lone_mod import x\n")
        assert "skill:user" in mg.select_suites(change, snap)
        _touch(snap, ".claude/skills/libuser/scripts/lone_mod.py", "x = 2\n")
        assert mg.select_suites(change, snap) == ["skill:lone"]
        assert mg.cross_skill_importers(change, snap) == {}

    def test_single_module_under_scripts_counts(self, snap):
        _touch(snap, ".claude/skills/lone/scripts/lone_gate.py", "y = 1\n")
        _touch(snap, ".claude/skills/user/tests/test_u.py", "from lone_gate import y\n")
        assert mg.select_suites([".claude/skills/lone/scripts/lone_gate.py"], snap) == ["skill:lone", "skill:user"]

    def test_deleted_single_module_still_adds_importer(self, snap):
        """E2：單檔被刪除後快照已無該檔，匯入它的 skill 仍須加選。"""
        _touch(snap, ".claude/skills/user/tests/test_u.py", "import gone_mod\n")
        assert "skill:user" in mg.select_suites([".claude/skills/lone/gone_mod.py"], snap)

    def test_test_files_and_nested_files_not_treated_as_modules(self, snap):
        _touch(snap, ".claude/skills/user/tests/test_u.py", "import test_a\nimport helper\n")
        assert mg.select_suites([".claude/skills/lone/tests/test_a.py"], snap) == ["skill:lone"]
        assert mg.select_suites([".claude/skills/lone/references/helper.py"], snap) == ["skill:lone"]
