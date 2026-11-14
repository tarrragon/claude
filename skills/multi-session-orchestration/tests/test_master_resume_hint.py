"""master_resume_hint.py 測試。

子行程測試（HOME 與 CLAUDE_PROJECT_DIR 指向 tmp）驗整支 hook 的輸出；
模組測試（importlib 載入、monkeypatch 行程查詢）驗名稱解析的兩條路徑與優先序。

正向：名稱為「主控」且 source 為 clear／compact 時輸出 additionalContext。
E2 對照：名稱不是「主控」、source 為 startup／resume、找不到 session 檔、
路徑 1 比對到非主控而祖先檔為主控、同 id 舊檔的行程已結束時，都不輸出。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "master_resume_hint.py"
SESSION_ID = "c1c1c1c1-0000-4000-8000-000000000000"
# pid 1 必定存在；session 檔不寫 procStart 時存活判定只看 pid 存在
LIVE_PID = 1


def load_module():
    spec = importlib.util.spec_from_file_location("master_resume_hint", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_session(home: Path, file_stem: str, name: str, session_id: str, pid: int = LIVE_PID, **extra) -> None:
    directory = home / ".claude" / "sessions"
    directory.mkdir(parents=True, exist_ok=True)
    record = {"pid": pid, "name": name, "sessionId": session_id, **extra}
    (directory / f"{file_stem}.json").write_text(json.dumps(record), encoding="utf-8")


def write_config(project: Path, *tickets: str) -> None:
    """建 active 版本與帶 coordination: true 的進行中票；不給票號時用單一預設票。"""
    (project / "docs").mkdir(parents=True, exist_ok=True)
    (project / "docs" / "todolist.yaml").write_text(
        'versions:\n  - version: "0.5.0"\n    status: "active"\n    worklog: "docs/work-logs/v0.5.0/"\n',
        encoding="utf-8",
    )
    directory = project / "docs" / "work-logs" / "v0.5.0" / "tickets"
    directory.mkdir(parents=True, exist_ok=True)
    for ticket in tickets or ("0.5.0-W1-349",):
        (directory / f"{ticket}.md").write_text(
            f"---\nid: {ticket}\nstatus: in_progress\ncoordination: true\n---\n", encoding="utf-8"
        )


def env_for(tmp_path: Path) -> dict:
    # HOOK_TEST_ISOLATION：日誌目錄經 hook_logging 解析，pytest 在 linked worktree 內執行時
    # 會繞過 CLAUDE_PROJECT_DIR；此旗標讓解析採 tmp 專案根
    return {
        "HOME": str(tmp_path / "home"),
        "CLAUDE_PROJECT_DIR": str(tmp_path / "project"),
        "HOOK_TEST_ISOLATION": "1",
        "PATH": "/usr/bin:/bin",
    }


def run(tmp_path: Path, source: str, session_id: str = SESSION_ID, stdin: str | None = None) -> subprocess.CompletedProcess:
    payload = stdin if stdin is not None else json.dumps({"source": source, "session_id": session_id})
    return subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True, env=env_for(tmp_path), timeout=30)


def context_of(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


# ---- 子行程：整支 hook 的輸出 ----


@pytest.mark.parametrize("source", ["clear", "compact"])
def test_master_after_clear_or_compact_gets_hint(tmp_path, source):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    text = context_of(run(tmp_path, source))
    assert f"剛經過 /{source}" in text
    assert "mcp__line-board__line_status" in text
    assert "0.5.0-W1-349" in text
    assert "line-continuity.md §4" in text


@pytest.mark.parametrize("source", ["startup", "resume"])
def test_master_on_startup_or_resume_gets_nothing(tmp_path, source):
    """E2 對照：同一個「主控」session 檔，只換 source，輸出必須為空。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    result = run(tmp_path, source)
    assert result.returncode == 0
    assert result.stdout == ""


