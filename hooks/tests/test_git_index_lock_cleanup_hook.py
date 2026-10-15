"""
Unit tests for git-index-lock-cleanup-hook.

Source: 0.18.0-W17-194 — 強化 lock 殘留警告訊息加入 GUI app 外部進程偵測
Related: PC-139 (git-index-lock-source-misattribution-gui-app-fork)
"""

import importlib.util
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / "git-index-lock-cleanup-hook.py"


@pytest.fixture(scope="module")
def hook_module():
    sys.path.insert(0, str(HOOK_PATH.parent))
    sys.path.insert(0, str(HOOK_PATH.parent.parent))
    spec = importlib.util.spec_from_file_location(
        "git_index_lock_cleanup_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_lock(tmp_path):
    """建立一個 .git/index.lock 模擬剛產生的 lock（lock_age < threshold）。"""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    lock = git_dir / "index.lock"
    lock.write_text("")
    return tmp_path, lock


# 調整說明（0.5.0-W1-164.4.1）：新鎖改為只寫日誌、不回傳訊息也不寫 stderr，
# 原三則對回傳 msg 的斷言改讀日誌（PC-139 排查文字內容不變，載體由 stderr 改為日誌）。
def _young_lock_log(hook_module, project_root, caplog):
    with patch.object(hook_module, "get_project_root", return_value=str(project_root)):
        with caplog.at_level(logging.INFO, logger="test"):
            msg = hook_module.check_and_cleanup_index_lock(logging.getLogger("test"))
    assert msg is None
    return caplog.text


def test_fresh_lock_message_contains_gui_app_names(hook_module, fresh_lock, caplog):
    """日誌必須包含 4 個 GUI app 名稱（Fork / GitKraken / SourceTree / VS Code）。"""
    text = _young_lock_log(hook_module, fresh_lock[0], caplog)
    for name in ("Fork", "GitKraken", "SourceTree", "VS Code"):
        assert name in text, f"日誌缺少 GUI app 名稱: {name}"


def test_fresh_lock_message_contains_ps_aux_detection(hook_module, fresh_lock, caplog):
    text = _young_lock_log(hook_module, fresh_lock[0], caplog)
    assert re.search(r"ps\s+aux\s*\|\s*grep", text), "日誌缺少 ps aux | grep 偵測指令"
    assert re.search(r"Fork\|GitKraken\|SourceTree", text), "日誌缺少 GUI app pattern"


def test_fresh_lock_message_contains_pc139_reference(hook_module, fresh_lock, caplog):
    text = _young_lock_log(hook_module, fresh_lock[0], caplog)
    assert "PC-139-git-index-lock-source-misattribution-gui-app-fork" in text


def test_no_lock_returns_none(hook_module, tmp_path):
    """無 lock 檔時應回傳 None。"""
    (tmp_path / ".git").mkdir()
    with patch.object(hook_module, "get_project_root", return_value=str(tmp_path)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)
    assert msg is None


def test_stale_lock_auto_removed(hook_module, tmp_path):
    """過期 lock 自動移除，訊息含 IMP-046 標記。"""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    lock = git_dir / "index.lock"
    lock.write_text("")
    # 將 mtime 設為遠超過 STALE_THRESHOLD_SECONDS
    old_time = time.time() - (hook_module.STALE_THRESHOLD_SECONDS + 60)
    os.utime(lock, (old_time, old_time))

    with patch.object(hook_module, "get_project_root", return_value=str(tmp_path)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)

    assert msg is not None
    assert "IMP-046" in msg
    assert not lock.exists(), "過期 lock 應被自動移除"


# ---- 0.5.0-W1-164.2：linked worktree 與三項刪除條件 ----

import logging
import subprocess


def _sh(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def wt(tmp_path):
    """tmp repo + linked worktree；回傳 (worktree 路徑, 其 index.lock 路徑)。"""
    main = tmp_path / "main"
    main.mkdir()
    _sh(main, "init", "-q")
    _sh(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
    w = tmp_path / "wt"
    _sh(main, "worktree", "add", "-q", str(w), "-b", "wtb")
    r = subprocess.run(["git", "-C", str(w), "rev-parse", "--git-path", "index.lock"],
                       capture_output=True, text=True, check=True)
    lock = Path(r.stdout.strip())
    if not lock.is_absolute():
        lock = w / lock
    return w, lock


def _run(hook_module, root):
    with patch.object(hook_module, "get_project_root", return_value=str(root)):
        return hook_module.check_and_cleanup_index_lock(logging.getLogger("test"))


def _age(lock, hook_module):
    t = time.time() - (hook_module.STALE_THRESHOLD_SECONDS + 60)
    os.utime(lock, (t, t))


def test_worktree_lock_path_is_under_worktrees_dir(hook_module, wt):
    w, lock = wt
    assert "worktrees" in lock.parts
    assert Path(hook_module.resolve_lock_path(str(w), logging.getLogger("test"))).resolve() == lock.resolve()


def test_worktree_stale_empty_lock_removed(hook_module, wt):
    w, lock = wt
    lock.write_text("")
    _age(lock, hook_module)
    msg = _run(hook_module, w)
    assert msg and "IMP-046" in msg
    assert not lock.exists()


def test_worktree_nonempty_lock_kept(hook_module, wt):
    w, lock = wt
    lock.write_text("x")
    _age(lock, hook_module)
    msg = _run(hook_module, w)
    assert msg and "非 0 位元組" in msg
    assert lock.exists()


def test_worktree_young_lock_kept(hook_module, wt):
    w, lock = wt
    lock.write_text("")
    msg = _run(hook_module, w)
    assert msg is None  # 調整：新鎖不再回傳訊息（只寫日誌）
    assert lock.exists()


def test_worktree_lock_held_by_process_kept(hook_module, wt):
    """liveness：真實行程持有鎖檔時不得刪除。"""
    w, lock = wt
    lock.write_text("")
    _age(lock, hook_module)
    holder = subprocess.Popen(["tail", "-f", str(lock)], stdout=subprocess.DEVNULL)
    try:
        time.sleep(0.5)
        msg = _run(hook_module, w)
    finally:
        holder.kill()
        holder.wait()
    assert msg is None  # 調整：確定有持有者屬正常狀態，只寫日誌
    assert lock.exists()


def test_lsof_unavailable_fails_safe(hook_module, wt):
    """失敗語意：無法判定持有者時不刪。"""
    w, lock = wt
    lock.write_text("")
    _age(lock, hook_module)
    # 調整：上溯取代 rev-parse 後 subprocess.run 只剩 lsof，side_effect 改為單一 OSError
    with patch.object(hook_module.subprocess, "run", side_effect=OSError("no lsof")):
        msg = _run(hook_module, w)
    assert msg and "不自動移除" in msg
    assert lock.exists()


# ---- 合併前追修：payload cwd、刪除前複核、lsof 判定、解析失敗記錄 ----

import json


def _aged_empty(lock, hook_module):
    lock.write_text("")
    _age(lock, hook_module)


def test_payload_cwd_beats_env_real_stdin(hook_module, wt, tmp_path):
    """env 指主 repo、payload cwd 為 worktree：清 worktree 的鎖，主 repo 的鎖不動（真實 stdin）。"""
    w, wlock = wt
    main = tmp_path / "main"
    mlock = main / ".git" / "index.lock"
    _aged_empty(wlock, hook_module)
    _aged_empty(mlock, hook_module)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git add x"}, "cwd": str(w)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(main))
    r = subprocess.run(
        ["python3", str(HOOK_PATH)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert not wlock.exists(), "worktree 的鎖應被清"
    assert mlock.exists(), "主 repo 的鎖不得被動"


def test_lock_replaced_during_lsof_not_removed(hook_module, wt):
    w, lock = wt
    _aged_empty(lock, hook_module)

    def swap(path, logger):
        os.remove(path)
        with open(path, "w"):
            pass
        return False

    # 調整：cleanup_lock 改呼叫 lsof_state（三態），swap 回傳 'free'
    with patch.object(hook_module, "lsof_state", side_effect=lambda p, l: "free" if not swap(p, l) else "held"):
        msg = _run(hook_module, w)
    assert lock.exists(), "新 inode 的鎖不得被刪"
    assert msg and "被替換" in msg


@pytest.mark.parametrize("rc,out,err,held", [
    (1, "", "", False),
    (1, "", "lsof: WARNING", True),
    (2, "", "", True),
    (0, "123\n", "", True),
    (127, "", "", True),
])
def test_lsof_result_matrix(hook_module, rc, out, err, held):
    cp = subprocess.CompletedProcess([], rc, stdout=out, stderr=err)
    with patch.object(hook_module.subprocess, "run", return_value=cp):
        assert hook_module.is_held_by_process("/x", logging.getLogger("test")) is held


def test_lsof_timeout_treated_as_held(hook_module):
    with patch.object(hook_module.subprocess, "run",
                      side_effect=subprocess.TimeoutExpired("lsof", 5)):
        assert hook_module.is_held_by_process("/x", logging.getLogger("test")) is True


def test_rev_parse_failure_logged_and_falls_back(hook_module, tmp_path, caplog):
    # 調整：退路只在 .git 檔解析不了時啟用（非 repo 改為靜默回 None）
    (tmp_path / ".git").write_text("garbage\n")
    with caplog.at_level(logging.WARNING, logger="test"):
        with patch.object(hook_module.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("git", 5)):
            p = hook_module.resolve_lock_path(str(tmp_path), logging.getLogger("test"))
    assert p == str(tmp_path / ".git" / "index.lock")
    assert "無法解析" in caplog.text


def test_fresh_lock_logs_resolved_path_without_stderr(hook_module, wt, capsys, caplog):
    """調整：新鎖日誌含解析後路徑，stderr 靜默（E1 對照見下方過期鎖測試）。"""
    w, lock = wt
    lock.write_text("")
    with caplog.at_level(logging.INFO, logger="test"):
        _run(hook_module, w)
    assert str(lock) in caplog.text
    assert capsys.readouterr().err == ""


# ---- 0.5.0-W1-164.4.1：目標集合、每次 Bash 檢查、線索記錄 ----

import shutil


def _mk_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _sh(path, "init", "-q")
    return path


def _stale(repo):
    lock = Path(repo) / ".git" / "index.lock"
    lock.write_text("")
    t = time.time() - 120
    os.utime(lock, (t, t))
    return lock


def _hook(payload, project_dir, cwd_env=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    return subprocess.run(["python3", str(HOOK_PATH)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=60)


@pytest.fixture
def two_repos(tmp_path):
    mine = _mk_repo(tmp_path / "mine")
    (mine / ".claude").mkdir()
    other = _mk_repo(tmp_path / "other")
    return mine, other


def _evidence(repo):
    f = Path(repo) / ".claude" / "hook-logs" / "git-index-lock-cleanup" / "index-lock-evidence.txt"
    return f.read_text().splitlines() if f.exists() else []


@pytest.mark.parametrize("cmd_tpl", [
    "git add x",
    "git commit -m m",
    "git -C {other} add x",
    "git -C ../other add x",
    "ticket track commit T-1 -m m --worktree {other} -- f",
    "ticket track commit T-1 -m m --worktree={other} -- f",
    "echo hello",
])
def test_stale_lock_cleaned_per_command_shape(two_repos, cmd_tpl):
    """閘門各列：cwd / -C 絕對 / -C 相對 / --worktree 兩形 / 不含 git 字樣。"""
    mine, other = two_repos
    target = mine if ("{other}" not in cmd_tpl and "../other" not in cmd_tpl) else other
    lock = _stale(target)
    cmd = cmd_tpl.format(other=other)
    r = _hook({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(mine)}, mine)
    assert r.returncode == 0, r.stderr
    assert not lock.exists(), f"{cmd} 應清除 {lock}"


def test_dash_c_other_repo_without_flag_keeps_other_lock(two_repos):
    """對照（E1）：不帶 -C 時他 repo 的鎖不動。"""
    mine, other = two_repos
    lock = _stale(other)
    _hook({"tool_name": "Bash", "tool_input": {"command": "git add x"}, "cwd": str(mine)}, mine)
    assert lock.exists()


def test_other_repo_gets_no_new_files(two_repos):
    """寫入設限：清他 repo 的鎖後，該 repo 不得新增任何檔案；線索寫回本專案。"""
    mine, other = two_repos
    lock = _stale(other)
    before = {p for p in other.rglob("*")}
    r = _hook({"tool_name": "Bash", "tool_input": {"command": f"git -C {other} add x"},
               "cwd": str(mine), "session_id": "S1"}, mine)
    assert r.returncode == 0, r.stderr
    after = {p for p in other.rglob("*")}
    assert after == before - {lock}
    assert not lock.exists()
    assert not (other / ".claude").exists()
    lines = _evidence(mine)
    assert len(lines) == 1 and str(lock) in lines[0]


def test_evidence_fields_and_secret_masking(two_repos):
    mine, _ = two_repos
    lock = _stale(mine)
    cmd = "API_TOKEN=abc123 git add x # Bearer zzz"
    _hook({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(mine),
           "session_id": "S2"}, mine)
    line = _evidence(mine)[0]
    assert line.startswith("IDXLOCK-EVIDENCE ")
    for key in ("ts=", "lock_path=", "size=0", "lock_mtime=", "hook_cwd=", "found_by_cmd=",
                "index_mtime=", "reflog_new=", "reflog_last_ts=", "loadavg_1m=", "session_id=S2"):
        assert key in line, key
    assert "abc123" not in line and "zzz" not in line
    assert not lock.exists()


def test_evidence_in_main_repo_when_run_in_worktree(wt, tmp_path):
    """linked worktree 內執行：鎖在 worktree gitdir，線索進主倉。"""
    w, lock = wt
    lock.write_text("")
    t = time.time() - 120
    os.utime(lock, (t, t))
    main = tmp_path / "main"
    r = subprocess.run(["python3", str(HOOK_PATH)], capture_output=True, text=True, timeout=60,
                       input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"},
                                         "cwd": str(w)}),
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=str(w)))
    assert r.returncode == 0, r.stderr
    assert not lock.exists()
    assert len(_evidence(main)) == 1
    assert not (w / ".claude" / "hook-logs" / "git-index-lock-cleanup" / "index-lock-evidence.txt").exists()


def test_fresh_lock_silent_stderr_vs_stale_stderr(two_repos):
    """E1 對照：同命令，新鎖 stderr 為空；過期鎖有 IMP-046 stderr。"""
    mine, _ = two_repos
    lock = mine / ".git" / "index.lock"
    lock.write_text("")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git add x"}, "cwd": str(mine)}
    assert _hook(payload, mine).stderr.strip() == ""
    assert lock.exists()
    t = time.time() - 120
    os.utime(lock, (t, t))
    assert "IMP-046" in _hook(payload, mine).stderr


def test_non_git_command_does_not_import_git_command_parse(two_repos):
    """子程序內執行 hook 後檢查 sys.modules（不受 pytest 行程其他測試影響）。"""
    mine, _ = two_repos
    code = (
        "import sys, runpy, json, io\n"
        "sys.stdin = io.StringIO(json.dumps({'tool_name':'Bash','tool_input':{'command':'echo hi'},'cwd':%r}))\n"
        "try:\n    runpy.run_path(%r, run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        "sys.stderr.write('IMPORTED=' + str('lib.git_command_parse' in sys.modules))\n"
    ) % (str(mine), str(HOOK_PATH))
    r = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=str(mine)))
    assert "IMPORTED=False" in r.stderr, r.stderr


def test_dash_c_nonexistent_dir_no_error(two_repos):
    mine, _ = two_repos
    r = _hook({"tool_name": "Bash", "tool_input": {"command": "git -C /no/such/dir add x"},
               "cwd": str(mine)}, mine)
    assert r.returncode == 0 and r.stderr.strip() == ""


def test_evidence_write_failure_does_not_block_cleanup(hook_module, two_repos, capsys):
    mine, _ = two_repos
    lock = _stale(mine)
    with patch.object(hook_module, "get_project_root", return_value=str(mine)), \
         patch.object(hook_module, "build_evidence_line", side_effect=RuntimeError("boom")):
        msg = hook_module.check_and_cleanup_index_lock(logging.getLogger("test"), str(mine), "git add x")
    assert msg and "IMP-046" in msg
    assert not lock.exists()
    assert "線索記錄失敗" in capsys.readouterr().err


def test_main_root_resolution(hook_module, tmp_path):
    root = tmp_path / "plain"
    (root / ".git").mkdir(parents=True)
    assert hook_module.find_main_root(str(root)) == str(root)


def _worktree_with_commondir(tmp_path, common_name):
    """主倉 gitdir 名為 common_name 的 linked worktree 佈局（手工構造）。"""
    common = tmp_path / "m" / common_name
    gd = common / "worktrees" / "w"
    gd.mkdir(parents=True)
    (gd / "commondir").write_text("../..\n")
    w = tmp_path / "w"
    w.mkdir()
    (w / ".git").write_text(f"gitdir: {gd}\n")
    return w, gd


def test_commondir_basename_not_dotgit_is_unresolved(hook_module, tmp_path):
    w, _ = _worktree_with_commondir(tmp_path, "repo.git")
    assert hook_module.find_main_root(str(w)) is None


def test_commondir_dotgit_resolves_main_root(hook_module, tmp_path):
    w, _ = _worktree_with_commondir(tmp_path, ".git")
    assert hook_module.find_main_root(str(w)) == str(tmp_path / "m")


def test_unresolved_main_root_writes_fallback_note(hook_module, tmp_path):
    """主倉推不到：線索寫到專案根並註記 evidence_location=fallback。"""
    w, gd = _worktree_with_commondir(tmp_path, "repo.git")
    lock = gd / "index.lock"
    lock.write_text("")
    t0 = time.time() - 120
    os.utime(lock, (t0, t0))
    with patch.object(hook_module, "get_project_root", return_value=str(w)):
        msg = hook_module.check_and_cleanup_index_lock(logging.getLogger("test"), str(w), "x")
    assert msg and not lock.exists()
    lines = _evidence(w)
    assert len(lines) == 1 and "evidence_location=" in lines[0] and "fallback" in lines[0]


def test_duplicate_targets_deduped(hook_module, two_repos):
    mine, _ = two_repos
    lock = _stale(mine)
    with patch.object(hook_module, "get_project_root", return_value=str(mine)):
        hook_module.check_and_cleanup_index_lock(
            logging.getLogger("test"), str(mine), f"git -C {mine} add x && git add y")
    assert not lock.exists()
    assert len(_evidence(mine)) == 1


def test_already_removed_by_peer_is_silent(hook_module, two_repos, capsys):
    mine, _ = two_repos
    lock = _stale(mine)
    real_remove = os.remove
    def racing(path):
        real_remove(path)
        raise FileNotFoundError(path)
    with patch.object(hook_module, "get_project_root", return_value=str(mine)), \
         patch.object(hook_module.os, "remove", side_effect=racing):
        msg = hook_module.check_and_cleanup_index_lock(logging.getLogger("test"), str(mine), "x")
    assert msg is None
    assert "IMP-046" not in capsys.readouterr().err


# ---- 覆核修正：非 repo 靜默、損壞 .git 檔走退路、網址帳密遮罩 ----

def _spy_run_code(hook, payload, project_dir):
    """子程序執行 hook，並記錄 subprocess.run 是否被呼叫。"""
    return (
        "import sys, runpy, json, io, subprocess\n"
        "calls=[]\n_orig=subprocess.run\n"
        "def _spy(*a, **k):\n    calls.append(a[0] if a else k.get('args'))\n    return _orig(*a, **k)\n"
        "subprocess.run=_spy\n"
        "sys.stdin=io.StringIO(%r)\n"
        "try:\n    runpy.run_path(%r, run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        "sys.stderr.write('GITCALLS=' + str(sum(1 for c in calls if c and c[0]=='git')))\n"
    ) % (json.dumps(payload), str(hook))


def _run_spy(payload, project_dir):
    r = subprocess.run(["python3", "-c", _spy_run_code(HOOK_PATH, payload, project_dir)],
                       capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir)))
    return r


