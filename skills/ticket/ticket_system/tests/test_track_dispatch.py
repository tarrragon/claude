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
from ticket_system.commands import track_dispatch_validate as tdv_mod
from ticket_system.lib.dispatch_skeleton import HOOK_TICKET_REMINDER


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


def test_dispatch_dry_run_prepends_watermark_first_line(dispatch_ticket, monkeypatch, capsys):
    """--dry-run 輸出首行含浮水印（3-F M-7），其餘骨架文字與非 dry-run
    逐字相同（正式骨架不變，差異僅在首行前綴）。"""
    monkeypatch.setattr(td_mod, "execute_dispatch_readiness", lambda a, v: 0)
    monkeypatch.setattr(td_mod, "execute_dispatch_validate", lambda a, v: 0)

    args_normal = _base_args(dry_run=False)
    rc_normal = td_mod.execute_dispatch(args_normal, "0.0.0")
    assert rc_normal == 0
    out_normal = capsys.readouterr().out

    args_dry_run = _base_args(dry_run=True)
    rc_dry_run = td_mod.execute_dispatch(args_dry_run, "0.0.0")
    assert rc_dry_run == 0
    out_dry_run = capsys.readouterr().out

    assert out_dry_run.startswith(f"{td_mod.DRY_RUN_WATERMARK}\n")
    assert out_dry_run[len(td_mod.DRY_RUN_WATERMARK) + 1:] == out_normal


def test_dispatch_dry_run_does_not_invoke_precheck(dispatch_ticket, monkeypatch):
    """--dry-run 不落盤，連帶不應呼叫派發前檢查（僅唯讀確認票存在）。"""
    calls = []
    monkeypatch.setattr(
        td_mod, "execute_dispatch_readiness",
        lambda a, v: calls.append("readiness") or 0,
    )
    monkeypatch.setattr(
        td_mod, "execute_dispatch_validate",
        lambda a, v: calls.append("validate") or 0,
    )

    args = _base_args(dry_run=True)
    rc = td_mod.execute_dispatch(args, "0.0.0")

    assert rc == 0
    assert calls == []


# --- 派發前檢查 exit code 落派發日誌（3-F M-5） -------------------------


def test_dispatch_records_readiness_and_validate_exit_codes(dispatch_ticket, tmp_path, monkeypatch):
    """非 dry-run 落票時，即使無 --note，派發日誌仍含 readiness／validate
    兩項 exit code（使〈派發前檢查順序〉留下痕跡，不需 PM 另跑）。"""
    monkeypatch.setattr(td_mod, "execute_dispatch_readiness", lambda a, v: 0)
    monkeypatch.setattr(td_mod, "execute_dispatch_validate", lambda a, v: 1)

    args = _base_args(note=None, commit_policy="none")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    md_path = tmp_path / f"{dispatch_ticket}.md"
    content = md_path.read_text(encoding="utf-8")
    assert f"### {td_mod.DISPATCH_LOG_SECTION}" in content
    assert "readiness=0" in content
    assert "validate=1" in content


def test_dispatch_precheck_codes_coexist_with_note(dispatch_ticket, tmp_path, monkeypatch):
    """帶 --note 時，precheck exit code 附加於同一則派發日誌 entry，
    原 note 文字不被覆蓋或截斷。"""
    monkeypatch.setattr(td_mod, "execute_dispatch_readiness", lambda a, v: 2)
    monkeypatch.setattr(td_mod, "execute_dispatch_validate", lambda a, v: 0)

    args = _base_args(note="自訂備註")
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    md_path = tmp_path / f"{dispatch_ticket}.md"
    content = md_path.read_text(encoding="utf-8")
    assert "自訂備註" in content
    assert "readiness=2" in content
    assert "validate=0" in content


def test_dispatch_precheck_diagnostic_output_muted(dispatch_ticket, capsys, monkeypatch):
    """內部呼叫 readiness／validate 的診斷輸出須靜音，不污染骨架 stdout。"""
    def _readiness(a, v):
        print("readiness diagnostic noise")
        return 0

    def _validate(a, v):
        print("validate diagnostic noise")
        return 0

    monkeypatch.setattr(td_mod, "execute_dispatch_readiness", _readiness)
    monkeypatch.setattr(td_mod, "execute_dispatch_validate", _validate)

    args = _base_args()
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert "readiness diagnostic noise" not in out
    assert "validate diagnostic noise" not in out
    assert "ticket track claim" in out


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
    # 比對提醒常數的每個條目行，而非硬寫整段字面
    entries = [ln.strip() for ln in HOOK_TICKET_REMINDER.splitlines() if ln.strip()]
    assert len(entries) >= 2
    assert all(entry in out for entry in entries)


