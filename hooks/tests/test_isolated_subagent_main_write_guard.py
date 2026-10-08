#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
isolated-subagent-main-write-guard-hook 測試（0.5.0-W1-111.2.1）

覆蓋：
- E2 正向對照 (a)：隔離代理人（映射命中 branch_name == worktree）的寫入落在主 repo -> 介入
  （重播 W1-105.1 事件的 6 筆真實 payload，加上 Edit/Write/NotebookEdit 路徑）
- 放行 (b)(c)(d)(e)：自己 worktree 內 / branch_name 為空 / 無 agent_id（PM）/ 映射缺失（含 info 日誌）
- E1 對照：同一組 (a) 輸入拿掉映射命中後翻為放行（有映射 vs 無映射，產物不同）
- 排除 ticket CLI、失敗語意（hook 例外 -> fail-open + stderr + 日誌）
"""

import importlib.util
import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import dispatch_tracker

HOOK_FILE = Path(__file__).parent.parent / "isolated-subagent-main-write-guard-hook.py"
FIXTURE = Path(__file__).parent / "fixtures" / "isolation_loss_replay.json"

_spec = importlib.util.spec_from_file_location("isolated_subagent_main_write_guard_hook", HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

AGENT_ID = "a8a4e24138605a3d3"


@pytest.fixture
def replay():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def main_root(tmp_path):
    root = tmp_path / "main"
    (root / ".claude").mkdir(parents=True)
    dispatch_tracker.reset_cache()
    return root


@pytest.fixture
def log():
    logger = logging.getLogger("test-isolated-guard")
    logger.setLevel(logging.DEBUG)
    return logger


def write_state(root, entries):
    (root / ".claude" / "dispatch-active.json").write_text(
        json.dumps({"dispatches": entries}), encoding="utf-8"
    )
    dispatch_tracker.reset_cache()


def entry(**kw):
    base = {
        "agent_description": "d",
        "agent_id": AGENT_ID,
        "agent_handle": "",
        "branch_name": "worktree",
        "ticket_id": "T",
        "turn_ended_at": None,
    }
    base.update(kw)
    return base


def bash_payload(cmd, cwd, agent_id=AGENT_ID):
    p = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd)}
    if agent_id is not None:
        p["agent_id"] = agent_id
    return p


def file_payload(tool, path, cwd, agent_id=AGENT_ID):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    p = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {key: str(path)}, "cwd": str(cwd)}
    if agent_id is not None:
        p["agent_id"] = agent_id
    return p


def replay_payloads(replay, main_root):
    """把 fixture 的真實主 repo 路徑換成測試用 main_root。"""
    old = replay["payloads"][0]["cwd"]
    out = []
    for p in replay["payloads"]:
        raw = json.dumps(p).replace(old, str(main_root))
        out.append(json.loads(raw))
    return out


class TestE2PositiveReplay:
    """(a) W1-105.1 事件重播：映射命中 + 寫入落在主 repo -> 介入"""

    def test_replay_write_commands_are_warned(self, replay, main_root, log):
        write_state(main_root, [replay["dispatch_entry"] | {"agent_id": replay["mapped_agent_id"]}])
        results = [hook.evaluate(p, main_root, log) for p in replay_payloads(replay, main_root)]
        warned = [bool(r) for r in results]
        # 6 筆：git status / (mkdir && git mv) / doc validate / git add / git add / git commit
        assert warned == [False, True, False, True, True, True]

    def test_warning_tells_agent_to_stop_and_handback(self, replay, main_root, log):
        write_state(main_root, [replay["dispatch_entry"] | {"agent_id": replay["mapped_agent_id"]}])
        msg = hook.evaluate(replay_payloads(replay, main_root)[3], main_root, log)
        assert "NeedsContext" in msg and "PM" in msg

    @pytest.mark.parametrize("tool", ["Edit", "Write", "NotebookEdit"])
    def test_file_tools_into_main_repo_warned(self, tool, main_root, log):
        write_state(main_root, [entry()])
        p = file_payload(tool, main_root / "docs" / "a.md", main_root)
        assert hook.evaluate(p, main_root, log)

    def test_agent_handle_regex_mapping(self, main_root, log):
        write_state(main_root, [entry(agent_id=None, agent_handle="fix-abc")])
        p = bash_payload("git add x", main_root, agent_id="afix-abc-73070ca5c1d3f849")
        assert hook.evaluate(p, main_root, log)

    def test_restore_staged_warned(self, main_root, log):
        write_state(main_root, [entry()])
        assert hook.evaluate(bash_payload("git restore --staged a.md", main_root), main_root, log)


class TestAllowCases:
    def test_b_write_inside_own_worktree(self, main_root, log):
        write_state(main_root, [entry()])
        wt = main_root / ".claude" / "worktrees" / "agent-x"
        assert not hook.evaluate(file_payload("Edit", wt / "docs" / "a.md", wt), main_root, log)
        assert not hook.evaluate(bash_payload("git add a.md", wt), main_root, log)

    def test_c_branch_name_empty(self, main_root, log):
        write_state(main_root, [entry(branch_name="")])
        assert not hook.evaluate(file_payload("Edit", main_root / "a.md", main_root), main_root, log)
        assert not hook.evaluate(bash_payload("git add a.md", main_root), main_root, log)

    def test_d_no_agent_id_pm(self, main_root, log):
        write_state(main_root, [entry()])
        assert not hook.evaluate(file_payload("Edit", main_root / "a.md", main_root, agent_id=None), main_root, log)
        assert not hook.evaluate(bash_payload("git add a.md", main_root, agent_id=None), main_root, log)

    def test_e_mapping_missing_allows_and_logs_info(self, main_root, log, caplog):
        write_state(main_root, [entry(agent_id="other")])
        with caplog.at_level(logging.INFO, logger="test-isolated-guard"):
            assert not hook.evaluate(file_payload("Write", main_root / "a.md", main_root), main_root, log)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_state_file_missing_fail_open_with_info(self, main_root, log, caplog):
        with caplog.at_level(logging.INFO, logger="test-isolated-guard"):
            assert not hook.evaluate(bash_payload("git add a.md", main_root), main_root, log)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_missing_file_path_or_cwd_fail_open(self, main_root, log):
        write_state(main_root, [entry()])
        p = {"agent_id": AGENT_ID, "tool_name": "Edit", "tool_input": {}}
        assert not hook.evaluate(p, main_root, log)
        p2 = {"agent_id": AGENT_ID, "tool_name": "Bash", "tool_input": {"command": "git add a"}}
        assert not hook.evaluate(p2, main_root, log)

    def test_non_write_git_and_ticket_cli_excluded(self, main_root, log):
        write_state(main_root, [entry()])
        for cmd in ("git status", "git log -1", "ticket track complete X --as a",
                    "ticket track append-log X --section s 'git add x'"):
            assert not hook.evaluate(bash_payload(cmd, main_root), main_root, log), cmd

    def test_state_read_error_fail_open(self, main_root, log):
        (main_root / ".claude" / "dispatch-active.json").write_text("{not json", encoding="utf-8")
        dispatch_tracker.reset_cache()
        assert not hook.evaluate(bash_payload("git add a", main_root), main_root, log)


class TestE1Contrast:
    """拿掉映射命中後，(a) 翻為放行：證明介入來自映射而非路徑本身"""

    def test_same_input_flips_without_mapping(self, main_root, log):
        p = file_payload("Edit", main_root / "docs" / "a.md", main_root)
        write_state(main_root, [entry()])
        with_mapping = hook.evaluate(p, main_root, log)
        write_state(main_root, [entry(agent_id="someone-else")])
        without_mapping = hook.evaluate(p, main_root, log)
        assert with_mapping and not without_mapping


class TestFailureSemantics:
    def test_hook_exception_fail_open_stderr_and_log(self, main_root, capsys):
        payload = bash_payload("git add a", main_root)
        with patch.object(hook, "read_json_from_stdin", return_value=payload), \
             patch.object(hook, "resolve_main_root", return_value=main_root), \
             patch.object(hook, "evaluate", side_effect=RuntimeError("boom")):
            rc = hook.main()
        cap = capsys.readouterr()
        assert rc == 0
        assert "boom" in cap.err
        assert cap.out.strip() == ""

    def _run_main(self, payload, main_root, capsys):
        with patch.object(hook, "read_json_from_stdin", return_value=payload), \
             patch.object(hook, "resolve_main_root", return_value=main_root):
            rc = hook.main()
        out = capsys.readouterr().out.strip()
        return rc, (json.loads(out) if out else None)

    @pytest.mark.parametrize("tool", ["Edit", "Write", "NotebookEdit"])
    def test_e2_file_tool_hit_emits_deny(self, tool, main_root, capsys):
        write_state(main_root, [entry()])
        rc, out = self._run_main(file_payload(tool, main_root / "a.md", main_root), main_root, capsys)
        spec = out["hookSpecificOutput"]
        assert rc == 0
        assert spec["hookEventName"] == "PreToolUse"
        assert spec["permissionDecision"] == "deny"
        assert "NeedsContext" in spec["permissionDecisionReason"]
        assert "PM" in spec["permissionDecisionReason"]

    def test_e2_bash_hit_stays_warn_only(self, main_root, capsys):
        write_state(main_root, [entry()])
        rc, out = self._run_main(bash_payload("git add a.md", main_root), main_root, capsys)
        spec = out["hookSpecificOutput"]
        assert rc == 0
        assert "permissionDecision" not in spec
        assert "NeedsContext" in spec["additionalContext"]

    def test_e1_file_tool_without_mapping_allows(self, main_root, capsys):
        write_state(main_root, [entry(agent_id="someone-else")])
        rc, out = self._run_main(file_payload("Edit", main_root / "a.md", main_root), main_root, capsys)
        assert rc == 0
        assert out is None


class TestResolveMainRoot:
    def test_strips_worktree_suffix(self):
        p = Path("/a/b/.claude/worktrees/agent-x")
        assert hook.main_root_from(p) == Path("/a/b")
        assert hook.main_root_from(Path("/a/b")) == Path("/a/b")