def test_non_repo_cwd_is_silent_and_hook_spawns_no_git(tmp_path, two_repos):
    """間諜只攔 hook 自身的 subprocess.run；共用程式庫啟動時的 git 呼叫不在守住範圍內。"""
    mine, _ = two_repos
    plain = tmp_path / "plain"
    plain.mkdir()
    r = _run_spy({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(plain)}, mine)
    assert "WARNING" not in r.stderr and "GITCALLS=0" in r.stderr, r.stderr


def test_dash_c_non_repo_dir_is_silent_and_hook_spawns_no_git(tmp_path, two_repos):
    """同上：只守住 hook 自身不起 git。"""
    mine, _ = two_repos
    plain = tmp_path / "plain2"
    plain.mkdir()
    r = _run_spy({"tool_name": "Bash", "tool_input": {"command": f"git -C {plain} status"},
                  "cwd": str(mine)}, mine)
    assert "WARNING" not in r.stderr and "GITCALLS=0" in r.stderr, r.stderr


def test_corrupt_dotgit_file_takes_fallback_with_record(tmp_path, two_repos):
    """對照：同一方法下，內容損壞的 .git 檔確實走到 rev-parse 退路並有記錄。"""
    mine, _ = two_repos
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / ".git").write_text("garbage\n")
    r = _run_spy({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(bad)}, mine)
    assert "GITCALLS=1" in r.stderr and "無法解析 index.lock 路徑" in r.stderr, r.stderr