def test_dispatch_non_hook_ticket_omits_four_item_reminder(dispatch_ticket, capsys):
    args = _base_args(ticket_id=dispatch_ticket)
    rc = td_mod.execute_dispatch(args, "0.0.0")
    assert rc == 0

    out = capsys.readouterr().out
    assert HOOK_TICKET_REMINDER.splitlines()[0].strip() not in out


# --- dispatch-validate 規則 4b 樣板偵測（0.1.0-W3-087） -----------------
#
# 規則 4 只數 acceptance 條數、不檢查內容是否為未填的建立端樣板，未給
# --acceptance（或以 --force 建立）產生的預設樣板恰好三條因此恆通過。


def test_check_acceptance_placeholder_blocks_unfilled_doc_template():
    """DOC 型未填樣板三條（其中僅第一條帶大括號）全部被判為未填，規則 4b FAIL。"""
    acceptance = [
        "[ ] 文件內容完整：包含標題、背景、正文、結論、附錄等 {N} 部分",
        "[ ] 格式符合規範：遵守 CLAUDE.md 的文件格式規則",
        "[ ] 內容無遺漏：所有預期的小節都已填寫（無 TODO 或空白區段）",
    ]

    ok, msg = tdv_mod.check_acceptance_placeholder(acceptance)

    assert ok is False
    assert "3 項未填樣板" in msg


def test_check_acceptance_placeholder_passes_filled_content():
    """已填的真實驗收條件（非建立端樣板、不含佔位符 token）通過規則 4b。"""
    acceptance = [
        "[ ] gap_report_screen 的空狀態改用共用 EmptyStateWidget",
        "[ ] flutter test 全數通過（含新增的空狀態 widget test）",
        "[ ] dart analyze 0 issues",
    ]

    ok, msg = tdv_mod.check_acceptance_placeholder(acceptance)

    assert ok is True


def test_check_acceptance_placeholder_does_not_block_normal_curly_content():
    """含大括號但非佔位符 token 樣式（如描述設定片段）的正常內容不誤擋。"""
    acceptance = [
        "[ ] 設定檔採用 {mode: production} 格式時仍可正確解析",
        "[ ] 相關測試 100% 通過（uv run pytest）",
        "[ ] ruff check 0 issues",
    ]

    ok, msg = tdv_mod.check_acceptance_placeholder(acceptance)

    assert ok is True


def test_check_acceptance_placeholder_detects_verbatim_template_without_braces():
    """DOC 型第 2、3 條樣板不含大括號，仍須靠逐字比對命中（單靠大括號偵測會漏判）。"""
    acceptance = [
        "[ ] 格式符合規範：遵守 CLAUDE.md 的文件格式規則",
    ]

    ok, msg = tdv_mod.check_acceptance_placeholder(acceptance)

    assert ok is False
    assert "1 項未填樣板" in msg


def _fake_ticket_for_validate(body: str, acceptance: list[str]) -> dict:
    return {
        "_body": body,
        "where": {"files": []},
        "acceptance": acceptance,
    }


def test_dispatch_validate_reports_both_hard_rules_when_simultaneously_violated(monkeypatch):
    """規則 1（缺 Context Bundle）與規則 4b（未填樣板）同時違反是主要路徑，
    不是邊角案例——訊息須列出兩者，exit code 仍為 2（硬性失敗）。"""
    fake_ticket = _fake_ticket_for_validate(
        body="# Execution Log\n\n## Task Summary\n\n無 Context Bundle 章節\n",
        acceptance=[
            "[ ] 文件內容完整：包含標題、背景、正文、結論、附錄等 {N} 部分",
            "[ ] 格式符合規範：遵守 CLAUDE.md 的文件格式規則",
            "[ ] 內容無遺漏：所有預期的小節都已填寫（無 TODO 或空白區段）",
        ],
    )
    monkeypatch.setattr(
        "ticket_system.lib.dispatch_common.load_ticket",
        lambda version, tid: fake_ticket,
    )
    monkeypatch.setattr(
        tdv_mod, "check_acceptance_uc_alignment", lambda tid: (True, "skip")
    )

    args = argparse.Namespace(ticket_id="0.0.0-W0-BOTHHARD", version="0.0.0")
    rc = tdv_mod.execute_dispatch_validate(args, "0.0.0")

    assert rc == 2


