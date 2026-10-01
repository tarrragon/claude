"""單一路徑隔離提交的 CAS 重試與檔案日誌（0.4.1-W1-026）。

競爭構造：包裝 git_ops._prevalidate_guard_env（update-ref 前一刻呼叫），
在其中由另一個 commit 推進 HEAD，使 update-ref 的 old_head 過期。
E1 對照：同 fixture 無競爭時不重試、不寫日誌。
"""
import re
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import git_ops, git_utils

_TID = "0.0.0-W0-001"
_LOG_DIR = Path(".claude") / "hook-logs" / "ticket-commit-retry"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _read_log(repo: Path) -> str:
    d = repo / _LOG_DIR
    return "".join(p.read_text() for p in sorted(d.glob("*.log"))) if d.exists() else ""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    md = tmp_path / f"{_TID}.md"
    md.write_text("v1\n")
    _git(tmp_path, "add", md.name)
    _git(tmp_path, "commit", "-q", "-m", "init")
    md.write_text("v2\n")
    # conftest 預設把日誌導向 tmp；本檔要驗 repo 內的預設相對位置
    monkeypatch.setattr(git_utils, "_RETRY_LOG_DIR", str(_LOG_DIR))
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BACKOFF_SECONDS", (0.01,))
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 1.0)
    monkeypatch.setattr(git_utils, "_COMMIT_MIN_RETRIES", 1)
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_WALL_CAP_SECONDS", 1.0)
    real_sleep = git_ops.time.sleep
    # 全域 time.sleep 僅縮短真實等待（不推進任何假時鐘），故不影響假時鐘測試；
    # 重試迴圈的等待走 git_utils._sleep 接縫，同樣縮短。
    monkeypatch.setattr(git_ops.time, "sleep", lambda s: real_sleep(min(s, 0.01)))
    monkeypatch.setattr(git_utils, "_sleep", lambda s: real_sleep(min(s, 0.01)))
    return tmp_path


def _advance_head_times(monkeypatch, repo: Path, times: int) -> None:
    """update-ref 前一刻由他方 commit 推進 HEAD，共 ``times`` 次。"""
    original = git_ops._prevalidate_guard_env
    state = {"n": 0}

    def racing(repo_root, commit_sha, old_head):
        if state["n"] < times:
            state["n"] += 1
            other = repo / f"other-{state['n']}.txt"
            other.write_text("x\n")
            _git(repo, "add", other.name)
            _git(repo, "commit", "-q", "-m", f"competing {state['n']}")
        return original(repo_root, commit_sha, old_head)

    monkeypatch.setattr(git_ops, "_prevalidate_guard_env", racing)


def _run(repo: Path):
    return git_utils.auto_commit_ticket_md_with_retry(
        str(repo / f"{_TID}.md"), _TID, "Solution"
    )


def test_control_no_race_no_retry_no_log(repo):
    result = _run(repo)
    assert result["status"] == "committed"
    assert result["attempts"] == 1
    assert _read_log(repo) == ""


def test_head_advanced_retries_and_commit_content_correct(repo, monkeypatch):
    _advance_head_times(monkeypatch, repo, 1)
    result = _run(repo)
    assert result["status"] == "committed"
    assert result["attempts"] == 2
    assert _git(repo, "show", f"HEAD:{_TID}.md") == "v2\n"
    # 他方提交仍在歷史中，重試提交疊在其上
    assert _git(repo, "log", "--format=%s", "-3").splitlines()[1] == "competing 1"
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == [f"{_TID}.md"]


def test_retry_event_logged_with_fields(repo, monkeypatch):
    _advance_head_times(monkeypatch, repo, 1)
    _run(repo)
    log = _read_log(repo)
    assert re.search(r"retry .*ticket=" + re.escape(_TID), log)
    assert "reason=cas_rejected" in log
    assert re.search(r"waited_s=\d+(\.\d+)?", log)
    assert re.search(r"attempt=1\b", log)


