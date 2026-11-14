"""
Test: path_permission / branch-verify / main-thread-edit-restriction 以目標檔所屬
checkout 為路徑相對化與 host 比對的根（情境 C：env=MAIN、cwd=WT）

以 subprocess 實際執行 hook（env CLAUDE_PROJECT_DIR=MAIN，行程 cwd 與 payload.cwd=WT），
decision 取自實際 stdout / exit code。每個測試自建 tmp repo，不碰真實主 repo。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR.parent))

from lib.path_permission import check_file_permission, normalize_path  # noqa: E402


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k != "HOOK_TEST_ISOLATION"}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e.com")
    env.update(extra)
    return env


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True, env=_clean_env())


def _init(path: Path, branch: str) -> Path:
    path.mkdir()
    _git(path, "init", "-q", "-b", branch)
    for rel in ("docs/a.md", "src/x.js", ".claude/hooks/h.py"):
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    return path


@pytest.fixture
def world(tmp_path):
    base = tmp_path.resolve()
    main = _init(base / "main", "main")
    wt = base / "wt"
    _git(main, "worktree", "add", "-q", "-b", "develop", str(wt))  # develop 為保護分支
    other = _init(base / "other", "main")
    return main, wt, other


def _run(hook, payload, env_root, cwd, tool="Edit"):
    """回傳 (exit code, decision, stderr, stdout)。"""
    payload = dict(payload)
    payload.setdefault("tool_name", tool)
    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / hook)], input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(cwd),
        env=_clean_env(CLAUDE_PROJECT_DIR=str(env_root)),
    )
    decision = None
    out = proc.stdout.strip()
    if out:
        try:
            data = json.loads(out)
            decision = (data.get("hookSpecificOutput", {}).get("permissionDecision")
                        or data.get("decision"))
        except json.JSONDecodeError:
            decision = "unparsed"
    return proc.returncode, decision, proc.stderr, out


def _payload(file_path, cwd, with_cwd=True):
    payload = {"tool_input": {"file_path": str(file_path)}}
    if with_cwd:
        payload["cwd"] = str(cwd)
    return payload


def _bv(file_path, main, cwd, with_cwd=True):
    return _run("branch-verify-hook.py", _payload(file_path, cwd, with_cwd), main, cwd)


def _mt(file_path, main, cwd, with_cwd=True):
    return _run("main-thread-edit-restriction-hook.py",
                _payload(file_path, cwd, with_cwd), main, cwd)


# ---------------- branch-verify ----------------

def test_bv_wt_exempt_path_allowed_in_scenario_c(world):
    # 舊碼：WT 檔對 MAIN host 判為跨專案，docs/ 不套本專案豁免而被擋
    main, wt, _ = world
    rc, decision, _, _ = _bv(wt / "docs" / "a.md", main, wt)
    assert (rc, decision) == (0, None)


def test_bv_wt_nonexempt_path_denied_as_same_repo(world):
    # E2 正向對照：WT 內應擋的編輯被擋，且走同 repo 訊息而非跨專案訊息
    main, wt, _ = world
    _, decision, _, out = _bv(wt / "src" / "x.js", main, wt)
    assert decision == "deny"
    assert "共用主工作樹禁止切換" in out


def test_bv_main_target_unchanged(world):
    main, wt, _ = world
    assert _bv(main / "docs" / "a.md", main, wt)[1] is None
    assert _bv(main / "src" / "x.js", main, wt)[1] == "deny"


def test_bv_other_repo_stays_cross_repo(world):
    main, wt, other = world
    _, decision, _, out = _bv(other / "docs" / "a.md", main, wt)
    assert decision == "deny"  # 通用豁免清單不含 docs/
    assert "共用主工作樹禁止切換" not in out


def test_bv_missing_cwd_no_get_action_root_stderr(world):
    main, wt, _ = world
    _, _, err, _ = _bv(wt / "docs" / "a.md", main, wt, with_cwd=False)
    assert "[get_action_root]" not in err


def test_bv_missing_file_path_no_get_action_root_stderr(world):
    main, wt, _ = world
    _, _, err, _ = _run("branch-verify-hook.py", {"tool_input": {}}, main, wt)
    assert "[get_action_root]" not in err


# ---------------- path_permission ----------------

def test_path_permission_wt_target_uses_owning_checkout(world, monkeypatch):
    main, wt, _ = world
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    target = str(wt / ".claude" / "hooks" / "h.py")
    assert normalize_path(target, str(wt)) == ".claude/hooks/h.py"
    assert normalize_path(target) == target  # 舊行為：對 MAIN 根相對化失敗


def test_path_permission_positive_control_blocked(world, monkeypatch):
    # E2：WT 內 src/ 程式檔以 WT 為根相對化後被禁止清單攔下
    main, wt, _ = world
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    allowed, _ = check_file_permission(str(wt / "src" / "x.js"), _Log(), str(wt))
    assert allowed is False
    allowed, _ = check_file_permission(str(wt / "docs" / "a.md"), _Log(), str(wt))
    assert allowed is True


# ---------------- main-thread-edit-restriction ----------------

def test_mt_main_target_src_blocked_in_scenario_c(world):
    main, wt, _ = world
    # E2 正向對照：WT 內應擋的編輯被擋；WT 內 docs/ 改為放行（舊碼 deny：相對化失敗）
    rc, decision, _, _ = _mt(wt / "src" / "x.js", main, wt)
    assert (rc, decision) == (2, "deny")
    rc, decision, _, _ = _mt(wt / "docs" / "a.md", main, wt)
    assert (rc, decision) == (0, "allow")


def test_mt_main_target_docs_allowed(world):
    main, wt, _ = world
    rc, decision, _, _ = _mt(main / "docs" / "a.md", main, wt)
    assert (rc, decision) == (0, "allow")


def test_mt_dispatch_warning_relativizes_against_target_checkout(world):
    # WT 內檔案對以相對路徑登記的派發紀錄命中；舊碼對 MAIN 根相對化失敗而無警告
    main, wt, _ = world
    (main / ".claude").mkdir(exist_ok=True)
    (main / ".claude" / "dispatch-active.json").write_text(json.dumps({"dispatches": [{
        "files": ["docs/a.md"], "agent_description": "d", "ticket_id": "T-1",
        "dispatched_at": "2999-01-01T00:00:00+00:00",
    }]}))
    _, decision, _, out = _mt(wt / "docs" / "a.md", main, wt)
    assert decision == "allow"
    assert "此檔案正在被背景代理人處理" in out


def test_mt_missing_cwd_no_get_action_root_stderr(world):
    main, wt, _ = world
    _, decision, err, _ = _mt(main / "docs" / "a.md", main, wt, with_cwd=False)
    assert "[get_action_root]" not in err
    assert decision == "allow"


# ---------------- NotebookEdit（notebook_path）----------------

def _nb(hook, notebook_path, main, cwd):
    payload = {"tool_name": "NotebookEdit", "cwd": str(cwd),
               "tool_input": {"notebook_path": str(notebook_path)}}
    return _run(hook, payload, main, cwd, tool="NotebookEdit")


def test_bv_notebook_path_wt_exempt_allowed(world):
    main, wt, _ = world
    rc, decision, _, _ = _nb("branch-verify-hook.py", wt / "docs" / "n.ipynb", main, wt)
    assert (rc, decision) == (0, None)


def test_bv_notebook_path_wt_nonexempt_denied(world):
    main, wt, _ = world
    _, decision, _, out = _nb("branch-verify-hook.py", wt / "src" / "n.ipynb", main, wt)
    assert decision == "deny"
    assert "共用主工作樹禁止切換" in out


def test_mt_notebook_path_dispatch_relativized_from_notebook_path(world):
    main, wt, _ = world
    (main / ".claude").mkdir(exist_ok=True)
    (main / ".claude" / "dispatch-active.json").write_text(json.dumps({"dispatches": [{
        "files": ["docs/n.ipynb"], "agent_description": "d", "ticket_id": "T-1",
        "dispatched_at": "2999-01-01T00:00:00+00:00",
    }]}))
    _, decision, _, out = _nb("main-thread-edit-restriction-hook.py",
                              wt / "docs" / "n.ipynb", main, wt)
    assert decision == "allow"
    assert "此檔案正在被背景代理人處理" in out


# ---------------- 失敗語意（實測，見票 Solution〈失敗語意〉）----------------

def test_failure_owning_root_none_branch_verify_falls_back(world, tmp_path):
    # 觸發條件：目標在無 .git 祖先的目錄 -> owning_checkout_root=None，退回 get_action_root(cwd=WT)
    main, wt, _ = world
    outside = tmp_path.resolve().parent / "no_repo_dir" / "docs" / "a.md"
    rc, decision, _, _ = _bv(outside, main, wt)
    assert rc == 0 and decision is None  # 非專案檔案：放行（不輸出 decision）


def test_failure_owning_root_none_main_thread_falls_back(world, tmp_path):
    main, wt, _ = world
    outside = tmp_path.resolve().parent / "no_repo_dir" / "docs" / "a.md"
    rc, decision, _, _ = _mt(outside, main, wt)
    assert (rc, decision) == (2, "deny")  # 預設拒絕（非白名單路徑）


def _load(name, fname):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _boom(*a, **k):
    raise RuntimeError("boom")


def test_failure_helper_raises_main_thread_keeps_deny(world, monkeypatch, capsys):
    # 觸發條件：get_target_root（含 get_action_root）拋例外；main-thread 沿用原根，
    # 判定同修改前（WT/src/x.js 仍 deny exit 2），並寫 stderr
    import io
    from unittest.mock import patch
    main, wt, _ = world
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    payload = json.dumps({"tool_name": "Edit", "cwd": str(wt),
                          "tool_input": {"file_path": str(wt / "src" / "x.js")}})
    mt = _load("mt_fail", "main-thread-edit-restriction-hook.py")
    with patch("sys.stdin", io.StringIO(payload)), \
            patch.object(mt, "is_subagent_environment", return_value=False), \
            patch.object(mt, "get_project_root", return_value=str(wt)), \
            patch.object(mt, "get_target_root", _boom):
        rc = mt.main()
    cap = capsys.readouterr()
    assert rc == mt.EXIT_BLOCK and '"deny"' in cap.out
    assert "get_target_root 失敗" in cap.err


def test_failure_helper_raises_branch_verify_fails_closed(world, monkeypatch, capsys):
    # 觸發條件：同上；branch-verify 由 run_hook_safely(fail_closed=True) 包裝 -> deny
    import io
    from unittest.mock import patch
    main, wt, _ = world
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    payload = json.dumps({"tool_name": "Edit", "cwd": str(wt),
                          "tool_input": {"file_path": str(wt / "src" / "x.js")}})
    bv = _load("bv_fail", "branch-verify-hook.py")
    with patch("sys.stdin", io.StringIO(payload)), patch.object(bv, "get_target_root", _boom):
        rc = bv.run_hook_safely(bv.main, "branch-verify", fail_closed=True)
    out = capsys.readouterr().out
    assert '"deny"' in out or rc != 0
    print("FAILSEM bv rc=%s out=%s" % (rc, out[:120]))
