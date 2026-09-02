"""ticket track dispatch 子命令測試。

驗收對應（0.2.1-W3-876.1）：
1. dispatch --note 可寫入派發日誌章節（帶時間戳，可重複追加）
2. --kind review 輸出審查骨架，不含認領/收尾
3. --kind normal 輸出含收尾協議
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.commands import track_dispatch as td_mod


def _write_ticket_md(path: Path, tid: str, where_files=None) -> None:
    where_yaml = ""
    if where_files:
        files_yaml = "\n".join(f"  - {f}" for f in where_files)
        where_yaml = f"where:\n  layer: Infrastructure\n  files:\n{files_yaml}\n"
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        f"{where_yaml}"
        "---\n\n"
    )
    body = (
        "# Execution Log\n\n"
        "## Task Summary\n\nTest task.\n\n"
        "---\n\n"
        "## Problem Analysis\n\n占位。\n\n"
        "---\n\n"
        "## Solution\n\n占位。\n\n"
        "---\n\n"
        "## Test Results\n\n占位。\n\n"
        "---\n\n"
        "## Completion Info\n\n占位。\n"
    )
    path.write_text(fm + body, encoding="utf-8")


def _make_dispatch_ticket(tmp_path: Path, monkeypatch, where_files=None) -> str:
    """建立可被 track_dispatch 讀寫的暫存 ticket，回傳 ticket_id。"""
    from ticket_system.lib.parser import parse_frontmatter, save_ticket as real_save

    tid = "0.0.0-W0-DISPATCH"
    md_path = tmp_path / f"{tid}.md"
    _write_ticket_md(md_path, tid, where_files=where_files)

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return md_path

    def _fake_load_ticket(version: str, ticket_id: str):
        fm, body = parse_frontmatter(md_path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(md_path)
        return fm

    def _fake_save_ticket(ticket, ticket_path):
        real_save(ticket, Path(ticket_path))

    monkeypatch.setattr(td_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(td_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(td_mod, "save_ticket", _fake_save_ticket)
    monkeypatch.setattr(td_mod, "resolve_ticket_path", lambda ticket, version, tid: md_path)

    return tid


@pytest.fixture
def dispatch_ticket(tmp_path: Path, monkeypatch) -> str:
    return _make_dispatch_ticket(tmp_path, monkeypatch)


@pytest.fixture
def dispatch_ticket_hook_scope(tmp_path: Path, monkeypatch) -> str:
    """where.files 觸及 `.claude/hooks/` 的 ticket。"""
    return _make_dispatch_ticket(
        tmp_path, monkeypatch, where_files=[".claude/hooks/example-guard-hook.py"]
    )


def _base_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        ticket_id="0.0.0-W0-DISPATCH",
        version="0.0.0",
        as_agent="thyme-python-developer",
        note=None,
        kind="normal",
        task_summary="測試任務",
        review_perspective=None,
        decision_question=None,
        commit_policy="agent",
        dry_run=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_dispatch_note_writes_to_dispatch_log_section(dispatch_ticket, tmp_path, capsys):
    args = _base_args(note="並行派發，commit policy = agent commit")
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 0

    md_path = tmp_path / f"{dispatch_ticket}.md"
    content = md_path.read_text(encoding="utf-8")
    assert f"### {td_mod.DISPATCH_LOG_SECTION}" in content
    assert f"## {td_mod.PARENT_SCHEMA_SECTION}" in content
    assert "並行派發，commit policy = agent commit" in content


def test_dispatch_note_appends_multiple_entries_with_timestamp(dispatch_ticket, tmp_path):
    args1 = _base_args(note="第一次備註")
    td_mod.execute_dispatch(args1, "0.0.0")
    args2 = _base_args(note="第二次備註")
    td_mod.execute_dispatch(args2, "0.0.0")

    md_path = tmp_path / f"{dispatch_ticket}.md"
    content = md_path.read_text(encoding="utf-8")
    assert "第一次備註" in content
    assert "第二次備註" in content
    # 帶時間戳格式 [YYYY-MM-DD HH:MM]
    import re
    assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]", content)


def test_dispatch_note_and_commit_section_coexist_as_h3_siblings(dispatch_ticket, tmp_path):
    """`### 派發日誌` 與 `### Commit 規範` 為同一 `## Problem Analysis` 下的
    H3 手足子節（骨架瘦身後新增後者）。多次 dispatch --note 交錯呼叫，
    兩節內容必須互不吞噬——回歸測試：`section_locator.find_section` 的
    levels=(3,) 只以下一個 H2 為界，若局部子節查詢誤沿用該語意，會讓查
    在前的子節把在後的手足子節內容一併吃入自己範圍，新增的 note entry
    因此附加在錯誤位置甚至被覆寫消失。
    """
    args1 = _base_args(note="第一則備註")
    td_mod.execute_dispatch(args1, "0.0.0")  # 預設 commit_policy=agent，一併寫入 Commit 規範

    md_path = tmp_path / f"{dispatch_ticket}.md"
    content_after_first = md_path.read_text(encoding="utf-8")
    assert f"### {td_mod.DISPATCH_LOG_SECTION}" in content_after_first
    assert f"### {td_mod.COMMIT_SECTION_HEADING}" in content_after_first
    assert "第一則備註" in content_after_first
    assert td_mod.STAGING_PHRASE_AGENT.splitlines()[0] in content_after_first

    args2 = _base_args(note="第二則備註")
    td_mod.execute_dispatch(args2, "0.0.0")

    content_after_second = md_path.read_text(encoding="utf-8")
    # 兩則 note entry 都必須存在（第一則不可被第二次呼叫覆寫或吞沒）。
    assert "第一則備註" in content_after_second
    assert "第二則備註" in content_after_second
    # Commit 規範全文須維持完整（不可因 note 附加操作而被截斷或搬移）。
    assert td_mod.STAGING_PHRASE_AGENT in content_after_second
    # 兩節仍各自成立、互不吞噬：派發日誌只含自己的 entry，不含 Commit 規範全文。
    dispatch_log_section = _find_h3_subsection_text(content_after_second, td_mod.DISPATCH_LOG_SECTION)
    assert "Recommended: commit via isolated index" not in dispatch_log_section


def _find_h3_subsection_text(content: str, heading: str) -> str:
    """測試輔助：擷取 markdown body 中 `### {heading}` 子節內容（至下一個
    `## `/`### ` 標題或檔案結尾），用於斷言子節互不吞噬。"""
    import re

    match = re.search(rf"^###\s+{re.escape(heading)}\s*$", content, re.MULTILINE)
    assert match, f"未找到子節 ### {heading}"
    start = match.end()
    boundary = re.search(r"\n#{2,3} ", content[start:])
    end = start + boundary.start() if boundary else len(content)
    return content[start:end]


def test_dispatch_note_creates_problem_analysis_when_missing(tmp_path, monkeypatch):
    """Problem Analysis 章節不存在時，dispatch --note 不可靜默丟 note，
    必須建立該 H2 並內含 ### 派發日誌 子節。"""
    from ticket_system.lib.parser import parse_frontmatter, save_ticket as real_save

    tid = "0.0.0-W0-NOPA"
    md_path = tmp_path / f"{tid}.md"
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
    )
    body = "# Execution Log\n\n## Task Summary\n\nTest task.\n\n---\n\n## Solution\n\n占位。\n"
    md_path.write_text(fm + body, encoding="utf-8")

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return md_path

    def _fake_load_ticket(version: str, ticket_id: str):
        fm2, body2 = parse_frontmatter(md_path.read_text(encoding="utf-8"))
        if not fm2:
            return None
        fm2["_body"] = body2
        fm2["_path"] = str(md_path)
        return fm2

    def _fake_save_ticket(ticket, ticket_path):
        real_save(ticket, Path(ticket_path))

    monkeypatch.setattr(td_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(td_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(td_mod, "save_ticket", _fake_save_ticket)
    monkeypatch.setattr(td_mod, "resolve_ticket_path", lambda ticket, version, tid_: md_path)

    args = _base_args(ticket_id=tid, note="無 Problem Analysis 章節時的備註")
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 0
    content = md_path.read_text(encoding="utf-8")
    assert f"## {td_mod.PARENT_SCHEMA_SECTION}" in content
    assert f"### {td_mod.DISPATCH_LOG_SECTION}" in content
    assert "無 Problem Analysis 章節時的備註" in content


def test_dispatch_kind_review_excludes_claim_and_completion(dispatch_ticket, capsys):
    args = _base_args(
        kind="review",
        review_perspective="架構一致性",
        decision_question="是否符合單一權威決策？",
    )
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert "ticket track claim" not in out
    assert "ticket track complete" not in out
    assert "審查視角" in out or "架構一致性" in out
    assert "架構一致性" in out
    assert "是否符合單一權威決策？" in out


def test_dispatch_kind_normal_includes_completion_protocol(dispatch_ticket, capsys):
    args = _base_args(kind="normal")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert "ticket track claim" in out
    assert "ticket track complete" in out
    assert "ticket track set-acceptance" in out


# --- --dry-run（0.2.1-W4-022） ------------------------------------------


def test_dispatch_dry_run_does_not_write_ticket_file(dispatch_ticket, tmp_path):
    """--dry-run 時即使帶 --note 且 commit_policy=agent（預設會觸發兩種
    寫入副作用），票面檔內容與 mtime 都必須維持不變（不落盤、不冪等寫入
    Commit 規範子節）。"""
    md_path = tmp_path / f"{dispatch_ticket}.md"
    content_before = md_path.read_text(encoding="utf-8")
    mtime_before = md_path.stat().st_mtime_ns

    args = _base_args(note="dry-run 不應落票", dry_run=True)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 0
    content_after = md_path.read_text(encoding="utf-8")
    mtime_after = md_path.stat().st_mtime_ns
    assert content_after == content_before
    assert mtime_after == mtime_before
    assert f"### {td_mod.DISPATCH_LOG_SECTION}" not in content_after
    assert f"### {td_mod.COMMIT_SECTION_HEADING}" not in content_after


def test_dispatch_dry_run_outputs_same_skeleton_as_normal(dispatch_ticket, capsys):
    """--dry-run 的骨架輸出與非 dry-run 完全相同（差異僅在票面副作用）。"""
    args_normal = _base_args(dry_run=False)
    rc_normal = td_mod.execute_dispatch(args_normal, "0.0.0")
    assert rc_normal == 0
    out_normal = capsys.readouterr().out

    args_dry_run = _base_args(dry_run=True)
    rc_dry_run = td_mod.execute_dispatch(args_dry_run, "0.0.0")
    assert rc_dry_run == 0
    out_dry_run = capsys.readouterr().out

    assert out_dry_run == out_normal


def test_dispatch_dry_run_missing_ticket_returns_error(tmp_path, monkeypatch, capsys):
    """--dry-run 仍須確認票存在，不可對不存在的票輸出骨架。"""
    monkeypatch.setattr(td_mod, "get_ticket_path", lambda version, tid: tmp_path / f"{tid}.md")
    monkeypatch.setattr(td_mod, "load_ticket", lambda version, tid: None)

    args = _base_args(ticket_id="0.0.0-W0-NOPE", dry_run=True)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 1


def test_dispatch_missing_ticket_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(td_mod, "get_ticket_path", lambda version, tid: tmp_path / f"{tid}.md")
    monkeypatch.setattr(td_mod, "load_ticket", lambda version, tid: None)

    args = _base_args(ticket_id="0.0.0-W0-NOPE", note=None)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 1


# --- 目錄級 where.files 宣告硬擋（0.2.1-W3-891 / PC-BAL-040） -----------


def test_dispatch_blocks_directory_declaration_without_read(tmp_path, monkeypatch, capsys):
    tid = _make_dispatch_ticket(tmp_path, monkeypatch, where_files=[".claude/hooks/"])
    monkeypatch.setattr("ticket_system.lib.ticket_loader.list_tickets", lambda version: [])

    args = _base_args(ticket_id=tid)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 1
    out = capsys.readouterr().out
    assert "[BLOCKED]" in out
    assert ".claude/hooks/" in out
    assert "ticket track claim" not in out  # 骨架未輸出


def test_dispatch_allows_directory_declaration_with_read_marker(tmp_path, monkeypatch, capsys):
    tid = _make_dispatch_ticket(tmp_path, monkeypatch, where_files=[".claude/hooks/::read"])
    monkeypatch.setattr("ticket_system.lib.ticket_loader.list_tickets", lambda version: [])

    args = _base_args(ticket_id=tid)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "[BLOCKED]" not in out
    assert "ticket track claim" in out


def test_dispatch_lists_affected_active_tickets_for_directory_declaration(tmp_path, monkeypatch, capsys):
    tid = _make_dispatch_ticket(tmp_path, monkeypatch, where_files=[".claude/hooks/"])
    other_ticket = {
        "id": "0.0.0-W0-OTHER",
        "status": "in_progress",
        "type": "IMP",
        "where": {"files": [".claude/hooks/example-guard-hook.py"]},
    }
    monkeypatch.setattr(
        "ticket_system.lib.ticket_loader.list_tickets", lambda version: [other_ticket]
    )

    args = _base_args(ticket_id=tid)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 1
    out = capsys.readouterr().out
    assert "0.0.0-W0-OTHER" in out


# --- --commit-policy（0.2.1-W3-879） ------------------------------------

def _load_missing_categories():
    """Lazy import dispatch-staging-phrase-guard-hook._missing_categories
    （檔名含連字號不可 import，沿用 hooks/tests 既有慣例動態載入）。"""
    import importlib.util
    from pathlib import Path as _Path

    hooks_dir = _Path(__file__).resolve().parents[4] / "hooks"
    spec = importlib.util.spec_from_file_location(
        "dispatch_staging_phrase_guard_hook",
        hooks_dir / "dispatch-staging-phrase-guard-hook.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._missing_categories


def test_dispatch_commit_policy_agent_satisfies_all_staging_categories(dispatch_ticket, capsys):
    args = _base_args(commit_policy="agent")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    missing_categories = _load_missing_categories()
    assert missing_categories(out.lower()) == []


def test_dispatch_commit_policy_pm_outputs_one_liner(dispatch_ticket, capsys):
    args = _base_args(commit_policy="pm")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert td_mod.STAGING_PHRASE_PM in out
    assert "git add {exact files}" not in out


def test_dispatch_commit_policy_none_outputs_one_liner(dispatch_ticket, capsys):
    args = _base_args(commit_policy="none")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert td_mod.STAGING_PHRASE_NONE in out
    assert "git add {exact files}" not in out


def test_dispatch_commit_policy_default_is_agent(dispatch_ticket, capsys):
    args = _base_args()
    del args.commit_policy  # 模擬未傳入 --commit-policy 時 argparse default 生效前的情境
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    missing_categories = _load_missing_categories()
    assert missing_categories(out.lower()) == []


# --- hook 票四項必含提醒（0.2.1-W3-879） --------------------------------

def test_dispatch_hook_ticket_appends_four_item_reminder(dispatch_ticket_hook_scope, capsys):
    args = _base_args(ticket_id=dispatch_ticket_hook_scope)
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert "本 session 實地觸發確認" in out
    assert "liveness 驗證方式" in out
    assert "fail-open" in out and "fail-closed" in out
    assert "產生路徑盤點表" in out


def test_dispatch_non_hook_ticket_omits_four_item_reminder(dispatch_ticket, capsys):
    args = _base_args(ticket_id=dispatch_ticket)
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert "liveness 驗證方式" not in out