def test_dispatch_validate_passes_when_acceptance_is_filled(monkeypatch):
    """已填內容的 ticket（含 Context Bundle）通過規則 4b，不受新檢查誤擋。"""
    context_bundle_content = "需求摘要與實作細節" * 10  # >= 50 字元
    fake_ticket = _fake_ticket_for_validate(
        body=(
            "# Execution Log\n\n## Task Summary\n\n任務\n\n---\n\n"
            f"## Context Bundle\n\n{context_bundle_content}\n"
        ),
        acceptance=[
            "[ ] gap_report_screen 的空狀態改用共用 EmptyStateWidget",
            "[ ] flutter test 全數通過（含新增的空狀態 widget test）",
            "[ ] dart analyze 0 issues",
        ],
    )
    monkeypatch.setattr(
        "ticket_system.lib.dispatch_common.load_ticket",
        lambda version, tid: fake_ticket,
    )
    monkeypatch.setattr(
        tdv_mod, "check_acceptance_uc_alignment", lambda tid: (True, "skip")
    )

    args = argparse.Namespace(ticket_id="0.0.0-W0-FILLED", version="0.0.0")
    rc = tdv_mod.execute_dispatch_validate(args, "0.0.0")

    assert rc == 0


# --- --isolation 感知與 review 首行宣告（0.3.2-W1-013） -------------------------

_NON_EXEMPT_FILES = ["src/app/main.dart", ".claude/skills/ticket/SKILL.md"]
_EXEMPT_FILES = [".claude/hooks/x.py", "docs/a.md", "CHANGELOG.md", "scripts/experiments/e.py"]


def _dispatch_out(args, capsys):
    rc = td_mod.execute_dispatch(args, "0.0.0")
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_dispatch_isolation_worktree_vs_default_closing_differs(dispatch_ticket, capsys):
    """E1：同票帶 --isolation worktree 與不帶，收尾句不同。"""
    _, out_default, _ = _dispatch_out(_base_args(), capsys)
    _, out_wt, _ = _dispatch_out(_base_args(isolation="worktree"), capsys)

    assert out_default != out_wt
    assert "ticket track complete" in out_default
    assert "ticket track finish" not in out_default
    # 通用 Commit 段落兩側都提到 --worktree，故以收尾句專有的完整片段區分
    assert "--worktree <worktree 絕對路徑>" not in out_default
    assert "--worktree <worktree 絕對路徑>" in out_wt
    assert "ticket track finish" not in out_wt
    assert "ticket track complete" not in out_wt
    assert "回報 PM" in out_wt


def test_dispatch_isolation_none_keeps_complete_closing(dispatch_ticket, capsys):
    _, out_none, _ = _dispatch_out(_base_args(isolation="none"), capsys)
    _, out_default, _ = _dispatch_out(_base_args(), capsys)
    assert out_none == out_default


def test_dispatch_review_first_line_declares_readonly_normal_does_not(dispatch_ticket, capsys):
    """E1：review 首行 Dispatch-Mode: readonly，normal 首行不是。"""
    _, out_review, _ = _dispatch_out(
        _base_args(kind="review", review_perspective="p", decision_question="q"), capsys
    )
    _, out_normal, _ = _dispatch_out(_base_args(), capsys)

    assert out_review.splitlines()[0] == "Dispatch-Mode: readonly"
    assert out_review.splitlines()[1].startswith("Ticket:")
    assert out_normal.splitlines()[0] != "Dispatch-Mode: readonly"
    assert "Dispatch-Mode" not in out_normal


def test_dispatch_warns_when_non_exempt_files_and_no_isolation(tmp_path, monkeypatch, capsys):
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=_NON_EXEMPT_FILES)
    rc, out, err = _dispatch_out(_base_args(), capsys)
    assert rc == 0
    assert "WARNING" in err
    assert "parallel-dispatch.md" in err
    assert "ticket track claim" in out  # 骨架照常輸出


