"""
合併閘門自動批次測試（3.3.1-W1-001.1）

分三層：merge_cas 的批次鏈（假檢查）、MergeGate 的候選組成與 follower 判定（真名額目錄）、
worktree_manager 的成功與逾時路徑。E1 以 N=1 與 N=4 各跑一次斷言產物不同；E2 放已知重疊的分支，
斷言它被判為衝突不併。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude"))

import merge_cas as mc  # noqa: E402
import merge_gate as mg  # noqa: E402
import worktree_manager as wm  # noqa: E402
from lib import slot_gate  # noqa: E402


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_file(repo, name, text, msg):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-m", msg)


def make_branch(repo, name, files):
    git(repo, "checkout", "-b", name, "main")
    for fname in files:
        commit_file(repo, fname, f"{name}\n", f"{name} {fname}")
    git(repo, "checkout", "main")


def sha_of(repo, branch):
    return git(repo, "rev-parse", f"refs/heads/{branch}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    commit_file(r, "pubspec.yaml", "name: app\n", "base pubspec")
    for i in range(1, 6):
        commit_file(r, f"lib/f{i}.txt", "base\n", f"base f{i}")
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
    monkeypatch.chdir(r)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(r))
    return r


@pytest.fixture
def sleepers():
    procs = []
    yield procs
    for p in procs:
        p.kill()
        p.wait()


def hooks_for(repo, names, alive=None, refused=None, dropped=None):
    """follower 為 names 的假掛點；alive 預設全存活。"""
    items = [mc.BatchItem(n, sha_of(repo, n), f"Merge {n} (T-{n})") for n in names]
    return mc.BatchHooks(
        collect=lambda: items,
        alive=alive or (lambda _i: True),
        on_refused=lambda i, r: refused.append((i.branch, r)) if refused is not None else None,
        on_dropped=lambda i: dropped.append(i.branch) if dropped is not None else None,
    )


def counting_check(calls, red_files=()):
    """檢查：合併 commit 的 tree 中 red_files 任一檔內容已非 base（壞票內容在樹中）即紅燈。"""
    def check(commit, ref, old, attempt):
        calls.append(commit)
        for f in red_files:
            shown = subprocess.run(["git", "show", f"{commit}:{f}"], capture_output=True, text=True).stdout
            if shown.strip() != "base":  # 該檔已被某分支改動 = 壞票的內容在樹中
                return mc.CheckResult(False, f"[flutter] 全套件紅燈（exit 1），失敗項：{f}")
        return mc.CheckResult(True)
    return check


def merge_subjects(repo):
    return git(repo, "log", "--merges", "--format=%s", "main").splitlines()


class TestBatchChain:
    def test_each_unit_keeps_own_merge_commit_and_one_check(self, repo):
        for i in (1, 2, 3, 4):
            make_branch(repo, f"feat/t{i}", [f"lib/f{i}.txt"])
        calls = []
        out = mc.merge_branch_cas("feat/t1", repo=str(repo), pre_merge_check=counting_check(calls),
                                  message="Merge feat/t1 (T-feat/t1)",
                                  batch=hooks_for(repo, ["feat/t2", "feat/t3", "feat/t4"]))
        assert out.ok and len(calls) == 1  # 整批只測一次鏈尾
        assert sorted(merge_subjects(repo)) == sorted(f"Merge feat/t{i} (T-feat/t{i})" for i in (1, 2, 3, 4))
        assert out.commit_sha == git(repo, "log", "--merges", "--format=%H", "--grep=feat/t1", "main")

    def test_e1_solo_versus_batch_differ(self, repo):
        """E1：同批 fixture，單票（N=1 等價，不給 batch）與批次各跑一次，產物不同。"""
        for i in (1, 2, 3, 4):
            make_branch(repo, f"feat/t{i}", [f"lib/f{i}.txt"])
        base = git(repo, "rev-parse", "main")
        solo_calls = []
        for i in (1, 2, 3, 4):
            assert mc.merge_branch_cas(f"feat/t{i}", repo=str(repo), pre_merge_check=counting_check(solo_calls)).ok
        git(repo, "update-ref", "refs/heads/main", base)
        git(repo, "reset", "-q", "--hard")
        batch_calls = []
        assert mc.merge_branch_cas("feat/t1", repo=str(repo), pre_merge_check=counting_check(batch_calls),
                                   batch=hooks_for(repo, ["feat/t2", "feat/t3", "feat/t4"])).ok
        assert len(solo_calls) == 4 and len(batch_calls) == 1

    def test_red_third_only_third_refused(self, repo):
        for i in (1, 2, 3, 4):
            make_branch(repo, f"feat/t{i}", [f"lib/f{i}.txt"])
        calls, refused = [], []
        out = mc.merge_branch_cas("feat/t1", repo=str(repo),
                                  pre_merge_check=counting_check(calls, red_files=["lib/f3.txt"]),
                                  batch=hooks_for(repo, ["feat/t2", "feat/t3", "feat/t4"], refused=refused))
        assert out.ok
        assert [b for b, _ in refused] == ["feat/t3"] and "全套件紅燈" in refused[0][1]
        assert git(repo, "show", "main:lib/f3.txt") == "base"  # 紅燈票未寫入
        assert git(repo, "show", "main:lib/f4.txt") == "feat/t4"
        assert len(calls) == 4  # 鏈尾、前綴 m2、前綴 m3（定位）、重建後的 t4

    def test_red_leader_followers_still_written(self, repo):
        for i in (1, 2, 3):
            make_branch(repo, f"feat/t{i}", [f"lib/f{i}.txt"])
        out = mc.merge_branch_cas("feat/t1", repo=str(repo),
                                  pre_merge_check=counting_check([], red_files=["lib/f1.txt"]),
                                  batch=hooks_for(repo, ["feat/t2", "feat/t3"]))
        assert not out.ok and "全套件紅燈" in out.error
        assert git(repo, "show", "main:lib/f1.txt") == "base"
        assert git(repo, "show", "main:lib/f3.txt") == "feat/t3"

    def test_follower_gone_before_write_is_dropped_not_written(self, repo):
        """修訂 High 1：入選者排隊檔在 CAS 前消失，自鏈中剔除並重建，不寫入它。"""
        for i in (1, 2, 3):
            make_branch(repo, f"feat/t{i}", [f"lib/f{i}.txt"])
        dropped = []
        out = mc.merge_branch_cas("feat/t1", repo=str(repo), pre_merge_check=counting_check([]),
                                  batch=hooks_for(repo, ["feat/t2", "feat/t3"],
                                                  alive=lambda i: i.branch != "feat/t2", dropped=dropped))
        assert out.ok and dropped == ["feat/t2"]
        assert git(repo, "show", "main:lib/f2.txt") == "base"
        assert git(repo, "show", "main:lib/f3.txt") == "feat/t3"

    def test_follower_conflict_dropped_leader_unaffected(self, repo):
        make_branch(repo, "feat/t1", ["lib/f1.txt"])
        make_branch(repo, "feat/t2", ["lib/f1.txt"])  # 與領導者同檔：鏈中衝突
        dropped = []
        out = mc.merge_branch_cas("feat/t1", repo=str(repo), pre_merge_check=counting_check([]),
                                  batch=hooks_for(repo, ["feat/t2"], dropped=dropped))
        assert out.ok and dropped == ["feat/t2"]


def add_waiter(slots, seq, pid, branch, sha, repo, **over):
    info = {"pid": pid, "command": ["merge-gate", branch], "estimate": 10.0, "arrived": "x",
            "repo": str(repo.resolve()), "branch": branch, "branch_sha": sha, "target": "main",
            "message": f"Merge {branch}"}
    info.update(over)
    (Path(slots) / f"queue-{seq:012d}-{pid}.json").write_text(json.dumps(info))


def sleeper(sleepers):
    p = subprocess.Popen(["sleep", "60"])
    sleepers.append(p)
    return p.pid


def gate_for(repo):
    return mg.MergeGate(str(repo), lambda a, c: (0, "ok"))


class TestCollect:
    def setup_branches(self, repo):
        make_branch(repo, "feat/3.3.1-W1-213.8", ["lib/f1.txt"])  # 領導者
        make_branch(repo, "feat/3.3.1-W1-overlap", ["lib/f1.txt"])  # 與領導者重疊
        make_branch(repo, "feat/3.3.1-W1-214", ["lib/f2.txt"])
        make_branch(repo, "feat/3.3.1-W1-215", ["lib/f3.txt"])

    def collect(self, repo, sleepers, slots, extra=None):
        self.setup_branches(repo)
        gate = gate_for(repo)
        names = ["feat/3.3.1-W1-overlap", "feat/3.3.1-W1-214", "feat/3.3.1-W1-215"]
        with gate.hold("feat/3.3.1-W1-213.8", "main"):
            for n, name in enumerate(names):
                add_waiter(slots, 900 + n, sleeper(sleepers), name, sha_of(repo, name), repo, **(extra or {}))
            return gate, gate.collect_batch("feat/3.3.1-W1-213.8", "main")

    def test_overlapping_branch_is_judged_conflict_e2(self, repo, sleepers, tmp_path):
        gate, items = self.collect(repo, sleepers, tmp_path / "slots")
        assert [i.branch for i in items] == ["feat/3.3.1-W1-214", "feat/3.3.1-W1-215"]
        assert "feat/3.3.1-W1-overlap" not in [i.branch for i in items]
        assert gate.batch_id.startswith("b")

    def test_claims_written_only_for_included(self, repo, sleepers, tmp_path):
        slots = tmp_path / "slots"
        gate, items = self.collect(repo, sleepers, slots)
        claims = sorted(p.name for p in slots.glob("claim-*"))
        assert len(claims) == 2
        for i in items:
            c = slot_gate.read_sidecar(str(slots), "claim", i.ref["pid"], i.ref["key"])
            assert c["batch"] == gate.batch_id

    def test_e1_batch_max_one_disables(self, repo, sleepers, tmp_path, monkeypatch):
        monkeypatch.setenv(mg.BATCH_MAX_ENV, "1")
        _, items = self.collect(repo, sleepers, tmp_path / "slots")
        assert items == []

    def test_batch_max_caps_followers(self, repo, sleepers, tmp_path, monkeypatch):
        monkeypatch.setenv(mg.BATCH_MAX_ENV, "2")
        _, items = self.collect(repo, sleepers, tmp_path / "slots")
        assert [i.branch for i in items] == ["feat/3.3.1-W1-214"]

    def test_stale_sha_and_old_format_not_batched(self, repo, sleepers, tmp_path):
        slots = tmp_path / "slots"
        self.setup_branches(repo)
        gate = gate_for(repo)
        with gate.hold("feat/3.3.1-W1-213.8", "main"):
            add_waiter(slots, 900, sleeper(sleepers), "feat/3.3.1-W1-214", "0" * 40, repo)
            (slots / f"queue-{901:012d}-{sleeper(sleepers)}.json").write_text(
                json.dumps({"command": ["merge-gate", "x"], "estimate": 1}))  # 舊格式無欄位
            assert gate.collect_batch("feat/3.3.1-W1-213.8", "main") == []

    def test_declaration_change_not_batched(self, repo, sleepers, tmp_path):
        slots = tmp_path / "slots"
        make_branch(repo, "feat/lead", ["lib/f1.txt"])
        make_branch(repo, "feat/decl", [mg.DECLARATION_PATH])
        gate = gate_for(repo)
        with gate.hold("feat/lead", "main"):
            add_waiter(slots, 900, sleeper(sleepers), "feat/decl", sha_of(repo, "feat/decl"), repo)
            assert gate.collect_batch("feat/lead", "main") == []

    def test_holder_estimate_updated_for_union(self, repo, sleepers, tmp_path):
        slots = tmp_path / "slots"
        self.setup_branches(repo)
        gate = gate_for(repo)
        with gate.hold("feat/3.3.1-W1-213.8", "main"):
            add_waiter(slots, 900, sleeper(sleepers), "feat/3.3.1-W1-214", sha_of(repo, "feat/3.3.1-W1-214"), repo)
            gate.collect_batch("feat/3.3.1-W1-213.8", "main")
            info = json.loads((slots / "heavy-slot-0.holder.json").read_text())
            assert info["estimate"] == mg.suite_estimate_seconds([mg.SUITE_FLUTTER], str(repo))


class TestFollowerSide:
    def own_key(self, gate, branch):
        gate.queue_extra(branch, "main", None)
        return gate._own

    def test_verdict_is_reported_as_refusal(self, repo, tmp_path):
        import os
        slots = tmp_path / "slots"
        make_branch(repo, "feat/f", ["lib/f1.txt"])
        gate = gate_for(repo)
        with gate.hold("feat/f", "main"):
            key, _ = self.own_key(gate, "feat/f")
            slot_gate.write_sidecar(str(slots), "verdict", os.getpid(), key,
                                    {"batch": "b1", "result": "拒絕", "reason": "[flutter] 全套件紅燈（exit 1）"})
            out = gate.followed_outcome("feat/f", "main")
        assert out is not None and not out.ok and out.via == "批次 b1"
        assert mg.gate_result_label(out.error) == mg.GATE_RED

    def land(self, repo, branch):
        git(repo, "merge", "--no-ff", "-m", f"Merge {branch}", branch)

    def claim(self, gate, slots, branch):
        import os
        key, _ = self.own_key(gate, branch)
        slot_gate.write_sidecar(str(slots), "claim", os.getpid(), key, {"batch": "b9"})

    def test_claim_and_ancestor_is_success_with_source(self, repo, tmp_path):
        slots = tmp_path / "slots"
        make_branch(repo, "feat/f", ["lib/f1.txt"])
        gate = gate_for(repo)
        with gate.hold("feat/f", "main"):
            self.claim(gate, slots, "feat/f")
            self.land(repo, "feat/f")
            out = gate.followed_outcome("feat/f", "main")
        assert out.ok and out.via == "批次 b9" and out.commit_sha == git(repo, "rev-parse", "main")

    def test_claim_without_landing_runs_solo(self, repo, tmp_path):
        slots = tmp_path / "slots"
        make_branch(repo, "feat/f", ["lib/f1.txt"])
        gate = gate_for(repo)
        with gate.hold("feat/f", "main"):
            self.claim(gate, slots, "feat/f")
            assert gate.followed_outcome("feat/f", "main") is None
        assert list(slots.glob("claim-*")) == []

    def test_ancestor_without_claim_keeps_existing_behavior(self, repo, tmp_path):
        """PM 裁定：無認領檔而已是祖先視為閘門外合併，維持既有「已包含」錯誤路徑。"""
        make_branch(repo, "feat/f", ["lib/f1.txt"])
        gate = gate_for(repo)
        with gate.hold("feat/f", "main"):
            self.land(repo, "feat/f")
            assert gate.followed_outcome("feat/f", "main") is None
        landed = gate.landed_outcome("main", require_claim=False)
        assert landed.via == "未經本閘門"


class TestManagerPaths:
    def test_follower_success_skips_sync_and_three_planes(self, monkeypatch, capsys):
        def boom(*a, **k):
            raise AssertionError("follower 成功路徑不得核對三平面")
        monkeypatch.setattr(wm, "_verify_three_planes", boom)
        rc = wm._print_merge_outcome(mc.MergeOutcome(True, commit_sha="abc123", via="批次 b9"), "T")
        out = capsys.readouterr().out
        assert rc == 0 and "批次 b9" in out and "abc123" in out

    def run_timeout(self, repo, monkeypatch, land):
        from contextlib import contextmanager
        make_branch(repo, "feat/f", ["lib/f1.txt"])
        if land:
            git(repo, "merge", "--no-ff", "-m", "Merge feat/f", "feat/f")
        gate = gate_for(repo)

        @contextmanager
        def timed_out(self_, branch, base):
            self_.queue_extra(branch, base, None)
            raise mg.SlotWaitRefused(125)
            yield

        monkeypatch.setattr(mg.MergeGate, "hold", timed_out)
        return wm._merge_through_gate(gate, "feat/f", "feat/f", None)

    def test_timeout_after_leader_wrote_reports_success(self, repo, monkeypatch, capsys):
        assert self.run_timeout(repo, monkeypatch, land=True) == 0
        assert "未經本閘門" in capsys.readouterr().out

    def test_timeout_without_landing_still_refused(self, repo, monkeypatch):
        assert self.run_timeout(repo, monkeypatch, land=False) == 125
