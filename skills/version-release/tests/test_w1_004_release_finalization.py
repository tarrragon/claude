"""
0.19.1-W1-004: 修正 version-release CLI release 收尾完整性

覆蓋兩 Gap：
1. CHANGELOG finalize：release 偵測既有 In-Development 區段，將 header 改為發布日期
   並保留人寫內容，不再插入 UC-XX placeholder 空殼模板。
2. todolist 版本狀態：release 成功後自動將 todolist.yaml 對應版本 active→completed。
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


# ---------------------------------------------------------------------------
# Gap 1：CHANGELOG finalize In-Development 區段
# ---------------------------------------------------------------------------
class TestChangelogFinalize:
    HEADER = "# 變更紀錄\n\n本文件記錄所有重要變更。\n\n"

    def _write_changelog(self, tmp_path, body: str) -> Path:
        path = tmp_path / "CHANGELOG.md"
        path.write_text(self.HEADER + body, encoding="utf-8")
        return path

    def test_finalize_in_development_section_header_to_date(
        self, tmp_path, monkeypatch
    ):
        """既有 In-Development 區段：header 改為發布日期，保留人寫內容，不插空殼"""
        body = (
            "## [v0.19.1] - In Development\n\n"
            "### 修復項目\n"
            "- [修復] 實際人寫的修復內容（W1-004）\n\n"
            "---\n\n"
            "## [0.19.0] - 2026-06-02\n\n### 既有內容\n"
        )
        changelog = self._write_changelog(tmp_path, body)
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)

        result = vr.update_changelog("0.19.1", dry_run=False)
        assert result is True

        content = changelog.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")

        # In-Development header 已 finalize 為日期
        assert "## [v0.19.1] - In Development" not in content
        assert f"## [0.19.1] - {today}" in content or f"## [v0.19.1] - {today}" in content
        # 人寫內容保留
        assert "實際人寫的修復內容（W1-004）" in content
        # 不插入 placeholder 空殼
        assert "UC-XX 功能名稱" not in content
        assert "新增功能項目" not in content
        # 不產生第二個 0.19.1 區段（finalize 而非新增）
        assert content.count("0.19.1]") == 1

    def test_no_in_development_section_falls_back_to_template(
        self, tmp_path, monkeypatch
    ):
        """無 In-Development 區段且版本未存在：維持原有插入模板行為（向後相容）"""
        body = "## [0.19.0] - 2026-06-02\n\n### 既有內容\n"
        changelog = self._write_changelog(tmp_path, body)
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)

        result = vr.update_changelog("0.19.1", dry_run=False)
        assert result is True

        content = changelog.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"## [0.19.1] - {today}" in content

    def test_already_finalized_version_is_idempotent(self, tmp_path, monkeypatch):
        """版本已 finalize（header 帶日期）：冪等跳過，不重複插入"""
        today = datetime.now().strftime("%Y-%m-%d")
        body = f"## [0.19.1] - {today}\n\n### 內容\n- 已發布\n"
        changelog = self._write_changelog(tmp_path, body)
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)

        result = vr.update_changelog("0.19.1", dry_run=False)
        assert result is True

        content = changelog.read_text(encoding="utf-8")
        assert content.count("0.19.1]") == 1
        assert "UC-XX 功能名稱" not in content

    def test_dry_run_does_not_write(self, tmp_path, monkeypatch):
        """dry_run 模式不寫入檔案"""
        body = (
            "## [v0.19.1] - In Development\n\n### 修復項目\n- [修復] 內容\n\n---\n\n"
            "## [0.19.0] - 2026-06-02\n\n### 既有\n"
        )
        changelog = self._write_changelog(tmp_path, body)
        before = changelog.read_text(encoding="utf-8")
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)

        result = vr.update_changelog("0.19.1", dry_run=True)
        assert result is True
        assert changelog.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Gap 2：todolist active→completed
# ---------------------------------------------------------------------------
class TestMarkVersionCompleted:
    TODOLIST = (
        'last_updated: "2026-05-27"\n\n'
        "versions:\n"
        '  - version: "0.19.0"\n'
        "    status: completed\n"
        '    description: "前版本"\n'
        '  - version: "0.19.1"\n'
        "    status: active\n"
        '    description: "當前版本"\n'
        '  - version: "0.20.0"\n'
        "    status: planned\n"
        '    description: "下版本"\n'
    )

    def _write_todolist(self, tmp_path) -> Path:
        path = tmp_path / "todolist.yaml"
        path.write_text(self.TODOLIST, encoding="utf-8")
        return path

    def test_mark_active_version_completed(self, tmp_path):
        """將 active 版本標記為 completed，不影響其他版本"""
        todolist = self._write_todolist(tmp_path)
        result = vr.mark_version_completed(todolist, "0.19.1", dry_run=False)
        assert result is True

        import yaml

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.19.1"] == "completed"
        assert statuses["0.19.0"] == "completed"
        assert statuses["0.20.0"] == "planned"

    def test_mark_completed_updates_last_updated(self, tmp_path):
        """標記 completed 時更新 last_updated"""
        todolist = self._write_todolist(tmp_path)
        vr.mark_version_completed(todolist, "0.19.1", dry_run=False)

        today = datetime.now().strftime("%Y-%m-%d")
        content = todolist.read_text(encoding="utf-8")
        assert f'last_updated: "{today}"' in content

    def test_mark_completed_version_not_found(self, tmp_path):
        """版本不存在於 todolist：回傳 False，不修改"""
        todolist = self._write_todolist(tmp_path)
        before = todolist.read_text(encoding="utf-8")
        result = vr.mark_version_completed(todolist, "9.9.9", dry_run=False)
        assert result is False
        assert todolist.read_text(encoding="utf-8") == before

    def test_mark_completed_dry_run_does_not_write(self, tmp_path):
        """dry_run 模式不寫入檔案"""
        todolist = self._write_todolist(tmp_path)
        before = todolist.read_text(encoding="utf-8")
        result = vr.mark_version_completed(todolist, "0.19.1", dry_run=True)
        assert result is True
        assert todolist.read_text(encoding="utf-8") == before

    def test_mark_completed_idempotent_already_completed(self, tmp_path):
        """版本已 completed：冪等回傳 True，狀態不變"""
        todolist = self._write_todolist(tmp_path)
        vr.mark_version_completed(todolist, "0.19.0", dry_run=False)

        import yaml

        data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
        statuses = {v["version"]: v["status"] for v in data["versions"]}
        assert statuses["0.19.0"] == "completed"
