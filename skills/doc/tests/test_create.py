"""create 子命令測試。"""

import argparse
from pathlib import Path
from unittest.mock import patch

import yaml

from doc_system.commands.create import execute
from doc_system.core.file_locator import FileLocator


def _setup_project(tmp_path):
    """在 tmp_path 建立基礎專案結構（含模板）。"""
    # 建立必要目錄
    (tmp_path / "docs" / "proposals").mkdir(parents=True)
    (tmp_path / "docs" / "usecases").mkdir(parents=True)
    (tmp_path / "docs" / "spec").mkdir(parents=True)

    # 建立模板目錄和模板檔案
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    (templates_dir / "proposal-template.md").write_text(
        '---\nid: PROP-NNN\ntitle: "{提案標題}"\nstatus: draft\n'
        'proposed_date: "YYYY-MM-DD"\n---\n# PROP-{NNN}: {提案標題}\n'
    )
    (templates_dir / "usecase-template.md").write_text(
        '---\nid: UC-XX\ntitle: "{用例名稱}"\nstatus: draft\n'
        'created: "YYYY-MM-DD"\nupdated: "YYYY-MM-DD"\n---\n# UC-{XX}\n'
    )
    (templates_dir / "spec-template.md").write_text(
        '---\nid: SPEC-NNN\ntitle: "{規格標題}"\nstatus: draft\n'
        'created: "YYYY-MM-DD"\n---\n# SPEC-{NNN}\n'
    )

    return str(tmp_path)


class TestCreateProposal:
    """create proposal 的測試案例。"""

    def test_create_proposal_basic(self, tmp_path, capsys):
        """建立 proposal 應產生檔案並更新 tracking.yaml。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        args = argparse.Namespace(
            type="proposal", id="PROP-006", title="test-feature", domain=None,
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        output = capsys.readouterr().out
        assert "已建立" in output
        assert "PROP-006" in output

        # 檢查檔案是否存在
        created_file = tmp_path / "docs" / "proposals" / "PROP-006-test-feature.md"
        assert created_file.is_file()

        # 檢查 frontmatter 中的 id 已替換
        content = created_file.read_text()
        assert "id: PROP-006" in content

        # 檢查 tracking.yaml 已新增 entry
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        assert tracking.is_file()
        data = yaml.safe_load(tracking.read_text())
        assert isinstance(data["proposals"], list)
        entry = next(e for e in data["proposals"] if e["id"] == "PROP-006")
        assert entry["status"] == "draft"
        assert "confirmed_at" in entry
        # 對齊真實 proposals-tracking.yaml schema：頂層僅 proposals/usecases/specs 三區塊
        assert "last_updated" not in data
        assert "version" not in data
        assert set(data.keys()) == {"proposals", "usecases", "specs"}

    def test_create_proposal_against_real_list_format_tracking_file(self, tmp_path, capsys):
        """對真實 list-based tracking.yaml 新增 proposal 不應 crash（活 bug 回歸測試）。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        tracking.write_text(
            yaml.dump(
                {
                    "proposals": [
                        {"id": "PROP-001", "title": "既有提案", "status": "confirmed"},
                    ],
                    "usecases": [],
                    "specs": [],
                },
                allow_unicode=True,
                sort_keys=False,
            )
        )

        args = argparse.Namespace(
            type="proposal", id="PROP-007", title="new-feature", domain=None,
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        data = yaml.safe_load(tracking.read_text())
        assert isinstance(data["proposals"], list)
        ids = [e["id"] for e in data["proposals"]]
        assert "PROP-001" in ids
        assert "PROP-007" in ids

    def test_create_usecase(self, tmp_path, capsys):
        """建立 usecase 應產生檔案，不更新 tracking.yaml。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        args = argparse.Namespace(
            type="usecase", id="UC-09", title="scan-book", domain=None,
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        output = capsys.readouterr().out
        assert "已建立" in output

        created_file = tmp_path / "docs" / "usecases" / "UC-09-scan-book.md"
        assert created_file.is_file()

        content = created_file.read_text()
        assert "id: UC-09" in content

        # tracking.yaml 不應被建立（非 proposal）
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        assert not tracking.is_file()

    def test_create_duplicate_id_fails(self, tmp_path, capsys):
        """建立已存在的 ID 應報錯並結束。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        # 先建立一個 proposal
        existing = tmp_path / "docs" / "proposals" / "PROP-006-existing.md"
        existing.write_text("---\nid: PROP-006\nstatus: draft\n---\n# Existing\n")

        args = argparse.Namespace(
            type="proposal", id="PROP-006", title="new-title", domain=None,
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            try:
                execute(args)
            except SystemExit:
                pass

        output = capsys.readouterr().out
        assert "ID 已存在" in output

    def test_create_spec_requires_domain(self, tmp_path, capsys):
        """建立 spec 時未指定 --domain 應報錯。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        args = argparse.Namespace(
            type="spec", id="SPEC-009", title="test-spec", domain=None,
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            try:
                execute(args)
            except SystemExit:
                pass

        output = capsys.readouterr().out
        assert "domain" in output.lower()

    def test_create_spec_with_domain(self, tmp_path, capsys):
        """建立 spec 時指定 --domain 應在正確子目錄建立檔案。"""
        project_root = _setup_project(tmp_path)
        templates_dir = tmp_path / "templates"

        args = argparse.Namespace(
            type="spec", id="SPEC-009", title="auth-flow", domain="auth",
        )

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        output = capsys.readouterr().out
        assert "已建立" in output

        created_file = tmp_path / "docs" / "spec" / "auth" / "SPEC-009-auth-flow.md"
        assert created_file.is_file()

        content = created_file.read_text()
        assert "id: SPEC-009" in content
