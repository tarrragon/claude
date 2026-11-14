"""
3.3.0-W1-060.3: release／finish 標 completed 後預設不推進下一版（版本空窗）

背景：下一版要等發版後回饋檢查決定（先發 patch 或直接開下一個 minor），
release／finish 原本在標 completed 後立即推進最小的 planned 版本，等於在
檢查前選定下一版。改為預設維持 planned，以 --activate-next 保留舊行為。
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import version_release as vr  # noqa: E402

TODOLIST_BODY = (
    'last_updated: "2026-11-12"\n\nversions:\n'
    '  - version: "3.3.0"\n    status: "completed"\n'
    '  - version: "3.4.0"\n    status: "planned"\n'
)


def _write_todolist(tmp_path: Path) -> Path:
    path = tmp_path / "todolist.yaml"
    path.write_text(TODOLIST_BODY, encoding="utf-8")
    return path


def _statuses(todolist: Path) -> dict:
    data = yaml.safe_load(todolist.read_text(encoding="utf-8"))
    return {v["version"]: v["status"] for v in data["versions"]}


def _advance(tmp_path: Path, monkeypatch, activate_next: bool) -> dict:
    """在同一份 fixture 上執行 advance_after_completion，回傳執行後的版本狀態。

    ensure_version_activated 的 worklog 與版本檔補齊依賴專案根目錄，這裡把
    專案根導向 tmp_path，只觀察 todolist 的狀態變化。
    """
    todolist = _write_todolist(tmp_path)
    monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)
    ok = vr.advance_after_completion(
        todolist, "3.3.0", dry_run=False, activate_next=activate_next
    )
    assert ok is True
    return _statuses(todolist)


class TestAdvanceAfterCompletion:
    def test_flag_changes_outcome(self, tmp_path, monkeypatch):
        """E1：同一份 fixture，傳與不傳 --activate-next 的結果不同"""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        without_flag = _advance(tmp_path / "a", monkeypatch, activate_next=False)
        with_flag = _advance(tmp_path / "b", monkeypatch, activate_next=True)
        assert without_flag != with_flag

    def test_default_keeps_next_planned(self, tmp_path, monkeypatch, capsys):
        """正向對照：預設標 completed 後，下一個 planned 維持 planned"""
        statuses = _advance(tmp_path, monkeypatch, activate_next=False)
        assert statuses == {"3.3.0": "completed", "3.4.0": "planned"}
        out = capsys.readouterr().out
        assert "version-release start --version" in out
        assert "--activate-next" in out

    def test_activate_next_promotes_planned(self, tmp_path, monkeypatch):
        """--activate-next 沿用舊行為，下一個 planned 轉 active"""
        statuses = _advance(tmp_path, monkeypatch, activate_next=True)
        assert statuses["3.3.0"] == "completed"
        assert statuses["3.4.0"] == "active"


@pytest.mark.parametrize("command", ["release", "finish"])
def test_subcommand_accepts_activate_next_flag(command):
    """release 與 finish 都接受 --activate-next"""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "version_release.py"), command, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--activate-next" in result.stdout
