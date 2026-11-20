"""create 建立端契約測試（3.5.0-W1-151.1.1）：title、範本註解、slug、spec 寫索引。"""

import argparse
from unittest.mock import patch

import yaml

from doc_system.commands.create import execute
from doc_system.core.file_locator import FileLocator
from tests.test_create import _setup_project

_COMMENTED_PROPOSAL_TEMPLATE = (
    "---\n# 提案模板說明\n# 複製本檔案\n\nid: PROP-NNN\n"
    'title: "{提案標題}"\nstatus: draft                    # draft / discussing\n'
    'source: ""                       # 允許值: development\n'
    'proposed_date: "YYYY-MM-DD"\n  # 縮排說明註解\n---\n'
    "# PROP-{NNN}: {提案標題}\n\n正文 # 不是註解\n"
)


def _run_create(tmp_path, commented=False, spec_template=None, **kwargs):
    project_root = _setup_project(tmp_path)
    templates_dir = tmp_path / "templates"
    if spec_template:
        (templates_dir / "spec-template.md").write_text(spec_template)
    if commented:
        (templates_dir / "proposal-template.md").write_text(_COMMENTED_PROPOSAL_TEMPLATE)
    with (
        patch.object(FileLocator, "get_project_root", return_value=project_root),
        patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
    ):
        execute(argparse.Namespace(**kwargs))


class TestCreateEstablishesTitle:
    def test_proposal_title_in_frontmatter_and_h1(self, tmp_path):
        _run_create(tmp_path, type="proposal", id="PROP-001", title="提案甲", domain=None)
        text = next((tmp_path / "docs" / "proposals").glob("PROP-001*.md")).read_text()
        assert 'title: "提案甲"' in text
        assert "# PROP-001: 提案甲" in text
        assert "{提案標題}" not in text

    def test_spec_title_in_frontmatter_and_h1(self, tmp_path):
        _run_create(
            tmp_path, spec_template='---\nid: SPEC-NNN\ntitle: "{規格標題}"\n---\n# {規格標題}\n',
            type="spec", id="SPEC-001", title="規格乙", domain="auth",
        )
        text = next((tmp_path / "docs" / "spec" / "auth").glob("SPEC-001*.md")).read_text()
        assert 'title: "規格乙"' in text
        assert "\n# 規格乙\n" in text


class TestCreateStripsTemplateComments:
    def test_frontmatter_comments_removed(self, tmp_path):
        _run_create(
            tmp_path, commented=True, type="proposal", id="PROP-001", title="t", domain=None,
        )
        text = next((tmp_path / "docs" / "proposals").glob("PROP-001*.md")).read_text()
        assert "提案模板說明" not in text
        assert "允許值" not in text
        assert "縮排說明註解" not in text
        assert "status: draft" in text
        assert 'source: ""' in text
        assert "正文 # 不是註解" in text


class TestCreateSlug:
    def test_ascii_slug_kept(self, tmp_path):
        _run_create(tmp_path, type="proposal", id="PROP-001", title="Hello World", domain=None)
        assert (tmp_path / "docs" / "proposals" / "PROP-001-hello-world.md").is_file()

    def test_cjk_dropped_from_slug(self, tmp_path):
        _run_create(
            tmp_path, type="proposal", id="PROP-001", title="Hello 世界 Feature", domain=None,
        )
        assert (tmp_path / "docs" / "proposals" / "PROP-001-hello-feature.md").is_file()

    def test_cjk_only_title_falls_back_to_id(self, tmp_path):
        _run_create(tmp_path, type="proposal", id="PROP-001", title="純中文標題", domain=None)
        assert (tmp_path / "docs" / "proposals" / "PROP-001.md").is_file()


class TestCreateSpecWritesTrackingIndex:
    def test_spec_registered_in_tracking_specs_section(self, tmp_path):
        _run_create(tmp_path, type="spec", id="SPEC-001", title="規格乙", domain="auth")
        data = yaml.safe_load((tmp_path / "docs" / "proposals-tracking.yaml").read_text())
        assert [s["id"] for s in data["specs"]] == ["SPEC-001"]
        assert data["specs"][0]["title"] == "規格乙"

    def test_spec_registration_appends_to_existing_entries(self, tmp_path):
        project_root = _setup_project(tmp_path)
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        tracking.write_text(yaml.dump({"proposals": [], "specs": [{"id": "SPEC-000"}]}))
        args = argparse.Namespace(type="spec", id="SPEC-001", title="x", domain="auth")
        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch(
                "doc_system.commands.create._get_templates_dir",
                return_value=tmp_path / "templates",
            ),
        ):
            execute(args)
        data = yaml.safe_load(tracking.read_text())
        assert [s["id"] for s in data["specs"]] == ["SPEC-000", "SPEC-001"]