def test_cas_rejection_does_not_sleep_inside_single_git_call(repo, monkeypatch):
    """CAS 拒絕以同一 old_head 內層重試必敗，不應在內層睡眠。"""
    sleeps = []
    monkeypatch.setattr(git_ops.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(git_utils, "_sleep", lambda s: sleeps.append(s))
    _advance_head_times(monkeypatch, repo, 1)
    _run(repo)
    assert 1 not in sleeps  # _RETRY_WAIT_SECONDS 的內層等待


def test_residual_ref_lock_exhausts_logs_and_reports(repo, capsys):
    lock = repo / ".git" / "refs" / "heads" / "main.lock"
    lock.write_text("residue\n")
    failed = git_utils.commit_ticket_md_reporting(
        "append-log", str(repo / f"{_TID}.md"), _TID, "Solution"
    )
    assert failed is True
    log = _read_log(repo)
    assert "final_failure" in log
    assert "main.lock" in log
    assert re.search(r"attempt=\d+", log)
    assert re.search(r"waited_s=\d+(\.\d+)?", log)


def test_control_no_lock_writes_no_failure_record(repo):
    failed = git_utils.commit_ticket_md_reporting(
        "append-log", str(repo / f"{_TID}.md"), _TID, "Solution"
    )
    assert failed is False
    assert "final_failure" not in _read_log(repo)


def test_exhausted_stderr_lists_path_and_remedy(repo, monkeypatch, capsys):
    _advance_head_times(monkeypatch, repo, 10_000)
    failed = git_utils.commit_ticket_md_reporting(
        "append-log", str(repo / f"{_TID}.md"), _TID, "Solution"
    )
    err = capsys.readouterr().err
    assert failed is True
    assert str(repo / f"{_TID}.md") in err
    assert f"git add {repo / (_TID + '.md')}" in err
    assert "git commit" in err
    assert "ticket track commit" in err
    assert "final_failure" in _read_log(repo)


def test_log_write_failure_goes_to_stderr_and_keeps_commit_result(repo, monkeypatch, capsys):
    # 日誌目錄位置被檔案佔住 -> makedirs 失敗
    blocker = repo / ".claude"
    blocker.write_text("not a dir\n")
    _advance_head_times(monkeypatch, repo, 1)
    result = _run(repo)
    assert result["status"] == "committed"
    assert _git(repo, "show", f"HEAD:{_TID}.md") == "v2\n"
    assert "日誌寫入失敗" in capsys.readouterr().err


def test_e2_mock_path_does_not_write_into_process_cwd_repo(repo, monkeypatch, capsys):
    """E2：票檔不存在的 mock 路徑（"p"）不得退回 process cwd 所屬 repo 寫日誌。"""
    monkeypatch.chdir(repo)  # process cwd 是一個真 repo，正是污染主 repo 的條件

    def fake(*_a, result_out=None, **_k):
        result_out.update({"error": "fatal: Unable to create '/r/.git/refs/heads/main.lock': File exists."})
        return "git_failed"

    monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", fake)
    out = git_utils.auto_commit_ticket_md_with_retry("p", "id", "s")
    assert out["status"] == "git_failed"
    assert _read_log(repo) == ""
    assert "未寫檔" in capsys.readouterr().err


class _FakeClock:
    """假時鐘：每次提交嘗試前進 ``per_attempt`` 秒，sleep 前進其等待秒數。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _install_fake_clock(monkeypatch, per_attempt: float) -> _FakeClock:
    """重試判定改用假時鐘，與機器負載及 git 子程序實際耗時隔離。"""
    clock = _FakeClock()
    original = git_utils._auto_commit_ticket_md

    def timed(*args, **kwargs):
        status = original(*args, **kwargs)
        clock.now += per_attempt
        return status

    monkeypatch.setattr(git_utils, "_clock", clock)
    monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", timed)
    monkeypatch.setattr(git_utils, "_sleep", lambda s: setattr(clock, "now", clock.now + s))
    return clock


def test_slow_first_attempt_still_retries_once(repo, monkeypatch):
    """首次嘗試耗時遠超預算時，可重試失敗仍須重試（高負載下零重試的回歸）。"""
    _install_fake_clock(monkeypatch, per_attempt=10.0)
    _advance_head_times(monkeypatch, repo, 1)
    result = _run(repo)
    assert result["status"] == "committed"
    assert result["attempts"] == 2


def test_control_fast_attempt_retries_once(repo, monkeypatch):
    """正向對照：嘗試不耗時時同一競爭同樣重試一次（與慢嘗試路徑結果一致）。"""
    _install_fake_clock(monkeypatch, per_attempt=0.0)
    _advance_head_times(monkeypatch, repo, 1)
    result = _run(repo)
    assert result["status"] == "committed"
    assert result["attempts"] == 2


def test_min_retries_guaranteed_then_wall_cap_stops(repo, monkeypatch):
    """持續被拒且每次嘗試都超過牆鐘上限：恰好最少重試次數後停止（1 + MIN）。"""
    monkeypatch.setattr(git_utils, "_COMMIT_MIN_RETRIES", 3)
    _install_fake_clock(monkeypatch, per_attempt=30.0)
    _advance_head_times(monkeypatch, repo, 10_000)
    result = _run(repo)
    assert result["status"] == "git_failed"
    assert result["attempts"] == 4


def test_budget_counts_sleep_only_not_attempt_time(repo, monkeypatch):
    """等待預算只計 sleep：每次嘗試 1 秒、退避 1 秒、預算 2.5 秒 -> 兩次重試後停止。"""
    monkeypatch.setattr(git_utils, "_COMMIT_MIN_RETRIES", 0)
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BACKOFF_SECONDS", (1.0,))
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 2.5)
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_WALL_CAP_SECONDS", 1000.0)
    _install_fake_clock(monkeypatch, per_attempt=1.0)
    _advance_head_times(monkeypatch, repo, 10_000)
    result = _run(repo)
    assert result["status"] == "git_failed"
    assert result["attempts"] == 3


def test_wall_cap_limits_retries_beyond_min(repo, monkeypatch):
    """最少重試之外的額外重試受牆鐘上限約束（對照：上限放寬則多重試）。"""
    monkeypatch.setattr(git_utils, "_COMMIT_MIN_RETRIES", 0)
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BACKOFF_SECONDS", (1.0,))
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 1000.0)
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_WALL_CAP_SECONDS", 5.5)
    clock = _install_fake_clock(monkeypatch, per_attempt=1.0)
    _advance_head_times(monkeypatch, repo, 10_000)
    capped = _run(repo)["attempts"]
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_WALL_CAP_SECONDS", 9.5)
    clock.now = 0.0
    relaxed = _run(repo)["attempts"]
    assert capped < relaxed
    # 假時鐘決定性推算：牆鐘 5.5 -> 3 次、9.5 -> 5 次
    assert capped == 3
    assert relaxed == 5


def test_e2_global_sleep_patch_leaks_into_subprocess_polling_but_seam_does_not(monkeypatch):
    """E2 正向對照：改寫全域 time.sleep 會讓 subprocess 輪詢推進假時鐘（推進量取決於子程序
    實際耗時）；改用 git_utils._sleep 接縫後，同一子程序呼叫推進量固定為 0。"""
    cmd = ["sleep", "0.3"]
    leaked = _FakeClock()
    with monkeypatch.context() as m:
        m.setattr(git_ops.time, "sleep", lambda s: setattr(leaked, "now", leaked.now + s))
        subprocess.run(cmd, timeout=30, check=True)
    assert leaked.now > 0.0  # 正向對照：全域 patch 確實被輪詢污染

    seam = _install_fake_clock(monkeypatch, per_attempt=0.0)
    subprocess.run(cmd, timeout=30, check=True)
    assert seam.now == 0.0


def test_default_log_dir_is_isolated_by_conftest():
    """E2：未自行覆寫的測試，日誌根目錄由 conftest 導向 tmp 絕對路徑。"""
    import os

    assert os.path.isabs(git_utils._RETRY_LOG_DIR)
