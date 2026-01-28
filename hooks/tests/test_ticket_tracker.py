#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""
ticket-tracker.py 測試套件

測試 CSV 式 Ticket 追蹤系統的核心功能。
"""

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# 取得腳本路徑
SCRIPT_PATH = Path(__file__).parent.parent / "ticket-tracker.py"


def run_tracker(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """執行 ticket-tracker.py 並回傳結果"""
    result = subprocess.run(
        ["uv", "run", str(SCRIPT_PATH)] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def temp_project(tmp_path: Path):
    """建立臨時專案目錄"""
    # 建立 pubspec.yaml 讓腳本能識別專案根目錄
    (tmp_path / "pubspec.yaml").write_text("name: test_project\n")
    (tmp_path / "docs" / "work-logs").mkdir(parents=True)
    return tmp_path


class TestInit:
    """測試 init 命令"""

    def test_init_creates_directory_and_csv(self, temp_project: Path):
        """初始化應該建立版本資料夾和空的 CSV"""
        returncode, stdout, _ = run_tracker(["init", "v0.1.0"], temp_project)

        assert returncode == 0
        assert "已初始化 v0.1.0" in stdout

        csv_path = temp_project / "docs" / "work-logs" / "v0.1.0" / "tickets.csv"
        assert csv_path.exists()

        # 驗證 CSV 只有標題行
        with open(csv_path) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 1  # 只有標題
            assert rows[0][0] == "ticket_id"

    def test_init_fails_if_exists(self, temp_project: Path):
        """如果已存在應該報錯"""
        run_tracker(["init", "v0.1.0"], temp_project)
        returncode, stdout, _ = run_tracker(["init", "v0.1.0"], temp_project)

        assert returncode == 1
        assert "已存在" in stdout


class TestAdd:
    """測試 add 命令"""

    def test_add_creates_ticket(self, temp_project: Path):
        """新增 Ticket 應該寫入 CSV"""
        run_tracker(["init", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        assert returncode == 0
        assert "已新增 T-001" in stdout

        # 驗證 CSV 內容
        csv_path = temp_project / "docs" / "work-logs" / "v0.1.0" / "tickets.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["ticket_id"] == "T-001"
            assert rows[0]["assigned"] == "false"
            assert rows[0]["completed"] == "false"

    def test_add_duplicate_fails(self, temp_project: Path):
        """重複的 ID 應該報錯"""
        run_tracker(["init", "v0.1.0"], temp_project)

        args = [
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ]

        run_tracker(args, temp_project)
        returncode, stdout, _ = run_tracker(args, temp_project)

        assert returncode == 1
        assert "已存在" in stdout


class TestClaim:
    """測試 claim 命令"""

    def test_claim_updates_status(self, temp_project: Path):
        """接手應該更新 assigned 和 started_at"""
        run_tracker(["init", "v0.1.0"], temp_project)
        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        returncode, stdout, _ = run_tracker([
            "claim", "T-001", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "已接手 T-001" in stdout

        # 驗證 CSV 內容
        csv_path = temp_project / "docs" / "work-logs" / "v0.1.0" / "tickets.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]["assigned"] == "true"
            assert rows[0]["started_at"] != ""

    def test_claim_already_claimed_fails(self, temp_project: Path):
        """已被接手應該報錯"""
        run_tracker(["init", "v0.1.0"], temp_project)
        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        run_tracker(["claim", "T-001", "--version", "v0.1.0"], temp_project)
        returncode, stdout, _ = run_tracker([
            "claim", "T-001", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 1
        assert "已被接手" in stdout


class TestComplete:
    """測試 complete 命令"""

    def test_complete_updates_status(self, temp_project: Path):
        """完成應該更新 completed"""
        run_tracker(["init", "v0.1.0"], temp_project)
        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)
        run_tracker(["claim", "T-001", "--version", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "complete", "T-001", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "已完成 T-001" in stdout

        # 驗證 CSV 內容
        csv_path = temp_project / "docs" / "work-logs" / "v0.1.0" / "tickets.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]["completed"] == "true"


class TestRelease:
    """測試 release 命令"""

    def test_release_clears_status(self, temp_project: Path):
        """放棄應該清除 assigned 和 started_at"""
        run_tracker(["init", "v0.1.0"], temp_project)
        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)
        run_tracker(["claim", "T-001", "--version", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "release", "T-001", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "已放棄 T-001" in stdout

        # 驗證 CSV 內容
        csv_path = temp_project / "docs" / "work-logs" / "v0.1.0" / "tickets.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]["assigned"] == "false"
            assert rows[0]["started_at"] == ""


class TestQuery:
    """測試 query 命令"""

    def test_query_shows_ticket(self, temp_project: Path):
        """查詢應該顯示 Ticket 詳情"""
        run_tracker(["init", "v0.1.0"], temp_project)
        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Test task",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        returncode, stdout, _ = run_tracker([
            "query", "T-001", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "T-001" in stdout
        assert "Test task" in stdout
        assert "parsley" in stdout

    def test_query_not_found_fails(self, temp_project: Path):
        """找不到應該報錯"""
        run_tracker(["init", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "query", "T-999", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 1
        assert "找不到" in stdout


class TestList:
    """測試 list 命令"""

    def test_list_shows_all(self, temp_project: Path):
        """列出應該顯示所有 Tickets"""
        run_tracker(["init", "v0.1.0"], temp_project)

        for i in range(3):
            run_tracker([
                "add",
                "--id", f"T-00{i+1}",
                "--log", f"v0.1.0-ticket-00{i+1}.md",
                "--who", "parsley",
                "--what", f"Task {i+1}",
                "--when", "Now",
                "--where", "lib/",
                "--why", "Testing",
                "--how", "TDD",
                "--version", "v0.1.0",
            ], temp_project)

        returncode, stdout, _ = run_tracker([
            "list", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "T-001" in stdout
        assert "T-002" in stdout
        assert "T-003" in stdout

    def test_list_filter_in_progress(self, temp_project: Path):
        """過濾進行中的 Tickets"""
        run_tracker(["init", "v0.1.0"], temp_project)

        run_tracker([
            "add",
            "--id", "T-001",
            "--log", "v0.1.0-ticket-001.md",
            "--who", "parsley",
            "--what", "Task 1",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        run_tracker([
            "add",
            "--id", "T-002",
            "--log", "v0.1.0-ticket-002.md",
            "--who", "sage",
            "--what", "Task 2",
            "--when", "Now",
            "--where", "lib/",
            "--why", "Testing",
            "--how", "TDD",
            "--version", "v0.1.0",
        ], temp_project)

        run_tracker(["claim", "T-001", "--version", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "list", "--in-progress", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "T-001" in stdout
        assert "T-002" not in stdout


class TestSummary:
    """測試 summary 命令"""

    def test_summary_shows_progress(self, temp_project: Path):
        """摘要應該顯示進度統計"""
        run_tracker(["init", "v0.1.0"], temp_project)

        for i in range(3):
            run_tracker([
                "add",
                "--id", f"T-00{i+1}",
                "--log", f"v0.1.0-ticket-00{i+1}.md",
                "--who", "parsley",
                "--what", f"Task {i+1}",
                "--when", "Now",
                "--where", "lib/",
                "--why", "Testing",
                "--how", "TDD",
                "--version", "v0.1.0",
            ], temp_project)

        run_tracker(["claim", "T-001", "--version", "v0.1.0"], temp_project)
        run_tracker(["complete", "T-001", "--version", "v0.1.0"], temp_project)

        returncode, stdout, _ = run_tracker([
            "summary", "--version", "v0.1.0"
        ], temp_project)

        assert returncode == 0
        assert "v0.1.0" in stdout
        assert "1/3" in stdout  # 1 完成，共 3 個
        assert "✅" in stdout  # 有完成的
        assert "⏸️" in stdout  # 有未接手的


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
