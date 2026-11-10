"""conftest session 級專案根重導的契約測試。

防止 hooks 測試套件把日誌寫進真實 .claude/hook-logs：套件執行期間
CLAUDE_PROJECT_DIR 必須指向含 CLAUDE.md 的 tmp 目錄，且 HOOK_TEST_ISOLATION=1。
"""

import os
from pathlib import Path


def test_project_dir_points_to_tmp_with_claude_md():
    project_dir = Path(os.environ["CLAUDE_PROJECT_DIR"])
    production_root = Path(__file__).resolve().parents[3]
    assert project_dir.resolve() != production_root
    assert (project_dir / "CLAUDE.md").is_file()


def test_hook_test_isolation_flag_is_set():
    assert os.environ.get("HOOK_TEST_ISOLATION") == "1"


def test_real_project_root_fixture_opts_out(real_project_root):
    assert "CLAUDE_PROJECT_DIR" not in os.environ
    assert "HOOK_TEST_ISOLATION" not in os.environ
    assert real_project_root == Path(__file__).resolve().parents[3]