def test_url_credentials_masked(hook_module):
    out = hook_module.sanitize_command("git clone https://user:s3cret@host/x.git")
    assert "s3cret" not in out and "https://user:***@host/x.git" in out


@pytest.mark.parametrize("cmd,secret", [
    ("curl -u user:pass1234 http://h", "pass1234"),
    ("curl -H 'Authorization: token abc123xyz' http://h", "abc123xyz"),
    ("curl -H 'X-Api-Key: k3y valu3' http://h", "k3y valu3"),
    ("tool --password hunter2 run", "hunter2"),
    ("gh --with-token ghtoken99 x", "ghtoken99"),
    ("mysql -psecretpw db", "secretpw"),
    ("git clone https://TOKEN123@host/x.git", "TOKEN123"),
    ("echo ghp_abcdefgh12345678", "abcdefgh12345678"),
    ('API_TOKEN="a b c" run', "b c"),
])
def test_secret_forms_masked(hook_module, cmd, secret):
    out = hook_module.sanitize_command(cmd)
    assert secret not in out and "***" in out, out


@pytest.mark.parametrize("cmd", [
    "git cat-file -t " + "a1b2c3d4" * 5,
    "uv run pytest tests/" + "x" * 32 + ".py",
    "git log --author 'A <a@b>'",
    "git log --author=alice --author-date-order",
])
def test_locating_info_preserved(hook_module, cmd):
    assert hook_module.sanitize_command(cmd) == cmd