def test_other_name_gets_nothing(tmp_path):
    """E2 對照：source=clear 不變，名稱不是「主控」時不提示。"""
    write_session(tmp_path / "home", "999", "看板工具", SESSION_ID)
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_session_file_gets_nothing(tmp_path):
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_dead_process_file_with_same_session_id_is_ignored(tmp_path):
    """E2 對照：同 id 的「主控」檔屬於已結束行程（procStart 不符），不得採用。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID, procStart="Mon Jan  1 00:00:00 1990")
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_zero_tickets_still_hints_and_says_so(tmp_path):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    for ticket in (tmp_path / "project/docs/work-logs/v0.5.0/tickets").glob("*.md"):
        ticket.unlink()
    text = context_of(run(tmp_path, "clear"))
    assert "找不到協調票，成因：active 版本裡沒有標記 coordination: true 的進行中票" in text
    assert "AskUserQuestion 問用戶開工作線或單一線" in text
    assert "先把版本轉 active" not in text
    assert "mcp__line-board__line_status" in text


def test_no_active_version_asks_user_and_says_cause(tmp_path):
    """沒有 active 版本（上一版完成、下一版 planned）時，提示寫明成因並先問開線或單一線。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    todolist = tmp_path / "project" / "docs" / "todolist.yaml"
    todolist.write_text(todolist.read_text(encoding="utf-8").replace('"active"', '"planned"'), encoding="utf-8")
    text = context_of(run(tmp_path, "clear"))
    assert "todolist 沒有 active 版本" in text
    assert "AskUserQuestion 問用戶開工作線或單一線" in text
    assert "先把版本轉 active" in text
    assert "單一線時把〈主控接續〉段與裁定寫進當前處理的票" in text


def test_none_step_does_not_tell_master_to_decide_alone(mod):
    """E2 對照：舊版 none 文字（只說先請用戶確認協調票）不含開線／單一線的詢問。"""
    legacy = "2. 找不到進行中的協調票（active 版本無 coordination: true 且 in_progress 的票）：先請用戶確認協調票，再繼續"
    assert "開工作線或單一線" not in legacy
    for has_active in (True, False):
        assert "開工作線或單一線" in mod.none_step(has_active)


@pytest.mark.parametrize("has_active", [True, False])
def test_none_record_step_follows_step_two_answer(tmp_path, has_active):
    """正向對照：沒有協調票時，第 3 步不得無條件寫「在協調票追加」，
    寫入位置須對應第 2 步的兩種答案。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    for ticket in (tmp_path / "project/docs/work-logs/v0.5.0/tickets").glob("*.md"):
        ticket.unlink()
    if not has_active:
        todolist = tmp_path / "project" / "docs" / "todolist.yaml"
        todolist.write_text(todolist.read_text(encoding="utf-8").replace('"active"', '"planned"'), encoding="utf-8")
    text = context_of(run(tmp_path, "clear"))
    step3 = next(line for line in text.splitlines() if line.startswith("3. "))
    assert "在協調票追加" not in step3
    assert "開工作線時寫進新建的協調票" in step3
    assert "單一線時寫進當前處理的票" in step3
    assert "〈主控接續（clear，<日期 時間>）〉段" in step3


def test_record_step_with_ticket_is_unchanged(tmp_path):
    """有協調票時第 3 步與修改前逐字相同。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    text = context_of(run(tmp_path, "compact"))
    assert (
        "3. 依 .claude/skills/multi-session-orchestration/references/line-continuity.md §4 "
        "在協調票追加〈主控接續（compact，<日期 時間>）〉段、推送，並先向用戶回報各線狀態與下一步"
    ) in text