def test_dispatch_no_warning_when_all_files_exempt(tmp_path, monkeypatch, capsys):
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=_EXEMPT_FILES)
    rc, _, err = _dispatch_out(_base_args(), capsys)
    assert rc == 0
    assert "WARNING" not in err


@pytest.mark.parametrize("isolation", ["none", "worktree"])
def test_dispatch_no_warning_when_isolation_explicit(tmp_path, monkeypatch, capsys, isolation):
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=_NON_EXEMPT_FILES)
    rc, _, err = _dispatch_out(_base_args(isolation=isolation), capsys)
    assert rc == 0
    assert "WARNING" not in err


def test_dispatch_worktree_closing_excludes_ticket_md_from_commit(dispatch_ticket, capsys):
    """0.4.0-W1-053 E1：worktree 收尾句須說明只提交產品檔、票面由主 repo 處理；
    none 變體不帶此限制。斷言語意關鍵詞，不鎖整句。"""
    _, out_default, _ = _dispatch_out(_base_args(), capsys)
    _, out_wt, _ = _dispatch_out(_base_args(isolation="worktree"), capsys)

    closing = next(ln for ln in out_wt.splitlines() if ln.startswith("收尾"))
    default_closing = next(ln for ln in out_default.splitlines() if ln.startswith("收尾"))
    assert "票面" in closing
    assert "產品檔" in closing
    assert "主 repo" in closing
    assert "票面" not in default_closing


# --- 含測試 acceptance 的 IMP 骨架紅燈實跑要求（0.5.0-W1-388） -----------

from ticket_system.lib.dispatch_skeleton import (  # noqa: E402
    RED_RUN_LINE,
    build_skeleton,
    requires_red_run,
)


@pytest.mark.parametrize(
    "ticket_type, acceptance, expected",
    [
        ("IMP", ["[ ] 新增測試全綠"], True),
        ("IMP", ["[ ] 守衛含 E2 正向對照"], True),
        ("IMP", ["[ ] 旗標 E1 對照"], True),
        ("IMP", ["[ ] 文件更新完成"], False),
        ("DOC", ["[ ] 測試通過"], False),
        ("ANA", ["[ ] 測試通過"], False),
        ("IMP", [], False),
        ("IMP", None, False),
    ],
)
def test_requires_red_run_predicate(ticket_type, acceptance, expected):
    assert requires_red_run(ticket_type, acceptance) is expected


def _skeleton(**overrides) -> str:
    kwargs = dict(kind="normal", ticket_id="T-1", task_summary="x")
    kwargs.update(overrides)
    return build_skeleton(**kwargs)


def test_skeleton_includes_red_run_line_when_required():
    assert RED_RUN_LINE in _skeleton(require_red_run=True)


def test_skeleton_unchanged_when_red_run_not_required():
    assert RED_RUN_LINE not in _skeleton()
    assert _skeleton(require_red_run=True).replace(RED_RUN_LINE + "\n", "") == _skeleton()


def test_dispatch_cli_wires_red_run_line_for_test_acceptance_imp(dispatch_ticket, capsys, monkeypatch):
    monkeypatch.setattr(td_mod, "requires_red_run", lambda *_: True)
    rc = td_mod.execute_dispatch(_base_args(ticket_id=dispatch_ticket), "0.0.0")
    assert rc == 0
    assert RED_RUN_LINE in capsys.readouterr().out


# --- worktree 骨架：票面 CLI 被拒處置與 heredoc 傳入（0.5.0-W1-355.1） -----

from ticket_system.lib.dispatch_skeleton import (  # noqa: E402
    WORKTREE_CLI_REJECT_LINE,
    WORKTREE_MULTILINE_LINE,
)


def test_worktree_skeleton_includes_cli_reject_and_multiline_lines():
    out = _skeleton(isolation="worktree")
    assert WORKTREE_CLI_REJECT_LINE in out
    assert WORKTREE_MULTILINE_LINE in out
    assert "### 自檢結果" in WORKTREE_MULTILINE_LINE
    assert "--content-file" in WORKTREE_MULTILINE_LINE
    assert "票號" in WORKTREE_MULTILINE_LINE
    assert "以 heredoc 傳" not in WORKTREE_MULTILINE_LINE
    assert "\n" not in WORKTREE_MULTILINE_LINE


