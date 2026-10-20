"""
合併前全套件閘門測試

套件執行器一律注入假的，不真的跑 hooks 或 flutter 全套件。快照建立與移除用 tmp repo 實測；
名額序列化用 tmp 目錄內的小型 pytest 實測。
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude"))

import merge_gate as mg  # noqa: E402
import worktree_manager as wm  # noqa: E402
import merge_cas as mc  # noqa: E402
from lib.test_command_parse import WEIGHT_HEAVY, classify_argv_weight  # noqa: E402

TICKET_FILE = "docs/work-logs/v0/v0.5/v0.5.0/tickets/9.9.9-W1-001.md"


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


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    commit_file(r, "lib/marker.txt", "clean\n", "base marker")
    commit_file(r, "lib/other.txt", "o\n", "base other")
    commit_file(r, TICKET_FILE, "t0\n", "base ticket")
    git(r, "checkout", "-b", "feat")
    commit_file(r, "lib/other.txt", "o-feat\n", "feat edit")
    git(r, "checkout", "main")
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))  # 合併持有名額時不碰真實 ~/.cache
    monkeypatch.chdir(r)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(r))
    monkeypatch.setattr(wm, "get_worktree_list", lambda: [])
    return r


def snapshots(repo):
    return [ln for ln in git(repo, "worktree", "list").splitlines() if mg.SNAPSHOT_PREFIX in ln]


def make_artifact(cwd):
    art = Path(cwd) / ".dart_tool" / "package_config.json"
    art.parent.mkdir(exist_ok=True)
    art.write_text("{}")


def art(run):
    """為假執行器補上生成產物步驟（pub get 時建立檔案並回 0），其餘交給 run。"""
    def wrapped(argv, cwd):
        if "pub" in argv:
            make_artifact(cwd)
            return 0, ""
        return run(argv, cwd)
    return wrapped


def green_runner(calls):
    def run(argv, cwd):
        calls.append((argv, cwd))
        if "pub" in argv:
            make_artifact(cwd)
        return 0, "ok"
    return run


class TestRedGreen:
    def test_red_does_not_merge_and_lists_failures(self, repo):
        old = git(repo, "rev-parse", "main")
        seen = {}

        def red(argv, cwd):
            seen["main_during_check"] = git(repo, "rev-parse", "main")
            return 1, "collected\nFAILED tests/test_x.py::test_boom - assert 1 == 2\n"

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), art(red)))
        assert not out.ok
        assert "FAILED tests/test_x.py::test_boom" in out.error
        assert git(repo, "rev-parse", "main") == old
        assert seen["main_during_check"] == old  # 檢查時 update-ref 尚未發生
        assert snapshots(repo) == []

    def test_green_merges(self, repo):
        calls = []
        old = git(repo, "rev-parse", "main")
        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), green_runner(calls)))
        assert out.ok and git(repo, "rev-parse", "main") == out.commit_sha != old
        assert len([c for c in calls if "pub" not in c[0]]) == 1

    def test_cmd_merge_red_returns_nonzero(self, repo, capsys):
        old = git(repo, "rev-parse", "main")
        rc = wm.cmd_merge(None, branch="feat", gate_runner=art(lambda a, c: (1, "FAILED t::x\n")))
        assert rc == 1
        assert "FAILED t::x" in capsys.readouterr().out
        assert git(repo, "rev-parse", "main") == old

    def test_cmd_merge_green_returns_zero(self, repo):
        assert wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([]))) == 0


class TestHeavySlot:
    def test_suite_commands_are_wrapped_and_heavy(self):
        for suite, cmd in mg.SUITE_COMMANDS.items():
            argv = mg.wrapped_argv(cmd)
            assert argv[1].endswith("run-with-timeout.py"), suite
            assert argv[argv.index("--") + 1:] == cmd
            assert classify_argv_weight(cmd) == WEIGHT_HEAVY, suite

    def test_runner_receives_wrapped_argv(self, repo):
        calls = []
        wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), green_runner(calls)))
        argv = calls[-1][0]
        assert argv[1].endswith("run-with-timeout.py") and "--" in argv

    def test_two_concurrent_runs_are_serialized(self, tmp_path, monkeypatch):
        slots = tmp_path / "slots"
        slots.mkdir(mode=0o700)
        monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
        stamps = {}

        def make_dir(name):
            d = tmp_path / name
            d.mkdir()
            (d / "test_stamp.py").write_text(
                "import time, pathlib\n"
                "def test_stamp():\n"
                f"    pathlib.Path(r'{d}/start').write_text(str(time.time()))\n"
                "    time.sleep(1.0)\n"
                f"    pathlib.Path(r'{d}/end').write_text(str(time.time()))\n"
            )
            return d

        def run(d):
            argv = mg.wrapped_argv([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], 120)
            stamps[d.name] = mg.default_runner(argv, str(d))[0]

        dirs = [make_dir("a"), make_dir("b")]
        threads = [threading.Thread(target=run, args=(d,)) for d in dirs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert stamps == {"a": 0, "b": 0}
        spans = sorted((float((d / "start").read_text()), float((d / "end").read_text())) for d in dirs)
        assert spans[1][0] >= spans[0][1]  # 第二份在第一份結束後才開始


def _touch(root, rel, text=""):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


@pytest.fixture
def skel(tmp_path):
    """模擬合併快照：三種 skill 型態 + 無 tests 的 skill。"""
    r = tmp_path / "snap"
    for name, pyproject, imports_lib in (("withpy", True, True), ("nopy", False, True), ("lone", True, False)):
        _touch(r, f".claude/skills/{name}/tests/test_a.py")
        _touch(r, f".claude/skills/{name}/mod.py", "from lib import x\n" if imports_lib else "import os\n")
        if pyproject:
            _touch(r, f".claude/skills/{name}/pyproject.toml")
    _touch(r, ".claude/skills/docsonly/SKILL.md")
    return str(r)


class TestScope:
    def test_flutter_scope(self, skel):
        assert mg.select_suites(["lib/main.dart"], skel) == [mg.SUITE_FLUTTER]

    def test_assets_only_runs_flutter(self, skel):
        """E2 正向對照：只改 assets 下檔案（內嵌副本）必跑 flutter。"""
        paths = ["assets/schema/tracking_schema.json"]
        assert mg.needs_gate(paths)
        assert mg.select_suites(paths, skel) == [mg.SUITE_FLUTTER]

    def test_ticket_only_still_exempt(self, skel):
        assert not mg.needs_gate([TICKET_FILE])
        assert mg.select_suites([TICKET_FILE], skel) == []

    def test_hooks_and_other_claude_paths_run_hooks(self, skel):
        for p in (".claude/hooks/x.py", ".claude/rules/core/a.md", ".claude/settings.json",
                  ".claude/skills/docsonly/SKILL.md"):
            assert mg.select_suites([p], skel) == [mg.SUITE_HOOKS], p

    def test_skill_runs_its_own_tests_not_hooks(self, skel):
        """E2：只改 skill 不會只跑 hooks。"""
        assert mg.select_suites([".claude/skills/withpy/mod.py"], skel) == ["skill:withpy"]
        assert mg.select_suites([".claude/skills/nopy/tests/test_a.py"], skel) == ["skill:nopy"]

    def test_scripts_scope(self, skel):
        assert mg.select_suites([".claude/scripts/run-with-timeout.py"], skel) == [mg.SUITE_SCRIPTS]

    def test_lib_runs_hooks_scripts_and_importing_skills(self, skel):
        assert mg.select_suites([".claude/lib/x.py"], skel) == [
            mg.SUITE_HOOKS, mg.SUITE_SCRIPTS, "skill:nopy", "skill:withpy"]  # lone 不匯入 lib，不在內

    def test_multiple_scopes_ordered_and_none(self, skel):
        got = mg.select_suites(["lib/a.dart", ".claude/hooks/b.py", ".claude/scripts/c.py",
                                ".claude/skills/lone/mod.py"], skel)
        assert got == [mg.SUITE_FLUTTER, mg.SUITE_HOOKS, mg.SUITE_SCRIPTS, "skill:lone"]
        assert mg.select_suites([TICKET_FILE, "README.md"], skel) == []
        assert not mg.needs_gate([TICKET_FILE, "README.md"])

    def test_new_skill_is_picked_up_without_list_edit(self, skel):
        _touch(Path(skel), ".claude/skills/brandnew/tests/test_a.py")
        assert mg.select_suites([".claude/skills/brandnew/x.py"], skel) == ["skill:brandnew"]

    def test_skill_imported_by_hooks_also_runs_hooks(self, skel):
        """E2：改被 hooks 匯入的 skill（含 sys.path.insert 之後的匯入），加跑 hooks。"""
        _touch(Path(skel), ".claude/skills/withpy/withpy_system/__init__.py")
        _touch(Path(skel), ".claude/hooks/h.py",
               "import sys\nsys.path.insert(0, 'x')\nif True:\n    from withpy_system.lib import y\n")
        assert mg.select_suites([".claude/skills/withpy/mod.py"], skel) == [mg.SUITE_HOOKS, "skill:withpy"]

    def test_skill_imported_by_scripts_also_runs_scripts(self, skel):
        _touch(Path(skel), ".claude/scripts/s.py", "import mod\n")  # mod 是 withpy 根下的模組
        assert mg.select_suites([".claude/skills/withpy/mod.py"], skel) == [mg.SUITE_SCRIPTS, "skill:withpy"]

    def test_unimported_skill_runs_only_own_suite(self, skel):
        """對照：沒被 hooks／scripts 匯入或引用的 skill 不加跑。"""
        _touch(Path(skel), ".claude/hooks/h.py", "import os\nfrom lib import z\n")
        assert mg.select_suites([".claude/skills/lone/mod.py"], skel) == ["skill:lone"]

    def test_path_reference_counts_only_in_non_test_files(self, skel):
        _touch(Path(skel), ".claude/hooks/tests/test_h.py", "p = '.claude/skills/lone/x.json'\n")
        assert mg.select_suites([".claude/skills/lone/mod.py"], skel) == ["skill:lone"]
        _touch(Path(skel), ".claude/hooks/g.py", "p = '.claude/skills/lone/x.json'\n")
        assert mg.select_suites([".claude/skills/lone/mod.py"], skel) == [mg.SUITE_HOOKS, "skill:lone"]

    def test_suite_commands(self, skel):
        assert mg.suite_command("skill:withpy", skel) == ["uv", "--directory", ".claude/skills/withpy", "run", "pytest"]
        nopy = mg.suite_command("skill:nopy", skel)
        assert nopy[:5] == ["uv", "--directory", ".claude/hooks", "run", "pytest"] and nopy[-1] == "../skills/nopy/tests"
        assert mg.suite_command(mg.SUITE_SCRIPTS, skel)[2] == ".claude/scripts"
        for suite in ("skill:withpy", "skill:nopy", mg.SUITE_SCRIPTS):
            assert classify_argv_weight(mg.suite_command(suite, skel)) == WEIGHT_HEAVY, suite

    def test_gate_runs_skill_suite_only_for_skill_change(self, repo):
        git(repo, "checkout", "-q", "feat")
        commit_file(repo, ".claude/skills/foo/tests/test_a.py", "", "foo tests")
        commit_file(repo, ".claude/skills/foo/mod.py", "x = 1\n", "foo mod")
        git(repo, "checkout", "-q", "main")
        calls = []
        gate = mg.MergeGate(str(repo), art(green_runner(calls)))
        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate)
        assert out.ok
        cmds = [" ".join(argv[argv.index("--") + 1:]) for argv, _ in calls]
        assert any("--directory .claude/hooks" in c and "../skills/foo/tests" in c for c in cmds)
        assert not any(c.endswith(".claude/hooks run pytest") for c in cmds)  # 不只跑 hooks 全套

    def test_skill_documents_scope_rule(self):
        text = (Path(__file__).parent.parent / "SKILL.md").read_text(encoding="utf-8")
        assert "合併前全套件" in text and "flutter test" in text and "hooks pytest" in text
        assert "skill:" in text and ".claude/scripts" in text and ".claude/lib" in text

    def test_scope_selects_runner_commands(self, repo):
        calls = []
        wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), green_runner(calls)))
        flat = [a for argv, _ in calls for a in argv]
        assert "flutter" in flat and "pytest" not in flat  # 只改 lib/，不跑 hooks


class TestSnapshot:
    def test_result_not_affected_by_dirty_main_checkout(self, repo):
        (repo / "lib" / "marker.txt").write_text("dirty\n")  # 主 checkout 未提交修改
        seen = {}

        def run(argv, cwd):
            seen["cwd"] = cwd
            return (0, "") if (Path(cwd) / "lib/marker.txt").read_text() == "clean\n" else (1, "dirty tree")

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), art(run)))
        assert out.ok, out.error
        assert seen["cwd"] != str(repo) and mg.SNAPSHOT_PREFIX in seen["cwd"]

    @pytest.mark.parametrize("path", ["green", "red", "timeout", "interrupt"])
    def test_snapshot_removed_on_every_exit_path(self, repo, path):
        during = {}

        def run(argv, cwd):
            during["n"] = len(snapshots(repo))
            if path == "interrupt":
                raise KeyboardInterrupt
            return {"green": (0, ""), "red": (1, "x"), "timeout": (124, "")}[path]

        gate = mg.MergeGate(str(repo), art(run))
        if path == "interrupt":
            with pytest.raises(KeyboardInterrupt):
                wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate)
        else:
            out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate)
            assert out.ok == (path == "green")
            if path == "timeout":
                assert "逾時" in out.error
        assert during["n"] == 1  # 執行期間快照存在
        assert snapshots(repo) == []
        assert not list((repo / mg.SNAPSHOT_DIR).glob(mg.SNAPSHOT_PREFIX + "*"))


class TestArtifacts:
    def test_missing_artifact_generated_before_suite(self, repo):
        order = []

        def run(argv, cwd):
            if "pub" in argv:
                order.append("gen")
                art = Path(cwd) / ".dart_tool" / "package_config.json"
                art.parent.mkdir(exist_ok=True)
                art.write_text("{}")
            else:
                order.append("suite")
                assert (Path(cwd) / ".dart_tool/package_config.json").exists()
            return 0, ""

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), run))
        assert out.ok and order == ["gen", "suite"]

    def test_generation_failure_names_missing_artifact(self, repo):
        calls = []

        def run(argv, cwd):
            calls.append(argv)
            return 1, "pub get failed"

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), run))
        assert not out.ok and ".dart_tool/package_config.json" in out.error
        assert len(calls) == 1  # 套件本體未執行


def advance_main(repo, name, text):
    """模擬並行 session 推進 main。"""
    commit_file(repo, name, text, f"advance {name}")


class TestUnmappedWarning:
    def _run(self, repo, monkeypatch, capsys, paths):
        monkeypatch.setattr(mg, "changed_paths_between", lambda *_a: paths)
        head = git(repo, "rev-parse", "HEAD")
        res = mg.MergeGate(str(repo), art(lambda argv, cwd: (0, "")))(head, "main", head, 1)
        assert res.passed
        return capsys.readouterr().out

    def test_all_exempt_lists_unmapped_paths(self, repo, monkeypatch, capsys):
        out = self._run(repo, monkeypatch, capsys, ["tools/sub/a.py", "README.md"])
        assert "WARNING" in out and "tools/sub/a.py" in out and "README.md" in out and "免跑" in out

    def test_partial_lists_unmapped_paths(self, repo, monkeypatch, capsys):
        out = self._run(repo, monkeypatch, capsys, ["lib/a.dart", "tools/sub/a.py"])
        assert "WARNING" in out and "tools/sub/a.py" in out and "lib/a.dart" not in out

    def test_exempt_only_has_no_warning(self, repo, monkeypatch, capsys):
        out = self._run(repo, monkeypatch, capsys, [TICKET_FILE, "docs/work-logs/topic-assignments.txt"])
        assert "WARNING" not in out and "免跑" in out

    def test_truncates_with_total(self, repo, monkeypatch, capsys):
        paths = [f"tools/f{i}.py" for i in range(mg.UNMAPPED_SHOW_MAX + 3)]
        out = self._run(repo, monkeypatch, capsys, paths)
        assert f"{len(paths)} 個" in out and "其餘 3 個略" in out and paths[-1] not in out


class TestRetryReuse:
    def _merge_with_advance(self, repo, advance_path):
        state = {"n": 0}

        def run(argv, cwd):
            state["n"] += 1
            if state["n"] == 1:
                advance_main(repo, advance_path, "new\n")
            return 0, ""

        gate = mg.MergeGate(str(repo), art(run))
        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate, max_retries=mg.GATE_MAX_RETRIES)
        return out, gate

    def test_exempt_only_difference_reuses_result(self, repo):
        out, gate = self._merge_with_advance(repo, TICKET_FILE)
        assert out.ok and out.attempts == 2
        assert gate.suite_runs == 1

    def test_non_exempt_difference_reruns_suite(self, repo):
        out, gate = self._merge_with_advance(repo, "lib/new.txt")
        assert out.ok and out.attempts == 2
        assert gate.suite_runs == 2


    def test_ticket_plus_topic_assignments_reuses_result(self, repo):
        state = {"n": 0}

        def run(argv, cwd):
            state["n"] += 1
            if state["n"] == 1:
                advance_main(repo, TICKET_FILE, "t1\n")
                advance_main(repo, "docs/work-logs/topic-assignments.txt", "line\n")
            return 0, ""

        gate = mg.MergeGate(str(repo), art(run))
        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=gate, max_retries=mg.GATE_MAX_RETRIES)
        assert out.ok and out.attempts == 2 and gate.suite_runs == 1


class TestPerSuiteReuse:
    """CAS 重試依套件範圍沿用：只重跑差異觸及的套件。"""

    @staticmethod
    def _suite_of(argv):
        if "flutter" in argv:
            return mg.SUITE_FLUTTER
        joined = " ".join(argv)
        if "../skills/foo/tests" in joined:
            return "skill:foo"
        return mg.SUITE_HOOKS if ".claude/hooks" in joined else "other"

    def _multi_branch(self, repo):
        git(repo, "checkout", "-b", "multi")
        commit_file(repo, "lib/m.txt", "m\n", "multi lib")
        commit_file(repo, ".claude/hooks/h.py", "x = 1\n", "multi hook")
        commit_file(repo, ".claude/skills/foo/tests/test_a.py", "# t\n", "multi skill tests")
        commit_file(repo, ".claude/skills/foo/a.py", "y = 1\n", "multi skill src")
        git(repo, "checkout", "main")

    def _merge(self, repo, advance_path, text="new\n"):
        self._multi_branch(repo)
        ran, state = [], {"n": 0}

        def run(argv, cwd):
            suite = self._suite_of(argv)
            ran.append(suite)
            state["n"] += 1
            if state["n"] == 1:
                advance_main(repo, advance_path, text)
            return 0, "1 passed in 0.1s"

        gate = mg.MergeGate(str(repo), art(run))
        out = wm.merge_branch_cas("multi", repo=str(repo), pre_merge_check=gate, max_retries=mg.GATE_MAX_RETRIES)
        return out, ran

    def test_skill_only_difference_reruns_only_that_skill(self, repo, capsys):
        out, ran = self._merge(repo, ".claude/skills/foo/b.py")
        assert out.ok and out.attempts == 2
        assert ran[:3] == [mg.SUITE_FLUTTER, mg.SUITE_HOOKS, "skill:foo"]
        assert ran[3:] == ["skill:foo"]  # 第二輪只重跑受影響套件
        text = capsys.readouterr().out
        assert "套件 flutter：沿用" in text and "套件 hooks：沿用" in text

    def test_hooks_difference_reruns_hooks_only(self, repo):
        out, ran = self._merge(repo, ".claude/hooks/new_hook.py")
        assert out.ok and out.attempts == 2
        assert ran[3:] == [mg.SUITE_HOOKS]

    def test_suite_outside_first_set_is_added(self, repo):
        # main 新增匯入該 skill 模組的 scripts 檔：套件集合因匯入掃描而變大，新套件加跑、其餘沿用
        out, ran = self._merge(repo, ".claude/scripts/new_tool.py", "import a\n")
        assert out.ok and out.attempts == 2
        assert ran[3:] == ["other"]

    def test_reused_state_carries_to_next_retry(self, repo):
        self._multi_branch(repo)
        ran, state = [], {"n": 0}

        def run(argv, cwd):
            ran.append(self._suite_of(argv))
            state["n"] += 1
            if state["n"] == 1:
                advance_main(repo, ".claude/skills/foo/b.py", "1\n")
            if state["n"] == 4:  # 第二輪重跑 skill:foo 期間再推進 main 一次，與 skill 無關
                advance_main(repo, "lib/z.txt", "z\n")
            return 0, ""

        gate = mg.MergeGate(str(repo), art(run))
        out = wm.merge_branch_cas("multi", repo=str(repo), pre_merge_check=gate, max_retries=mg.GATE_MAX_RETRIES)
        assert out.ok and out.attempts == 3
        assert ran[3:] == ["skill:foo", mg.SUITE_FLUTTER]  # hooks 沿用兩輪、skill:foo 於第二輪已驗


class TestResultLine:
    def _log(self, repo):
        return (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")

    def test_green_line_has_suite_summary_and_duration(self, repo, capsys):
        wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), art(lambda a, c: (0, "...\n==== 5748 passed, 3 skipped in 424.01s ====\n"))))
        lines = [ln for ln in capsys.readouterr().out.splitlines() if "套件 flutter" in ln]
        print(lines[0])  # 供回報取用的實際輸出範例
        assert len(lines) == 1
        assert "綠燈" in lines[0] and "5748 passed, 3 skipped in 424.01s" in lines[0] and "耗時" in lines[0]
        assert lines[0] in self._log(repo)

    def test_flutter_summary(self):
        assert mg.summarize_output("00:41 +812: All tests passed!\n") == "00:41 +812: All tests passed!"
        assert mg.summarize_output("nothing useful") == "無摘要"

    @pytest.mark.parametrize("rc,status", [(1, "紅燈"), (124, "逾時")])
    def test_red_and_timeout_also_logged_with_duration(self, repo, rc, status):
        wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), art(lambda a, c: (rc, "1 failed, 2 passed in 3.00s\n"))))
        line = [ln for ln in self._log(repo).splitlines() if "套件 flutter" in ln][0]
        assert status in line and "耗時" in line

    def test_interrupt_logged(self, repo):
        def run(argv, cwd):
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), art(run)))
        assert "中斷" in self._log(repo)


class TestRetryCap:
    def test_cap_aborts_with_last_failure_and_keeps_branch(self, repo, capsys):
        calls = {"n": 0}

        def run(argv, cwd):
            calls["n"] += 1
            advance_main(repo, f"lib/adv{calls['n']}.txt", "x\n")  # 每次都使 CAS 失敗
            return 0, ""

        rc = wm.cmd_merge(None, branch="feat", gate_runner=art(run))
        out = capsys.readouterr().out
        assert rc == 1
        assert "expected" in out  # 回報最後一次失敗原因（CAS 預算與閘門上限擇先中止）
        assert calls["n"] == mg.GATE_MAX_RETRIES + 1
        merged = subprocess.run(["git", "merge-base", "--is-ancestor", "feat", "main"], cwd=repo).returncode
        assert merged != 0  # main 未含分支（ref 未被寫成合併 commit）
        assert git(repo, "rev-parse", "--verify", "refs/heads/feat")


    def test_explicit_cap_message_names_limit_and_last_error(self, repo):
        calls = {"n": 0}

        def run(argv, cwd):
            calls["n"] += 1
            advance_main(repo, f"lib/adv{calls['n']}.txt", "x\n")
            return 0, ""

        old_branch = git(repo, "rev-parse", "feat")
        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=mg.MergeGate(str(repo), art(run)),
                                  max_retries=1)
        assert not out.ok and "上限 1" in out.error and "expected" in out.error
        assert calls["n"] == 2
        assert git(repo, "rev-parse", "feat") == old_branch


class TestBypassFlag:
    def test_skip_gate_logs_reason_and_skips_runner(self, repo, capsys):
        called = []
        rc = wm.cmd_merge(None, branch="feat", skip_gate_reason="緊急修復", gate_runner=green_runner(called))
        assert rc == 0 and called == []
        log = (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")
        assert "略過合併前測試" in log and "緊急修復" in log

    def test_skip_gate_without_reason_rejected(self, repo):
        old = git(repo, "rev-parse", "main")
        assert wm.cmd_merge(None, branch="feat", skip_gate_reason="  ") == 1
        assert git(repo, "rev-parse", "main") == old


class TestExemptList:
    def test_patterns(self):
        assert mg.is_reuse_exempt(TICKET_FILE)
        assert mg.is_reuse_exempt("docs/work-logs/v0/v0.5/v0.5.0-main.md")
        assert mg.is_reuse_exempt("docs/work-logs/topic-assignments.txt")
        assert not mg.is_reuse_exempt("docs/work-logs/v0/topic-assignments.txt")
        assert not mg.is_reuse_exempt("docs/spec/ui/domain-map.md")

    def test_list_is_exactly_three_entries(self):
        assert mg.RETRY_REUSE_EXEMPT_GLOBS == (
            "docs/work-logs/**/tickets/*.md",
            "docs/work-logs/**/v*-main.md",
            "docs/work-logs/topic-assignments.txt",
        )

    def test_guard_flags_test_reading_real_exempt_file(self, tmp_path):
        """E2 正向對照：讀取清單內實際檔案的樣本須為紅。"""
        (tmp_path / "docs/work-logs/v1/tickets").mkdir(parents=True)
        (tmp_path / "docs/work-logs/v1/tickets/1.0.0-W1-001.md").write_text("x")
        (tmp_path / "test").mkdir()
        (tmp_path / "test/a_test.dart").write_text(
            "File('docs/work-logs/v1/tickets/1.0.0-W1-001.md').readAsStringSync();\n")
        (tmp_path / "test/b_test.dart").write_text(
            "expect(p, 'docs/work-logs/v1/tickets/not-there.md');\n")
        hits = mg.find_exempt_file_reads(tmp_path)
        assert hits == [("test/a_test.dart", "docs/work-logs/v1/tickets/1.0.0-W1-001.md")]

    def test_no_test_reads_exempt_files(self):
        assert mg.find_exempt_file_reads(ROOT) == []


# ===== 名額先於合併 commit 取得、持有至 update-ref（0.5.0-W1-231.8）=====


def slot_free():
    """名額目前是否可取得（取得後立即釋放）。"""
    import os
    from lib import slot_gate
    got = slot_gate._try_acquire(slot_gate.slot_dir())
    if got is None:
        return False
    os.close(got[0])
    return True


class Events:
    """帶單調時間戳的事件序列；測試以序列順序與時間戳斷言先後。"""

    def __init__(self):
        self.items = []
        self.lock = threading.Lock()

    def add(self, name):
        with self.lock:
            self.items.append((name, time.monotonic()))

    def names(self):
        return [n for n, _ in self.items]

    def at(self, name):
        return next(t for n, t in self.items if n == name)


def instrument(monkeypatch, ev):
    """記錄 commit-tree（_prepare_candidate 成功返回）與 update-ref 完成；事件名不分執行緒。"""
    real_prepare, real_raw = mc._prepare_candidate, mc._git_raw

    def prepare(branch, base, repo, message):
        out = real_prepare(branch, base, repo, message)
        if out[0] is not None:
            ev.add("commit")
        return out

    def raw(args, repo, *a, **k):
        proc = real_raw(args, repo, *a, **k)
        if args and args[0] == "update-ref":
            ev.add("update-ref")
        return proc

    monkeypatch.setattr(mc, "_prepare_candidate", prepare)
    monkeypatch.setattr(mc, "_git_raw", raw)


def gated_merge(repo, branch, runner, ev, tag="", **kw):
    gate = mg.MergeGate(str(repo), art(runner), on_event=lambda n: ev.add(f"{tag}{n}"))
    out = wm.merge_branch_cas(branch, repo=str(repo), pre_merge_check=gate,
                              hold=gate.hold(branch, "main"), **kw)
    return out, gate


class TestSlotBeforeCommit:
    def test_slot_taken_before_commit_and_released_after_update_ref(self, repo, monkeypatch):
        ev = Events()
        instrument(monkeypatch, ev)
        seen = {}

        def run(argv, cwd):
            seen["free_during_suite"] = slot_free()
            return 0, ""

        out, _ = gated_merge(repo, "feat", run, ev)
        assert out.ok
        names = ev.names()
        assert names.index("slot_acquired") < names.index("commit") < names.index("update-ref") \
            < names.index("slot_released")
        assert ev.at("slot_acquired") <= ev.at("commit") <= ev.at("update-ref") <= ev.at("slot_released")
        assert seen["free_during_suite"] is False  # E1 對照：持有期間名額確實被占
        assert slot_free()

    def test_doc_only_change_does_not_take_slot(self, repo):
        git(repo, "checkout", "-q", "-b", "docs-only")
        commit_file(repo, "notes/readme.txt", "n\n", "notes")
        git(repo, "checkout", "-q", "main")
        ev = Events()
        out, _ = gated_merge(repo, "docs-only", lambda a, c: (0, ""), ev)
        assert out.ok and "slot_acquired" not in ev.names()


class TestNoSelfDeadlock:
    def _argv(self, tmp_path):
        d = tmp_path / "suite"
        d.mkdir()
        (d / "test_ok.py").write_text("def test_ok():\n    assert True\n")
        argv = mg.wrapped_argv([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], 60)
        return argv, str(d)

    def test_suite_completes_while_holding_slot(self, repo, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "3")
        argv, cwd = self._argv(tmp_path)
        gate = mg.MergeGate(str(repo))
        with gate.hold("feat", "main"):
            rc, out = mg.default_runner(argv, cwd)
        assert rc == 0, out

    def test_control_without_hold_marker_is_blocked_by_holder(self, repo, tmp_path, monkeypatch):
        """E1 對照：同樣被占用、但不帶持有標記的套件命令會等名額逾時，證明上一條通過來自標記。"""
        monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "2")
        argv, cwd = self._argv(tmp_path)
        from lib import slot_gate
        hold, _ = slot_gate.acquire_slot(["x"], lambda: None, estimate_seconds=0)  # 預估 0：超過上限即視為卡住
        try:
            rc, _out = mg.default_runner(argv, cwd)
        finally:
            hold.release()
        assert rc == 125

    def test_wrapper_script_comes_from_same_tree_as_gate(self):
        """持有者與子程序必須載入同一份 slot_gate：腳本取自 merge_gate.py 所在的樹，不取主 checkout。"""
        expected = Path(mg.__file__).resolve().parents[3] / "scripts" / "run-with-timeout.py"
        assert Path(mg.wrapped_argv(["true"])[1]) == expected

    def test_child_that_ignores_marker_fails_fast(self, repo, tmp_path, monkeypatch):
        """E2：子程序的 slot_gate 不認得持有標記（版本不一致）時，等待上限須遠短於預設，不可占住名額。"""
        from lib import slot_gate
        stub = tmp_path / "old_run_with_timeout.py"
        stub.write_text(
            "import sys\n"
            f"sys.path.insert(0, r'{ROOT / '.claude'}')\n"
            "from lib import slot_gate\n"
            "hold, early = slot_gate.acquire_slot(['x'], lambda: None)  # 舊版：不處理持有標記\n"
            "sys.exit(early or 0)\n"
        )
        monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "20")  # 模擬預設的長上限
        monkeypatch.setattr(slot_gate, "HELD_CHILD_WAIT_LIMIT_SECONDS", 2, raising=False)
        with mg.MergeGate(str(repo)).hold("feat", "main"):
            start = time.monotonic()
            rc, _ = mg.default_runner([sys.executable, str(stub)], str(tmp_path))
            elapsed = time.monotonic() - start
        assert rc == 125 and elapsed < 10
        assert slot_free()

    def test_holder_wait_notice_names_its_own_source(self, repo, monkeypatch, capsys):
        from lib import slot_gate
        monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "1")
        other, _ = slot_gate.acquire_slot(["other"], lambda: None, estimate_seconds=0)
        try:
            with pytest.raises(RuntimeError):
                with mg.MergeGate(str(repo)).hold("feat", "main"):
                    pass
        finally:
            other.release()
        err = capsys.readouterr().err
        assert "merge-gate:" in err and "run-with-timeout:" not in err

    def test_marker_cleared_after_hold(self, repo):
        import os
        from lib import slot_gate
        with mg.MergeGate(str(repo)).hold("feat", "main"):
            assert slot_gate.HELD_ENV in os.environ
        assert slot_gate.HELD_ENV not in os.environ

    def test_stale_marker_does_not_bypass_gate(self, repo, monkeypatch):
        import os
        from lib import slot_gate
        monkeypatch.setenv(slot_gate.HELD_ENV, str(os.getpid()))  # 名額實際未被占用
        assert slot_gate.held_by_ancestor() is False
        monkeypatch.setenv(slot_gate.HELD_ENV, "999999999")
        assert slot_gate.held_by_ancestor() is False


class TestSerializedMerges:
    def test_second_commit_after_first_update_ref(self, repo, monkeypatch):
        from lib import slot_gate
        # 同進程兩執行緒共用 os.environ：A 持有期間環境上限被降為子程序用的值，B 會讀到；
        # 預估耗時因此超過上限而被拒絕。真實情境 B 是另一進程，不受此影響。
        monkeypatch.setattr(slot_gate, "HELD_CHILD_WAIT_LIMIT_SECONDS", slot_gate.SLOT_WAIT_LIMIT_SECONDS)
        git(repo, "checkout", "-q", "-b", "feat2", "main")
        commit_file(repo, "lib/second.txt", "s\n", "feat2 edit")
        git(repo, "checkout", "-q", "main")
        ev = Events()
        instrument(monkeypatch, ev)
        a_started = threading.Event()
        results = {}

        def run_a(argv, cwd):
            a_started.set()
            time.sleep(1.0)
            return 0, ""

        def go(name, branch, runner):
            results[name] = gated_merge(repo, branch, runner, ev, tag=name + ":",
                                        max_retries=mg.GATE_MAX_RETRIES)

        ta = threading.Thread(target=go, args=("a", "feat", run_a))
        ta.start()
        assert a_started.wait(30)
        tb = threading.Thread(target=go, args=("b", "feat2", lambda a, c: (0, "")))
        tb.start()
        time.sleep(0.3)
        assert "b:slot_acquired" not in ev.names()  # B 在 A 持有期間排隊中
        ta.join(60)
        tb.join(60)
        assert results["a"][0].ok and results["b"][0].ok
        assert ev.at("a:slot_released") <= ev.at("b:slot_acquired")
        a_ref = [t for n, t in ev.items if n == "update-ref"]  # instrument 無標籤；以時間序判斷
        assert len(a_ref) == 2 and a_ref[0] <= ev.at("b:slot_acquired")

    def test_retry_under_hold_reuses_when_only_exempt_differs(self, repo):
        state = {"n": 0}

        def run(argv, cwd):
            state["n"] += 1
            if state["n"] == 1:
                advance_main(repo, TICKET_FILE, "t-new\n")
            return 0, ""

        ev = Events()
        out, gate = gated_merge(repo, "feat", run, ev, max_retries=mg.GATE_MAX_RETRIES)
        assert out.ok and out.attempts == 2 and gate.suite_runs == 1
        assert ev.names().count("slot_acquired") == 1  # 重試不重新排隊


class TestReleaseOnEveryExit:
    @pytest.mark.parametrize("rc", [1, 124, 125])
    def test_red_timeout_wait_timeout(self, repo, rc):
        old = git(repo, "rev-parse", "main")
        ev = Events()
        out, _ = gated_merge(repo, "feat", lambda a, c: (rc, "FAILED t::x\n"), ev)
        assert not out.ok and git(repo, "rev-parse", "main") == old
        assert slot_free() and snapshots(repo) == []
        assert ev.names()[-1] == "slot_released"

    def test_interrupt(self, repo):
        def run(argv, cwd):
            raise KeyboardInterrupt

        ev = Events()
        with pytest.raises(KeyboardInterrupt):
            gated_merge(repo, "feat", run, ev)
        assert slot_free() and snapshots(repo) == []
        assert ev.names()[-1] == "slot_released"

    def test_abort_on_conflict(self, repo):
        commit_file(repo, "lib/other.txt", "o-main\n", "main edit")
        ev = Events()
        out, _ = gated_merge(repo, "feat", lambda a, c: (0, ""), ev)
        assert not out.ok
        assert slot_free() and snapshots(repo) == []
        assert ev.names() == ["slot_acquired", "slot_released"]


class TestSlotEstimate:
    """合併閘門寫入名額的預估持有秒數：取自 worktree-merge.log 近期綠燈耗時的中位數（0.5.0-W1-303.2）。"""

    @staticmethod
    def write_log(root, lines):
        log = Path(root) / mg._LOG_FILE
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def line(suite, status, seconds):
        return f"2026-10-15T09:00:00 [合併前測試] 套件 {suite}：{status}｜1 passed｜耗時 {seconds}s"

    def test_median_of_recent_green_runs_per_suite_summed(self, tmp_path):
        self.write_log(tmp_path, [
            self.line("hooks", "綠燈", 100.0), self.line("hooks", "綠燈", 300.0), self.line("hooks", "綠燈", 200.0),
            self.line("hooks", "紅燈", 9999.0),  # 非綠燈不計
            self.line("scripts", "綠燈", 40.0),
        ])
        assert mg.suite_estimate_seconds(["hooks", "scripts"], str(tmp_path)) == 200.0 + 40.0

    def test_only_last_samples_are_used(self, tmp_path):
        old = [self.line("hooks", "綠燈", 1000.0)] * 10
        new = [self.line("hooks", "綠燈", 10.0)] * mg.ESTIMATE_SAMPLE_COUNT
        self.write_log(tmp_path, old + new)
        assert mg.suite_estimate_seconds(["hooks"], str(tmp_path)) == 10.0

    def test_missing_log_uses_defaults(self, tmp_path):
        assert mg.suite_estimate_seconds(["hooks", "flutter"], str(tmp_path)) == \
            mg.default_suite_seconds("hooks") + mg.default_suite_seconds("flutter")

    def test_suite_without_history_uses_its_default_others_use_median(self, tmp_path):
        self.write_log(tmp_path, [self.line("hooks", "綠燈", 50.0)])
        assert mg.suite_estimate_seconds(["hooks", "scripts"], str(tmp_path)) == \
            50.0 + mg.default_suite_seconds("scripts")

    def test_hold_writes_estimate_into_holder_file(self, repo):
        self.write_log(repo, [self.line("flutter", "綠燈", 100.0), self.line("flutter", "綠燈", 300.0),
                              self.line("flutter", "綠燈", 200.0)])
        gate = mg.MergeGate(str(repo), runner=lambda a, c: (0, ""))
        from lib import slot_gate
        with gate.hold("feat", "main"):
            holders = list(Path(slot_gate.slot_dir()).glob("heavy-slot-*.holder.json"))
            assert len(holders) == 1
            assert json.loads(holders[0].read_text())["estimate"] == 200.0


class TestGateRefusalExpected:
    """持有者超出預估過久的放棄等待是預期內結果：一行說明、結束碼 125、不印 traceback；非預期例外仍保留。"""

    @staticmethod
    def occupy(estimate):
        """占住名額的持有者，已持有時間遠超自身預估與等待上限（卡住）。"""
        from lib import slot_gate
        hold, _ = slot_gate.acquire_slot(["other"], lambda: None, estimate_seconds=estimate)
        assert hold is not None
        info = json.loads(Path(hold.holder_path).read_text())
        info["started_epoch"] = time.time() - estimate - 99999
        Path(hold.holder_path).write_text(json.dumps(info))
        return hold

    def test_estimate_rejection_is_single_line_exit_125(self, repo, capsys):
        old = git(repo, "rev-parse", "main")
        hold = self.occupy(10.0)
        try:
            rc = wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([])))
        finally:
            hold.release()
        cap = capsys.readouterr()
        assert rc == 125
        assert "Traceback" not in cap.out + cap.err
        assert (cap.out + cap.err).count("疑似卡住") == 1
        assert git(repo, "rev-parse", "main") == old

    def test_unexpected_exception_keeps_traceback(self, repo, monkeypatch):
        def boom(*_a, **_k):
            raise ValueError("非預期故障")

        monkeypatch.setattr(mg.slot_gate, "acquire_slot", boom)
        with pytest.raises(ValueError, match="非預期故障"):
            wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([])))
        assert "結果 中止" in (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")

    def test_refusal_error_is_distinct_type_carrying_exit_code(self, repo):
        hold = self.occupy(10.0)
        try:
            with pytest.raises(mg.SlotWaitRefused) as info:
                with mg.MergeGate(str(repo)).hold("feat", "main"):
                    pass
        finally:
            hold.release()
        assert info.value.exit_code == 125


class TestGateLog:
    """每次閘門開始與結束各一行：target、分支、commit、結果；寫入 stdout 與 worktree-merge.log。"""

    @staticmethod
    def gate_lines(repo):
        log = (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")
        return [ln for ln in log.splitlines() if mg.GATE_LINE_PREFIX in ln]

    def test_written_has_start_and_end_with_merge_commit(self, repo, capsys):
        base = git(repo, "rev-parse", "main")
        assert wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([]))) == 0
        merged = git(repo, "rev-parse", "main")
        start, _pre, end = self.gate_lines(repo)
        print(start)
        print(end)
        assert "開始" in start and "target main" in start and base[:12] in start and "分支 feat" in start
        assert "結束" in end and "target main" in end and merged[:12] in end and "結果 寫入" in end
        out = capsys.readouterr().out
        assert start.split(" ", 1)[1] in out and end.split(" ", 1)[1] in out

    def test_red_result(self, repo):
        base = git(repo, "rev-parse", "main")
        assert wm.cmd_merge(None, branch="feat", gate_runner=art(lambda a, c: (1, "FAILED t::x\n"))) == 1
        start, _pre, end = self.gate_lines(repo)
        assert "結果 紅燈" in end and base[:12] in end

    def test_refused_result(self, repo):
        base = git(repo, "rev-parse", "main")
        hold = TestGateRefusalExpected.occupy(10.0)
        try:
            assert wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([]))) == 125
        finally:
            hold.release()
        start, _pre, end = self.gate_lines(repo)
        assert "結果 拒絕" in end and base[:12] in end

    def test_timeout_and_abort_are_distinguished(self):
        assert mg.gate_result_label("[hooks] 全套件逾時（1 秒）") == "逾時"
        assert mg.gate_result_label("[hooks] 等待本機名額逾時，全套件未執行") == "逾時"
        assert mg.gate_result_label("CAS expected old") == "中止"

    def test_gate_lines_do_not_pollute_estimate_samples(self, repo):
        assert wm.cmd_merge(None, branch="feat", gate_runner=art(lambda a, c: (0, "1 passed in 7.00s\n"))) == 0
        lines = self.gate_lines(repo)
        assert lines and all("[合併前測試]" not in ln for ln in lines)
        assert set(mg._recent_green_seconds(str(repo))) == {"flutter"}
        assert len(mg._recent_green_seconds(str(repo))["flutter"]) == 1
        # 對照：日誌中偽造含「綠燈」「耗時」的閘門行也不被當樣本
        fake = f"{mg.GATE_LINE_PREFIX} 結束｜target main｜分支 x｜commit abc｜結果 寫入｜套件 flutter：綠燈｜耗時 1s"
        with open(repo / ".claude/logs/worktree-merge.log", "a", encoding="utf-8") as fh:
            fh.write(f"2026-10-15T00:00:00 {fake}\n")
        assert len(mg._recent_green_seconds(str(repo))["flutter"]) == 1


class TestFailureDetailRetention:
    """紅燈時保留失敗細節（W1-314.1）：E 行、全輸出旁置檔、記憶體快照。"""

    def _run_red(self, tmp_path, monkeypatch, output):
        monkeypatch.setattr(mg, "memory_snapshot", lambda: "memory_pressure: 測試值\nvm_stat pageouts: 42")
        runner = lambda argv, cwd: (1, output)  # noqa: E731
        return mg._run_suites(["hooks"], str(tmp_path), str(tmp_path), runner, str(tmp_path), tag="abc123def456789")

    def test_reason_has_e_line_and_detail_path(self, tmp_path, monkeypatch, capsys):
        out = "FAILED t.py::test_x - assert 1 == 2\nE   assert 1 == 2\nCaptured stderr call\nBOOM-STDERR\n"
        reason = self._run_red(tmp_path, monkeypatch, out)
        assert "E   assert 1 == 2" in reason
        detail = tmp_path / ".claude/logs/merge-gate-failures/abc123def456-hooks.log"
        assert str(detail) in reason
        text = detail.read_text(encoding="utf-8")
        assert "BOOM-STDERR" in text
        assert "vm_stat pageouts: 42" in text and "memory_pressure: 測試值" in text

    def test_e2_no_log_root_does_not_raise(self, monkeypatch, capsys):
        """E2 對照：log_root 與 project_root 皆為 None 時紅燈不拋例外，失敗項照常輸出。"""
        monkeypatch.setattr(mg, "_ensure_artifacts", lambda *a: "")
        out = "FAILED t.py::test_x - boom\nE   boom\n"
        reason = mg._run_suites(["hooks"], "/snap", None, lambda a, c: (1, out), None)
        assert "FAILED t.py::test_x" in reason and "E   boom" in reason
        assert "全輸出與記憶體快照" not in reason
        assert "略過失敗細節旁置檔" in capsys.readouterr().err

    def test_green_writes_no_detail_file(self, tmp_path):
        mg._run_suites(["hooks"], str(tmp_path), str(tmp_path), lambda a, c: (0, "1 passed"), str(tmp_path))
        assert not (tmp_path / ".claude/logs/merge-gate-failures").exists()

    def test_memory_probe_failure_is_fail_open(self, monkeypatch, capsys):
        def boom(*a, **k):
            raise FileNotFoundError("no memory_pressure")
        monkeypatch.setattr(mg.subprocess, "run", boom)
        snap = mg.memory_snapshot()
        assert "取不到" in snap and "swap: 取不到" in snap
        assert "fail-open" in capsys.readouterr().err

    def test_snapshot_includes_swap(self, monkeypatch):
        monkeypatch.setattr(mg, "_probe", lambda argv: "vm.swapusage: total = 1.00M" if argv[0] == "sysctl" else "")
        assert "swap: vm.swapusage: total = 1.00M" in mg.memory_snapshot()

    def test_e2_real_failing_pytest_keeps_detail(self, tmp_path, monkeypatch):
        """E2 對照：真實必紅測試經 default_runner 跑，細節確實落檔。"""
        t = tmp_path / "test_always_red.py"
        t.write_text(
            "import sys\n"
            "def test_red():\n"
            "    sys.stderr.write('E2-STDERR-MARK\\n')\n"
            "    assert 1 == 2, 'E2-ASSERT-MARK'\n")
        monkeypatch.setattr(mg, "suite_command", lambda s, root: [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", str(t)])
        monkeypatch.setattr(mg, "wrapped_argv", lambda cmd, timeout=0: cmd)
        monkeypatch.setattr(mg, "_ensure_artifacts", lambda *a: "")
        reason = mg._run_suites(["hooks"], str(tmp_path), str(tmp_path), mg.default_runner, str(tmp_path), tag="e2commit0000")
        assert "E2-ASSERT-MARK" in reason
        text = (tmp_path / ".claude/logs/merge-gate-failures/e2commit0000-hooks.log").read_text(encoding="utf-8")
        assert "E2-STDERR-MARK" in text and "E2-ASSERT-MARK" in text


class TestPrecheckConflict:
    """進場排隊前以 merge-tree 預檢文字衝突（0.5.0-W1-328）。"""

    @staticmethod
    def gate_lines(repo):
        log = (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")
        return [ln for ln in log.splitlines() if mg.GATE_LINE_PREFIX in ln]

    def test_conflict_reported_before_queueing(self, repo):
        advance_main(repo, "lib/other.txt", "o-main\n")  # 與 feat 對同檔同處不同改動
        base = git(repo, "rev-parse", "main")
        calls = []
        hold = TestGateRefusalExpected.occupy(10.0)  # 若進入排隊，會因名額被占而回 125
        try:
            rc = wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner(calls)))
        finally:
            hold.release()
        assert rc == 1
        assert git(repo, "rev-parse", "main") == base and not calls
        _, end = self.gate_lines(repo)
        assert f"結果 {mg.GATE_PRECHECK_CONFLICT}" in end

    def test_conflict_appearing_while_queued_still_aborts_after_slot(self, repo, monkeypatch):
        """對照：預檢通過，排隊期間 main 前進產生衝突，取得名額後仍中止且 ref 不變。"""
        real_hold = mg.MergeGate.hold
        state = {}

        def hold_then_advance(self, branch, base):
            with real_hold(self, branch, base):
                advance_main(repo, "lib/other.txt", "o-main\n")
                state["advanced"] = git(repo, "rev-parse", "main")
                yield

        import contextlib
        monkeypatch.setattr(mg.MergeGate, "hold", contextlib.contextmanager(hold_then_advance))
        rc = wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([])))
        assert rc == 1
        assert git(repo, "rev-parse", "main") == state["advanced"]
        *_, end = self.gate_lines(repo)
        assert f"結果 {mg.GATE_ABORTED}" in end

    def test_clean_precheck_logs_one_line_between_start_and_end(self, repo):
        """預檢無衝突時，gate 日誌依序為開始、預檢無衝突、結束（0.5.0-W1-328.1）。"""
        rc = wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([])))
        assert rc == 0
        start, pre, end = self.gate_lines(repo)
        assert "開始" in start and "結束" in end
        assert pre.split(mg.GATE_LINE_PREFIX, 1)[1].strip().startswith("預檢") and f"結果 {mg.GATE_PRECHECK_CLEAR}" in pre
        assert pre.split("｜")[1:3] == start.split("｜")[1:3]  # target、分支欄位與開始行一致

    def test_already_merged_passes_precheck(self, repo):
        git(repo, "merge", "--no-edit", "feat")
        assert mc.precheck_merge_conflict("feat", "main", str(repo)) == ""


class TestPrecheckException:
    def test_precheck_exception_logs_abort_and_reraises(self, repo, monkeypatch):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired("git", 60)

        monkeypatch.setattr(wm, "precheck_merge_conflict", boom)
        with pytest.raises(subprocess.TimeoutExpired):
            wm.cmd_merge(None, branch="feat", gate_runner=art(green_runner([])))
        log = (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")
        lines = [ln for ln in log.splitlines() if mg.GATE_LINE_PREFIX in ln]
        assert len(lines) == 2 and f"結果 {mg.GATE_ABORTED}" in lines[1]


# ---- 專案宣告的套件對應（410.3.1）----

DECL_REL = ".claude/project-integration/merge-gate.yaml"
WEB_DECL = """\
suites:
  web:
    prefixes: [web/]
    files: [package.json]
    command: [npm, test]
    artifacts:
      - path: node_modules/.ready
        generate: [npm, ci]
