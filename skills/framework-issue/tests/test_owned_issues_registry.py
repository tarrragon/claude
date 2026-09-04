"""owned_issues_registry.py 測試：schema 讀寫、fail-open 語意、路徑解析。

registry_path() 皆以 project_root 引數顯式指定 tmp_path，避免真實 git
subprocess 呼叫或觸碰開發者本機的 .claude/state/。
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import owned_issues_registry as registry  # noqa: E402


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


# --- _project_root：解析優先序 ---


def test_project_root_prefers_claude_project_dir_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    with mock.patch.object(registry.subprocess, "run") as run:
        result = registry._project_root()
    assert result == tmp_path
    run.assert_not_called()


def test_project_root_falls_back_to_git_toplevel_when_env_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    with mock.patch.object(
        registry.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout=str(tmp_path) + "\n", stderr=""
        ),
    ):
        result = registry._project_root()
    assert result == tmp_path


def test_project_root_falls_back_to_cwd_when_git_fails(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    with mock.patch.object(
        registry.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="not a git repo"),
    ):
        result = registry._project_root()
    assert result == Path.cwd()
