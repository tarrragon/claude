"""
session-start-scheduler-hint-hook 測試套件

驗證：
1. 正常：resume 有結果 → additionalContext 顯示 resume 輸出
2. Fallback：resume 無結果 → 呼叫 next（--format=list --top 1）
3. 雙無：resume + next 皆無 → suppressOutput=True
4. CLI 錯誤：subprocess 失敗 → 靜默不阻塞 session（stderr 有記錄）
5. Timeout：subprocess 超時 → 靜默不阻塞
6. hookEventName 必為 SessionStart
7. additionalContext 為字串
8. 輸出為合法 JSON

W17-041 新增：spawned pending 提醒
9. build_hook_output：只有 spawned_pending_section 也輸出 additionalContext
10. build_hook_output：兩者皆無 → suppressOutput=True
11. build_hook_output：兩者皆有 → 兩個小節都顯示且可區分
12. build_spawned_pending_section：空清單 → None
13. build_spawned_pending_section：區分原生 pending 與 spawned（標題含「來源為 completed ANA」）
14. build_spawned_pending_section：超過顯示上限時標示「…其餘 N 筆省略」
15. _extract_spawned_list：list 與 YAML 字串皆可解析
16. _detect_active_version：status=active 的版本能被 regex 偵測到
17. scan_spawned_pending：只納入 completed ANA；只回傳非 terminal spawned
"""

import json
import subprocess
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock


# 動態載入 hook（檔名含 dash）
HOOK_PATH = Path(__file__).parent.parent / "session-start-scheduler-hint-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "session_start_scheduler_hint_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mk_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# 1. resume 有待恢復 → 顯示 resume 輸出
# ---------------------------------------------------------------------------
def test_resume_has_pending_uses_resume_output():
    hook = load_hook_module()
    resume_out = "─────\n（待恢復 handoff / top 3）\n  1. 0.18.0-W17-001\n"
    with patch.object(hook.subprocess, "run", return_value=_mk_completed(resume_out)) as mrun:
        ctx = hook.fetch_scheduler_context(logger=MagicMock())
    assert resume_out.strip() in ctx
    # 只會呼叫一次 resume，不會 fallback 到 next
    assert mrun.call_count == 1
    called_args = mrun.call_args[0][0]
    assert "runqueue" in called_args
    assert "--context=resume" in called_args


# ---------------------------------------------------------------------------
# 2. resume 無結果 → fallback 呼叫 next
# ---------------------------------------------------------------------------
def test_resume_empty_falls_back_to_next():
    hook = load_hook_module()
    empty_resume = "─────\n（無可執行 Ticket；blockedBy 全非空或 status 非 pending）"
    next_out = "─────\n  1. [P0] 0.18.0-W17-005  補上 append-log"

    def side_effect(cmd, **kwargs):
        if "--context=resume" in cmd:
            return _mk_completed(empty_resume)
        return _mk_completed(next_out)

    with patch.object(hook.subprocess, "run", side_effect=side_effect) as mrun:
        ctx = hook.fetch_scheduler_context(logger=MagicMock())

    assert next_out.strip() in ctx
    assert mrun.call_count == 2
    # 第二次呼叫含 --format=list
    second_cmd = mrun.call_args_list[1][0][0]
    assert "--format=list" in second_cmd
    assert "--top" in second_cmd


# ---------------------------------------------------------------------------
# 3. resume + next 皆無 → 回傳 None
# ---------------------------------------------------------------------------
def test_both_empty_returns_none():
    hook = load_hook_module()
    empty = "（無可執行 Ticket；blockedBy 全非空或 status 非 pending）"
    with patch.object(hook.subprocess, "run", return_value=_mk_completed(empty)):
        ctx = hook.fetch_scheduler_context(logger=MagicMock())
    assert ctx is None


