"""doc validate DOMAIN-MAP-* 對 path_patterns 的檢查（格式、跨 bundle 重複、路徑存在性）。

E2：每條檢查各一個該紅 fixture，須 exit 1 並列出檔案、值與原因。
E1：合法 fixture（含不同 bundle 的巢狀前綴、缺欄位、空清單）須 exit 0。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import check_path_pattern_format, read_path_patterns


def _bundle(root: Path, domain: str, patterns: str | None) -> None:
    path = root / f"docs/spec/{domain}/domain-map.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = "" if patterns is None else f"path_patterns: {patterns}\n"
    path.write_text(
        f"---\nid: DOMAIN-MAP-{domain}\ndomain: {domain}\n{extra}---\n# map\n", encoding="utf-8"
    )


def _real_paths(root: Path) -> None:
    (root / "lib/ui").mkdir(parents=True, exist_ok=True)
    (root / "lib/ui/deep").mkdir(parents=True, exist_ok=True)
    (root / "pubspec.yaml").write_text("name: x\n", encoding="utf-8")


def _run(tmp_path: Path, doc_id: str) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            execute(argparse.Namespace(doc_id=doc_id))
    return exc.value.code


class TestValid:
    def test_field_absent_passes(self, tmp_path):
        _bundle(tmp_path, "alpha", None)
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 0

    def test_empty_list_passes(self, tmp_path):
        _bundle(tmp_path, "alpha", "[]")
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 0

    def test_nested_prefix_across_bundles_passes(self, tmp_path):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/ui/", "pubspec.yaml"]')
        _bundle(tmp_path, "beta", '["lib/ui/deep/"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 0
        assert _run(tmp_path, "DOMAIN-MAP-beta") == 0


class TestThreeState:
    def test_absent_and_explicit_empty_read_differently(self):
        assert read_path_patterns({"id": "x"}) is None
        assert read_path_patterns({"id": "x", "path_patterns": None}) is None
        assert read_path_patterns({"id": "x", "path_patterns": []}) == []
        assert read_path_patterns({"id": "x", "path_patterns": ["a/"]}) == ["a/"]

    def test_parsed_frontmatter_keeps_difference(self, tmp_path):
        from doc_system.commands.validate import _load_domain_bundles

        _bundle(tmp_path, "alpha", None)
        _bundle(tmp_path, "beta", "[]")
        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            bundles = _load_domain_bundles(str(tmp_path))
        assert read_path_patterns(bundles["DOMAIN-MAP-alpha"]) is None
        assert read_path_patterns(bundles["DOMAIN-MAP-beta"]) == []


class TestFormat:
    def test_backslash_rejected(self):
        assert check_path_pattern_format("lib\\ui/") is not None
        assert check_path_pattern_format("lib/ui/") is None

    @pytest.mark.parametrize(
        "bad",
        ["/lib/ui/", "./lib/ui/", "lib/../ui/", "lib/*/ui/", "lib/u?/", "lib/[a]/"],
    )
    def test_bad_format_fails_with_value(self, tmp_path, capsys, bad):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", f'["{bad}"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        out = capsys.readouterr().out
        assert "domain-map.md" in out and bad.replace("\\\\", "\\") in out

    def test_non_string_list_fails(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", "[1, 2]")
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert "path_patterns" in capsys.readouterr().out

    def test_scalar_instead_of_list_fails(self, tmp_path):
        _bundle(tmp_path, "alpha", "lib/ui/")
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1


class TestDuplicateAndExistence:
    def test_same_string_in_two_bundles_fails(self, tmp_path, capsys):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/ui/"]')
        _bundle(tmp_path, "beta", '["lib/ui/"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert "lib/ui/" in capsys.readouterr().out

    def test_duplicate_within_one_bundle_fails(self, tmp_path):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/ui/", "lib/ui/"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1

    def test_missing_path_fails(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", '["lib/ghost/"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert "lib/ghost/" in capsys.readouterr().out

    def test_directory_prefix_pointing_at_file_fails(self, tmp_path):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["pubspec.yaml/"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1

    def test_file_pattern_pointing_at_directory_fails(self, tmp_path):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/ui"]')
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