def test_feedback_check_reminder_only_in_version_gap(mod):
    """E1：同一函式傳 has_active 兩值，只有沒有 active 版本（版本空窗）時提醒回饋檢查；
    有 active 版本時文字與加入提醒前逐字相同。"""
    gap = mod.none_step(False)
    active = mod.none_step(True)
    assert gap != active
    assert ".claude/skills/framework-issue/scripts/feedback.py" in gap
    assert "發版後回饋檢查" in gap
    assert "version-release start --version <下一版>" in gap
    assert "feedback.py" not in active and "發版後回饋檢查" not in active
    assert active == (
        "2. 找不到協調票，成因：active 版本裡沒有標記 coordination: true 的進行中票。"
        "不自行判定單一線，先以 AskUserQuestion 問用戶開工作線或單一線："
        "開工作線時建協調票並列開線計畫表；"
        "單一線時把〈主控接續〉段與裁定寫進當前處理的票，下次接續先讀該票"
        "（.claude/skills/multi-session-orchestration/references/line-continuity.md §3）"
    )


def test_unresolvable_still_hints(tmp_path):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    assert "協調票解析失敗" in context_of(run(tmp_path, "clear"))


def test_multiple_tickets_lists_candidates_for_user(tmp_path):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project", "0.5.0-W1-349", "0.5.0-W1-350")
    text = context_of(run(tmp_path, "clear"))
    assert "0.5.0-W1-349" in text and "0.5.0-W1-350" in text
    assert "請用戶裁定" in text
    assert "ticket track full" not in text


def test_log_lands_in_main_repo_when_run_in_linked_worktree(tmp_path):
    """linked worktree 內（不設 HOOK_TEST_ISOLATION）日誌寫入主 repo，worktree 自己不建 hook-logs。"""
    main, wt = tmp_path / "main", tmp_path / "wt"
    main.mkdir()
    git = ["git", "-C", str(main)]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "-c", "user.email=t@e.x", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"], check=True)
    subprocess.run([*git, "worktree", "add", "-q", str(wt), "-b", "wt-branch"], check=True)
    env = {"HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True,
        env=env, cwd=str(wt), timeout=30,
    )
    assert result.returncode == 0
    log = main.resolve() / ".claude" / "hook-logs" / "master-resume-hint" / "hook.log"
    assert "Traceback" in log.read_text(encoding="utf-8")
    assert not (wt / ".claude" / "hook-logs").exists()


def _linked_worktree_with_main_config(tmp_path):
    """MAIN 寫協調設定與 todolist，WT 不寫。"""
    main, wt = (tmp_path / "main").resolve(), tmp_path / "wt"
    main.mkdir()
    git = ["git", "-C", str(main), "-c", "user.email=t@e.x", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "i"], check=True)
    subprocess.run([*git, "worktree", "add", "-q", str(wt), "-b", "wt-branch"], check=True)
    write_config(main, "0.5.0-W1-349")
    return wt.resolve()


def _run_in_worktree(wt: Path, tmp_path: Path, isolation: bool) -> subprocess.CompletedProcess:
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    env = {"HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"}
    if isolation:
        env["HOOK_TEST_ISOLATION"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps({"source": "clear", "session_id": SESSION_ID}),
        capture_output=True, text=True, env=env, cwd=str(wt), timeout=30,
    )


def test_linked_worktree_hint_reads_main_coordination_ticket(tmp_path):
    wt = _linked_worktree_with_main_config(tmp_path)
    assert "0.5.0-W1-349" in context_of(_run_in_worktree(wt, tmp_path, isolation=False))


def test_linked_worktree_e1_isolation_reads_worktree_plane(tmp_path):
    wt = _linked_worktree_with_main_config(tmp_path)
    assert "0.5.0-W1-349" not in context_of(_run_in_worktree(wt, tmp_path, isolation=True))


