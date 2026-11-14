#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis-before-edit-checkpoint-hook 測試

覆蓋：
- E2 正向對照：子代理人（agent_id 映射命中）在章節仍為 placeholder 時寫產品檔 -> deny
- E1 對照：同一寫入在章節已填時放行（placeholder vs 已填，產物不同）
- 形態 T（IMP 且 acceptance 含測試字樣）讀 Test Results；形態 P 讀 Problem Analysis
- 無 agent_id：where.files 唯一命中 -> additionalContext 提醒；零張／多張 -> 放行並記 info
- 測試檔、票面、docs/、專案根外路徑一律放行
- 失敗語意：hook 例外 -> 放行並寫 stderr
"""

import importlib.util
import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import dispatch_tracker

HOOK_FILE = Path(__file__).parent.parent / "analysis-before-edit-checkpoint-hook.py"
_spec = importlib.util.spec_from_file_location("analysis_before_edit_checkpoint_hook", HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

AGENT_ID = "a1b2c3d4e5f60718"
TICKET_ID = "9.9.0-W1-001"
OTHER_ID = "9.9.0-W1-002"

PA_PLACEHOLDER = "### 問題根因\n\n（選填：問題如何發現？直接原因是什麼？）\n"
# 照抄現行 `ticket create --dedup-checked none` 產出的 Problem Analysis 結構：
# 範本 H3 只有 HTML 註解，另有 CLI 自動寫入的「### 查重紀錄」子節（人未填任何分析）
PA_CREATE_WITH_DEDUP = (
    "### 問題根因\n\n<!-- 必填：問題發生的直接原因是什麼？影響範圍有多大？ -->\n\n"
    "### 影響範圍\n\n<!-- 必填：哪些檔案、模組或功能受影響？ -->\n\n"
    "### 相關 Error Pattern\n\n<!-- 必填：是否有相關的已知錯誤模式？ -->\n\n"
    "### 查重紀錄\n\n`--dedup-checked none`，查重關鍵字（逐字）：\n\n- `analysis 效能`\n\n"
    "dedup 命中 issue（請覆核關係：重複／切分／引用）：\n\n"
    "- #31 doc test-map 掃描範圍寫死\n- #33 ticket body 模板 placeholder 殘留\n\n"
    "<!-- 調查過程記錄（可選）：\n搜尋指令：grep\n-->\n"
)
PA_DISPATCH_LOG_ONLY = (
    "### 問題根因\n\n（選填：問題如何發現？直接原因是什麼？）\n\n"
    "### 派發日誌\n\n- 2026-11-13 09:00 派發 thyme-python-developer\n\n"
    "### Commit 規範\n\n- 提交訊息以票號開頭\n"
)
PA_FILLED_WITH_DEDUP = PA_CREATE_WITH_DEDUP.replace(
    "<!-- 必填：問題發生的直接原因是什麼？影響範圍有多大？ -->",
    "讀票確認：寫入點在 foo.py 的 bar()。",
)
PA_FILLED = "### 問題根因\n\n讀票確認：寫入點在 foo.py 的 bar()。\n"
TR_PLACEHOLDER = "（必填：測試執行指令、通過數/失敗數或 commit SHA）\n"
TR_FILLED = "紅燈：pytest tests/test_foo.py -> 1 failed（新測試）\n"


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "proj"
    (r / ".claude").mkdir(parents=True)
    (r / "docs" / "work-logs" / "v9" / "v9.9" / "v9.9.0" / "tickets").mkdir(parents=True)
    dispatch_tracker.reset_cache()
    return r


@pytest.fixture
def log():
    logger = logging.getLogger("test-analysis-before-edit")
    logger.setLevel(logging.DEBUG)
    return logger


def write_ticket(root, ticket_id=TICKET_ID, *, ticket_type="IMP", acceptance=None,
                 where=("src/foo.py",), status="in_progress", pa=PA_PLACEHOLDER, tr=TR_PLACEHOLDER):
    acceptance = acceptance if acceptance is not None else ["[ ] 行為正確"]
    acc = "\n".join("- '%s'" % a for a in acceptance)
    files = "\n".join("  - %s" % w for w in where)
    text = (
        "---\n"
        "id: %s\ntype: %s\nstatus: %s\n"
        "where:\n  layer: x\n  files:\n%s\n"
        "acceptance:\n%s\n"
        "---\n\n# Execution Log\n\n"
        "## Problem Analysis\n<!-- Schema -->\n\n%s\n---\n\n"
        "## Solution\n\n（選填：修復方式概述）\n\n---\n\n"
        "## Test Results\n<!-- Schema -->\n\n%s\n---\n"
    ) % (ticket_id, ticket_type, status, files, acc, pa, tr)
    path = root / "docs" / "work-logs" / "v9" / "v9.9" / "v9.9.0" / "tickets" / ("%s.md" % ticket_id)
    path.write_text(text, encoding="utf-8")
    return path


def map_agent(root, ticket_id=TICKET_ID, agent_id=AGENT_ID):
    entry = {
        "agent_description": "d",
        "agent_id": agent_id,
        "agent_handle": "",
        "branch_name": "",
        "ticket_id": ticket_id,
        "turn_ended_at": None,
    }
    (root / ".claude" / "dispatch-active.json").write_text(
        json.dumps({"dispatches": [entry]}), encoding="utf-8"
    )
    dispatch_tracker.reset_cache()


def payload(root, rel_path, *, agent_id=AGENT_ID, tool="Edit"):
    p = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(root / rel_path)},
        "cwd": str(root),
    }
    if agent_id is not None:
        p["agent_id"] = agent_id
    return p


# --- 子代理人：E2 正向對照與 E1 對照 ---

def test_subagent_placeholder_problem_analysis_denied(root, log):
    write_ticket(root)
    map_agent(root)
    decision, message = hook.evaluate(payload(root, "src/foo.py"), root, log)
    assert decision == "deny"
    assert "Problem Analysis" in message
    assert "ticket track append-log %s" % TICKET_ID in message


def test_subagent_filled_problem_analysis_allowed(root, log):
    write_ticket(root, pa=PA_FILLED)
    map_agent(root)
    assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)


def test_form_t_reads_test_results(root, log):
    write_ticket(root, acceptance=["[ ] 新增測試覆蓋 bar()"], pa=PA_FILLED)
    map_agent(root)
    decision, message = hook.evaluate(payload(root, "src/foo.py"), root, log)
    assert decision == "deny"
    assert "Test Results" in message
    assert "紅燈" in message


def test_form_t_filled_test_results_allowed(root, log):
    write_ticket(root, acceptance=["[ ] 新增測試覆蓋 bar()"], tr=TR_FILLED)
    map_agent(root)
    assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)


def test_form_t_uses_requires_red_run(root, log):
    write_ticket(root, acceptance=["[ ] 新增測試覆蓋 bar()"], pa=PA_FILLED)
    map_agent(root)
    with patch.object(hook, "requires_red_run", return_value=False) as spy:
        assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)
    spy.assert_called_once()


def test_create_generated_dedup_subsection_does_not_count_as_filled(root, log):
    """E2 正向對照：現行 create 產出的票（有查重紀錄、分析未填）須 deny"""
    write_ticket(root, pa=PA_CREATE_WITH_DEDUP)
    map_agent(root)
    decision, message = hook.evaluate(payload(root, "src/foo.py"), root, log)
    assert decision == "deny"
    assert "Problem Analysis" in message


def test_dispatch_managed_subsections_do_not_count_as_filled(root, log):
    write_ticket(root, pa=PA_DISPATCH_LOG_ONLY)
    map_agent(root)
    decision, _ = hook.evaluate(payload(root, "src/foo.py"), root, log)
    assert decision == "deny"


def test_human_analysis_alongside_dedup_allowed(root, log):
    """E1 對照：同一結構補上人寫分析後放行"""
    write_ticket(root, pa=PA_FILLED_WITH_DEDUP)
    map_agent(root)
    assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)


@pytest.mark.parametrize("ticket_type", ["DOC", "ANA"])
def test_non_imp_allowed_with_info(root, log, caplog, ticket_type):
    write_ticket(root, ticket_type=ticket_type, pa=PA_CREATE_WITH_DEDUP)
    map_agent(root)
    with caplog.at_level(logging.INFO, logger=log.name):
        assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)
    assert "非 IMP" in caplog.text


def test_non_imp_no_agent_not_reminded(root, log):
    write_ticket(root, ticket_type="DOC", pa=PA_CREATE_WITH_DEDUP)
    assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)


def test_subagent_unmapped_allowed_with_info(root, log, caplog):
    write_ticket(root)
    map_agent(root, agent_id="azzzz")
    with caplog.at_level(logging.INFO, logger=log.name):
        assert hook.evaluate(payload(root, "src/foo.py", agent_id="a0"), root, log) == (None, None)
    assert "無映射" in caplog.text


def test_subagent_mapped_ticket_missing_allowed(root, log, caplog):
    map_agent(root, ticket_id="9.9.0-W1-404")
    with caplog.at_level(logging.INFO, logger=log.name):
        assert hook.evaluate(payload(root, "src/foo.py"), root, log) == (None, None)
    assert "找不到票面" in caplog.text


# --- 排除路徑 ---

@pytest.mark.parametrize("rel", [
    "tests/test_foo.py",
    "src/foo_test.go",
    ".claude/hooks/tests/test_x.py",
    "docs/notes.md",
    "docs/work-logs/v9/v9.9/v9.9.0/tickets/9.9.0-W1-001.md",
])
def test_excluded_paths_allowed(root, log, rel):
    write_ticket(root)
    map_agent(root)
    assert hook.evaluate(payload(root, rel), root, log) == (None, None)


@pytest.mark.parametrize("path", [
    "/private/tmp/claude-501/proj/session/scratchpad/x.py",
    "/tmp/x/y.py",
])
def test_scratchpad_and_tmp_allowed(root, log, path):
    write_ticket(root)
    map_agent(root)
    p = payload(root, "src/foo.py")
    p["tool_input"]["file_path"] = path
    assert hook.evaluate(p, root, log) == (None, None)


def test_sibling_worktree_product_file_still_checked(root, log, tmp_path):
    # 本框架的 worktree 建在主 repo 旁（非其子目錄），子代理人在 worktree 寫產品檔仍須檢查
    write_ticket(root)
    map_agent(root)
    p = payload(root, "src/foo.py")
    p["tool_input"]["file_path"] = str(tmp_path / "proj-9.9.0-W1-001" / "src" / "foo.py")
    decision, _ = hook.evaluate(p, root, log)
    assert decision == "deny"


def test_no_agent_sibling_worktree_matches_where_files(root, log, tmp_path):
    write_ticket(root)
    p = payload(root, "src/foo.py", agent_id=None)
    p["tool_input"]["file_path"] = str(tmp_path / "proj-9.9.0-W1-001" / "src" / "foo.py")
    decision, _ = hook.evaluate(p, root, log)
    assert decision == "remind"


# --- 無 agent_id：where.files 推測 ---

def test_no_agent_unique_match_reminds(root, log):
    write_ticket(root)
    decision, message = hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log)
    assert decision == "remind"
    assert TICKET_ID in message


@pytest.mark.parametrize("where_entry", [".claude/hooks/x.py", "./.claude/hooks/x.py"])
def test_no_agent_dot_prefixed_where_files_matched(root, log, where_entry):
    # 正向對照：where.files 以 "." 開頭的框架路徑也要命中（舊碼 lstrip 剝掉開頭的點而永不命中）
    write_ticket(root, where=(where_entry,))
    decision, message = hook.evaluate(payload(root, ".claude/hooks/x.py", agent_id=None), root, log)
    assert decision == "remind"
    assert TICKET_ID in message


def test_no_agent_unique_match_filled_allowed(root, log):
    write_ticket(root, pa=PA_FILLED)
    assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)


def test_no_agent_zero_match_allowed_with_info(root, log, caplog):
    write_ticket(root, where=("src/other.py",))
    with caplog.at_level(logging.INFO, logger=log.name):
        assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)
    assert "命中 0 張" in caplog.text


def test_no_agent_multiple_match_allowed_with_info(root, log, caplog):
    write_ticket(root)
    write_ticket(root, OTHER_ID)
    with caplog.at_level(logging.INFO, logger=log.name):
        assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)
    assert "命中 2 張" in caplog.text


def test_no_agent_ignores_non_in_progress(root, log):
    write_ticket(root, status="pending")
    assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)


def test_no_agent_read_intent_not_matched(root, log):
    write_ticket(root, where=("src/foo.py::read",))
    assert hook.evaluate(payload(root, "src/foo.py", agent_id=None), root, log) == (None, None)


# --- main：輸出管道與失敗語意 ---

def _run_main(p, root):
    out = io.StringIO()
    err = io.StringIO()
    with patch.object(hook, "get_project_root", return_value=root), \
            patch("sys.stdin", io.StringIO(json.dumps(p))), \
            patch("sys.stdout", out), patch("sys.stderr", err):
        rc = hook.main()
    return rc, out.getvalue(), err.getvalue()


def test_main_emits_deny(root):
    write_ticket(root)
    map_agent(root)
    rc, out, _ = _run_main(payload(root, "src/foo.py"), root)
    assert rc == 0
    data = json.loads(out)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_emits_additional_context_for_remind(root):
    write_ticket(root)
    rc, out, _ = _run_main(payload(root, "src/foo.py", agent_id=None), root)
    assert rc == 0
    data = json.loads(out)
    assert "permissionDecision" not in data["hookSpecificOutput"]
    assert TICKET_ID in data["hookSpecificOutput"]["additionalContext"]


def test_main_pass_outputs_nothing(root):
    write_ticket(root, pa=PA_FILLED)
    map_agent(root)
    rc, out, _ = _run_main(payload(root, "src/foo.py"), root)
    assert rc == 0
    assert out == ""


def test_main_exception_fails_open_with_stderr(root):
    with patch.object(hook, "evaluate", side_effect=RuntimeError("boom")):
        rc, out, err = _run_main(payload(root, "src/foo.py"), root)
    assert rc == 0
    assert out == ""
    assert "boom" in err