# ---------------------------------------------------------------------------
# 4. subprocess 異常 → 靜默（stderr 記錄由 logger 負責）
# ---------------------------------------------------------------------------
def test_subprocess_error_returns_none_and_logs(capsys):
    hook = load_hook_module()
    logger = MagicMock()
    with patch.object(hook.subprocess, "run", side_effect=FileNotFoundError("ticket")):
        ctx = hook.fetch_scheduler_context(logger=logger)
    assert ctx is None
    # 規則 4：必須有錯誤記錄
    assert logger.error.called or logger.warning.called


# ---------------------------------------------------------------------------
# 5. subprocess timeout → 靜默
# ---------------------------------------------------------------------------
def test_subprocess_timeout_returns_none():
    hook = load_hook_module()
    logger = MagicMock()
    with patch.object(
        hook.subprocess, "run",
        side_effect=subprocess.TimeoutExpired(cmd="ticket", timeout=5),
    ):
        ctx = hook.fetch_scheduler_context(logger=logger)
    assert ctx is None
    assert logger.error.called or logger.warning.called


# ---------------------------------------------------------------------------
# 6. hookEventName 必為 SessionStart
# ---------------------------------------------------------------------------
def test_build_output_has_session_start_event():
    hook = load_hook_module()
    out = hook.build_hook_output("some context text")
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


# ---------------------------------------------------------------------------
# 7. additionalContext 為字串且非空
# ---------------------------------------------------------------------------
def test_build_output_context_is_nonempty_string():
    hook = load_hook_module()
    out = hook.build_hook_output("一些排程提示")
    ac = out["hookSpecificOutput"]["additionalContext"]
    assert isinstance(ac, str)
    assert ac.strip() != ""
    assert "一些排程提示" in ac


# ---------------------------------------------------------------------------
# 8. 無排程內容 → suppressOutput=True
# ---------------------------------------------------------------------------
def test_build_output_none_suppresses():
    hook = load_hook_module()
    out = hook.build_hook_output(None)
    assert out.get("suppressOutput") is True
    assert "hookSpecificOutput" not in out


# ---------------------------------------------------------------------------
# 9. 完整輸出為合法 JSON（整合：stdin 空 + 兩次 CLI mock）
# ---------------------------------------------------------------------------
def test_main_outputs_valid_json(capsys, monkeypatch):
    hook = load_hook_module()
    resume_out = "（待恢復 handoff）\n  1. 0.18.0-W17-001"

    monkeypatch.setattr("sys.stdin", _StdinStub('{"hook_event_name":"SessionStart"}'))

    with patch.object(hook.subprocess, "run", return_value=_mk_completed(resume_out)):
        rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "0.18.0-W17-001" in parsed["hookSpecificOutput"]["additionalContext"]


class _StdinStub:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text

    def isatty(self):
        return False


# ===========================================================================
# W17-041：spawned pending 提醒測試
# ===========================================================================


# ---------------------------------------------------------------------------
# 9. build_hook_output：只有 spawned_pending_section 也輸出 additionalContext
# ---------------------------------------------------------------------------
def test_build_output_only_spawned_section():
    hook = load_hook_module()
    section = "## Spawned 推進清單（來源為 completed ANA...）\n\n- ..."
    out = hook.build_hook_output(None, section)
    assert out.get("suppressOutput") is False
    ac = out["hookSpecificOutput"]["additionalContext"]
    assert "Spawned 推進清單" in ac
    # 不含排程提示區塊（W17-165 L2-B：標題改為「下 session 建議項目」，副標保留 scheduler hint）
    assert "## 下 session 建議項目" not in ac


# ---------------------------------------------------------------------------
# 10. build_hook_output：兩者皆無 → suppressOutput=True
# ---------------------------------------------------------------------------
def test_build_output_both_none_suppresses():
    hook = load_hook_module()
    out = hook.build_hook_output(None, None)
    assert out.get("suppressOutput") is True
    assert "hookSpecificOutput" not in out


