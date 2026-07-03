"""
0.4.0-W1-004: 修復 version-release 版本生命週期推進斷鏈

覆蓋兩缺陷：
1. activate_next_planned_version regex 只認 "planned"，本專案 todolist 用
   "pending"，release 自動推進永遠靜默跳過。
2. start Step 2 對既有條目不分狀態一律 FAIL，「已規劃版本要啟動」這條正常
   主路徑無工具出路。
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


# ---------------------------------------------------------------------------
# 缺陷 1：activate_next_planned_version 雙詞彙支援
# ---------------------------------------------------------------------------
class TestActivateNextPlannedVersionDualVocabulary:
    def _write_todolist(self, tmp_path, body: str) -> Path:
        path = tmp_path / "todolist.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_pending_unquoted_is_recognized(self, tmp_path):
        """status: pending（無引號）能被推進為 active"""
        todolist = self._write_todolist(
            tmp_path,
            'last_updated: "2026-07-01"\n\nversions:\n'
            '  - version: "0.19.0"\n    status: completed\n'
            '  - version: "0.20.0"\n    status: pending\n',
        )
        result = vr.activate_next_planned_version(todolist, "0.19.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"

    def test_pending_quoted_is_recognized(self, tmp_path):
        """status: "pending"（帶引號）能被推進為 active，保留引號風格"""
        todolist = self._write_todolist(
            tmp_path,
            'last_updated: "2026-07-01"\n\nversions:\n'
            '  - version: "0.19.0"\n    status: "completed"\n'
            '  - version: "0.20.0"\n    status: "pending"\n',
        )
        result = vr.activate_next_planned_version(todolist, "0.19.0", dry_run=False)
        assert result is True

        content = todolist.read_text(encoding="utf-8")
        assert 'status: "active"' in content

    def test_planned_still_recognized_backward_compat(self, tmp_path):
        """既有 status: planned 詞彙向後相容，仍能被推進"""
        todolist = self._write_todolist(
            tmp_path,
            'last_updated: "2026-07-01"\n\nversions:\n'
            '  - version: "0.19.0"\n    status: completed\n'
            '  - version: "0.20.0"\n    status: planned\n',
        )
        result = vr.activate_next_planned_version(todolist, "0.19.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"

    def test_no_planned_or_pending_version_skips(self, tmp_path):
        """無 planned/pending 版本：跳過，回傳 True（非錯誤）"""
        todolist = self._write_todolist(
            tmp_path,
            'last_updated: "2026-07-01"\n\nversions:\n'
            '  - version: "0.19.0"\n    status: completed\n'
            '  - version: "0.20.0"\n    status: active\n',
        )
        result = vr.activate_next_planned_version(todolist, "0.19.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"


# ---------------------------------------------------------------------------
# 缺陷 2：activate_existing_version（start Step 2/3 狀態感知啟動路徑）
# ---------------------------------------------------------------------------
class TestActivateExistingVersion:
    TODOLIST = (
        'last_updated: "2026-07-01"\n\n'
        "versions:\n"
        '  - version: "0.19.0"\n'
        "    status: completed\n"
        '    description: "前版本"\n'
        '  - version: "0.20.0"\n'
        "    status: pending\n"
        '    description: "已規劃版本"\n'
        '  - version: "0.21.0"\n'
        "    status: planned\n"
        '    description: "另一已規劃版本"\n'
        '  - version: "0.22.0"\n'
        "    status: active\n"
        '    description: "進行中版本"\n'
    )

    def _write_todolist(self, tmp_path) -> Path:
        path = tmp_path / "todolist.yaml"
        path.write_text(self.TODOLIST, encoding="utf-8")
        return path

    def test_pending_entry_transitions_to_active(self, tmp_path):
        """pending 版本啟動後轉為 active"""
        todolist = self._write_todolist(tmp_path)
        result = vr.activate_existing_version(todolist, "0.20.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"
        # 未影響其他條目
        assert statuses["0.19.0"] == "completed"
        assert statuses["0.21.0"] == "planned"
        assert statuses["0.22.0"] == "active"

    def test_planned_entry_transitions_to_active(self, tmp_path):
        """planned 版本啟動後轉為 active（向後相容）"""
        todolist = self._write_todolist(tmp_path)
        result = vr.activate_existing_version(todolist, "0.21.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.21.0"] == "active"

    def test_already_active_is_idempotent(self, tmp_path):
        """已是 active：冪等回傳 True，狀態不變"""
        todolist = self._write_todolist(tmp_path)
        result = vr.activate_existing_version(todolist, "0.22.0", dry_run=False)
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.22.0"] == "active"

    def test_completed_entry_rejected(self, tmp_path):
        """completed 版本不允許啟動，回傳 False，不修改"""
        todolist = self._write_todolist(tmp_path)
        before = todolist.read_text(encoding="utf-8")
        result = vr.activate_existing_version(todolist, "0.19.0", dry_run=False)
        assert result is False
        assert todolist.read_text(encoding="utf-8") == before

    def test_version_not_found_rejected(self, tmp_path):
        """版本不存在於 todolist：回傳 False"""
        todolist = self._write_todolist(tmp_path)
        result = vr.activate_existing_version(todolist, "9.9.9", dry_run=False)
        assert result is False

    def test_dry_run_does_not_write(self, tmp_path):
        """dry_run 模式不寫入檔案"""
        todolist = self._write_todolist(tmp_path)
        before = todolist.read_text(encoding="utf-8")
        result = vr.activate_existing_version(todolist, "0.20.0", dry_run=True)
        assert result is True
        assert todolist.read_text(encoding="utf-8") == before

    def test_updates_last_updated(self, tmp_path):
        """啟動時更新 last_updated"""
        todolist = self._write_todolist(tmp_path)
        vr.activate_existing_version(todolist, "0.20.0", dry_run=False)

        today = datetime.now().strftime("%Y-%m-%d")
        content = todolist.read_text(encoding="utf-8")
        assert f'last_updated: "{today}"' in content


# ---------------------------------------------------------------------------
# 缺陷 2：cmd_start_version 對既有 planned/pending 版本走啟動路徑（整合層）
# ---------------------------------------------------------------------------
class TestCmdStartVersionActivatePath:
    def _setup_project(self, tmp_path, existing_status: str):
        """建立最小可跑 cmd_start_version 的專案骨架。"""
        (tmp_path / "docs").mkdir()
        todolist = tmp_path / "docs" / "todolist.yaml"
        todolist.write_text(
            'last_updated: "2026-07-01"\n\n'
            "versions:\n"
            '  - version: "0.19.0"\n'
            "    status: completed\n"
            '    description: "前版本"\n'
            '  - version: "0.20.0"\n'
            f"    status: {existing_status}\n"
            '    description: "已規劃版本"\n',
            encoding="utf-8",
        )
        return todolist

    def _patch_common(self, monkeypatch, tmp_path):
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(vr, "load_version_release_config", lambda root: {})
        monkeypatch.setattr(vr, "detect_project_type", lambda root: "generic")
        monkeypatch.setattr(
            vr, "resolve_version_source", lambda root, config: (None, "git-tag")
        )

        class _DummyResult:
            stdout = "v0.19.0\n"

        monkeypatch.setattr(
            vr.subprocess, "run", lambda *a, **k: _DummyResult()
        )

    def test_pending_existing_version_activates_instead_of_failing(
        self, tmp_path, monkeypatch
    ):
        """既有 pending 版本 start：走啟動路徑，成功回傳 True，狀態轉 active"""
        todolist = self._setup_project(tmp_path, "pending")
        self._patch_common(monkeypatch, tmp_path)

        result = vr.cmd_start_version(
            version="0.20.0", from_version="0.19.0", description="", dry_run=False
        )
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"
        # 未插入重複條目
        assert len(data["versions"]) == 2

    def test_planned_existing_version_activates_instead_of_failing(
        self, tmp_path, monkeypatch
    ):
        """既有 planned 版本 start：走啟動路徑（向後相容）"""
        todolist = self._setup_project(tmp_path, "planned")
        self._patch_common(monkeypatch, tmp_path)

        result = vr.cmd_start_version(
            version="0.20.0", from_version="0.19.0", description="", dry_run=False
        )
        assert result is True

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.20.0"] == "active"
        assert len(data["versions"]) == 2

    def test_active_existing_version_still_fails(self, tmp_path, monkeypatch):
        """既有 active 版本 start：仍應 FAIL（重複啟動保護不變）"""
        self._setup_project(tmp_path, "active")
        self._patch_common(monkeypatch, tmp_path)

        result = vr.cmd_start_version(
            version="0.20.0", from_version="0.19.0", description="", dry_run=False
        )
        assert result is False

    def test_completed_existing_version_still_fails(self, tmp_path, monkeypatch):
        """既有 completed 版本 start：仍應 FAIL"""
        self._setup_project(tmp_path, "completed")
        self._patch_common(monkeypatch, tmp_path)

        result = vr.cmd_start_version(
            version="0.20.0", from_version="0.19.0", description="", dry_run=False
        )
        assert result is False
