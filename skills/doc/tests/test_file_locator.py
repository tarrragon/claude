"""file_locator 單元測試。"""

import os

from doc_system.core.file_locator import FileLocator


def _create_doc_tree(root):
    """在 root 下建立測試用的 docs/ 目錄結構。"""
    proposals = root / "docs" / "proposals"
    usecases = root / "docs" / "usecases"
    spec = root / "docs" / "spec" / "auth"

    proposals.mkdir(parents=True)
    usecases.mkdir(parents=True)
    spec.mkdir(parents=True)

    (proposals / "PROP-001-login.md").write_text("---\ntitle: Login\n---\n")
    (proposals / "PROP-002-export.md").write_text("---\ntitle: Export\n---\n")
    (usecases / "UC01-browse.md").write_text("---\ntitle: Browse\n---\n")
    (spec / "SPEC-auth-flow.md").write_text("---\ntitle: Auth Flow\n---\n")

    return root


class TestFindProposal:
    """find_proposal 測試。"""

    def test_find_existing_proposal(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.find_proposal("PROP-001")

        assert result is not None
        assert "PROP-001-login.md" in result

    def test_find_nonexistent_proposal(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.find_proposal("PROP-999")

        assert result is None


class TestFindUsecase:
    """find_usecase 測試。"""

    def test_find_existing_usecase(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.find_usecase("UC01")

        assert result is not None
        assert "UC01-browse.md" in result


class TestFindSpec:
    """find_spec 測試。"""

    def test_find_existing_spec(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.find_spec("SPEC-auth")

        assert result is not None
        assert "SPEC-auth-flow.md" in result


class TestPrecisePrefixMatch:
    """精確前綴匹配測試（修復 #1）。"""

    def test_uc01_does_not_match_uc010(self, tmp_path):
        """UC-01 搜尋不應匹配 UC-010。"""
        usecases = tmp_path / "docs" / "usecases"
        usecases.mkdir(parents=True)
        (usecases / "UC-01-import.md").write_text("---\ntitle: Import\n---\n")
        (usecases / "UC-010-bulk.md").write_text("---\ntitle: Bulk\n---\n")

        locator = FileLocator(str(tmp_path))

        result = locator.find_usecase("UC-01")

        assert result is not None
        assert "UC-01-import.md" in result
        assert "UC-010" not in result

    def test_exact_stem_match(self, tmp_path):
        """stem 完全等於 file_id 時應匹配。"""
        usecases = tmp_path / "docs" / "usecases"
        usecases.mkdir(parents=True)
        (usecases / "UC-01.md").write_text("---\ntitle: Exact\n---\n")

        locator = FileLocator(str(tmp_path))

        result = locator.find_usecase("UC-01")

        assert result is not None
        assert "UC-01.md" in result


class TestResolveFile:
    """resolve_file 公開方法測試（修復 #3：從 query.py 移至 file_locator.py）。"""

    def test_resolve_proposal(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.resolve_file("PROP-001")

        assert result is not None
        assert "PROP-001" in result

    def test_resolve_usecase(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.resolve_file("UC01")

        assert result is not None
        assert "UC01" in result

    def test_resolve_unknown_prefix(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.resolve_file("UNKNOWN-001")

        assert result is None


class TestListMethods:
    """list_proposals / list_usecases / list_specs 測試。"""

    def test_list_proposals(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.list_proposals()

        assert len(result) == 2

    def test_list_usecases(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.list_usecases()

        assert len(result) == 1

    def test_list_specs_with_domain(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.list_specs(domain="auth")

        assert len(result) == 1

    def test_list_specs_empty_domain(self, tmp_path):
        root = _create_doc_tree(tmp_path)
        locator = FileLocator(str(root))

        result = locator.list_specs(domain="nonexistent")

        assert result == []


class TestGetProjectRoot:
    """get_project_root 測試。"""

    def test_finds_root_from_subdir(self, tmp_path):
        _create_doc_tree(tmp_path)
        subdir = tmp_path / "some" / "nested" / "dir"
        subdir.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = FileLocator.get_project_root()
            assert result == str(tmp_path)
        finally:
            os.chdir(original_cwd)

    def test_env_var_takes_priority(self, tmp_path, monkeypatch):
        """CLAUDE_PROJECT_DIR 環境變數應優先於其他方式（修復 #2）。"""
        _create_doc_tree(tmp_path)
        env_dir = tmp_path / "env_root"
        env_dir.mkdir()

        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(env_dir))

        result = FileLocator.get_project_root()

        assert result == str(env_dir)
