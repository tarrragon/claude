"""
合併閘門批次寫入與跟隨者撤離的競態（3.4.0-W1-278）

leader 在 update-ref 前以認領檔原子 rename（claim -> committing）搶下跟隨者；跟隨者撤離前以
rename（claim -> withdrawn）撤回。兩方只有一方 rename 成功：撤回成功 leader 不寫入；leader 先搶下
跟隨者等 leader 寫完後以祖先判定回報成功。分三層：注入交錯順序、sidecar 命名、雙 subprocess 實跑。
"""

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude"))

import merge_cas as mc  # noqa: E402
import merge_gate as mg  # noqa: E402
from lib import slot_gate  # noqa: E402
from test_merge_gate_batch import (  # noqa: E402,F401
    add_waiter, gate_for, git, make_branch, repo, sha_of,
)


def follower_setup(repo, tmp_path):
    """本行程扮演跟隨者：排隊檔、認領檔俱全；回傳 (跟隨者閘門, 領導者掛點, 批次項目)。"""
    slots = tmp_path / "slots"
    make_branch(repo, "feat/l", ["lib/f1.txt"])
    make_branch(repo, "feat/f", ["lib/f2.txt"])
    follower = gate_for(repo)
    follower.queue_extra("feat/f", "main", None)
    key, _sha = follower._own
    add_waiter(slots, 900, os.getpid(), "feat/f", sha_of(repo, "feat/f"), repo)
    slot_gate.write_sidecar(str(slots), "claim", os.getpid(), key, {"batch": "b7", "leader_pid": os.getpid()})
    item = mc.BatchItem("feat/f", sha_of(repo, "feat/f"), "Merge feat/f",
                        {"pid": os.getpid(), "key": key, "name": f"queue-{900:012d}-{os.getpid()}.json"})
    hooks = replace(gate_for(repo).batch_hooks("feat/l", "main"), collect=lambda: [item])
    return follower, hooks


def is_ancestor(repo, branch):
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha_of(repo, branch), "main"],
                          cwd=repo).returncode == 0


class TestInterleaving:
    def test_follower_withdraws_after_alive_leader_does_not_write(self, repo, tmp_path):
        follower, hooks = follower_setup(repo, tmp_path)
        seen = {}
        real_alive = hooks.alive

        def alive_then_withdraw(item):
            result = real_alive(item)
            seen["outcome"] = follower.landed_outcome("main", require_claim=False)  # 查存活後才撤離
            return result

        out = mc.merge_branch_cas("feat/l", repo=str(repo), batch=replace(hooks, alive=alive_then_withdraw))
        assert out.ok
        assert seen["outcome"] is None  # 跟隨者回報未合併
        assert not is_ancestor(repo, "feat/f")  # 與 leader 寫入結果一致：不寫入該票

    def test_leader_seizes_first_follower_reports_success(self, repo, tmp_path, monkeypatch):
        follower, hooks = follower_setup(repo, tmp_path)
        result, real_git = {}, mc._git_raw

        def run_follower():
            result["outcome"] = follower.landed_outcome("main", require_claim=False)

        def slow_update_ref(args, repo_dir, input_bytes=None):
            if args[0] == "update-ref" and "thread" not in result:
                result["thread"] = threading.Thread(target=run_follower)
                result["thread"].start()
                time.sleep(0.5)  # 讓跟隨者在 leader 已搶下、尚未寫入時嘗試撤離
            return real_git(args, repo_dir, input_bytes)

        monkeypatch.setattr(mc, "_git_raw", slow_update_ref)
        out = mc.merge_branch_cas("feat/l", repo=str(repo), batch=hooks)
        result["thread"].join(10)
        assert out.ok and is_ancestor(repo, "feat/f")
        assert result["outcome"] is not None and result["outcome"].ok  # 與 leader 寫入結果一致


    def test_leader_retry_restores_then_follower_withdraws_before_reseize(self, repo, tmp_path, monkeypatch):
        """領導者首次 update-ref 失敗並歸還認領；跟隨者須回頭重試撤回，領導者重搶時才會落敗。"""
        follower, hooks = follower_setup(repo, tmp_path)
        state, real_git, real_seize = {"seizes": 0}, mc._git_raw, hooks.seize

        def run_follower():
            state["outcome"] = follower.landed_outcome("main", require_claim=False)

        def failing_first_update_ref(args, repo_dir, input_bytes=None):
            if args[0] == "update-ref" and "thread" not in state:
                state["thread"] = threading.Thread(target=run_follower)
                state["thread"].start()
                time.sleep(0.5)  # 跟隨者此時看到 committing 並等待
                return subprocess.CompletedProcess(args, 1, b"", b"cannot lock ref")
            return real_git(args, repo_dir, input_bytes)

        def seize_after_follower_decides(item):
            state["seizes"] += 1
            if state["seizes"] == 2:
                state["thread"].join(5)  # 第二次搶認領前，跟隨者已做完判定
            return real_seize(item)

        monkeypatch.setattr(mc, "_git_raw", failing_first_update_ref)
        out = mc.merge_branch_cas("feat/l", repo=str(repo), batch=replace(hooks, seize=seize_after_follower_decides))
        state["thread"].join(10)
        assert out.ok
        follower_ok = state["outcome"] is not None and state["outcome"].ok
        assert follower_ok == is_ancestor(repo, "feat/f")  # 兩方結果一致
        assert not follower_ok  # 本交錯下跟隨者先撤回成功，領導者不寫入


