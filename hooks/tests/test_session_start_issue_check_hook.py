"""session-start-issue-check-hook 測試套件。

驗證重點（owned-issues 登記檔快速路徑，見同名 ticket）：
1. 登記檔存在且為空清單 -> 直接跳過，不發任何 gh API 呼叫
2. 登記檔存在且非空 -> 逐張呼叫既有 check，省略候選發現／owner 驗證
3. 登記檔缺失／損毀／模組載入失敗 -> fail-open 退回舊 owner 前綴 heuristic 路徑
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
            patch.object(hook, "_collect_hits") as legacy_hits, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})), \
            patch("builtins.print") as mock_print:
        rc = hook.main()

    assert rc == hook.EXIT_SUCCESS
    registry_hits.assert_called_once_with([81], registry_hits.call_args.args[1])
    legacy_hits.assert_not_called()
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
# main()：登記檔缺失／損毀 -> fail-open 退回舊 owner 前綴 heuristic 路徑
# ---------------------------------------------------------------------------


def test_main_falls_back_to_legacy_heuristic_when_registry_missing(tmp_path):
    hook = load_hook_module()
    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_project_owner_prefix", return_value="flutter-balance") as prefix_fn, \
            patch.object(hook, "_collect_hits", return_value=[]) as collect_hits, \
            patch.object(hook, "_gh_ready", return_value=True), \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    prefix_fn.assert_called_once()
    collect_hits.assert_called_once()
    assert collect_hits.call_args.args[0] == "flutter-balance"


def test_main_falls_back_to_legacy_heuristic_when_registry_corrupt(tmp_path):
    hook = load_hook_module()
    path = owned_issues_registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_project_owner_prefix", return_value="flutter-balance"), \
            patch.object(hook, "_collect_hits", return_value=[]) as collect_hits, \
            patch.object(hook, "_gh_ready", return_value=True), \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    collect_hits.assert_called_once()


def test_main_legacy_fallback_skips_when_gh_not_ready(tmp_path):
    hook = load_hook_module()
    with patch.object(hook, "get_project_root", return_value=tmp_path), \
            patch.object(hook, "_gh_ready", return_value=False), \
            patch.object(hook, "_collect_hits") as collect_hits, \
            patch("sys.stdin.read", return_value=json.dumps({"source": "startup"})):
        rc = hook.main()
    assert rc == hook.EXIT_SUCCESS
    collect_hits.assert_not_called()


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
