"""
handoff-auto-resume-stop-hook tests.

W17-095.2：驗證 should_preserve_pending_json 引用 is_handoff_stale 後的行為。
W17-118：驗證 scan_pending_handoff_tasks 在剛建 handoff 與 stale 並存時的時序語意：
- 剛建 handoff (< RECENT_HANDOFF_WINDOW_SECONDS) → recent_tasks，不阻塞
- stale + 非剛建 → GC 刪除，不計入 pending_tasks
- 純 active（非 stale 非剛建） → pending_tasks
- 邊界值 299 / 300 / 301 秒驗證
"""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock


HOOK_PATH = Path(__file__).parent.parent / "handoff-auto-resume-stop-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "handoff_auto_resume_stop_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_is_handoff_stale(monkeypatch, return_value):
    """以 monkeypatch 替換 module 的 is_handoff_stale，避開實際 ticket fs 依賴。"""
    hook = load_hook_module()
    monkeypatch.setattr(hook, "is_handoff_stale", lambda record, project_root=None: return_value)
    return hook


# ===== should_preserve_pending_json 行為驗證（W17-095.2）=====


def test_task_chain_target_in_progress_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 in_progress → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 in_progress")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_completed_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 completed → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_pending_should_preserve(monkeypatch):
    """任務鏈方向 + 目標仍 pending → 非 stale → return True（保留）。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True


def test_non_chain_with_completed_source_should_not_preserve(monkeypatch):
    """非任務鏈方向 + 來源 ticket 已 completed → stale → return False。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "來源 ticket 0.18.0-W17-001 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_non_chain_pending_should_preserve(monkeypatch):
    """非任務鏈方向 + 來源仍 pending → 非 stale → return True。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True


# ===== is_handoff_recently_created 邊界值（W17-118 Phase 2）=====


def test_recently_created_within_window():
    """timestamp 在 RECENT_HANDOFF_WINDOW_SECONDS 之內 → True。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=10)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is True


def test_recently_created_boundary_299s():
    """邊界值 299 秒（窗口內）→ True。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=299)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is True


def test_recently_created_boundary_301s():
    """邊界值 301 秒（窗口外）→ False。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=301)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is False


def test_recently_created_missing_timestamp():
    """timestamp 缺失 → 保守 False（走原路徑）。"""
    hook = load_hook_module()
    assert hook.is_handoff_recently_created({}, MagicMock()) is False


def test_recently_created_invalid_format():
    """timestamp 格式錯誤 → 保守 False（走原路徑）。"""
    hook = load_hook_module()
    record = {"timestamp": "not-a-timestamp"}
    assert hook.is_handoff_recently_created(record, MagicMock()) is False


# ===== scan_pending_handoff_tasks 整合場景（W17-118 Phase 1+2）=====


def _write_handoff(pending_dir: Path, ticket_id: str, *,
                   direction: str = "context_refresh",
                   timestamp: datetime = None,
                   resumed_at=None,
                   title: str = "test"):
    """輔助：寫一筆 handoff json 到 pending dir。"""
    pending_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "title": title,
        "resumed_at": resumed_at,
    }
    file_path = pending_dir / f"{ticket_id}.json"
    file_path.write_text(json.dumps(record), encoding="utf-8")
    return file_path


def _setup_scan(monkeypatch, tmp_path, *, stale_map=None,
                completed_map=None, recent_started=False):
    """
    建立 hook module 並 patch ticket fs 依賴：
    - is_handoff_stale: 依 stale_map[ticket_id] → (bool, str)
    - is_ticket_completed: 依 completed_map[ticket_id] → bool
    - is_ticket_recently_started: 統一回傳 recent_started
    """
    stale_map = stale_map or {}
    completed_map = completed_map or {}
    hook = load_hook_module()

    def fake_is_handoff_stale(record, project_root=None):
        tid = (record or {}).get("ticket_id", "")
        return stale_map.get(tid, (False, ""))

    monkeypatch.setattr(hook, "is_handoff_stale", fake_is_handoff_stale)
    monkeypatch.setattr(
        hook, "is_ticket_completed",
        lambda root, tid, log: completed_map.get(tid, False),
    )
    monkeypatch.setattr(
        hook, "is_ticket_recently_started",
        lambda root, tid, log: recent_started,
    )
    # 將 PENDING_DIR_NAME 指向 tmp_path
    monkeypatch.setattr(hook, "PENDING_DIR_NAME", "pending")
    return hook


