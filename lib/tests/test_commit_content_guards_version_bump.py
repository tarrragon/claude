"""_check_branch_verify 對純版本號變動的放行判定 E2（tarrragon/claude#55）。

缺陷：finish 啟用提交 bump 版本檔（如 pubspec.yaml）後，保護分支上的
reference-transaction 守衛以「非豁免檔案」deny。修復：版本檔且 pre/post 的
差異只有版本欄位那一行時放行並留 info 紀錄；其他變動照舊 deny。
"""

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.commit_content_guards import StagedFile, _check_branch_verify  # noqa: E402

LOGGER_NAME = "test_version_bump_guard"

PUBSPEC_PRE = (
    "name: sample\n"
    "version: 0.1.0\n"
    "dependencies:\n"
    "  flutter:\n"
    "    sdk: flutter\n"
)


def _staged(rel_path: str, pre: str, post: str) -> StagedFile:
    return StagedFile(rel_path, pre, post, "")


def _run_on_main(sf: StagedFile, tmp_path: Path):
    with patch("lib.git_utils.get_current_branch", return_value="main"), patch(
        "lib.git_utils.get_project_root", return_value=tmp_path
    ):
        return _check_branch_verify(sf, logging.getLogger(LOGGER_NAME))


def test_version_line_only_change_is_allowed_with_info_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    post = PUBSPEC_PRE.replace("version: 0.1.0", "version: 0.1.1")
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        findings = _run_on_main(_staged("pubspec.yaml", PUBSPEC_PRE, post), tmp_path)
    assert findings == []
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "0.1.0" in messages and "0.1.1" in messages


def test_dependency_line_change_is_denied(tmp_path: Path) -> None:
    post = PUBSPEC_PRE.replace("sdk: flutter", "sdk: other")
    findings = _run_on_main(_staged("pubspec.yaml", PUBSPEC_PRE, post), tmp_path)
    assert [f.severity for f in findings] == ["deny"]


def test_version_and_dependency_change_together_is_denied(tmp_path: Path) -> None:
    post = PUBSPEC_PRE.replace("version: 0.1.0", "version: 0.1.1").replace(
        "sdk: flutter", "sdk: other"
    )
    findings = _run_on_main(_staged("pubspec.yaml", PUBSPEC_PRE, post), tmp_path)
    assert [f.severity for f in findings] == ["deny"]


def test_package_json_top_level_version_only_is_allowed(tmp_path: Path) -> None:
    pre = '{\n  "name": "a",\n  "version": "1.0.0",\n  "scripts": {"t": "x"}\n}\n'
    post = pre.replace('"1.0.0"', '"1.0.1"')
    assert _run_on_main(_staged("package.json", pre, post), tmp_path) == []


def test_pyproject_version_under_project_section_is_allowed(tmp_path: Path) -> None:
    pre = '[project]\nname = "a"\nversion = "0.1.0"\n\n[tool.x]\nversion = "9"\n'
    post = pre.replace('version = "0.1.0"', 'version = "0.2.0"')
    assert _run_on_main(_staged("pyproject.toml", pre, post), tmp_path) == []


def test_pyproject_version_under_other_section_is_denied(tmp_path: Path) -> None:
    pre = '[project]\nname = "a"\nversion = "0.1.0"\n\n[tool.x]\nversion = "9"\n'
    post = pre.replace('version = "9"', 'version = "10"')
    findings = _run_on_main(_staged("pyproject.toml", pre, post), tmp_path)
    assert [f.severity for f in findings] == ["deny"]


def test_monorepo_subdir_version_file_is_allowed(tmp_path: Path) -> None:
    post = PUBSPEC_PRE.replace("version: 0.1.0", "version: 0.1.1")
    assert _run_on_main(_staged("app/pubspec.yaml", PUBSPEC_PRE, post), tmp_path) == []


def test_non_version_file_with_version_looking_line_is_denied(tmp_path: Path) -> None:
    findings = _run_on_main(
        _staged("lib/config.yaml", "version: 1\n", "version: 2\n"), tmp_path
    )
    assert [f.severity for f in findings] == ["deny"]


def test_new_version_file_is_denied(tmp_path: Path) -> None:
    """pre 為空（新增檔案）不是版本 bump。"""
    findings = _run_on_main(_staged("pubspec.yaml", "", PUBSPEC_PRE), tmp_path)
    assert [f.severity for f in findings] == ["deny"]
