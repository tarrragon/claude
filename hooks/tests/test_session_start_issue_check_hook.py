"""session-start-issue-check-hook 測試套件。

驗證重點（owned-issues 登記檔快速路徑，見同名 ticket）：
1. 登記檔存在且為空清單 -> 直接跳過，不發任何 gh API 呼叫
2. 登記檔存在且非空 -> 逐張呼叫既有 check，省略候選發現／owner 驗證
3. 登記檔缺失／損毀／模組載入失敗 -> 略過，不發任何 gh 命令（專案名不外送）
4. subagent 環境 / 非 startup-resume source -> 一律 suppressOutput，不觸碰登記檔

`_read_owned_issue_numbers` 的模組載入以「先讓真實 owned_issues_registry
進入 sys.modules 快取」手法測試——之後無論 hook 內部的 sys.path 插入指向
真實路徑或臨時目錄，`import owned_issues_registry` 皆命中快取，測試因而
能以 tmp_path 控制 registry 檔案內容而不觸碰真實專案的 .claude/state/。
ImportError fallback 分支另以 `monkeypatch.setitem(sys.modules, ..., None)`
（Python import 系統慣例：sys.modules 值為 None 時 import 視為失敗）單獨
驗證，不依賴真實環境缺模組。
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOK_PATH = Path(__file__).parent.parent / "session-start-issue-check-hook.py"
FRAMEWORK_ISSUE_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2] / "skills" / "framework-issue" / "scripts"
)
sys.path.insert(0, str(FRAMEWORK_ISSUE_SCRIPTS_DIR))
import owned_issues_registry  # noqa: E402  （預先載入，供快取命中手法使用）


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "session_start_issue_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_registry(project_root: Path, issues: list) -> None:
    path = owned_issues_registry.registry_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": owned_issues_registry.SCHEMA_VERSION, "issues": issues}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# _read_owned_issue_numbers：登記檔讀取端到端驗證
# ---------------------------------------------------------------------------


def test_read_owned_issue_numbers_returns_none_when_registry_missing(tmp_path):
    hook = load_hook_module()
    assert hook._read_owned_issue_numbers(tmp_path, MagicMock()) is None


def test_read_owned_issue_numbers_returns_empty_list_when_registry_has_no_issues(tmp_path):
    hook = load_hook_module()
    _write_registry(tmp_path, [])
    assert hook._read_owned_issue_numbers(tmp_path, MagicMock()) == []


def test_read_owned_issue_numbers_returns_registered_numbers(tmp_path):
    hook = load_hook_module()
    _write_registry(
        tmp_path,
        [{"number": 81, "owner": "flutter-balance-99", "updated_at": "t"}],
    )
    assert hook._read_owned_issue_numbers(tmp_path, MagicMock()) == [81]


def test_read_owned_issue_numbers_returns_none_when_module_import_fails(monkeypatch, tmp_path):
    hook = load_hook_module()
    monkeypatch.setitem(sys.modules, "owned_issues_registry", None)
    logger = MagicMock()
    assert hook._read_owned_issue_numbers(tmp_path, logger) is None
    assert logger.info.called


# ---------------------------------------------------------------------------
# main()：登記檔快速路徑（空清單 -> 零 gh API 呼叫）
# ---------------------------------------------------------------------------


def test_main_skips_all_gh_calls_when_registry_has_no_owned_issues(tmp_path):
    """registry 有效但為空清單：連 `_gh_ready`（gh 可用性檢查，本身即一次
    subprocess 呼叫）都不應被觸發，acceptance 條款「不發任何 gh API 呼叫」
    的最嚴格判定——若被呼叫即代表快速路徑未在 gh 呼叫發生前提前跳過。"""
    hook = load_hook_module()
    _write_registry(tmp_path, [])
    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_gh_ready", side_effect=AssertionError("不應檢查 gh 可用性")) as gh_ready, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    gh_ready.assert_not_called()


# ---------------------------------------------------------------------------
# main()：登記檔快速路徑（非空 -> 逐張呼叫既有 check，省略候選發現/owner 驗證）
# ---------------------------------------------------------------------------


def test_main_uses_registry_fast_path_when_issues_registered(tmp_path):
    """registry 非空時：以登記清單直接呼叫 `_collect_registry_hits`（省略
    候選發現/owner 驗證），且不觸碰舊 heuristic 路徑的 `_collect_hits`。"""
    hook = load_hook_module()
    _write_registry(
        tmp_path,
        [{"number": 81, "owner": "flutter-balance-99", "updated_at": "t"}],
    )
    check_output = "[framework-issue] check（comment 數：3）\n\n[警訊 B][主警訊] 觸發：...\n"

    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_gh_ready", return_value=True), \
            patch.object(hook, "_collect_registry_hits", return_value=[(81, check_output)]) as registry_hits, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})), \
            patch("builtins.print") as mock_print:
        rc = hook.main()

    assert rc == hook.EXIT_SUCCESS
    registry_hits.assert_called_once_with([81], registry_hits.call_args.args[1])
    printed = json.loads(mock_print.call_args.args[0])
    assert printed["suppressOutput"] is False
    ctx = printed["hookSpecificOutput"]["additionalContext"]
    assert "owned-issues 登記檔" in ctx
    assert "#81" in ctx


def test_main_registry_fast_path_skips_when_gh_not_ready(tmp_path):
    hook = load_hook_module()
    _write_registry(
        tmp_path,
        [{"number": 81, "owner": "flutter-balance-99", "updated_at": "t"}],
    )
    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_gh_ready", return_value=False), \
            patch.object(hook, "_collect_registry_hits") as registry_hits, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    registry_hits.assert_not_called()


# ---------------------------------------------------------------------------
# main()：登記檔缺失／損毀 -> 略過，不發任何 gh 命令（專案名不外送）
# ---------------------------------------------------------------------------


def _run_main_recording_subprocess(hook, tmp_path):
    """執行 main，記錄 hook 模組內所有 subprocess.run 呼叫與 gh 可用性查詢。"""
    calls = []

    def _record(args, *a, **kw):
        calls.append(list(args))
        return MagicMock(returncode=0, stdout="[]", stderr="")

    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook.subprocess, "run", side_effect=_record), \
            patch.object(hook.shutil, "which", side_effect=lambda name: calls.append(["which", name]) or "/usr/bin/gh"), \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})), \
            patch("builtins.print") as mock_print:
        rc = hook.main()
    return rc, calls, json.loads(mock_print.call_args.args[0])


def test_main_sends_no_gh_command_when_registry_missing(tmp_path):
    """登記檔缺失：不呼叫任何 gh 命令（含 gh auth status 與 gh search）。"""
    hook = load_hook_module()
    rc, calls, printed = _run_main_recording_subprocess(hook, tmp_path)
    assert rc == hook.EXIT_SUCCESS
    assert calls == []
    assert printed == {"suppressOutput": True}


def test_main_sends_no_gh_command_when_registry_corrupt(tmp_path):
    hook = load_hook_module()
    path = owned_issues_registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    rc, calls, _ = _run_main_recording_subprocess(hook, tmp_path)
    assert rc == hook.EXIT_SUCCESS
    assert calls == []


def test_registry_present_reaches_gh_while_missing_does_not(tmp_path):
    """E1 對照：同一環境下，有登記檔時走到 gh 命令，沒有登記檔時不走到。

    證明上兩則的「零呼叫」來自登記檔缺失的分支，而不是記錄手法本身攔不到呼叫。
    """
    hook = load_hook_module()
    _, calls_missing, _ = _run_main_recording_subprocess(hook, tmp_path)

    _write_registry(tmp_path, [{"number": 81, "owner": "flutter-balance-99", "updated_at": "t"}])
    hook = load_hook_module()
    _, calls_present, _ = _run_main_recording_subprocess(hook, tmp_path)

    assert calls_missing == []
    assert ["gh", "auth", "status"] in calls_present
    assert not any(c[:3] == ["gh", "search", "issues"] for c in calls_present)


def test_hook_has_no_search_path_left():
    """hook 原始碼不再含以專案名搜尋 GitHub 的路徑。"""
    source = HOOK_PATH.read_text(encoding="utf-8")
    assert '"search", "issues"' not in source
    for name in ("_project_owner_prefix", "_search_candidate_issues", "_collect_hits"):
        assert name not in source


# ---------------------------------------------------------------------------
# main()：既有守門條件不受本次改動影響（subagent / 非 startup-resume source）
# ---------------------------------------------------------------------------


def test_main_skips_registry_lookup_in_subagent_environment(tmp_path):
    hook = load_hook_module()
    with patch.object(hook, "get_project_root", return_value=tmp_path) as get_root, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup", "cwd": "/x", "subagent_id": "a1"})):
        with patch.object(hook, "is_subagent_environment", return_value=True):
            rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    get_root.assert_not_called()


def test_main_skips_registry_lookup_when_source_not_startup_or_resume(tmp_path):
    hook = load_hook_module()
    with patch.object(hook, "get_project_root", return_value=tmp_path) as get_root, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "compact"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    get_root.assert_not_called()


# ---------------------------------------------------------------------------
# 並行執行（0.4.0-W1-051.1）：E1 牆鐘與順序、E2 單張失敗隔離、已關閉略過
# ---------------------------------------------------------------------------

import time  # noqa: E402

_HIT = "[警訊 B][主警訊] 觸發：#{n}\n"


def _fake_check_factory(delay: float, fail_numbers=(), raise_numbers=()):
    def fake(number, logger):
        time.sleep(delay)
        if number in raise_numbers:
            raise RuntimeError("boom")
        if number in fail_numbers:
            return None
        return _HIT.format(n=number)
    return fake


def _concurrency_probe(width: int):
    """回傳 (fake_check, peak)：前 width 個呼叫在柵欄會合後才返回，記錄同時進行的最大數量。

    以柵欄同步取代牆鐘：並行時 width 個呼叫立即會合；串行時第一個呼叫等不到其他人，
    柵欄逾時拋 BrokenBarrierError，測試以例外翻紅。逾時只在失敗路徑才會用到，
    正確程式的通過與否不取決於機器負載（test-assertion-design 規則 D1）。
    hook 把單張檢查的例外轉成失敗訊息而不中止，所以串行時翻紅的訊號是 peak 只有 1。
    """
    import threading
    barrier = threading.Barrier(width, timeout=10)
    lock = threading.Lock()
    state = {"active": 0, "peak": 0, "met": 0}

    def fake(number, logger):
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            first_wave = state["met"] < width
            state["met"] += 1
        try:
            if first_wave:
                barrier.wait()
            return _HIT.format(n=number)
        finally:
            with lock:
                state["active"] -= 1

    return fake, state


def test_e1_registry_hits_run_in_parallel_and_keep_issue_order():
    """亂序輸入下 worker 上限內的呼叫同時進行，輸出依 issue 編號排序（與串行版一致）。"""
    hook = load_hook_module()
    numbers = [30, 12, 25, 1, 8, 19, 5, 40, 3, 22, 15, 9]
    fake, state = _concurrency_probe(hook.MAX_CHECK_WORKERS)
    with patch.object(hook, "_run_check", fake), \
            patch.object(hook, "_closed_issue_numbers", return_value=set()):
        hits = hook._collect_registry_hits(numbers, MagicMock())
    assert state["peak"] == hook.MAX_CHECK_WORKERS
    assert [n for n, _ in hits] == sorted(numbers)


def test_e2_single_check_exception_does_not_lose_other_results_and_is_visible():
    hook = load_hook_module()
    logger = MagicMock()
    with patch.object(hook, "_run_check", _fake_check_factory(0.01, raise_numbers=(2,))), \
            patch.object(hook, "_closed_issue_numbers", return_value=set()):
        hits = hook._collect_registry_hits([1, 2, 3], logger)
    assert [n for n, _ in hits] == [1, 2, 3]
    assert "警訊 B" in dict(hits)[1] and "警訊 B" in dict(hits)[3]
    assert hook.CHECK_FAILED_PREFIX in dict(hits)[2]
    assert logger.info.called or logger.error.called or logger.warning.called


def test_e2_run_check_timeout_is_reported_as_failure():
    hook = load_hook_module()
    import subprocess as sp
    with patch.object(hook.subprocess, "run", side_effect=sp.TimeoutExpired("x", 1)), \
            patch.object(hook, "get_project_root", return_value=Path("/nonexistent")):
        out = hook._run_check(7, MagicMock())
    assert out is not None and out.startswith(hook.CHECK_FAILED_PREFIX)


def test_closed_issues_are_skipped_without_per_issue_api_calls():
    hook = load_hook_module()
    calls = []

    def fake(number, logger):
        calls.append(number)
        return _HIT.format(n=number)

    with patch.object(hook, "_run_check", fake), \
            patch.object(hook, "_closed_issue_numbers", return_value={2, 3}) as closed:
        hits = hook._collect_registry_hits([1, 2, 3, 4], MagicMock())
    assert sorted(calls) == [1, 4]
    assert [n for n, _ in hits] == [1, 4]
    closed.assert_called_once()  # 狀態取得為單次批次查詢，非逐張


def test_closed_issue_numbers_uses_single_gh_call_and_fails_open():
    hook = load_hook_module()
    ok = MagicMock(returncode=0, stdout='[{"number": 5}, {"number": 9}]', stderr="")
    with patch.object(hook.subprocess, "run", return_value=ok) as run:
        assert hook._closed_issue_numbers(MagicMock()) == {5, 9}
    assert run.call_count == 1
    bad = MagicMock(returncode=1, stdout="", stderr="err")
    with patch.object(hook.subprocess, "run", return_value=bad):
        assert hook._closed_issue_numbers(MagicMock()) == set()
