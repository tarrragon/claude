"""
Pytest 測試配置

提供共用的 fixture 和測試工具
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib import liveness_session_isolation as _liveness_iso


_ISOLATED = {"root": None, "patch": None}


def pytest_configure(config):
    """collection 之前就重導專案根。

    Why：部分 hook 在模組層以 get_project_root() 計算日誌路徑常數
    （例：agent-dispatch-validation-hook 的 _EVENTS_JSONL_PATH），test 檔 import
    它時發生於 collection 階段，早於任何 fixture；只靠 session fixture 設環境變數
    會讓這類常數仍指向真實 hook-logs（同族 IMP-BAL-018）。
    """
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="hook_project_root_"))
    (root / "CLAUDE.md").write_text("# isolated test project root\n", encoding="utf-8")
    mp = pytest.MonkeyPatch()
    mp.setenv("CLAUDE_PROJECT_DIR", str(root))
    mp.setenv("HOOK_TEST_ISOLATION", "1")
    # 測試 session 專屬 id：漏網的 _liveness 寫入落在 pytest- 前綴檔，不併入呼叫者 session 檔
    mp.setenv(_liveness_iso.ENV_SESSION_ID, _liveness_iso.new_test_session_id())
    _ISOLATED["root"], _ISOLATED["patch"] = root, mp


def pytest_sessionfinish(session, exitstatus):
    """洩漏哨兵：真實 _liveness 出現 pytest- 前綴檔即令套件失敗（fail-closed）。"""
    _liveness_iso.apply_leak_sentinel(session, Path(__file__).resolve().parents[3])


def pytest_unconfigure(config):
    import shutil

    if _ISOLATED["patch"] is not None:
        _ISOLATED["patch"].undo()
    if _ISOLATED["root"] is not None:
        shutil.rmtree(_ISOLATED["root"], ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def isolate_project_root():
    """session 級：回傳 pytest_configure 建立的隔離專案根（含 CLAUDE.md 的 tmp 目錄）。

    Why：subprocess 執行的 hook 與自行解析根目錄的模組會繞過 isolate_hook_logs
    的 monkeypatch，把測試記錄（含 _liveness）寫進真實 .claude/hook-logs，
    污染 hook 健康檢查與 liveness 判斷。
    機制：CLAUDE_PROJECT_DIR 指向 tmp，HOOK_TEST_ISOLATION=1 使
    hook_base.get_project_root 略過 linked worktree 偵測；子程序繼承環境。
    環境變數由 pytest_configure 設定（見其 docstring），本 fixture 僅斷言其存在。
    斷言真實專案根的測試用 real_project_root。
    """
    assert _ISOLATED["root"] is not None, "pytest_configure 未建立隔離專案根"
    return _ISOLATED["root"]


@pytest.fixture(autouse=True)
def clear_caller_effort(monkeypatch):
    """清除呼叫者的 CLAUDE_EFFORT，使測試紅綠不取決於呼叫者環境。

    Why：effort=low 會抑制部分 hook 的 warn/info 輸出，斷言輸出的測試在
    CLAUDE_EFFORT=low 的環境下會翻紅。
    測 effort 行為的測試以 setenv / os.environ 賦值 / payload 顯式覆寫，
    本 fixture 只移除繼承自呼叫者的值，不影響顯式設定。
    """
    monkeypatch.delenv("CLAUDE_EFFORT", raising=False)


@pytest.fixture
def real_project_root(monkeypatch):
    """顯式 opt-out：本測試斷言真實專案根的解析行為，暫時移除 session 級重導。"""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    return Path(__file__).resolve().parents[3]


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

    與 session 級 isolate_project_root 的分工：本 fixture 只處理同程序內
    lib.hook_logging 的解析；subprocess hook 與自行拼 hook-logs 路徑的模組由
    session 級 fixture 以環境變數重導專案根（實測全套件僅 5 項
    斷言「真實專案根」的測試需 opt-out，見 real_project_root）。

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
    CLAUDE_PROJECT_DIR 指向 project_root，並同步注入 HOOK_TEST_ISOLATION=1。
    本機執行環境不是 git linked worktree 時（worktree 偵測回傳 None），
    CLAUDE_PROJECT_DIR 本就是第二優先，subprocess 可正確解析到假專案根；
    pytest 進程本身在 git linked worktree 內執行時（如 agent 在自己的 ticket
    worktree 內跑整套 hooks 測試），worktree 偵測（優先序高於 CLAUDE_PROJECT_DIR）
    會蓋過本 fixture 注入的隔離，subprocess 誤讀到真實 worktree 根目錄，計數器
    /節流檔等斷言失敗——同型根因與修法見
    ticket_system/lib/paths.py._resolve_project_root() 步驟 0（先前於 worktree
    環境下修復同型 ticket 系統測試隔離失效）。HOOK_TEST_ISOLATION=1 使
    .claude/lib/hook_base.get_project_root() 略過 worktree 偵測、優先採用
    CLAUDE_PROJECT_DIR，確保 subprocess 不受實際執行 cwd（是否位於 worktree）
    影響（呼應本票驗收「任意 cwd 結果一致」）。

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
    env = {"CLAUDE_PROJECT_DIR": str(project_root), "HOOK_TEST_ISOLATION": "1"}
    return project_root, env