def test_none_and_review_skeletons_unchanged_by_worktree_lines():
    for out in (_skeleton(), _skeleton(kind="review")):
        assert WORKTREE_CLI_REJECT_LINE not in out
        assert WORKTREE_MULTILINE_LINE not in out
    assert _skeleton(isolation="none") == _skeleton()


# --- 骨架依 where.files 附測試入口命令（0.5.0-W1-397） ---------------------

from ticket_system.lib.dispatch_skeleton import entry_commands_for_files  # noqa: E402

_HOOKS_ENTRY = "uv --directory <checkout>/.claude/hooks run pytest"


_REAL_ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def entry_root(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    (skills / "ticket").mkdir(parents=True)
    (skills / "ticket" / "pyproject.toml").write_text("")
    (skills / "spec" / "tests").mkdir(parents=True)
    (skills / "bare").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    "files, expected",
    [
        ([".claude/skills/bare/a.py"], []),
        ([".claude/hooks/x-hook.py"], [_HOOKS_ENTRY]),
        ([".claude/lib/y.py"], [_HOOKS_ENTRY]),
        (
            [".claude/skills/ticket/ticket_system/lib/a.py"],
            ["uv --directory <checkout>/.claude/skills/ticket run pytest"],
        ),
        (
            [".claude/skills/spec/scripts/a.py"],
            [_HOOKS_ENTRY + " <checkout>/.claude/skills/spec/tests"],
        ),
        ([".claude/hooks/a.py", ".claude/hooks/b.py"], [_HOOKS_ENTRY]),
        (["lib/main.dart", "docs/a.md", ".claude/rules/a.md"], []),
        ([], []),
    ],
)
def test_test_entry_commands_mapping(entry_root, files, expected):
    assert entry_commands_for_files(files, entry_root) == expected


def test_own_pyproject_skills_match_testing_md_table():
    """md 表落後檔案系統（漏列有 pyproject 的 skill）時翻紅。"""
    skills_dir = _REAL_ROOT / ".claude" / "skills"
    derived = {p.parent.name for p in skills_dir.glob("*/pyproject.toml")}
    md = (_REAL_ROOT / ".claude/references/agent-dispatch-testing.md").read_text()
    listed = {"ticket"}
    for line in md.splitlines():
        if line.startswith("| skills/doc"):
            names = line.split("|")[1].strip().removeprefix("skills/")
            listed |= {n.strip() for n in names.split("、")}
    assert derived == listed


def test_skeleton_includes_test_entry_only_when_mapped():
    entries = entry_commands_for_files([".claude/hooks/x.py"], _REAL_ROOT)
    with_entry = _skeleton(test_entries=entries)
    assert _HOOKS_ENTRY in with_entry
    assert _HOOKS_ENTRY not in _skeleton()
    assert _skeleton(test_entries=[]) == _skeleton()


# --- 閘門逐檔檢查套件併入收尾句（0.5.0-W1-563.1） ---------------------------
#
# merge-gate.yaml 帶 changed_files 的套件只對本次改動檔執行，結果由代理人自己的
# 改動決定；骨架依 where.files 推出命令併入收尾句，代理人提交前在本機先跑。

from ticket_system.lib.dispatch_skeleton import (  # noqa: E402
    GATE_DECLARATION_PATH,
    GateDeclarationError,
    gate_check_commands,
)

_GATE_YAML = """suites:
  dart-format:
    prefixes: [lib/, test/, integration_test/]
    command: [fvm, dart, format, --output=none, --set-exit-if-changed]
    changed_files: '\\.dart$'
  flutter:
    prefixes: [lib/, test/]
    files: [pubspec.yaml]
    command: [fvm, flutter, test]
  pinned:
    files: [tool/gen.dart]
    command: [dart, run, tool/check.dart]
    changed_files: 'gen'
"""

_FORMAT_CMD = "fvm dart format --output=none --set-exit-if-changed"


def test_gate_check_commands_only_changed_files_suites():
    files = ["lib/a.dart", "test/b_test.dart", "docs/x.md", "pubspec.yaml", "lib/c.json"]
    assert gate_check_commands(files, _GATE_YAML) == [
        f"{_FORMAT_CMD} lib/a.dart test/b_test.dart"
    ]


def test_gate_check_commands_matches_exact_files_entry():
    assert gate_check_commands(["tool/gen.dart"], _GATE_YAML) == [
        "dart run tool/check.dart tool/gen.dart"
    ]


