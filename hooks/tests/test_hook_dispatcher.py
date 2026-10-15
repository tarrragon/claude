#!/usr/bin/env python3
"""
hook-dispatcher 測試

涵蓋：合併規則、單支例外與逾時隔離、stdin/環境隔離、fail_closed 保留、
分派機制失敗的退回路徑、registry 與 settings.json 一致性，
以及已知應被攔下的輸入（未包裝的全套件 pytest）經分派程序後仍被 deny。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HOOKS_DIR.parent.parent
sys.path.insert(0, str(HOOKS_DIR))

_spec = importlib.util.spec_from_file_location("hook_dispatcher_module", HOOKS_DIR / "hook-dispatcher.py")
disp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(disp)

HookResult = disp.HookResult


def _deny_json(reason, level="deny"):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": level,
        "permissionDecisionReason": reason}}, ensure_ascii=False)


def _write_hook(tmp_path, name, body):
    p = tmp_path / (name + ".py")
    p.write_text(body, encoding="utf-8")
    return {"path": p.name}


# 同程序測試的預算須 >= DEFAULT_HOOK_TIMEOUT，否則 dispatch 會把該支與其後全部改走尾段子程序，
# 名義上測同程序的斷言就會在子程序裡空過（鑑別力為零）。刻意測尾段的案例才傳小預算。
INPROC_BUDGET = disp.DEFAULT_GROUP_BUDGET

PID_PROBE = "import os, sys\nsys.stderr.write('pid=' + str(os.getpid()))\n"


def _pid_probe(tmp_path, name="pid_probe"):
    return _write_hook(tmp_path, name, PID_PROBE)


def _assert_ran_in_process(result):
    """只在同程序執行才成立：探針回報的 pid 等於測試程序 pid（改走子程序則不同）。"""
    assert result.stderr == "pid=" + str(os.getpid()), result.stderr


# ---------- 合併規則 ----------

class TestMerge:
    def test_any_exit2_blocks_whole(self):
        code, _, err = disp.merge_results([
            HookResult("a", 0), HookResult("b", 2, stderr="擋下原因"), HookResult("c", 0)])
        assert code == 2
        assert "[b] 擋下原因" in err

    def test_nonblocking_error_is_exit1(self):
        code, _, _ = disp.merge_results([HookResult("a", 0), HookResult("b", 1)])
        assert code == 1

    def test_all_zero_is_zero_and_silent(self):
        assert disp.merge_results([HookResult("a", 0), HookResult("b", 0)]) == (0, "", "")

    def test_single_deny_reason_passes_verbatim(self):
        reason = "偵測到未包裝的命令\n  python3 x -- pytest"
        code, out, _ = disp.merge_results([
            HookResult("a", 0, _deny_json("放行原因", "allow")),
            HookResult("b", 0, _deny_json(reason))])
        obj = json.loads(out)["hookSpecificOutput"]
        assert code == 0
        assert obj["permissionDecision"] == "deny"
        assert obj["permissionDecisionReason"] == reason

    def test_strictest_wins_deny_over_ask_over_allow(self):
        _, out, _ = disp.merge_results([
            HookResult("a", 0, _deny_json("r1", "allow")),
            HookResult("b", 0, _deny_json("r2", "ask")),
            HookResult("c", 0, _deny_json("r3", "deny"))])
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_multiple_deny_reasons_are_prefixed(self):
        _, out, _ = disp.merge_results([
            HookResult("a", 0, _deny_json("甲")), HookResult("b", 0, _deny_json("乙"))])
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "[a] 甲" in reason and "[b] 乙" in reason

    def test_exit2_also_carries_json_deny_reason_in_stderr(self):
        _, _, err = disp.merge_results([
            HookResult("a", 2, stderr="x"), HookResult("b", 0, _deny_json("JSON 理由"))])
        assert "JSON 理由" in err

    def test_additional_context_joined_without_prefix(self):
        ctx = lambda t: json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": t}})
        _, out, _ = disp.merge_results([HookResult("a", 0, ctx("[Guard A] 一")), HookResult("b", 0, ctx("[Guard B] 二"))])
        text = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        assert text == "[Guard A] 一\n\n[Guard B] 二"

    def test_stderr_prefixed_per_hook(self):
        _, _, err = disp.merge_results([HookResult("a", 0, stderr="l1\nl2")])
        assert err == "[a] l1\n[a] l2"


# ---------- 隔離 ----------

class TestIsolation:
    def test_exception_in_one_hook_does_not_stop_others_and_is_visible(self, tmp_path):
        bad = _write_hook(tmp_path, "bad", "raise RuntimeError('boom')\n")
        good = _write_hook(tmp_path, "good", "import sys\nsys.stderr.write('ok-ran')\n")
        probe = _pid_probe(tmp_path)
        results = disp.dispatch([bad, good, probe], "{}", tmp_path, INPROC_BUDGET)
        assert results[0].code == 1 and "boom" in results[0].error
        assert results[1].code == 0 and results[1].stderr == "ok-ran"
        _assert_ran_in_process(results[2])
        _, _, err = disp.merge_results(results)
        assert "[bad] 分派器" in err and "boom" in err

    def test_exit2_from_one_hook_blocks_whole(self, tmp_path):
        # 合併規則與執行模式無關（同程序或尾段子程序皆同結果），預算沿用小值亦可；此處不主張同程序
        blocker = _write_hook(tmp_path, "blocker", "import sys\nsys.stderr.write('no')\nsys.exit(2)\n")
        other = _write_hook(tmp_path, "other", "pass\n")
        code, _, err = disp.merge_results(disp.dispatch([blocker, other], "{}", tmp_path, 30))
        assert code == 2 and "[blocker] no" in err

    def test_each_hook_gets_fresh_stdin(self, tmp_path):
        body = "import os, sys\nsys.stderr.write(sys.stdin.read() + '|' + str(os.getpid()))\n"
        a, b = _write_hook(tmp_path, "a", body), _write_hook(tmp_path, "b", body)
        results = disp.dispatch([a, b], "PAYLOAD", tmp_path, INPROC_BUDGET)
        # 帶 pid 後綴：確認兩支都在測試程序內執行，stdin 隔離才真的被行使
        assert [r.stderr for r in results] == ["PAYLOAD|" + str(os.getpid())] * 2

    def test_environment_cwd_and_path_restored(self, tmp_path):
        mutate = _write_hook(tmp_path, "mutate",
                             "import os, sys\nos.environ['DISP_X']='1'\nos.chdir('/')\nsys.path.insert(0,'/nonexistent-disp')\n"
                             "sys.stderr.write('pid=' + str(os.getpid()))\n")
        cwd, path0 = os.getcwd(), list(sys.path)
        results = disp.dispatch([mutate], "{}", tmp_path, INPROC_BUDGET)
        _assert_ran_in_process(results[0])  # 同程序才真的改過 environ/cwd/sys.path，還原斷言才有鑑別力
        assert "DISP_X" not in os.environ
        assert os.getcwd() == cwd
        assert sys.path == path0

    def test_timeout_kills_only_that_hook(self, tmp_path):
        slow = _write_hook(tmp_path, "slow", "import time\ntime.sleep(5)\n")
        fast = _pid_probe(tmp_path, "fast")
        slow["timeout"] = 0.3
        results = disp.dispatch([slow, fast], "{}", tmp_path, INPROC_BUDGET)
        assert results[0].code == 1 and "逾時" in results[0].error
        assert results[1].code == 0
        _assert_ran_in_process(results[1])

    def test_exhausted_budget_defers_later_hooks_to_tail_instead_of_skipping(self, tmp_path):
        slow = _write_hook(tmp_path, "slow", "import time\ntime.sleep(5)\n")
        later = _write_hook(tmp_path, "later", "import sys\nsys.stderr.write('tail-ran')\n")
        slow["timeout"] = 0.3
        results = disp.dispatch([slow, later], "{}", tmp_path, 5)
        assert "逾時" in results[0].error
        assert results[1].code == 0 and results[1].stderr == "tail-ran"
        assert "預算用盡" not in results[1].error

    def test_missing_hook_file_is_visible_not_silent(self, tmp_path):
        results = disp.dispatch([{"path": "nope.py"}], "{}", tmp_path, 30)
        assert results[0].code == 1 and "不存在" in results[0].error

    def test_fail_closed_guard_still_blocks_on_crash(self, tmp_path):
        body = (
            "import sys\n"
            "sys.path.insert(0, {!r})\n"
            "from lib import run_hook_safely\n"
            "def main():\n    raise RuntimeError('guard crashed')\n"
            "if __name__ == '__main__':\n"
            "    sys.exit(run_hook_safely(main, 'disp-test-guard', fail_closed=True))\n"
        ).format(str(PROJECT_ROOT / ".claude"))
        guard = _write_hook(tmp_path, "guard", body)
        probe = _pid_probe(tmp_path)
        results = disp.dispatch([guard, probe], "{}", tmp_path, INPROC_BUDGET)
        assert results[0].code == 2
        assert disp.merge_results(results)[0] == 2
        _assert_ran_in_process(results[1])  # 守衛之後的 hook 仍在同程序，代表守衛走的是同程序路徑


# ---------- linked worktree 下的專案根一致性 ----------

class TestProjectRootInLinkedWorktree:
    """同程序先後執行的 hook，經專案根快取取得的根須與各自單獨執行相同。"""

    PROBE = (
        "import sys\n"
        "sys.path.insert(0, {claude_dir!r})\n"
        "from lib import get_project_root\n"
        "sys.stderr.write(str(get_project_root()))\n"
    )
    MUTATE = (
        "import os\n"
        "os.environ['CLAUDE_PROJECT_DIR'] = '/nonexistent-other-root'\n"
        "os.chdir('/')\n"
    )

    def _is_linked_worktree(self):
        def git(*a):
            return subprocess.run(["git", "-C", str(PROJECT_ROOT)] + list(a), capture_output=True,
                                  text=True).stdout.strip()
        return Path(git("rev-parse", "--git-dir")).resolve() != Path(
            git("rev-parse", "--git-common-dir")).resolve() if git("rev-parse", "--git-dir") else False

    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
        monkeypatch.chdir(PROJECT_ROOT)

    def _standalone_root(self, probe_path):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "HOOK_TEST_ISOLATION")}
        p = subprocess.run([sys.executable, str(probe_path)], capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), env=env)
        return p.stderr.strip()

    def test_roots_after_in_process_sequence_match_standalone(self, tmp_path, monkeypatch):
        probe_body = self.PROBE.format(claude_dir=str(PROJECT_ROOT / ".claude"))
        a = _write_hook(tmp_path, "probe_a", probe_body)
        mutate = _write_hook(tmp_path, "mutate_env", self.MUTATE)
        b = _write_hook(tmp_path, "probe_b", probe_body)
        want = self._standalone_root(tmp_path / "probe_a.py")
        self._clean_env(monkeypatch)
        from lib.hook_base import clear_project_root_cache
        clear_project_root_cache()
        pid = _pid_probe(tmp_path)
        results = disp.dispatch([a, mutate, b, pid], "{}", tmp_path, INPROC_BUDGET)
        _assert_ran_in_process(results[3])  # 全序列同程序，專案根快取才真的被共用
        assert results[0].stderr.strip() == want
        assert results[2].stderr.strip() == want
        assert os.getcwd() == str(PROJECT_ROOT)
        assert "CLAUDE_PROJECT_DIR" not in os.environ

    def test_worktree_root_is_read_when_cwd_is_linked_worktree(self, tmp_path, monkeypatch):
        if not self._is_linked_worktree():
            pytest.skip("目前 checkout 不是 linked worktree")
        probe_body = self.PROBE.format(claude_dir=str(PROJECT_ROOT / ".claude"))
        a = _write_hook(tmp_path, "probe_a", probe_body)
        self._clean_env(monkeypatch)
        from lib.hook_base import clear_project_root_cache
        clear_project_root_cache()
        pid = _pid_probe(tmp_path)
        results = disp.dispatch([a, pid], "{}", tmp_path, INPROC_BUDGET)
        _assert_ran_in_process(results[1])
        assert Path(results[0].stderr.strip()).resolve() == PROJECT_ROOT.resolve()


class TestSharedStateRootCacheIsolation:
    """同程序內 get_project_root 與 get_shared_state_root 兩個快取互不汙染（自建 linked worktree）。"""

    # 預算須 >= DEFAULT_HOOK_TIMEOUT，否則 dispatch 會把 hook 全部改走尾段子程序，等於沒測同程序快取
    BUDGET = disp.DEFAULT_GROUP_BUDGET

    PROBE_PROJECT = (
        "import sys\n"
        "sys.path.insert(0, {claude_dir!r})\n"
        "from lib import get_project_root\n"
        "sys.stderr.write(str(get_project_root()))\n"
    )
    PROBE_SHARED = (
        "import sys\n"
        "sys.path.insert(0, {claude_dir!r})\n"
        "from lib.hook_base import get_shared_state_root\n"
        "sys.stderr.write(str(get_shared_state_root()))\n"
    )

    @pytest.fixture
    def repos(self, tmp_path, monkeypatch):
        main = tmp_path / "main_repo"
        wt = tmp_path / "linked_wt"
        main.mkdir()

        def git(*a):
            subprocess.run(["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@t"] + list(a),
                           check=True, capture_output=True)
        git("init", "-q")
        git("commit", "-q", "--allow-empty", "-m", "init")
        git("worktree", "add", "-q", str(wt), "-b", "wt-branch")
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
        monkeypatch.chdir(wt)
        from lib.hook_base import clear_project_root_cache
        clear_project_root_cache()
        yield main.resolve(), wt.resolve()
        clear_project_root_cache()

    def _probes(self, tmp_path):
        claude_dir = str(PROJECT_ROOT / ".claude")
        proj = _write_hook(tmp_path, "probe_project", self.PROBE_PROJECT.format(claude_dir=claude_dir))
        shared = _write_hook(tmp_path, "probe_shared", self.PROBE_SHARED.format(claude_dir=claude_dir))
        return proj, shared

    def _standalone(self, tmp_path, name, cwd):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "HOOK_TEST_ISOLATION")}
        p = subprocess.run([sys.executable, str(tmp_path / (name + ".py"))], capture_output=True,
                           text=True, cwd=str(cwd), env=env)
        return Path(p.stderr.strip()).resolve()

    def test_e2_roots_differ(self, repos):
        main, wt = repos
        assert main != wt

    @pytest.mark.parametrize("order", ["project_first", "shared_first"])
    def test_roots_per_kind_in_both_orders_match_standalone(self, tmp_path, repos, order):
        main, wt = repos
        proj, shared = self._probes(tmp_path)
        entries = [proj, shared] if order == "project_first" else [shared, proj]
        results = {r.name: Path(r.stderr.strip()).resolve()
                   for r in disp.dispatch(entries, "{}", tmp_path, self.BUDGET)}
        assert results["probe_project"] == wt
        assert results["probe_shared"] == main
        # E1：單獨以子程序執行讀到的根相同
        assert self._standalone(tmp_path, "probe_project", wt) == results["probe_project"]
        assert self._standalone(tmp_path, "probe_shared", wt) == results["probe_shared"]

    def test_e2_polluted_cache_would_be_detected(self, tmp_path, repos):
        """正向對照：人為讓兩者共用同一快取值時，斷言必須翻紅（證明測試有鑑別力）。"""
        main, wt = repos
        proj, shared = self._probes(tmp_path)
        polluter = _write_hook(
            tmp_path, "polluter",
            "import sys\n"
            "sys.path.insert(0, {!r})\n"
            "import lib.hook_base as hb\n"
            "import os\n"
            "hb._MAIN_REPO_ROOT_CACHE[os.getcwd()] = hb.get_project_root()\n".format(
                str(PROJECT_ROOT / ".claude")))
        import lib.hook_base as hb
        try:
            rs = disp.dispatch([polluter, proj, shared], "{}", tmp_path, self.BUDGET)
            results = {r.name: Path(r.stderr.strip()).resolve() for r in rs}
        finally:
            hb.clear_project_root_cache()
        assert results["probe_shared"] != main


# ---------- 子程序輸出不汙染分派器 stdout ----------

class TestChildProcessOutputIsolation:
    """hook 啟動且不擷取輸出的子程序，其文字不得出現在分派器真實 stdout（須維持合法 JSON）。"""

    BUDGET = disp.DEFAULT_GROUP_BUDGET  # 須 >= DEFAULT_HOOK_TIMEOUT，否則改走尾段子程序而沒測到同程序路徑

    LEAKER = (
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, '-c', \"print('LEAKED-OUT'); import sys; sys.stderr.write('LEAKED-ERR')\"],\n"
        "               capture_output=False)\n"
        "print('{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", "
        "\"permissionDecision\": \"deny\", \"permissionDecisionReason\": \"r\"}}')\n"
    )

    DRIVER = (
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        "spec = importlib.util.spec_from_file_location('d', {hook_dispatcher!r})\n"
        "d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)\n"
        "rs = d.dispatch([{{'path': 'leaker.py'}}], '{{}}', Path({root!r}), d.DEFAULT_GROUP_BUDGET)\n"
        "code, out, err = d.merge_results(rs, 'PreToolUse')\n"
        "sys.stdout.write(out + '\\n')\n"
    )

    def _run_driver(self, tmp_path):
        _write_hook(tmp_path, "leaker", self.LEAKER)
        driver = tmp_path / "driver.py"
        driver.write_text(self.DRIVER.format(
            hook_dispatcher=str(HOOKS_DIR / "hook-dispatcher.py"), root=str(tmp_path)), encoding="utf-8")
        return subprocess.run([sys.executable, str(driver)], capture_output=True, text=True)

    def test_dispatcher_stdout_is_valid_json_when_child_leaks(self, tmp_path):
        """E2：修正前子程序文字排在 JSON 前面，json.loads 失敗而翻紅"""
        p = self._run_driver(tmp_path)
        obj = json.loads(p.stdout)
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "LEAKED" not in p.stdout

    def test_child_output_lands_in_hook_stderr(self, tmp_path):
        _write_hook(tmp_path, "leaker", self.LEAKER)
        r = disp.dispatch([{"path": "leaker.py"}], "{}", tmp_path, self.BUDGET)[0]
        assert "LEAKED-OUT" in r.stderr and "LEAKED-ERR" in r.stderr
        assert "LEAKED" not in r.stdout

    def test_fds_restored_after_timeout(self, tmp_path):
        """逾時中斷（SIGALRM）時 fd 1/2 仍須還原"""
        hang = _write_hook(tmp_path, "hang", "import time\ntime.sleep(5)\n")
        hang["timeout"] = 0.3
        before = (os.fstat(1).st_ino, os.fstat(2).st_ino)
        probe = _pid_probe(tmp_path)
        rs = disp.dispatch([hang, probe], "{}", tmp_path, self.BUDGET)
        assert rs[0].error
        _assert_ran_in_process(rs[1])  # 逾時中斷後的下一支仍在同程序，代表 fd 還原發生在同程序路徑
        assert (os.fstat(1).st_ino, os.fstat(2).st_ino) == before


# ---------- 失敗語意 ----------

class TestFailureSemantics:
    def test_inprocess_failure_falls_back_to_subprocess(self, tmp_path, monkeypatch):
        blocker = _write_hook(tmp_path, "blocker", "import sys\nsys.stderr.write('sub')\nsys.exit(2)\n")

        def boom(*a, **k):
            raise OSError("機制失敗")
        calls = []

        def counting_boom(*a, **k):
            calls.append(1)
            return boom(*a, **k)
        monkeypatch.setattr(disp, "run_inprocess", counting_boom)
        results = disp.dispatch([blocker], "{}", tmp_path, INPROC_BUDGET)
        assert calls, "run_inprocess 未被呼叫：改走尾段，退回路徑沒被行使"
        assert results[0].code == 2 and results[0].stderr == "sub"

    def test_registry_unreadable_is_fail_open_but_visible(self, tmp_path):
        env = dict(os.environ)
        p = subprocess.run([sys.executable, str(HOOKS_DIR / "hook-dispatcher.py"), "--group", "NoSuch:Group"],
                           input="{}", capture_output=True, text=True, env=env, cwd=str(PROJECT_ROOT))
        assert p.returncode == 1
        assert "分派失敗" in p.stderr


# ---------- registry 與 settings.json ----------

class TestRegistry:
    def _reg(self):
        return json.loads((HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))["groups"]

    def test_every_registered_hook_exists(self):
        for group in self._reg().values():
            for e in group["hooks"]:
                assert (PROJECT_ROOT / e["path"]).is_file(), e["path"]

    def test_no_duplicate_entries_per_group(self):
        for group in self._reg().values():
            paths = [e["path"] for e in group["hooks"]]
            assert len(paths) == len(set(paths))

    def test_guards_not_dropped(self):
        pre = [e["path"] for e in self._reg()["PreToolUse:Bash"]["hooks"]]
        for must in ("pre-test-hook.py", "workspace-wipe-guard-hook.py", "bare-commit-guard-hook.py",
                     "bash-git-protected-branch-guard-hook.py", "skill-sync-push-residue-gate-hook.py"):
            assert any(p.endswith("/" + must) for p in pre), must

    def test_settings_has_single_dispatcher_entry_per_bash_matcher(self):
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        for event, group in (("PreToolUse", "PreToolUse:Bash"), ("PostToolUse", "PostToolUse:Bash")):
            bash = [g for g in hooks[event] if g.get("matcher") == "Bash"]
            assert len(bash) == 1
            assert len(bash[0]["hooks"]) == 1
            assert bash[0]["hooks"][0]["command"].endswith("hook-dispatcher.py --group " + group)

    def test_settings_timeout_covers_group_budget(self):
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        for event, group in (("PreToolUse", "PreToolUse:Bash"), ("PostToolUse", "PostToolUse:Bash")):
            bash = [g for g in hooks[event] if g.get("matcher") == "Bash"][0]
            assert bash["hooks"][0]["timeout"] > self._reg()[group]["budget"]

    def test_pre_test_hook_keeps_mcp_registration(self):
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        mcp = [g for g in hooks["PreToolUse"] if g.get("matcher") == "mcp__dart__run_tests"]
        assert any("pre-test-hook.py" in h["command"] for g in mcp for h in g["hooks"])


# ---------- 正向對照：已知應被攔下的輸入 ----------

class TestKnownBlockedInputStillBlocked:
    UNWRAPPED = "pytest tests/"
    WRAPPED = "python3 .claude/scripts/run-with-timeout.py 600 -- pytest tests/"

    def _payload(self, command):
        return json.dumps({"session_id": "disp-test", "cwd": str(PROJECT_ROOT),
                           "hook_event_name": "PreToolUse", "tool_name": "Bash",
                           "tool_input": {"command": command}})

    def _standalone(self, command):
        p = subprocess.run([sys.executable, str(HOOKS_DIR / "pre-test-hook.py")], input=self._payload(command),
                           capture_output=True, text=True, cwd=str(PROJECT_ROOT),
                           env=dict(os.environ))
        return json.loads(p.stdout)["hookSpecificOutput"]

    def test_unwrapped_full_pytest_denied_via_dispatcher_with_original_reason(self):
        want = self._standalone(self.UNWRAPPED)
        assert want["permissionDecision"] == "deny"
        p = subprocess.run([sys.executable, str(HOOKS_DIR / "hook-dispatcher.py"), "--group", "PreToolUse:Bash"],
                           input=self._payload(self.UNWRAPPED), capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), env=dict(os.environ))
        got = json.loads(p.stdout)["hookSpecificOutput"]
        assert got["permissionDecision"] == "deny"
        assert got["permissionDecisionReason"] == want["permissionDecisionReason"]

    def test_wrapped_command_not_denied_via_dispatcher(self):
        p = subprocess.run([sys.executable, str(HOOKS_DIR / "hook-dispatcher.py"), "--group", "PreToolUse:Bash"],
                           input=self._payload(self.WRAPPED), capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), env=dict(os.environ))
        if p.stdout.strip():
            assert json.loads(p.stdout)["hookSpecificOutput"].get("permissionDecision") != "deny"
        assert p.returncode != 2
