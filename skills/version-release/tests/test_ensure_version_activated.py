"""
0.2.0-W1-031: 版本啟用冪等化

覆蓋：
- E1：四種缺漏組合（全缺／只缺版本檔／只缺 worklog／全就位）各只補缺項，
  全就位時不改任何檔案（含 mtime 不變）
- E2：舊碼會 FAIL 的 active 版本案例——ensure_version_activated 對 active
  版本不再視為錯誤，仍走檢查/補齊路徑並回傳 True；completed 版本仍為
  無法復原的錯誤（紅輸入對照）
"""

import os
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _write_todolist(tmp_path: Path, version: str, status: str) -> Path:
    todolist = tmp_path / "docs" / "todolist.yaml"
    todolist.parent.mkdir(parents=True, exist_ok=True)
    todolist.write_text(
        'last_updated: "2026-07-01"\n\n'
        "versions:\n"
        '  - version: "0.1.0"\n'
        "    status: completed\n"
        f'  - version: "{version}"\n'
        f"    status: {status}\n",
        encoding="utf-8",
    )
    return todolist


def _write_version_file(tmp_path: Path, current_version: str) -> Path:
    version_file = tmp_path / "pubspec.yaml"
    version_file.write_text(f"name: sample\nversion: {current_version}\n", encoding="utf-8")
    return version_file


def _write_changelog(tmp_path: Path, version: str | None) -> Path:
    changelog = tmp_path / "CHANGELOG.md"
    body = "# Changelog\n\n"
    if version:
        body += f"## [{version}] - In Development\n\n（待補充）\n\n---\n\n"
    body += "## [0.1.0] - 2026-09-01\n\n舊版本\n"
    changelog.write_text(body, encoding="utf-8")
    return changelog


def _write_worklog(tmp_path: Path, version: str) -> Path:
    worklog_dir = tmp_path / "docs" / "work-logs" / f"v{version}"
    worklog_dir.mkdir(parents=True, exist_ok=True)
    worklog_file = worklog_dir / f"v{version}-main.md"
    worklog_file.write_text(f"# v{version} 版本工作日誌\n", encoding="utf-8")
    return worklog_file


def _patch_common(monkeypatch, tmp_path: Path, version_file: Path):
    monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(vr, "load_version_release_config", lambda root: {})
    monkeypatch.setattr(vr, "detect_project_type", lambda root: "generic")
    monkeypatch.setattr(
        vr, "resolve_version_source", lambda root, config: (version_file, "yaml")
    )


