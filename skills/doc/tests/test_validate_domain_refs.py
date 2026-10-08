"""doc validate 對 traverses 與 depends_on_domains 的已宣告 domain 檢查。

E2：值不是任何 DomainBundle 宣告的 domain 時，validate 須 exit 1 並列出檔案與欄位。
E1：同一批 fixture 換成已宣告的名稱，須 exit 0。
另含：語料沒有任何 DomainBundle 時不報錯（舊版語料）。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import find_undeclared_domain_names


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _domain_map(root: Path, domain: str) -> None:
    _write(
        root, f"docs/spec/{domain}/domain-map.md",
        f"---\nid: DOMAIN-MAP-{domain}\ndomain: {domain}\n---\n# map\n",
    )


def _uc(root: Path, traverses: str) -> None:
    _write(
        root, "docs/usecases/UC-01-sample.md",
        "---\nid: UC-01\ntitle: sample\n---\n# UC\n\n```yaml\nflow:\n"
        '  - id: "s1"\n    name: "step"\n    next: []\n    branch_from: null\n'
        f"    return_to: null\n    emits: []\n    consumes: []\n    traverses: {traverses}\n```\n",
    )


def _spec(root: Path, depends: str) -> None:
    _write(
        root, "docs/spec/ui/SPEC-001-sample.md",
        f"---\nid: SPEC-001\ndomain: ui\nsubdomain: null\ndepends_on_domains: {depends}\n---\n# spec\n",
    )


def _run(tmp_path: Path, doc_id: str) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            execute(argparse.Namespace(doc_id=doc_id))
    return exc.value.code


class TestFindUndeclaredDomainNames:
    def test_reports_names_outside_declared(self):
        assert find_undeclared_domain_names(["alpha", "Ghost"], {"alpha"}) == ["Ghost"]

    def test_all_declared_returns_empty(self):
        assert find_undeclared_domain_names(["alpha"], {"alpha"}) == []


class TestUcTraverses:
    def test_undeclared_traverses_fails_with_location(self, tmp_path, capsys):
        _domain_map(tmp_path, "alpha")
        _uc(tmp_path, '["Workspace"]')
        assert _run(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "UC-01-sample.md" in out and "traverses" in out and "Workspace" in out

    def test_declared_traverses_passes(self, tmp_path):
        _domain_map(tmp_path, "alpha")
        _uc(tmp_path, '["alpha"]')
        assert _run(tmp_path, "UC-01") == 0

    def test_no_bundle_corpus_not_checked(self, tmp_path):
        _uc(tmp_path, '["Workspace"]')
        assert _run(tmp_path, "UC-01") == 0


class TestSpecDependsOnDomains:
    def test_undeclared_depends_fails_with_location(self, tmp_path, capsys):
        _domain_map(tmp_path, "alpha")
        _spec(tmp_path, "[alpha, ghost]")
        assert _run(tmp_path, "SPEC-001") == 1
        out = capsys.readouterr().out
        assert "SPEC-001-sample.md" in out and "depends_on_domains" in out and "ghost" in out

    def test_declared_depends_passes(self, tmp_path):
        _domain_map(tmp_path, "alpha")
        _spec(tmp_path, "[alpha]")
        assert _run(tmp_path, "SPEC-001") == 0

    def test_no_bundle_corpus_not_checked(self, tmp_path):
        _spec(tmp_path, "[ghost]")
        assert _run(tmp_path, "SPEC-001") == 0
