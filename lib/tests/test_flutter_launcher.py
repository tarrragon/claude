"""lib.flutter_launcher：依專案是否以 FVM 釘選版本決定 flutter／dart 的呼叫方式。

每個判定都以「有設定檔」與「無設定檔」同批對照，斷言兩者結果不同（E1）。
"""

import pytest

from lib.flutter_launcher import launch_argv, uses_fvm


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    return root


@pytest.mark.parametrize("marker", [".fvmrc", ".fvm/fvm_config.json"])
def test_marker_file_switches_to_fvm(project, marker):
    assert launch_argv(["flutter", "test"], project) == ["flutter", "test"]
    target = project / marker
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"flutter":"3.47.1"}')
    assert launch_argv(["flutter", "test"], project) == ["fvm", "flutter", "test"]


def test_dart_is_also_managed(project):
    (project / ".fvmrc").write_text("{}")
    assert launch_argv(["dart", "format", "lib"], project) == ["fvm", "dart", "format", "lib"]


def test_other_commands_unchanged(project):
    (project / ".fvmrc").write_text("{}")
    assert launch_argv(["uv", "run", "pytest"], project) == ["uv", "run", "pytest"]
    assert launch_argv(["fvm", "flutter", "test"], project) == ["fvm", "flutter", "test"]
    assert launch_argv([], project) == []


def test_marker_found_from_subdirectory(project):
    sub = project / "packages" / "app"
    sub.mkdir(parents=True)
    assert uses_fvm(sub) is False
    (project / ".fvmrc").write_text("{}")
    assert uses_fvm(sub) is True


def test_search_stops_at_project_root(tmp_path):
    (tmp_path / ".fvmrc").write_text("{}")  # 專案根之外的設定檔不算
    inner = tmp_path / "proj"
    (inner / ".git").mkdir(parents=True)
    assert uses_fvm(inner) is False
    assert uses_fvm(tmp_path) is True


def test_directory_named_fvmrc_is_not_a_marker(project):
    (project / ".fvmrc").mkdir()
    assert uses_fvm(project) is False