class TestEnsureVersionActivatedGapCombinations:
    """E1：四種缺漏組合各只補缺項，全就位時不改任何檔案。"""

    VERSION = "0.20.0"

    def test_all_gaps_are_backfilled(self, tmp_path, monkeypatch):
        """全缺：todolist pending、worklog 不存在、版本檔錯誤、CHANGELOG 無段落"""
        _write_todolist(tmp_path, self.VERSION, "pending")
        version_file = _write_version_file(tmp_path, "0.19.0")
        _write_changelog(tmp_path, version=None)
        _patch_common(monkeypatch, tmp_path, version_file)

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is True

        todolist_data = yaml.safe_load(
            (tmp_path / "docs" / "todolist.yaml").read_text(encoding="utf-8")
        )
        statuses = {v["version"]: v["status"] for v in todolist_data["versions"]}
        assert statuses[self.VERSION] == "active"

        assert version_file.read_text(encoding="utf-8").splitlines()[1] == (
            f"version: {self.VERSION}"
        )

        worklog_file = (
            tmp_path / "docs" / "work-logs" / f"v{self.VERSION}" / f"v{self.VERSION}-main.md"
        )
        assert worklog_file.exists()

        changelog_content = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
        assert f"## [{self.VERSION}] - In Development" in changelog_content

    def test_only_version_file_gap_is_backfilled(self, tmp_path, monkeypatch):
        """只缺版本檔：todolist 已 active、worklog 已存在、CHANGELOG 已有段落"""
        _write_todolist(tmp_path, self.VERSION, "active")
        version_file = _write_version_file(tmp_path, "0.19.0")
        worklog_file = _write_worklog(tmp_path, self.VERSION)
        _write_changelog(tmp_path, version=self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        worklog_mtime_before = worklog_file.stat().st_mtime_ns

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is True

        assert version_file.read_text(encoding="utf-8").splitlines()[1] == (
            f"version: {self.VERSION}"
        )
        assert worklog_file.stat().st_mtime_ns == worklog_mtime_before

    def test_only_worklog_gap_is_backfilled(self, tmp_path, monkeypatch):
        """只缺 worklog：todolist 已 active、版本檔已正確、CHANGELOG 已有段落"""
        _write_todolist(tmp_path, self.VERSION, "active")
        version_file = _write_version_file(tmp_path, self.VERSION)
        _write_changelog(tmp_path, version=self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        version_content_before = version_file.read_text(encoding="utf-8")

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is True

        worklog_file = (
            tmp_path / "docs" / "work-logs" / f"v{self.VERSION}" / f"v{self.VERSION}-main.md"
        )
        assert worklog_file.exists()
        assert version_file.read_text(encoding="utf-8") == version_content_before

    def test_all_present_changes_nothing(self, tmp_path, monkeypatch, capsys):
        """全就位：不改任何檔案，含版本檔 mtime 不變，並印出無缺漏訊息"""
        _write_todolist(tmp_path, self.VERSION, "active")
        version_file = _write_version_file(tmp_path, self.VERSION)
        worklog_file = _write_worklog(tmp_path, self.VERSION)
        _write_changelog(tmp_path, version=self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        todolist_before = (tmp_path / "docs" / "todolist.yaml").read_text(encoding="utf-8")
        version_mtime_before = version_file.stat().st_mtime_ns
        worklog_content_before = worklog_file.read_text(encoding="utf-8")
        changelog_before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

        # 確保若函式誤觸檔案寫入，mtime 差異可被偵測到
        time.sleep(0.01)

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is True

        assert (
            tmp_path / "docs" / "todolist.yaml"
        ).read_text(encoding="utf-8") == todolist_before
        assert version_file.stat().st_mtime_ns == version_mtime_before
        assert worklog_file.read_text(encoding="utf-8") == worklog_content_before
        assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == changelog_before

        captured = capsys.readouterr()
        assert "無缺漏" in captured.out


class TestEnsureVersionActivatedStatusHandling:
    """E2：active 版本不再 FAIL（舊碼會 FAIL 的紅輸入對照）；completed 仍為錯誤。"""

    VERSION = "0.20.0"

    def test_active_version_does_not_fail(self, tmp_path, monkeypatch):
        """舊碼（cmd_start_version Step 2）對 active 版本一律 FAIL；
        ensure_version_activated 對 active 版本應正常走檢查路徑並回傳 True
        （改回舊碼行為即翻紅：舊碼路徑等同直接 print_error + return False）"""
        _write_todolist(tmp_path, self.VERSION, "active")
        version_file = _write_version_file(tmp_path, self.VERSION)
        _write_worklog(tmp_path, self.VERSION)
        _write_changelog(tmp_path, version=self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is True

    def test_completed_version_is_unrecoverable_error(self, tmp_path, monkeypatch):
        """completed 版本無法用 ensure_version_activated 重新啟用（紅輸入）"""
        _write_todolist(tmp_path, self.VERSION, "completed")
        version_file = _write_version_file(tmp_path, self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is False

    def test_missing_version_entry_is_error(self, tmp_path, monkeypatch):
        """todolist 中根本沒有該版本條目時回傳 False（紅輸入）"""
        _write_todolist(tmp_path, "0.19.0", "completed")
        version_file = _write_version_file(tmp_path, self.VERSION)
        _patch_common(monkeypatch, tmp_path, version_file)

        result = vr.ensure_version_activated(self.VERSION, dry_run=False)
        assert result is False


class TestEnsureVersionActivatedDryRun:
    VERSION = "0.20.0"

    def test_dry_run_does_not_write_any_file(self, tmp_path, monkeypatch):
        """dry_run 模式下即使全缺也不寫入任何檔案"""
        todolist = _write_todolist(tmp_path, self.VERSION, "pending")
        version_file = _write_version_file(tmp_path, "0.19.0")
        _write_changelog(tmp_path, version=None)
        _patch_common(monkeypatch, tmp_path, version_file)

        todolist_before = todolist.read_text(encoding="utf-8")
        version_content_before = version_file.read_text(encoding="utf-8")
        changelog_before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

        result = vr.ensure_version_activated(self.VERSION, dry_run=True)
        assert result is True

        assert todolist.read_text(encoding="utf-8") == todolist_before
        assert version_file.read_text(encoding="utf-8") == version_content_before
        assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == changelog_before
        worklog_file = (
            tmp_path / "docs" / "work-logs" / f"v{self.VERSION}" / f"v{self.VERSION}-main.md"
        )
        assert not worklog_file.exists()
