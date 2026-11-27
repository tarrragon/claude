"""version-consistency-guard-hook 測試（3.6.0-W1-090）。"""

import importlib.util
import logging
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "version_consistency_guard_hook",
    _HOOKS_DIR / "version-consistency-guard-hook.py",
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

LOGGER = logging.getLogger("test-vcg")


def _entry(version: str, status: str) -> str:
    return f'  - version: "{version}"\n    status: "{status}"\n'


def _project(tmp_path, entries=(), worklog_versions=()):
    docs = tmp_path / "docs"
    docs.mkdir()
    if entries:
        body = "versions:\n" + "".join(_entry(v, s) for v, s in entries)
    else:
        body = "meta:\n  project: x\n"
    (docs / "todolist.yaml").write_text(body, encoding="utf-8")
    for v in worklog_versions:
        major, minor, _ = v.split(".")
        (docs / "work-logs" / f"v{major}" / f"v{major}.{minor}" / f"v{v}").mkdir(parents=True)
    return tmp_path


def _run_main(monkeypatch, root, capsys):
    monkeypatch.setattr(hook, "get_shared_state_root", lambda _r: root)
    assert hook.main() == 0
    return capsys.readouterr().out


def test_registered_versions_parsed_from_list_entries(tmp_path):
    root = _project(tmp_path, [("3.0.0", "completed"), ("3.1.0", "active")])
    assert hook.get_registered_versions(root, LOGGER) == {"3.0.0", "3.1.0"}


def test_unregistered_worklog_version_warns(tmp_path, monkeypatch, capsys):
    root = _project(
        tmp_path,
        [("3.0.0", "completed"), ("3.1.0", "active")],
        worklog_versions=["3.0.0", "3.1.0", "3.2.0"],
    )
    out = _run_main(monkeypatch, root, capsys)
    assert "v3.2.0" in out
    assert "未在 todolist.yaml 中註冊" in out


def test_no_version_entries_warns_visibly(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, [])
    out = _run_main(monkeypatch, root, capsys)
    assert "解析不出任何版本條目" in out
    assert "All" not in out


def test_single_active_is_current_version(tmp_path):
    root = _project(tmp_path, [("3.0.0", "completed"), ("3.1.0", "active")])
    assert hook.resolve_current_version(root, LOGGER) == "3.1.0"


def test_zero_active_no_warning(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, [("3.0.0", "completed")], worklog_versions=["3.0.0"])
    assert hook.resolve_current_version(root, LOGGER) is None
    assert _run_main(monkeypatch, root, capsys).strip() == ""


def test_two_active_warns(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, [("3.0.0", "active"), ("3.1.0", "active")])
    out = _run_main(monkeypatch, root, capsys)
    assert "多個 active 版本" in out