"""
# 與內建 Flutter 對應等價的宣告：改寫後選套件結果須與內建一致
FLUTTER_DECL = """\
suites:
  flutter:
    prefixes: [lib/, test/, integration_test/, macos/, docs/, assets/]
    files: [pubspec.yaml, pubspec.lock, l10n.yaml, analysis_options.yaml]
    command: [fvm, flutter, test]
    artifacts:
      - path: .dart_tool/package_config.json
        generate: [fvm, flutter, pub, get]
"""


def declare(root, text):
    _touch(Path(root), DECL_REL, text)


class TestDeclaration:
    def test_declared_prefix_and_file_hit(self, skel):
        declare(skel, WEB_DECL)
        assert mg.select_suites(["web/a.js"], skel) == ["web"]
        assert mg.select_suites(["package.json"], skel) == ["web"]

    def test_declared_replaces_builtin_flutter_miss(self, skel):
        """E1 未命中向：宣告取代內建，lib/ 不再對應 flutter。"""
        declare(skel, WEB_DECL)
        assert mg.select_suites(["lib/main.dart"], skel) == []
        assert not mg.needs_gate(["lib/main.dart"], mg.load_declaration(skel))

    def test_claude_mapping_kept_with_declaration(self, skel):
        declare(skel, WEB_DECL)
        assert mg.select_suites([".claude/hooks/a.py"], skel) == [mg.SUITE_HOOKS]

    def test_declared_command(self, skel):
        declare(skel, WEB_DECL)
        assert mg.suite_command("web", skel) == ["npm", "test"]

    def test_builtin_flutter_equals_declared_flutter(self, skel):
        paths = ["lib/a.dart", "pubspec.lock", "docs/x.md", "assets/a.json", "tools/z.py",
                 ".claude/hooks/h.py", "README.md"]
        builtin = ([mg.select_suites([p], skel) for p in paths], mg.suite_command("flutter", skel),
                   [mg.needs_gate([p]) for p in paths], mg.unmapped_paths(paths))
        declare(skel, FLUTTER_DECL)
        decl = mg.load_declaration(skel)
        declared = ([mg.select_suites([p], skel) for p in paths], mg.suite_command("flutter", skel),
                    [mg.needs_gate([p], decl) for p in paths], mg.unmapped_paths(paths, decl))
        assert declared == builtin
        assert mg.declared_artifacts("flutter", decl) == mg.REQUIRED_ARTIFACTS["flutter"]

    def test_absent_declaration_is_none(self, skel):
        assert mg.load_declaration(skel) is None


BAD_DECLS = [
    ("suites: [1]\n", "suites"),
    ("suites:\n  web:\n    prefixes: [web/]\n", "suites.web.command"),
    ("suites:\n  web:\n    command: [npm, test]\n", "suites.web.prefixes"),
    ("suites:\n  web:\n    prefixes: []\n    files: []\n    command: [npm]\n", "suites.web.prefixes"),
    ("suites:\n  hooks:\n    prefixes: [a/]\n    command: [x]\n", "suites.hooks"),
    ("suites:\n  scripts:\n    prefixes: [a/]\n    command: [x]\n", "suites.scripts"),
    ("suites:\n  skill:foo:\n    prefixes: [a/]\n    command: [x]\n", "suites.skill:foo"),
    ("suites:\n  web:\n    prefixes: [a/]\n    command: [x]\n    artifacts: [{path: p}]\n",
     "suites.web.artifacts[0].generate"),
    ("suites: {\n", "YAML"),
]


class TestDeclarationInvalid:
    @pytest.mark.parametrize("text,field", BAD_DECLS)
    def test_load_raises_naming_file_and_field(self, skel, text, field):
        declare(skel, text)
        with pytest.raises(mg.DeclarationError) as exc:
            mg.load_declaration(skel)
        assert DECL_REL in str(exc.value) and field in str(exc.value)

    @pytest.mark.parametrize("text,field", BAD_DECLS)
    def test_gate_red_fail_closed(self, repo, text, field):
        """E2：格式錯誤的宣告使閘門判紅（正向對照見 TestDeclaredGate 的合法宣告通過）。"""
        commit_file(repo, DECL_REL, text, "bad decl")
        head = git(repo, "rev-parse", "HEAD")
        calls = []
        res = mg.MergeGate(str(repo), green_runner(calls))(head, "main", head, 1)
        assert not res.passed and DECL_REL in res.reason and field in res.reason
        assert calls == []


class TestYamlUnavailable:
    def test_no_declaration_passes_declared_fails_closed(self, repo, monkeypatch):
        monkeypatch.setitem(sys.modules, "yaml", None)  # import yaml 觸發 ImportError
        head = git(repo, "rev-parse", "HEAD")
        assert mg.MergeGate(str(repo), green_runner([]))(head, "main", head, 1).passed
        commit_file(repo, DECL_REL, WEB_DECL, "decl")
        head = git(repo, "rev-parse", "HEAD")
        res = mg.MergeGate(str(repo), green_runner([]))(head, "main", head, 1)
        assert not res.passed and "pyyaml" in res.reason and DECL_REL in res.reason


class TestDeclaredGate:
    def _gate(self, repo, monkeypatch, paths, calls):
        monkeypatch.setattr(mg, "changed_paths_between", lambda *_a: paths)
        head = git(repo, "rev-parse", "HEAD")

        def run(argv, cwd):
            calls.append(argv[argv.index("--") + 1:])
            if "ci" in argv:
                _touch(Path(cwd), "node_modules/.ready")
            elif "pub" in argv:
                make_artifact(cwd)
            return 0, ""

        return mg.MergeGate(str(repo), run)(head, "main", head, 1)

    def test_hit_runs_declared_command_after_artifact(self, repo, monkeypatch):
        commit_file(repo, DECL_REL, WEB_DECL, "decl")
        calls = []
        assert self._gate(repo, monkeypatch, ["web/a.js"], calls).passed
        assert calls == [["npm", "ci"], ["npm", "test"]]

    def test_miss_runs_nothing(self, repo, monkeypatch, capsys):
        commit_file(repo, DECL_REL, WEB_DECL, "decl")
        calls = []
        assert self._gate(repo, monkeypatch, ["lib/a.dart"], calls).passed
        assert calls == [] and "免跑" in capsys.readouterr().out

    def test_declared_prefix_not_warned_as_unmapped(self, repo, monkeypatch, capsys):
        commit_file(repo, DECL_REL, WEB_DECL, "decl")
        self._gate(repo, monkeypatch, ["web/a.js", "tools/x.py"], [])
        out = capsys.readouterr().out
        assert "tools/x.py" in out and "web/a.js" not in out

    def test_absent_declaration_prints_info_and_uses_flutter(self, repo, monkeypatch, capsys):
        calls = []
        assert self._gate(repo, monkeypatch, ["lib/a.dart"], calls).passed
        out = capsys.readouterr().out
        assert "INFO" in out and DECL_REL in out
        assert ["fvm", "flutter", "test"] in calls