# ---------------------------------------------------------------------------
# 11. build_hook_output：兩者皆有 → 兩個小節都顯示且可區分
# ---------------------------------------------------------------------------
def test_build_output_both_sections_visible():
    hook = load_hook_module()
    sched = "some scheduler context"
    section = "## Spawned 推進清單（來源為 completed ANA...）\n\n- item"
    out = hook.build_hook_output(sched, section)
    ac = out["hookSpecificOutput"]["additionalContext"]
    # W17-165 L2-B：標題從「排程提示」改為「下 session 建議項目」
    assert "## 下 session 建議項目" in ac
    assert "## Spawned 推進清單" in ac
    # scheduler hint 區塊位於 spawned 之前
    assert ac.index("## 下 session 建議項目") < ac.index("## Spawned 推進清單")


# ---------------------------------------------------------------------------
# 12. build_spawned_pending_section：空清單 → None
# ---------------------------------------------------------------------------
def test_build_spawned_section_empty_returns_none():
    hook = load_hook_module()
    assert hook.build_spawned_pending_section([]) is None


# ---------------------------------------------------------------------------
# 13. build_spawned_pending_section：區分原生 pending 與 spawned
# ---------------------------------------------------------------------------
def test_build_spawned_section_distinguishes_spawned_from_native():
    hook = load_hook_module()
    items = [
        ("0.18.0-W17-032", "pending", "0.18.0-W17-022"),
        ("0.18.0-W17-033", "pending", "0.18.0-W17-022"),
    ]
    section = hook.build_spawned_pending_section(items)
    # 區分標記：必含「來源為 completed ANA」或「非原生 pending」字樣
    assert (
        "來源為 completed ANA" in section
        or "非原生 pending" in section
    )
    # source ANA 有顯示
    assert "0.18.0-W17-022" in section
    # spawned 有顯示
    assert "0.18.0-W17-032" in section
    assert "0.18.0-W17-033" in section
    # status 有顯示
    assert "pending" in section


# ---------------------------------------------------------------------------
# 14. build_spawned_pending_section：超過顯示上限時顯示省略訊息
# ---------------------------------------------------------------------------
def test_build_spawned_section_respects_display_limit():
    hook = load_hook_module()
    limit = hook.SPAWNED_PENDING_DISPLAY_LIMIT
    # 製造 limit+3 個項目（全來自同一 ANA 簡化）
    items = [
        (f"0.18.0-W99-{i:03d}", "pending", "0.18.0-W99-000")
        for i in range(1, limit + 4)
    ]
    section = hook.build_spawned_pending_section(items)
    # 含省略訊息
    assert "省略" in section
    # 只顯示 limit 項
    displayed = sum(1 for line in section.split("\n") if "[status=" in line)
    assert displayed == limit
    # 總數顯示正確
    assert str(len(items)) in section


# ---------------------------------------------------------------------------
# 15. _extract_spawned_list：list 與 YAML 字串皆可解析
# ---------------------------------------------------------------------------
def test_extract_spawned_list_handles_list():
    hook = load_hook_module()
    fm = {"spawned_tickets": ["0.18.0-W1-001", "0.18.0-W1-002"]}
    assert hook._extract_spawned_list(fm) == ["0.18.0-W1-001", "0.18.0-W1-002"]


def test_extract_spawned_list_handles_yaml_string():
    hook = load_hook_module()
    fm = {"spawned_tickets": "- 0.18.0-W1-001\n- 0.18.0-W1-002"}
    assert hook._extract_spawned_list(fm) == ["0.18.0-W1-001", "0.18.0-W1-002"]


def test_extract_spawned_list_handles_empty():
    hook = load_hook_module()
    assert hook._extract_spawned_list({"spawned_tickets": []}) == []
    assert hook._extract_spawned_list({"spawned_tickets": None}) == []
    assert hook._extract_spawned_list({}) == []


