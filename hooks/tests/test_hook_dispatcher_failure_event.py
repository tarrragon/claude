"""hook 分派器對 PostToolUseFailure:Bash 群組的支援測試

涵蓋驗收 1（群組、hook_event_name 原樣轉交、同一 hook 列兩群組、兩群組 hookEventName）、
4（失敗事件處理出錯時不阻擋）、6（event_type 與 fallback 清單）、7（註冊表消費端）。
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HOOKS_DIR.parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(PROJECT_ROOT / ".claude"))

_spec = importlib.util.spec_from_file_location("hook_dispatcher_failure_mod", HOOKS_DIR / "hook-dispatcher.py")
disp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(disp)

from lib import hook_registry  # noqa: E402

FAILURE_GROUP = "PostToolUseFailure:Bash"
FAILURE_PAYLOAD = json.dumps({
    "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
    "tool_input": {"command": "false"}, "error": "Exit code 1",
    "is_interrupt": False, "duration_ms": 12})
# 子 hook 把收到的 hook_event_name 放進 additionalContext，並固定宣稱事件為 PostToolUse
ECHO_HOOK = (
    "import json, sys\n"
    "d = json.load(sys.stdin)\n"
    "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse',"
    " 'additionalContext': 'got=' + d.get('hook_event_name', '')}}))\n")


def _registry(tmp_path, groups):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"groups": groups}), encoding="utf-8")
    return reg


def _echo_hook(tmp_path):
    (tmp_path / "echo.py").write_text(ECHO_HOOK, encoding="utf-8")
    return {"path": "echo.py"}


class TestEventNameInMergedOutput:
    """驗收 1：合併輸出的 hookEventName 等於群組的實際事件"""

    @pytest.mark.parametrize("group,event", [
        (FAILURE_GROUP, "PostToolUseFailure"),
        ("PostToolUse:Bash", "PostToolUse"),
        ("PreToolUse:Bash", "PreToolUse"),
    ])
    def test_each_group_emits_its_own_event_name(self, tmp_path, group, event):
        reg = _registry(tmp_path, {group: {"budget": 30, "hooks": [_echo_hook(tmp_path)]}})
        code, out, _ = disp.run_group(group, FAILURE_PAYLOAD, reg, tmp_path, inprocess=False)
        assert code == 0
        assert json.loads(out)["hookSpecificOutput"]["hookEventName"] == event

    def test_contrast_without_event_child_name_leaks_through(self):
        """E1 對照：不傳 event 時沿用子 hook 的 PostToolUse，證明覆寫確實生效而非巧合相等"""
        child = json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "x"}})
        _, without, _ = disp.merge_results([disp.HookResult("a", 0, child)])
        _, with_event, _ = disp.merge_results([disp.HookResult("a", 0, child)], "PostToolUseFailure")
        assert json.loads(without)["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert json.loads(with_event)["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"

    def test_event_of_group(self):
        assert disp.event_of_group(FAILURE_GROUP) == "PostToolUseFailure"
        assert disp.event_of_group("") == ""


class TestPayloadForwarding:
    def test_hook_event_name_forwarded_verbatim(self, tmp_path):
        reg = _registry(tmp_path, {FAILURE_GROUP: {"budget": 30, "hooks": [_echo_hook(tmp_path)]}})
        _, out, _ = disp.run_group(FAILURE_GROUP, FAILURE_PAYLOAD, reg, tmp_path, inprocess=False)
        assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == "got=PostToolUseFailure"

    def test_same_hook_can_sit_in_two_groups(self, tmp_path):
        entry = _echo_hook(tmp_path)
        reg = _registry(tmp_path, {
            "PostToolUse:Bash": {"budget": 30, "hooks": [entry]},
            FAILURE_GROUP: {"budget": 30, "hooks": [entry]}})
        success = json.dumps({"hook_event_name": "PostToolUse"})
        _, out_ok, _ = disp.run_group("PostToolUse:Bash", success, reg, tmp_path, inprocess=False)
        _, out_fail, _ = disp.run_group(FAILURE_GROUP, FAILURE_PAYLOAD, reg, tmp_path, inprocess=False)
        assert "got=PostToolUse" in out_ok and "got=PostToolUseFailure" not in out_ok
        assert "got=PostToolUseFailure" in out_fail
        groups = hook_registry.load_registry_groups(tmp_path, reg)
        assert [e["path"] for e in groups["PostToolUse:Bash"]["hooks"]] == \
            [e["path"] for e in groups[FAILURE_GROUP]["hooks"]]


class TestFailureEventNeverBlocks:
    """驗收 4：處理失敗事件出錯時不阻擋（exit 不為 2）"""

    def _run_main(self, monkeypatch, capsys, group, break_registry=True):
        if break_registry:
            def unreadable(*a, **k):
                raise OSError("registry 讀取失敗")
            monkeypatch.setattr(disp, "load_group", unreadable)
        monkeypatch.setattr(sys, "argv", ["hook-dispatcher.py", "--group", group])
        monkeypatch.setattr(sys, "stdin", io.StringIO(FAILURE_PAYLOAD))
        return disp.main(), capsys.readouterr()

    def test_dispatch_layer_failure_is_visible_but_not_blocking(self, monkeypatch, capsys):
        code, cap = self._run_main(monkeypatch, capsys, FAILURE_GROUP)
        assert code == 1
        assert "分派失敗" in cap.err

    def test_contrast_pre_tool_use_group_still_runs_fail_closed_guards(self, tmp_path, monkeypatch, capsys):
        """正向對照：同一故障下，有 fail_closed 守衛的 PreToolUse 群組仍可 exit 2，失敗群組則不會"""
        guard = tmp_path / "guard.py"
        guard.write_text("import sys\nsys.stderr.write('blocked')\nsys.exit(2)\n", encoding="utf-8")
        monkeypatch.setattr(disp, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(disp, "is_fail_closed", lambda p: True)
        monkeypatch.setattr(disp, "FALLBACK_FAIL_CLOSED_GUARDS", {
            "PreToolUse:Bash": ["guard.py"], FAILURE_GROUP: []})
        pre_code, _ = self._run_main(monkeypatch, capsys, "PreToolUse:Bash")
        fail_code, _ = self._run_main(monkeypatch, capsys, FAILURE_GROUP)
        assert pre_code == 2
        assert fail_code != 2

    def test_crashing_child_hook_does_not_block(self, tmp_path):
        (tmp_path / "boom.py").write_text("raise RuntimeError('壞掉')\n", encoding="utf-8")
        reg = _registry(tmp_path, {FAILURE_GROUP: {"budget": 30, "hooks": [{"path": "boom.py"}]}})
        code, _, err = disp.run_group(FAILURE_GROUP, FAILURE_PAYLOAD, reg, tmp_path)
        assert code == 1 and "壞掉" in err

    def test_real_group_exits_zero_on_failure_payload(self):
        p = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "hook-dispatcher.py"), "--group", FAILURE_GROUP],
            input=FAILURE_PAYLOAD, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert p.returncode == 0, p.stderr
        # 群組成員無內容時可能輸出 DEFAULT_OUTPUT 空殼（IMP-055 契約），守的是「不阻擋」
        if p.stdout.strip():
            specific = json.loads(p.stdout)["hookSpecificOutput"]
            assert "permissionDecision" not in specific
            assert "decision" not in specific
            assert specific["hookEventName"] == "PostToolUseFailure"


class TestMetadataAndFallback:
    """驗收 6"""

    @staticmethod
    def _dispatcher_events(hooks):
        """settings.hooks 中有群組 command 指向 hook-dispatcher.py 的事件集合。"""
        return {
            event
            for event, groups in hooks.items()
            for g in groups
            for h in g.get("hooks", [])
            if "hook-dispatcher.py" in h.get("command", "")
        }

    def test_settings_registers_failure_event_and_keeps_existing_events(self):
        # 權威來源為 settings.json 的事件註冊（HOOK_METADATA 已於 299 移除）
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        events = self._dispatcher_events(hooks)
        assert "PostToolUseFailure" in events
        assert {"PreToolUse", "PostToolUse"} <= events  # 既有事件未被擠掉

    def test_dispatcher_events_detects_missing_failure_registration(self):
        # E2 對照：刪掉 PostToolUseFailure 的複本，上一案的斷言必翻紅
        hooks = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        trimmed = {k: v for k, v in hooks.items() if k != "PostToolUseFailure"}
        assert "PostToolUseFailure" in self._dispatcher_events(hooks)
        assert "PostToolUseFailure" not in self._dispatcher_events(trimmed)

    def test_fallback_has_explicit_failure_group_without_guards(self):
        assert disp.FALLBACK_FAIL_CLOSED_GUARDS[FAILURE_GROUP] == []

    def test_registry_failure_group_members_declare_no_fail_closed(self):
        reg = json.loads((HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))["groups"]
        members = reg[FAILURE_GROUP]["hooks"]
        assert members, "群組不得為空：需有成員使實地觸發留下 liveness"
        for e in members:
            assert not disp.is_fail_closed(PROJECT_ROOT / e["path"]), e["path"]


class TestSettingsRegistration:
    def _hooks(self):
        return json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]

    def test_failure_event_registered_once_for_bash_via_dispatcher(self):
        bash = [g for g in self._hooks()["PostToolUseFailure"] if g.get("matcher") == "Bash"]
        assert len(bash) == 1 and len(bash[0]["hooks"]) == 1
        assert bash[0]["hooks"][0]["command"].endswith("hook-dispatcher.py --group " + FAILURE_GROUP)

    def test_timeout_covers_budget_plus_slowest_hook(self):
        reg = json.loads((HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))["groups"]
        tmax = max([float(e.get("timeout", disp.DEFAULT_HOOK_TIMEOUT)) for e in reg[FAILURE_GROUP]["hooks"]]
                   + [float(disp.DEFAULT_HOOK_TIMEOUT)])
        timeout = self._hooks()["PostToolUseFailure"][0]["hooks"][0]["timeout"]
        assert reg[FAILURE_GROUP]["budget"] + tmax + 20 <= timeout < 1000


class TestRegistryConsumers:
    """驗收 7：消費端把失敗群組的 hook 判為已註冊"""

    def _coverage(self):
        spec = importlib.util.spec_from_file_location(
            "coverage_check_failure_mod", HOOKS_DIR / "hook-registration-coverage-check.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _merged_real(self):
        settings = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        return hook_registry.merge_dispatch_registry(settings, PROJECT_ROOT)

    def test_merge_puts_failure_hook_under_failure_event_with_bash_matcher(self):
        merged = self._merged_real()
        groups = [g for g in merged["hooks"]["PostToolUseFailure"] if g.get("matcher") == "Bash"]
        cmds = [h["command"] for g in groups for h in g["hooks"]]
        assert any("post-tool-failure-liveness-hook.py" in c for c in cmds)

    def test_probe_hook_registered_only_via_merge(self):
        """E1 對照：不併入 registry 則判為未註冊，併入後為已註冊"""
        mod = self._coverage()
        raw = json.loads((PROJECT_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        assert "post-tool-failure-liveness-hook.py" not in mod.extract_registered_hooks(raw)
        assert "post-tool-failure-liveness-hook.py" in mod.extract_registered_hooks(self._merged_real())

    def test_validator_covers_failure_event(self):
        spec = importlib.util.spec_from_file_location(
            "validator_failure_mod", PROJECT_ROOT / ".claude" / "lib" / "hook_output_validator.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        events = {e for e, _, _ in mod.load_target_hooks()}
        assert "PostToolUseFailure" in events
