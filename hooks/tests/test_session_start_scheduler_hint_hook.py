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
    # 不含排程提示區塊
    assert "## 排程提示" not in ac


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
    assert "## 排程提示" in ac
    assert "## Spawned 推進清單" in ac
    # 排程提示位於 spawned 之前
    assert ac.index("## 排程提示") < ac.index("## Spawned 推進清單")


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