# ---------------------------------------------------------------------------
# 16. _detect_active_version：status=active 的版本能被偵測到
# ---------------------------------------------------------------------------
def test_detect_active_version_finds_status_active(tmp_path):
    hook = load_hook_module()
    todolist = tmp_path / "docs" / "todolist.yaml"
    todolist.parent.mkdir(parents=True)
    todolist.write_text(
        "versions:\n"
        "  - version: \"0.17.0\"\n"
        "    status: completed\n"
        "  - version: \"0.18.0\"\n"
        "    status: active\n"
        "  - version: \"0.19.0\"\n"
        "    status: planned\n",
        encoding="utf-8",
    )
    logger = MagicMock()
    assert hook._detect_active_version(tmp_path, logger) == "0.18.0"


def test_detect_active_version_no_active_returns_none(tmp_path):
    hook = load_hook_module()
    todolist = tmp_path / "docs" / "todolist.yaml"
    todolist.parent.mkdir(parents=True)
    todolist.write_text(
        "versions:\n  - version: \"0.17.0\"\n    status: completed\n",
        encoding="utf-8",
    )
    assert hook._detect_active_version(tmp_path, MagicMock()) is None


def test_detect_active_version_no_todolist_returns_none(tmp_path):
    hook = load_hook_module()
    # 沒建 todolist
    assert hook._detect_active_version(tmp_path, MagicMock()) is None


# ---------------------------------------------------------------------------
# 17. scan_spawned_pending：只納入 completed ANA，只回傳非 terminal spawned
# ---------------------------------------------------------------------------
def _write_ticket(root: Path, version: str, ticket_id: str, fm: dict):
    """輔助：寫入 ticket md（flat 結構）。"""
    d = root / "docs" / "work-logs" / f"v{version}" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    # 極簡 frontmatter（hook_utils.parse_ticket_frontmatter 支援）
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"- {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append("# Body")
    (d / f"{ticket_id}.md").write_text("\n".join(lines), encoding="utf-8")


def test_scan_spawned_pending_end_to_end(tmp_path):
    hook = load_hook_module()
    version = "0.18.0"
    # ANA-1: completed，spawned=[IMP-A pending, IMP-B completed, IMP-C in_progress]
    _write_ticket(tmp_path, version, "0.18.0-W1-001", {
        "id": "0.18.0-W1-001",
        "type": "ANA",
        "status": "completed",
        "spawned_tickets": ["0.18.0-W1-002", "0.18.0-W1-003", "0.18.0-W1-004"],
    })
    _write_ticket(tmp_path, version, "0.18.0-W1-002", {
        "id": "0.18.0-W1-002", "type": "IMP", "status": "pending",
    })
    _write_ticket(tmp_path, version, "0.18.0-W1-003", {
        "id": "0.18.0-W1-003", "type": "IMP", "status": "completed",
    })
    _write_ticket(tmp_path, version, "0.18.0-W1-004", {
        "id": "0.18.0-W1-004", "type": "IMP", "status": "in_progress",
    })
    # ANA-2: in_progress（不應被納入，即便 spawned 有 pending）
    _write_ticket(tmp_path, version, "0.18.0-W2-001", {
        "id": "0.18.0-W2-001",
        "type": "ANA",
        "status": "in_progress",
        "spawned_tickets": ["0.18.0-W2-002"],
    })
    _write_ticket(tmp_path, version, "0.18.0-W2-002", {
        "id": "0.18.0-W2-002", "type": "IMP", "status": "pending",
    })
    # ANA-3: completed，無 spawned
    _write_ticket(tmp_path, version, "0.18.0-W3-001", {
        "id": "0.18.0-W3-001", "type": "ANA", "status": "completed",
    })

    logger = MagicMock()
    result = hook.scan_spawned_pending(tmp_path, version, logger)

    # 只含 ANA-1 的 pending 與 in_progress（completed 排除）
    ids = sorted(sid for sid, _, _ in result)
    assert ids == ["0.18.0-W1-002", "0.18.0-W1-004"]
    # source ANA 皆為 W1-001
    assert all(ana_id == "0.18.0-W1-001" for _, _, ana_id in result)