DRIVER =textwrap.dedent("""
    import os, sys, time
    sys.path.insert(0, {scripts!r})
    sys.path.insert(0, {claude!r})
    import merge_gate as mg
    import worktree_manager as wm
    wm.get_project_root = lambda: {repo!r}
    def runner(argv, cwd):
        if "pub" in argv:  # 生成產物命令：造出快照所缺的檔，不計入套件執行
            os.makedirs(os.path.join(cwd, ".dart_tool"), exist_ok=True)
            open(os.path.join(cwd, ".dart_tool", "package_config.json"), "w").write("{{}}")
            return 0, "ok"
        with open({counter!r}, "a") as fh:
            fh.write("run\\n")
        time.sleep(1.0)
        return 0, "ok"
    gate = mg.MergeGate({repo!r}, runner)
    sys.exit(wm._merge_through_gate(gate, sys.argv[1], sys.argv[1], None, "Merge " + sys.argv[1]))
""")


class TestTwoProcesses:
    def test_two_real_processes_one_suite_run_two_merges(self, repo, tmp_path):
        make_branch(repo, "feat/a", ["lib/f1.txt"])
        make_branch(repo, "feat/b", ["lib/f2.txt"])
        counter = tmp_path / "counter.txt"
        script = tmp_path / "driver.py"
        script.write_text(DRIVER.format(
            scripts=str(Path(mg.__file__).parent), claude=str(Path(__file__).resolve().parents[4] / ".claude"),
            repo=str(repo), counter=str(counter)))
        slots = Path(os.environ["CLAUDE_SLOT_LOCK_DIR"])
        holder, _ = slot_gate.acquire_slot(["holder"], lambda: None, estimate_seconds=5)
        procs = []
        try:
            for name in ("feat/a", "feat/b"):
                procs.append(subprocess.Popen([sys.executable, str(script), name], cwd=repo,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
                deadline = time.time() + 15
                while time.time() < deadline and len(list(slots.glob("queue-*"))) < len(procs):
                    time.sleep(0.05)
        finally:
            holder.release()
        outs = [p.communicate(timeout=90)[0] for p in procs]
        assert [p.returncode for p in procs] == [0, 0], outs
        assert len(git(repo, "log", "--merges", "--format=%s", "main").splitlines()) == 2
        assert counter.read_text().count("run") == 1  # 套件只跑一次
        assert sorted(p.name for p in slots.iterdir() if p.name.startswith(("claim", "committing", "withdrawn"))) == []


class TestSidecarKinds:
    def test_rename_is_exclusive_and_sweep_knows_new_kinds(self, tmp_path):
        d = str(tmp_path)
        os.chmod(d, 0o700)
        key, dead = "0123456789abcdef", 2 ** 22 + 12345
        slot_gate.write_sidecar(d, "claim", os.getpid(), key, {"b": 1})
        assert slot_gate.rename_sidecar(d, os.getpid(), key, "claim", "committing") is True
        assert slot_gate.rename_sidecar(d, os.getpid(), key, "claim", "withdrawn") is False
        assert slot_gate.read_sidecar(d, "committing", os.getpid(), key) == {"b": 1}
        for kind in ("committing", "withdrawn"):
            slot_gate.write_sidecar(d, kind, dead, key, {"x": 1})
        slot_gate.sweep_sidecars(d)
        assert json.dumps(sorted(os.listdir(d))) == json.dumps([f"committing-{os.getpid()}-{key}.json"])
