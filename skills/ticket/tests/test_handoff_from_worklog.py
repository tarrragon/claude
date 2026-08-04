"""
handoff --from-worklog 掃描範圍測試（0.2.1-W3-222）

驗證 _execute_from_worklog 的 ticket ID 抽取範圍限縮至交接段落，
不再掃整份 worklog（避免歷史 ticket ID 造成大量 false positive DRY-RUN）。
"""

import argparse
import os
import tempfile
from pathlib import Path

import pytest

from ticket_system.commands.handoff import _execute_from_worklog


@pytest.fixture
def temp_project() -> Path:
    """建立臨時專案根目錄（含 pubspec.yaml 標記）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        (project_root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _make_args(worklog_path: Path, dry_run: bool = True) -> argparse.Namespace:
    return argparse.Namespace(worklog_path=worklog_path, dry_run=dry_run)


class TestExecuteFromWorklogSectionScope:
    """驗證掃描範圍限縮至交接段落（W3-222）"""

    def test_ignores_historical_ids_outside_handoff_section(
        self, temp_project: Path, capsys
    ):
        """
        整份 worklog 含多個歷史 ticket ID（散落各處，非交接段），
        交接段只含 1-2 個目標 ID；修復後只應處理交接段內的 ID。
        """
        worklog_content = """# v0.2.1 工作日誌

## 0.2.1-W1-001 完成記錄

歷史工作：0.2.1-W1-001、0.2.1-W1-002、0.2.1-W1-003 均已完成。

## 0.2.1-W2-005 完成記錄

另一段歷史：0.2.1-W2-005、0.2.1-W2-006。

## 下個 Session 接手 Context

待處理：0.2.1-W3-999
"""
        worklog_path = temp_project / "v0.2.1-main.md"
        worklog_path.write_text(worklog_content, encoding="utf-8")

        rc = _execute_from_worklog(_make_args(worklog_path, dry_run=True))

        assert rc == 0
        captured = capsys.readouterr()
        # 交接段內的目標 ID 應出現
        assert "0.2.1-W3-999" in captured.out
        # 交接段外的歷史 ID 不應出現在輸出中
        assert "0.2.1-W1-001" not in captured.out
        assert "0.2.1-W1-002" not in captured.out
        assert "0.2.1-W1-003" not in captured.out
        assert "0.2.1-W2-005" not in captured.out
        assert "0.2.1-W2-006" not in captured.out

    def test_no_handoff_section_yields_no_ids(self, temp_project: Path, capsys):
        """無 handoff 關鍵字命中時，維持既有行為：提前 return，不掃描任何 ID"""
        worklog_content = """# v0.2.1 工作日誌

## 0.2.1-W1-001 完成記錄

一般記錄：0.2.1-W1-001、0.2.1-W1-002。
"""
        worklog_path = temp_project / "v0.2.1-main.md"
        worklog_path.write_text(worklog_content, encoding="utf-8")

        rc = _execute_from_worklog(_make_args(worklog_path, dry_run=True))

        assert rc == 0
        captured = capsys.readouterr()
        assert "未偵測到 handoff 段落" in captured.out