def test_scan_spawned_pending_no_active_version_returns_empty(tmp_path):
    """沒有 ticket 檔案時回空（scan_ticket_files_by_version 找不到目錄）。"""
    hook = load_hook_module()
    result = hook.scan_spawned_pending(tmp_path, "0.99.0", MagicMock())
    assert result == []


# ---------------------------------------------------------------------------
# 18. 失敗靜默降級：fetch_spawned_pending_context 遇異常回傳 None
# ---------------------------------------------------------------------------
def test_fetch_spawned_pending_context_graceful_degrade(monkeypatch):
    hook = load_hook_module()
    logger = MagicMock()
    # 強迫 get_project_root 拋例外 → 必回 None 且 logger 有警告
    monkeypatch.setattr(hook, "get_project_root", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    result = hook.fetch_spawned_pending_context(logger)
    assert result is None
    assert logger.warning.called


# ===========================================================================
# W17-031.5：NeedsContext 警示測試（盲區 E）
# ===========================================================================


def _write_handoff(root: Path, ticket_id: str, payload: dict) -> Path:
    """輔助：寫入 .claude/handoff/pending/<ticket_id>.json"""
    pending = root / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    path = pending / f"{ticket_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 19. scan_needs_context_handoffs：找出 exit_status=needs_context
# ---------------------------------------------------------------------------
def test_scan_needs_context_finds_marked(tmp_path):
    hook = load_hook_module()
    _write_handoff(tmp_path, "0.18.0-W17-100", {
        "ticket_id": "0.18.0-W17-100", "exit_status": "needs_context",
    })
    _write_handoff(tmp_path, "0.18.0-W17-101", {
        "ticket_id": "0.18.0-W17-101", "exit_status": "success",
    })
    _write_handoff(tmp_path, "0.18.0-W17-102", {
        "ticket_id": "0.18.0-W17-102", "exit_status": "needs_context",
    })
    # 無 exit_status 欄位（schema 解耦：W17-031.2 前的舊 JSON）→ 不視為 needs_context
    _write_handoff(tmp_path, "0.18.0-W17-103", {
        "ticket_id": "0.18.0-W17-103",
    })

    ids = hook.scan_needs_context_handoffs(tmp_path, MagicMock())
    assert ids == ["0.18.0-W17-100", "0.18.0-W17-102"]


# ---------------------------------------------------------------------------
# 20. scan_needs_context_handoffs：目錄不存在 fail-open
# ---------------------------------------------------------------------------
def test_scan_needs_context_dir_missing_returns_empty(tmp_path):
    hook = load_hook_module()
    # 完全不建 .claude/handoff/pending
    assert hook.scan_needs_context_handoffs(tmp_path, MagicMock()) == []


# ---------------------------------------------------------------------------
# 21. scan_needs_context_handoffs：壞 JSON 不阻擋
# ---------------------------------------------------------------------------
def test_scan_needs_context_bad_json_skipped(tmp_path):
    hook = load_hook_module()
    pending = tmp_path / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True)
    (pending / "broken.json").write_text("{ not valid json", encoding="utf-8")
    _write_handoff(tmp_path, "0.18.0-W17-200", {
        "ticket_id": "0.18.0-W17-200", "exit_status": "needs_context",
    })
    ids = hook.scan_needs_context_handoffs(tmp_path, MagicMock())
    assert ids == ["0.18.0-W17-200"]


# ---------------------------------------------------------------------------
# 22. build_needs_context_section：空清單 → None
# ---------------------------------------------------------------------------
def test_build_needs_context_section_empty_returns_none():
    hook = load_hook_module()
    assert hook.build_needs_context_section([]) is None


