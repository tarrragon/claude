"""兩個 DomainBundle 宣告相同 domain 值的檢查。

E2：兩份 bundle 宣告相同 domain，DOMAIN-MAP 驗證與 validate-paths 皆為紅，訊息含 domain 值與兩份路徑。
E1：把其中一份改成不同 domain 後，兩個入口皆為綠。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute, execute_paths
from doc_system.core.file_locator import FileLocator


def _bundle(root: Path, folder: str, domain: str) -> Path:
    path = root / f"docs/spec/{folder}/domain-map.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: DOMAIN-MAP-{folder}\ndomain: {domain}\n---\n# map\n", encoding="utf-8"
    )
    return path


def _run(root: Path, fn, args, capsys) -> tuple[int, str]:
    with patch.object(FileLocator, "get_project_root", return_value=str(root)):
        with pytest.raises(SystemExit) as exc:
            fn(args)
    return exc.value.code, capsys.readouterr().out


def _validate_map(root: Path, folder: str, capsys) -> tuple[int, str]:
    return _run(root, execute, argparse.Namespace(doc_id=f"DOMAIN-MAP-{folder}"), capsys)


def _validate_paths(root: Path, capsys) -> tuple[int, str]:
    return _run(root, execute_paths, argparse.Namespace(), capsys)


class TestDuplicateDomainRejected:
    def test_domain_map_validation_red_and_lists_both_paths(self, tmp_path, capsys):
        a = _bundle(tmp_path, "alpha", "shared")
        b = _bundle(tmp_path, "beta", "shared")
        code, out = _validate_map(tmp_path, "alpha", capsys)
        assert code == 1
        assert "shared" in out and str(a) in out and str(b) in out

    def test_validate_paths_red_and_lists_both_paths(self, tmp_path, capsys):
        a = _bundle(tmp_path, "alpha", "shared")
        b = _bundle(tmp_path, "beta", "shared")
        code, out = _validate_paths(tmp_path, capsys)
        assert code == 1
        assert "shared" in out and str(a) in out and str(b) in out

    def test_validate_paths_reports_every_duplicate_group(self, tmp_path, capsys):
        for folder, domain in [("a1", "x"), ("a2", "x"), ("b1", "y"), ("b2", "y"), ("c1", "z")]:
            _bundle(tmp_path, folder, domain)
        code, out = _validate_paths(tmp_path, capsys)
        assert code == 1
        assert "'x'" in out and "'y'" in out and "'z'" not in out


class TestDistinctDomainAccepted:
    """E1：與 E2 同一批 fixture，僅其中一份 domain 不同。"""

    def test_changed_domain_makes_both_entry_points_green(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", "shared")
        _bundle(tmp_path, "beta", "other")
        assert _validate_map(tmp_path, "alpha", capsys)[0] == 0
        assert _validate_paths(tmp_path, capsys)[0] == 0

    def test_duplicate_elsewhere_does_not_fail_unrelated_bundle(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", "shared")
        _bundle(tmp_path, "beta", "shared")
        _bundle(tmp_path, "gamma", "solo")
        assert _validate_map(tmp_path, "gamma", capsys)[0] == 0
