"""doc validate-paths：全部 DomainBundle path_patterns 與 docs/non-domain-paths.yaml 的檢查。

E2：每條檢查各一個該紅 fixture（格式、同檔重複、與 path_patterns 同字串、路徑不存在、缺鍵）。
E1：合法 fixture（檔案缺席、顯式 []、巢狀前綴）exit 0；缺席／顯式 []／缺鍵三者讀取結果對照。
"""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands import schema
from doc_system.commands.validate import execute_paths
from doc_system.core import tracking_schema
from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import (
    NON_DOMAIN_PATHS_FILE,
    NonDomainPathsFormatError,
    read_non_domain_paths,
)


def _bundle(root: Path, domain: str, patterns: str | None) -> None:
    path = root / f"docs/spec/{domain}/domain-map.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = "" if patterns is None else f"path_patterns: {patterns}\n"
    path.write_text(
        f"---\nid: DOMAIN-MAP-{domain}\ndomain: {domain}\n{extra}---\n# map\n", encoding="utf-8"
    )


def _write_nd(root: Path, text: str) -> None:
    path = root / NON_DOMAIN_PATHS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _real_paths(root: Path) -> None:
    (root / "lib/ui").mkdir(parents=True, exist_ok=True)
    (root / ".claude/skills").mkdir(parents=True, exist_ok=True)
    (root / "pubspec.yaml").write_text("name: x\n", encoding="utf-8")


def _run(root: Path) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(root)):
        with pytest.raises(SystemExit) as exc:
            execute_paths(argparse.Namespace())
    return exc.value.code


class TestReadThreeState:
    def test_absent_file_is_none(self, tmp_path):
        assert read_non_domain_paths(tmp_path) is None

    def test_explicit_empty_list(self, tmp_path):
        _write_nd(tmp_path, "non_domain_path_patterns: []\n")
        assert read_non_domain_paths(tmp_path) == []

    def test_listed_values(self, tmp_path):
        _write_nd(tmp_path, "non_domain_path_patterns:\n  - .claude/\n")
        assert read_non_domain_paths(tmp_path) == [".claude/"]

    @pytest.mark.parametrize("text", ["{}\n", "other: 1\n", "non_domain_path_patterns:\n", "non_domain_path_patterns: x/\n", "", "- a/\n"])
    def test_missing_key_or_non_list_is_format_error_not_absent(self, tmp_path, text):
        _write_nd(tmp_path, text)
        with pytest.raises(NonDomainPathsFormatError):
            read_non_domain_paths(tmp_path)

    def test_three_states_pairwise_distinct(self, tmp_path):
        absent = read_non_domain_paths(tmp_path)
        _write_nd(tmp_path, "non_domain_path_patterns: []\n")
        empty = read_non_domain_paths(tmp_path)
        _write_nd(tmp_path, "unrelated: 1\n")
        with pytest.raises(NonDomainPathsFormatError):
            read_non_domain_paths(tmp_path)
        assert absent is None and empty == [] and absent != empty


class TestValid:
    def test_repo_like_state_no_file_no_patterns_passes(self, tmp_path):
        _bundle(tmp_path, "alpha", None)
        assert _run(tmp_path) == 0

    def test_explicit_empty_passes(self, tmp_path):
        _write_nd(tmp_path, "non_domain_path_patterns: []\n")
        assert _run(tmp_path) == 0

    def test_nested_prefix_with_domain_passes(self, tmp_path):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/"]')
        _write_nd(tmp_path, "non_domain_path_patterns:\n  - lib/ui/\n  - .claude/\n  - pubspec.yaml\n")
        assert _run(tmp_path) == 0


class TestRedFixtures:
    def test_bad_format(self, tmp_path, capsys):
        _real_paths(tmp_path)
        _write_nd(tmp_path, 'non_domain_path_patterns: ["/abs/", "lib/*/"]\n')
        assert _run(tmp_path) == 1
        out = capsys.readouterr().out
        assert "non-domain-paths.yaml" in out and "/abs/" in out and "lib/*/" in out

    def test_duplicate_within_file(self, tmp_path, capsys):
        _real_paths(tmp_path)
        _write_nd(tmp_path, "non_domain_path_patterns: [.claude/, .claude/]\n")
        assert _run(tmp_path) == 1
        assert "重複" in capsys.readouterr().out

    def test_same_string_as_bundle_path_patterns(self, tmp_path, capsys):
        _real_paths(tmp_path)
        _bundle(tmp_path, "alpha", '["lib/ui/"]')
        _write_nd(tmp_path, "non_domain_path_patterns: [lib/ui/]\n")
        assert _run(tmp_path) == 1
        out = capsys.readouterr().out
        assert "lib/ui/" in out and "DOMAIN-MAP-alpha" in out

    def test_path_missing(self, tmp_path, capsys):
        _write_nd(tmp_path, "non_domain_path_patterns: [nowhere/]\n")
        assert _run(tmp_path) == 1
        assert "nowhere/" in capsys.readouterr().out

    def test_missing_key_is_failure_not_absent(self, tmp_path, capsys):
        _write_nd(tmp_path, "other: 1\n")
        assert _run(tmp_path) == 1
        assert "non_domain_path_patterns" in capsys.readouterr().out

    def test_bundle_problem_reported_too(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", '["nowhere/"]')
        assert _run(tmp_path) == 1
        assert "nowhere/" in capsys.readouterr().out


class TestSchemaExport:
    def test_export_carries_loader_location(self):
        exported = schema.build_schema_dict()
        assert exported["non_domain_paths_file"] == tracking_schema.NON_DOMAIN_PATHS_FILE
        assert exported["non_domain_paths_key"] == tracking_schema.NON_DOMAIN_PATHS_KEY
        json.dumps(exported)
