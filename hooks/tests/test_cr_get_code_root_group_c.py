#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3.3.0-W1-204.1.4.4：C 組六支 hook 的 CR 取用點改用 get_code_root。

情境 C：get_project_root 回 WT（cwd 所在 checkout），get_code_root 回 MAIN
（載入中的 .claude）。兩份 .claude 內容不同，CR 讀取必須落在 MAIN。
舊碼（呼叫 get_project_root 取 CR）會落在 WT，這些測試即為紅燈。
"""

import importlib.util
import json
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HOOKS = REPO / ".claude" / "hooks"
SKILLS = REPO / ".claude" / "skills"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def roots(tmp_path, monkeypatch):
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    main, wt = tmp_path / "MAIN", tmp_path / "WT"
    for r in (main, wt):
        (r / ".claude" / "agents").mkdir(parents=True)
        (r / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    return main, wt


def _patch_roots(mod, monkeypatch, main, wt):
    monkeypatch.setattr(mod, "get_project_root", lambda: wt, raising=False)
    monkeypatch.setattr(mod, "get_code_root", lambda: main, raising=False)


def test_post_test_orphan_script_from_code_root(roots, monkeypatch, tmp_path):
    main, wt = roots
    mod = _load("ptt_c", HOOKS / "post-test-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    mon = tmp_path / "mon.json"
    mon.write_text(json.dumps({"status": "running", "start_timestamp": time.time() - 5}))
    monkeypatch.setattr(mod, "legacy_monitor_file", lambda _d: mon)
    monkeypatch.setattr(mod, "get_hook_log_dir", lambda _n="": tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    seen = []
    monkeypatch.setattr(mod, "_classify_duration",
                        lambda d, p: (seen.append(p) or ("normal", "ok")))
    import logging
    mod.check_test_timeout({}, {}, logging.getLogger("t"))
    assert seen == [main]


def test_file_size_guardian_scans_code_root(roots, monkeypatch):
    main, wt = roots
    mod = _load("fsg_c", HOOKS / "file-size-guardian-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    seen = []
    monkeypatch.setattr(mod, "setup_hook_logging", lambda _n: None)
    monkeypatch.setattr(mod, "_report_oversized_files", lambda r: seen.append(r))
    monkeypatch.setattr(mod, "report_auto_load_budget", lambda r, _l: seen.append(r))
    mod.main()
    assert seen == [main, main]


def test_agent_dispatch_agent_md_from_code_root(roots, monkeypatch):
    main, wt = roots
    mod = _load("adv_c", SKILLS / "ticket" / "hooks" / "agent-dispatch-validation-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    assert mod._agent_md_path("x-agent") == main / ".claude" / "agents" / "x-agent.md"


def test_ana_metadata_reads_claude_md_from_code_root(roots, monkeypatch):
    main, wt = roots
    mod = _load("ana_c", SKILLS / "ticket" / "hooks" / "ana-ticket-metadata-validation-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    seen = []

    class _Stop(Exception):
        pass

    def spy(root, _logger):
        seen.append(root)
        raise _Stop

    monkeypatch.setattr(mod, "read_json_from_stdin", lambda _l: {
        "tool_input": {"file_path": "/x/1.md", "content": "---\nid: a\n---\n"}})
    monkeypatch.setattr(mod, "is_ticket_file", lambda _p: True)
    monkeypatch.setattr(mod, "parse_frontmatter", lambda _c, _l: {"id": "a"})
    monkeypatch.setattr(mod, "is_ana_created_ticket", lambda _f: True)
    monkeypatch.setattr(mod, "get_project_implementation_agent", spy)
    with pytest.raises(_Stop):
        mod.main()
    assert seen == [main]


def test_wrap_tripwire_config_from_code_root(roots, monkeypatch):
    main, wt = roots
    mod = _load("wrap_c", SKILLS / "wrap-decision" / "hooks" / "wrap-decision-tripwire-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    seen = []
    monkeypatch.setattr(mod, "read_json_from_stdin", lambda _l: {})
    monkeypatch.setattr(mod, "is_pytest_environment", lambda: False)
    monkeypatch.setattr(mod, "get_effort_level", lambda _e: "high")
    monkeypatch.setattr(mod, "load_config", lambda p, _l: (seen.append(p) or None))
    mod.main()
    assert seen == [main / mod.CONFIG_REL_PATH]


def test_comment_qa_config_and_parser_from_code_root(roots, monkeypatch, tmp_path):
    main, wt = roots
    import lib
    monkeypatch.setattr(lib, "get_project_root", lambda: wt)
    monkeypatch.setattr(lib, "get_code_root", lambda: main)
    monkeypatch.setattr(lib, "get_hook_log_dir", lambda _n="": tmp_path / "qa-logs")
    mod = _load("cqa_c", SKILLS / "dart-comment-traceability" / "hooks" / "comment-qa-hook.py")
    assert mod.PROJECT_ROOT == wt
    assert mod.CODE_ROOT == main


# --- agent-dispatch-validation 放行／阻擋變化表（情境 C，輸入實測）---

_AGENT_WITH_KW = "## 禁止行為\n\n1. **禁止 git commit**：不得自行 commit\n"
_AGENT_NO_KW = "## 禁止行為\n\n1. **禁止實作程式碼**：不得撰寫實作\n"
_PROMPT = "完成後 git commit -m 'done'"


def _verdicts(monkeypatch, main, wt, main_md, wt_md):
    """同一組輸入，回傳 (舊碼, 新碼) 判決；舊碼 = 以 get_project_root 取 agents/*.md。"""
    import logging
    mod = _load("adv_tbl", SKILLS / "ticket" / "hooks" / "agent-dispatch-validation-hook.py")
    _patch_roots(mod, monkeypatch, main, wt)
    monkeypatch.delenv(mod._BYPASS_ENV_VAR, raising=False)
    for root, body in ((main, main_md), (wt, wt_md)):
        agent = root / ".claude" / "agents" / "x-agent.md"
        agent.unlink(missing_ok=True)
        if body is not None:
            agent.write_text(body, encoding="utf-8")
    log = logging.getLogger("t")
    new_path = mod._agent_md_path
    new = mod._emit_keyword_conflict_warning_if_any("x-agent", _PROMPT, log)
    monkeypatch.setattr(mod, "_agent_md_path",
                        lambda st: wt / ".claude" / "agents" / f"{st}.md")
    old = mod._emit_keyword_conflict_warning_if_any("x-agent", _PROMPT, log)
    monkeypatch.setattr(mod, "_agent_md_path", new_path)
    return old, new


def test_dispatch_table_main_only_agent_tightens(roots, monkeypatch):
    main, wt = roots
    assert _verdicts(monkeypatch, main, wt, _AGENT_WITH_KW, None) == ("pass", "block")


def test_dispatch_table_wt_only_agent_loosens(roots, monkeypatch):
    main, wt = roots
    assert _verdicts(monkeypatch, main, wt, None, _AGENT_WITH_KW) == ("block", "pass")


def test_dispatch_table_differing_content_follows_main(roots, monkeypatch):
    main, wt = roots
    assert _verdicts(monkeypatch, main, wt, _AGENT_WITH_KW, _AGENT_NO_KW) == ("pass", "block")
    # 反向內容：MAIN 無關鍵字、WT 有 -> 新碼放行（放寬）
    assert _verdicts(monkeypatch, main, wt, _AGENT_NO_KW, _AGENT_WITH_KW) == ("block", "pass")