def test_non_secret_command_unchanged(hook_module):
    cmd = "mkdir -p a/b && git -C /x status"
    assert hook_module.sanitize_command(cmd) == cmd


# ---- 審查修正 A-D 與測試補強 ----

def test_evidence_file_survives_log_retention_cleanup(hook_module, two_repos):
    """A：以實際的共用清理函式驗證線索檔不被刪；對照：8 天前的 .log 被刪。"""
    from lib.hook_logging import _cleanup_old_logs
    mine, _ = two_repos
    _stale(mine)
    with patch.object(hook_module, "get_project_root", return_value=str(mine)):
        hook_module.check_and_cleanup_index_lock(logging.getLogger("test"), str(mine), "x")
    log_dir = mine / ".claude" / "hook-logs" / "git-index-lock-cleanup"
    ev = log_dir / hook_module.EVIDENCE_FILENAME
    old_log = log_dir / "old.log"
    old_log.write_text("x")
    old = time.time() - 8 * 86400
    for f in (ev, old_log):
        os.utime(f, (old, old))
    _cleanup_old_logs(log_dir)
    assert ev.exists()
    assert not old_log.exists()


def test_evidence_written_before_remove(hook_module, two_repos):
    """B：os.remove 被呼叫的當下線索行已存在（先記後刪）。"""
    mine, _ = two_repos
    lock = _stale(mine)
    seen = {}
    real_remove = os.remove

    def checking_remove(path):
        seen["lines"] = len(_evidence(mine))
        real_remove(path)

    with patch.object(hook_module, "get_project_root", return_value=str(mine)), \
         patch.object(hook_module.os, "remove", side_effect=checking_remove):
        hook_module.check_and_cleanup_index_lock(logging.getLogger("test"), str(mine), "x")
    assert seen.get("lines") == 1
    assert not lock.exists()