def test_linked_worktree_e1_identity_old_code_misses_main_config(tmp_path, monkeypatch):
    """E1：lib.hook_base.get_shared_state_root 換成恆等函式（等於舊碼）後讀不到 MAIN 協調設定。"""
    wt = _linked_worktree_with_main_config(tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    module = load_module()
    assert "0.5.0-W1-349" in str(module.coordination_ticket(module.state_dir()))
    import lib.hook_base as hook_base

    monkeypatch.setattr(hook_base, "get_shared_state_root", lambda r=None: r)
    assert "0.5.0-W1-349" not in str(module.coordination_ticket(module.state_dir()))


def test_invalid_stdin_does_not_block_and_logs_traceback(tmp_path):
    result = run(tmp_path, "clear", stdin="not json")
    assert result.returncode == 0
    assert result.stdout == ""
    assert "[master-resume-hint] error" in result.stderr
    log = (tmp_path / "project" / ".claude" / "hook-logs" / "master-resume-hint" / "hook.log").read_text(encoding="utf-8")
    assert "Traceback" in log


# ---- 模組：名稱解析的兩條路徑與優先序 ----


@pytest.fixture
def mod(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "project"))
    return module


def fake_chain(monkeypatch, mod, start: int, chain: dict[int, tuple[str, int]]) -> None:
    """chain：pid → (執行檔名, 父 pid)；os.getppid() 回傳 start。"""
    monkeypatch.setattr(mod.os, "getppid", lambda: start)
    monkeypatch.setattr(mod, "process_comm", lambda pid: chain.get(pid, ("", 0))[0])
    monkeypatch.setattr(mod, "parent_pid", lambda pid: chain.get(pid, ("", None))[1])
    monkeypatch.setattr(mod, "is_alive_session", lambda data: True)


def test_ancestor_path_reads_nearest_claude_through_wrappers(tmp_path, monkeypatch, mod):
    """/clear 後檔內 sessionId 仍是舊的：沿 python → uv → sh → claude 找到 claude 祖先的檔。"""
    write_session(tmp_path / "home", "400", "主控", "old-id", pid=400)
    fake_chain(monkeypatch, mod, 100, {100: ("uv", 200), 200: ("/bin/sh", 400), 400: ("claude", 1)})
    assert mod.session_name(SESSION_ID) == "主控"


def test_ancestor_path_stops_at_first_claude(tmp_path, monkeypatch, mod):
    """E2 對照：最近的 claude 祖先沒有檔時停手，不得走到外層另一個 claude（主控以 claude -p 開的子 session）。"""
    write_session(tmp_path / "home", "900", "主控", "outer-id", pid=900)
    fake_chain(monkeypatch, mod, 100, {100: ("uv", 400), 400: ("claude", 800), 800: ("zsh", 900), 900: ("claude", 1)})
    assert mod.session_name(SESSION_ID) is None


def test_session_id_path_takes_priority_over_ancestor(tmp_path, monkeypatch, mod):
    """E2 對照：路徑 1 比對到非主控時，即使祖先檔名為主控也不採用（兩路徑不得取聯集或對調）。"""
    write_session(tmp_path / "home", "300", "看板工具", SESSION_ID, pid=300)
    write_session(tmp_path / "home", "400", "主控", "old-id", pid=400)
    fake_chain(monkeypatch, mod, 100, {100: ("claude", 1)})
    monkeypatch.setattr(mod.os, "getppid", lambda: 400)
    monkeypatch.setattr(mod, "process_comm", lambda pid: "claude")
    assert mod.session_name(SESSION_ID) == "看板工具"


def test_is_alive_session_compares_proc_start(monkeypatch, mod):
    monkeypatch.setattr(mod, "ps_field", lambda pid, field: "Sat Oct 31  06:58:39 2026")
    assert mod.is_alive_session({"pid": 5, "procStart": "Sat Oct 31 06:58:39 2026"})
    assert not mod.is_alive_session({"pid": 5, "procStart": "Fri Oct 30 06:58:39 2026"})
    monkeypatch.setattr(mod, "ps_field", lambda pid, field: None)
    assert not mod.is_alive_session({"pid": 5, "procStart": "Sat Oct 31 06:58:39 2026"})
