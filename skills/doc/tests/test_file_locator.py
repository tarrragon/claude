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

    def test_resolve_event(self, tmp_path):
        """EVT 型別的 domain-scoped ID 應能透過 resolve_file 解析（0.2.1-W3-1071 合併）。"""
        events_dir = tmp_path / "docs" / "events" / "balance"
        events_dir.mkdir(parents=True)
        (events_dir / "EVT-BALANCE-001-snapshot.md").write_text("---\nid: EVT-BALANCE-001\n---\n")

        locator = FileLocator(str(tmp_path))

        result = locator.resolve_file("EVT-BALANCE-001")

        assert result is not None
        assert "EVT-BALANCE-001-snapshot.md" in result


class TestFindEvent:
    """find_event 測試（0.2.1-W3-1071：合併 validate.py._find_event_file）。

    EVT 的 domain-scoped ID（如 EVT-LIBRARY-001）不在 FileLocator 原有
    的 PROP/UC/SPEC 固定前綴表中，find_event 是為此新增的專用方法，內部
    仍沿用與其他 find_* 方法相同的 _find_file_by_id 精確前綴比對邏輯。
    """

    def test_find_event_in_domain_subdirectory(self, tmp_path):
        events_dir = tmp_path / "docs" / "events" / "library"
        events_dir.mkdir(parents=True)
        (events_dir / "EVT-LIBRARY-001-checkout.md").write_text("---\nid: EVT-LIBRARY-001\n---\n")

        locator = FileLocator(str(tmp_path))

        result = locator.find_event("EVT-LIBRARY-001")

        assert result is not None
        assert "EVT-LIBRARY-001-checkout.md" in result

    def test_find_event_nonexistent_returns_none(self, tmp_path):
        (tmp_path / "docs").mkdir()
        locator = FileLocator(str(tmp_path))

        result = locator.find_event("EVT-LIBRARY-999")

        assert result is None

    def test_find_event_precise_prefix_no_false_match(self, tmp_path):
        """EVT-1 不應誤匹配 EVT-10（精確前綴比對，同 UC-01/UC-010 修復）。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        events_dir.mkdir(parents=True)
        (events_dir / "EVT-LIBRARY-1-a.md").write_text("---\nid: EVT-LIBRARY-1\n---\n")
        (events_dir / "EVT-LIBRARY-10-b.md").write_text("---\nid: EVT-LIBRARY-10\n---\n")

        locator = FileLocator(str(tmp_path))

        result = locator.find_event("EVT-LIBRARY-1")

        assert result is not None
        assert "EVT-LIBRARY-1-a.md" in result
        assert "EVT-LIBRARY-10" not in result


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


# ---------------------------------------------------------------------------
# resolve_code_root / 外接模式偵測（3.5.0-W1-151.1.8.1）
# ---------------------------------------------------------------------------
import subprocess  # noqa: E402

import pytest  # noqa: E402

from doc_system.core.file_locator import (  # noqa: E402
    CodeRootError,
    format_code_path,
    is_external_mode,
    resolve_code_root,
)


def _git(*args, cwd):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("commit", "-q", "--allow-empty", "-m", "init", cwd=path)
    return path


def _write_trace(root, body):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability.yaml").write_text(body, encoding="utf-8")


class TestExternalModeDetection:
    def test_env_unset_is_single_root(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert is_external_mode() is False

    def test_env_dir_outside_any_repo_is_external(self, tmp_path, monkeypatch):
        """正向對照：doc root 不在任何 git repo 內、cwd 在另一 repo，必為外接。"""
        repo = _init_repo(tmp_path / "analyst")
        ws = tmp_path / "ws"
        ws.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ws))
        monkeypatch.chdir(repo)
        assert is_external_mode() is True

    def test_env_dir_is_other_repo_is_external(self, tmp_path, monkeypatch):
        """正向對照：doc root 為另一個 repo，git dir 不同，判為外接。"""
        a = _init_repo(tmp_path / "a")
        b = _init_repo(tmp_path / "b")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(b))
        monkeypatch.chdir(a)
        assert is_external_mode() is True

    def test_same_repo_is_single(self, tmp_path, monkeypatch):
        repo = _init_repo(tmp_path / "r")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
        monkeypatch.chdir(repo)
        assert is_external_mode() is False

    def test_worktree_not_misjudged_as_external(self, tmp_path, monkeypatch):
        """CLAUDE_PROJECT_DIR 為主 checkout、cwd 在 worktree（反向亦然）不得誤判。"""
        main = _init_repo(tmp_path / "main")
        wt = tmp_path / "wt"
        _git("worktree", "add", "-q", str(wt), "-b", "feat", cwd=main)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
        monkeypatch.chdir(wt)
        assert is_external_mode() is False
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
        monkeypatch.chdir(main)
        assert is_external_mode() is False

    def test_cwd_not_in_repo_is_not_judged_external(self, tmp_path, monkeypatch):
        """cwd 不在 git repo 時無從比對，保守判為單根（不憑空要求 code_root）。"""
        ws = tmp_path / "ws"
        ws.mkdir()
        cwd = tmp_path / "plain"
        cwd.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ws))
        monkeypatch.chdir(cwd)
        assert is_external_mode() is False


class TestResolveCodeRoot:
    def test_single_no_key_falls_back_to_doc_root(self, tmp_path):
        _write_trace(tmp_path, "version: 1\n")
        r = resolve_code_root(str(tmp_path), external=False)
        assert r.path == str(tmp_path) and r.external is False

    def test_single_no_traceability_file_falls_back(self, tmp_path):
        assert resolve_code_root(str(tmp_path), external=False).path == str(tmp_path)

    def test_null_value_treated_as_absent(self, tmp_path):
        _write_trace(tmp_path, "code_root:\n")
        assert resolve_code_root(str(tmp_path), external=False).path == str(tmp_path)

    @pytest.mark.parametrize("value", ['""', '"   "', "123", "[a, b]"])
    def test_invalid_format_errors(self, tmp_path, value):
        _write_trace(tmp_path, f"code_root: {value}\n")
        with pytest.raises(CodeRootError, match="code_root"):
            resolve_code_root(str(tmp_path), external=False)

    def test_nonexistent_path_errors(self, tmp_path):
        _write_trace(tmp_path, "code_root: /no/such/dir/xyz\n")
        with pytest.raises(CodeRootError, match="不存在"):
            resolve_code_root(str(tmp_path), external=False)

    def test_valid_absolute_path(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        ws = tmp_path / "ws"
        _write_trace(ws, f"code_root: {repo}\n")
        r = resolve_code_root(str(ws), external=True)
        assert r.path == str(repo) and r.external is True

    def test_relative_path_resolved_against_doc_root(self, tmp_path):
        (tmp_path / "repo").mkdir()
        _write_trace(tmp_path / "ws", "code_root: ../repo\n")
        r = resolve_code_root(str(tmp_path / "ws"), external=True)
        assert os.path.realpath(r.path) == os.path.realpath(tmp_path / "repo")

    def test_external_without_code_root_errors_with_hint(self, tmp_path):
        """正向對照：外接模式未設定必須失敗，訊息指出設定方式，不退回 doc root。"""
        _write_trace(tmp_path, "version: 1\n")
        with pytest.raises(CodeRootError) as exc:
            resolve_code_root(str(tmp_path), external=True)
        assert "docs/traceability.yaml" in str(exc.value)
        assert "--code-root" in str(exc.value)

    def test_override_beats_config(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        _write_trace(tmp_path, f"code_root: {a}\n")
        assert resolve_code_root(str(tmp_path), override=str(b), external=True).path == str(b)

    def test_override_rescues_external_without_config(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        r = resolve_code_root(str(tmp_path), override=str(repo), external=True)
        assert r.path == str(repo)

    def test_override_nonexistent_errors(self, tmp_path):
        with pytest.raises(CodeRootError, match="不存在"):
            resolve_code_root(str(tmp_path), override=str(tmp_path / "nope"), external=False)

    def test_override_blank_errors(self, tmp_path):
        with pytest.raises(CodeRootError):
            resolve_code_root(str(tmp_path), override="  ", external=False)


class TestFormatCodePath:
    def test_external_gets_repo_prefix(self):
        assert format_code_path(os.path.join("lib", "a.dart"), True) == "repo:lib/a.dart"

    def test_single_unchanged(self):
        assert format_code_path("lib/a.dart", False) == "lib/a.dart"
