"""
Pytest 測試配置

提供共用的 fixture 和測試工具
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def isolate_hook_logs(tmp_path, monkeypatch):
    """將 hook 日誌輸出隔離至 tmp_path，防止測試污染 production hook-logs。

    Why：部分 hook 測試（如 uv-tool-staleness-check 的 RuntimeError side_effect
    案例）會觸發 setup_hook_logging / run_hook_safely 將 traceback 寫入
    production .claude/hook-logs/，使 hook system health check 誤報 FAIL/ERROR
    （quality-baseline 規則 4：可觀測性信號不可被測試噪音污染）。

    機制：setup_hook_logging / save_check_log 解析日誌根目錄時，呼叫
    hook_utils.hook_logging 模組內綁定的 get_project_root。本 fixture 僅
    monkeypatch 該模組層綁定，使日誌目錄落在每個測試專屬的 tmp_path，而不影響
    其他模組（hook 主程式、ticket validator 等）各自 import 的 get_project_root
    或 CLAUDE_PROJECT_DIR 環境變數。

    為何不改 CLAUDE_PROJECT_DIR：環境變數會被 get_project_root 全域優先採用，
    連帶改變所有以相對路徑 / Path.cwd / 真實 repo 路徑解析的測試（路徑分類、
    handoff cache glob、cross-repo 判定），造成大量誤傷。僅綁定日誌模組的
    get_project_root 可精準隔離日誌寫入路徑。

    覆蓋語意：唯有當原 get_project_root 解析結果指向**真實 production repo**
    （即會污染 .claude/hook-logs/ 的情形）時，才改寫為隔離目錄。若測試已透過
    CLAUDE_PROJECT_DIR 環境變數或 chdir 到自己的 tmp_path 取得控制（如
    test_hook_utils 的 env 優先 / CLAUDE.md 搜尋 / cwd fallback 三類場景），
    解析結果非 production repo，本 fixture 不介入，既有日誌路徑斷言以測試設定
    為準。
    """
    import lib.hook_logging as _hl

    log_root = tmp_path / "hook_log_isolation"
    log_root.mkdir(parents=True, exist_ok=True)

    _original_get_project_root = _hl.get_project_root
    # 真實 production repo 根目錄（本 conftest 位於 <repo>/.claude/hooks/tests/）
    _production_root = Path(__file__).resolve().parents[3]

    def _isolated_get_project_root():
        resolved = _original_get_project_root()
        try:
            is_production = resolved.resolve() == _production_root
        except OSError:
            is_production = False
        # 僅在會污染 production hook-logs 時導向隔離目錄；
        # 測試已自行隔離（env / chdir 到 tmp）則沿用其解析結果。
        return log_root if is_production else resolved

    monkeypatch.setattr(_hl, "get_project_root", _isolated_get_project_root)
    yield log_root


@pytest.fixture
def tmp_project_root():
    """建立臨時專案根目錄結構"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 建立目錄結構
        (root / ".claude" / "handoff" / "pending").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "work-logs" / "v0.31.0" / "tickets").mkdir(parents=True, exist_ok=True)

        yield root


@pytest.fixture
def env_with_project_root(tmp_project_root):
    """設定環境變數指向臨時專案根目錄

    同時停用 hook_base.get_project_root() 的 worktree 偵測（0.38.1-W2-020）：
    偵測優先於 CLAUDE_PROJECT_DIR，若不停用，在 git linked worktree 環境下
    執行測試時會忽略此處設定的 tmp_project_root，一律回傳真實 worktree 根目錄。
    """
    with patch("lib.hook_base._linked_worktree_root", return_value=None):
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_project_root)}):
            yield tmp_project_root


@pytest.fixture
def mock_ppid():
    """模擬父進程 PID"""
    with patch("os.getppid", return_value=12345):
        yield 12345


@pytest.fixture
def sample_handoff_data():
    """範例 handoff 資料"""
    return {
        "ticket_id": "0.31.0-W15-001",
        "title": "測試任務",
        "direction": "continuation",
        "created_at": "2026-02-10T10:00:00",
        "resumed_at": None
    }


@pytest.fixture
def sample_session_state():
    """範例 session 狀態資料"""
    return {
        "locked_ticket_id": "0.31.0-W15-001",
        "locked_at": "2026-02-10T10:30:00"
    }


@pytest.fixture
def hook_project_env(tmp_path):
    """cwd 無關 + 自動清理的假專案根，供以 subprocess 執行 hook 的測試使用（0.2.1-W3-027）。

    Why：部分 hook（creation-acceptance-gate-hook 等）透過 get_project_root()
    （優先序：worktree 偵測 > CLAUDE_PROJECT_DIR > git rev-parse > cwd 向上搜尋）
    解析專案根，再以「project_root 相對路徑」尋找 ticket 檔（見
    lib.hook_ticket.find_ticket_file）。過去測試直接在真實 repo 下
    mkdir(parents=True) 建 fixture ticket 目錄，且 finally 只 unlink 檔案不刪
    目錄，會在 repo 留下空目錄殘留（PM 於 W3-025、W3-026 驗收時各手動清除一次）。

    機制：回傳 (project_root, env) — project_root 為 tmp_path（pytest 自動清理，
    無殘留風險）；env 為可直接傳入 _run_hook(..., env=env) 的字典，內含
    CLAUDE_PROJECT_DIR 指向 project_root。由於本機執行環境不是 git linked
    worktree（worktree 偵測回傳 None），CLAUDE_PROJECT_DIR 為第二優先，subprocess
    可正確解析到假專案根，不受實際執行 cwd 影響（呼應本票驗收「任意 cwd 結果一致」）。

    使用範例：
        def test_x(self, hook_project_env):
            project_root, env = hook_project_env
            ticket_dir = project_root / "docs/work-logs/v0.2.1/tickets"
            ticket_dir.mkdir(parents=True)
            (ticket_dir / "x.md").write_text("---\nid: x\n---\n")
            rc, out, err = _run_hook(HOOK, payload, env=env)

    何時改用真實路徑而非本 fixture：僅當測試目的就是驗證「hook 依實際專案根
    （非 CLAUDE_PROJECT_DIR override）解析路徑」的行為本身時，才使用真實路徑，
    且該情況下 finally 必須以 shutil.rmtree 移除整棵建立的目錄樹（而非只
    unlink 葉節點檔案），避免重蹈殘留覆轍。
    """
    project_root = tmp_path / "fake_project_root"
    project_root.mkdir(parents=True, exist_ok=True)
    env = {"CLAUDE_PROJECT_DIR": str(project_root)}
    return project_root, env