# ---------------------------------------------------------------------------
# 23. build_needs_context_section：總數 + ID 顯示
# ---------------------------------------------------------------------------
def test_build_needs_context_section_shows_total_and_ids():
    hook = load_hook_module()
    section = hook.build_needs_context_section([
        "0.18.0-W17-100", "0.18.0-W17-101",
    ])
    assert "NeedsContext 警示" in section
    assert "共 2 個" in section
    assert "0.18.0-W17-100" in section
    assert "0.18.0-W17-101" in section


# ---------------------------------------------------------------------------
# 24. build_needs_context_section：超過上限顯示省略
# ---------------------------------------------------------------------------
def test_build_needs_context_section_respects_limit():
    hook = load_hook_module()
    limit = hook.NEEDS_CONTEXT_DISPLAY_LIMIT
    ids = [f"0.18.0-W99-{i:03d}" for i in range(1, limit + 3)]
    section = hook.build_needs_context_section(ids)
    # 最多 limit 個 ID 顯示
    displayed = sum(1 for line in section.split("\n") if line.startswith("- `0.18.0-W99-"))
    assert displayed == limit
    # 省略訊息
    assert "省略" in section
    # 總數正確
    assert f"共 {len(ids)} 個" in section


# ---------------------------------------------------------------------------
# 25. build_hook_output：三段全在時可區分順序
# ---------------------------------------------------------------------------
def test_build_output_three_sections_in_order():
    hook = load_hook_module()
    out = hook.build_hook_output(
        "sched ctx",
        "## Spawned 推進清單（來源為 completed ANA）\n\n- a",
        "## NeedsContext 警示\n\n- b",
    )
    ac = out["hookSpecificOutput"]["additionalContext"]
    # W17-165 L2-B：標題從「排程提示」改為「下 session 建議項目」
    assert "## 下 session 建議項目" in ac
    assert "## Spawned 推進清單" in ac
    assert "## NeedsContext 警示" in ac
    # 順序：scheduler hint < spawned < needs_context
    assert (
        ac.index("## 下 session 建議項目")
        < ac.index("## Spawned 推進清單")
        < ac.index("## NeedsContext 警示")
    )


# ---------------------------------------------------------------------------
# 26. build_hook_output：只有 needs_context 也輸出 additionalContext
# ---------------------------------------------------------------------------
def test_build_output_only_needs_context_section():
    hook = load_hook_module()
    out = hook.build_hook_output(None, None, "## NeedsContext 警示\n\n- x")
    assert out.get("suppressOutput") is False
    ac = out["hookSpecificOutput"]["additionalContext"]
    assert "NeedsContext 警示" in ac
    # W17-165 L2-B：scheduler hint 區塊缺席（標題改為「下 session 建議項目」）
    assert "## 下 session 建議項目" not in ac


# ---------------------------------------------------------------------------
# 27. fetch_needs_context_section：失敗 fail-open
# ---------------------------------------------------------------------------
def test_fetch_needs_context_section_graceful_degrade(monkeypatch):
    hook = load_hook_module()
    logger = MagicMock()
    monkeypatch.setattr(
        hook, "get_project_root",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = hook.fetch_needs_context_section(logger)
    assert result is None
    assert logger.warning.called


# ---------------------------------------------------------------------------
# 28. fetch_needs_context_section：無 needs_context 時回 None
# ---------------------------------------------------------------------------
def test_fetch_needs_context_section_none_when_no_needs_context(tmp_path, monkeypatch):
    hook = load_hook_module()
    monkeypatch.setattr(hook, "get_project_root", lambda: tmp_path)
    # 寫入只有 success 的 handoff
    _write_handoff(tmp_path, "0.18.0-W17-300", {
        "ticket_id": "0.18.0-W17-300", "exit_status": "success",
    })
    assert hook.fetch_needs_context_section(MagicMock()) is None