def test_scan_recently_created_with_stale_goes_to_recent(monkeypatch, tmp_path):
    """剛建 handoff（< 300s）+ stale → recent_tasks（不阻塞、不 GC）。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-117",
        direction="to-sibling:W17-118",
        timestamp=datetime.now() - timedelta(seconds=30),
    )
    _write_handoff(
        pending_dir, "W17-115",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(seconds=3600),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={
            "W17-117": (True, "任務鏈目標已啟動"),  # stale 但剛建 → recent
            "W17-115": (True, "來源 completed"),     # stale 且非剛建 → GC
        },
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in recent] == ["W17-117"]
    assert pending == []
    # W17-115 應被 GC 刪除
    assert not (pending_dir / "W17-115.json").exists()
    # W17-117 仍保留（剛建，不 GC）
    assert (pending_dir / "W17-117.json").exists()


def test_scan_pure_stale_gets_gced(monkeypatch, tmp_path):
    """純 stale（任務鏈目標已啟動，非剛建）→ GC 刪除，不計入 pending。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-001",
        direction="to-sibling:W17-002",
        timestamp=datetime.now() - timedelta(hours=2),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={"W17-001": (True, "任務鏈目標已 in_progress")},
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert pending == []
    assert recent == []
    assert not (pending_dir / "W17-001.json").exists()


def test_scan_pure_active_goes_to_pending(monkeypatch, tmp_path):
    """純 active（非 stale 非剛建 非 recent_started）→ pending_tasks。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-200",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(monkeypatch, tmp_path, recent_started=False)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in pending] == ["W17-200"]
    assert recent == []


def test_scan_stale_plus_active_mixed(monkeypatch, tmp_path):
    """stale + active 混合 → stale 被 GC，active 進 pending。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-stale",
        direction="to-sibling:W17-target",
        timestamp=datetime.now() - timedelta(hours=2),
    )
    _write_handoff(
        pending_dir, "W17-active",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={"W17-stale": (True, "任務鏈目標已啟動")},
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in pending] == ["W17-active"]
    assert recent == []
    assert not (pending_dir / "W17-stale.json").exists()
    assert (pending_dir / "W17-active.json").exists()


def test_scan_multiple_active_all_blocking(monkeypatch, tmp_path):
    """多 active（皆非 stale 非剛建）→ 全進 pending（多任務 blocking 行為保留）。"""
    pending_dir = tmp_path / "pending"
    for tid in ("W17-A", "W17-B"):
        _write_handoff(
            pending_dir, tid,
            direction="context_refresh",
            timestamp=datetime.now() - timedelta(hours=1),
        )
    hook = _setup_scan(monkeypatch, tmp_path)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert sorted(t["ticket_id"] for t in pending) == ["W17-A", "W17-B"]
    assert recent == []


def test_scan_recently_created_pure_no_block(monkeypatch, tmp_path):
    """純剛建 handoff（非 stale）→ recent_tasks，不阻塞。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-117",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(seconds=10),
    )
    hook = _setup_scan(monkeypatch, tmp_path)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert pending == []
    assert [t["ticket_id"] for t in recent] == ["W17-117"]
    # 不應被 GC
    assert (pending_dir / "W17-117.json").exists()


# ===== W17-165 L2-C：terminal status 過濾（closed 也視為 terminal）=====


def test_terminal_statuses_includes_closed():
    """W17-165 L2-C：TERMINAL_STATUSES 集合包含 completed 與 closed。

    W17-197 修法：hook 不直接 re-export TERMINAL_STATUSES（W17-181.2 起 SSOT 移至
    ticket_system.constants），改為驗證 lib 端 constants 的 TERMINAL_STATUSES。
    """
    # 透過 hook 的 sys.path 設定取得 lib 端 TERMINAL_STATUSES
    load_hook_module()  # 確保 sys.path 已設定（hook 模組加 skills/ticket 父路徑）
    from ticket_system.constants import TERMINAL_STATUSES
    assert set(TERMINAL_STATUSES) == {"completed", "closed"}


def test_is_ticket_completed_returns_true_for_closed(monkeypatch, tmp_path):
    """W17-165 L2-C：closed 狀態應走 terminal 路徑（is_ticket_completed=True）。

    W17-197 修法：hook.is_ticket_completed delegate 至 lib `is_ticket_terminal`
    （W17-181.2 SSOT），原測試 monkeypatch hook 層級 find_ticket_file /
    parse_ticket_frontmatter 已不適用。改為 monkeypatch hook 內 `_lib_is_ticket_terminal`。
    """
    hook = load_hook_module()
    monkeypatch.setattr(
        hook, "_lib_is_ticket_terminal",
        lambda tid, project_root=None: True,
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is True


def test_is_ticket_completed_returns_true_for_completed(monkeypatch, tmp_path):
    """向後相容：completed 仍視為 terminal。

    W17-197 修法：同 closed 測試，改 monkeypatch lib delegate。
    """
    hook = load_hook_module()
    monkeypatch.setattr(
        hook, "_lib_is_ticket_terminal",
        lambda tid, project_root=None: True,
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is True


def test_is_ticket_completed_returns_false_for_in_progress(monkeypatch, tmp_path):
    """非 terminal 狀態（in_progress/pending）回 False。"""
    hook = load_hook_module()
    fake_path = tmp_path / "fake.md"
    fake_path.write_text("---\nstatus: in_progress\n---\n")
    monkeypatch.setattr(
        hook, "find_ticket_file",
        lambda tid, root, log: fake_path,
    )
    monkeypatch.setattr(
        hook, "parse_ticket_frontmatter",
        lambda path, log: {"status": "in_progress"},
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is False
