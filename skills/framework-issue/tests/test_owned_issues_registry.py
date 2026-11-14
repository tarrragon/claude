"""owned_issues_registry.py 測試：schema 讀寫、fail-open 語意、路徑解析。

registry_path() 皆以 project_root 引數顯式指定 tmp_path，避免真實 git
subprocess 呼叫或觸碰開發者本機的 .claude/state/。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import owned_issues_registry as registry  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_state_root(monkeypatch):
    """預設隔離：讓 registry_path 採用測試傳入的 tmp_path。

    不隔離時，從 linked worktree 執行測試會把登記檔寫進主倉庫。需要驗證
    共用狀態根的測試自行清除本變數。
    """
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")


# --- registry_path：路徑組成 ---


def test_registry_path_appends_relative_parts_to_project_root(tmp_path):
    path = registry.registry_path(tmp_path)
    assert path == tmp_path / ".claude" / "state" / "framework-issue-owned.json"


# --- load_registry：fail-open 語意（缺檔／損毀／schema 不符一律 None） ---


def test_load_registry_returns_none_when_file_missing(tmp_path):
    assert registry.load_registry(tmp_path) is None


def test_load_registry_returns_none_on_corrupt_json(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert registry.load_registry(tmp_path) is None


def test_load_registry_returns_none_on_schema_version_mismatch(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 999, "issues": []}), encoding="utf-8")
    assert registry.load_registry(tmp_path) is None


def test_load_registry_returns_none_when_issues_not_a_list(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": registry.SCHEMA_VERSION, "issues": "not-a-list"}),
        encoding="utf-8",
    )
    assert registry.load_registry(tmp_path) is None


def test_load_registry_returns_data_when_valid(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    data = {
        "schema_version": registry.SCHEMA_VERSION,
        "issues": [{"number": 81, "owner": "flutter-balance-99", "updated_at": "2026-09-04T00:00:00+00:00"}],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert registry.load_registry(tmp_path) == data


# --- owned_issue_numbers：None（無法判定）vs 空清單（已確認無擁有） ---


def test_owned_issue_numbers_returns_none_when_registry_missing(tmp_path):
    assert registry.owned_issue_numbers(tmp_path) is None


def test_owned_issue_numbers_returns_empty_list_when_registry_has_no_issues(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": registry.SCHEMA_VERSION, "issues": []}),
        encoding="utf-8",
    )
    assert registry.owned_issue_numbers(tmp_path) == []


def test_owned_issue_numbers_extracts_numbers_and_filters_malformed_entries(tmp_path):
    path = registry.registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    data = {
        "schema_version": registry.SCHEMA_VERSION,
        "issues": [
            {"number": 81, "owner": "flutter-balance-99", "updated_at": "t"},
            {"number": 82, "owner": "flutter-balance-99", "updated_at": "t"},
            {"owner": "缺 number 欄位"},
            "非 dict 項目",
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert registry.owned_issue_numbers(tmp_path) == [81, 82]


# --- record_owned_issue：新增／覆蓋／原子寫入 ---


def test_record_owned_issue_creates_registry_with_correct_schema(tmp_path):
    registry.record_owned_issue(81, "flutter-balance-99", "2026-09-04T00:00:00+00:00", tmp_path)
    data = registry.load_registry(tmp_path)
    assert data == {
        "schema_version": registry.SCHEMA_VERSION,
        "issues": [{"number": 81, "owner": "flutter-balance-99", "updated_at": "2026-09-04T00:00:00+00:00"}],
    }


def test_record_owned_issue_appends_new_number_alongside_existing(tmp_path):
    registry.record_owned_issue(81, "flutter-balance-99", "t1", tmp_path)
    registry.record_owned_issue(82, "flutter-balance-99", "t2", tmp_path)
    numbers = registry.owned_issue_numbers(tmp_path)
    assert numbers == [81, 82]


def test_record_owned_issue_overwrites_existing_entry_for_same_number(tmp_path):
    registry.record_owned_issue(81, "flutter-balance-99", "t1", tmp_path)
    registry.record_owned_issue(81, "flutter-balance-99", "t2-更新", tmp_path)
    data = registry.load_registry(tmp_path)
    assert data["issues"] == [
        {"number": 81, "owner": "flutter-balance-99", "updated_at": "t2-更新"}
    ]


def test_record_owned_issue_leaves_no_tmp_file_after_atomic_replace(tmp_path):
    registry.record_owned_issue(81, "flutter-balance-99", "t1", tmp_path)
    state_dir = tmp_path / ".claude" / "state"
    assert [p.name for p in state_dir.iterdir()] == ["framework-issue-owned.json"]


def test_record_owned_issue_swallows_oserror_without_raising(tmp_path, monkeypatch):
    """best-effort 快取：寫入失敗（權限、磁碟空間等）不應向呼叫端拋例外
    （呼叫端已完成的 GitHub 寫入不應因本機快取失敗而回報錯誤，見模組
    docstring）。"""
    def _raise_mkdir(*args, **kwargs):
        raise OSError("模擬磁碟寫入失敗")

    monkeypatch.setattr(Path, "mkdir", _raise_mkdir)
    registry.record_owned_issue(81, "flutter-balance-99", "t1", tmp_path)  # 不應拋例外


# --- 共用狀態根：真實 linked worktree ---


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def linked_worktree(tmp_path):
    """建主 repo 與一個 linked worktree，回傳 (main_root, worktree_root)。"""
    main = (tmp_path / "main").resolve()
    worktree = (tmp_path / "wt").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    (main / "README.md").write_text("x", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "worktree", "add", "-q", str(worktree), "-b", "wt")
    return main, worktree


def test_write_in_linked_worktree_is_readable_from_main_repo(linked_worktree, monkeypatch):
    """正向對照：清除 HOOK_TEST_ISOLATION，在 linked worktree 內寫入，主 repo 讀得到。

    呼叫端傳入的 project_root 是 worktree 自己的根（hook 與 section_comment 的
    實際傳法），登記檔仍須落在主倉庫。
    """
    main, worktree = linked_worktree
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)

    monkeypatch.chdir(worktree)
    registry.record_owned_issue(81, "llm-dev", "t1", worktree)
    registry.record_owned_issue(82, "llm-dev", "t2")

    assert (main / ".claude" / "state" / "framework-issue-owned.json").exists()
    assert not (worktree / ".claude" / "state" / "framework-issue-owned.json").exists()

    monkeypatch.chdir(main)
    assert sorted(registry.owned_issue_numbers(main)) == [81, 82]


def test_isolation_keeps_registry_in_given_root(linked_worktree, monkeypatch):
    """對照組：HOOK_TEST_ISOLATION=1 時退回呼叫端傳入的根，證明上一則的主 repo
    落點來自共用狀態根解析，而不是測試環境本來就寫到主 repo。"""
    main, worktree = linked_worktree
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    monkeypatch.chdir(worktree)
    registry.record_owned_issue(81, "llm-dev", "t1", worktree)

    assert (worktree / ".claude" / "state" / "framework-issue-owned.json").exists()
    assert not (main / ".claude" / "state" / "framework-issue-owned.json").exists()


def test_module_has_no_own_root_resolver():
    """根目錄解析只走 get_shared_state_root，模組內不得再有自寫解析。"""
    source = Path(registry.__file__).read_text(encoding="utf-8")
    assert "get_shared_state_root" in source
    for forbidden in ("CLAUDE_PROJECT_DIR", "--show-toplevel", "get_project_root", "def _project_root"):
        assert forbidden not in source