def test_lsof_unknown_warns_but_held_is_silent(hook_module, wt, capsys):
    """D：確定持有只寫日誌；無法判定維持 WARNING。"""
    w, lock = wt
    _aged_empty(lock, hook_module)
    with patch.object(hook_module, "lsof_state", return_value="held"):
        assert _run(hook_module, w) is None
    assert capsys.readouterr().err == ""
    with patch.object(hook_module, "lsof_state", return_value="unknown"):
        msg = _run(hook_module, w)
    assert msg and "無法判定" in msg
    assert lock.exists()


def test_worktree_option_only_taken_from_ticket_commit_statement(hook_module):
    f = hook_module._worktree_values
    assert f(["ticket", "track", "commit", "T", "--worktree", "/a"]) == ["/a"]
    assert f(["ticket", "track", "commit", "T", "--worktree=/b"]) == ["/b"]
    assert f(["git", "worktree", "add", "--worktree", "/c"]) == []
    assert f(["ticket", "track", "claim", "T", "--worktree", "/d"]) == []


def test_git_word_command_does_load_parser(two_repos):
    """正向對照：命令含 git 字樣時確實載入解析器（子程序內檢查）。"""
    mine, _ = two_repos
    code = (
        "import sys, runpy, json, io\n"
        "sys.stdin = io.StringIO(json.dumps({'tool_name':'Bash','tool_input':{'command':'git status'},'cwd':%r}))\n"
        "try:\n    runpy.run_path(%r, run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        "sys.stderr.write('IMPORTED=' + str('lib.git_command_parse' in sys.modules))\n"
    ) % (str(mine), str(HOOK_PATH))
    r = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=str(mine)))
    assert "IMPORTED=True" in r.stderr, r.stderr


def test_repo_cwd_without_lock_hook_spawns_no_git(two_repos):
    """無鎖常態路徑（cwd 為 repo、無鎖）：hook 自身不起 git，stderr 為空。"""
    mine, _ = two_repos
    r = _run_spy({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(mine)}, mine)
    assert "GITCALLS=0" in r.stderr and "WARNING" not in r.stderr, r.stderr
