"""DomainBundle 的 depends_on_bundles 出邊測試。

E1：同一個 DomainBundle fixture，帶與不帶出邊，解析產物必須不同。
E2：出邊指向不存在的 bundle 時，驗證必須報錯（正向對照輸入）。
另含邊型契約：新邊型為 proposed，established 邊型集合不變。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import (
    GRAPH_EDGE_TYPES,
    GRAPH_LAYER_ESTABLISHED,
    GRAPH_LAYER_PROPOSED,
    extract_bundle_dependencies,
    find_dangling_bundle_dependencies,
)

BASE_BUNDLE = {"id": "DOMAIN-MAP-alpha", "domain": "alpha"}

ESTABLISHED_EDGE_NAMES = frozenset(
    {
        "provenance", "spec_association", "uc_association", "proposal_association",
        "requirement_impl", "domain_dependency", "domain_coverage", "blood",
        "spawn", "blocking", "association", "discovery",
    }
)


class TestEdgeTypeContract:
    def test_bundle_dependency_edge_is_proposed(self):
        edge = GRAPH_EDGE_TYPES["bundle_dependency"]
        assert edge["forward_field"] == "depends_on_bundles"
        assert edge["layer"] == GRAPH_LAYER_PROPOSED
        assert edge["forward_cardinality"] == "many"
        assert edge["direction"] == "directed"

    def test_established_edges_unchanged(self):
        established = {
            n for n, v in GRAPH_EDGE_TYPES.items() if v["layer"] == GRAPH_LAYER_ESTABLISHED
        }
        assert established == ESTABLISHED_EDGE_NAMES


class TestExtractBundleDependenciesDiscrimination:
    """E1：帶與不帶 depends_on_bundles 的解析產物不同。"""

    def test_with_and_without_outgoing_edge_differ(self):
        without = extract_bundle_dependencies(dict(BASE_BUNDLE))
        with_edge = extract_bundle_dependencies(
            {**BASE_BUNDLE, "depends_on_bundles": ["DOMAIN-MAP-beta"]}
        )
        assert without != with_edge
        assert without == []
        assert with_edge == ["DOMAIN-MAP-beta"]

    def test_scalar_normalized_to_list(self):
        assert extract_bundle_dependencies(
            {**BASE_BUNDLE, "depends_on_bundles": "DOMAIN-MAP-beta"}
        ) == ["DOMAIN-MAP-beta"]

    def test_null_means_no_edges(self):
        assert extract_bundle_dependencies({**BASE_BUNDLE, "depends_on_bundles": None}) == []


class TestDanglingBundleDependencies:
    """E2：指向不存在 bundle 的出邊被報出；全部存在則為空。"""

    def test_dangling_target_reported(self):
        bundles = {
            "DOMAIN-MAP-alpha": {**BASE_BUNDLE, "depends_on_bundles": ["DOMAIN-MAP-ghost"]},
        }
        assert find_dangling_bundle_dependencies(bundles) == {
            "DOMAIN-MAP-alpha": ["DOMAIN-MAP-ghost"]
        }

    def test_existing_target_not_reported(self):
        bundles = {
            "DOMAIN-MAP-alpha": {**BASE_BUNDLE, "depends_on_bundles": ["DOMAIN-MAP-beta"]},
            "DOMAIN-MAP-beta": {"id": "DOMAIN-MAP-beta", "domain": "beta"},
        }
        assert find_dangling_bundle_dependencies(bundles) == {}


def _write_domain_map(root: Path, rel: str, frontmatter: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n# map\n", encoding="utf-8")


def _run_validate(tmp_path: Path, doc_id: str) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            execute(argparse.Namespace(doc_id=doc_id))
    return exc.value.code


class TestValidateCoversDependsOnBundles:
    def test_dangling_edge_fails_validation(self, tmp_path, capsys):
        _write_domain_map(
            tmp_path, "docs/spec/alpha/domain-map.md",
            "id: DOMAIN-MAP-alpha\ndomain: alpha\ndepends_on_bundles: [DOMAIN-MAP-ghost]",
        )
        assert _run_validate(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert "DOMAIN-MAP-ghost" in capsys.readouterr().out

    def test_resolvable_edge_passes_validation(self, tmp_path):
        _write_domain_map(
            tmp_path, "docs/spec/alpha/domain-map.md",
            "id: DOMAIN-MAP-alpha\ndomain: alpha\ndepends_on_bundles: [DOMAIN-MAP-beta]",
        )
        _write_domain_map(
            tmp_path, "docs/spec/beta/domain-map.md",
            "id: DOMAIN-MAP-beta\ndomain: beta",
        )
        assert _run_validate(tmp_path, "DOMAIN-MAP-alpha") == 0

    def test_no_edge_passes_validation(self, tmp_path):
        _write_domain_map(
            tmp_path, "docs/spec/alpha/domain-map.md", "id: DOMAIN-MAP-alpha\ndomain: alpha"
        )
        assert _run_validate(tmp_path, "DOMAIN-MAP-alpha") == 0
