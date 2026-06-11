"""Skill-root 共用 pytest fixtures（W1-054）。

收斂背景：`tests/conftest.py` 與 `ticket_system/tests/conftest.py` 原各自
逐字維護 `_isolate_project_root` + `real_repo_root` 兩份副本（W1-050 引入）。
W1-050 Phase 4 兩視角發現此重複（linux 判 DRY 違規，docstring 已漂移為徵兆）。

收斂可行性（已實證，見 W1-054 Solution）：
- pyproject.toml 的 `[tool.pytest.ini_options]` 位於 skill root，故 pytest
  rootdir = skill root，且 `testpaths = ["tests", "ticket_system/tests"]`
  使兩樹共用單一 pytest session。
- skill-root `conftest.py` 對「在 rootdir 下任一 testpath 收集到的測試」皆生效，
  兩樹自然共享，無需 cross-rootdir 技巧。
- 故將共用 fixture 上提至此，兩子 conftest 移除副本（DRY 收斂成立）。

仍保留於各子 conftest 的 fixture（職責分裂合理，不上提）：
- `tests/conftest.py`：`_assert_no_repo_pollution`（依賴 `parents[4]` 相對路徑，
  與該檔位置耦合）、ticket data fixtures（`valid_ticket_data` 等）。
- `ticket_system/tests/conftest.py`：`_isolate_hook_logs_dir`、
  `_mock_track_snapshot_filesystem_scan`、precondition fixtures（僅該樹消費）。
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.fixture(autouse=True)
def _isolate_project_root(tmp_path_factory, monkeypatch):
    """Autouse fixture: 將 CLAUDE_PROJECT_DIR 預設導向 tmp，避免 lock 污染真實 repo。

    Why（W1-050）：`paths.get_project_root()` 第一優先讀 CLAUDE_PROJECT_DIR，
    未設時 fallback 至 `git rev-parse --show-toplevel`，解析到真實 repo root。
    測試若呼叫 `file_lock(get_ticket_path(...))` 但未 patch 路徑解析，lock 檔
    會落在真實 `docs/work-logs/v0/.../tickets/`（W14-042 設計不刪 lock 檔，
    產生殘留如 dummy.md.lock / 0.31.0-W4-001.md.lock）。

    設計（提供 default，個別測試可 override，opt-out 機制）：
    - autouse 在每個 test 前注入 CLAUDE_PROJECT_DIR 指向獨立 tmp 目錄
    - 需要真實 repo 或測試 fallback 行為的測試（如 test_paths_get_project_root）
      已用 `patch.dict("os.environ", {}, clear=True)` 或顯式 setenv 覆蓋；
      後注入者勝出，不影響其既有斷言（自然 opt-out）
    - 預先建立 docs/work-logs 階層，使 lock 路徑解析有合法落點
    """
    root = tmp_path_factory.mktemp("project-root-default")
    (root / "docs" / "work-logs").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))


@pytest.fixture
def real_repo_root(monkeypatch):
    """Opt-out fixture：將 CLAUDE_PROJECT_DIR 還原為真實 repo root。

    Why（W1-050）：少數測試刻意驗證真實 repo 下的版本自動偵測（version=None
    → 讀 docs/todolist.yaml / 掃 work-logs），autouse `_isolate_project_root`
    將 root 導向空 tmp 會使版本偵測先觸發 VERSION_NOT_DETECTED，遮蔽待測的
    後續錯誤路徑。這類測試走 early-exit 錯誤路徑（exit 1），不會抵達 file_lock，
    故在真實 repo root 執行無 lock 污染風險。

    使用（統一為簽名注入，W1-054）：在依賴真實版本偵測的測試函式簽名直接加入
    `real_repo_root` 參數即可（無需 `_use_real_repo_root` 中介 autouse fixture）。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
