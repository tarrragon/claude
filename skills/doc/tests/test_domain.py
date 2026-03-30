"""domain 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.domain import execute
from doc_system.core.file_locator import FileLocator


def _setup_spec_domains(tmp_path):
    """建立多個 domain 子目錄和 spec 檔案。"""
    for domain_name, specs in [
        ("core", [("core-systems.md", "SPEC-001", "Core Spec", ["UC-01", "UC-02"])]),
        ("extraction", [("extraction.md", "SPEC-002", "Extraction Spec", ["UC-03"])]),
    ]:
        d = tmp_path / "docs" / "spec" / domain_name
        d.mkdir(parents=True)
        for filename, fid, title, ucs in specs:
            uc_yaml = ", ".join(ucs)
            (d / filename).write_text(
                f"---\nid: {fid}\ntitle: \"{title}\"\nstatus: approved\n"
                f"related_usecases: [{uc_yaml}]\n---\n"
            )
    return str(tmp_path)


class TestDomainExecute:
    """domain.execute 的測試案例。"""

    def test_list_all_domains(self, tmp_path, capsys):
        """無參數應列出所有 domain。"""
        project_root = _setup_spec_domains(tmp_path)
        args = argparse.Namespace(domain_name=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "core" in output
        assert "extraction" in output

    def test_specific_domain(self, tmp_path, capsys):
        """指定 domain 應顯示該 domain 的 spec 和關聯 UC。"""
        project_root = _setup_spec_domains(tmp_path)
        args = argparse.Namespace(domain_name="core")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "SPEC-001" in output
        assert "Core Spec" in output
        assert "UC-01" in output

    def test_empty_domain(self, tmp_path, capsys):
        """空的 domain 應顯示無 spec 訊息。"""
        (tmp_path / "docs" / "spec" / "empty_domain").mkdir(parents=True)
        args = argparse.Namespace(domain_name="empty_domain")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "沒有 spec 文件" in output
