"""nav 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.nav import execute, _extract_refs
from doc_system.core.file_locator import FileLocator


def _create_uc(tmp_path, uc_id="UC-01"):
    """建立含引用欄位的 UC 文件。"""
    usecases_dir = tmp_path / "docs" / "usecases"
    usecases_dir.mkdir(parents=True)
    md = usecases_dir / f"{uc_id}-test.md"
    md.write_text(
        f"---\nid: {uc_id}\ntitle: \"Test UC\"\nstatus: approved\n"
        f"source_proposal: PROP-004\n"
        f"related_specs: [SPEC-001, SPEC-002]\n"
        f"related_usecases: [UC-02]\n---\n"
    )
    return str(tmp_path)


class TestNavExecute:
    """nav.execute 的測試案例。"""

    def test_nav_shows_refs(self, tmp_path, capsys):
        """導覽含引用的 UC 應顯示引用地圖。"""
        project_root = _create_uc(tmp_path)
        args = argparse.Namespace(doc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "UC-01" in output
        assert "source_proposal" in output
        assert "PROP-004" in output
        assert "SPEC-001" in output
        assert "SPEC-002" in output

    def test_nav_nonexistent_id(self, tmp_path, capsys):
        """導覽不存在的 ID 應顯示錯誤訊息。"""
        (tmp_path / "docs" / "usecases").mkdir(parents=True)
        args = argparse.Namespace(doc_id="UC-999")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "找不到文件" in output

    def test_extract_refs_with_outputs(self):
        """含 outputs 巢狀結構的 frontmatter 應正確展開引用。"""
        frontmatter = {
            "id": "PROP-001",
            "outputs": {
                "spec_refs": ["spec/core.md"],
                "usecase_refs": [],
                "ticket_refs": ["REF-SAMPLE-A"],
            },
            "related_proposals": [],
        }

        refs = _extract_refs(frontmatter)

        assert "spec_refs" in refs
        assert "spec/core.md" in refs["spec_refs"]
        assert "ticket_refs" in refs
        assert "REF-SAMPLE-A" in refs["ticket_refs"]
        # 空 list 不應出現
        assert "usecase_refs" not in refs
        assert "related_proposals" not in refs

    def test_nav_no_refs(self, tmp_path, capsys):
        """無引用的文件應顯示「無引用關聯」。"""
        usecases_dir = tmp_path / "docs" / "usecases"
        usecases_dir.mkdir(parents=True)
        md = usecases_dir / "UC-99-empty.md"
        md.write_text("---\nid: UC-99\ntitle: \"Empty UC\"\nstatus: draft\n---\n")
        args = argparse.Namespace(doc_id="UC-99")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "無引用關聯" in output


def _make_reverse_ref_project(tmp_path, prop_spec_refs=""):
    """PROP 未必填 spec_refs；SPEC 以純量、UC 以清單 source_proposal 指向它。"""
    (tmp_path / "docs" / "proposals").mkdir(parents=True)
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "usecases").mkdir(parents=True)
    (tmp_path / "docs" / "proposals" / "PROP-010-x.md").write_text(
        f"---\nid: PROP-010\ntitle: \"P\"\nstatus: draft\n{prop_spec_refs}---\n"
    )
    (tmp_path / "docs" / "spec" / "SPEC-010-x.md").write_text(
        "---\nid: SPEC-010\ntitle: \"S\"\nstatus: draft\nsource_proposal: PROP-010\n---\n"
    )
    (tmp_path / "docs" / "usecases" / "UC-10-x.md").write_text(
        "---\nid: UC-10\ntitle: \"U\"\nstatus: draft\nsource_proposal: [PROP-010, PROP-011]\n---\n"
    )
    return str(tmp_path)


class TestNavReverseLookup:
    """PROP 起點由 source_proposal 反查 SPEC／UC。"""

    def test_prop_without_spec_refs_finds_spec_and_uc(self, tmp_path, capsys):
        root = _make_reverse_ref_project(tmp_path)
        with patch.object(FileLocator, "get_project_root", return_value=root):
            execute(argparse.Namespace(doc_id="PROP-010"))
        out = capsys.readouterr().out
        assert "SPEC-010" in out
        assert "UC-10" in out
        assert "source_proposal" in out

    def test_spec_refs_mismatch_shows_both(self, tmp_path, capsys):
        root = _make_reverse_ref_project(tmp_path, "spec_refs: [SPEC-999]\n")
        with patch.object(FileLocator, "get_project_root", return_value=root):
            execute(argparse.Namespace(doc_id="PROP-010"))
        out = capsys.readouterr().out
        assert "SPEC-999" in out
        assert "非權威" in out
        assert "SPEC-010" in out

    def test_non_prop_start_has_no_reverse_section(self, tmp_path, capsys):
        root = _make_reverse_ref_project(tmp_path)
        with patch.object(FileLocator, "get_project_root", return_value=root):
            execute(argparse.Namespace(doc_id="UC-10"))
        assert "反查" not in capsys.readouterr().out
