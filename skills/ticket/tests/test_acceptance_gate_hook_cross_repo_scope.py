"""acceptance-gate-hook 依 ticket 命令實際作用的 repo 判定（子 shell cd）。

session repo（主 checkout 與其 linked worktree）照常讀票判定；其他 repo 的
ticket 命令不讀 session repo 的同 ID 票，直接放行（其他 repo 由它自己的
session 與 hook 管）。目錄無法靜態解析時擋下。

阻擋條件以「未完成子票」構造：父票 children 指向一張 in_progress 子票。
本檔不設 HOOK_TEST_ISOLATION，hook 行程 cwd 落在 linked worktree 的組合
會實際走 get_shared_state_root 的回推路徑。
"""
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

TICKET_ID = "0.0.0-W1-900"
CHILD_ID = "0.0.0-W1-900.1"

PARENT_BODY = """---
id: {tid}
title: t
type: IMP
status: in_progress
version: 0.0.0
priority: P2
children:{children}
acceptance:
- '[x] a'
---

## Solution

x
"""

CHILD_BODY = """---
id: {cid}
title: c
type: IMP
status: in_progress
version: 0.0.0
priority: P2
parent_id: {tid}
acceptance:
- '[ ] a'
---
"""


def _load_hook_module():
    path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_xrepo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _tickets_dir(root: Path) -> Path:
    d = root / "docs" / "work-logs" / "v0.0.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_repo(path: Path, blocking: bool) -> Path:
    """建 repo，放 TICKET_ID；blocking 為真時附一張未完成子票（gate 會擋）。"""
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "CLAUDE.md").write_text("x", encoding="utf-8")
    d = _tickets_dir(path)
    children = f"\n- {CHILD_ID}" if blocking else " []"
    body = PARENT_BODY.format(tid=TICKET_ID, children=children)
    (d / f"{TICKET_ID}.md").write_text(body, encoding="utf-8")
    if blocking:
        (d / f"{CHILD_ID}.md").write_text(CHILD_BODY.format(cid=CHILD_ID, tid=TICKET_ID), encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    return path.resolve()


@pytest.fixture
def env(tmp_path, monkeypatch):
    _load_hook_module()  # 副作用：把 .claude 加入 sys.path 供 import lib
    from lib import hook_base

    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    hook_base.clear_project_root_cache()
    yield monkeypatch
    hook_base.clear_project_root_cache()


def _run(monkeypatch, session: Path, command: str, process_cwd: Path = None) -> int:
    """以 session 為 payload cwd 執行 main()；process_cwd 預設同 session。"""
    from lib import hook_base

    module = _load_hook_module()
    monkeypatch.chdir(process_cwd or session)
    hook_base.clear_project_root_cache()
    payload = {"tool_name": "Bash", "cwd": str(session), "tool_input": {"command": command}}
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "save_check_log"):
        try:
            return module.main()
        except SystemExit as exc:
            return exc.code


def test_direct_complete_blocked(env, tmp_path):
    """正向對照：在有未完成子票的 repo 直接 complete 應擋。"""
    repo = _make_repo(tmp_path / "a", blocking=True)
    assert _run(env, repo, f"ticket track complete {TICKET_ID}") == 2


def test_other_repo_not_blocked_by_session_ticket(env, tmp_path):
    """修正誤擋：session repo 同 ID 票會擋，complete 作用在他 repo 時放行。"""
    session = _make_repo(tmp_path / "session", blocking=True)
    other = _make_repo(tmp_path / "other", blocking=False)
    assert _run(env, session, f"(cd {other} && ticket track complete {TICKET_ID})") == 0


def test_other_repo_allowed_regardless_of_its_ticket(env, tmp_path):
    """他 repo 的票由它自己的 hook 管：即使他 repo 的同 ID 票會擋，本 hook 也放行。"""
    session = _make_repo(tmp_path / "session", blocking=False)
    other = _make_repo(tmp_path / "other", blocking=True)
    assert _run(env, session, f"(cd {other} && ticket track complete {TICKET_ID})") == 0


def test_other_repo_allowed_without_same_id_ticket(env, tmp_path):
    """session repo 沒有同 ID 票時，他 repo 的 complete 同樣放行。"""
    session = tmp_path / "session"
    session.mkdir()
    _git(session, "init", "-q")
    other = _make_repo(tmp_path / "other", blocking=True)
    assert _run(env, session.resolve(), f"(cd {other} && ticket track complete {TICKET_ID})") == 0


def test_same_repo_worktree_still_blocked(env, tmp_path):
    """同 repo：session 在主 checkout，子 shell cd 進 linked worktree complete，仍讀主倉庫票面並擋。"""
    main = _make_repo(tmp_path / "main", blocking=True)
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    assert _run(env, main, f"(cd {wt} && ticket track complete {TICKET_ID})") == 2


def test_process_cwd_in_worktree_effective_dir_other_repo(env, tmp_path):
    """hook 行程 cwd 在 session repo 的 linked worktree、命令作用在他 repo：放行，
    不會被 get_shared_state_root 蓋回 session 主倉庫而讀到會擋的同 ID 票。"""
    main = _make_repo(tmp_path / "main", blocking=True)
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    other = _make_repo(tmp_path / "other", blocking=False)
    rc = _run(env, wt, f"(cd {other} && ticket track complete {TICKET_ID})", process_cwd=wt)
    assert rc == 0


def test_unresolvable_dir_blocked(env, tmp_path, capsys):
    """目錄含變數無法靜態解析：擋下並要求改用字面路徑。"""
    session = _make_repo(tmp_path / "session", blocking=False)
    rc = _run(env, session, f'cd "$TARGET" && ticket track complete {TICKET_ID}')
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "字面絕對路徑" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_non_git_dir_keeps_previous_behavior(env, tmp_path):
    """cd 目標不在 git repo 內：沿用修改前讀 session repo 的判定。"""
    session = _make_repo(tmp_path / "session", blocking=True)
    plain = (tmp_path / "plain").resolve()
    plain.mkdir()
    assert _run(env, session, f"(cd {plain} && ticket track complete {TICKET_ID})") == 2
