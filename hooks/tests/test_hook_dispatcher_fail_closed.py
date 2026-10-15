"""0.5.0-W1-277：分派層故障（預算用盡、逾時、registry 讀取失敗、分派例外）不得整批放行守衛。

每種故障各有正向對照：已知應被擋下的輸入，仍被擋下（exit 2）。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HOOKS_DIR.parent.parent
sys.path.insert(0, str(HOOKS_DIR))

_spec = importlib.util.spec_from_file_location("hook_dispatcher_module_fc", HOOKS_DIR / "hook-dispatcher.py")
disp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(disp)

GUARD_BODY = (
    "import json, sys\n"
    "# run_hook_safely(main, 'x', fail_closed=True)\n"
    "cmd = json.load(sys.stdin).get('tool_input', {}).get('command', '')\n"
    "if 'danger' in cmd:\n"
    "    sys.stderr.write('guard blocked')\n"
    "    sys.exit(2)\n"
)
BLOCK_PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "danger"}})
PASS_PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
HANG = "import time\ntime.sleep(10)\n"
CLOSED_MARK = "# run_hook_safely(main, 'g', fail_closed=True)\n"


def _write_hook(tmp_path, name, body):
    p = tmp_path / (name + ".py")
    p.write_text(body, encoding="utf-8")
    return {"path": p.name}


class _Clock:
    """第一次呼叫（起點）回 0，之後回固定值，模擬預算已耗盡或仍充裕"""

    def __init__(self, later):
        self.later = later
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return 0.0 if self.calls == 1 else self.later


EXHAUSTED = 10 ** 6


class TestBudgetExhaustedDoesNotSkipGuards:
    def test_exhausted_budget_still_blocks_with_trailing_guard(self, tmp_path):
        entries = [_write_hook(tmp_path, "first", "pass\n"), _write_hook(tmp_path, "guard", GUARD_BODY)]
        results = disp.dispatch(entries, BLOCK_PAYLOAD, tmp_path, 100, clock=_Clock(EXHAUSTED))
        assert [r.name for r in results] == ["first", "guard"]
        assert results[1].code == 2 and "guard blocked" in results[1].stderr
        assert not any("未執行" in r.error for r in results)
        assert disp.merge_results(results)[0] == 2

    def test_benign_command_passes_when_budget_exhausted(self, tmp_path):
        results = disp.dispatch([_write_hook(tmp_path, "guard", GUARD_BODY)], PASS_PAYLOAD, tmp_path, 100,
                                clock=_Clock(EXHAUSTED))
        assert disp.merge_results(results)[0] == 0

    def test_tail_hook_gets_full_own_timeout(self, tmp_path):
        slow = _write_hook(tmp_path, "slowguard", "import time\ntime.sleep(2)\nimport sys\nsys.exit(2)\n")
        slow["timeout"] = 30  # 剩餘預算為負，仍須拿到完整自身逾時
        results = disp.dispatch([slow], "{}", tmp_path, 100, clock=_Clock(EXHAUSTED))
        assert results[0].code == 2 and not results[0].error

    def test_ample_budget_stays_serial_in_process(self, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(disp, "_run_tail", lambda *a, **k: called.append(1))
        results = disp.dispatch([_write_hook(tmp_path, "guard", GUARD_BODY)], BLOCK_PAYLOAD, tmp_path, 100,
                                clock=_Clock(1.0))
        assert not called and results[0].code == 2

    def test_hook_whose_timeout_exceeds_remaining_budget_goes_to_tail_not_shortened(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(disp, "_run_one", lambda path, payload, timeout, inprocess, logger:
                            seen.append((timeout, inprocess)) or disp.HookResult(path.stem, 0))
        heavy = _write_hook(tmp_path, "heavy", "pass\n")
        heavy["timeout"] = 595
        disp.dispatch([heavy], "{}", tmp_path, 380, clock=_Clock(10.0))
        assert seen == [(595.0, False)]

    def test_tail_results_keep_registry_order(self, tmp_path):
        entries = [_write_hook(tmp_path, n, "pass\n") for n in ("a", "b", "c")]
        results = disp.dispatch(entries, "{}", tmp_path, 100, clock=_Clock(EXHAUSTED))
        assert [r.name for r in results] == ["a", "b", "c"]


class TestTimeoutRespectsFailClosed:
    def test_fail_closed_guard_timeout_blocks(self, tmp_path):
        guard = _write_hook(tmp_path, "g", HANG + CLOSED_MARK)
        guard["timeout"] = 1
        r = disp.dispatch([guard], "{}", tmp_path, 100)[0]
        assert r.code == 2 and "逾時" in r.error

    def test_fail_open_hook_timeout_stays_visible_exit_1(self, tmp_path):
        hook = _write_hook(tmp_path, "o", HANG)
        hook["timeout"] = 1
        r = disp.dispatch([hook], "{}", tmp_path, 100)[0]
        assert r.code == 1 and "逾時" in r.error

    def test_fail_closed_guard_timeout_in_tail_subprocess_blocks(self, tmp_path):
        guard = _write_hook(tmp_path, "g", HANG + CLOSED_MARK)
        guard["timeout"] = 1
        r = disp.dispatch([guard], "{}", tmp_path, 100, clock=_Clock(EXHAUSTED))[0]
        assert r.code == 2 and "逾時" in r.error

    def test_fail_closed_guard_load_error_blocks_but_open_hook_does_not(self, tmp_path):
        broken_closed = _write_hook(tmp_path, "bc", "def (:\n" + CLOSED_MARK)
        broken_open = _write_hook(tmp_path, "bo", "def (:\n")
        rc, ro = disp.dispatch([broken_closed, broken_open], "{}", tmp_path, 100)
        assert rc.code == 2 and ro.code == 1

    def test_default_timeout_not_below_claude_code_default(self):
        assert disp.DEFAULT_HOOK_TIMEOUT >= 60


class TestDispatchLayerFailureStillRunsFailClosedGuards:
    def _run_main(self, tmp_path, monkeypatch, capsys, payload, break_how):
        guard = _write_hook(tmp_path, "guard", GUARD_BODY)
        monkeypatch.setattr(disp, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(disp, "FALLBACK_FAIL_CLOSED_GUARDS", {"G:Bash": [guard["path"]]})
        if break_how == "registry":
            def unreadable(*a, **k):
                raise OSError("registry 讀取失敗")
            monkeypatch.setattr(disp, "load_group", unreadable)
        else:
            def boom(*a, **k):
                raise RuntimeError("分派層例外")
            monkeypatch.setattr(disp, "run_group", boom)
        monkeypatch.setattr(sys, "argv", ["hook-dispatcher.py", "--group", "G:Bash"])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        code = disp.main()
        return code, capsys.readouterr()

    @pytest.mark.parametrize("how", ["registry", "run_group"])
    def test_blocked_command_still_blocked(self, tmp_path, monkeypatch, capsys, how):
        code, cap = self._run_main(tmp_path, monkeypatch, capsys, BLOCK_PAYLOAD, how)
        assert code == 2
        assert "guard blocked" in cap.err and "分派失敗" in cap.err

    @pytest.mark.parametrize("how", ["registry", "run_group"])
    def test_benign_command_is_visible_exit_1_not_locked_out(self, tmp_path, monkeypatch, capsys, how):
        code, cap = self._run_main(tmp_path, monkeypatch, capsys, PASS_PAYLOAD, how)
        assert code == 1 and "分派失敗" in cap.err

    def test_fallback_list_matches_declared_fail_closed_guards(self):
        reg = json.loads((HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))["groups"]
        for group, cfg in reg.items():
            declared = sorted(e["path"] for e in cfg["hooks"] if disp.is_fail_closed(PROJECT_ROOT / e["path"]))
            assert sorted(disp.FALLBACK_FAIL_CLOSED_GUARDS.get(group, [])) == declared, group


class TestSettingsTimeoutCoversWorstCase:
    def test_settings_timeout_covers_serial_budget_plus_tail_and_stays_below_unit_guard(self):
        reg = json.loads((HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))["groups"]
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        for event, group in (("PreToolUse", "PreToolUse:Bash"), ("PostToolUse", "PostToolUse:Bash")):
            tmax = max([float(e.get("timeout", disp.DEFAULT_HOOK_TIMEOUT)) for e in reg[group]["hooks"]]
                       + [float(disp.DEFAULT_HOOK_TIMEOUT)])
            bash = [g for g in hooks[event] if g.get("matcher") == "Bash"][0]
            assert reg[group]["budget"] + tmax + 20 <= bash["hooks"][0]["timeout"] < 1000