@pytest.mark.parametrize("files", [[], ["docs/x.md"], ["pubspec.yaml"], ["lib/c.json"]])
def test_gate_check_commands_empty_when_no_file_matches(files):
    assert gate_check_commands(files, _GATE_YAML) == []


@pytest.mark.parametrize("text", [None, "", "suites: {}\n"])
def test_gate_check_commands_empty_without_declaration(text):
    assert gate_check_commands(["lib/a.dart"], text) == []


@pytest.mark.parametrize("text", ["suites: [1, 2\n", "suites: 3\n", "- a\n"])
def test_gate_check_commands_raises_on_malformed_declaration(text):
    with pytest.raises(GateDeclarationError):
        gate_check_commands(["lib/a.dart"], text)


def test_quotes_paths_with_spaces():
    cmds = gate_check_commands(["lib/a b.dart"], _GATE_YAML)
    assert cmds == [f"{_FORMAT_CMD} 'lib/a b.dart'"]


@pytest.mark.parametrize("isolation", ["none", "worktree"])
def test_skeleton_closing_contains_gate_check_before_commit(isolation):
    cmd = f"{_FORMAT_CMD} lib/a.dart"
    with_gate = _skeleton(isolation=isolation, gate_checks=[cmd])
    without = _skeleton(isolation=isolation)
    assert with_gate != without  # E1：傳與不傳產物不同
    assert cmd not in without
    closing = next(l for l in with_gate.splitlines() if l.startswith("收尾："))
    assert cmd in closing
    commit_word = "ticket track commit" if isolation == "worktree" else "→ commit →"
    assert closing.index(cmd) < closing.index(commit_word)
    assert len(with_gate.splitlines()) == len(without.splitlines())  # 不新增行


def test_skeleton_unchanged_when_gate_checks_empty():
    assert _skeleton(gate_checks=[]) == _skeleton()
    assert _skeleton(isolation="worktree", gate_checks=()) == _skeleton(isolation="worktree")


def _write_gate_declaration(root: Path, text: str) -> None:
    path = root / GATE_DECLARATION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_dispatch_cli_wires_gate_check_from_declaration(tmp_path, monkeypatch, capsys):
    root = tmp_path / "checkout"
    _write_gate_declaration(root, _GATE_YAML)
    monkeypatch.setattr(td_mod, "_CHECKOUT_ROOT", root)
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=["lib/a.dart", "docs/x.md"])
    rc, out, err = _dispatch_out(_base_args(isolation="worktree"), capsys)
    assert rc == 0
    assert f"{_FORMAT_CMD} lib/a.dart" in out
    assert "docs/x.md" not in out.split("收尾：", 1)[1].split("\n", 1)[0]


def test_dispatch_cli_no_gate_check_without_declaration(tmp_path, monkeypatch, capsys):
    root = tmp_path / "checkout"
    root.mkdir()
    monkeypatch.setattr(td_mod, "_CHECKOUT_ROOT", root)
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=["lib/a.dart"])
    rc, out, err = _dispatch_out(_base_args(isolation="worktree"), capsys)
    assert rc == 0
    assert "閘門逐檔檢查" not in out


def test_dispatch_cli_warns_on_malformed_declaration(tmp_path, monkeypatch, capsys):
    root = tmp_path / "checkout"
    _write_gate_declaration(root, "suites: [1, 2\n")
    monkeypatch.setattr(td_mod, "_CHECKOUT_ROOT", root)
    _make_dispatch_ticket(tmp_path, monkeypatch, where_files=["lib/a.dart"])
    rc, out, err = _dispatch_out(_base_args(isolation="worktree"), capsys)
    assert rc == 0
    assert "WARNING" in err and GATE_DECLARATION_PATH in err
    assert "ticket track claim" in out  # 骨架照常輸出
    assert "閘門逐檔檢查" not in out


def test_real_declaration_yields_dart_format_for_dart_files():
    """本 checkout 的宣告若含 changed_files 套件，對 .dart 檔應產出命令（宣告不存在則略過）。"""
    path = _REAL_ROOT / GATE_DECLARATION_PATH
    if not path.is_file():
        pytest.skip("本 checkout 無閘門宣告")
    cmds = gate_check_commands(["lib/x.dart"], path.read_text(encoding="utf-8"))
    assert all(c.endswith(" lib/x.dart") for c in cmds)
